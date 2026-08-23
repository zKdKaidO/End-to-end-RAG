# Bootstrap runbook V1

1. Copy `.env.production.example` to a protected host location outside source control and replace every placeholder. Never commit that file.
2. Prepare explicit host paths for TLS certificate/key, Ollama models, recovery control, and backups. Backup storage must be encrypted and on a separate failure domain.
3. Set `PRODUCTION_ENV_FILE` to that protected file, supply the release pipeline's full `GIT_COMMIT_SHA`, and validate rendered Compose: `docker compose --env-file <env> -f deployment/docker-compose.production.yml config --quiet`.
4. Provision `qwen3.5:9b` explicitly. Online provisioning requires the operator acknowledgement flag; offline provisioning requires an independently verified artifact hash. See `model-provisioning-v1.md`.
5. Run the production preflight through the operations profile.
6. Start PostgreSQL. A fresh data directory runs `CREATE EXTENSION IF NOT EXISTS vector` before Alembic.
7. Run the one-shot migration service and require the reported revision to equal `auth_authorization_v1`.
8. Start the remaining stack and require `/live` and `/ready` to pass before routing traffic.
9. Create users with `python -m app.auth.cli`; no default application credentials exist.
10. Create and verify the first paired backup before admitting durable user data.

Generate `deployment/release-manifest.json` from the operations tool for every release, then have the host release step attach the built API/frontend image identities. Container processes intentionally have no Docker socket, so image IDs are release-pipeline metadata rather than runtime-discovered metadata.

Never use `docker compose down -v` in production. A normal restart must preserve all named volumes and external mounts.
