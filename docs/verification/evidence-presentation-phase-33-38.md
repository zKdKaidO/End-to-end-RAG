# Evidence Presentation Experiment — Phases 33–38

- Experimental calls used the real streaming provider adapter and the same
  strict accumulated-output status/citation parsers.
- All four full finalists achieved 100% status validity over 65 cases.
- The best finalist emitted no duplicate status markers and all answerable
  citations used valid exact syntax.
- The experiment did not ask for or record chain-of-thought.
- No production SSE event, parser, prompt loader, or GenerationProfile changed.
- No second LLM, classifier, reranker, query rewrite, cosine gate, context-budget
  increase, or evidence removal was introduced.

The best joint combination passes all ten acceptance rules: materially lower
false abstention, 10/10 unanswerable abstention, zero unsupported answers, 100%
status validity, improved citation validity and expected-source match, no
ground-truth ordering, one model call, reduced prompt tokens, and compatibility
with the existing first-marker buffering contract.

The compact prompt with current P0 also passed the full-corpus rules and
outperformed presentation-only P1. Therefore the measured decision-tree target
is **LEGAL-RAG-V3 DESIGN**. P1 is a smaller secondary gain and should remain an
experimental presentation candidate until that separate design phase decides
whether its added contract surface is worthwhile.

Production remains `legal-rag-v2`; Blocks 1–6 and Hierarchy Retrieval V2 are
unchanged.

