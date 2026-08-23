# Legal-RAG-V3 Targeted Grounding Amendment Experiment V1

This directory is an isolated Block 6 prompt-contract experiment. E0 is the immutable runtime `legal-rag-v3`; E1 and E2 are unregistered experiment-only prompts. Production remains `legal-rag-v2`.

The variants were authored from the predeclared H1–H4 hypotheses and frozen before any new provider output was generated:

- E1: whole-question sufficiency, exact proposition matching, claim-level citations, and scope discipline.
- E2: the same constraints with a bounded qualified-response policy for safely separable partial coverage.

No benchmark-specific rule, case identifier, real evaluation date, document name, or expected answer appears in either prompt. No additional few-shot was added because concise rules are the first tested intervention.

Primary comparison invariants: P0 selected context, `qwen3.5:9b`, tokenizer/chat template, temperature, provider, and generation settings are held constant. Checkpoint keys include prompt hashes. Output is diagnostic and does not authorize prompt activation.

Prompt hashes and measured token deltas are recorded by `runner.py` after the prompt files are frozen.

Frozen prompt fingerprints:

- E1: `ae7d35a85fdd5db661ed43b198c9dc67c6c6e2513b5a8b3989f83c963bd83da2` (491 system-prompt tokens; +171 vs E0).
- E2: `353c0aa1749be65b16eba59fa0708b0bc2c8cee4fbeeabd2dfcae5b3fc668e5f` (521 system-prompt tokens; +201 vs E0).

## Semantic diff from immutable E0

| Added constraint | E1 exact policy | E2 exact policy | Failure addressed | Regression risk |
|---|---|---|---|---|
| Material sub-question coverage | Every material requested conclusion must be directly established; otherwise `INSUFFICIENT_EVIDENCE` and stop | A safely separable supported part may be answered, but the unsupported part must be explicitly identified without supplying a concrete missing fact | Partial-coverage hallucination | E1 false abstention; E2 ambiguous qualification or continuation after insufficient marker |
| Proposition matching | Match actor, action, object, condition, threshold, date, exception, and scope; shared topic/article/similar wording is insufficient | Identical to E1 | Wrong-action and condition transfer | Overly literal interpretation |
| Claim-level citation alignment | Put a directly supporting source immediately after each material claim; a parent heading cannot substitute for a child rule; avoid citation dumping | Identical to E1 | Claim/source mismatch | Fragmented output or extra abstention |
| Scope discipline | Omit unnecessary broader provisions; if needed, state their separate condition/scope and cite directly | Identical to E1 | Harmful superfluousness | Less supplementary explanation |

Apart from H1's strict-versus-qualified policy, E1 and E2 use the same H2–H4 wording. They preserve the exact two-status and exact `[Sx]` contracts. No chain-of-thought or visible checklist was requested.
