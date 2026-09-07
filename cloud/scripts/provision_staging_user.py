"""Provision one D1 staging user without a public registration endpoint.

Passwords are accepted only from standard input, transformed immediately into
the Worker-compatible PBKDF2 record, and never written or printed.
"""
from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import json
import re
import secrets
import subprocess
import sys
import shutil
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY = json.loads((ROOT / "cloud" / "password_policy.json").read_text(encoding="utf-8"))
# Deliberately excludes SQL quoting characters because Wrangler D1 CLI has no
# positional bind interface. This is narrower than RFC email syntax by design.
EMAIL = re.compile(r"^[A-Za-z0-9.!#$%&+/_=~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")


def password_record(password: str) -> str:
    salt = secrets.token_bytes(POLICY["salt_bytes"])
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, POLICY["iterations"], dklen=POLICY["derived_key_bytes"])
    return "{}${}${}${}".format(POLICY["scheme"], POLICY["iterations"], base64.b64encode(salt).decode("ascii"), base64.b64encode(derived).decode("ascii"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision an account in the staging D1 database only.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password-stdin", action="store_true", help="Read password from stdin instead of a non-echoing prompt.")
    args = parser.parse_args()
    email = args.email.strip().lower()
    if not EMAIL.fullmatch(email):
        parser.error("--email must be a normal email address")
    password = sys.stdin.readline().rstrip("\r\n") if args.password_stdin else getpass.getpass("Staging password: ")
    if len(password) < 16:
        parser.error("staging password must contain at least 16 characters")
    record = password_record(password)
    user_id = str(uuid.uuid4())
    # All interpolation is from fixed-format values validated above. The
    # command hard-codes --env staging and its staging database name.
    sql = "INSERT INTO users(id,email,password_hash,role,status,created_at) VALUES('{}','{}','{}','USER','ACTIVE',unixepoch('now')*1000) ON CONFLICT(email) DO UPDATE SET password_hash=excluded.password_hash,status='ACTIVE';".format(user_id, email, record)
    npx = shutil.which("npx.cmd") or shutil.which("npx")
    if not npx:
        print("STAGING_USER_PROVISION_FAILED: npx is required", file=sys.stderr)
        return 2
    command = [npx, "wrangler", "d1", "execute", "zkd-control-plane-staging", "--remote", "--config", "cloud/wrangler.jsonc", "--env", "staging", "--command", sql]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if completed.returncode:
        print("STAGING_USER_PROVISION_FAILED", file=sys.stderr)
        return completed.returncode
    print(json.dumps({"status": "provisioned", "email": email, "database": "zkd-control-plane-staging"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
