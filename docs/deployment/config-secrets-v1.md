# Configuration and secrets V1

Production preflight rejects insecure cookies, disabled HSTS, non-HTTPS trusted origins, absent proxy trust, absent release/model identity, an unencrypted backup destination, a backup destination without separate-failure-domain acknowledgement, or an unwritable recovery-control path.

Secrets include the database password, MinIO credentials, bootstrap passwords, TLS private key, and any future provider credentials. They belong in a protected deployment environment file or secret manager, never image layers, source control, logs, backup manifests, or generated reports. `.env.production.example` contains placeholders only.

The edge proxy is authoritative for TLS. `TRUSTED_PROXY_CIDRS` must name only the actual proxy network. Cookies are secure, HTTP-only, same-site, and the API accepts mutating browser requests only from configured trusted origins.

Release identity, model digest, PostgreSQL/pgvector version, Alembic revision, and storage-format versions are non-secret compatibility metadata and are recorded in release/backup manifests.

`GIT_COMMIT_SHA` must be supplied by the release pipeline because production images do not contain `.git`. Long-lived production services use bounded Docker `json-file` logs configured by `LOG_MAX_SIZE` and `LOG_MAX_FILES`; these are operational size/count bounds, not legal-retention promises. RQ result and failure metadata use the separately configurable TTL values in the production environment.
