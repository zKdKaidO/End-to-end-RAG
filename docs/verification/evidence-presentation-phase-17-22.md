# Evidence Presentation Experiment — Phases 17–22

## Joint status/citation contract

Experimental prompts preserve the existing first-line status markers and exact
`[S1]` citation syntax. They do not introduce JSON or chain-of-thought. The
compact forms place status, qualified-answer, citation, and abstention rules
adjacently and explicitly prohibit repeating the marker.

## Duplicate-status reproduction

The historical previous-combined output failure reproduced 3/3. Every raw
provider output contained two status markers and two complete answer blocks.
The strict parser correctly rejected all three. The duplicate therefore exists
before parser/stream processing and is a repeatable prompt/model output-contract
failure, not a streaming artifact. Parser behavior was not changed.

## Citation fading

Previous full-answerable citation validity: variant A 74.55%, B 72.73%, old
few-shot 12.73%, combined 87.27% (with one status failure). The old few-shot
also added 72 system tokens. The new compact variants keep citation rules next
to ANSWERABLE output syntax and achieved 92.73–94.55% full-answerable citation
validity with 100% status validity. This supports instruction placement and
example design as material factors; prompt length alone does not explain the
old degradation.

## Small cross-matrix targeted results

| Prompt + presentation | Answerable | Grounded | Citations valid | Safety |
|---|---:|---:|---:|---:|
| legal-rag-v2 + P0 | 25% | 25% | 25% | 10/10 |
| legal-rag-v2 + P1 | 50% | 50% | 50% | 10/10 |
| compact + P0 | 75% | 75% | 75% | 10/10 |
| compact + P1 | 75% | 75% | 75% | 10/10 |
| compact few-shot + P1 | 75% | 75% | 75% | 10/10 |

No combination produced an unsupported answer in the safety screen.

