# Block 5 Phase 06 — Separator and exact token accounting

Status: PASS

Central separator:

```text
\n\n---\n\n
```

Tests verify no leading separator for one evidence, exactly one separator for two, and `N-1` separators for `N` evidence blocks.

`SelectedEvidence.token_count` counts the formatted block alone. `context_token_count` recounts the complete final string and includes all separators. Both additive and deliberately non-additive deterministic TokenCounter behavior are tested.

Verified invariant:

```text
TokenCounter.count(context_text) == context_token_count
```
