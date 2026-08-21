# Block 6 Phase 05 — Prompt registry and assembler

Added Git-controlled `app/prompts/legal-rag-v1.txt` and deterministic system/user messages. The system prompt requires evidence-only answers, `[S#]` citations, no invented IDs/facts, explicit insufficiency, and rejection of instructions embedded in evidence.

User query and evidence remain untrusted user-message data. Evidence is delimited by `BEGIN EVIDENCE` / `END EVIDENCE`; legal text is not deleted or reinterpreted as an instruction. No prompt database, CRUD API, or client prompt override exists.

Result: PASS.
