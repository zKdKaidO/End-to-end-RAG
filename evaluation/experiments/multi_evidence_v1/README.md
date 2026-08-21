# Multi-Evidence Retrieval Experiment V1

Offline-only replay and ablation over frozen Evaluation V2 artifacts.

Run inside the API container:

```text
python -m evaluation.experiments.multi_evidence_v1.runner
```

The runner:

- verifies the frozen V2 dataset hash;
- reads the existing V2 baseline retrieval snapshots;
- uses read-only access to `chunks` and `legal_units` for deterministic hierarchy relationships;
- reconstructs frozen RRF pools without changing production RRF;
- replays bounded hierarchy, wider-window, and coverage-aware strategies;
- sends every strategy through real frozen Block 5;
- invokes real frozen Block 6 only for the selected finalist and affected multi-piece cases;
- writes auditable reports under `evaluation/reports/`.

It must not be imported by `app/`. It creates no database data and does not alter production configuration, endpoints, Top-K, retrieval, context, or generation behavior.

