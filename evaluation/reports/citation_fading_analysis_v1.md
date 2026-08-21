# Citation Fading Analysis V1

The citation parser and validator were unchanged. Prior variants improved targeted answerability but sometimes displaced or weakened exact citation adherence. Controlled results:

```json
{
  "previous_variant_full_answerable": {
    "variant-a": {
      "citation_validity_rate": 0.7454545454545455,
      "expected_source_match_rate": 0.7454545454545455,
      "status_valid_rate": 1.0
    },
    "variant-b": {
      "citation_validity_rate": 0.7272727272727273,
      "expected_source_match_rate": 0.6909090909090909,
      "status_valid_rate": 1.0
    },
    "fewshot": {
      "citation_validity_rate": 0.12727272727272726,
      "expected_source_match_rate": 0.12727272727272726,
      "status_valid_rate": 1.0
    },
    "combined": {
      "citation_validity_rate": 0.8727272727272727,
      "expected_source_match_rate": 0.8545454545454545,
      "status_valid_rate": 0.9818181818181818
    }
  },
  "current_cross_matrix": {
    "legal-rag-v2|P0": {
      "citation_validity_rate": 0.25,
      "expected_source_match_rate": 0.25,
      "missing_citation_rate": 0.0
    },
    "legal-rag-v2|P1": {
      "citation_validity_rate": 0.5,
      "expected_source_match_rate": 0.5,
      "missing_citation_rate": 0.0
    },
    "compact|P0": {
      "citation_validity_rate": 0.75,
      "expected_source_match_rate": 0.75,
      "missing_citation_rate": 0.0
    },
    "compact|P1": {
      "citation_validity_rate": 0.75,
      "expected_source_match_rate": 0.75,
      "missing_citation_rate": 0.0
    },
    "compact-fewshot|P1": {
      "citation_validity_rate": 0.75,
      "expected_source_match_rate": 0.75,
      "missing_citation_rate": 0.0
    }
  },
  "citation_parser_changed": false
}
```

The compact prompts place the exact citation rule adjacent to the ANSWERABLE rule and explicitly forbid duplicate status markers. A candidate is rejected if status or citation stability regresses on the full answerable corpus, regardless of targeted answer-rate improvement.
