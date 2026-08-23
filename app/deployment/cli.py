from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from app.core.config import settings


def _print(data) -> None:
    print(json.dumps(data, indent=2, sort_keys=True, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deployment + Backup + Recovery V1 operator tooling")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("preflight")
    commands.add_parser("migration-check")

    release = commands.add_parser("release-manifest")
    release.add_argument("--output", required=True, type=Path)

    commands.add_parser("model-check")
    online = commands.add_parser("provision-model-online")
    online.add_argument("--model", default=settings.GENERATION_MODEL_ID)
    online.add_argument("--allow-network", action="store_true")
    online.add_argument("--output", required=True, type=Path)
    offline = commands.add_parser("verify-model-artifact")
    offline.add_argument("--artifact", required=True, type=Path)
    offline.add_argument("--sha256", required=True)

    backup = commands.add_parser("backup-create")
    backup.add_argument("--root", type=Path, default=Path(settings.BACKUP_DESTINATION))
    backup.add_argument("--backup-id")
    verify = commands.add_parser("backup-verify")
    verify.add_argument("--root", type=Path, default=Path(settings.BACKUP_DESTINATION))
    verify.add_argument("--backup-id", required=True)
    retention = commands.add_parser("backup-retention")
    retention.add_argument("--root", type=Path, default=Path(settings.BACKUP_DESTINATION))
    retention.add_argument("--apply", action="store_true")
    retention.add_argument("--confirm")

    store = commands.add_parser("reconcile-store")
    store.add_argument("--backup-id")
    store.add_argument("--output", type=Path)
    jobs = commands.add_parser("reconcile-jobs")
    jobs.add_argument("--output", type=Path)

    restore = commands.add_parser("restore")
    restore.add_argument("--root", required=True, type=Path)
    restore.add_argument("--backup-id", required=True)
    restore.add_argument("--environment", required=True)
    restore.add_argument("--confirm", required=True)
    restore.add_argument("--ollama-stopped", action="store_true")
    restore.add_argument("--output", type=Path)
    hnsw = commands.add_parser("rebuild-hnsw")
    hnsw.add_argument("--ollama-stopped", action="store_true")

    recovery = commands.add_parser("recovery-mode")
    recovery.add_argument("action", choices=("enter", "clear"))
    recovery.add_argument("--reason", default="OPERATOR_RECOVERY")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "preflight":
            from app.deployment.preflight import validate_deployment_configuration
            _print(asdict(validate_deployment_configuration()))
        elif args.command == "migration-check":
            from app.deployment.release import current_alembic_revision, expected_alembic_head
            current, expected = current_alembic_revision(), expected_alembic_head()
            if current != expected:
                raise RuntimeError("MIGRATION_HEAD_MISMATCH")
            _print({"status": "MIGRATION_HEAD_VERIFIED", "current": current, "expected": expected})
        elif args.command == "release-manifest":
            from app.deployment.release import write_release_manifest
            _print(write_release_manifest(args.output))
        elif args.command == "model-check":
            from app.deployment.model import verify_expected_model
            _print(asdict(verify_expected_model()))
        elif args.command == "provision-model-online":
            from app.deployment.model import provision_online
            _print(asdict(provision_online(args.model, allow_network=args.allow_network, output=args.output)))
        elif args.command == "verify-model-artifact":
            from app.deployment.model import verify_offline_store
            _print({"sha256": verify_offline_store(args.artifact, args.sha256), "verified": True})
        elif args.command == "backup-create":
            from app.deployment.backup import create_backup
            _print(create_backup(backup_root=args.root, backup_id=args.backup_id))
        elif args.command == "backup-verify":
            from app.deployment.backup import verify_backup
            _print(verify_backup(args.root, args.backup_id))
        elif args.command == "backup-retention":
            from app.deployment.backup import apply_retention
            if args.apply and args.confirm != "DELETE_EXPIRED_COMPLETE_BACKUPS":
                raise RuntimeError("RETENTION_CONFIRMATION_REQUIRED")
            _print(apply_retention(backup_root=args.root, dry_run=not args.apply))
        elif args.command == "reconcile-store":
            from app.deployment.reconcile import reconcile_cross_store
            _print(reconcile_cross_store(backup_id=args.backup_id, output=args.output))
        elif args.command == "reconcile-jobs":
            from app.deployment.reconcile import reconcile_durable_jobs
            _print(reconcile_durable_jobs(output=args.output))
        elif args.command == "restore":
            from app.deployment.restore import restore_backup
            _print(restore_backup(
                backup_root=args.root,
                backup_id=args.backup_id,
                environment_name=args.environment,
                confirmation=args.confirm,
                ollama_stopped_ack=args.ollama_stopped,
                output=args.output,
            ))
        elif args.command == "rebuild-hnsw":
            from app.deployment.restore import rebuild_hnsw
            _print(rebuild_hnsw(ollama_stopped_ack=args.ollama_stopped))
        elif args.command == "recovery-mode":
            from app.deployment.readiness import clear_recovery_mode, set_recovery_mode
            if args.action == "enter":
                set_recovery_mode(args.reason)
            else:
                clear_recovery_mode()
            _print({"recovery_mode": args.action})
        return 0
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "error_code": str(exc) or type(exc).__name__}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
