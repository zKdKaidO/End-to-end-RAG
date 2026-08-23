# Security Remediation Summary V1

| Attack | Before | Minimal change | After |
|---|---|---|---|
| Rapid invalid login | Every request reached Argon2 | Atomic Redis account/network token buckets | Bounded work, `429` + `Retry-After` |
| Concurrent provider calls | Cross-session inference unbounded | Redis rate + per-user/global leases | 1 admitted, excess rejected; stale recovery |
| Invalid/pathological PDF | Magic-only, whole-file buffer | Bounded streaming, structural/cap validation | Safe `400/413`; app remains healthy |
| Worker resource abuse | No container/job limits | Memory/CPU/PID bounds and timeouts | Blast radius bounded |
| Internal service bypass | Broad host bindings | Internal backend network, loopback public surfaces | No DB/Redis/MinIO host listeners; Ollama loopback |
| Secret disclosure | Tracked `.env`, fallback credentials | Rotate, untrack/ignore, require env secrets | Clean image and bundle |
| Internal error disclosure | Raw worker messages public | Stable sanitizer at public mappings | Diagnostic detail remains server-side |
| Browser/input hardening | No deliberate headers/global body cap | Security middleware/nginx headers and input caps | CSP/nosniff/frame/referrer/permissions; `413` |

No migration, database table, retrieval ranking, hierarchy, context, generation semantic, status parser, citation parser, model, or prompt change was made. Auth V1, History V1 and Frontend Product V1 remain green.

Known residuals are network-isolation-only Redis trust, local HTTP without HSTS, parser complexity, prompt-injection/legal-correctness limits, finite queue/log/backup retention, and the need to pre-seed model caches for egress-isolated workers.
