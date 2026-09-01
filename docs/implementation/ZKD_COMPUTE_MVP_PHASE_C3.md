# ZKD Compute MVP — Phase C.3

## Scope

Phase C.3 completes the deferred local hierarchy and context-compatibility
work for the standalone loopback local-compute service.  It does not change
the cloud Block 1–6 implementation, its PostgreSQL schema, any retrieval
parameters, or generation.  It does not add an LLM or a cloud dependency.

## Canonical DIRECT_CHILD semantics

The local implementation delegates expansion policy to the unchanged
`LegalHierarchyExpander`.  Its frozen semantics are:

- only the immutable canonical base window (up to the first ten RRF
  candidates) can be anchors;
- only an anchor with a legal-unit ID is eligible;
- expansion is exactly one hop: a unit whose `parent_id` is the anchor legal
  unit, never a parent, sibling, cousin, or deeper descendant;
- legal children are ordered by source position, legal-unit ID, chunk index,
  and chunk ID;
- the result retains every base candidate, emits children immediately after
  their anchor, gives base candidates precedence, and suppresses duplicate
  children found through multiple anchors;
- limits remain ten anchors, four children per anchor, twenty added children,
  and depth one;
- child candidates have no retrieval rank or dense/lexical/fusion score.  They
  instead carry `candidate_origin=HIERARCHY_CHILD`,
  `hierarchy_relation=DIRECT_CHILD`, legal-unit identity, and authoritative
  anchor references.

## Local hierarchy storage adapter

`LocalHierarchyRepository` reads only the active SQLite artifact selected by
the local retrieval request.  It resolves an anchor in that artifact, joins
only `legal_units.parent_id = anchor.legal_unit_id` to the artifact's chunks,
and returns the canonical `DirectChildRow` type.  It verifies:

- the catalog document, artifact, and active-artifact pointer agree;
- every resolved anchor and child has the selected document ID;
- an artifact from another document or a stale artifact is rejected rather
  than used;
- the expander's existing fail-safe baseline fallback is retained on a lookup
  invariant failure.

Local retrieval results include `artifact_id` as a local transport identity.
The canonical retrieval fields preserve document ID, chunk ID, legal-unit ID,
metadata, provenance, immutable RRF fields for base candidates, and explicit
hierarchy relation/anchor fields for expanded children.

## Block 5 compatibility

`local_compute.context_adapter` is intentionally a thin mapping.  It removes
only the local transport-only `artifact_id`, validates the remaining data as
the existing `RetrievedCandidate` model, and invokes the unchanged
`ContextBuilderService`.  There is no second context builder and no local
formatting, deduplication, ordering, source-numbering, or token-budget policy.

Consequently, the frozen Block 5 behavior remains authoritative:

- strictly increasing `context_candidate_order` determines deterministic
  evidence order;
- exact normalized-content deduplication is unchanged;
- source IDs are gapless `S1`, `S2`, …;
- the injected production `ContextTokenCounter` and 4096-token generation
  context budget are used;
- the exact top-evidence and ordinary token-budget stop reasons remain intact;
- selected evidence preserves source document/chunk identity, ranking signals
  where applicable, hierarchy anchor data, and provenance.

## Evidence and parity

`tests/unit/local_compute/test_hierarchy_context.py` uses a self-contained,
text-native Unicode PDF fixture containing a legal parent article with direct
clauses, the canonical PDF extractor/parser/chunker, real local E5 indexing,
local dense/FTS5/RRF retrieval, the shared direct-child expander, and the
production Qwen tokenizer/Block 5 builder.  It verifies repeatable expanded
ordering, direct-child provenance, document/artifact isolation, bounded
expansion, source numbering, deterministic context output, and a top-evidence
budget stop.  No LLM call is possible in this flow.

The canonical hierarchy unit suite verifies the pure policy independently of
PostgreSQL, including anchor ordering, limits, duplicate handling, and atomic
baseline fallback.  The canonical Block 5 service suite verifies its existing
input, provenance, determinism, and privacy semantics.

## Privacy and limitations

All C.3 data access is loopback-local SQLite under the local data root.  The
adapter sends neither query text nor evidence to a cloud service and logs no
raw query, evidence, or context.  Browser acceptance remains
`BROWSER_ACCEPTANCE_NOT_EXECUTABLE`; no browser-security workaround was
attempted.  Local production routing of context into generation remains out
of scope for this phase.

## Next phase

`P2C.4D LOCAL CONTEXT + GENERATION ROUTING FOUNDATION`.
