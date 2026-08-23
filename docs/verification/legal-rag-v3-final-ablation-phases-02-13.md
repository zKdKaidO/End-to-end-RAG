# Legal-RAG-V3 Final Ablation — Phases 02–13

Date: 2026-08-22 (Asia/Saigon)

## Controlled comparison

- A: `legal-rag-v3-compact-fewshot-experimental` + P0 current evidence presentation.
- B: the identical experimental prompt + P1 structural hierarchy presentation.
- Provider/model: Ollama / `qwen3.5:9b`.
- Temperature: 0.0; top-p: 0.9; top-k: 20; thinking: false.
- Tokenizer: Hugging Face `Qwen/Qwen3.5-9B`.
- Context budget: 4096; max output: 512; prompt safety margin: 32.
- The selected Block 5 chunk set was identical for A and B for every case. Only model-facing presentation differed.
- Intended analyzed calls: 210 (105 per variant). The final result contains exactly these 210 records.

## Full 55-case answerable evaluation

| Metric | A: compact few-shot + P0 | B: compact few-shot + P1 |
|---|---:|---:|
| Answerable acceptance | 94.55% (52/55) | 92.73% (51/55) |
| False abstention | 5.45% (3/55) | 7.27% (4/55) |
| Citation presence | 94.55% | 92.73% |
| Citation structural validity | 94.55% | 92.73% |
| Expected-source match | 90.91% (50/55) | 90.91% (50/55) |
| Missing citation among completed answers | 0% | 0% |
| Invalid citation among completed answers | 0% | 0% |
| Status validity | 100% | 100% |

Paired outcomes:

- Answerability: P1 gains 0, losses 1; exact two-sided McNemar p = 1.0.
- Grounded expected-source completion: P1 gains 1, losses 1; net 0; exact two-sided McNemar p = 1.0.
- Expected-source match: P1 gains 1, losses 1; net 0; exact two-sided McNemar p = 1.0.

P1 is not materially beneficial. It did not improve the targeted repeated cases, did not improve overall grounded conversion, and introduced one additional false abstention.

## Targeted repeatability

Each historical false-abstention case was generated five times per variant.

| Case | A answerable / grounded | B answerable / grounded | Status valid |
|---|---:|---:|---:|
| `v2_bank_scope_ratios` | 5/5 / 5/5 | 5/5 / 5/5 | 10/10 |
| `v2_bank_below_80_measures` | 5/5 / 5/5 | 5/5 / 5/5 | 10/10 |
| `v2_civil_scope` | 0/5 / 0/5 | 0/5 / 0/5 | 10/10 |
| `v2_cross_document_effective_dates` | 5/5 / 5/5 | 5/5 / 5/5 | 10/10 |

Targeted grounded conversion was 75% for both variants. `v2_civil_scope` also failed in both single full-evaluation runs. It remains a future Context Selection V2 candidate; the prompt should not be weakened for this case alone.

## Repeated safety and structured output

- Frozen unanswerable cases: 10.
- Repeats: 3 per case per variant.
- Total safety calls: 60.
- Correct structured abstentions: 60/60.
- Unsupported direct answers: 0/60.
- Exactly one valid first-line status marker: 60/60.
- Duplicate, missing, or malformed markers: 0.

Across targeted, full-answerable, and safety runs, A and B each had 105/105 valid first-line markers. Citation and answerability parsers were unchanged.

## Partial-support / qualified answer

The frozen dataset contains one `PARTIAL_SUPPORT` case, `v2_bank_below_80_measures`. Across five targeted repeats plus the full evaluation, both variants produced 6/6 answerable results, 6/6 valid citations, and 6/6 expected-source matches. No invalid or uncited completion was observed. These are deterministic structural/source checks, not a semantic-entailment claim.

## Evidence-type breakdown

The hierarchy and multi-document strata overlap with single/multi-evidence groupings.

| Stratum | Cases | A accepted | B accepted | A grounded | B grounded |
|---|---:|---:|---:|---:|---:|
| Single evidence | 46 | 95.65% | 95.65% | 95.65% | 95.65% |
| Multi evidence | 9 | 88.89% | 77.78% | 66.67% | 66.67% |
| Hierarchy recovered | 5 | 100% | 100% | 80% | 100% |
| Multi-document | 1 | 100% | 100% | 100% | 100% |

The 1/5 hierarchy-grounding gain for P1 is a small subgroup observation and was offset by a loss outside that subgroup. The five-run targeted multi-evidence outcomes were identical. The compact few-shot prompt improves general answerability relative to production; the evidence does not isolate its benefit to multi-evidence synthesis.

## Token and latency diagnostics

| Configuration | Prompt tokens mean | TTFT mean ms | Generation mean ms | Comparable total mean ms |
|---|---:|---:|---:|---:|
| Production `legal-rag-v2` | 2812.9 | 1783.9 | 2562.9 | 2959.1 |
| A: compact few-shot + P0 | 2795.4 | 758.2 | 1518.8 | 1783.1 |
| B: compact few-shot + P1 | 2714.7 | 1008.1 | 1698.2 | 1963.0 |

A/B totals add measured experimental provider elapsed time to identical frozen retrieval/context timings. Calls ran sequentially, not interleaved, so host-load and warm-up effects limit latency inference. Token counts are deterministic for the captured prompts; latency is observational and not an SLA.

## Design gate

Selected candidate: **PROMPT-ONLY LEGAL-RAG-V3**.

All nine design criteria pass for A: material false-abstention reduction versus production, 100% repeated safety, zero unsupported answers, 100% status validity, preserved/improved citation validity and expected-source performance, no second LLM, no semantic status inference, and no runtime evaluation-ground-truth dependency.

P1 is rejected as unnecessary production complexity. This is a design recommendation only; production remains `legal-rag-v2`.
