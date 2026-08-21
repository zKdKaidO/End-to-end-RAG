# Hierarchy V2 Phases 21–25 — Observability and Tests

Status: **PASS**

DebugTrace now exposes Dense, Lexical, immutable RRF candidates, hierarchy candidates, final context order, Block 5, and Block 6. The hierarchy diagnostic object includes enablement, anchor/unit counts, expansion/absence counts, examined/added/duplicate/filter counts, per-anchor/global caps, fallback state, and lookup/total timing.

The Debug Cockpit adds read-only hierarchy and final-order panels. It exposes child identity, legal unit, origin, relation, depth, primary/all anchors, context order, content preview, and stored provenance. No hierarchy tuning control was added.

New deterministic tests cover no unit, leaf unit, direct children, both caps, one-hop-only SQL, base-wins dedup, multiple anchors, document isolation, ordering, null diagnostics, immutable RRF rank, gapless context order, single bulk lookup, fallback, real provenance, Block 5 nullable fields, and disabled/noncanonical behavior.

Targeted hierarchy/context/repository tests: **34 passed**. Final complete backend result is recorded separately.

