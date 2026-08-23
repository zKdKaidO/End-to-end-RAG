# Frontend Product Design System V1

## Product direction

The interface is a legal-research workstation, not a general chatbot or a marketing dashboard. It favors compact navigation, readable evidence, explicit system states, and engineering detail on demand. Decorative gradients, glass surfaces, oversized type, and generic KPI cards are deliberately absent.

## Audit and reuse

The existing React 19, TypeScript, Vite, React Router, typed client, SSE parser, route pages, and backend response types were retained. Reusable status, error, evidence, citation, JSON, table, and drawer behaviors were consolidated in `frontend/src/components/Common.tsx`. The existing API contracts and route set were preserved.

The prior handcrafted CSS architecture was viable, so Tailwind and shadcn were not introduced. Migrating the small working interface would have added a second styling abstraction without improving its runtime contract. Motion was also omitted: the product has no state transition that needs a dedicated animation runtime.

## Tokens

- Typography: Inter-like system sans stack for UI; Georgia/Times for long legal evidence; SFMono/Consolas for IDs, ranks, hashes, model names, and request identifiers.
- Spacing: the layout uses the 4/8/12/16/24/32/48 scale, with small optical adjustments only for borders and controls.
- Radius: 6 px controls, 8 px panels, 10 px major bounded workspaces.
- Surfaces: flat neutral background, opaque primary surface, subtle secondary surface, and 1 px dividers. Elevation is limited to modal drawers and citation previews.
- Accent: one restrained legal blue. Muted green, amber, and red are reserved for semantic state.
- Themes: light and dark token sets are selected by a persistent shell toggle. System preference is the initial default.
- Motion: no decorative animation. `prefers-reduced-motion` suppresses transitions and smooth behavior globally.

## Shared components

- `PageHeading` establishes page title, context, and optional primary action.
- `Metric` creates compact grouped metric rows rather than oversized dashboard tiles.
- `StatusBadge` renders backend state without changing its meaning.
- `ErrorNotice` preserves safe backend messages and request IDs.
- `Drawer` supplies labelled modal semantics, Escape close, focus containment, and focus restoration.
- `CitedAnswer`, `SourceList`, and `SourceDrawer` make mapped citations keyboard-operable and provenance-first.
- `CandidateTable` and `EvidenceCards` progressively expose large diagnostic payloads.

## Responsive contract

- Above 1180 px: 216 px workstation navigation, full labels, four-column document status, and wide diagnostics.
- 900–1180 px: 68 px compact icon navigation, contained diagnostic grids, and the Ask split workspace remains available.
- Below 900 px: Ask sources use a drawer, metrics wrap, debug stages stack, and evidence comparisons become one column.
- Below 680 px: the shell becomes a compact top navigation; all primary content is single-column and drawers use full width.

Tables can scroll inside their own bounded region. Primary answer text and document workflows never require page-level horizontal scrolling.

## Dependency decisions

- `lucide-react`: consistent, tree-shakeable application icons; replaces improvised glyphs without bringing a UI framework.
- `react-resizable-panels`: supplies accessible keyboard-aware split resizing, collapse, restore, and panel constraints. Implementing this interaction correctly with pointer, keyboard, and imperative collapse semantics was not justified in local code.

No Material UI, Ant Design, Bootstrap, Chakra, animation framework, or global client-state library was added.
