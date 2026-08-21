# Legal Corpus Scale + Evaluation V2 — Final Verification

Date: 2026-08-19

Final decision: **EVALUATION V2 BASELINE READY FOR HUMAN REVIEW**.

The supplied corpus was exhaustively preflighted without OCR. Three text-native PDFs were ingested through the real frozen production pipeline; two scan-like PDFs were explicitly excluded. Corpus integrity, provenance, indexing, dataset validation, immutable hashing, real-pipeline evaluation, deterministic metric arithmetic, failure attribution, Debug Cockpit compatibility, and full regressions all passed.

No production behavior in Blocks 1–6 changed. No table or schema was added. No retrieval, context, prompt, model, citation, or answerability parameter was tuned. The only UI/API work is read-only V2 artifact compatibility. Evaluation V1 is unchanged.

Measured weaknesses are preserved rather than fixed:

1. Complete multi-evidence retrieval was 33.33% across 9 multi-piece cases; six of those cases were incomplete.
2. Two single-evidence cases missed, including one wrong-document result.
3. Two fully supported answerable cases abstained; all ten unsupported cases also abstained correctly.
4. Lexical retrieval was non-empty for only 24.62% of cases and never used strict matching.
5. pgvector 0.5.1 ANN searches sometimes returned fewer than the configured 50 candidates under frozen filters.

Recommended next experiments are documented, not implemented, in `evaluation/reports/legal_eval_v2_recommendations.md`.
