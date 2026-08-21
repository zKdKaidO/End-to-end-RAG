# Legal RAG Evaluation V1 — Baseline Measurement

> This is a measured baseline. Recommended thresholds are not enforced.

## Dataset

- Cases: 32 (27 answerable, 5 unanswerable)
- Categories: {'DEEPER_RANK': 5, 'DIRECT_FACT': 6, 'DOCUMENT_FILTER': 3, 'KEYWORD_IDENTIFIER': 5, 'MULTI_EVIDENCE': 2, 'OUT_OF_CORPUS': 3, 'SEMANTIC_PARAPHRASE': 6, 'UNANSWERABLE': 2}
- Dataset validation: PASS

## Measured results

- Retrieval Hit@1 / @3 / @5 / @10: 85.19% / 92.59% / 92.59% / 92.59%
- Retrieval MRR: 0.8889
- Context expected-evidence retention: 100.00%
- Citation presence: 96.30%
- Citation structural validity: 100.00%
- Expected-source citation match: 85.19%
- Invalid / missing citation rate: 0.00% / 0.00%
- Correct abstention / unsupported answer rate: 100.00% / 0.00%
- Failure counts: {'GENERATION_WRONG_SOURCE': 1, 'INSUFFICIENT_EVIDENCE_FALSE_NEGATIVE': 1, 'PASS': 28, 'RETRIEVAL_MISS': 2}

## Latency

| Stage | Mean ms | P50 ms | P95 ms | N |
|---|---:|---:|---:|---:|
| retrieval_ms | 47.01 | 45.69 | 63.12 | 32 |
| context_ms | 17.24 | 17.62 | 22.05 | 32 |
| ttft_ms | 1080.36 | 1172.92 | 1342.33 | 32 |
| generation_ms | 2137.26 | 1929.54 | 3509.71 | 32 |
| total_ms | 2448.50 | 1997.62 | 6532.31 | 32 |

## Recommended gate thresholds

These are recommendations only and are **not enforced**. The first recommendation is a no-regression gate against this measured baseline; independent production-readiness thresholds require human review and a broader corpus.

```json
{
  "status": "PROVISIONAL_RECOMMENDATIONS_ONLY_NOT_ENFORCED",
  "rationale": "Candidate review targets informed by the measured misses and legal-risk profile; they are not pass/fail criteria until explicitly approved on a broader human-reviewed dataset.",
  "retrieval_hit_at_10_min": 0.9,
  "retrieval_mrr_min": 0.85,
  "context_retention_min": 1.0,
  "citation_structural_validity_min": 0.95,
  "expected_source_match_min": 0.9,
  "unsupported_answer_rate_max": 0.1,
  "invalid_citation_rate_max": 0.0,
  "missing_citation_rate_max": 0.05
}
```

## Per-case reports

### scope_direct — DIRECT_FACT

- Question: Nghị định 135/2026/NĐ-CP điều chỉnh những nhóm cơ chế, chính sách nào?
- Answerable: True
- Expected evidence: [['60f5801d-7d95-40b4-b1e9-90dd1260dd90'], ['749da3f5-6394-476a-b99f-44400d7c115b', 'b9237b2e-31c5-47ac-8fe7-57595be42fdf']]
- Block 4 final chunks/ranks: [('9ab66b53-663f-4642-9190-d80a6f61997d', 1), ('60f5801d-7d95-40b4-b1e9-90dd1260dd90', 2), ('749da3f5-6394-476a-b99f-44400d7c115b', 3), ('993f9dc0-6cce-4b64-b941-0d9d74763147', 4), ('f2d1cb68-7796-4a19-a2e2-04e857740343', 5), ('9f5e20ba-61af-4f1d-9ee8-6aa8a3cab585', 6), ('1f40648f-42b1-4a17-8858-d3c3024ee510', 7), ('6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1', 8), ('b9237b2e-31c5-47ac-8fe7-57595be42fdf', 9), ('46ea4b72-f1e5-46c6-96d9-fbf317f9b9a8', 10)]
- Expected solution rank: 2
- Retrieval result: FOUND
- Block 5 selected: [('S1', '9ab66b53-663f-4642-9190-d80a6f61997d'), ('S2', '60f5801d-7d95-40b4-b1e9-90dd1260dd90'), ('S3', '749da3f5-6394-476a-b99f-44400d7c115b'), ('S4', '993f9dc0-6cce-4b64-b941-0d9d74763147'), ('S5', 'f2d1cb68-7796-4a19-a2e2-04e857740343'), ('S6', '9f5e20ba-61af-4f1d-9ee8-6aa8a3cab585'), ('S7', '1f40648f-42b1-4a17-8858-d3c3024ee510'), ('S8', '6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1'), ('S9', 'b9237b2e-31c5-47ac-8fe7-57595be42fdf'), ('S10', '46ea4b72-f1e5-46c6-96d9-fbf317f9b9a8')]
- Context tokens: 1304 / 4096; stop=NONE
- Expected evidence retained: True
- Block 6: COMPLETED; citation validation=PASS
- Answer preview: Nghị định 135/2026/NĐ-CP quy định về các cơ chế, chính sách theo quy định tại điểm g và điểm h khoản 1 Điều 64, điểm e và điểm g khoản 1 Điều 65 của Luật Điện lực số 61/2024/QH15, bao gồm: [S2]; cụ thể là cơ chế, chính sách ưu đãi để bảo đảm cơ sở hạ tầng và các hệ thống thiết yếu khác phục vụ hoạt động điều độ hệ thống điện quốc gia và điều hành thị trường điện [S3].
- Citations / expected-source match: ['60f5801d-7d95-40b4-b1e9-90dd1260dd90', '749da3f5-6394-476a-b99f-44400d7c115b'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 61.189173000002484, 'context_ms': 14.950458999919647, 'ttft_ms': 1342.3320689998945, 'generation_ms': 3355.523174999689, 'total_ms': 11150.319095000214}

### applicable_entities_multi — MULTI_EVIDENCE

- Question: Những đối tượng nào thuộc phạm vi áp dụng của Nghị định?
- Answerable: True
- Expected evidence: [['e9e217b3-268a-4fbf-9d4f-a33de58b1110', '88d71393-ec3f-4bc1-be9d-72f50be0fd45', '46ea4b72-f1e5-46c6-96d9-fbf317f9b9a8']]
- Block 4 final chunks/ranks: [('1bcf57c2-823e-448d-b228-638094100edb', 1), ('60f5801d-7d95-40b4-b1e9-90dd1260dd90', 2), ('0210460d-1df2-497b-8dfa-662c87bcd136', 3), ('a2938526-154c-46fa-812c-ca4be5e42fc5', 4), ('46ea4b72-f1e5-46c6-96d9-fbf317f9b9a8', 5), ('32b30c2b-9ac9-46f9-9c70-60e869d4c820', 6), ('6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1', 7), ('b5ffcc91-2a3c-4b9d-98ff-f57f4c1a53a4', 8), ('6c815bcf-52d2-44ca-a974-f7dd82d82eef', 9), ('14dcae3b-7755-440d-bb08-f0ea08c3563c', 10)]
- Expected solution rank: None
- Retrieval result: MISS
- Block 5 selected: [('S1', '1bcf57c2-823e-448d-b228-638094100edb'), ('S2', '60f5801d-7d95-40b4-b1e9-90dd1260dd90'), ('S3', '0210460d-1df2-497b-8dfa-662c87bcd136'), ('S4', 'a2938526-154c-46fa-812c-ca4be5e42fc5'), ('S5', '46ea4b72-f1e5-46c6-96d9-fbf317f9b9a8'), ('S6', '32b30c2b-9ac9-46f9-9c70-60e869d4c820'), ('S7', '6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1'), ('S8', 'b5ffcc91-2a3c-4b9d-98ff-f57f4c1a53a4'), ('S9', '6c815bcf-52d2-44ca-a974-f7dd82d82eef'), ('S10', '14dcae3b-7755-440d-bb08-f0ea08c3563c')]
- Context tokens: 1431 / 4096; stop=NONE
- Expected evidence retained: False
- Block 6: COMPLETED; citation validation=PASS
- Answer preview: Đơn vị điều độ hệ thống điện quốc gia và đơn vị điều hành giao dịch thị trường điện [S1].
- Citations / expected-source match: ['1bcf57c2-823e-448d-b228-638094100edb'] / False
- Failure attribution: RETRIEVAL_MISS
- Timings ms: {'retrieval_ms': 38.35767600003237, 'context_ms': 15.4522090001592, 'ttft_ms': 1150.011295999775, 'generation_ms': 1629.3277079998916, 'total_ms': 1688.7863450001532}

### nsmo_definition — SEMANTIC_PARAPHRASE

- Question: Doanh nghiệp nào hiện được xác định là đơn vị vận hành hệ thống điện và thị trường điện?
- Answerable: True
- Expected evidence: [['2851c158-aff0-44c1-9526-df907299d251']]
- Block 4 final chunks/ranks: [('2851c158-aff0-44c1-9526-df907299d251', 1), ('3f7bfb6a-9d4c-4115-9fbd-c9b0a452f30b', 2), ('f1a28b76-e9f0-4a8b-83f6-59374c0fc98d', 3), ('88d71393-ec3f-4bc1-be9d-72f50be0fd45', 4), ('e3e6bd37-81aa-470c-bbc1-4e596ce51b81', 5), ('ea21d5a1-92e7-4863-8619-5db9a4b0217f', 6), ('56a9f913-4fb8-4b95-b90f-4e7f04b9e945', 7), ('525ff655-b131-4375-8ead-0740eaa65957', 8), ('6c815bcf-52d2-44ca-a974-f7dd82d82eef', 9), ('aa94940b-7ed8-48e2-a634-5423a3aaef8e', 10)]
- Expected solution rank: 1
- Retrieval result: FOUND
- Block 5 selected: [('S1', '2851c158-aff0-44c1-9526-df907299d251'), ('S2', '3f7bfb6a-9d4c-4115-9fbd-c9b0a452f30b'), ('S3', 'f1a28b76-e9f0-4a8b-83f6-59374c0fc98d'), ('S4', '88d71393-ec3f-4bc1-be9d-72f50be0fd45'), ('S5', 'e3e6bd37-81aa-470c-bbc1-4e596ce51b81'), ('S6', 'ea21d5a1-92e7-4863-8619-5db9a4b0217f'), ('S7', '56a9f913-4fb8-4b95-b90f-4e7f04b9e945'), ('S8', '525ff655-b131-4375-8ead-0740eaa65957'), ('S9', '6c815bcf-52d2-44ca-a974-f7dd82d82eef'), ('S10', 'aa94940b-7ed8-48e2-a634-5423a3aaef8e')]
- Context tokens: 1400 / 4096; stop=NONE
- Expected evidence retained: True
- Block 6: COMPLETED; citation validation=PASS
- Answer preview: Doanh nghiệp hiện được xác định là đơn vị vận hành hệ thống điện và thị trường điện là Công ty trách nhiệm hữu hạn một thành viên Vận hành hệ thống điện và thị trường điện Quốc gia - NSMO [S1].
- Citations / expected-source match: ['2851c158-aff0-44c1-9526-df907299d251'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 45.00181599996722, 'context_ms': 15.456940000149189, 'ttft_ms': 661.1294599997564, 'generation_ms': 1504.941565000081, 'total_ms': 1572.8231650000453}

### national_dispatcher_role — MULTI_EVIDENCE

- Question: Điều độ viên quốc gia có được xem là người lao động trực tiếp làm công tác điều độ hệ thống điện quốc gia không?
- Answerable: True
- Expected evidence: [['123a2580-3ab8-42d6-aa50-c796fc691baa', '14dcae3b-7755-440d-bb08-f0ea08c3563c']]
- Block 4 final chunks/ranks: [('123a2580-3ab8-42d6-aa50-c796fc691baa', 1), ('5a5aeeb5-ce90-41de-837c-332bd208f897', 2), ('3f7bfb6a-9d4c-4115-9fbd-c9b0a452f30b', 3), ('32b30c2b-9ac9-46f9-9c70-60e869d4c820', 4), ('e9e217b3-268a-4fbf-9d4f-a33de58b1110', 5), ('e3e6bd37-81aa-470c-bbc1-4e596ce51b81', 6), ('6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1', 7), ('0210460d-1df2-497b-8dfa-662c87bcd136', 8), ('525ff655-b131-4375-8ead-0740eaa65957', 9), ('2851c158-aff0-44c1-9526-df907299d251', 10)]
- Expected solution rank: None
- Retrieval result: MISS
- Block 5 selected: [('S1', '123a2580-3ab8-42d6-aa50-c796fc691baa'), ('S2', '5a5aeeb5-ce90-41de-837c-332bd208f897'), ('S3', '3f7bfb6a-9d4c-4115-9fbd-c9b0a452f30b'), ('S4', '32b30c2b-9ac9-46f9-9c70-60e869d4c820'), ('S5', 'e9e217b3-268a-4fbf-9d4f-a33de58b1110'), ('S6', 'e3e6bd37-81aa-470c-bbc1-4e596ce51b81'), ('S7', '6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1'), ('S8', '0210460d-1df2-497b-8dfa-662c87bcd136'), ('S9', '525ff655-b131-4375-8ead-0740eaa65957'), ('S10', '2851c158-aff0-44c1-9526-df907299d251')]
- Context tokens: 1741 / 4096; stop=NONE
- Expected evidence retained: False
- Block 6: COMPLETED; citation validation=PASS
- Answer preview: Người lao động trực tiếp thực hiện công tác điều độ hệ thống điện quốc gia bao gồm các chức danh được quy định tại Nghị định số 135/2026/NĐ-CP [S1]. Tuy nhiên, bằng chứng cung cấp không liệt kê cụ thể chức danh "Điều độ viên quốc gia" vào danh sách này mà chỉ nêu chung là "người lao động trực tiếp thực hiện công tác điều độ hệ thống điện quốc gia" [S1], do đó không thể xác định từ bằng chứng có đư
- Citations / expected-source match: ['123a2580-3ab8-42d6-aa50-c796fc691baa'] / False
- Failure attribution: RETRIEVAL_MISS
- Timings ms: {'retrieval_ms': 46.749792999889905, 'context_ms': 17.830394000156957, 'ttft_ms': 1214.3052430001262, 'generation_ms': 3331.434062000426, 'total_ms': 3402.1460949998072}

### modernization_principle — SEMANTIC_PARAPHRASE

- Question: Nguyên tắc về hiện đại hóa hạ tầng và ứng dụng công nghệ trong công tác điều độ được quy định ra sao?
- Answerable: True
- Expected evidence: [['b345594b-9fd4-4d24-97ad-257b0f5df2b0']]
- Block 4 final chunks/ranks: [('b345594b-9fd4-4d24-97ad-257b0f5df2b0', 1), ('bc958182-732b-4fa9-a5c0-79dc75282032', 2), ('ccc02a68-e8d3-442c-9dca-fa2d4de42bbf', 3), ('fd3f2bd6-3f66-4167-8efb-542078559d9b', 4), ('56a9f913-4fb8-4b95-b90f-4e7f04b9e945', 5), ('749da3f5-6394-476a-b99f-44400d7c115b', 6), ('3bed5a7c-a0a1-43e5-b6ed-3ec6a67611cf', 7), ('dd8abf92-4c4a-473c-8e6d-3fa8625da484', 8), ('b9237b2e-31c5-47ac-8fe7-57595be42fdf', 9), ('6c815bcf-52d2-44ca-a974-f7dd82d82eef', 10)]
- Expected solution rank: 1
- Retrieval result: FOUND
- Block 5 selected: [('S1', 'b345594b-9fd4-4d24-97ad-257b0f5df2b0'), ('S2', 'bc958182-732b-4fa9-a5c0-79dc75282032'), ('S3', 'ccc02a68-e8d3-442c-9dca-fa2d4de42bbf'), ('S4', 'fd3f2bd6-3f66-4167-8efb-542078559d9b'), ('S5', '56a9f913-4fb8-4b95-b90f-4e7f04b9e945'), ('S6', '749da3f5-6394-476a-b99f-44400d7c115b'), ('S7', '3bed5a7c-a0a1-43e5-b6ed-3ec6a67611cf'), ('S8', 'dd8abf92-4c4a-473c-8e6d-3fa8625da484'), ('S9', 'b9237b2e-31c5-47ac-8fe7-57595be42fdf'), ('S10', '6c815bcf-52d2-44ca-a974-f7dd82d82eef')]
- Context tokens: 1068 / 4096; stop=NONE
- Expected evidence retained: True
- Block 6: COMPLETED; citation validation=PASS
- Answer preview: Nguyên tắc về hiện đại hóa hạ tầng và ứng dụng công nghệ trong công tác điều độ được quy định là ưu tiên đầu tư đồng bộ, hiện đại hóa hạ tầng kỹ thuật; đẩy mạnh ứng dụng công nghệ số và tự động hóa trong công tác điều độ, vận hành hệ thống điện và công tác điều hành giao dịch thị trường điện [S1].
- Citations / expected-source match: ['b345594b-9fd4-4d24-97ad-257b0f5df2b0'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 73.81577599971934, 'context_ms': 19.369769000149972, 'ttft_ms': 1077.7716769998733, 'generation_ms': 2432.002332999673, 'total_ms': 2531.0572200000934}

### human_resource_benefits — DIRECT_FACT

- Question: Đơn vị vận hành được chi trả những khoản gì cho người lao động trực tiếp theo nguyên tắc tại Điều 4?
- Answerable: True
- Expected evidence: [['6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1']]
- Block 4 final chunks/ranks: [('6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1', 1), ('e3e6bd37-81aa-470c-bbc1-4e596ce51b81', 2), ('32b30c2b-9ac9-46f9-9c70-60e869d4c820', 3), ('525ff655-b131-4375-8ead-0740eaa65957', 4), ('3f7bfb6a-9d4c-4115-9fbd-c9b0a452f30b', 5), ('5a5aeeb5-ce90-41de-837c-332bd208f897', 6), ('123a2580-3ab8-42d6-aa50-c796fc691baa', 7), ('8b3f9a09-d190-4c38-8b2f-c5e3cc689f2f', 8), ('3a16c7b5-6d12-4d34-b432-ef5078eee0c9', 9), ('46ea4b72-f1e5-46c6-96d9-fbf317f9b9a8', 10)]
- Expected solution rank: 1
- Retrieval result: FOUND
- Block 5 selected: [('S1', '6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1'), ('S2', 'e3e6bd37-81aa-470c-bbc1-4e596ce51b81'), ('S3', '32b30c2b-9ac9-46f9-9c70-60e869d4c820'), ('S4', '525ff655-b131-4375-8ead-0740eaa65957'), ('S5', '3f7bfb6a-9d4c-4115-9fbd-c9b0a452f30b'), ('S6', '5a5aeeb5-ce90-41de-837c-332bd208f897'), ('S7', '123a2580-3ab8-42d6-aa50-c796fc691baa'), ('S8', '8b3f9a09-d190-4c38-8b2f-c5e3cc689f2f'), ('S9', '3a16c7b5-6d12-4d34-b432-ef5078eee0c9'), ('S10', '46ea4b72-f1e5-46c6-96d9-fbf317f9b9a8')]
- Context tokens: 1620 / 4096; stop=NONE
- Expected evidence retained: True
- Block 6: COMPLETED; citation validation=PASS
- Answer preview: Đơn vị vận hành được chi trả các khoản thu nhập tăng thêm, phúc lợi và bảo hiểm hưu trí bổ sung cho người lao động trực tiếp thực hiện công tác điều độ hệ thống điện quốc gia và điều hành giao dịch thị trường điện [S1]. Đơn vị vận hành cũng được chi thu nhập tăng thêm (theo tỷ lệ 30% mức lương theo hệ số hiện hưởng) do doanh nghiệp xây dựng (không bao gồm phụ cấp) cho người lao động trực tiếp thực
- Citations / expected-source match: ['6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1', '525ff655-b131-4375-8ead-0740eaa65957'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 52.42359199974089, 'context_ms': 19.026647999908164, 'ttft_ms': 1186.7978659997789, 'generation_ms': 3320.8262690000083, 'total_ms': 3398.1374060003873}

### worker_rights_security — SEMANTIC_PARAPHRASE

- Question: Đơn vị vận hành phải bảo đảm những quyền lợi và điều kiện nào cho người lao động trực tiếp?
- Answerable: True
- Expected evidence: [['3f7bfb6a-9d4c-4115-9fbd-c9b0a452f30b']]
- Block 4 final chunks/ranks: [('3f7bfb6a-9d4c-4115-9fbd-c9b0a452f30b', 1), ('6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1', 2), ('123a2580-3ab8-42d6-aa50-c796fc691baa', 3), ('e3e6bd37-81aa-470c-bbc1-4e596ce51b81', 4), ('32b30c2b-9ac9-46f9-9c70-60e869d4c820', 5), ('525ff655-b131-4375-8ead-0740eaa65957', 6), ('0210460d-1df2-497b-8dfa-662c87bcd136', 7), ('c45e3d45-7183-42c5-8d65-9917878e1f6d', 8), ('5a5aeeb5-ce90-41de-837c-332bd208f897', 9), ('db8ea6e4-5401-4fd9-b867-28faf56d3328', 10)]
- Expected solution rank: 1
- Retrieval result: FOUND
- Block 5 selected: [('S1', '3f7bfb6a-9d4c-4115-9fbd-c9b0a452f30b'), ('S2', '6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1'), ('S3', '123a2580-3ab8-42d6-aa50-c796fc691baa'), ('S4', 'e3e6bd37-81aa-470c-bbc1-4e596ce51b81'), ('S5', '32b30c2b-9ac9-46f9-9c70-60e869d4c820'), ('S6', '525ff655-b131-4375-8ead-0740eaa65957'), ('S7', '0210460d-1df2-497b-8dfa-662c87bcd136'), ('S8', 'c45e3d45-7183-42c5-8d65-9917878e1f6d'), ('S9', '5a5aeeb5-ce90-41de-837c-332bd208f897'), ('S10', 'db8ea6e4-5401-4fd9-b867-28faf56d3328')]
- Context tokens: 1708 / 4096; stop=NONE
- Expected evidence retained: True
- Block 6: COMPLETED; citation validation=PASS
- Answer preview: Đơn vị vận hành phải bảo đảm quyền lợi và điều kiện sau cho người lao động trực tiếp thực hiện công tác điều độ hệ thống điện quốc gia và điều hành giao dịch thị trường điện:
- Bảo đảm quyền, lợi ích hợp pháp [S1].
- Điều kiện làm việc an toàn [S1].
- An ninh thông tin [S1].
- Được chi trả các khoản thu nhập tăng thêm [S2].
- Phúc lợi [S2].
- Bảo hiểm hưu trí bổ sung [S2].
- Chế độ bảo hiểm hưu tr
- Citations / expected-source match: ['3f7bfb6a-9d4c-4115-9fbd-c9b0a452f30b', '6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1', 'e3e6bd37-81aa-470c-bbc1-4e596ce51b81'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 44.43905000016457, 'context_ms': 18.6562750000121, 'ttft_ms': 1248.8866250000683, 'generation_ms': 3509.7091980001096, 'total_ms': 3577.4803910003357}

### benefit_cost_accounting — DEEPER_RANK

- Question: Chi phí thuê chuyên gia, thu nhập tăng thêm và bảo hiểm hưu trí bổ sung được hạch toán và thu hồi như thế nào?
- Answerable: True
- Expected evidence: [['5a5aeeb5-ce90-41de-837c-332bd208f897']]
- Block 4 final chunks/ranks: [('5a5aeeb5-ce90-41de-837c-332bd208f897', 1), ('e3e6bd37-81aa-470c-bbc1-4e596ce51b81', 2), ('6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1', 3), ('76cce61d-99aa-4e26-8cf9-74ed41353463', 4), ('525ff655-b131-4375-8ead-0740eaa65957', 5), ('db8ea6e4-5401-4fd9-b867-28faf56d3328', 6), ('abdf4475-fa62-47bd-83a7-36aec6df506a', 7), ('9f5e20ba-61af-4f1d-9ee8-6aa8a3cab585', 8), ('3a16c7b5-6d12-4d34-b432-ef5078eee0c9', 9), ('9667c02d-ef15-4ac9-8ce7-1e41fa0122e4', 10)]
- Expected solution rank: 1
- Retrieval result: FOUND
- Block 5 selected: [('S1', '5a5aeeb5-ce90-41de-837c-332bd208f897'), ('S2', 'e3e6bd37-81aa-470c-bbc1-4e596ce51b81'), ('S3', '6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1'), ('S4', '76cce61d-99aa-4e26-8cf9-74ed41353463'), ('S5', '525ff655-b131-4375-8ead-0740eaa65957'), ('S6', 'db8ea6e4-5401-4fd9-b867-28faf56d3328'), ('S7', 'abdf4475-fa62-47bd-83a7-36aec6df506a'), ('S8', '9f5e20ba-61af-4f1d-9ee8-6aa8a3cab585'), ('S9', '3a16c7b5-6d12-4d34-b432-ef5078eee0c9'), ('S10', '9667c02d-ef15-4ac9-8ce7-1e41fa0122e4')]
- Context tokens: 1526 / 4096; stop=NONE
- Expected evidence retained: True
- Block 6: COMPLETED; citation validation=PASS
- Answer preview: Chi phí thuê chuyên gia tư vấn, thu nhập tăng thêm và bảo hiểm hưu trí bổ sung được hạch toán vào chi phí, giá thành kinh doanh của Đơn vị vận hành hệ thống điện và thị trường điện và được tính để thu hồi trong giá dịch vụ điều độ vận hành hệ thống điện và giá dịch vụ điều hành giao dịch thị trường điện lực hằng năm [S1].

Cụ thể:
- Thu nhập tăng thêm được chi trả cho người lao động trực tiếp thực
- Citations / expected-source match: ['5a5aeeb5-ce90-41de-837c-332bd208f897', '525ff655-b131-4375-8ead-0740eaa65957', '3a16c7b5-6d12-4d34-b432-ef5078eee0c9', 'e3e6bd37-81aa-470c-bbc1-4e596ce51b81'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 47.83950500041101, 'context_ms': 17.417403999843373, 'ttft_ms': 1219.9051920001693, 'generation_ms': 6462.551734000044, 'total_ms': 6532.311272999777}

### headquarters_infrastructure_filter — DOCUMENT_FILTER

- Question: Trụ sở của đơn vị vận hành bao gồm những trung tâm điều khiển nào?
- Answerable: True
- Expected evidence: [['ea21d5a1-92e7-4863-8619-5db9a4b0217f']]
- Block 4 final chunks/ranks: [('ea21d5a1-92e7-4863-8619-5db9a4b0217f', 1), ('5296ee36-1e31-42ef-a152-7850d13f15ba', 2), ('e9e217b3-268a-4fbf-9d4f-a33de58b1110', 3), ('56a9f913-4fb8-4b95-b90f-4e7f04b9e945', 4), ('0210460d-1df2-497b-8dfa-662c87bcd136', 5), ('ccc02a68-e8d3-442c-9dca-fa2d4de42bbf', 6), ('fd3f2bd6-3f66-4167-8efb-542078559d9b', 7), ('6c815bcf-52d2-44ca-a974-f7dd82d82eef', 8), ('f688f717-2d7c-465e-905f-338fa064168b', 9), ('dd8abf92-4c4a-473c-8e6d-3fa8625da484', 10)]
- Expected solution rank: 1
- Retrieval result: FOUND
- Block 5 selected: [('S1', 'ea21d5a1-92e7-4863-8619-5db9a4b0217f'), ('S2', '5296ee36-1e31-42ef-a152-7850d13f15ba'), ('S3', 'e9e217b3-268a-4fbf-9d4f-a33de58b1110'), ('S4', '56a9f913-4fb8-4b95-b90f-4e7f04b9e945'), ('S5', '0210460d-1df2-497b-8dfa-662c87bcd136'), ('S6', 'ccc02a68-e8d3-442c-9dca-fa2d4de42bbf'), ('S7', 'fd3f2bd6-3f66-4167-8efb-542078559d9b'), ('S8', '6c815bcf-52d2-44ca-a974-f7dd82d82eef'), ('S9', 'f688f717-2d7c-465e-905f-338fa064168b'), ('S10', 'dd8abf92-4c4a-473c-8e6d-3fa8625da484')]
- Context tokens: 1414 / 4096; stop=NONE
- Expected evidence retained: True
- Block 6: COMPLETED; citation validation=PASS
- Answer preview: Trụ sở của đơn vị vận hành bao gồm Trung tâm điều khiển chính và Trung tâm điều khiển dự phòng độc lập về vị trí [S1], [S2].
- Citations / expected-source match: ['ea21d5a1-92e7-4863-8619-5db9a4b0217f', '5296ee36-1e31-42ef-a152-7850d13f15ba'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 42.07055299957574, 'context_ms': 18.023801000254025, 'ttft_ms': 1212.5584209998124, 'generation_ms': 1909.2802669997582, 'total_ms': 1974.7495920000802}

### cybersecurity_infrastructure — KEYWORD_IDENTIFIER

- Question: Cơ sở hạ tầng công nghệ thông tin và an ninh mạng được xếp vào danh mục nào tại Điều 5?
- Answerable: True
- Expected evidence: [['3bed5a7c-a0a1-43e5-b6ed-3ec6a67611cf']]
- Block 4 final chunks/ranks: [('3bed5a7c-a0a1-43e5-b6ed-3ec6a67611cf', 1), ('bc958182-732b-4fa9-a5c0-79dc75282032', 2), ('56a9f913-4fb8-4b95-b90f-4e7f04b9e945', 3), ('39a22902-005b-4733-abb2-b9524ddcb829', 4), ('6c815bcf-52d2-44ca-a974-f7dd82d82eef', 5), ('fd3f2bd6-3f66-4167-8efb-542078559d9b', 6), ('dd8abf92-4c4a-473c-8e6d-3fa8625da484', 7), ('7ef3b873-84ef-414f-9615-b341cb94f1cc', 8), ('ccc02a68-e8d3-442c-9dca-fa2d4de42bbf', 9), ('749da3f5-6394-476a-b99f-44400d7c115b', 10)]
- Expected solution rank: 1
- Retrieval result: FOUND
- Block 5 selected: [('S1', '3bed5a7c-a0a1-43e5-b6ed-3ec6a67611cf'), ('S2', 'bc958182-732b-4fa9-a5c0-79dc75282032'), ('S3', '56a9f913-4fb8-4b95-b90f-4e7f04b9e945'), ('S4', '39a22902-005b-4733-abb2-b9524ddcb829'), ('S5', '6c815bcf-52d2-44ca-a974-f7dd82d82eef'), ('S6', 'fd3f2bd6-3f66-4167-8efb-542078559d9b'), ('S7', 'dd8abf92-4c4a-473c-8e6d-3fa8625da484'), ('S8', '7ef3b873-84ef-414f-9615-b341cb94f1cc'), ('S9', 'ccc02a68-e8d3-442c-9dca-fa2d4de42bbf'), ('S10', '749da3f5-6394-476a-b99f-44400d7c115b')]
- Context tokens: 992 / 4096; stop=NONE
- Expected evidence retained: True
- Block 6: COMPLETED; citation validation=PASS
- Answer preview: Cơ sở hạ tầng công nghệ thông tin và an ninh mạng được xếp vào danh mục "Cơ sở hạ tầng công nghệ thông tin, an ninh mạng chuyên ngành trọng yếu" tại Điều 5 [S1].
- Citations / expected-source match: ['3bed5a7c-a0a1-43e5-b6ed-3ec6a67611cf'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 46.535585000128776, 'context_ms': 11.31775000021662, 'ttft_ms': 1026.6541300002245, 'generation_ms': 1814.293438000277, 'total_ms': 1876.9516759998623}

### oda_project_priority — DIRECT_FACT

- Question: Đơn vị vận hành có được ưu tiên tham gia dự án đầu tư sử dụng vốn ODA không?
- Answerable: True
- Expected evidence: [['b5ffcc91-2a3c-4b9d-98ff-f57f4c1a53a4']]
- Block 4 final chunks/ranks: [('b5ffcc91-2a3c-4b9d-98ff-f57f4c1a53a4', 1), ('1a6b7744-8a26-4f62-8eca-207bdd065151', 2), ('bfae2ca5-6855-4583-83db-841870e5a379', 3), ('aa94940b-7ed8-48e2-a634-5423a3aaef8e', 4), ('76cce61d-99aa-4e26-8cf9-74ed41353463', 5), ('7da489f6-8090-4d00-8ed7-86fccb2c7fde', 6), ('7ef3b873-84ef-414f-9615-b341cb94f1cc', 7), ('ccc02a68-e8d3-442c-9dca-fa2d4de42bbf', 8), ('8b3f9a09-d190-4c38-8b2f-c5e3cc689f2f', 9), ('abdf4475-fa62-47bd-83a7-36aec6df506a', 10)]
- Expected solution rank: 1
- Retrieval result: FOUND
- Block 5 selected: [('S1', 'b5ffcc91-2a3c-4b9d-98ff-f57f4c1a53a4'), ('S2', '1a6b7744-8a26-4f62-8eca-207bdd065151'), ('S3', 'bfae2ca5-6855-4583-83db-841870e5a379'), ('S4', 'aa94940b-7ed8-48e2-a634-5423a3aaef8e'), ('S5', '76cce61d-99aa-4e26-8cf9-74ed41353463'), ('S6', '7da489f6-8090-4d00-8ed7-86fccb2c7fde'), ('S7', '7ef3b873-84ef-414f-9615-b341cb94f1cc'), ('S8', 'ccc02a68-e8d3-442c-9dca-fa2d4de42bbf'), ('S9', '8b3f9a09-d190-4c38-8b2f-c5e3cc689f2f'), ('S10', 'abdf4475-fa62-47bd-83a7-36aec6df506a')]
- Context tokens: 1548 / 4096; stop=NONE
- Expected evidence retained: True
- Block 6: COMPLETED; citation validation=PASS
- Answer preview: Đơn vị vận hành hệ thống điện và thị trường điện được ưu tiên đề xuất, tham gia và thực hiện các dự án đầu tư sử dụng vốn hỗ trợ phát triển chính thức (ODA) [S1]. Đơn vị này cũng được ưu tiên tiếp cận, sử dụng vốn ODA để thực hiện các dự án được cơ quan nhà nước có thẩm quyền phê duyệt [S2].
- Citations / expected-source match: ['b5ffcc91-2a3c-4b9d-98ff-f57f4c1a53a4', '1a6b7744-8a26-4f62-8eca-207bdd065151'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 45.28350700002193, 'context_ms': 18.5845139999401, 'ttft_ms': 1166.6501280001285, 'generation_ms': 2456.5284830000564, 'total_ms': 2526.2633380002626}

### land_lease_no_auction — SEMANTIC_PARAPHRASE

- Question: Cơ quan có thẩm quyền có thể cho đơn vị vận hành thuê đất mà không đấu giá quyền sử dụng đất hay không?
- Answerable: True
- Expected evidence: [['f1a28b76-e9f0-4a8b-83f6-59374c0fc98d']]
- Block 4 final chunks/ranks: [('f1a28b76-e9f0-4a8b-83f6-59374c0fc98d', 1), ('5296ee36-1e31-42ef-a152-7850d13f15ba', 2), ('aa94940b-7ed8-48e2-a634-5423a3aaef8e', 3), ('bfae2ca5-6855-4583-83db-841870e5a379', 4), ('1a6b7744-8a26-4f62-8eca-207bdd065151', 5), ('3a16c7b5-6d12-4d34-b432-ef5078eee0c9', 6), ('d5c99d40-c7d1-4c2d-8990-45fccf92c3db', 7), ('ccc02a68-e8d3-442c-9dca-fa2d4de42bbf', 8), ('88d71393-ec3f-4bc1-be9d-72f50be0fd45', 9), ('d5227ce1-cff9-492b-b542-5022be73931d', 10)]
- Expected solution rank: 1
- Retrieval result: FOUND
- Block 5 selected: [('S1', 'f1a28b76-e9f0-4a8b-83f6-59374c0fc98d'), ('S2', '5296ee36-1e31-42ef-a152-7850d13f15ba'), ('S3', 'aa94940b-7ed8-48e2-a634-5423a3aaef8e'), ('S4', 'bfae2ca5-6855-4583-83db-841870e5a379'), ('S5', '1a6b7744-8a26-4f62-8eca-207bdd065151'), ('S6', '3a16c7b5-6d12-4d34-b432-ef5078eee0c9'), ('S7', 'd5c99d40-c7d1-4c2d-8990-45fccf92c3db'), ('S8', 'ccc02a68-e8d3-442c-9dca-fa2d4de42bbf'), ('S9', '88d71393-ec3f-4bc1-be9d-72f50be0fd45'), ('S10', 'd5227ce1-cff9-492b-b542-5022be73931d')]
- Context tokens: 1491 / 4096; stop=NONE
- Expected evidence retained: True
- Block 6: COMPLETED; citation validation=PASS
- Answer preview: Cơ quan có thẩm quyền xem xét cho đơn vị vận hành thuê đất không đấu giá quyền sử dụng đất để bảo đảm hoạt động ổn định, an toàn, lâu dài và an ninh cho công tác điều độ hệ thống điện quốc gia và điều hành giao dịch thị trường điện [S1].
- Citations / expected-source match: ['f1a28b76-e9f0-4a8b-83f6-59374c0fc98d'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 46.14467700002933, 'context_ms': 17.367671000101836, 'ttft_ms': 1179.194329999973, 'generation_ms': 2176.865766999981, 'total_ms': 2245.097438000357}

### oda_capital_source — KEYWORD_IDENTIFIER

- Question: Khoản 1 Điều 7 có coi vốn ODA và vốn vay ưu đãi nước ngoài là nguồn vốn đầu tư không?
- Answerable: True
- Expected evidence: [['7da489f6-8090-4d00-8ed7-86fccb2c7fde']]
- Block 4 final chunks/ranks: [('7da489f6-8090-4d00-8ed7-86fccb2c7fde', 1), ('abdf4475-fa62-47bd-83a7-36aec6df506a', 2), ('b5ffcc91-2a3c-4b9d-98ff-f57f4c1a53a4', 3), ('1a6b7744-8a26-4f62-8eca-207bdd065151', 4), ('7ef3b873-84ef-414f-9615-b341cb94f1cc', 5), ('aa911e85-ccd4-4799-adda-2f5d51155bb6', 6), ('00428e4c-508d-4c2f-98b6-e6b2617f98ee', 7), ('53a2dd91-1e8f-4071-a904-ff1f83cf76f1', 8), ('bfae2ca5-6855-4583-83db-841870e5a379', 9), ('76cce61d-99aa-4e26-8cf9-74ed41353463', 10)]
- Expected solution rank: 1
- Retrieval result: FOUND
- Block 5 selected: [('S1', '7da489f6-8090-4d00-8ed7-86fccb2c7fde'), ('S2', 'abdf4475-fa62-47bd-83a7-36aec6df506a'), ('S3', 'b5ffcc91-2a3c-4b9d-98ff-f57f4c1a53a4'), ('S4', '1a6b7744-8a26-4f62-8eca-207bdd065151'), ('S5', '7ef3b873-84ef-414f-9615-b341cb94f1cc'), ('S6', 'aa911e85-ccd4-4799-adda-2f5d51155bb6'), ('S7', '00428e4c-508d-4c2f-98b6-e6b2617f98ee'), ('S8', '53a2dd91-1e8f-4071-a904-ff1f83cf76f1'), ('S9', 'bfae2ca5-6855-4583-83db-841870e5a379'), ('S10', '76cce61d-99aa-4e26-8cf9-74ed41353463')]
- Context tokens: 1243 / 4096; stop=NONE
- Expected evidence retained: True
- Block 6: COMPLETED; citation validation=PASS
- Answer preview: Khoản 1 Điều 7 coi vốn ODA, vốn vay ưu đãi nước ngoài là nguồn vốn đầu tư [S3].
- Citations / expected-source match: ['b5ffcc91-2a3c-4b9d-98ff-f57f4c1a53a4'] / False
- Failure attribution: GENERATION_WRONG_SOURCE
- Timings ms: {'retrieval_ms': 42.12528000016391, 'context_ms': 12.070957000105409, 'ttft_ms': 623.5326279997935, 'generation_ms': 1171.1147819996768, 'total_ms': 1229.648496000209}

### non_oda_grants — DEEPER_RANK

- Question: Đơn vị vận hành được tiếp nhận các khoản viện trợ không hoàn lại ngoài ODA dưới những hình thức nào?
- Answerable: True
- Expected evidence: [['8b3f9a09-d190-4c38-8b2f-c5e3cc689f2f']]
- Block 4 final chunks/ranks: [('8b3f9a09-d190-4c38-8b2f-c5e3cc689f2f', 1), ('b5ffcc91-2a3c-4b9d-98ff-f57f4c1a53a4', 2), ('7da489f6-8090-4d00-8ed7-86fccb2c7fde', 3), ('1a6b7744-8a26-4f62-8eca-207bdd065151', 4), ('bfae2ca5-6855-4583-83db-841870e5a379', 5), ('76cce61d-99aa-4e26-8cf9-74ed41353463', 6), ('d5c99d40-c7d1-4c2d-8990-45fccf92c3db', 7), ('aa911e85-ccd4-4799-adda-2f5d51155bb6', 8), ('46ea4b72-f1e5-46c6-96d9-fbf317f9b9a8', 9), ('1bcf57c2-823e-448d-b228-638094100edb', 10)]
- Expected solution rank: 1
- Retrieval result: FOUND
- Block 5 selected: [('S1', '8b3f9a09-d190-4c38-8b2f-c5e3cc689f2f'), ('S2', 'b5ffcc91-2a3c-4b9d-98ff-f57f4c1a53a4'), ('S3', '7da489f6-8090-4d00-8ed7-86fccb2c7fde'), ('S4', '1a6b7744-8a26-4f62-8eca-207bdd065151'), ('S5', 'bfae2ca5-6855-4583-83db-841870e5a379'), ('S6', '76cce61d-99aa-4e26-8cf9-74ed41353463'), ('S7', 'd5c99d40-c7d1-4c2d-8990-45fccf92c3db'), ('S8', 'aa911e85-ccd4-4799-adda-2f5d51155bb6'), ('S9', '46ea4b72-f1e5-46c6-96d9-fbf317f9b9a8'), ('S10', '1bcf57c2-823e-448d-b228-638094100edb')]
- Context tokens: 1560 / 4096; stop=NONE
- Expected evidence retained: True
- Block 6: COMPLETED; citation validation=PASS
- Answer preview: Đơn vị vận hành được tiếp nhận các khoản viện trợ không hoàn lại ngoài ODA dưới hình thức các khóa đào tạo chuyển giao công nghệ, tư vấn kỹ thuật, hội thảo chuyên ngành, công trình, thiết bị và các hạng mục kỹ thuật phù hợp với hạ tầng theo quy định của Chính phủ về quản lý và sử dụng viện trợ không hoàn lại không thuộc hỗ trợ phát triển chính thức của cơ quan, tổ chức, cá nhân nước ngoài dành cho
- Citations / expected-source match: ['8b3f9a09-d190-4c38-8b2f-c5e3cc689f2f'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 50.25464500022281, 'context_ms': 19.693829999596346, 'ttft_ms': 1162.871093999911, 'generation_ms': 2768.2227260002037, 'total_ms': 2843.224695999652}

### government_loan_guarantee — DIRECT_FACT

- Question: Dự án hạ tầng vay vốn thương mại có được ưu tiên xem xét cấp bảo lãnh Chính phủ không?
- Answerable: True
- Expected evidence: [['bfae2ca5-6855-4583-83db-841870e5a379']]
- Block 4 final chunks/ranks: [('bfae2ca5-6855-4583-83db-841870e5a379', 1), ('1a6b7744-8a26-4f62-8eca-207bdd065151', 2), ('b5ffcc91-2a3c-4b9d-98ff-f57f4c1a53a4', 3), ('7da489f6-8090-4d00-8ed7-86fccb2c7fde', 4), ('aa94940b-7ed8-48e2-a634-5423a3aaef8e', 5), ('8b3f9a09-d190-4c38-8b2f-c5e3cc689f2f', 6), ('76cce61d-99aa-4e26-8cf9-74ed41353463', 7), ('7ef3b873-84ef-414f-9615-b341cb94f1cc', 8), ('53a2dd91-1e8f-4071-a904-ff1f83cf76f1', 9), ('ccc02a68-e8d3-442c-9dca-fa2d4de42bbf', 10)]
- Expected solution rank: 1
- Retrieval result: FOUND
- Block 5 selected: [('S1', 'bfae2ca5-6855-4583-83db-841870e5a379'), ('S2', '1a6b7744-8a26-4f62-8eca-207bdd065151'), ('S3', 'b5ffcc91-2a3c-4b9d-98ff-f57f4c1a53a4'), ('S4', '7da489f6-8090-4d00-8ed7-86fccb2c7fde'), ('S5', 'aa94940b-7ed8-48e2-a634-5423a3aaef8e'), ('S6', '8b3f9a09-d190-4c38-8b2f-c5e3cc689f2f'), ('S7', '76cce61d-99aa-4e26-8cf9-74ed41353463'), ('S8', '7ef3b873-84ef-414f-9615-b341cb94f1cc'), ('S9', '53a2dd91-1e8f-4071-a904-ff1f83cf76f1'), ('S10', 'ccc02a68-e8d3-442c-9dca-fa2d4de42bbf')]
- Context tokens: 1541 / 4096; stop=NONE
- Expected evidence retained: True
- Block 6: COMPLETED; citation validation=PASS
- Answer preview: Dự án hạ tầng vay vốn thương mại có được ưu tiên xem xét cấp bảo lãnh Chính phủ [S1].
- Citations / expected-source match: ['bfae2ca5-6855-4583-83db-841870e5a379'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 45.900744999926246, 'context_ms': 15.720256999884441, 'ttft_ms': 1250.824362000003, 'generation_ms': 1747.7421790003973, 'total_ms': 1818.0807199996707}

### minimum_charter_capital — KEYWORD_IDENTIFIER

- Question: Trong thời hạn bao lâu và ở mức nào đơn vị vận hành phải được bổ sung, duy trì vốn điều lệ tối thiểu?
- Answerable: True
- Expected evidence: [['76cce61d-99aa-4e26-8cf9-74ed41353463']]
- Block 4 final chunks/ranks: [('76cce61d-99aa-4e26-8cf9-74ed41353463', 1), ('aa94940b-7ed8-48e2-a634-5423a3aaef8e', 2), ('d5c99d40-c7d1-4c2d-8990-45fccf92c3db', 3), ('b5ffcc91-2a3c-4b9d-98ff-f57f4c1a53a4', 4), ('4e2d6ec4-55a0-4467-a200-e221d7e5e0ac', 5), ('ccc02a68-e8d3-442c-9dca-fa2d4de42bbf', 6), ('e3e6bd37-81aa-470c-bbc1-4e596ce51b81', 7), ('bfae2ca5-6855-4583-83db-841870e5a379', 8), ('6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1', 9), ('2851c158-aff0-44c1-9526-df907299d251', 10)]
- Expected solution rank: 1
- Retrieval result: FOUND
- Block 5 selected: [('S1', '76cce61d-99aa-4e26-8cf9-74ed41353463'), ('S2', 'aa94940b-7ed8-48e2-a634-5423a3aaef8e'), ('S3', 'd5c99d40-c7d1-4c2d-8990-45fccf92c3db'), ('S4', 'b5ffcc91-2a3c-4b9d-98ff-f57f4c1a53a4'), ('S5', '4e2d6ec4-55a0-4467-a200-e221d7e5e0ac'), ('S6', 'ccc02a68-e8d3-442c-9dca-fa2d4de42bbf'), ('S7', 'e3e6bd37-81aa-470c-bbc1-4e596ce51b81'), ('S8', 'bfae2ca5-6855-4583-83db-841870e5a379'), ('S9', '6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1'), ('S10', '2851c158-aff0-44c1-9526-df907299d251')]
- Context tokens: 1820 / 4096; stop=NONE
- Expected evidence retained: True
- Block 6: COMPLETED; citation validation=PASS
- Answer preview: Đơn vị vận hành phải được bổ sung và duy trì vốn điều lệ tối thiểu là 3.000 tỷ đồng trong vòng 03 năm kể từ ngày Nghị định có hiệu lực [S1].
- Citations / expected-source match: ['76cce61d-99aa-4e26-8cf9-74ed41353463'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 50.03839800019705, 'context_ms': 22.04564300018319, 'ttft_ms': 1453.2499539996024, 'generation_ms': 2311.1998839999615, 'total_ms': 2389.009768000051}

### debt_over_three_times — DEEPER_RANK

- Question: Khi tổng nợ phải trả vượt quá ba lần vốn chủ sở hữu, đơn vị vận hành cần làm gì để tiếp tục dự án?
- Answerable: True
- Expected evidence: [['d5c99d40-c7d1-4c2d-8990-45fccf92c3db']]
- Block 4 final chunks/ranks: [('d5c99d40-c7d1-4c2d-8990-45fccf92c3db', 1), ('76cce61d-99aa-4e26-8cf9-74ed41353463', 2), ('bfae2ca5-6855-4583-83db-841870e5a379', 3), ('b5ffcc91-2a3c-4b9d-98ff-f57f4c1a53a4', 4), ('1a6b7744-8a26-4f62-8eca-207bdd065151', 5), ('8b3f9a09-d190-4c38-8b2f-c5e3cc689f2f', 6), ('4e2d6ec4-55a0-4467-a200-e221d7e5e0ac', 7), ('9667c02d-ef15-4ac9-8ce7-1e41fa0122e4', 8), ('aa94940b-7ed8-48e2-a634-5423a3aaef8e', 9), ('7ef3b873-84ef-414f-9615-b341cb94f1cc', 10)]
- Expected solution rank: 1
- Retrieval result: FOUND
- Block 5 selected: [('S1', 'd5c99d40-c7d1-4c2d-8990-45fccf92c3db'), ('S2', '76cce61d-99aa-4e26-8cf9-74ed41353463'), ('S3', 'bfae2ca5-6855-4583-83db-841870e5a379'), ('S4', 'b5ffcc91-2a3c-4b9d-98ff-f57f4c1a53a4'), ('S5', '1a6b7744-8a26-4f62-8eca-207bdd065151'), ('S6', '8b3f9a09-d190-4c38-8b2f-c5e3cc689f2f'), ('S7', '4e2d6ec4-55a0-4467-a200-e221d7e5e0ac'), ('S8', '9667c02d-ef15-4ac9-8ce7-1e41fa0122e4'), ('S9', 'aa94940b-7ed8-48e2-a634-5423a3aaef8e'), ('S10', '7ef3b873-84ef-414f-9615-b341cb94f1cc')]
- Context tokens: 1727 / 4096; stop=NONE
- Expected evidence retained: True
- Block 6: COMPLETED; citation validation=PASS
- Answer preview: Đơn vị vận hành hệ thống điện và thị trường điện có thể tiếp tục triển khai dự án sau khi đánh giá tình hình tài chính của dự án, xây dựng phương án vay, trả nợ khả thi và báo cáo Cơ quan đại diện chủ sở hữu giám sát việc sử dụng vốn và theo dõi nghĩa vụ trả nợ cho đến khi hoàn thành nghĩa vụ hoặc khi hệ số nợ phải trả so với vốn chủ sở hữu giảm xuống dưới 03 lần [S1].
- Citations / expected-source match: ['d5c99d40-c7d1-4c2d-8990-45fccf92c3db'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 49.46511000025566, 'context_ms': 20.737550999911036, 'ttft_ms': 1320.8713199996964, 'generation_ms': 3046.3501110002653, 'total_ms': 3121.50403700025}

### after_tax_profit_use — SEMANTIC_PARAPHRASE

- Question: Phần lợi nhuận sau thuế còn lại được sử dụng cho mục đích gì và phần không sử dụng phải xử lý ra sao?
- Answerable: True
- Expected evidence: [['4e2d6ec4-55a0-4467-a200-e221d7e5e0ac']]
- Block 4 final chunks/ranks: [('4e2d6ec4-55a0-4467-a200-e221d7e5e0ac', 1), ('aa911e85-ccd4-4799-adda-2f5d51155bb6', 2), ('8b3f9a09-d190-4c38-8b2f-c5e3cc689f2f', 3), ('1bcf57c2-823e-448d-b228-638094100edb', 4), ('d5227ce1-cff9-492b-b542-5022be73931d', 5), ('53a2dd91-1e8f-4071-a904-ff1f83cf76f1', 6), ('00428e4c-508d-4c2f-98b6-e6b2617f98ee', 7), ('7da489f6-8090-4d00-8ed7-86fccb2c7fde', 8), ('9667c02d-ef15-4ac9-8ce7-1e41fa0122e4', 9), ('db8ea6e4-5401-4fd9-b867-28faf56d3328', 10)]
- Expected solution rank: 1
- Retrieval result: FOUND
- Block 5 selected: [('S1', '4e2d6ec4-55a0-4467-a200-e221d7e5e0ac'), ('S2', 'aa911e85-ccd4-4799-adda-2f5d51155bb6'), ('S3', '8b3f9a09-d190-4c38-8b2f-c5e3cc689f2f'), ('S4', '1bcf57c2-823e-448d-b228-638094100edb'), ('S5', 'd5227ce1-cff9-492b-b542-5022be73931d'), ('S6', '53a2dd91-1e8f-4071-a904-ff1f83cf76f1'), ('S7', '00428e4c-508d-4c2f-98b6-e6b2617f98ee'), ('S8', '7da489f6-8090-4d00-8ed7-86fccb2c7fde'), ('S9', '9667c02d-ef15-4ac9-8ce7-1e41fa0122e4'), ('S10', 'db8ea6e4-5401-4fd9-b867-28faf56d3328')]
- Context tokens: 1137 / 4096; stop=NONE
- Expected evidence retained: True
- Block 6: COMPLETED; citation validation=PASS
- Answer preview: Phần lợi nhuận sau thuế còn lại được sử dụng để bổ sung vốn điều lệ, đầu tư và triển khai các dự án phục vụ hoạt động điều độ hệ thống điện và điều hành giao dịch thị trường điện [S1]. Phần lợi nhuận sau thuế không sử dụng vào mục đích nêu trên phải được nộp vào ngân sách nhà nước theo quy định [S1].
- Citations / expected-source match: ['4e2d6ec4-55a0-4467-a200-e221d7e5e0ac'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 49.088954000581, 'context_ms': 14.265492000049562, 'ttft_ms': 1082.3151949998646, 'generation_ms': 2455.522672999905, 'total_ms': 2525.0206569999136}

### land_assets_capital — DIRECT_FACT

- Question: Nhà nước có thể bổ sung vốn điều lệ cho đơn vị vận hành bằng đất và tài sản gắn liền với đất không?
- Answerable: True
- Expected evidence: [['aa94940b-7ed8-48e2-a634-5423a3aaef8e']]
- Block 4 final chunks/ranks: [('aa94940b-7ed8-48e2-a634-5423a3aaef8e', 1), ('76cce61d-99aa-4e26-8cf9-74ed41353463', 2), ('4e2d6ec4-55a0-4467-a200-e221d7e5e0ac', 3), ('f1a28b76-e9f0-4a8b-83f6-59374c0fc98d', 4), ('bfae2ca5-6855-4583-83db-841870e5a379', 5), ('1a6b7744-8a26-4f62-8eca-207bdd065151', 6), ('b5ffcc91-2a3c-4b9d-98ff-f57f4c1a53a4', 7), ('ccc02a68-e8d3-442c-9dca-fa2d4de42bbf', 8), ('7ef3b873-84ef-414f-9615-b341cb94f1cc', 9), ('6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1', 10)]
- Expected solution rank: 1
- Retrieval result: FOUND
- Block 5 selected: [('S1', 'aa94940b-7ed8-48e2-a634-5423a3aaef8e'), ('S2', '76cce61d-99aa-4e26-8cf9-74ed41353463'), ('S3', '4e2d6ec4-55a0-4467-a200-e221d7e5e0ac'), ('S4', 'f1a28b76-e9f0-4a8b-83f6-59374c0fc98d'), ('S5', 'bfae2ca5-6855-4583-83db-841870e5a379'), ('S6', '1a6b7744-8a26-4f62-8eca-207bdd065151'), ('S7', 'b5ffcc91-2a3c-4b9d-98ff-f57f4c1a53a4'), ('S8', 'ccc02a68-e8d3-442c-9dca-fa2d4de42bbf'), ('S9', '7ef3b873-84ef-414f-9615-b341cb94f1cc'), ('S10', '6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1')]
- Context tokens: 1605 / 4096; stop=NONE
- Expected evidence retained: True
- Block 6: COMPLETED; citation validation=PASS
- Answer preview: Nhà nước có thể xem xét ưu tiên bố trí vốn để bổ sung vốn điều lệ cho đơn vị vận hành thông qua hình thức giao đất và các tài sản khác gắn liền với đất [S1].
- Citations / expected-source match: ['aa94940b-7ed8-48e2-a634-5423a3aaef8e'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 47.13563899986184, 'context_ms': 19.183200000043144, 'ttft_ms': 1281.7879450003602, 'generation_ms': 2118.3336230005807, 'total_ms': 2190.3440019996196}

### domestic_expert_pay_cap — KEYWORD_IDENTIFIER

- Question: Mức thuê chuyên gia tư vấn trong nước tối đa so với mức lương chuyên gia của Nhà nước là bao nhiêu?
- Answerable: True
- Expected evidence: [['3a16c7b5-6d12-4d34-b432-ef5078eee0c9']]
- Block 4 final chunks/ranks: [('3a16c7b5-6d12-4d34-b432-ef5078eee0c9', 1), ('5a5aeeb5-ce90-41de-837c-332bd208f897', 2), ('14dcae3b-7755-440d-bb08-f0ea08c3563c', 3), ('f2e31a1b-b8f9-4ebb-95ef-6f93566028e5', 4), ('00428e4c-508d-4c2f-98b6-e6b2617f98ee', 5), ('53a2dd91-1e8f-4071-a904-ff1f83cf76f1', 6), ('ac4ac0ec-5c9b-4fad-8155-f169f6c4f12a', 7), ('b487af78-9ec4-4f2e-98cb-0a2bbd0a332a', 8), ('db8ea6e4-5401-4fd9-b867-28faf56d3328', 9), ('9667c02d-ef15-4ac9-8ce7-1e41fa0122e4', 10)]
- Expected solution rank: 1
- Retrieval result: FOUND
- Block 5 selected: [('S1', '3a16c7b5-6d12-4d34-b432-ef5078eee0c9'), ('S2', '5a5aeeb5-ce90-41de-837c-332bd208f897'), ('S3', '14dcae3b-7755-440d-bb08-f0ea08c3563c'), ('S4', 'f2e31a1b-b8f9-4ebb-95ef-6f93566028e5'), ('S5', '00428e4c-508d-4c2f-98b6-e6b2617f98ee'), ('S6', '53a2dd91-1e8f-4071-a904-ff1f83cf76f1'), ('S7', 'ac4ac0ec-5c9b-4fad-8155-f169f6c4f12a'), ('S8', 'b487af78-9ec4-4f2e-98cb-0a2bbd0a332a'), ('S9', 'db8ea6e4-5401-4fd9-b867-28faf56d3328'), ('S10', '9667c02d-ef15-4ac9-8ce7-1e41fa0122e4')]
- Context tokens: 1035 / 4096; stop=NONE
- Expected evidence retained: True
- Block 6: COMPLETED; citation validation=PASS
- Answer preview: Mức thuê chuyên gia tư vấn trong nước tối đa là 1,5 lần mức lương chuyên gia của Nhà nước [S1].
- Citations / expected-source match: ['3a16c7b5-6d12-4d34-b432-ef5078eee0c9'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 49.51067099955253, 'context_ms': 14.722619999702147, 'ttft_ms': 655.6413139996948, 'generation_ms': 1256.0995969997748, 'total_ms': 1326.1278319996563}

### additional_income_filter — DOCUMENT_FILTER

- Question: Thu nhập tăng thêm cho người lao động trực tiếp được tính theo tỷ lệ nào và trả vào thời điểm nào?
- Answerable: True
- Expected evidence: [['525ff655-b131-4375-8ead-0740eaa65957']]
- Block 4 final chunks/ranks: [('525ff655-b131-4375-8ead-0740eaa65957', 1), ('5a5aeeb5-ce90-41de-837c-332bd208f897', 2), ('6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1', 3), ('e3e6bd37-81aa-470c-bbc1-4e596ce51b81', 4), ('1bcf57c2-823e-448d-b228-638094100edb', 5), ('76cce61d-99aa-4e26-8cf9-74ed41353463', 6), ('db8ea6e4-5401-4fd9-b867-28faf56d3328', 7), ('123a2580-3ab8-42d6-aa50-c796fc691baa', 8), ('b487af78-9ec4-4f2e-98cb-0a2bbd0a332a', 9), ('00428e4c-508d-4c2f-98b6-e6b2617f98ee', 10)]
- Expected solution rank: 1
- Retrieval result: FOUND
- Block 5 selected: [('S1', '525ff655-b131-4375-8ead-0740eaa65957'), ('S2', '5a5aeeb5-ce90-41de-837c-332bd208f897'), ('S3', '6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1'), ('S4', 'e3e6bd37-81aa-470c-bbc1-4e596ce51b81'), ('S5', '1bcf57c2-823e-448d-b228-638094100edb'), ('S6', '76cce61d-99aa-4e26-8cf9-74ed41353463'), ('S7', 'db8ea6e4-5401-4fd9-b867-28faf56d3328'), ('S8', '123a2580-3ab8-42d6-aa50-c796fc691baa'), ('S9', 'b487af78-9ec4-4f2e-98cb-0a2bbd0a332a'), ('S10', '00428e4c-508d-4c2f-98b6-e6b2617f98ee')]
- Context tokens: 1433 / 4096; stop=NONE
- Expected evidence retained: True
- Block 6: COMPLETED; citation validation=PASS
- Answer preview: Thu nhập tăng thêm được tính theo tỷ lệ 30% mức lương theo hệ số hiện hưởng [S1] và được trả cùng với kỳ lương hằng tháng [S1].
- Citations / expected-source match: ['525ff655-b131-4375-8ead-0740eaa65957'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 43.481026999870664, 'context_ms': 20.809627000744513, 'ttft_ms': 1202.6985949996742, 'generation_ms': 1949.8093860001973, 'total_ms': 2020.4993340003057}

### supplementary_retirement — SEMANTIC_PARAPHRASE

- Question: Người lao động trực tiếp được hưởng chế độ hưu trí bổ sung trong thời gian nào và ai quyết định mức đóng?
- Answerable: True
- Expected evidence: [['e3e6bd37-81aa-470c-bbc1-4e596ce51b81']]
- Block 4 final chunks/ranks: [('e3e6bd37-81aa-470c-bbc1-4e596ce51b81', 1), ('6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1', 2), ('5a5aeeb5-ce90-41de-837c-332bd208f897', 3), ('525ff655-b131-4375-8ead-0740eaa65957', 4), ('123a2580-3ab8-42d6-aa50-c796fc691baa', 5), ('c45e3d45-7183-42c5-8d65-9917878e1f6d', 6), ('32b30c2b-9ac9-46f9-9c70-60e869d4c820', 7), ('b487af78-9ec4-4f2e-98cb-0a2bbd0a332a', 8), ('1bcf57c2-823e-448d-b228-638094100edb', 9), ('a2938526-154c-46fa-812c-ca4be5e42fc5', 10)]
- Expected solution rank: 1
- Retrieval result: FOUND
- Block 5 selected: [('S1', 'e3e6bd37-81aa-470c-bbc1-4e596ce51b81'), ('S2', '6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1'), ('S3', '5a5aeeb5-ce90-41de-837c-332bd208f897'), ('S4', '525ff655-b131-4375-8ead-0740eaa65957'), ('S5', '123a2580-3ab8-42d6-aa50-c796fc691baa'), ('S6', 'c45e3d45-7183-42c5-8d65-9917878e1f6d'), ('S7', '32b30c2b-9ac9-46f9-9c70-60e869d4c820'), ('S8', 'b487af78-9ec4-4f2e-98cb-0a2bbd0a332a'), ('S9', '1bcf57c2-823e-448d-b228-638094100edb'), ('S10', 'a2938526-154c-46fa-812c-ca4be5e42fc5')]
- Context tokens: 1290 / 4096; stop=NONE
- Expected evidence retained: True
- Block 6: COMPLETED; citation validation=PASS
- Answer preview: Người lao động trực tiếp được hưởng chế độ hưu trí bổ sung trong suốt quá trình công tác tại Đơn vị vận hành hệ thống điện và thị trường điện [S1]. Mức đóng bảo hiểm hưu trí bổ sung do Đơn vị vận hành hệ thống điện và thị trường điện quyết định căn cứ vào điều kiện tài chính [S1].
- Citations / expected-source match: ['e3e6bd37-81aa-470c-bbc1-4e596ce51b81'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 45.4696070000864, 'context_ms': 15.861185000176192, 'ttft_ms': 1189.958721000039, 'generation_ms': 2470.82197599957, 'total_ms': 2539.5204619999276}

### liability_correct_procedure — DEEPER_RANK

- Question: Một điều kiện để được xem xét miễn hoặc giảm nhẹ trách nhiệm là người lao động phải thực hiện nhiệm vụ theo thẩm quyền và thủ tục như thế nào?
- Answerable: True
- Expected evidence: [['956cafca-c7e0-4b2d-b9a9-23365a8a9af9']]
- Block 4 final chunks/ranks: [('32b30c2b-9ac9-46f9-9c70-60e869d4c820', 1), ('956cafca-c7e0-4b2d-b9a9-23365a8a9af9', 2), ('c45e3d45-7183-42c5-8d65-9917878e1f6d', 3), ('123a2580-3ab8-42d6-aa50-c796fc691baa', 4), ('1bcf57c2-823e-448d-b228-638094100edb', 5), ('ac499a6f-b6fc-407a-8de2-f3607017944f', 6), ('e14d63ba-3882-43ad-b7b0-22cbebe5248c', 7), ('0210460d-1df2-497b-8dfa-662c87bcd136', 8), ('ec777336-15be-4698-8a21-6b6ba94cfaba', 9), ('46ea4b72-f1e5-46c6-96d9-fbf317f9b9a8', 10)]
- Expected solution rank: 2
- Retrieval result: FOUND
- Block 5 selected: [('S1', '32b30c2b-9ac9-46f9-9c70-60e869d4c820'), ('S2', '956cafca-c7e0-4b2d-b9a9-23365a8a9af9'), ('S3', 'c45e3d45-7183-42c5-8d65-9917878e1f6d'), ('S4', '123a2580-3ab8-42d6-aa50-c796fc691baa'), ('S5', '1bcf57c2-823e-448d-b228-638094100edb'), ('S6', 'ac499a6f-b6fc-407a-8de2-f3607017944f'), ('S7', 'e14d63ba-3882-43ad-b7b0-22cbebe5248c'), ('S8', '0210460d-1df2-497b-8dfa-662c87bcd136'), ('S9', 'ec777336-15be-4698-8a21-6b6ba94cfaba'), ('S10', '46ea4b72-f1e5-46c6-96d9-fbf317f9b9a8')]
- Context tokens: 1202 / 4096; stop=NONE
- Expected evidence retained: True
- Block 6: COMPLETED; citation validation=PASS
- Answer preview: Người lao động phải thực hiện đúng thẩm quyền, trình tự, thủ tục [S2].
- Citations / expected-source match: ['956cafca-c7e0-4b2d-b9a9-23365a8a9af9'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 63.1183030000102, 'context_ms': 13.875487000404974, 'ttft_ms': 1110.3356280000298, 'generation_ms': 1567.6105869997627, 'total_ms': 1649.9645780004357}

### ministry_approves_list — DIRECT_FACT

- Question: Cơ quan nào phê duyệt danh mục chi tiết cơ sở hạ tầng, hệ thống thiết yếu do đơn vị vận hành trình?
- Answerable: True
- Expected evidence: [['6c815bcf-52d2-44ca-a974-f7dd82d82eef']]
- Block 4 final chunks/ranks: [('6c815bcf-52d2-44ca-a974-f7dd82d82eef', 1), ('56a9f913-4fb8-4b95-b90f-4e7f04b9e945', 2), ('ccc02a68-e8d3-442c-9dca-fa2d4de42bbf', 3), ('0210460d-1df2-497b-8dfa-662c87bcd136', 4), ('bfae2ca5-6855-4583-83db-841870e5a379', 5), ('7ef3b873-84ef-414f-9615-b341cb94f1cc', 6), ('749da3f5-6394-476a-b99f-44400d7c115b', 7), ('fd3f2bd6-3f66-4167-8efb-542078559d9b', 8), ('1a6b7744-8a26-4f62-8eca-207bdd065151', 9), ('9ab66b53-663f-4642-9190-d80a6f61997d', 10)]
- Expected solution rank: 1
- Retrieval result: FOUND
- Block 5 selected: [('S1', '6c815bcf-52d2-44ca-a974-f7dd82d82eef'), ('S2', '56a9f913-4fb8-4b95-b90f-4e7f04b9e945'), ('S3', 'ccc02a68-e8d3-442c-9dca-fa2d4de42bbf'), ('S4', '0210460d-1df2-497b-8dfa-662c87bcd136'), ('S5', 'bfae2ca5-6855-4583-83db-841870e5a379'), ('S6', '7ef3b873-84ef-414f-9615-b341cb94f1cc'), ('S7', '749da3f5-6394-476a-b99f-44400d7c115b'), ('S8', 'fd3f2bd6-3f66-4167-8efb-542078559d9b'), ('S9', '1a6b7744-8a26-4f62-8eca-207bdd065151'), ('S10', '9ab66b53-663f-4642-9190-d80a6f61997d')]
- Context tokens: 1672 / 4096; stop=NONE
- Expected evidence retained: True
- Block 6: INSUFFICIENT_EVIDENCE; citation validation=PASS
- Answer preview: Bằng chứng được cung cấp không đủ để trả lời câu hỏi.
- Citations / expected-source match: [] / False
- Failure attribution: INSUFFICIENT_EVIDENCE_FALSE_NEGATIVE
- Timings ms: {'retrieval_ms': 55.19626099976449, 'context_ms': 18.131136000192782, 'ttft_ms': 1271.7585620002865, 'generation_ms': 1441.4517280001746, 'total_ms': 1520.6815850006024}

### city_land_responsibility — KEYWORD_IDENTIFIER

- Question: UBND những thành phố nào xem xét giao hoặc cho thuê đất không đấu giá để xây dựng trụ sở độc lập?
- Answerable: True
- Expected evidence: [['5296ee36-1e31-42ef-a152-7850d13f15ba']]
- Block 4 final chunks/ranks: [('5296ee36-1e31-42ef-a152-7850d13f15ba', 1), ('f1a28b76-e9f0-4a8b-83f6-59374c0fc98d', 2), ('0210460d-1df2-497b-8dfa-662c87bcd136', 3), ('aa94940b-7ed8-48e2-a634-5423a3aaef8e', 4), ('bfae2ca5-6855-4583-83db-841870e5a379', 5), ('8b3f9a09-d190-4c38-8b2f-c5e3cc689f2f', 6), ('46ea4b72-f1e5-46c6-96d9-fbf317f9b9a8', 7), ('d5227ce1-cff9-492b-b542-5022be73931d', 8), ('3a16c7b5-6d12-4d34-b432-ef5078eee0c9', 9), ('ea21d5a1-92e7-4863-8619-5db9a4b0217f', 10)]
- Expected solution rank: 1
- Retrieval result: FOUND
- Block 5 selected: [('S1', '5296ee36-1e31-42ef-a152-7850d13f15ba'), ('S2', 'f1a28b76-e9f0-4a8b-83f6-59374c0fc98d'), ('S3', '0210460d-1df2-497b-8dfa-662c87bcd136'), ('S4', 'aa94940b-7ed8-48e2-a634-5423a3aaef8e'), ('S5', 'bfae2ca5-6855-4583-83db-841870e5a379'), ('S6', '8b3f9a09-d190-4c38-8b2f-c5e3cc689f2f'), ('S7', '46ea4b72-f1e5-46c6-96d9-fbf317f9b9a8'), ('S8', 'd5227ce1-cff9-492b-b542-5022be73931d'), ('S9', '3a16c7b5-6d12-4d34-b432-ef5078eee0c9'), ('S10', 'ea21d5a1-92e7-4863-8619-5db9a4b0217f')]
- Context tokens: 1759 / 4096; stop=NONE
- Expected evidence retained: True
- Block 6: COMPLETED; citation validation=PASS
- Answer preview: UBND Thành phố Hà Nội, Thành phố Hồ Chí Minh, Thành phố Đà Nẵng xem xét quyết định giao đất, cho thuê đất không đấu giá quyền sử dụng đất để xây dựng trụ sở độc lập của Đơn vị vận hành hệ thống điện và thị trường điện [S1].
- Citations / expected-source match: ['5296ee36-1e31-42ef-a152-7850d13f15ba'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 44.24058899985539, 'context_ms': 19.97237799969298, 'ttft_ms': 1283.231608999813, 'generation_ms': 2286.6408549998596, 'total_ms': 2360.4975409998588}

### annual_report_deadline — DEEPER_RANK

- Question: Hằng năm, đơn vị vận hành phải báo cáo Bộ Công Thương về triển khai chính sách ưu đãi trước ngày nào?
- Answerable: True
- Expected evidence: [['642f394d-0dbb-4e95-9ef7-a676e1209d5f']]
- Block 4 final chunks/ranks: [('642f394d-0dbb-4e95-9ef7-a676e1209d5f', 1), ('9ab66b53-663f-4642-9190-d80a6f61997d', 2), ('9f5e20ba-61af-4f1d-9ee8-6aa8a3cab585', 3), ('d5c99d40-c7d1-4c2d-8990-45fccf92c3db', 4), ('749da3f5-6394-476a-b99f-44400d7c115b', 5), ('b487af78-9ec4-4f2e-98cb-0a2bbd0a332a', 6), ('ac499a6f-b6fc-407a-8de2-f3607017944f', 7), ('1f40648f-42b1-4a17-8858-d3c3024ee510', 8), ('6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1', 9), ('ccc02a68-e8d3-442c-9dca-fa2d4de42bbf', 10)]
- Expected solution rank: 1
- Retrieval result: FOUND
- Block 5 selected: [('S1', '642f394d-0dbb-4e95-9ef7-a676e1209d5f'), ('S2', '9ab66b53-663f-4642-9190-d80a6f61997d'), ('S3', '9f5e20ba-61af-4f1d-9ee8-6aa8a3cab585'), ('S4', 'd5c99d40-c7d1-4c2d-8990-45fccf92c3db'), ('S5', '749da3f5-6394-476a-b99f-44400d7c115b'), ('S6', 'b487af78-9ec4-4f2e-98cb-0a2bbd0a332a'), ('S7', 'ac499a6f-b6fc-407a-8de2-f3607017944f'), ('S8', '1f40648f-42b1-4a17-8858-d3c3024ee510'), ('S9', '6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1'), ('S10', 'ccc02a68-e8d3-442c-9dca-fa2d4de42bbf')]
- Context tokens: 1432 / 4096; stop=NONE
- Expected evidence retained: True
- Block 6: COMPLETED; citation validation=PASS
- Answer preview: Trước ngày 15 tháng 12 hằng năm [S1].
- Citations / expected-source match: ['642f394d-0dbb-4e95-9ef7-a676e1209d5f'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 45.2924900000653, 'context_ms': 16.332768999745895, 'ttft_ms': 1193.604848999712, 'generation_ms': 1552.4649440003486, 'total_ms': 1622.591872999692}

### effective_date_filter — DOCUMENT_FILTER

- Question: Nghị định 135/2026/NĐ-CP có hiệu lực từ ngày nào?
- Answerable: True
- Expected evidence: [['a2938526-154c-46fa-812c-ca4be5e42fc5']]
- Block 4 final chunks/ranks: [('a2938526-154c-46fa-812c-ca4be5e42fc5', 1), ('9ab66b53-663f-4642-9190-d80a6f61997d', 2), ('76cce61d-99aa-4e26-8cf9-74ed41353463', 3), ('118586b0-33dd-4ce8-9919-aba2efd5a2cd', 4), ('1bcf57c2-823e-448d-b228-638094100edb', 5), ('14dcae3b-7755-440d-bb08-f0ea08c3563c', 6), ('9667c02d-ef15-4ac9-8ce7-1e41fa0122e4', 7), ('1f40648f-42b1-4a17-8858-d3c3024ee510', 8), ('46ea4b72-f1e5-46c6-96d9-fbf317f9b9a8', 9), ('642f394d-0dbb-4e95-9ef7-a676e1209d5f', 10)]
- Expected solution rank: 1
- Retrieval result: FOUND
- Block 5 selected: [('S1', 'a2938526-154c-46fa-812c-ca4be5e42fc5'), ('S2', '9ab66b53-663f-4642-9190-d80a6f61997d'), ('S3', '76cce61d-99aa-4e26-8cf9-74ed41353463'), ('S4', '118586b0-33dd-4ce8-9919-aba2efd5a2cd'), ('S5', '1bcf57c2-823e-448d-b228-638094100edb'), ('S6', '14dcae3b-7755-440d-bb08-f0ea08c3563c'), ('S7', '9667c02d-ef15-4ac9-8ce7-1e41fa0122e4'), ('S8', '1f40648f-42b1-4a17-8858-d3c3024ee510'), ('S9', '46ea4b72-f1e5-46c6-96d9-fbf317f9b9a8'), ('S10', '642f394d-0dbb-4e95-9ef7-a676e1209d5f')]
- Context tokens: 1301 / 4096; stop=NONE
- Expected evidence retained: True
- Block 6: COMPLETED; citation validation=PASS
- Answer preview: Nghị định 135/2026/NĐ-CP có hiệu lực thi hành kể từ ngày 25 tháng 5 năm 2026 [S1].
- Citations / expected-source match: ['a2938526-154c-46fa-812c-ca4be5e42fc5'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 40.532872999392566, 'context_ms': 18.87940799952048, 'ttft_ms': 1113.013905999651, 'generation_ms': 1837.1168300000136, 'total_ms': 1901.3306890001331}

### corporate_tax_rate_absent — UNANSWERABLE

- Question: Nghị định 135/2026/NĐ-CP quy định mức thuế suất thuế thu nhập doanh nghiệp của NSMO là bao nhiêu?
- Answerable: False
- Expected evidence: []
- Block 4 final chunks/ranks: [('76cce61d-99aa-4e26-8cf9-74ed41353463', 1), ('a2938526-154c-46fa-812c-ca4be5e42fc5', 2), ('1bcf57c2-823e-448d-b228-638094100edb', 3), ('9ab66b53-663f-4642-9190-d80a6f61997d', 4), ('00428e4c-508d-4c2f-98b6-e6b2617f98ee', 5), ('46ea4b72-f1e5-46c6-96d9-fbf317f9b9a8', 6), ('2851c158-aff0-44c1-9526-df907299d251', 7), ('53a2dd91-1e8f-4071-a904-ff1f83cf76f1', 8), ('d5227ce1-cff9-492b-b542-5022be73931d', 9), ('abdf4475-fa62-47bd-83a7-36aec6df506a', 10)]
- Expected solution rank: None
- Retrieval result: MISS
- Block 5 selected: [('S1', '76cce61d-99aa-4e26-8cf9-74ed41353463'), ('S2', 'a2938526-154c-46fa-812c-ca4be5e42fc5'), ('S3', '1bcf57c2-823e-448d-b228-638094100edb'), ('S4', '9ab66b53-663f-4642-9190-d80a6f61997d'), ('S5', '00428e4c-508d-4c2f-98b6-e6b2617f98ee'), ('S6', '46ea4b72-f1e5-46c6-96d9-fbf317f9b9a8'), ('S7', '2851c158-aff0-44c1-9526-df907299d251'), ('S8', '53a2dd91-1e8f-4071-a904-ff1f83cf76f1'), ('S9', 'd5227ce1-cff9-492b-b542-5022be73931d'), ('S10', 'abdf4475-fa62-47bd-83a7-36aec6df506a')]
- Context tokens: 1346 / 4096; stop=NONE
- Expected evidence retained: None
- Block 6: INSUFFICIENT_EVIDENCE; citation validation=PASS
- Answer preview: Bằng chứng được cung cấp không đủ để trả lời câu hỏi.
- Citations / expected-source match: [] / None
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 43.69200099972659, 'context_ms': 15.892656000687566, 'ttft_ms': 632.8263039995363, 'generation_ms': 785.9205959994142, 'total_ms': 850.0531419995241}

### administrative_fine_absent — UNANSWERABLE

- Question: Mức phạt hành chính đối với NSMO khi nộp báo cáo trễ là bao nhiêu tiền?
- Answerable: False
- Expected evidence: []
- Block 4 final chunks/ranks: [('67e38280-1017-4f93-b9ac-179a4a0db565', 1), ('1bcf57c2-823e-448d-b228-638094100edb', 2), ('d5c99d40-c7d1-4c2d-8990-45fccf92c3db', 3), ('642f394d-0dbb-4e95-9ef7-a676e1209d5f', 4), ('a2938526-154c-46fa-812c-ca4be5e42fc5', 5), ('c7c23b8f-e543-4c6b-b069-695f30d6c022', 6), ('76cce61d-99aa-4e26-8cf9-74ed41353463', 7), ('e14d63ba-3882-43ad-b7b0-22cbebe5248c', 8), ('0210460d-1df2-497b-8dfa-662c87bcd136', 9), ('46ea4b72-f1e5-46c6-96d9-fbf317f9b9a8', 10)]
- Expected solution rank: None
- Retrieval result: MISS
- Block 5 selected: [('S1', '67e38280-1017-4f93-b9ac-179a4a0db565'), ('S2', '1bcf57c2-823e-448d-b228-638094100edb'), ('S3', 'd5c99d40-c7d1-4c2d-8990-45fccf92c3db'), ('S4', '642f394d-0dbb-4e95-9ef7-a676e1209d5f'), ('S5', 'a2938526-154c-46fa-812c-ca4be5e42fc5'), ('S6', 'c7c23b8f-e543-4c6b-b069-695f30d6c022'), ('S7', '76cce61d-99aa-4e26-8cf9-74ed41353463'), ('S8', 'e14d63ba-3882-43ad-b7b0-22cbebe5248c'), ('S9', '0210460d-1df2-497b-8dfa-662c87bcd136'), ('S10', '46ea4b72-f1e5-46c6-96d9-fbf317f9b9a8')]
- Context tokens: 1568 / 4096; stop=NONE
- Expected evidence retained: None
- Block 6: INSUFFICIENT_EVIDENCE; citation validation=PASS
- Answer preview: Bằng chứng được cung cấp không đủ để trả lời câu hỏi.
- Citations / expected-source match: [] / None
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 36.62032500051282, 'context_ms': 15.181398999629891, 'ttft_ms': 642.5680550000834, 'generation_ms': 803.4340249996603, 'total_ms': 863.516838000578}

### retail_electricity_price_absent — OUT_OF_CORPUS

- Question: Giá bán lẻ điện sinh hoạt bậc 3 hiện nay là bao nhiêu đồng mỗi kWh?
- Answerable: False
- Expected evidence: []
- Block 4 final chunks/ranks: [('76cce61d-99aa-4e26-8cf9-74ed41353463', 1), ('e3e6bd37-81aa-470c-bbc1-4e596ce51b81', 2), ('5a5aeeb5-ce90-41de-837c-332bd208f897', 3), ('9ab66b53-663f-4642-9190-d80a6f61997d', 4), ('525ff655-b131-4375-8ead-0740eaa65957', 5), ('88d71393-ec3f-4bc1-be9d-72f50be0fd45', 6), ('2851c158-aff0-44c1-9526-df907299d251', 7), ('6cdbbffe-98e1-4d7f-870f-ce1d369e7046', 8), ('123a2580-3ab8-42d6-aa50-c796fc691baa', 9), ('3f7bfb6a-9d4c-4115-9fbd-c9b0a452f30b', 10)]
- Expected solution rank: None
- Retrieval result: MISS
- Block 5 selected: [('S1', '76cce61d-99aa-4e26-8cf9-74ed41353463'), ('S2', 'e3e6bd37-81aa-470c-bbc1-4e596ce51b81'), ('S3', '5a5aeeb5-ce90-41de-837c-332bd208f897'), ('S4', '9ab66b53-663f-4642-9190-d80a6f61997d'), ('S5', '525ff655-b131-4375-8ead-0740eaa65957'), ('S6', '88d71393-ec3f-4bc1-be9d-72f50be0fd45'), ('S7', '2851c158-aff0-44c1-9526-df907299d251'), ('S8', '6cdbbffe-98e1-4d7f-870f-ce1d369e7046'), ('S9', '123a2580-3ab8-42d6-aa50-c796fc691baa'), ('S10', '3f7bfb6a-9d4c-4115-9fbd-c9b0a452f30b')]
- Context tokens: 1727 / 4096; stop=NONE
- Expected evidence retained: None
- Block 6: INSUFFICIENT_EVIDENCE; citation validation=PASS
- Answer preview: Bằng chứng được cung cấp không đủ để trả lời câu hỏi.
- Citations / expected-source match: [] / None
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 41.24353899987909, 'context_ms': 21.750527000222064, 'ttft_ms': 611.4218889997574, 'generation_ms': 770.7827459998953, 'total_ms': 839.4152159999066}

### maternity_leave_absent — OUT_OF_CORPUS

- Question: Người lao động nữ tại NSMO được nghỉ thai sản bao nhiêu tháng?
- Answerable: False
- Expected evidence: []
- Block 4 final chunks/ranks: [('a2938526-154c-46fa-812c-ca4be5e42fc5', 1), ('1bcf57c2-823e-448d-b228-638094100edb', 2), ('ec777336-15be-4698-8a21-6b6ba94cfaba', 3), ('c45e3d45-7183-42c5-8d65-9917878e1f6d', 4), ('14dcae3b-7755-440d-bb08-f0ea08c3563c', 5), ('b487af78-9ec4-4f2e-98cb-0a2bbd0a332a', 6), ('e14d63ba-3882-43ad-b7b0-22cbebe5248c', 7), ('46ea4b72-f1e5-46c6-96d9-fbf317f9b9a8', 8), ('ac499a6f-b6fc-407a-8de2-f3607017944f', 9), ('32b30c2b-9ac9-46f9-9c70-60e869d4c820', 10)]
- Expected solution rank: None
- Retrieval result: MISS
- Block 5 selected: [('S1', 'a2938526-154c-46fa-812c-ca4be5e42fc5'), ('S2', '1bcf57c2-823e-448d-b228-638094100edb'), ('S3', 'ec777336-15be-4698-8a21-6b6ba94cfaba'), ('S4', 'c45e3d45-7183-42c5-8d65-9917878e1f6d'), ('S5', '14dcae3b-7755-440d-bb08-f0ea08c3563c'), ('S6', 'b487af78-9ec4-4f2e-98cb-0a2bbd0a332a'), ('S7', 'e14d63ba-3882-43ad-b7b0-22cbebe5248c'), ('S8', '46ea4b72-f1e5-46c6-96d9-fbf317f9b9a8'), ('S9', 'ac499a6f-b6fc-407a-8de2-f3607017944f'), ('S10', '32b30c2b-9ac9-46f9-9c70-60e869d4c820')]
- Context tokens: 874 / 4096; stop=NONE
- Expected evidence retained: None
- Block 6: INSUFFICIENT_EVIDENCE; citation validation=PASS
- Answer preview: Bằng chứng được cung cấp không đủ để trả lời câu hỏi.
- Citations / expected-source match: [] / None
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 34.72572000009677, 'context_ms': 9.760034999999334, 'ttft_ms': 1111.3561559996015, 'generation_ms': 1284.6330429993031, 'total_ms': 1334.3379390007613}

### renewable_license_absent — OUT_OF_CORPUS

- Question: Hồ sơ xin giấy phép cho dự án điện gió ngoài khơi gồm những tài liệu nào?
- Answerable: False
- Expected evidence: []
- Block 4 final chunks/ranks: [('0210460d-1df2-497b-8dfa-662c87bcd136', 1), ('56a9f913-4fb8-4b95-b90f-4e7f04b9e945', 2), ('3a16c7b5-6d12-4d34-b432-ef5078eee0c9', 3), ('7ef3b873-84ef-414f-9615-b341cb94f1cc', 4), ('b5ffcc91-2a3c-4b9d-98ff-f57f4c1a53a4', 5), ('db8ea6e4-5401-4fd9-b867-28faf56d3328', 6), ('8b3f9a09-d190-4c38-8b2f-c5e3cc689f2f', 7), ('1a6b7744-8a26-4f62-8eca-207bdd065151', 8), ('bfae2ca5-6855-4583-83db-841870e5a379', 9), ('ccc02a68-e8d3-442c-9dca-fa2d4de42bbf', 10)]
- Expected solution rank: None
- Retrieval result: MISS
- Block 5 selected: [('S1', '0210460d-1df2-497b-8dfa-662c87bcd136'), ('S2', '56a9f913-4fb8-4b95-b90f-4e7f04b9e945'), ('S3', '3a16c7b5-6d12-4d34-b432-ef5078eee0c9'), ('S4', '7ef3b873-84ef-414f-9615-b341cb94f1cc'), ('S5', 'b5ffcc91-2a3c-4b9d-98ff-f57f4c1a53a4'), ('S6', 'db8ea6e4-5401-4fd9-b867-28faf56d3328'), ('S7', '8b3f9a09-d190-4c38-8b2f-c5e3cc689f2f'), ('S8', '1a6b7744-8a26-4f62-8eca-207bdd065151'), ('S9', 'bfae2ca5-6855-4583-83db-841870e5a379'), ('S10', 'ccc02a68-e8d3-442c-9dca-fa2d4de42bbf')]
- Context tokens: 1748 / 4096; stop=NONE
- Expected evidence retained: None
- Block 6: INSUFFICIENT_EVIDENCE; citation validation=PASS
- Answer preview: Bằng chứng được cung cấp không đủ để trả lời câu hỏi.
- Citations / expected-source match: [] / None
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 37.34559099939361, 'context_ms': 23.490645000492805, 'ttft_ms': 691.5600499996799, 'generation_ms': 863.7695159995928, 'total_ms': 930.6639070000529}

## Metric semantics and limitations

An acceptable evidence solution is found only when every chunk in at least one acceptable set occurs within K; its rank is the lowest possible maximum member rank. MRR uses that solution rank. Context retention uses the same complete-set rule. Expected-source citation match is separate from structural citation validity and also requires a complete acceptable set. No LLM-as-judge or semantic entailment claim is made.

The indexed evaluation corpus contains one substantive legal document. Dataset breadth and all aggregate estimates are therefore limited and require human review before any production gate is approved.
