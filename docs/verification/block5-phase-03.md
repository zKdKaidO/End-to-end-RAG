# Block 5 Phase 03 — Conservative exact deduplication

Status: PASS

V1 dedup key:

```text
(document_id, collapse_whitespace(Unicode_NFC(content_text)).strip())
```

Tests verify:

- exact and whitespace-equivalent text in one document deduplicates;
- Unicode NFC-equivalent text deduplicates;
- the highest-ranked occurrence is retained;
- original content is not mutated;
- identical text from distinct documents is preserved;
- similar legal wording is preserved;
- case and Vietnamese accents are not removed or folded;
- output order remains deterministic.

No semantic, fuzzy, embedding, MinHash, or LLM deduplication exists.
