# ZKD Compute Windows Productization — P2C.6

## Product boundary

ZKD Compute is packaged as a per-user, windowless PyInstaller **onedir**
application installed under `%LOCALAPPDATA%\Programs\ZKD Compute`. Persistent
data is deliberately separate at `%LOCALAPPDATA%\ZKD\Compute`:

- `state` — SQLite catalog and DPAPI-protected device credential;
- `config` — platform verification configuration;
- `documents` and `artifacts` — local PDF source data and RAG artifacts;
- `models` — managed E5/Hugging Face cache and release-managed generation runtime;
- `logs` — bounded privacy-safe JSONL audit logs;
- `tmp` — atomic staging files.

Upgrades replace application files only. Uninstall removes the application,
autostart, and URI registration but intentionally leaves product data. A future
explicit data-purge UI must own destructive deletion.

## Security and privacy

The packaged runtime retains literal `127.0.0.1`, OS-assigned ephemeral ports,
the production HTTPS origin, exact CORS/PNA rules, platform signed grants,
memory-only browser sessions, and canonical HMAC request signing. The Windows
named mutex prevents two user-runtime instances from owning the local endpoint.
The device private key remains Windows-DPAPI protected and is neither emitted
by status output nor application logs.

Logs rotate at 5 MiB with five backups. Their event schema records only request
ID, method/path, duration, and status. It deliberately excludes PDF/chunk text,
evidence, context, prompts, answers, credentials, tokens, MACs, headers, and
filesystem content.

## Startup, pairing, and lifecycle

The installer creates a per-user HKCU Run entry for `ZKD-Compute.exe
--background`; no SYSTEM service or visible console is required. Runtime signal
handling closes the control channel, loopback server, and embedded worker
boundary. Durable SQLite jobs are reconciled on the next start.

`zkd-compute://pair?request_id=<uuid>&token=<opaque>` is the sole accepted
companion URI. Its parser accepts exactly those two parameters, validates the
UUID and URL-safe token, redacts the token in diagnostics, and never interprets
URI fields as a command, path, or executable. Pairing tokens are only used for
the immediate server challenge completion and are not persisted.

## Models and local generation

Before ML modules initialize, the launcher sets Hugging Face cache locations to
`%LOCALAPPDATA%\ZKD\Compute\models\huggingface`. Users never configure
`PYTHONPATH` or `EMBEDDING_MODEL_CACHE_DIR`. The required embedding artifact is
still exactly `intfloat/multilingual-e5-base`; missing artifacts fail closed
with a typed availability state and never silently substitute a model.

`GenerationRuntimeManager` is the secure sidecar lifecycle boundary for the
existing `qwen3.5:9b` Ollama-compatible provider. It can launch only a
release-bundled executable with an expected SHA-256 and binds it to
`127.0.0.1:11434`. The repository intentionally does not invent an executable
download URL, checksum, or model binary. Release engineering must supply the
versioned, verified Ollama asset manifest and model-provisioning bundle before
normal-user automatic generation provisioning is enabled.

## Build and installer

The local dependency boundary is `requirements-local-compute.txt`; it excludes
PostgreSQL, Alembic, MinIO, Redis, RQ, and pgvector. Build a release artifact:

```powershell
python -m pip install -r requirements-local-compute.txt
python packaging/build_windows.py
python packaging/build_installer.py
```

The first command produces `build\windows\ZKD-Compute\ZKD-Compute.exe` when
PyInstaller is available. The second produces `build\installer\ZKD-Compute-
Setup.exe` when Inno Setup 6 (`ISCC.exe`) is installed. `build/` is gitignored;
models, private credentials, local data, and binaries are never committed.

## Product limits and next release requirements

- Text-native PDFs only; scanned/OCR PDFs are not supported in V1.
- Packaging must be built from a Windows Python environment with the ML native
  dependencies installed.
- A release must provide pinned checksums for the Ollama sidecar and Qwen model
  provisioner before automatic sidecar/model download can be enabled.
- Browser PNA permission remains a browser-controlled security prompt.
- No cloud hosting migration or cloud RAG-content transport is part of P2C.6.
