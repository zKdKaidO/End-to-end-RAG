# Corpus V2 Phase 01 — Pre-flight

Date: 2026-08-19

## Input PDFs

- Supplied: 5
- READY: 3
- Excluded: 2
- Encrypted: 0
- Invalid: 0

Native extraction classified `104.2026.TT-BQP.pdf` (5 pages, 4 extracted characters) and `Nghị-định-273-2026-NĐ-CP.pdf` (67 pages, 66 extracted characters) as `TEXT_TOO_SPARSE_OR_SCAN_LIKE`. Representative first-page renders confirm that both contain visible scanned legal text, but OCR is outside the frozen text-native pipeline and was not used.

READY inputs:

- `Thong tu quy dinh thuc hanh cong tac xa hoi va cap nhat kien thuc cong.pdf` — 18 pages, 33,196 extracted characters.
- `Thông tư 40.2026.TT-NHNN.pdf` — 21 pages, 33,886 extracted characters.
- `VBHN 10.2026.pdf` — 66 pages, 157,065 extracted characters.

The exhaustive hashes, byte sizes, encryption flags, extraction counts, and classifications are in `evaluation/reports/legal_corpus_v2_preflight.json` and `.md`.

## Frozen gates

- Evaluation V1 SHA-256: `afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245` — PASS.
- Backend intended-stack baseline: 192 collected, 192 passed, 0 failed, 8 warnings, 88.57 seconds.
- Frontend baseline: 10 passed, 0 failed.
- Frontend production build: PASS.

An initial backend attempt found the processing worker stopped and produced one `PENDING` queue timeout. After starting the existing frozen worker services, the required full rerun was clean; no code or data contract was changed.

Result: PASS — three usable PDFs remain, so Corpus V2 proceeds with those inputs only.
