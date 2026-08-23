# Legal-RAG-V3 Final Ablation + Design Gate

## Frozen state

- Evaluation V1 SHA-256: `afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245`
- Evaluation V2 SHA-256: `ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842`
- Experimental prompt SHA-256: `cb43cd1998e857f232b8eb998a7021d51d68a6da74f91399c103fd2e577a6af1`
- Production prompt: `legal-rag-v2`
- Production changed: **NO**

## P0 versus P1

| Variant | Acceptance | False abstention | Citation presence | Citation validity | Expected source | Status validity |
|---|---:|---:|---:|---:|---:|---:|
| A: compact few-shot + P0 | 94.55% | 5.45% | 94.55% | 94.55% | 90.91% | 100.00% |
| B: compact few-shot + P1 | 92.73% | 7.27% | 92.73% | 92.73% | 90.91% | 100.00% |

P1 materially beneficial: **NO**.

On the 55 paired answerable cases, P1 had zero answerability gains and one loss (`v2_civil_effect_and_repeal`). For grounded expected-source completions it had one gain and one loss, a net change of zero (two-sided exact McNemar p = 1.0). The targeted 20-run grounded rate was identical at 75% for A and B. P1 therefore did not show a clear, repeatable benefit; prompt-only P0 is the smaller architecture change.

## Targeted 5-run repeatability

| Case | A answerable/grounded | B answerable/grounded | A/B status valid |
|---|---:|---:|---:|
| `v2_bank_scope_ratios` | 5/5, 5/5 | 5/5, 5/5 | 5/5, 5/5 |
| `v2_bank_below_80_measures` | 5/5, 5/5 | 5/5, 5/5 | 5/5, 5/5 |
| `v2_civil_scope` | 0/5, 0/5 | 0/5, 0/5 | 5/5, 5/5 |
| `v2_cross_document_effective_dates` | 5/5, 5/5 | 5/5, 5/5 | 5/5, 5/5 |

## Repeated safety

- Runs: 30 A + 30 B = 60
- Correct structured abstentions: 60/60
- Unsupported direct answers: 0
- Status failures: 0

The safety set comprised all 10 frozen unanswerable cases, run three times per variant. Every raw provider response began with exactly one valid `[STATUS: INSUFFICIENT_EVIDENCE]` marker. No duplicate or malformed first-line markers and no unsupported direct answers were observed.

## Partial-support / qualified-answer check

The frozen V2 dataset contains one `PARTIAL_SUPPORT` case: `v2_bank_below_80_measures`. Including five targeted repeats and the full-corpus run, both A and B produced 6/6 structured `ANSWERABLE` results, 6/6 valid citations, and 6/6 expected-source matches. No invalid or uncited completion was observed. This is the available deterministic conservatism check; it does not claim semantic entailment beyond the frozen expected-source contract.

## Multi-evidence breakdown

| Class | Cases | A accepted | B accepted | A grounded | B grounded |
|---|---:|---:|---:|---:|---:|
| single_evidence | 46 | 95.65% | 95.65% | 95.65% | 95.65% |
| multi_evidence | 9 | 88.89% | 77.78% | 66.67% | 66.67% |
| hierarchy_recovered | 5 | 100.00% | 100.00% | 80.00% | 100.00% |
| multi_document | 1 | 100.00% | 100.00% | 100.00% | 100.00% |

The strata overlap: hierarchy-recovered cases are also included in the single/multi evidence groups. P1's 1/5 hierarchy expected-source gain is a small subgroup signal, not a demonstrated general benefit; it was offset by a loss elsewhere and did not improve the targeted multi-evidence repeats.

## Civil scope

- A: 0/5 grounded
- B: 0/5 grounded
- Resolved: **NO**
- Future Context Selection V2 candidate: **YES**

Both variants also abstained on the single full-evaluation run. The same selected evidence was sufficient under the frozen case contract, so the prompt is not weakened further for this isolated case.

## Token and latency comparison

| Configuration | Prompt tokens | TTFT ms | Generation ms | Comparable total ms |
|---|---:|---:|---:|---:|
| production legal-rag-v2 | 2812.9 | 1783.9 | 2562.9 | 2959.1 |
| A: compact few-shot + P0 | 2795.4 | 758.2 | 1518.8 | 1783.1 |
| B: compact few-shot + P1 | 2714.7 | 1008.1 | 1698.2 | 1963.0 |

A/B comparable totals reuse the identical frozen retrieval/context timings and add the newly measured prompt/provider elapsed time; they are diagnostics, not an SLA.

The provider calls ran sequentially rather than interleaved; warm-up and host-load effects can influence TTFT and latency. Token counts are deterministic for the captured prompts, while latency comparisons are observational.

## Structured output contract

- A: 105/105 runs had one valid first-line marker; 0 duplicates; 0 malformed/missing.
- B: 105/105 runs had one valid first-line marker; 0 duplicates; 0 malformed/missing.
- Exact citations remained `[S1]`, `[S2]`, etc.; parser code was unchanged.

## Design gate

- Candidate: **PROMPT-ONLY LEGAL-RAG-V3**
- Gate pass: **YES**
- Next target: **LEGAL-RAG-V3 DESIGN**

PROMPT-ONLY LEGAL-RAG-V3 passes all nine design-gate criteria. P1 is excluded because it did not demonstrate a clear repeatable benefit sufficient to justify a Block 5 presentation-contract amendment.

The experimental prompt remains isolated. GenerationProfile still selects `legal-rag-v2`.

## Architecture and method limits

- Blocks 1–5, retrieval, hierarchy retrieval, context budget, production profile, parsers, and schema were not changed.
- P0 and P1 used identical selected chunk IDs for every case; only the model-facing presentation changed.
- No second LLM, classifier, semantic free-text status inference, or runtime evaluation ground truth was used.
- Semantic correctness is bounded by deterministic citation/expected-source checks; no LLM-as-judge claim is made.
