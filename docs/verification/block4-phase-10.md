# Block 4 Phase 10 — Zero and edge cases

Status: PASS

Live API results:

| Case | HTTP | Result |
|---|---:|---|
| empty query | 400 | `VALIDATE_QUERY` |
| whitespace query | 400 | `VALIDATE_QUERY` |
| valid global nonsense query | 200 | 10 dense candidates, lexical empty |
| valid query filtered to nonexistent document | 200 | `results=[]` |
| 605-token query | 400 | `QUERY_EMBEDDING`; no truncation |

RRF unit cases additionally verify dense empty plus lexical nonempty, lexical empty plus dense nonempty, both empty, disjoint lists, and a single candidate with `final_rank=1`.
