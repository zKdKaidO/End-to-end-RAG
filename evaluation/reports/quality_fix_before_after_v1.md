# Targeted RAG Quality Fixes V1 — Before / After

Frozen dataset SHA-256: `afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245` (unchanged).

| Metric | Before | After |
|---|---:|---:|
| Hit@1 | 85.19% | 85.19% |
| Hit@3 | 92.59% | 92.59% |
| Hit@5 | 92.59% | 92.59% |
| Hit@10 | 92.59% | 92.59% |
| MRR | 88.89% | 88.89% |
| Lexical non-empty | 0.00% | 18.75% |
| Lexical expected solution | 0.00% | 22.22% |
| Context retention | 100.00% | 100.00% |
| Citation presence | 88.89% | 96.30% |
| Citation structural validity | 88.89% | 100.00% |
| Expected-source citation match | 81.48% | 85.19% |
| Invalid citation rate | 0.00% | 0.00% |
| Missing citation rate | 11.11% | 0.00% |
| Correct machine abstention | 0.00% | 100.00% |
| Unsupported direct-answer rate | 100.00% | 0.00% |

## Latency means

| Stage | Before ms | After ms |
|---|---:|---:|
| retrieval_ms | 41.99 | 47.01 |
| context_ms | 18.42 | 17.24 |
| ttft_ms | 608.42 | 1080.36 |
| generation_ms | 3084.57 | 2137.26 |
| total_ms | 3401.81 | 2448.50 |

## Lexical strategy decision

Selected: strict `websearch_to_tsquery` first; when it has no matches, derive distinct lexemes through parameterized `to_tsvector('simple', :query_text)`, discard lexemes absent from the filtered corpus, select the four rarest, and construct a quoted conjunction. Raw user text is never concatenated into tsquery syntax.

Safe all-lexeme OR was rejected because it reduced Hit@1 from 85.19% to 62.96% and MRR from 88.89% to 76.85%, despite returning more candidates.

## Multi-evidence

```json
{
  "applicable_entities_multi": {
    "before": [
      {
        "chunk_id": "e9e217b3-268a-4fbf-9d4f-a33de58b1110",
        "dense_rank": null,
        "lexical_rank": null,
        "final_rank": null
      },
      {
        "chunk_id": "88d71393-ec3f-4bc1-be9d-72f50be0fd45",
        "dense_rank": null,
        "lexical_rank": null,
        "final_rank": null
      },
      {
        "chunk_id": "46ea4b72-f1e5-46c6-96d9-fbf317f9b9a8",
        "dense_rank": 5,
        "lexical_rank": null,
        "final_rank": 5
      }
    ],
    "after": [
      {
        "chunk_id": "e9e217b3-268a-4fbf-9d4f-a33de58b1110",
        "dense_rank": null,
        "lexical_rank": null,
        "final_rank": null
      },
      {
        "chunk_id": "88d71393-ec3f-4bc1-be9d-72f50be0fd45",
        "dense_rank": null,
        "lexical_rank": null,
        "final_rank": null
      },
      {
        "chunk_id": "46ea4b72-f1e5-46c6-96d9-fbf317f9b9a8",
        "dense_rank": 5,
        "lexical_rank": null,
        "final_rank": 5
      }
    ]
  },
  "national_dispatcher_role": {
    "before": [
      {
        "chunk_id": "123a2580-3ab8-42d6-aa50-c796fc691baa",
        "dense_rank": 1,
        "lexical_rank": null,
        "final_rank": 1
      },
      {
        "chunk_id": "14dcae3b-7755-440d-bb08-f0ea08c3563c",
        "dense_rank": 13,
        "lexical_rank": null,
        "final_rank": null
      }
    ],
    "after": [
      {
        "chunk_id": "123a2580-3ab8-42d6-aa50-c796fc691baa",
        "dense_rank": 1,
        "lexical_rank": null,
        "final_rank": 1
      },
      {
        "chunk_id": "14dcae3b-7755-440d-bb08-f0ea08c3563c",
        "dense_rank": 13,
        "lexical_rank": null,
        "final_rank": null
      }
    ]
  }
}
```

## Citation stability

Both historical cases produced valid `[S1]` citations in all three real runs (6/6 total).

## Known limitations and regressions

- One answerable case (ministry_approves_list) now safely abstains because the selected action chunk omits the responsible authority and the separate Điều 9 heading chunk is absent from final context.
- Both multi-evidence failures remain unchanged; Top-K and reranking were intentionally not modified.
- The wrong-source case remains PLAUSIBLE_ALTERNATIVE_EVIDENCE pending human legal review.
- The evaluation corpus contains one substantive legal document, so generalization remains unmeasured.

No regression is hidden and no threshold was tuned.
