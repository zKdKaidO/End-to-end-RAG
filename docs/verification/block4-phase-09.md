# Block 4 Phase 09 — Canonical hybrid retrieval E2E

Status: PASS

Canonical document: `sample_legal.pdf`, document ID `89eebb70-2020-45c0-a6f0-44d292f4a49b`.

## Semantic-style query

Query: `Đơn vị vận hành thị trường điện được hỗ trợ như thế nào để thu hút nhân sự giỏi?`

Dense Top-10 IDs:

1. `b9237b2e-31c5-47ac-8fe7-57595be42fdf`
2. `6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1`
3. `8b3f9a09-d190-4c38-8b2f-c5e3cc689f2f`
4. `3f7bfb6a-9d4c-4115-9fbd-c9b0a452f30b`
5. `e3e6bd37-81aa-470c-bbc1-4e596ce51b81`
6. `525ff655-b131-4375-8ead-0740eaa65957`
7. `3a16c7b5-6d12-4d34-b432-ef5078eee0c9`
8. `123a2580-3ab8-42d6-aa50-c796fc691baa`
9. `5a5aeeb5-ce90-41de-837c-332bd208f897`
10. `ccc02a68-e8d3-442c-9dca-fa2d4de42bbf`

Lexical Top-10: empty. Overlap: empty. Dense-only RRF remained valid.

Final Top-5 IDs and evidence previews:

1. `b9237b2e-31c5-47ac-8fe7-57595be42fdf` — policy to attract high-quality human resources; page 1.
2. `6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1` — incentives, additional income, benefits, and supplementary retirement insurance; page 2.
3. `8b3f9a09-d190-4c38-8b2f-c5e3cc689f2f` — priority for grants, sponsorship, and donations; page 4.
4. `3f7bfb6a-9d4c-4115-9fbd-c9b0a452f30b` — worker rights, safety, and information security; page 3.
5. `e3e6bd37-81aa-470c-bbc1-4e596ce51b81` — supplementary retirement insurance; page 6.

## Keyword-heavy query

Query: `bảo hiểm hưu trí bổ sung người lao động`

Dense Top-10 IDs:

`e3e6bd37-81aa-470c-bbc1-4e596ce51b81`, `6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1`, `5a5aeeb5-ce90-41de-837c-332bd208f897`, `c45e3d45-7183-42c5-8d65-9917878e1f6d`, `b487af78-9ec4-4f2e-98cb-0a2bbd0a332a`, `1bcf57c2-823e-448d-b228-638094100edb`, `525ff655-b131-4375-8ead-0740eaa65957`, `46ea4b72-f1e5-46c6-96d9-fbf317f9b9a8`, `db8ea6e4-5401-4fd9-b867-28faf56d3328`, `ec777336-15be-4698-8a21-6b6ba94cfaba`.

Lexical IDs: `6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1`, `e3e6bd37-81aa-470c-bbc1-4e596ce51b81`, `5a5aeeb5-ce90-41de-837c-332bd208f897`.

Overlap: all three lexical IDs.

RRF final order:

1. `6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1` — dense rank 2, lexical rank 1, page 2.
2. `e3e6bd37-81aa-470c-bbc1-4e596ce51b81` — dense rank 1, lexical rank 2, page 6.
3. `5a5aeeb5-ce90-41de-837c-332bd208f897` — dense rank 3, lexical rank 3, page 3.
4. `c45e3d45-7183-42c5-8d65-9917878e1f6d` — dense rank 4, lexical rank null, page 7.
5. `b487af78-9ec4-4f2e-98cb-0a2bbd0a332a` — dense rank 5, lexical rank null, page 5.

Every final item retained metadata for Nghị định `135/2026/NĐ-CP`, issuing authority `Chính phủ`, issued date `2026-04-07`, and provenance containing the canonical document ID plus page range. No answer was generated.
