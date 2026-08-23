"""Bounded local red/blue probe for distributed generation admission."""

import asyncio
import json
import time
import uuid

import httpx
from sqlalchemy import delete, select

from app.auth.service import AuthService
from app.core.config import settings
from app.db.database import SessionLocal
from app.models.auth import User, UserRole


EMAIL = "security-generation-probe@example.invalid"
PASSWORD = "SecurityProbePassphrase!2026"
ORIGIN = "http://localhost:5173"


def provision() -> None:
    db = SessionLocal()
    try:
        existing = db.scalar(select(User).where(User.normalized_email == EMAIL))
        if existing is None:
            AuthService(db).provision_user(EMAIL, PASSWORD, UserRole.USER, must_change_password=False)
    finally:
        db.close()


def cleanup() -> None:
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.normalized_email == EMAIL))
        if user is not None:
            db.delete(user)
            db.commit()
    finally:
        db.close()


async def main() -> None:
    provision()
    base = "http://127.0.0.1:8000"
    async with httpx.AsyncClient(base_url=base, headers={"Origin": ORIGIN}, timeout=240) as client:
        login = await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
        login.raise_for_status()
        sessions = []
        for index in range(3):
            response = await client.post("/api/v1/chat/sessions", json={"title": f"Security admission {index}"})
            response.raise_for_status()
            sessions.append(response.json()["id"])

        async def invoke(session_id: str, index: int) -> dict:
            started = time.perf_counter()
            payload = {
                "client_turn_id": str(uuid.uuid4()),
                "query": "Doanh nghiệp được hưởng ưu đãi gì theo tài liệu?",
            }
            response = await client.post(f"/api/v1/chat/sessions/{session_id}/turns/stream", json=payload)
            event_names = [line[7:] for line in response.text.splitlines() if line.startswith("event: ")]
            error_code = None
            if response.headers.get("content-type", "").startswith("application/json"):
                error_code = response.json().get("detail", {}).get("error_code")
            return {
                "attempt": index,
                "status": response.status_code,
                "error_code": error_code,
                "events": event_names,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            }

        results = await asyncio.gather(*(invoke(session_id, i) for i, session_id in enumerate(sessions, 1)))
        print(json.dumps({
            "accepted": sum(item["status"] == 200 for item in results),
            "rejected": sum(item["status"] == 429 for item in results),
            "results": results,
        }, ensure_ascii=False))
    cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        cleanup()
