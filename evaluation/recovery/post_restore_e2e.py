from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from product_e2e import document_ids, login, require, upload, wait_indexed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--password", required=True)
    parser.add_argument("--fixture", default="/app/tests/fixtures/sample_legal.pdf")
    args = parser.parse_args()

    admin = login(args.base_url, "recovery-admin@example.invalid", args.password)
    bob = login(args.base_url, "recovery-bob@example.invalid", args.password)
    try:
        rejected = httpx.post(
            f"{args.base_url}/api/v1/auth/login",
            headers={"Origin": "http://localhost:15173"},
            json={"email": "recovery-alice@example.invalid", "password": args.password},
            timeout=30,
        )
        if rejected.status_code != 401:
            raise RuntimeError("DELETED_ACCOUNT_LOGIN_NOT_REJECTED")

        global_ids = document_ids(bob) & document_ids(admin)
        if not global_ids:
            raise RuntimeError("RESTORED_GLOBAL_DOCUMENT_MISSING")
        global_id = sorted(global_ids)[0]

        payload = Path(args.fixture).read_bytes() + b"\n% post-restore bob private fixture\n"
        private_id = upload(bob, payload, "post_restore_private.pdf", "private")
        private_document = wait_indexed(bob, private_id)
        require(admin.get(f"/documents/{private_id}"), 404)
        denied = bob.post(
            "/documents",
            params={"access": "global"},
            files={"file": ("forbidden_global.pdf", payload, "application/pdf")},
        )
        if denied.status_code != 403:
            raise RuntimeError("USER_GLOBAL_UPLOAD_RBAC_FAILED")

        query = "Nghị định quy định những chính sách ưu tiên nào để thu hút nguồn nhân lực chất lượng cao?"
        retrieval = require(
            bob.post("/retrieve", json={"query_text": query, "document_ids": [private_id], "top_k_final": 5})
        ).json()["results"]
        if not retrieval or any(item["document_id"] != private_id for item in retrieval):
            raise RuntimeError("POST_RESTORE_RETRIEVAL_FAILED")

        session = require(bob.post("/api/v1/chat/sessions", json={"title": "Post-restore E2E"}), 201).json()
        stream = require(
            bob.post(
                f"/api/v1/chat/sessions/{session['id']}/turns/stream",
                json={"client_turn_id": str(uuid.uuid4()), "query": query, "document_ids": [private_id]},
            )
        ).text
        if "event: done" not in stream:
            raise RuntimeError("POST_RESTORE_GENERATION_STREAM_FAILED")
        messages = require(bob.get(f"/api/v1/chat/sessions/{session['id']}/messages")).json()["data"]
        answer = next(item for item in messages if item["role"].upper() == "ASSISTANT")
        if answer["delivery_state"] != "COMPLETED" or not answer["citations"]:
            raise RuntimeError("POST_RESTORE_HISTORY_OR_CITATION_FAILED")

        print(json.dumps({
            "status": "PASS",
            "admin_login": "PASS",
            "user_login": "PASS",
            "deleted_account_login": "REJECTED",
            "restored_global_document_id": global_id,
            "new_private_document_id": private_id,
            "private_pipeline": private_document["indexing"]["status"],
            "private_isolation": "PASS",
            "admin_rbac": "PASS",
            "retrieval_count": len(retrieval),
            "generation_status": answer["answer_status"],
            "citation_snapshots": len(answer["citations"]),
            "history_delivery_state": answer["delivery_state"],
            "prompt_version": answer["prompt_version"],
        }, indent=2, sort_keys=True))
    finally:
        admin.close()
        bob.close()


if __name__ == "__main__":
    main()
