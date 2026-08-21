# Abstention Prompt Variant Comparison V1

Production-eligible finalist: **NONE** (`NO_VARIANT_PRESERVED_FULL_CORPUS_GROUNDING`).
Best diagnostic full-corpus variant: **combined**.

| Variant | Targeted answerable | Grounded conversion | Unanswerable abstention | Unsupported | System-token delta |
|---|---:|---:|---:|---:|---:|
| variant-a | 75.00% | 50.00% | 100.00% | 0 | -13 |
| variant-b | 75.00% | 50.00% | 100.00% | 0 | +8 |
| fewshot | 75.00% | 50.00% | 100.00% | 0 | +72 |
| combined | 75.00% | 50.00% | 100.00% | 0 | +38 |

## Full 55-answerable runs for every safety-passing finalist

| Variant | Accepted | False abstention | Citation validity | Expected source | Status failures | Mean generation |
|---|---:|---:|---:|---:|---:|---:|
| variant-a | 92.73% | 7.27% | 74.55% | 74.55% | 0 | 2930.3 ms |
| variant-b | 92.73% | 7.27% | 72.73% | 69.09% | 0 | 2851.4 ms |
| fewshot | 92.73% | 7.27% | 12.73% | 12.73% | 0 | 3223.8 ms |
| combined | 90.91% | 7.27% | 87.27% | 85.45% | 1 | 3366.9 ms |

## Full frozen answerable comparison

| Metric | legal-rag-v2 frozen run | Best diagnostic variant |
|---|---:|---:|
| Answerable accepted | 87.27% | 90.91% |
| False abstention | 12.73% | 7.27% |
| Citation presence | 87.27% | 87.27% |
| Citation structural validity | 87.27% | 87.27% |
| Expected-source match | 85.45% | 85.45% |

## Segment acceptance under finalist

- known_false_abstention_cases: 75.00%
- multi_evidence: 66.67%
- multi_document: 100.00%
- hierarchy_required_evidence: 80.00%

## Interpretation boundary

A conversion is counted as grounded only when the authoritative ANSWERABLE marker is valid and mapped citations contain a complete frozen acceptable evidence set. This is deterministic expected-source matching, not semantic-entailment adjudication. Raw answers and evidence remain available for human legal review.
