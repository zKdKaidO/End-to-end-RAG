# Block 4 Phase 11 — Performance and N+1

Status: PASS

Small-scale canonical diagnostics, without an SLA claim:

| Query | Embed ms | Dense ms | Lexical ms | Fusion ms | Hydration ms | Total ms |
|---|---:|---:|---:|---:|---:|---:|
| semantic-style | 44.011 | 6.377 | 1.660 | 0.037 | 0.866 | 53.006 |
| keyword-heavy | 54.807 | 4.857 | 1.724 | 0.057 | 0.555 | 62.063 |
| warm nonsense API request | 27.180 | 7.164 | 0.910 | 0.077 | 0.761 | 36.750 |

The first API request after process restart included model construction and took about 7.88 seconds; subsequent warm requests reused the singleton and persistent cache.

Hydration uses one `ANY(uuid[])` bulk query. The recording test confirms one execute call for multiple final IDs. N+1 queries: NONE.
