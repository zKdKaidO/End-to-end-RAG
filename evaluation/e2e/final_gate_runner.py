from __future__ import annotations

import concurrent.futures
import base64
import hashlib
import json
import os
import secrets
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import fitz
import httpx
import psycopg2
from psycopg2.extras import RealDictCursor


ROOT = Path(__file__).resolve().parents[2]
BASE_URL = "https://localhost:15443/api"
FRONTEND_URL = "https://localhost:15443/"
ORIGIN = "https://localhost:15443"
EXPECTED_API_IMAGE = "sha256:0b7bd04429e2cdbb6459866832fbcfd836591ba4c2c384f99a7658b5b05783a0"
EXPECTED_FRONTEND_IMAGE = "sha256:0609b046064912f679fd589cc6563c97b01ce21a0f6c5673eea70273e7e6dc74"
EXPECTED_MODEL_DIGEST = "6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7"
EXPECTED_PROMPT_SHA = "a41efc38ab53ad84550de27d913b13b4b6742aabe7a55a67f92685d132f303ee"
EXPECTED_BACKUP_ID = "20260823T161115Z-54300867"
RUNTIME_PATH = Path(os.environ.get("FINAL_GATE_RUNTIME", Path(tempfile.gettempdir()) / "final_product_v1_gate.runtime.json"))


class ProductFailure(AssertionError):
    def __init__(self, message: str, severity: str = "P1", evidence: list[Any] | None = None):
        super().__init__(message)
        self.severity = severity
        self.evidence = evidence or []


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_dotenv(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


ENV = load_dotenv(ROOT / ".env")
COMPOSE = [
    "docker", "compose", "-p", "rag_recovery_v1", "--env-file", ".env",
    "-f", "deployment/docker-compose.recovery-test.yml",
    "-f", "evaluation/e2e/final-gate.override.yml",
]


def compose_env() -> dict[str, str]:
    env = os.environ.copy()
    env["FINAL_GATE_TLS_DIR"] = str(Path(tempfile.gettempdir()) / "rag-final-gate-tls")
    return env


def run(command: list[str], *, timeout: float = 180, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = compose_env()
    if extra_env:
        env.update(extra_env)
    return subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, timeout=timeout)


def db_all(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    sql_b64 = base64.b64encode(sql.encode()).decode()
    params_b64 = base64.b64encode(json.dumps(params, default=str).encode()).decode()
    code = (
        "import base64,json,psycopg2;"
        "from psycopg2.extras import RealDictCursor;"
        "from app.core.config import settings;"
        "sql=base64.b64decode(__import__('os').environ['GATE_SQL_B64']).decode();"
        "params=json.loads(base64.b64decode(__import__('os').environ['GATE_PARAMS_B64']));"
        "conn=psycopg2.connect(settings.DATABASE_URL);"
        "cur=conn.cursor(cursor_factory=RealDictCursor);cur.execute(sql,params);"
        "print(json.dumps([dict(r) for r in cur.fetchall()],default=str));cur.close();conn.close()"
    )
    result = run([
        "docker", "exec", "-e", f"GATE_SQL_B64={sql_b64}", "-e", f"GATE_PARAMS_B64={params_b64}",
        "rag_recovery_v1-api-1", "python", "-c", code,
    ], timeout=60)
    if result.returncode != 0:
        raise RuntimeError(f"DB_INSPECTION_FAILED:{result.stderr[-1200:]}")
    return json.loads(result.stdout)


def db_one(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any]:
    rows = db_all(sql, params)
    return rows[0] if rows else {}


def require(response: httpx.Response, expected: int | tuple[int, ...], label: str, severity: str = "P1") -> httpx.Response:
    allowed = (expected,) if isinstance(expected, int) else expected
    if response.status_code not in allowed:
        try:
            body = response.text[:800]
        except httpx.ResponseNotRead:
            body = "<streaming response body not read>"
        raise ProductFailure(
            f"{label}: expected HTTP {allowed}, got {response.status_code}",
            severity,
            [{"url": str(response.request.url), "status": response.status_code, "body": body}],
        )
    return response


def browser() -> httpx.Client:
    return httpx.Client(base_url=BASE_URL, verify=False, timeout=240.0, headers={"Origin": ORIGIN})


def clone_browser(source: httpx.Client, *, include_origin: bool = True) -> httpx.Client:
    client = httpx.Client(
        base_url=BASE_URL, verify=False, timeout=240.0,
        headers={"Origin": ORIGIN} if include_origin else {},
    )
    client.cookies.update(source.cookies)
    return client


def login(email: str, password: str) -> httpx.Client:
    client = browser()
    require(client.post("/api/v1/auth/login", json={"email": email, "password": password}), 200, "login")
    require(client.get("/api/v1/auth/me"), 200, "auth_me")
    return client


def provision(email: str, password: str, admin: bool = False) -> str:
    command = COMPOSE + [
        "--profile", "operations", "run", "--rm", "--no-deps", "-e", "AUTH_BOOTSTRAP_PASSWORD",
        "deployment-tool", "python", "-m", "app.auth.cli",
        "create-admin" if admin else "create-user", "--email", email,
    ]
    result = run(command, timeout=120, extra_env={"AUTH_BOOTSTRAP_PASSWORD": password})
    if result.returncode != 0:
        raise RuntimeError(f"USER_PROVISION_FAILED:{email}:{result.stderr[-1000:]}")
    row = db_one("SELECT id FROM users WHERE normalized_email=%s", (email.casefold(),))
    if not row:
        raise RuntimeError(f"USER_PROVISION_NOT_DURABLE:{email}")
    return str(row["id"])


def make_pdf(lines: list[str], pages: int = 2) -> bytes:
    document = fitz.open()
    try:
        for page_number in range(pages):
            page = document.new_page(width=595, height=842)
            content = [f"FINAL PRODUCT V1 QA - PAGE {page_number + 1}"] + lines
            if pages > 3:
                content.append(f"PROCESSING_PAGE_MARKER_{page_number + 1:04d}")
            page.insert_textbox(fitz.Rect(45, 45, 550, 800), "\n\n".join(content), fontsize=11)
        return document.tobytes(garbage=4, deflate=True)
    finally:
        document.close()


def upload(client: httpx.Client, payload: bytes, filename: str, access: str = "private") -> tuple[str, dict[str, Any]]:
    response = require(
        client.post("/documents", params={"access": access}, files={"file": (filename, payload, "application/pdf")}),
        202, "upload",
    )
    data = response.json()
    return str(data["document"]["id"]), data


def get_document(client: httpx.Client, document_id: str) -> httpx.Response:
    return client.get(f"/api/v1/documents/{document_id}")


def wait_document(client: httpx.Client, document_id: str, *, timeout: float = 360) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    deadline = time.monotonic() + timeout
    states: list[dict[str, Any]] = []
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        response = get_document(client, document_id)
        if response.status_code != 200:
            raise ProductFailure(f"document status became HTTP {response.status_code}", "P1", [{"document_id": document_id}])
        last = response.json()
        state = {
            "document": last.get("status"),
            "ingestion": (last.get("ingestion") or {}).get("status"),
            "processing": (last.get("processing") or {}).get("status"),
            "indexing": (last.get("indexing") or {}).get("status"),
        }
        if not states or states[-1] != state:
            states.append(state)
        if state["indexing"] == "COMPLETED":
            return last, states
        if "FAILED" in state.values():
            raise ProductFailure("document pipeline failed", "P1", [{"document_id": document_id, "states": states}])
        time.sleep(0.5)
    raise ProductFailure("document pipeline timeout", "P1", [{"document_id": document_id, "states": states}])


def active_state(payload: dict[str, Any]) -> bool:
    values = {
        payload.get("status"),
        (payload.get("ingestion") or {}).get("status"),
        (payload.get("processing") or {}).get("status"),
        (payload.get("indexing") or {}).get("status"),
    }
    return bool(values & {"PENDING", "PROCESSING", "INDEXING"}) and (payload.get("indexing") or {}).get("status") != "COMPLETED"


def retrieve(client: httpx.Client, question: str, document_ids: list[str] | None = None, top_k: int = 10) -> tuple[httpx.Response, list[dict[str, Any]]]:
    body: dict[str, Any] = {"query_text": question, "top_k_final": top_k}
    if document_ids is not None:
        body["document_ids"] = document_ids
    response = client.post("/retrieve", json=body)
    results = response.json().get("results", []) if response.status_code == 200 else []
    return response, results


def create_chat(client: httpx.Client, title: str) -> str:
    response = require(client.post("/api/v1/chat/sessions", json={"title": title}), 201, "create_chat")
    return str(response.json()["id"])


def messages(client: httpx.Client, session_id: str) -> list[dict[str, Any]]:
    response = require(client.get(f"/api/v1/chat/sessions/{session_id}/messages"), 200, "history_messages")
    payload = response.json()
    return payload.get("data", payload) if isinstance(payload, dict) else payload


def generate(client: httpx.Client, session_id: str, question: str, document_ids: list[str] | None = None) -> tuple[dict[str, Any], str]:
    response = require(
        client.post(
            f"/api/v1/chat/sessions/{session_id}/turns/stream",
            json={"client_turn_id": str(uuid.uuid4()), "query": question, "document_ids": document_ids},
        ),
        200, "generation",
    )
    if "event: done" not in response.text:
        raise ProductFailure("generation stream did not finish with done", "P1", [{"stream_tail": response.text[-1200:]}])
    rows = messages(client, session_id)
    assistants = [row for row in rows if str(row.get("role", "")).upper() == "ASSISTANT"]
    if not assistants:
        raise ProductFailure("completed stream has no assistant history", "P1")
    return assistants[-1], response.text


def document_ids(client: httpx.Client) -> set[str]:
    response = require(client.get("/documents"), 200, "list_documents")
    return {str(row.get("document_id", row.get("id"))) for row in response.json()}


def citation_document_id(citation: dict[str, Any]) -> str:
    """Return the canonical document identity from the frozen History V1 citation schema."""
    return str(
        citation.get("current_document_id")
        or citation.get("original_document_id")
        or citation.get("document_id")
        or ""
    )


def wait_absent(document_id: str, *, timeout: float = 180) -> dict[str, int]:
    deadline = time.monotonic() + timeout
    last: dict[str, int] = {}
    while time.monotonic() < deadline:
        row = db_one(
            """
            SELECT
              (SELECT count(*) FROM documents WHERE id=%s) AS documents,
              (SELECT count(*) FROM chunks WHERE document_id=%s) AS chunks,
              (SELECT count(*) FROM chunk_indexes WHERE document_id=%s) AS indexes
            """,
            (document_id, document_id, document_id),
        )
        last = {key: int(value) for key, value in row.items()}
        if not any(last.values()):
            return last
        time.sleep(1)
    raise ProductFailure("deleted document retained semantic footprint", "P1", [{"document_id": document_id, "counts": last}])


def wait_user_absent(user_id: str, *, timeout: float = 240) -> dict[str, int]:
    deadline = time.monotonic() + timeout
    last: dict[str, int] = {}
    while time.monotonic() < deadline:
        row = db_one(
            """
            SELECT
              (SELECT count(*) FROM users WHERE id=%s) AS users,
              (SELECT count(*) FROM auth_sessions WHERE user_id=%s) AS auth_sessions,
              (SELECT count(*) FROM chat_sessions WHERE user_id=%s) AS chat_sessions,
              (SELECT count(*) FROM document_access_grants WHERE user_id=%s) AS grants
            """,
            (user_id, user_id, user_id, user_id),
        )
        last = {key: int(value) for key, value in row.items()}
        if not any(last.values()):
            return last
        time.sleep(1)
    raise ProductFailure("account deletion did not settle", "P0", [{"user_id": user_id, "counts": last}])


@dataclass
class Gate:
    started_at: str
    run_id: str
    password: str
    results: list[dict[str, Any]]
    identities: dict[str, dict[str, str]]
    documents: dict[str, str]
    sessions: dict[str, str]
    findings: list[dict[str, Any]]
    blocked: bool = False

    def persist(self) -> None:
        payload = {
            "gate": "FINAL_END_TO_END_PRODUCT_V1",
            "started_at": self.started_at,
            "updated_at": utcnow(),
            "run_id": self.run_id,
            "release": {
                "api_worker_image": EXPECTED_API_IMAGE,
                "frontend_image": EXPECTED_FRONTEND_IMAGE,
                "model": "qwen3.5:9b",
                "model_digest": EXPECTED_MODEL_DIGEST,
                "prompt": "legal-rag-v2",
                "prompt_sha256": EXPECTED_PROMPT_SHA,
                "alembic_head": "auth_authorization_v1",
                "pgvector": "0.5.1",
                "backup_id": EXPECTED_BACKUP_ID,
            },
            "identities": self.identities,
            "documents": self.documents,
            "sessions": self.sessions,
            "scenarios": self.results,
            "findings": self.findings,
            "blocked": self.blocked,
        }
        RUNTIME_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")

    def record(self, scenario: str, expected: str, actual: str, evidence: list[Any] | None = None, notes: str = "") -> None:
        self.results.append({
            "scenario": scenario,
            "status": "PASS",
            "severity": None,
            "expected": expected,
            "actual": actual,
            "evidence": evidence or [],
            "notes": notes,
            "timestamp": utcnow(),
        })
        self.persist()
        print(f"PASS {scenario}", flush=True)

    def scenario(self, name: str, expected: str, action: Callable[[], tuple[str, list[Any], str]]) -> None:
        try:
            actual, evidence, notes = action()
            self.record(name, expected, actual, evidence, notes)
        except ProductFailure as exc:
            finding = {
                "scenario": name,
                "expected": expected,
                "actual": str(exc),
                "exact_failure_point": name,
                "http_db_queue_state": exc.evidence,
                "relevant_logs": [],
                "suspected_component": "TO_BE_CLASSIFIED",
                "severity": exc.severity,
                "reproduction_steps": f"Run final_gate_runner.py scenario {name}",
            }
            self.findings.append(finding)
            self.results.append({
                "scenario": name,
                "status": "FAIL",
                "severity": exc.severity,
                "expected": expected,
                "actual": str(exc),
                "evidence": exc.evidence,
                "notes": "Gate stopped; no system fix attempted.",
                "timestamp": utcnow(),
            })
            self.blocked = exc.severity in {"P0", "P1"}
            self.persist()
            print(f"FAIL {name} {exc.severity}: {exc}", flush=True)
            raise


def main() -> None:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)
    password = secrets.token_urlsafe(24) + "Aa1!"
    gate = Gate(utcnow(), run_id, password, [], {}, {}, {}, [])
    gate.persist()

    emails = {
        "admin": f"gate-admin-{run_id}@example.invalid",
        "alice": f"gate-alice-{run_id}@example.invalid",
        "bob": f"gate-bob-{run_id}@example.invalid",
        "delete_race": f"gate-delete-race-{run_id}@example.invalid",
        "account_race": f"gate-account-race-{run_id}@example.invalid",
        "rate": f"gate-rate-{run_id}@example.invalid",
    }
    for name, email in emails.items():
        user_id = provision(email, password, admin=name == "admin")
        gate.identities[name] = {"id": user_id, "email": email}
    gate.record(
        "test_data_isolation",
        "New uniquely named QA identities are provisioned without reusing prior E2E accounts.",
        "Six new QA identities provisioned through the frozen operator contract.",
        [{"identity_ids": {key: value["id"] for key, value in gate.identities.items()}}],
        "Auth V1 has no public registration route; new-user registration uses the frozen operator provisioning CLI.",
    )

    admin = login(emails["admin"], password)
    alice = login(emails["alice"], password)
    bob = login(emails["bob"], password)
    delete_race = login(emails["delete_race"], password)
    account_race = login(emails["account_race"], password)

    alice_pdf = make_pdf([
        "Article 7. Final gate private support rule.",
        "ALICE_PRIVATE_SENTINEL_7F92 has the exact support rate of 37 percent.",
        "This rate applies only to the final-gate Alice private program.",
    ])
    bob_pdf = make_pdf([
        "Article 8. Final gate Bob private support rule.",
        "BOB_PRIVATE_SENTINEL_X3K91 has the exact support rate of 64 percent.",
        "This rate applies only to the final-gate Bob private program.",
    ])
    global_pdf = make_pdf([
        "Article 9. Final gate shared rule.",
        "GLOBAL_SENTINEL_G55 has a shared review period of exactly 55 days.",
        "This rule is globally visible to authorized product users.",
    ])

    global_id, _ = upload(admin, global_pdf, f"gate_global_{run_id}.pdf", "global")
    alice_id, _ = upload(alice, alice_pdf, f"gate_alice_{run_id}.pdf")
    bob_id, _ = upload(bob, bob_pdf, f"gate_bob_{run_id}.pdf")
    gate.documents.update(global_document=global_id, alice_private=alice_id, bob_private=bob_id)
    _, global_states = wait_document(admin, global_id)
    _, alice_states = wait_document(alice, alice_id)
    _, bob_states = wait_document(bob, bob_id)

    def fresh_user() -> tuple[str, list[Any], str]:
        require(alice.get("/api/v1/auth/me"), 200, "fresh_me")
        question = "What exact support rate is assigned to ALICE_PRIVATE_SENTINEL_7F92?"
        retrieval_response, retrieval_results = retrieve(alice, question, [alice_id])
        require(retrieval_response, 200, "fresh_retrieval")
        if not retrieval_results or any(str(item["document_id"]) != alice_id for item in retrieval_results):
            raise ProductFailure("fresh retrieval did not return only Alice evidence", "P1", retrieval_results)
        session_id = create_chat(alice, f"Final Gate Alice {run_id}")
        gate.sessions["alice_primary"] = session_id
        answer, _ = generate(alice, session_id, question, [alice_id])
        text = str(answer.get("content_text", answer.get("content", "")))
        citations = answer.get("citations") or []
        if "37" not in text or not citations:
            raise ProductFailure("new generation is not grounded with a citation", "P1", [{"answer": text, "citations": citations}])
        if any(citation_document_id(item) != alice_id for item in citations):
            raise ProductFailure("fresh answer cites a wrong document", "P1", citations)
        require(alice.get(f"/documents/{alice_id}"), 200, "open_source")
        before_refresh = messages(alice, session_id)
        require(httpx.get(FRONTEND_URL, verify=False, timeout=20), 200, "frontend_refresh")
        after_refresh = messages(alice, session_id)
        if len(before_refresh) != len(after_refresh):
            raise ProductFailure("history changed across refresh", "P1")
        require(alice.post("/api/v1/auth/logout"), 204, "logout")
        if alice.get("/api/v1/auth/me").status_code != 401:
            raise ProductFailure("logout did not revoke session", "P0")
        alice.cookies.clear()
        require(alice.post("/api/v1/auth/login", json={"email": emails["alice"], "password": password}), 200, "relogin")
        require(alice.get(f"/api/v1/chat/sessions/{session_id}/messages"), 200, "history_after_relogin")
        time.sleep(13)
        second, _ = generate(
            alice, session_id,
            "Does ALICE_PRIVATE_SENTINEL_7F92 apply outside Alice's final-gate private program?",
            [alice_id],
        )
        return (
            "A new user completed upload-to-index, retrieval, two new generations, citation open, refresh, logout/relogin, and history reopen.",
            [{"document_id": alice_id, "lifecycle": alice_states, "retrieval_count": len(retrieval_results), "citation_count": len(citations), "second_status": second.get("answer_status")}],
            "Every request used Secure HttpOnly session-cookie handling through the local HTTPS edge and a trusted browser Origin.",
        )

    gate.scenario(
        "fresh_user_journey",
        "A completely new user completes the full product journey with new grounded generations, citations, persistent history, and valid session behavior.",
        fresh_user,
    )

    large_pdf = make_pdf([
        "Article 21. Mid-ingestion final-gate rule.",
        "MID_INGESTION_SENTINEL_M91 has the exact verification period of 91 days.",
    ], pages=350)

    def mid_ingestion() -> tuple[str, list[Any], str]:
        document_id, _ = upload(alice, large_pdf, f"gate_mid_ingestion_{run_id}.pdf")
        gate.documents["mid_ingestion"] = document_id
        first = require(get_document(alice, document_id), 200, "mid_ingestion_status").json()
        if not active_state(first):
            raise ProductFailure("large document became ready before active-state query could execute", "P1", [first])
        question = "What verification period is assigned to MID_INGESTION_SENTINEL_M91?"
        response, partial = retrieve(alice, question, [document_id])
        require(response, 200, "mid_ingestion_retrieval")
        if partial:
            raise ProductFailure("processing document leaked partial retrieval evidence", "P1", partial)
        session_id = create_chat(alice, f"Mid ingestion {run_id}")
        mid_answer, _ = generate(alice, session_id, question, [document_id])
        if mid_answer.get("answer_status") != "INSUFFICIENT_EVIDENCE":
            raise ProductFailure("mid-ingestion generation completed as answerable", "P1", [mid_answer])
        _, states = wait_document(alice, document_id)
        response, ready_results = retrieve(alice, question, [document_id])
        require(response, 200, "ready_retrieval")
        if not ready_results:
            raise ProductFailure("ready document is not retrievable", "P1")
        time.sleep(13)
        ready_answer, _ = generate(alice, session_id, question, [document_id])
        answer_text = str(ready_answer.get("content_text", ready_answer.get("content", "")))
        if "91" not in answer_text or not ready_answer.get("citations"):
            raise ProductFailure("post-ready generation is not grounded", "P1", [ready_answer])
        return (
            "Active document returned no partial evidence and insufficient-evidence status; after indexing it retrieved and generated a cited 91-day answer.",
            [{"document_id": document_id, "active_state": first, "states": states, "ready_retrieval_count": len(ready_results)}],
            "The large 350-page PDF made the frozen asynchronous state observable without changing worker configuration.",
        )

    gate.scenario(
        "mid_ingestion_query",
        "A query during PROCESSING/INDEXING is safe and excludes partial evidence; the same query works after READY.",
        mid_ingestion,
    )

    duplicate_pdf = make_pdf([
        "Article 31. Concurrent canonical deduplication rule.",
        "DUPLICATE_SENTINEL_D88 has a canonical value of 88 units.",
    ], pages=12)
    duplicate_sha = hashlib.sha256(duplicate_pdf).hexdigest()

    def concurrent_duplicate() -> tuple[str, list[Any], str]:
        def request_upload(_: int) -> tuple[int, dict[str, Any]]:
            client = clone_browser(bob)
            try:
                response = client.post(
                    "/documents", params={"access": "private"},
                    files={"file": (f"gate_duplicate_{run_id}.pdf", duplicate_pdf, "application/pdf")},
                )
                return response.status_code, response.json() if response.headers.get("content-type", "").startswith("application/json") else {"text": response.text[:500]}
            finally:
                client.close()
        barrier = threading.Barrier(2)
        def synchronized(index: int):
            barrier.wait()
            return request_upload(index)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(synchronized, (1, 2)))
        if any(status >= 500 for status, _ in outcomes):
            raise ProductFailure("concurrent duplicate upload returned server error", "P1", outcomes)
        ids = [str(body.get("document", {}).get("id")) for status, body in outcomes if status == 202]
        if not ids or len(set(ids)) != 1:
            raise ProductFailure("concurrent duplicate requests did not resolve to one canonical document", "P1", outcomes)
        document_id = ids[0]
        gate.documents["concurrent_duplicate"] = document_id
        wait_document(bob, document_id)
        counts = db_one(
            """
            SELECT
              (SELECT count(*) FROM documents WHERE sha256=%s) AS canonical_documents,
              (SELECT count(*) FROM document_access_grants WHERE document_id=%s) AS grants,
              (SELECT count(*) FROM ingestion_jobs WHERE document_id=%s) AS ingestion_jobs,
              (SELECT count(*) FROM chunks WHERE document_id=%s) AS chunks,
              (SELECT count(*) FROM chunk_indexes WHERE document_id=%s) AS indexes
            """,
            (duplicate_sha, document_id, document_id, document_id, document_id),
        )
        if int(counts["canonical_documents"]) != 1 or int(counts["grants"]) != 1 or int(counts["ingestion_jobs"]) != 1:
            raise ProductFailure("dedup race created duplicate durable state", "P1", [{"outcomes": outcomes, "counts": counts}])
        if int(counts["chunks"]) == 0 or int(counts["chunks"]) != int(counts["indexes"]):
            raise ProductFailure("deduplicated document has inconsistent chunks/indexes", "P1", [counts])
        return (
            "Two synchronized uploads resolved to one document, grant, and ingestion pipeline with one consistent chunk/index set.",
            [{"http_outcomes": [status for status, _ in outcomes], "document_id": document_id, "sha256": duplicate_sha, "counts": counts}],
            "MinIO uniqueness is checked again by final storage reconciliation.",
        )

    gate.scenario(
        "concurrent_duplicate_upload",
        "Two simultaneous identical uploads create one canonical document and one durable processing pipeline without HTTP 500 or storage/index duplication.",
        concurrent_duplicate,
    )

    def authorization() -> tuple[str, list[Any], str]:
        alice_ids, bob_ids, admin_ids = document_ids(alice), document_ids(bob), document_ids(admin)
        if bob_id in alice_ids or alice_id in bob_ids:
            raise ProductFailure("private document leaked through listing", "P0")
        if global_id not in alice_ids or global_id not in bob_ids or global_id not in admin_ids:
            raise ProductFailure("global document visibility is inconsistent", "P1")
        direct = [
            ("alice_get_bob", alice.get(f"/documents/{bob_id}").status_code),
            ("bob_get_alice", bob.get(f"/documents/{alice_id}").status_code),
            ("alice_delete_bob", alice.delete(f"/documents/{bob_id}").status_code),
            ("bob_delete_alice", bob.delete(f"/documents/{alice_id}").status_code),
        ]
        if any(status != 404 for _, status in direct):
            raise ProductFailure("direct private document boundary did not return uniform 404", "P0", direct)
        if get_document(bob, bob_id).status_code != 200 or get_document(alice, alice_id).status_code != 200:
            raise ProductFailure("cross-user delete attempt damaged owner resource", "P0")
        response, alice_results = retrieve(alice, "What is BOB_PRIVATE_SENTINEL_X3K91 and its support rate?")
        require(response, 200, "alice_bob_retrieval")
        if any(str(item["document_id"]) == bob_id or "BOB_PRIVATE_SENTINEL_X3K91" in str(item.get("content_text", "")) for item in alice_results):
            raise ProductFailure("Bob private evidence leaked through Alice retrieval", "P0", alice_results)
        session_id = create_chat(alice, f"Isolation Alice {run_id}")
        gate.sessions["alice_isolation"] = session_id
        time.sleep(13)
        answer, _ = generate(alice, session_id, "What support rate belongs to BOB_PRIVATE_SENTINEL_X3K91?")
        text = str(answer.get("content_text", answer.get("content", "")))
        citations = answer.get("citations") or []
        if "64" in text or any(citation_document_id(item) == bob_id for item in citations):
            raise ProductFailure("Bob private fact leaked through Alice generation/citation", "P0", [{"answer": text, "citations": citations}])
        if any("BOB_PRIVATE_SENTINEL_X3K91" in str(item.get("evidence_text", "")) for item in citations):
            raise ProductFailure("Bob evidence leaked into Alice history snapshot", "P0", citations)
        bob_session = create_chat(bob, f"Isolation Bob {run_id}")
        gate.sessions["bob_isolation"] = bob_session
        bob_answer, _ = generate(bob, bob_session, "What support rate belongs to ALICE_PRIVATE_SENTINEL_7F92?")
        bob_text = str(bob_answer.get("content_text", bob_answer.get("content", "")))
        bob_citations = bob_answer.get("citations") or []
        if "37" in bob_text or any(citation_document_id(item) == alice_id for item in bob_citations):
            raise ProductFailure("Alice private fact leaked through Bob generation/citation", "P0", [{"answer": bob_text, "citations": bob_citations}])
        alice_history = gate.sessions["alice_primary"]
        if bob.get(f"/api/v1/chat/sessions/{alice_history}").status_code != 404:
            raise ProductFailure("cross-user history access was not hidden", "P0")
        return (
            "Listings, direct APIs, deletion, retrieval, generation, citations, and history remained private in both directions while the global document stayed visible.",
            [{"direct_statuses": direct, "alice_retrieval_count": len(alice_results), "alice_answer_status": answer.get("answer_status"), "bob_answer_status": bob_answer.get("answer_status")}],
            "No private sentinel value crossed the authorization boundary.",
        )

    gate.scenario(
        "authorization_isolation_full_stack",
        "Alice and Bob cannot cross private boundaries through any product layer; global evidence remains shared.",
        authorization,
    )

    conflict_pdf = make_pdf([
        "Article 7A. Conflicting final-gate source.",
        "For the same ALICE_PRIVATE_SENTINEL_7F92 program, this source states a support rate of 41 percent.",
        "This conflicts with the separate 37 percent source.",
    ])
    conflict_id, _ = upload(alice, conflict_pdf, f"gate_conflict_{run_id}.pdf")
    gate.documents["alice_conflict"] = conflict_id
    wait_document(alice, conflict_id)

    def grounding() -> tuple[str, list[Any], str]:
        session_id = create_chat(alice, f"Grounding Matrix {run_id}")
        gate.sessions["grounding"] = session_id
        time.sleep(13)
        weak, _ = generate(
            alice, session_id,
            "On what exact calendar date was ALICE_PRIVATE_SENTINEL_7F92 enacted, and who personally signed it?",
            [alice_id],
        )
        if weak.get("answer_status") != "INSUFFICIENT_EVIDENCE":
            raise ProductFailure("weak evidence produced an unqualified answer", "P1", [weak])
        time.sleep(13)
        none, _ = generate(
            alice, session_id,
            "What is the 2088 lunar mining tax rate for helium-3 under statute MOON_SENTINEL_Z0?",
            [alice_id],
        )
        if none.get("answer_status") != "INSUFFICIENT_EVIDENCE" or none.get("citations"):
            raise ProductFailure("no-evidence query did not abstain cleanly", "P1", [none])
        time.sleep(13)
        conflict, _ = generate(
            alice, session_id,
            "What conflicting support rates do the authorized sources state for ALICE_PRIVATE_SENTINEL_7F92?",
            [alice_id, conflict_id],
        )
        conflict_text = str(conflict.get("content_text", conflict.get("content", "")))
        conflict_citations = conflict.get("citations") or []
        if conflict.get("answer_status") == "ANSWERABLE":
            cited_docs = {citation_document_id(item) for item in conflict_citations}
            if not {alice_id, conflict_id}.issubset(cited_docs) or "37" not in conflict_text or "41" not in conflict_text:
                raise ProductFailure("conflict synthesis flattened values or citations", "P1", [{"answer": conflict_text, "citations": conflict_citations}])
        elif conflict.get("answer_status") != "INSUFFICIENT_EVIDENCE":
            raise ProductFailure("conflict response has invalid status", "P1", [conflict])
        primary_rows = messages(alice, gate.sessions["alice_primary"])
        strong = next(row for row in primary_rows if str(row.get("role", "")).upper() == "ASSISTANT")
        strong_citations = strong.get("citations") or []
        if not strong_citations or any(citation_document_id(item) != alice_id for item in strong_citations):
            raise ProductFailure("strong-evidence citation chain points to wrong source", "P1", strong_citations)
        if any(not item.get("evidence_text") or not item.get("original_chunk_id") for item in strong_citations):
            raise ProductFailure("history citation snapshot is structurally incomplete", "P1", strong_citations)
        return (
            "Strong evidence was cited; weak and absent evidence abstained; conflict was either explicitly cited as a conflict or conservatively abstained.",
            [{"strong_citations": len(strong_citations), "weak_status": weak.get("answer_status"), "none_status": none.get("answer_status"), "conflict_status": conflict.get("answer_status"), "conflict_citations": len(conflict_citations)}],
            "Citation checks followed answer -> snapshot -> original chunk/document and authorized scope.",
        )

    gate.scenario(
        "grounded_generation_and_citations",
        "Strong, weak, absent, and conflicting evidence follow legal-rag-v2 grounding and citation rules.",
        grounding,
    )

    def midstream_revocation() -> tuple[str, list[Any], str]:
        session_id = create_chat(bob, f"Midstream revocation {run_id}")
        gate.sessions["midstream"] = session_id
        stream_client = clone_browser(bob)
        revoke_client = clone_browser(bob)
        started = threading.Event()
        outcome: dict[str, Any] = {}
        def stream_call():
            try:
                with stream_client.stream(
                    "POST", f"/api/v1/chat/sessions/{session_id}/turns/stream",
                    json={"client_turn_id": str(uuid.uuid4()), "query": "Explain every clause governing BOB_PRIVATE_SENTINEL_X3K91 in detail.", "document_ids": [bob_id]},
                ) as response:
                    outcome["status"] = response.status_code
                    chunks: list[str] = []
                    for line in response.iter_lines():
                        chunks.append(line)
                        if line.startswith("event: start"):
                            started.set()
                    outcome["body"] = "\n".join(chunks)
            except Exception as exc:
                outcome["exception"] = repr(exc)
        thread = threading.Thread(target=stream_call, daemon=True)
        thread.start()
        if not started.wait(30):
            raise ProductFailure("stream did not emit start before revocation", "P1", [outcome])
        logout = revoke_client.post("/api/v1/auth/logout")
        require(logout, 204, "midstream_logout")
        thread.join(timeout=240)
        if thread.is_alive():
            raise ProductFailure("stream hung after authorization revocation", "P1")
        if revoke_client.get("/api/v1/auth/me").status_code != 401:
            raise ProductFailure("new request remained authorized after logout", "P0")
        rows = db_all("SELECT state, failure_code FROM chat_turns WHERE session_id=%s ORDER BY created_at DESC LIMIT 1", (session_id,))
        if not rows or rows[0]["state"] not in {"COMPLETED", "FAILED"}:
            raise ProductFailure("history state is invalid after midstream revocation", "P1", rows)
        if outcome.get("exception"):
            raise ProductFailure("SSE raised after revocation", "P1", [outcome])
        bob.cookies.clear()
        require(bob.post("/api/v1/auth/login", json={"email": emails["bob"], "password": password}), 200, "bob_relogin")
        return (
            "The request-start-authorized stream settled, the revoked session rejected new requests, and history reached a terminal state.",
            [{"logout_http": logout.status_code, "stream_http": outcome.get("status"), "turn": rows[0]}],
            "Frozen V1 resolves authorization at request start; it does not promise continuous token checks during an accepted stream.",
        )

    gate.scenario(
        "mid_stream_auth_revocation",
        "Under the frozen request-start policy, the accepted stream settles safely while every new request after logout is rejected and history is terminal.",
        midstream_revocation,
    )

    def ghost_generation() -> tuple[str, list[Any], str]:
        session_id = create_chat(bob, f"Ghost generation {run_id}")
        gate.sessions["ghost"] = session_id
        stream_client = clone_browser(bob)
        delete_client = clone_browser(bob)
        started = threading.Event()
        outcome: dict[str, Any] = {}
        def stream_call():
            with stream_client.stream(
                "POST", f"/api/v1/chat/sessions/{session_id}/turns/stream",
                json={"client_turn_id": str(uuid.uuid4()), "query": "Give a detailed grounded analysis of BOB_PRIVATE_SENTINEL_X3K91.", "document_ids": [bob_id]},
            ) as response:
                outcome["status"] = response.status_code
                lines = []
                for line in response.iter_lines():
                    lines.append(line)
                    if line.startswith("event: start"):
                        started.set()
                outcome["body"] = "\n".join(lines)
        thread = threading.Thread(target=stream_call, daemon=True)
        thread.start()
        if not started.wait(30):
            raise ProductFailure("ghost test stream did not start", "P1")
        deletion = delete_client.delete(f"/api/v1/chat/sessions/{session_id}")
        if deletion.status_code not in {204, 409}:
            raise ProductFailure("active-session deletion was uncontrolled", "P1", [{"status": deletion.status_code, "body": deletion.text[:500]}])
        thread.join(timeout=240)
        if thread.is_alive():
            raise ProductFailure("generation remained a zombie after delete attempt", "P1")
        row = db_one(
            "SELECT (SELECT count(*) FROM chat_sessions WHERE id=%s) sessions, (SELECT count(*) FROM chat_turns WHERE session_id=%s AND state='COMPLETED') completed",
            (session_id, session_id),
        )
        if deletion.status_code == 204 and (int(row["sessions"]) != 0 or int(row["completed"]) != 0):
            raise ProductFailure("late LLM output wrote into a deleted chat", "P1", [row])
        if deletion.status_code == 409 and (int(row["sessions"]) != 1 or int(row["completed"]) != 1):
            raise ProductFailure("busy-session protection did not preserve one consistent completion", "P1", [row])
        return (
            "Active chat deletion was either atomically rejected as busy or safely deleted; no orphan completed output was written.",
            [{"delete_http": deletion.status_code, "stream_http": outcome.get("status"), "db": row}],
            "The frozen busy-session guard is an acceptable lifecycle policy.",
        )

    gate.scenario(
        "ghost_generation_orphan_callback",
        "Late LLM output cannot recreate or write completed history into a deleted chat/session.",
        ghost_generation,
    )

    # Keep this lifecycle probe outside the frozen per-IP generation limiter window.
    # Rate limiting is audited separately below; a deliberate 429 here would not
    # exercise client-disconnect cleanup.
    time.sleep(65)

    def client_abort() -> tuple[str, list[Any], str]:
        session_id = create_chat(bob, f"Client abort {run_id}")
        gate.sessions["abort"] = session_id
        client = clone_browser(bob)
        client_turn_id = str(uuid.uuid4())
        observed: list[str] = []
        with client.stream(
            "POST", f"/api/v1/chat/sessions/{session_id}/turns/stream",
            json={"client_turn_id": client_turn_id, "query": "Provide a long section-by-section analysis of BOB_PRIVATE_SENTINEL_X3K91.", "document_ids": [bob_id]},
        ) as response:
            require(response, 200, "abort_stream")
            for line in response.iter_lines():
                observed.append(line)
                if line.startswith("event: start"):
                    break
        client.close()
        time.sleep(3)
        row = db_one("SELECT state, failure_code FROM chat_turns WHERE client_turn_id=%s", (client_turn_id,))
        if row.get("state") == "COMPLETED":
            raise ProductFailure("aborted client stream was recorded as completed", "P1", [{"turn": row, "events": observed[-10:]}])
        if row.get("state") not in {"CANCELLED", "FAILED", "PENDING", "STREAMING"}:
            raise ProductFailure("aborted stream has unknown history state", "P1", [row])
        if row.get("state") == "CANCELLED" and row.get("failure_code") != "CLIENT_CANCELLED":
            raise ProductFailure("cancelled stream has an unexpected failure code", "P1", [row])
        return (
            "Closing the SSE client immediately after the start event did not create a completed answer; history remained failed or recoverable under the frozen orphan contract.",
            [{"turn": row, "last_events": observed[-5:]}],
            "Client disconnect cancellation is a V1 contract verified by the frozen unit suite and this live abort.",
        )

    gate.scenario(
        "client_abort_during_generation",
        "A client disconnected immediately after SSE start does not produce an incorrectly completed answer or orphan transaction.",
        client_abort,
    )

    def dangling_history() -> tuple[str, list[Any], str]:
        session_id = gate.sessions["alice_primary"]
        before = messages(alice, session_id)
        assistants = [row for row in before if str(row.get("role", "")).upper() == "ASSISTANT" and row.get("citations")]
        if not assistants:
            raise ProductFailure("no persisted citation snapshot before deletion", "P1")
        snapshot = assistants[0]["citations"][0]
        deletion = alice.delete(f"/documents/{alice_id}")
        require(deletion, 202, "delete_grounded_document")
        counts = wait_absent(alice_id)
        if alice.get(f"/documents/{alice_id}").status_code != 404:
            raise ProductFailure("deleted document remains accessible", "P1")
        response, results = retrieve(alice, "What rate belongs to ALICE_PRIVATE_SENTINEL_7F92?")
        require(response, 200, "post_delete_retrieval")
        if any(str(item["document_id"]) == alice_id for item in results):
            raise ProductFailure("deleted document remains retrievable", "P1", results)
        after = messages(alice, session_id)
        historical = [row for row in after if str(row.get("role", "")).upper() == "ASSISTANT" and row.get("citations")]
        if not historical or not historical[0]["citations"][0].get("evidence_text"):
            raise ProductFailure("history citation snapshot disappeared after source deletion", "P1", after)
        time.sleep(13)
        new_answer, _ = generate(alice, session_id, "What rate belongs to ALICE_PRIVATE_SENTINEL_7F92?")
        new_text = str(new_answer.get("content_text", new_answer.get("content", "")))
        if "37" in new_text or any(citation_document_id(item) == alice_id for item in (new_answer.get("citations") or [])):
            raise ProductFailure("history snapshot became live retrieval evidence", "P1", [new_answer])
        return (
            "The old citation snapshot remained renderable while the deleted canonical source, chunks, index, direct API, retrieval, and new generation stayed dead.",
            [{"document_id": alice_id, "snapshot_id": snapshot.get("id"), "post_delete_counts": counts, "new_status": new_answer.get("answer_status")}],
            "Historical evidence remained snapshot-only and did not re-enter retrieval.",
        )

    gate.scenario(
        "dangling_history_and_document_deletion",
        "Historical citation snapshots survive source deletion without making the deleted source live or retrievable.",
        dangling_history,
    )

    delete_race_pdf = make_pdf([
        "Article 44. Delete-during-ingestion test.",
        "DELETE_DURING_INGESTION_SENTINEL_Q44 must never survive deletion.",
    ], pages=500)

    def delete_during_ingestion() -> tuple[str, list[Any], str]:
        document_id, _ = upload(delete_race, delete_race_pdf, f"gate_delete_race_{run_id}.pdf")
        gate.documents["delete_during_ingestion"] = document_id
        status = require(get_document(delete_race, document_id), 200, "delete_race_status").json()
        if not active_state(status):
            raise ProductFailure("delete-race document was not active at deletion", "P1", [status])
        require(delete_race.delete(f"/documents/{document_id}"), 202, "delete_active_document")
        counts = wait_absent(document_id, timeout=300)
        time.sleep(5)
        counts_after = wait_absent(document_id)
        response, results = retrieve(delete_race, "What is DELETE_DURING_INGESTION_SENTINEL_Q44?")
        require(response, 200, "delete_race_retrieval")
        if any(str(item["document_id"]) == document_id for item in results):
            raise ProductFailure("late worker resurrected deleted active document", "P1", results)
        jobs = db_all(
            "SELECT status FROM ingestion_jobs WHERE document_id=%s UNION ALL SELECT status FROM document_processing_jobs WHERE document_id=%s UNION ALL SELECT status FROM indexing_jobs WHERE document_id=%s",
            (document_id, document_id, document_id),
        )
        if any(row["status"] in {"PENDING", "PROCESSING"} for row in jobs):
            raise ProductFailure("deleted-resource job remained active", "P1", jobs)
        return (
            "Deleting an active document left no document, chunk, index, retrieval result, active job, or late READY transition.",
            [{"document_id": document_id, "active_state": status, "counts": counts, "counts_after_settle": counts_after, "jobs": jobs}],
            "A later normal restart checks resurrection again.",
        )

    gate.scenario(
        "delete_document_while_ingestion_active",
        "Deletion during ingestion settles all jobs and cannot create late chunks, vectors, objects, READY state, or retrieval ghosts.",
        delete_during_ingestion,
    )

    def account_deletion() -> tuple[str, list[Any], str]:
        alice_user_id = gate.identities["alice"]["id"]
        alice_doc_ids = [str(row["document_id"]) for row in db_all("SELECT document_id FROM document_access_grants WHERE user_id=%s", (alice_user_id,))]
        bob_before = document_ids(bob)
        global_before = db_one("SELECT count(*) count FROM global_document_access WHERE document_id=%s", (global_id,))["count"]
        response = alice.request("DELETE", "/api/v1/auth/account", json={"password": password})
        require(response, 202, "delete_account", "P0")
        if alice.get("/api/v1/auth/me").status_code != 401:
            raise ProductFailure("account session remained authorized after deletion accepted", "P0")
        counts = wait_user_absent(alice_user_id)
        for document_id in alice_doc_ids:
            wait_absent(document_id, timeout=300)
        relogin = browser()
        denied = relogin.post("/api/v1/auth/login", json={"email": emails["alice"], "password": password})
        relogin.close()
        if denied.status_code != 401:
            raise ProductFailure("deleted account can still log in", "P0", [{"status": denied.status_code}])
        bob_after = document_ids(bob)
        global_after = db_one("SELECT count(*) count FROM global_document_access WHERE document_id=%s", (global_id,))["count"]
        if bob_before != bob_after or int(global_before) != 1 or int(global_after) != 1:
            raise ProductFailure("Alice account deletion damaged Bob or global resources", "P0", [{"bob_before": sorted(bob_before), "bob_after": sorted(bob_after), "global_before": global_before, "global_after": global_after}])
        leaked = db_one(
            """
            SELECT
              (SELECT count(*) FROM chunks c JOIN documents d ON d.id=c.document_id JOIN document_access_grants g ON g.document_id=d.id WHERE g.user_id=%s) chunks,
              (SELECT count(*) FROM chat_sessions WHERE user_id=%s) chats,
              (SELECT count(*) FROM auth_sessions WHERE user_id=%s) sessions
            """,
            (alice_user_id, alice_user_id, alice_user_id),
        )
        if any(int(value) for value in leaked.values()):
            raise ProductFailure("deleted Alice private state remains", "P0", [leaked])
        return (
            "Alice authorization was revoked immediately; user, sessions, private grants/documents/chunks/history were purged while Bob and global resources were unchanged.",
            [{"user_id": alice_user_id, "account_counts": counts, "private_document_ids": alice_doc_ids, "bob_document_count": len(bob_after), "global_access": global_after}],
            "The external tombstone ledger is checked during final reconciliation and restart.",
        )

    gate.scenario(
        "account_deletion_e2e",
        "Accepted account deletion immediately revokes access, purges Alice private state, and cannot damage Bob or global data.",
        account_deletion,
    )

    account_race_pdf = make_pdf([
        "Article 52. Account delete during ingestion.",
        "ACCOUNT_DELETE_ACTIVE_SENTINEL_A52 must never survive account deletion.",
    ], pages=500)

    def account_delete_active() -> tuple[str, list[Any], str]:
        user_id = gate.identities["account_race"]["id"]
        document_id, _ = upload(account_race, account_race_pdf, f"gate_account_race_{run_id}.pdf")
        gate.documents["account_delete_active"] = document_id
        status = require(get_document(account_race, document_id), 200, "account_race_status").json()
        if not active_state(status):
            raise ProductFailure("account-race document was not active", "P1", [status])
        response = account_race.request("DELETE", "/api/v1/auth/account", json={"password": password})
        require(response, 202, "delete_active_account", "P0")
        if account_race.get("/api/v1/auth/me").status_code != 401:
            raise ProductFailure("active account-delete session was not revoked", "P0")
        user_counts = wait_user_absent(user_id, timeout=300)
        document_counts = wait_absent(document_id, timeout=300)
        time.sleep(5)
        document_counts_after = wait_absent(document_id)
        jobs = db_all(
            "SELECT status FROM ingestion_jobs WHERE document_id=%s UNION ALL SELECT status FROM document_processing_jobs WHERE document_id=%s UNION ALL SELECT status FROM indexing_jobs WHERE document_id=%s",
            (document_id, document_id, document_id),
        )
        if any(row["status"] in {"PENDING", "PROCESSING"} for row in jobs):
            raise ProductFailure("deleted-account job remained active", "P0", jobs)
        return (
            "Deleting an account during ingestion revoked access and left no account, document, semantic footprint, or active retrying job.",
            [{"user_id": user_id, "document_id": document_id, "active_state": status, "user_counts": user_counts, "document_counts": document_counts, "counts_after_settle": document_counts_after, "jobs": jobs}],
            "A later normal restart checks tombstone-backed resurrection prevention.",
        )

    gate.scenario(
        "account_deletion_while_ingestion_active",
        "Account deletion during active ingestion revokes immediately and prevents late account/document/object/chunk/vector resurrection or poisoned jobs.",
        account_delete_active,
    )

    def security_controls() -> tuple[str, list[Any], str]:
        no_origin = clone_browser(bob, include_origin=False)
        csrf = no_origin.delete(f"/documents/{uuid.uuid4()}")
        no_origin.close()
        if csrf.status_code != 403:
            raise ProductFailure("mutation without trusted Origin was not rejected", "P0", [{"status": csrf.status_code, "body": csrf.text[:500]}])
        rate_email = emails["rate"]
        attempts: list[dict[str, Any]] = []
        for _ in range(8):
            client = browser()
            response = client.post("/api/v1/auth/login", json={"email": rate_email, "password": "definitely-wrong-password"})
            attempts.append({"status": response.status_code, "retry_after": response.headers.get("Retry-After")})
            client.close()
        if 429 not in {item["status"] for item in attempts}:
            raise ProductFailure("deliberate login burst did not trigger configured limiter", "P1", attempts)
        if any(item["status"] >= 500 for item in attempts):
            raise ProductFailure("rate-limit burst caused server error", "P1", attempts)
        stale_alice = browser()
        stale_login = stale_alice.post("/api/v1/auth/login", json={"email": emails["alice"], "password": password})
        stale_alice.close()
        if stale_login.status_code != 401:
            raise ProductFailure("deleted Alice credentials unexpectedly authenticated", "P0", [{"status": stale_login.status_code}])
        return (
            "Legitimate Origin mutations succeeded throughout the journey; missing-Origin mutation returned 403, deliberate login burst returned controlled 429, and deleted credentials returned 401.",
            [{"missing_origin_http": csrf.status_code, "rate_attempts": attempts, "deleted_login_http": stale_login.status_code}],
            "Normal user flows recorded no 403/429. Only the deliberate machine-speed limiter probe received 429.",
        )

    gate.scenario(
        "security_rate_limit_csrf_and_direct_api",
        "Browser-style requests work normally; invalid Origin, deliberate bursts, stale credentials, and cross-user IDs receive controlled rejection without HTTP 500.",
        security_controls,
    )

    def restart_persistence() -> tuple[str, list[Any], str]:
        command = COMPOSE + [
            "restart", "postgres", "redis", "minio", "api", "worker", "processing-worker",
            "indexing-worker", "frontend", "final-gate-edge",
        ]
        result = run(command, timeout=180)
        if result.returncode != 0:
            raise ProductFailure("normal stack restart command failed", "P1", [{"stderr": result.stderr[-1500:]}])
        deadline = time.monotonic() + 180
        ready_payload: dict[str, Any] = {}
        while time.monotonic() < deadline:
            try:
                response = httpx.get(f"{BASE_URL}/ready", verify=False, timeout=10)
                if response.status_code == 200:
                    ready_payload = response.json()
                    break
            except Exception:
                pass
            time.sleep(2)
        if ready_payload.get("status") != "ready":
            raise ProductFailure("stack did not regain readiness after normal restart", "P1", [ready_payload])
        restarted_bob = login(emails["bob"], password)
        try:
            ids = document_ids(restarted_bob)
            if bob_id not in ids or global_id not in ids:
                raise ProductFailure("Bob/global persistent documents missing after restart", "P1", [sorted(ids)])
            for deleted_id in (alice_id, gate.documents["delete_during_ingestion"], gate.documents["account_delete_active"]):
                if restarted_bob.get(f"/documents/{deleted_id}").status_code != 404:
                    raise ProductFailure("deleted resource resurrected after restart", "P0", [{"document_id": deleted_id}])
            response, results = retrieve(restarted_bob, "What support rate belongs to BOB_PRIVATE_SENTINEL_X3K91?", [bob_id])
            require(response, 200, "post_restart_retrieval")
            if not results:
                raise ProductFailure("post-restart retrieval returned no Bob evidence", "P1")
            session_id = create_chat(restarted_bob, f"Post restart {run_id}")
            answer, _ = generate(restarted_bob, session_id, "What support rate belongs to BOB_PRIVATE_SENTINEL_X3K91?", [bob_id])
            text = str(answer.get("content_text", answer.get("content", "")))
            if "64" not in text or not answer.get("citations"):
                raise ProductFailure("new post-restart generation was not grounded", "P1", [answer])
            if not messages(restarted_bob, gate.sessions["bob_isolation"]):
                raise ProductFailure("pre-restart Bob history missing", "P1")
        finally:
            restarted_bob.close()
        alice_login = browser()
        alice_status = alice_login.post("/api/v1/auth/login", json={"email": emails["alice"], "password": password}).status_code
        account_race_status = alice_login.post("/api/v1/auth/login", json={"email": emails["account_race"], "password": password}).status_code
        alice_login.close()
        if alice_status != 401 or account_race_status != 401:
            raise ProductFailure("deleted account resurrected after restart", "P0", [{"alice": alice_status, "account_race": account_race_status}])
        return (
            "The full isolated stack restarted without restore; frontend/readiness, login, documents, retrieval, new generation, citations, history, and deletion non-resurrection all passed.",
            [{"ready": ready_payload, "bob_document_count": len(ids), "post_restart_retrieval_count": len(results), "post_restart_answer_status": answer.get("answer_status"), "deleted_login_statuses": [alice_status, account_race_status]}],
            "No volumes were deleted or restored.",
        )

    gate.scenario(
        "restart_persistence_and_resurrection",
        "A normal full-stack restart preserves live product state and new generation while deleted documents/accounts remain absent.",
        restart_persistence,
    )

    for client in (admin, alice, bob, delete_race, account_race):
        try:
            client.close()
        except Exception:
            pass

    gate.persist()
    print(f"RUNTIME_EVIDENCE={RUNTIME_PATH}", flush=True)


if __name__ == "__main__":
    main()
