import argparse
import getpass
import os

from app.auth.service import AuthService
from app.db.database import SessionLocal
from app.models.auth import UserRole


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision an Auth V1 user without default credentials")
    parser.add_argument("command", choices=("create-admin", "create-user"))
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    password = os.environ.get("AUTH_BOOTSTRAP_PASSWORD") or getpass.getpass("Temporary password: ")
    role = UserRole.ADMIN if args.command == "create-admin" else UserRole.USER
    db = SessionLocal()
    try:
        user = AuthService(db).provision_user(args.email, password, role, must_change_password=True)
        print(f"Created {user.role} user {user.email} ({user.id})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
