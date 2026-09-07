# Isolated staging Compute profile

The installed production companion at `F:\ZKD Compute` is not used or
modified for this test. `zkd://` remains production-only.

| Property | Production (default) | Staging (`--profile staging`) |
| --- | --- | --- |
| platform and allowed browser origin | `https://rag.zkd.id.vn` | `https://zkd-control-plane-staging.zkd-rag.workers.dev` |
| persistent root | `%LOCALAPPDATA%\ZKD\Compute` | `%LOCALAPPDATA%\ZKD\Compute-Staging` |
| grant verifier | existing production config file | staging-only config file |
| mutex | `Local\ZKD.Compute.Runtime.V1` | `Local\ZKD.Compute.Staging.Runtime.V1` |
| tray label | `ZKD Compute — …` | `ZKD Compute [STAGING] — …` |

The only write performed by the helper is the supplied staging *public* key:

```powershell
A:\RAG\build\windows\ZKD-Compute\ZKD-Compute.exe --profile staging --provision-staging-key
A:\RAG\build\windows\ZKD-Compute\ZKD-Compute.exe --profile staging --status
A:\RAG\build\windows\ZKD-Compute\ZKD-Compute.exe --profile staging
```

It writes `%LOCALAPPDATA%\ZKD\Compute-Staging\config\platform-grant-public.b64`.
It never reads, writes, copies, or replaces the production key, catalog,
device identity, grant-consumption state, or pairing state. The Hugging Face
cache remains shared read-only by design.

Before a browser/device test, an operator must provision a staging account in
D1 with a PBKDF2 credential as described in `README.md`. There is currently no
public registration route because the existing product only has authenticated
login; the Worker intentionally does not invent a self-service registration
policy during this migration.
