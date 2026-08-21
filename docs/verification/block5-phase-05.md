# Block 5 Phase 05 — Greedy budget selection

Status: PASS

Selection evaluates deduplicated candidates in strictly increasing `final_rank`. It formats a prospective `S<n>` block, counts the complete piece, verifies the exact prospective full-context count, and accepts only a whole chunk that fits.

At the first failure the loop stops. Lower-ranked candidates are not formatted or counted. Evidence numbering increments only after acceptance.

Tests cover all-fit, first-too-large, first-fit/second-fail, several-fit/next-fail, exact budget, one-token-short budget, lower-candidate non-inspection, no truncation, rank preservation, and contiguous numbering after a removed duplicate.

No skip-and-continue or truncation path exists.
