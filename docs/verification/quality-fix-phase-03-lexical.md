# Quality Fix Phase 03 — Block 4 Lexical Semantics

Date: 2026-08-19

## Strategy comparison

The frozen 32-case dataset was evaluated with unchanged dense retrieval, RRF, Top-K, document filtering, hydration, and output schema.

| Strategy | Lexical non-empty | Lexical expected solution | Hit@1 | MRR | Decision |
|---|---:|---:|---:|---:|---|
| Strict websearch | 0.00% | 0.00% | 85.19% | 88.89% | Retained as first attempt |
| Safe all-lexeme OR | 100.00% | 96.30% | 62.96% | 76.85% | Rejected: excessive noise/regression |
| Four-rarest conjunction fallback | 18.75% | 22.22% | 85.19% | 88.89% | Selected |

## Selected production behavior

1. Run parameterized `websearch_to_tsquery('simple', query_text)`.
2. Only when strict search has no matches, derive distinct normalized lexemes with parameterized `to_tsvector('simple', query_text)`.
3. Discard lexemes absent from the already document-filtered corpus, order by corpus rarity, select at most four, and form a quoted conjunction using PostgreSQL `quote_literal`.
4. Execute the existing GIN-backed `lexical_tsv @@ tsquery` search and `ts_rank_cd` ranking with the existing Top-K.

Raw user input is never concatenated into tsquery syntax. Unicode, punctuation-only input, duplicates, quotes, special characters, and injection-like input were tested. Document filters remain in SQL.

Result: PASS. Full diagnostics: `evaluation/reports/lexical_strategy_comparison_v1.json`.
