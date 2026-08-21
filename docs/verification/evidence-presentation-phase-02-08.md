# Evidence Presentation Experiment — Phases 02–08

## Frozen production baseline

- provider/model: `ollama` / `qwen3.5:9b`
- production prompt: `legal-rag-v2`
- prompt SHA-256: `a41efc38ab53ad84550de27d913b13b4b6742aabe7a55a67f92685d132f303ee`
- tokenizer: `huggingface` / `Qwen/Qwen3.5-9B`
- chat-template SHA-256: `a4aee8afcf2e0711942cf848899be66016f8d14a889ff9ede07bca099c28f715`
- model context: 32,768 tokens
- Block 5 context budget: 4,096 tokens
- max output: 512 tokens
- safety margin: 32 tokens
- temperature/top-p/top-k: 0.0 / 0.9 / 20
- thinking: false
- status parser: strict, deterministic, exactly one marker
- citation parser: exact `[S<n>]` syntax
- streaming contract: `start`, `delta*`, `done` or `start`, `delta*`, `error`; initial status buffered and stripped

## Diagnostic set

The harness uses only the 65 frozen Evaluation V2 cases: all four historical
complete-context false abstentions, six repeated successful controls, all 55
answerable cases (including nine multi-evidence, five hierarchy-recovered, and
one multi-document case), and all ten unanswerable cases (six hard/topically
close and four out-of-corpus). No new ground truth was created.

## Repeated production baseline

- targeted runs: 12
- ANSWERABLE: 3
- INSUFFICIENT_EVIDENCE: 9
- grounded expected-source: 3
- stable false abstentions: bank scope ratios, below-80 measures, civil scope
- historical cross-document false abstention: not reproduced (3/3 grounded)
- successful controls: 18/18 ANSWERABLE and grounded
- unanswerable controls: 30/30 abstained, 0 unsupported answers

## Context/distraction diagnosis

`v2_civil_scope` contains 4,049 tokens, 17 selected blocks, one supporting
block at S1, 16 diagnostic distractors, and about 3,482 tokens after the
supporting block. This remains strong case-specific distraction evidence.

Across all 52 complete-context answerable cases, however, context length was
not a useful general separator (point-biserial correlation -0.056). Distractor
count correlation was 0.180 and hierarchy-child-count correlation was 0.233.
These are descriptive, small-sample correlations and do not prove causality.

## Oracles (not production eligible)

With unchanged `legal-rag-v2`, both minimal-support and expected-first full
context produced 6/12 grounded runs (50%). Both bank cases were 3/3; civil
scope and cross-document dates were 0/3. These are prompt-specific diagnostic
ceilings, not universal model-capability ceilings.

## Runtime-available presentation features

The production-plausible strategies use only query text, current order,
retrieval rank, source identity, candidate origin, direct-child anchor fields,
document/legal-unit identity, and deterministic query/text lexical overlap.
Expected chunk IDs, acceptable evidence sets, labels, and human-selected
support are absent from every production-plausible algorithm.

