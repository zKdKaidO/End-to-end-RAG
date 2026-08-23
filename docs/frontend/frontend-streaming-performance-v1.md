# Frontend Streaming Performance V1

## Wire contract

`streamAnswer` retains the existing `fetch` + `ReadableStream` implementation and the backend's `start`, `delta`, `done`, and `error` SSE events. Cancellation uses the request's `AbortController`; unmount aborts the same controller. The backend event schema is unchanged.

## Rendering design

`useBufferedStream` separates transport frequency from React rendering:

1. Each `delta` appends text to a mutable ref.
2. The first pending delta schedules one 48 ms flush.
3. Further deltas accumulate without `setState`.
4. A flush commits the complete buffered value once.
5. `done` cancels a pending timer and commits authoritative `answer_text` immediately.
6. Reset and unmount clear the pending timer.

The query composer and application shell sit outside the streaming session. The answer renderer is memoized, as are diagnostic candidate lists. No global state library is involved.

## Development instrumentation

Development builds expose a collapsed “Streaming diagnostics” region showing:

- incoming provider delta count;
- visible React state commit count;
- configured 48 ms cadence.

The deterministic high-frequency test sends 100 deltas synchronously. They produce one authoritative visible commit when `done` arrives, demonstrating that visible commits can be substantially lower than wire deltas. Coarser real provider chunks may naturally approach a 1:1 ratio; the UI does not manufacture delay when batching is unnecessary.

The live production-container smoke completed a real answer with three mapped sources. Exact provider delta count is intentionally available only in a development build; production carries no analytics or instrumentation payload.

## Lifecycle verification

Tests cover completed insufficient evidence, rapid deltas, explicit cancellation, provider rejection, and component cleanup through Testing Library teardown. The implementation has one timer and one AbortController per active research session, with both cleaned on replacement or unmount.

## Known constraints

- Token cadence and TTFT are provider/runtime characteristics; the browser reports rendering cadence only.
- Long answer text is currently rendered as one memoized citation-aware block. The measured development corpus exceeded 1,000 list rows, so Documents uses 100-row progressive disclosure; bounded answer/source payloads do not require virtualization.
- Citation metadata becomes available in the authoritative `done` event, so citation controls activate at completion while answer text can render earlier.
