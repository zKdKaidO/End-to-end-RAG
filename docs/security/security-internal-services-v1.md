# Internal Services V1

## Pre-hardening exposure

Docker published PostgreSQL 5432, Redis 6379, MinIO 9000/9001, API 8001 and frontend 5173 broadly; host Ollama listened on all interfaces. Redis accepted unauthenticated `PING`, and direct PostgreSQL connectivity reached password authentication. MinIO objects were private (`403`) but its management/API surface was reachable. Ollama browser-origin policy rejected a hostile origin, but a non-browser LAN client could bypass product admission.

## Remediation and final state

PostgreSQL, Redis and MinIO now live only on an internal Docker network and have no host listeners. Workers use that internal network and cannot reach the public Internet. API and frontend bind only `127.0.0.1`. Ollama's user-level host setting is `127.0.0.1:11434`; the API can reach it through `host.docker.internal`, but the LAN address cannot.

Final listeners were only `127.0.0.1:5173`, `127.0.0.1:8001`, and `127.0.0.1:11434`. PostgreSQL 5432, Redis 6379 and MinIO 9000/9001 had no host listeners. Debug/evaluation flags default false in compose and remain admin-gated when enabled. MinIO continues to deny anonymous source-object reads. Browser users have no Redis/RQ route.
