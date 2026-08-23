# Legal-RAG-V3 Human Legal Review Gate — Verification

Date: 2026-08-22

Status: **READY FOR HUMAN REVIEW — PRODUCTION NOT ACTIVATED**

## Scope and integrity

This phase prepared the existing eight-case legal-review queue for a human reviewer. It did not rerun evaluation, change frozen labels, make legal judgments, or alter production behavior.

Verified SHA-256 values:

- Evaluation V1: `afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245`
- Evaluation V2: `ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842`
- `legal-rag-v2`: `a41efc38ab53ad84550de27d913b13b4b6742aabe7a55a67f92685d132f303ee`
- experimental `legal-rag-v3`: `35b0abd69608ef574ac7bbf5c314eadb6ef9decd0dda3dd60e0a170aad243ebf`

All hashes matched their approved values. The production default remains `legal-rag-v2`.

## Authoritative review queue

The queue was loaded from `evaluation/reports/legal_rag_v3_production_validation_v1.json`; it was not reconstructed from model judgment. It contains eight cases:

1. `v2_bank_actual_capital_formula`
2. `v2_bank_below_80_measures`
3. `v2_bank_scope_ratios`
4. `v2_civil_scope`
5. `v2_social_applicable_groups`
6. `v2_social_effective_transition`
7. `v2_social_plan_submission_filter`
8. `v2_social_practice_content`

Review-reason counts (categories can overlap): unexpected source 3, qualified answer 1, V3 answerability gain 3, multi-evidence 3, unresolved abstention 3.

## Packet construction

The deterministic offline generator `evaluation/human_legal_review_gate.py` performed read-only bulk hydration of the expected, selected, and cited chunks. It recorded full chunk text, document identifiers and hashes, filenames, metadata, provenance, article/clause/point/page lineage, retrieval origin and rank, context order, hierarchy relation, V2/V3 output, and engineering metrics.

No LLM-as-judge was used. Every legal decision field is deliberately blank. Generated validation found:

- 8/8 queue cases represented;
- expected and cited/selected source text present where applicable;
- all specialized review sections present;
- 0 populated human-decision fields;
- 0 packet validation errors.

For all three unexpected-source cases, the automated packet records the legal relationship as `INSUFFICIENT_FOR_AUTOMATIC_DETERMINATION`. Structural relationships such as same-document or same-article are supplied only as reviewer aids and are not legal conclusions.

The qualified-answer packet isolates each answer proposition and citation scope so the reviewer can determine whether the supplementary measures are responsive or overbroad. Multi-evidence packets show each required chunk's selected/cited state and the alternative citations actually used.

`v2_civil_scope` is recorded as a false abstention despite complete expected evidence in retrieval/context. Consistent with the approved gate instructions, it is a future `CONTEXT_SELECTION_V2` candidate and is not, by itself, a V3 activation blocker unless human review identifies a separate safety issue.

## Human decision form and activation rules

The separate review form leaves these fields blank for every case: disposition, expected-source judgment, actual-source judgment, grounding/safety finding, blocker status, reviewer identity, date, and notes.

Activation is not permitted until a qualified human legal reviewer completes every required decision. Expected-source mismatch alone is not an automatic failure. A candidate is blocked when human review finds a materially unsupported or conflicting legal proposition, an unsafe qualification, or another explicit activation-blocking issue. No dataset or ground-truth update is authorized by this packet.

## Existing review UI

The existing `/evaluation` UI can display frozen Evaluation V2 case details and source/chunk information. It does not require modification for this gate. Its rerun action uses the production profile (`legal-rag-v2`) and must not be treated as a V3 result; authoritative V3 outputs are the frozen validation snapshots included in the packet.

## Regression evidence

- Backend: 245 collected, 245 passed, 0 failed, 8 warnings, 92.27 seconds.
- Frontend: 5 test files, 11 tests passed, 0 failed, 1.04 seconds.
- Production build: PASS, 30 modules transformed, 124 ms.

The backend pytest process emitted its complete successful summary before the surrounding Docker pipe was interrupted after it lingered; the recorded pytest result is authoritative.

## Change audit

- Blocks 1–5: unchanged by this review phase.
- Block 6 production behavior: unchanged by this review phase.
- Production prompt: `legal-rag-v2` (unchanged).
- Retrieval, hierarchy retrieval, context budget, parsers, and datasets: unchanged.
- Schema drift: none.
- New production tables/services: none.

## Artifacts

- `evaluation/reports/legal_rag_v3_human_legal_review_gate_v1.md`
- `evaluation/reports/legal_rag_v3_human_legal_review_gate_v1.json`
- `evaluation/reports/legal_rag_v3_human_review_form_v1.md`

Final engineering decision: **READY FOR HUMAN REVIEW**. Legal-RAG-V3 remains inactive until the human legal review gate is completed.
