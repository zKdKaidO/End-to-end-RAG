# Block 2 - Phase 5: Legal Metadata Extraction

## 1. What was implemented
- Created `tests/fixtures/sample_legal_expected.json` as an independent expected golden truth fixture for evaluating metadata parsing on `sample_legal.pdf`.
- Created `app/processing/metadata_extractor.py` containing `MetadataExtractor`.
- Implemented deterministic regex/heuristics to parse:
  - `document_type` (e.g. Nghị định, Luật)
  - `document_number` (e.g. 135/2026/NĐ-CP)
  - `issuing_authority` (e.g. Chính phủ)
  - `issued_date` (mapped to `YYYY-MM-DD` format)
  - `title` (extracted by grabbing text between document type and "Căn cứ")
- Wrote unit tests in `tests/unit/test_metadata_extractor.py` covering standard Vietnamese legal header structures.
- Confirmed that this metadata is temporarily held in memory (to be later serialized into `chunks.metadata_json`) and not persisted into a separate table, as instructed.

## 2. Commands Executed
```bash
docker compose exec api python -m pytest tests/unit/test_metadata_extractor.py -v
```

## 3. Actual Outputs
```text
tests/unit/test_metadata_extractor.py::test_metadata_extraction PASSED   [100%]
```

## 4. Failures Encountered & Fixes Applied
- None. The deterministic extraction works accurately on correctly cleaned header text.

## 5. Remaining Limitations
- It assumes a standard Vietnamese legal document preamble structure. Uncommon or poorly formatted documents might miss fields.

## 6. Definition of Done Check
- [x] Extract standard metadata.
- [x] No LLMs used.
- [x] Output structure is dictionary (to be JSON later).
- [x] Expected fixture created.
