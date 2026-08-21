# RAG Evaluation Gate V1 — Phase 02 Dataset

Created `evaluation/datasets/legal_eval_v1.json` with 32 strict cases: 27 answerable and 5 unanswerable. Categories cover direct facts, semantic paraphrases, legal identifiers, deeper-rank evidence, multi-evidence solutions, document filters, explicit unanswerable questions, and out-of-corpus questions.

Corpus limitation: only one substantive indexed legal document is available (`sample_legal.pdf`, Nghị định 135/2026/NĐ-CP, 76 chunks). The dataset therefore favors 32 high-quality cases over fabricated breadth.

Validation against PostgreSQL confirms one real referenced document and 32 real `block3-v1` chunks. All answerable references have content, provenance, matching document ownership, and a review excerpt present in the referenced evidence. Unanswerable cases declare no expected evidence.

Result: PASS.
