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
- Citation presence: 88.89%
- Citation structural validity: 88.89%
- Expected-source citation match: 81.48%
- Invalid / missing citation rate: 0.00% / 11.11%
- Correct abstention / unsupported answer rate: 0.00% / 100.00%
- Failure counts: {'GENERATION_MISSING_CITATION': 2, 'GENERATION_WRONG_SOURCE': 1, 'PASS': 22, 'RETRIEVAL_MISS': 2, 'UNSUPPORTED_ANSWER': 5}

## Latency

| Stage | Mean ms | P50 ms | P95 ms | N |
|---|---:|---:|---:|---:|
| retrieval_ms | 41.99 | 40.61 | 50.83 | 32 |
| context_ms | 18.42 | 17.60 | 32.49 | 32 |
| ttft_ms | 608.42 | 601.35 | 642.87 | 32 |
| generation_ms | 3084.57 | 2869.39 | 5536.57 | 32 |
| total_ms | 3401.81 | 2933.88 | 5792.30 | 32 |

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
- Answer preview: Dựa trên bằng chứng được cung cấp, Nghị định 135/2026/NĐ-CP quy định về các cơ chế, chính sách ưu đãi, ưu tiên cho **đơn vị điều độ hệ thống điện quốc gia** và **đơn vị điều hành giao dịch thị trường điện**.

Cụ thể, nghị định này điều chỉnh các nhóm cơ chế, chính sách sau:
1.  Cơ chế, chính sách ưu đãi để bảo đảm cơ sở hạ tầng và các hệ thống thiết yếu khác phục vụ hoạt động điều độ hệ thống điện
- Citations / expected-source match: ['749da3f5-6394-476a-b99f-44400d7c115b', '6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1', 'b9237b2e-31c5-47ac-8fe7-57595be42fdf'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 48.649823998857755, 'context_ms': 14.757191001990577, 'ttft_ms': 836.0319999992498, 'generation_ms': 4710.765857002116, 'total_ms': 12831.731332000345}

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
- Answer preview: Dựa trên bằng chứng được cung cấp, những đối tượng thuộc phạm vi áp dụng của Nghị định bao gồm:

*   **Đơn vị điều độ hệ thống điện quốc gia** và **đơn vị điều hành giao dịch thị trường điện**. Đây là các đơn vị được quy định cụ thể trong tiêu đề Nghị định [S1] và là chủ thể chính được hưởng các cơ chế, chính sách ưu đãi, ưu tiên về nguồn nhân lực, dự án đầu tư, cũng như được xem xét áp dụng loại 
- Citations / expected-source match: ['1bcf57c2-823e-448d-b228-638094100edb', '46ea4b72-f1e5-46c6-96d9-fbf317f9b9a8', '6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1', 'b5ffcc91-2a3c-4b9d-98ff-f57f4c1a53a4', '32b30c2b-9ac9-46f9-9c70-60e869d4c820', '14dcae3b-7755-440d-bb08-f0ea08c3563c'] / False
- Failure attribution: RETRIEVAL_MISS
- Timings ms: {'retrieval_ms': 34.67463899869472, 'context_ms': 15.65748800203437, 'ttft_ms': 642.874141001812, 'generation_ms': 4736.447952000162, 'total_ms': 4792.689342000813}

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
- Block 6: COMPLETED_WITH_WARNINGS; citation validation=MISSING_CITATIONS
- Answer preview: Dựa trên bằng chứng được cung cấp, doanh nghiệp hiện được xác định là đơn vị vận hành hệ thống điện và thị trường điện là:

**Công ty trách nhiệm hữu hạn một thành viên Vận hành hệ thống điện và thị trường điện Quốc gia (NSMO)**.

Thông tin này được nêu rõ trong nội dung của [Evidence S1], nơi khẳng định rằng đơn vị này thực hiện quyền và nghĩa vụ của Đơn vị điều độ hệ thống điện quốc gia và Đơn v
- Citations / expected-source match: [] / False
- Failure attribution: GENERATION_MISSING_CITATION
- Timings ms: {'retrieval_ms': 50.83128299884265, 'context_ms': 17.272836001211544, 'ttft_ms': 641.8137389991898, 'generation_ms': 2669.1744640011166, 'total_ms': 2743.5322550009005}

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
- Block 6: COMPLETED_WITH_WARNINGS; citation validation=MISSING_CITATIONS
- Answer preview: Dựa trên bằng chứng được cung cấp, **Điều độ viên quốc gia** được xem là người lao động trực tiếp làm công tác điều độ hệ thống điện quốc gia.

Căn cứ vào nội dung tại [Evidence S1], Nghị định số 135/2026/NĐ-CP quy định rằng nhóm "Người lao động trực tiếp thực hiện công tác điều độ hệ thống điện quốc gia và điều hành giao dịch thị trường điện" bao gồm các chức danh cụ thể (trong đó có Điều độ viên
- Citations / expected-source match: [] / False
- Failure attribution: RETRIEVAL_MISS
- Timings ms: {'retrieval_ms': 47.357461000501644, 'context_ms': 21.631199000694323, 'ttft_ms': 590.0671279996459, 'generation_ms': 3316.7208479972032, 'total_ms': 3390.6948740004736}

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
- Answer preview: Theo bằng chứng được cung cấp, nguyên tắc về hiện đại hóa hạ tầng và ứng dụng công nghệ trong công tác điều độ được quy định như sau:

*   **Ưu tiên đầu tư đồng bộ:** Có cơ chế ưu tiên để bảo đảm đầu tư đồng bộ, hiện đại hóa hạ tầng kỹ thuật [S1].
*   **Ứng dụng công nghệ số và tự động hóa:** Đẩy mạnh ứng dụng công nghệ số và tự động hóa trong công tác điều độ, vận hành hệ thống điện và công tác đ
- Citations / expected-source match: ['b345594b-9fd4-4d24-97ad-257b0f5df2b0', 'fd3f2bd6-3f66-4167-8efb-542078559d9b', '3bed5a7c-a0a1-43e5-b6ed-3ec6a67611cf', 'bc958182-732b-4fa9-a5c0-79dc75282032'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 39.940929000295, 'context_ms': 12.166481999884127, 'ttft_ms': 623.9696809971065, 'generation_ms': 4613.460212000064, 'total_ms': 4670.816302001185}

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
- Answer preview: Dựa trên bằng chứng được cung cấp, Đơn vị vận hành hệ thống điện và thị trường điện được chi trả các khoản sau cho người lao động trực tiếp thực hiện công tác điều độ hệ thống điện quốc gia và điều hành giao dịch thị trường điện:

*   **Thu nhập tăng thêm:** Theo tỷ lệ 30% mức lương theo hệ số hiện hưởng (không bao gồm phụ cấp), được trả cùng với kỳ lương hằng tháng [S4].
*   **Phúc lợi và bảo hiể
- Citations / expected-source match: ['525ff655-b131-4375-8ead-0740eaa65957', '6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1', 'e3e6bd37-81aa-470c-bbc1-4e596ce51b81', '5a5aeeb5-ce90-41de-837c-332bd208f897'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 38.8425159981125, 'context_ms': 20.759256000019377, 'ttft_ms': 577.147726999101, 'generation_ms': 4402.364134999516, 'total_ms': 4466.609637998772}

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
- Answer preview: Dựa trên bằng chứng được cung cấp, đơn vị vận hành hệ thống điện và thị trường điện phải bảo đảm các quyền lợi và điều kiện sau cho người lao động trực tiếp thực hiện công tác điều độ hệ thống điện quốc gia và điều hành giao dịch thị trường điện:

1.  **Quyền, lợi ích hợp pháp và điều kiện làm việc:** Bảo đảm quyền, lợi ích hợp pháp, điều kiện làm việc an toàn, an ninh thông tin [S1].
2.  **Thu nh
- Citations / expected-source match: ['3f7bfb6a-9d4c-4115-9fbd-c9b0a452f30b', '525ff655-b131-4375-8ead-0740eaa65957', '6e49fa3a-b16e-4cab-8cea-c12cc4f2ced1', 'e3e6bd37-81aa-470c-bbc1-4e596ce51b81', '32b30c2b-9ac9-46f9-9c70-60e869d4c820', 'c45e3d45-7183-42c5-8d65-9917878e1f6d'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 37.96993099967949, 'context_ms': 18.02549499916495, 'ttft_ms': 581.0837190001621, 'generation_ms': 5536.566876002325, 'total_ms': 5597.538168000028}

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
- Answer preview: Dựa trên bằng chứng được cung cấp, cách thức hạch toán và thu hồi các khoản chi phí thuê chuyên gia, thu nhập tăng thêm và bảo hiểm hưu trí bổ sung như sau:

*   **Hạch toán:** Các khoản này (bao gồm cả chế độ bảo hiểm hưu trí bổ sung) được hạch toán vào **chi phí, giá thành kinh doanh** của Đơn vị vận hành hệ thống điện và thị trường điện [S1].
*   **Thu hồi:** Các khoản chi phí trên được tính để
- Citations / expected-source match: ['5a5aeeb5-ce90-41de-837c-332bd208f897', '525ff655-b131-4375-8ead-0740eaa65957', 'e3e6bd37-81aa-470c-bbc1-4e596ce51b81', '3a16c7b5-6d12-4d34-b432-ef5078eee0c9'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 39.863783997134306, 'context_ms': 17.497834996902384, 'ttft_ms': 602.041096000903, 'generation_ms': 5729.424630000722, 'total_ms': 5792.300330998842}

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
- Answer preview: Trụ sở của Đơn vị vận hành hệ thống điện và thị trường điện bao gồm các trung tâm sau:

*   Trung tâm điều khiển chính.
*   Trung tâm điều khiển dự phòng độc lập về vị trí (cho cả cấp quốc gia và miền).

Thông tin này được nêu trong nội dung tại [S1] và [S2].
- Citations / expected-source match: ['ea21d5a1-92e7-4863-8619-5db9a4b0217f', '5296ee36-1e31-42ef-a152-7850d13f15ba'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 37.07645699978457, 'context_ms': 16.614582997135585, 'ttft_ms': 577.5560750007571, 'generation_ms': 1752.918848000263, 'total_ms': 1811.0719659998722}

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
- Answer preview: Cơ sở hạ tầng công nghệ thông tin và an ninh mạng được xếp vào danh mục **Cơ sở hạ tầng công nghệ thông tin, an ninh mạng chuyên ngành trọng yếu** tại Điều 5 của Nghị định số 135/2026/NĐ-CP [S1].
- Citations / expected-source match: ['3bed5a7c-a0a1-43e5-b6ed-3ec6a67611cf'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 36.67192200009595, 'context_ms': 11.469568002212327, 'ttft_ms': 584.6239620004781, 'generation_ms': 1559.4823360006558, 'total_ms': 1611.5755509999872}

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
- Answer preview: Dựa trên bằng chứng được cung cấp, **Đơn vị vận hành hệ thống điện và thị trường điện được ưu tiên tham gia dự án đầu tư sử dụng vốn ODA**.

Cụ thể:
*   Đơn vị này được **ưu tiên đề xuất, tham gia và thực hiện** các dự án đầu tư sử dụng vốn hỗ trợ phát triển chính thức (ODA) [S1].
*   Đơn vị này được **ưu tiên tiếp cận, sử dụng vốn ODA** để thực hiện các dự án được cơ quan nhà nước có thẩm quyền p
- Citations / expected-source match: ['b5ffcc91-2a3c-4b9d-98ff-f57f4c1a53a4', '1a6b7744-8a26-4f62-8eca-207bdd065151', '7da489f6-8090-4d00-8ed7-86fccb2c7fde'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 43.136649001098704, 'context_ms': 17.694866997771896, 'ttft_ms': 621.5769490008825, 'generation_ms': 3093.710101002216, 'total_ms': 3159.562755998195}

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
- Answer preview: Dựa trên bằng chứng được cung cấp, cơ quan có thẩm quyền **có thể** xem xét cho đơn vị vận hành hệ thống điện và thị trường điện thuê đất mà không đấu giá quyền sử dụng đất.

Cụ thể:
*   Theo quy định tại Nghị định số 135/2026/NĐ-CP, đơn vị vận hành hệ thống điện và thị trường điện được cơ quan có thẩm quyền xem xét cho thuê đất không đấu giá quyền sử dụng đất để bảo đảm hoạt động ổn định, an toàn
- Citations / expected-source match: ['f1a28b76-e9f0-4a8b-83f6-59374c0fc98d', '5296ee36-1e31-42ef-a152-7850d13f15ba'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 37.31857599996147, 'context_ms': 17.84955499897478, 'ttft_ms': 600.6620379994274, 'generation_ms': 4061.857961001806, 'total_ms': 4121.582697000122}

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
- Answer preview: Dựa trên bằng chứng được cung cấp, **Khoản 1 Điều 7** của Nghị định số 135/2026/NĐ-CP **có coi** vốn ODA và vốn vay ưu đãi nước ngoài là nguồn vốn đầu tư.

Cụ thể:
*   **[S2]** xác nhận Điều 7 quy định về "Nguồn vốn đầu tư".
*   **[S3]** trong Khoản 1 của Điều này nêu rõ: "Đơn vị vận hành hệ thống điện và thị trường điện được ưu tiên đề xuất, tham gia và thực hiện các dự án đầu tư sử dụng vốn hỗ t
- Citations / expected-source match: ['abdf4475-fa62-47bd-83a7-36aec6df506a', 'b5ffcc91-2a3c-4b9d-98ff-f57f4c1a53a4', '7ef3b873-84ef-414f-9615-b341cb94f1cc'] / False
- Failure attribution: GENERATION_WRONG_SOURCE
- Timings ms: {'retrieval_ms': 45.63373800192494, 'context_ms': 13.519524000003003, 'ttft_ms': 629.6483999976772, 'generation_ms': 4368.0582429988135, 'total_ms': 4431.697530002566}

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
- Answer preview: Dựa trên bằng chứng được cung cấp, đơn vị vận hành hệ thống điện và thị trường điện được ưu tiên tiếp nhận các khoản viện trợ không hoàn lại ngoài ODA dưới những hình thức sau:

*   Các khóa đào tạo chuyển giao công nghệ;
*   Tư vấn kỹ thuật;
*   Hội thảo chuyên ngành;
*   Công trình, thiết bị và các hạng mục kỹ thuật phù hợp với hạ tầng theo quy định của Chính phủ về quản lý và sử dụng viện trợ k
- Citations / expected-source match: ['8b3f9a09-d190-4c38-8b2f-c5e3cc689f2f'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 45.918959000118775, 'context_ms': 18.420012002025032, 'ttft_ms': 580.239798000548, 'generation_ms': 3373.6933239997597, 'total_ms': 3442.6108990010107}

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
- Answer preview: Dựa trên bằng chứng được cung cấp, dự án hạ tầng vay vốn thương mại **có được ưu tiên xem xét cấp bảo lãnh Chính phủ** đối với đơn vị vận hành hệ thống điện và thị trường điện.

Cụ thể:
*   Đối với các dự án đầu tư cơ sở hạ tầng phục vụ công tác điều độ, vận hành hệ thống điện và điều hành giao dịch thị trường điện, trong trường hợp vay vốn thương mại (trong nước hoặc nước ngoài), Đơn vị vận hành 
- Citations / expected-source match: ['bfae2ca5-6855-4583-83db-841870e5a379', '53a2dd91-1e8f-4071-a904-ff1f83cf76f1'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 38.4370800020406, 'context_ms': 22.77329700154951, 'ttft_ms': 587.254870999459, 'generation_ms': 3288.4218280014466, 'total_ms': 3354.389457999787}

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
- Answer preview: Theo bằng chứng được cung cấp, thông tin về thời hạn và mức vốn điều lệ tối thiểu mà đơn vị vận hành phải bổ sung, duy trì như sau:

*   **Thời hạn:** Trong vòng 03 năm kể từ ngày Nghị định số 135/2026/NĐ-CP có hiệu lực [S1].
*   **Mức vốn điều lệ tối thiểu:** 3.000 tỷ đồng [S1].
- Citations / expected-source match: ['76cce61d-99aa-4e26-8cf9-74ed41353463'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 45.85329499968793, 'context_ms': 32.49105799841345, 'ttft_ms': 606.9144809989666, 'generation_ms': 2170.284518997505, 'total_ms': 2254.7396090012626}

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
- Answer preview: Khi tổng nợ phải trả vượt quá ba lần vốn chủ sở hữu, đơn vị vận hành có thể tiếp tục triển khai dự án sau khi thực hiện các bước sau theo quy định tại [S1]:

*   Đánh giá tình hình tài chính của dự án.
*   Xây dựng phương án vay, trả nợ khả thi.
*   Báo cáo Cơ quan đại diện chủ sở hữu để giám sát việc sử dụng vốn và theo dõi nghĩa vụ trả nợ cho đến khi hoàn thành nghĩa vụ hoặc khi hệ số nợ phải tr
- Citations / expected-source match: ['d5c99d40-c7d1-4c2d-8990-45fccf92c3db'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 47.11301600036677, 'context_ms': 21.117358999617863, 'ttft_ms': 584.0735330020834, 'generation_ms': 2570.835124999576, 'total_ms': 2644.905285000277}

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
- Answer preview: Dựa trên bằng chứng được cung cấp:

*   **Mục đích sử dụng:** Sau khi hoàn thành nghĩa vụ tài chính và trích lập đầy đủ các quỹ theo quy định của pháp luật, phần lợi nhuận sau thuế còn lại được sử dụng để **bổ sung vốn điều lệ**, **đầu tư** và **triển khai các dự án phục vụ hoạt động điều độ hệ thống điện và điều hành giao dịch thị trường điện** theo danh mục được quy định tại Điều 5 Nghị định này
- Citations / expected-source match: ['4e2d6ec4-55a0-4467-a200-e221d7e5e0ac'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 43.50115499983076, 'context_ms': 13.928362001024652, 'ttft_ms': 609.9525909994554, 'generation_ms': 3063.1322169974737, 'total_ms': 3125.2012039985857}

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
- Answer preview: Dựa trên bằng chứng được cung cấp, Nhà nước có thể bổ sung vốn điều lệ cho đơn vị vận hành bằng đất và tài sản gắn liền với đất.

Cụ thể, theo quy định tại **Điều 8** của Nghị định số 135/2026/NĐ-CP [S1], Đơn vị vận hành hệ thống điện và thị trường điện được Nhà nước xem xét ưu tiên bố trí vốn để bổ sung vốn điều lệ thông qua hình thức:
*   Giao đất;
*   Các tài sản khác gắn liền với đất.

Việc nà
- Citations / expected-source match: ['aa94940b-7ed8-48e2-a634-5423a3aaef8e'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 42.05708500012406, 'context_ms': 18.906574001448462, 'ttft_ms': 597.4643980007386, 'generation_ms': 2929.5766799987177, 'total_ms': 2996.1634009996487}

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
- Block 6: COMPLETED_WITH_WARNINGS; citation validation=MISSING_CITATIONS
- Answer preview: Theo bằng chứng được cung cấp, mức thuê chuyên gia tư vấn trong nước tối đa là **1,5 lần** so với mức lương chuyên gia theo quy định của Nhà nước.

Thông tin này dựa trên nội dung tại [Evidence S1]: "Đơn vị vận hành hệ thống điện và thị trường điện được thuê chuyên gia tư vấn trong nước theo thỏa thuận, tuy nhiên không vượt quá 1,5 lần so với mức lương chuyên gia theo quy định của Nhà nước."
- Citations / expected-source match: [] / False
- Failure attribution: GENERATION_MISSING_CITATION
- Timings ms: {'retrieval_ms': 44.46915900189197, 'context_ms': 12.317595999775222, 'ttft_ms': 585.3517830000783, 'generation_ms': 2168.7898480013246, 'total_ms': 2231.213684000977}

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
- Answer preview: Theo bằng chứng được cung cấp, thu nhập tăng thêm cho người lao động trực tiếp thực hiện công tác điều độ hệ thống điện quốc gia và điều hành giao dịch thị trường điện được quy định như sau:

*   **Tỷ lệ tính:** Thu nhập tăng thêm được tính theo tỷ lệ **30% mức lương theo hệ số hiện hưởng** (không bao gồm phụ cấp) [S1].
*   **Thời điểm trả:** Khoản thu nhập này được trả **cùng với kỳ lương hằng th
- Citations / expected-source match: ['525ff655-b131-4375-8ead-0740eaa65957'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 36.95606699693599, 'context_ms': 18.7728339988098, 'ttft_ms': 602.9072999990603, 'generation_ms': 2373.277725997468, 'total_ms': 2433.4812670022075}

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
- Answer preview: Dựa trên bằng chứng được cung cấp, thông tin trả lời như sau:

*   **Thời gian được hưởng:** Người lao động trực tiếp thực hiện công tác điều độ hệ thống điện quốc gia và điều hành giao dịch thị trường điện được chi trả chế độ bảo hiểm hưu trí bổ sung trong **suốt quá trình công tác tại Đơn vị vận hành hệ thống điện và thị trường điện** [S1].
*   **Ai quyết định mức đóng:** **Đơn vị vận hành hệ th
- Citations / expected-source match: ['e3e6bd37-81aa-470c-bbc1-4e596ce51b81'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 39.67213199939579, 'context_ms': 15.904723997664405, 'ttft_ms': 617.6422179996734, 'generation_ms': 2809.213209999143, 'total_ms': 2871.590048998769}

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
- Answer preview: Theo bằng chứng được cung cấp, một trong những điều kiện để người lao động được xem xét miễn hoặc giảm nhẹ trách nhiệm là phải thực hiện đúng các trách nhiệm sau:

*   Thực hiện đúng thẩm quyền, trình tự, thủ tục;
*   Bảo đảm khách quan, minh bạch, không vụ lợi trong quá trình thực hiện nhiệm vụ.

Thông tin này được nêu tại [S1] và chi tiết hóa ở mục b) trong [S2].
- Citations / expected-source match: ['32b30c2b-9ac9-46f9-9c70-60e869d4c820', '956cafca-c7e0-4b2d-b9a9-23365a8a9af9'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 45.38405999846873, 'context_ms': 13.18109899875708, 'ttft_ms': 616.1582320019079, 'generation_ms': 2172.12581000058, 'total_ms': 2235.8206859971688}

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
- Block 6: COMPLETED; citation validation=PASS
- Answer preview: Dựa trên bằng chứng được cung cấp, **Chính phủ** là cơ quan phê duyệt danh mục chi tiết các cơ sở hạ tầng, hệ thống thiết yếu do Đơn vị vận hành trình.

Căn cứ:
*   **[S1]**: Quy định tại Điều 2 của Nghị định số 135/2026/NĐ-CP nêu rõ: "Phê duyệt Danh mục chi tiết các cơ sở hạ tầng, hệ thống thiết yếu quy định tại Điều 5 Nghị định này do Đơn vị vận hành hệ thống điện và thị trường điện trình để phụ
- Citations / expected-source match: ['6c815bcf-52d2-44ca-a974-f7dd82d82eef', '9ab66b53-663f-4642-9190-d80a6f61997d'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 45.94155900122132, 'context_ms': 18.84338599847979, 'ttft_ms': 579.5146390009904, 'generation_ms': 4575.519000001805, 'total_ms': 4645.1129380002385}

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
- Answer preview: Dựa trên bằng chứng được cung cấp, các Ủy ban nhân dân Thành phố xem xét giao hoặc cho thuê đất không đấu giá để xây dựng trụ sở độc lập là:

*   Thành phố Hà Nội
*   Thành phố Hồ Chí Minh
*   Thành phố Đà Nẵng

Thông tin này được nêu trong Điều 10 của Nghị định số 135/2026/NĐ-CP [S1].
- Citations / expected-source match: ['5296ee36-1e31-42ef-a152-7850d13f15ba'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 39.22209600204951, 'context_ms': 40.118131997587625, 'ttft_ms': 616.8018909993407, 'generation_ms': 2057.1337639994454, 'total_ms': 2141.7738100026327}

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
- Answer preview: Theo bằng chứng được cung cấp, hằng năm, đơn vị vận hành phải báo cáo Bộ Công Thương về triển khai chính sách ưu đãi trước ngày **15 tháng 12** của năm đó.

Căn cứ: [S1]
- Citations / expected-source match: ['642f394d-0dbb-4e95-9ef7-a676e1209d5f'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 44.373327000357676, 'context_ms': 15.823036002984736, 'ttft_ms': 592.0322849997319, 'generation_ms': 1397.9410350002581, 'total_ms': 1463.0091859980894}

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
- Answer preview: Nghị định 135/2026/NĐ-CP có hiệu lực thi hành kể từ ngày **25 tháng 5 năm 2026** [S1].
- Citations / expected-source match: ['a2938526-154c-46fa-812c-ca4be5e42fc5'] / True
- Failure attribution: PASS
- Timings ms: {'retrieval_ms': 32.44299099969794, 'context_ms': 16.14504800090799, 'ttft_ms': 602.2786569992604, 'generation_ms': 1280.9512809981243, 'total_ms': 1333.9956019990495}

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
- Block 6: COMPLETED; citation validation=PASS
- Answer preview: Bằng chứng được cung cấp không đủ để trả lời câu hỏi về mức thuế suất thuế thu nhập doanh nghiệp của NSMO trong Nghị định 135/2026/NĐ-CP.

Các bằng chứng chỉ đề cập đến các nội dung như:
*   Hiệu lực thi hành của Nghị định [S2].
*   Đối tượng áp dụng [S3].
*   Định nghĩa về Đơn vị vận hành hệ thống điện và thị trường điện (NSMO) [S7].
*   Các nguồn vốn đầu tư và cơ chế huy động vốn (vốn chủ sở hữu
- Citations / expected-source match: ['a2938526-154c-46fa-812c-ca4be5e42fc5', '1bcf57c2-823e-448d-b228-638094100edb', '2851c158-aff0-44c1-9526-df907299d251', '00428e4c-508d-4c2f-98b6-e6b2617f98ee', '53a2dd91-1e8f-4071-a904-ff1f83cf76f1', 'd5227ce1-cff9-492b-b542-5022be73931d', 'abdf4475-fa62-47bd-83a7-36aec6df506a', '76cce61d-99aa-4e26-8cf9-74ed41353463'] / None
- Failure attribution: UNSUPPORTED_ANSWER
- Timings ms: {'retrieval_ms': 61.039651998726185, 'context_ms': 28.756027997587807, 'ttft_ms': 578.1808399988222, 'generation_ms': 4021.900382998865, 'total_ms': 4120.209234999493}

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
- Block 6: COMPLETED_WITH_WARNINGS; citation validation=MISSING_CITATIONS
- Answer preview: Bằng chứng được cung cấp không đủ để trả lời câu hỏi về mức phạt hành chính đối với NSMO khi nộp báo cáo trễ. Các bằng chứng chỉ nêu rõ các quy định về cơ chế, chính sách ưu đãi cho đơn vị điều độ hệ thống điện quốc gia và đơn vị điều hành giao dịch thị trường điện, cũng như trách nhiệm báo cáo của Đơn vị vận hành hệ thống điện và thị trường điện, nhưng không đề cập đến mức phạt cụ thể.
- Citations / expected-source match: [] / None
- Failure attribution: UNSUPPORTED_ANSWER
- Timings ms: {'retrieval_ms': 40.36157200243906, 'context_ms': 15.898048000963172, 'ttft_ms': 617.810144998657, 'generation_ms': 2162.359836998803, 'total_ms': 2224.246341000253}

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
- Block 6: COMPLETED_WITH_WARNINGS; citation validation=MISSING_CITATIONS
- Answer preview: Bằng chứng được cung cấp không đủ để trả lời câu hỏi về giá bán lẻ điện sinh hoạt bậc 3 hiện nay. Các bằng chứng chỉ đề cập đến cơ chế, chính sách ưu đãi cho đơn vị điều độ hệ thống điện quốc gia và đơn vị điều hành giao dịch thị trường điện, không nêu cụ thể mức giá điện sinh hoạt.
- Citations / expected-source match: [] / None
- Failure attribution: UNSUPPORTED_ANSWER
- Timings ms: {'retrieval_ms': 40.86250899854349, 'context_ms': 20.7838830028777, 'ttft_ms': 606.02390799977, 'generation_ms': 1747.8235570015386, 'total_ms': 1814.3081829985022}

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
- Block 6: COMPLETED_WITH_WARNINGS; citation validation=MISSING_CITATIONS
- Answer preview: Bằng chứng được cung cấp không đủ để trả lời câu hỏi về thời gian nghỉ thai sản của người lao động nữ tại NSMO. Các tài liệu trong bằng chứng chỉ đề cập đến Nghị định số 135/2026/NĐ-CP liên quan đến cơ chế, chính sách ưu đãi cho đơn vị điều độ hệ thống điện quốc gia và không nêu cụ thể quy định về thời gian nghỉ thai sản.
- Citations / expected-source match: [] / None
- Failure attribution: UNSUPPORTED_ANSWER
- Timings ms: {'retrieval_ms': 36.02975600006175, 'context_ms': 10.652433000359451, 'ttft_ms': 592.9875109977729, 'generation_ms': 2021.8804869982705, 'total_ms': 2072.4542620009743}

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
- Block 6: COMPLETED_WITH_WARNINGS; citation validation=MISSING_CITATIONS
- Answer preview: Bằng chứng được cung cấp không đủ để trả lời câu hỏi về danh mục tài liệu trong hồ sơ xin giấy phép cho dự án điện gió ngoài khơi. Các bằng chứng chỉ nêu quy định về cơ chế, chính sách ưu đãi và ưu tiên cho đơn vị điều độ hệ thống điện quốc gia mà không liệt kê các tài liệu cụ thể cần có trong hồ sơ xin giấy phép cho dự án điện gió ngoài khơi.
- Citations / expected-source match: [] / None
- Failure attribution: UNSUPPORTED_ANSWER
- Timings ms: {'retrieval_ms': 35.95195100206183, 'context_ms': 19.784296997386264, 'ttft_ms': 586.7116619992885, 'generation_ms': 1970.400657999562, 'total_ms': 2031.3421940008993}

## Metric semantics and limitations

An acceptable evidence solution is found only when every chunk in at least one acceptable set occurs within K; its rank is the lowest possible maximum member rank. MRR uses that solution rank. Context retention uses the same complete-set rule. Expected-source citation match is separate from structural citation validity and also requires a complete acceptable set. No LLM-as-judge or semantic entailment claim is made.

The indexed evaluation corpus contains one substantive legal document. Dataset breadth and all aggregate estimates are therefore limited and require human review before any production gate is approved.
