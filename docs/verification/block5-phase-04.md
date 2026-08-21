# Block 5 Phase 04 — Evidence formatter

Status: PASS

Stable prompt-facing template:

```text
[Evidence S1]
Nguồn: <document type/number/title from actual metadata>

Nội dung:
<original content_text>
```

Only actual `document_type`, `document_number`, and `title` values are used for legal identity. Missing identity is explicitly reported as unavailable in metadata; no legal identity is fabricated.

Tests verify original content preservation and confirm that pages, chunk/document UUIDs, scores, raw provenance, internal metadata keys, issuing authority, and whole metadata JSON are not rendered by default.
