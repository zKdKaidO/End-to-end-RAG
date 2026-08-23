# Legal-RAG-V3 Targeted Real-Provider Validation

Date: 2026-08-22

Method: real `qwen3.5:9b`, production provider/tokenizer/generation parameters, frozen P0 selected contexts, five V3 generations per case.

| Case | ANSWERABLE | Grounded expected source | Citation valid | Status valid |
|---|---:|---:|---:|---:|
| `v2_bank_scope_ratios` | 5/5 | 5/5 | 5/5 | 5/5 |
| `v2_bank_below_80_measures` | 5/5 | 5/5 | 5/5 | 5/5 |
| `v2_civil_scope` | 0/5 | 0/5 | n/a (abstained) | 5/5 |
| `v2_cross_document_effective_dates` | 5/5 | 5/5 | 5/5 | 5/5 |

The frozen partial-support case is `v2_bank_below_80_measures`. V3 produced a qualified, cited answer in 5/5 targeted runs and in the full run; its wording is included in the human-review package. No semantic correctness judgment was automated.

`v2_civil_scope` remains **UNRESOLVED** despite valid status formatting. No prompt/context/retrieval change was made for it. Future target: Context Selection V2.
