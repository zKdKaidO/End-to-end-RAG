from __future__ import annotations

import argparse
import hashlib
import json
import time
import uuid
from pathlib import Path

import httpx


def require(response: httpx.Response, expected: int | tuple[int, ...] = 200) -> httpx.Response:
    allowed = (expected,) if isinstance(expected, int) else expected
    if response.status_code not in allowed:
        raise RuntimeError(f"HTTP_{response.status_code}:{response.request.method}:{response.request.url}:{response.text[:500]}")
    return response


def login(base_url: str, email: str, password: str) -> httpx.Client:
    client = httpx.Client(
        base_url=base_url,
        timeout=180.0,
        headers={"Origin": "http://localhost:15173"},
    )
    require(client.post("/api/v1/auth/login", json={"email": email, "password": password}))
    require(client.get("/api/v1/auth/me"))
    return client


def upload(client: httpx.Client, payload: bytes, filename: str, access: str) -> str:
    response = require(
        client.post(
            "/documents",
            params={"access": access},
            files={"file": (filename, payload, "application/pdf")},
        ),
        202,
    )
    return response.json()["document"]["id"]


def wait_indexed(client: httpx.Client, document_id: str, timeout_seconds: int = 240) -> dict:
    deadline = time.monotonic() + timeout_seconds
    latest: dict = {}
    while time.monotonic() < deadline:
        latest = require(client.get(f"/api/v1/documents/{document_id}")).json()
        if latest.get("indexing", {}).get("status") == "COMPLETED":
            return latest
        if "FAILED" in {
            latest.get("ingestion", {}).get("status"),
            latest.get("processing", {}).get("status"),
            latest.get("indexing", {}).get("status"),
        }:
            raise RuntimeError(f"DOCUMENT_PIPELINE_FAILED:{document_id}:{latest}")
        time.sleep(2)
    raise RuntimeError(f"DOCUMENT_PIPELINE_TIMEOUT:{document_id}:{latest}")


def document_ids(client: httpx.Client) -> set[str]:
    return {row.get("document_id", row.get("id")) for row in require(client.get("/documents")).json()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("seed", "verify"))
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--password", required=True)
    parser.add_argument("--state", default="/recovery-control/product-e2e-state.json")
    parser.add_argument("--fixture", default="/app/tests/fixtures/sample_legal.pdf")
    args = parser.parse_args()

    state_path = Path(args.state)
    admin = login(args.base_url, "recovery-admin@example.invalid", args.password)
    alice = login(args.base_url, "recovery-alice@example.invalid", args.password)
    bob = login(args.base_url, "recovery-bob@example.invalid", args.password)
    try:
        if args.mode == "seed":
            source = Path(args.fixture).read_bytes()
            global_id = upload(admin, source, "sample_legal_global.pdf", "global")
            private_payload = source + b"\n% isolated recovery private fixture\n"
            private_id = upload(alice, private_payload, "sample_legal_private.pdf", "private")
            global_document = wait_indexed(admin, global_id)
            private_document = wait_indexed(alice, private_id)
            state = {
                "global_document_id": global_id,
                "private_document_id": private_id,
                "global_sha256": hashlib.sha256(source).hexdigest(),
                "private_sha256": hashlib.sha256(private_payload).hexdigest(),
                "seeded_at_epoch": time.time(),
            }
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        else:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            global_document = require(admin.get(f"/api/v1/documents/{state['global_document_id']}")).json()
            private_document = require(alice.get(f"/api/v1/documents/{state['private_document_id']}")).json()

        global_id = state["global_document_id"]
        private_id = state["private_document_id"]
        admin_ids = document_ids(admin)
        alice_ids = document_ids(alice)
        bob_ids = document_ids(bob)
        if global_id not in admin_ids | alice_ids | bob_ids:
            raise RuntimeError("GLOBAL_DOCUMENT_NOT_VISIBLE")
        if not all(global_id in ids for ids in (admin_ids, alice_ids, bob_ids)):
            raise RuntimeError("GLOBAL_DOCUMENT_VISIBILITY_INCOMPLETE")
        if private_id not in alice_ids or private_id in bob_ids:
            raise RuntimeError("PRIVATE_DOCUMENT_ISOLATION_FAILED")
        require(bob.get(f"/documents/{private_id}"), 404)

        query = "Nghị định quy định những cơ chế, chính sách ưu đãi và ưu tiên nào?"
        retrieval = require(
            alice.post("/retrieve", json={"query_text": query, "document_ids": [private_id], "top_k_final": 5})
        ).json()
        if not retrieval["results"] or any(row["document_id"] != private_id for row in retrieval["results"]):
            raise RuntimeError("RETRIEVAL_SCOPE_OR_EMPTY_FAILED")

        chat_session = require(alice.post("/api/v1/chat/sessions", json={"title": "Recovery verification"}), 201).json()
        turn_response = require(
            alice.post(
                f"/api/v1/chat/sessions/{chat_session['id']}/turns/stream",
                json={"client_turn_id": str(uuid.uuid4()), "query": query, "document_ids": [private_id]},
            )
        )
        stream_text = turn_response.text
        if "event: done" not in stream_text:
            raise RuntimeError(f"CHAT_STREAM_NOT_COMPLETED:{stream_text[-500:]}")
        messages = require(alice.get(f"/api/v1/chat/sessions/{chat_session['id']}/messages")).json()["data"]
        assistant_messages = [item for item in messages if item["role"].upper() == "ASSISTANT"]
        if not assistant_messages or assistant_messages[-1]["delivery_state"] != "COMPLETED":
            raise RuntimeError("CHAT_HISTORY_NOT_FINALIZED")

        result = {
            "status": "PASS",
            "mode": args.mode,
            "documents": {
                "global": {"id": global_id, "status": global_document["indexing"]["status"]},
                "private": {"id": private_id, "status": private_document["indexing"]["status"]},
            },
            "visibility": {
                "admin_count": len(admin_ids),
                "alice_count": len(alice_ids),
                "bob_count": len(bob_ids),
                "private_hidden_from_bob": True,
            },
            "retrieval": {"count": len(retrieval["results"]), "document_scoped": True},
            "generation_history": {
                "sse_done": True,
                "assistant_status": assistant_messages[-1]["answer_status"],
                "citation_count": len(assistant_messages[-1]["citations"]),
                "prompt_version": assistant_messages[-1]["prompt_version"],
            },
        }
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    finally:
        admin.close()
        alice.close()
        bob.close()


if __name__ == "__main__":
    main()
