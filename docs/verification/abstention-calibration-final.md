# Supported-Case Abstention Calibration Experiment V1 — Final Verification

Status: **COMPLETE; MORE DIAGNOSIS REQUIRED BEFORE A PRODUCTION PROMPT CHANGE**.

## Integrity

- Evaluation V1 SHA-256: `afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245`
- Evaluation V2 SHA-256: `ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842`
- Production prompt: `legal-rag-v2`, unchanged
- Production prompt SHA-256: `a41efc38ab53ad84550de27d913b13b4b6742aabe7a55a67f92685d132f303ee`
- Production model: `qwen3.5:9b`, unchanged
- Production database tables added: **0**

## Measured diagnosis

- Historical complete-context false-abstention cases: **4**.
- Current-prompt repeats: **3 ANSWERABLE / 9 INSUFFICIENT** across 12 calls.
- Stable false abstentions: **3**; one historical cross-document failure did not reproduce (3/3 grounded answers).
- Successful answerable controls: **18/18 ANSWERABLE with expected sources**.
- Unanswerable repeatability: **30/30 abstentions; 0 unsupported direct answers**.
- Every experimental prompt: **10/10 unanswerable abstentions; 0 unsupported direct answers**.
- Evidence-first: **6/12** grounded answers versus current order **3/12**; effect was case-specific.
- Minimal sufficient context: current prompt **6/12**, best diagnostic combined prompt **9/12** status acceptance but only **6/12** expected-source citation matches.
- Model capacity was not the dominant limitation: the unchanged 9B model answered three diagnostic cases under controlled conditions.

## Full-corpus guard

All four safety-passing experimental prompts ran across all 55 frozen answerable cases.

- A: false abstention 7.27%, citation validity 74.55%, expected source 74.55% — rejected.
- B: false abstention 7.27%, citation validity 72.73%, expected source 69.09% — rejected.
- Few-shot: false abstention 7.27%, citation validity 12.73%, expected source 12.73% — rejected.
- Combined: false abstention 7.27%, citation validity 87.27%, expected source 85.45%, but one duplicate status marker — rejected.

No variant satisfied every frozen selection rule. Production recommendation: **NO CHANGE**.

## Regression

- Backend: **230 passed, 0 failed, 8 warnings in 95.02s**.
- Frontend: **11 passed, 0 failed**.
- Frontend build: **PASS**.

Primary artifacts are `evaluation/reports/abstention_calibration_experiment_v1.md`
and `evaluation/reports/abstention_calibration_experiment_v1.json`.
