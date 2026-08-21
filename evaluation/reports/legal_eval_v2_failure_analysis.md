# Legal Evaluation V2 Failure Analysis

Deterministic attribution uses frozen document/chunk ground truth. It does not use an LLM as judge.

Failures: 10 of 65 cases.

## FALSE_ABSTENTION (2)

### v2_civil_scope

- Question: Văn bản hợp nhất 10/2026/VBHN-NĐ-BNV quy định phạm vi nào?
- Expected documents: `['ed9f3e56-f3cd-41f6-9ed9-8b70e7f44c25']`
- Expected evidence: `[['7239888d-6b34-417a-bb1d-4da08ebb5b67']]`
- Retrieval complete/partial/recall: True / False / 1.0
- Dense complete rank: 1
- Lexical complete rank / mode: None / NO_MATCH
- Required chunk ranks: `[{'chunk_id': '7239888d-6b34-417a-bb1d-4da08ebb5b67', 'dense_rank': 1, 'lexical_rank': None, 'final_rank': 1}]`
- Selected chunks: `['7239888d-6b34-417a-bb1d-4da08ebb5b67', '7ad5a22b-089a-4afe-85c4-77be8f5a98d4', '0e4c09e1-e442-48f4-a386-b3ef04dec969', 'c02689a4-1596-45c9-86d9-d2f48e8247a0', '9406cd83-efed-4c66-845b-f008e2f16d56', 'e02400d2-80f5-404e-9337-22a787e192dd', '34f2e2e3-b5ec-48cb-97c8-c48a68b1ba91', '4fe6d518-19e8-479b-b3a7-45d0ac23707b', '631d3b99-b80c-40d6-b08b-6e66758bb626', '44522c41-0190-4c0c-bce6-80efab7104b1']`
- Generation: INSUFFICIENT_EVIDENCE; citation validation: PASS
- Cited chunks: `[]`

### v2_civil_effect_and_repeal

- Question: Nghị định 170/2025/NĐ-CP có hiệu lực từ ngày nào và Nghị định 138/2020/NĐ-CP có bị hết hiệu lực không?
- Expected documents: `['ed9f3e56-f3cd-41f6-9ed9-8b70e7f44c25']`
- Expected evidence: `[['fbb59a42-1217-47d1-85c9-41c440381bab', 'c694da84-e725-4d60-95fd-db06adf27884']]`
- Retrieval complete/partial/recall: True / False / 1.0
- Dense complete rank: 5
- Lexical complete rank / mode: None / NO_MATCH
- Required chunk ranks: `[{'chunk_id': 'fbb59a42-1217-47d1-85c9-41c440381bab', 'dense_rank': 1, 'lexical_rank': None, 'final_rank': 1}, {'chunk_id': 'c694da84-e725-4d60-95fd-db06adf27884', 'dense_rank': 5, 'lexical_rank': None, 'final_rank': 5}]`
- Selected chunks: `['fbb59a42-1217-47d1-85c9-41c440381bab', '7239888d-6b34-417a-bb1d-4da08ebb5b67', 'd70d0769-76c6-4c6d-ac4c-b40ea5b7d3ef', '5cdcbb2d-9f21-4ee0-a3b9-4b3680ee75bc', 'c694da84-e725-4d60-95fd-db06adf27884', '70100659-7c0f-4617-ad9f-7ce2a3b44f2e', '2f06507a-fe73-40e8-a696-d26be29d691d', 'caa68e8c-4b5b-4f87-b702-8c2d54d1ffe2', '7d00a0c1-7c45-447a-951e-285cf78edfd1', '34f2e2e3-b5ec-48cb-97c8-c48a68b1ba91']`
- Generation: INSUFFICIENT_EVIDENCE; citation validation: PASS
- Cited chunks: `[]`


## PARTIAL_MULTI_EVIDENCE_RETRIEVAL (3)

### v2_social_practice_content

- Question: Nội dung thực hành công tác xã hội bao gồm những nhóm năng lực và kỹ năng nào?
- Expected documents: `['3fb22b9b-ed46-4e04-97e2-b8c854f8252b']`
- Expected evidence: `[['77d1986c-82a4-4ef3-a215-08e1c2250d9d', 'bb5ff3eb-1831-4df5-a40f-0b8cfb4444bf', 'e044e3d1-b910-4d49-ab4e-10b049acc42a', 'aebafad2-e8a0-49e6-82e0-2cd27270e54d']]`
- Retrieval complete/partial/recall: False / True / 0.5
- Dense complete rank: None
- Lexical complete rank / mode: None / NO_MATCH
- Required chunk ranks: `[{'chunk_id': '77d1986c-82a4-4ef3-a215-08e1c2250d9d', 'dense_rank': None, 'lexical_rank': None, 'final_rank': None}, {'chunk_id': 'bb5ff3eb-1831-4df5-a40f-0b8cfb4444bf', 'dense_rank': 20, 'lexical_rank': None, 'final_rank': None}, {'chunk_id': 'e044e3d1-b910-4d49-ab4e-10b049acc42a', 'dense_rank': 9, 'lexical_rank': None, 'final_rank': 9}, {'chunk_id': 'aebafad2-e8a0-49e6-82e0-2cd27270e54d', 'dense_rank': 1, 'lexical_rank': None, 'final_rank': 1}]`
- Selected chunks: `['aebafad2-e8a0-49e6-82e0-2cd27270e54d', 'aa4b26d2-0a3a-4b57-82fd-76531d8d9791', 'cf38602e-3071-4e35-b4f5-532752cf0b86', '0b2b4b29-e108-47c8-8bc1-3a774fa455da', 'fac9f444-c203-4ef7-aa90-acdba56a486d', 'c1b373eb-3a7e-423b-bd68-ffd339ff9af2', '4d0db85b-6496-47f8-a336-af7cec513cef', '98d4b7c3-ae85-4422-8abd-d18fb2962fc2', 'e044e3d1-b910-4d49-ab4e-10b049acc42a', '5face032-faa3-4b38-a5c8-35072a34adda']`
- Generation: INSUFFICIENT_EVIDENCE; citation validation: PASS
- Cited chunks: `[]`

### v2_social_effective_transition

- Question: Thông tư về công tác xã hội có hiệu lực ngày nào và người đã có giấy xác nhận thực hành có phải thực hành lại không?
- Expected documents: `['3fb22b9b-ed46-4e04-97e2-b8c854f8252b']`
- Expected evidence: `[['70100659-7c0f-4617-ad9f-7ce2a3b44f2e', 'ff57c879-4c67-4a7b-b550-6c2b373955be']]`
- Retrieval complete/partial/recall: False / True / 0.5
- Dense complete rank: None
- Lexical complete rank / mode: None / NO_MATCH
- Required chunk ranks: `[{'chunk_id': '70100659-7c0f-4617-ad9f-7ce2a3b44f2e', 'dense_rank': None, 'lexical_rank': None, 'final_rank': None}, {'chunk_id': 'ff57c879-4c67-4a7b-b550-6c2b373955be', 'dense_rank': 3, 'lexical_rank': None, 'final_rank': 3}]`
- Selected chunks: `['425f59be-f2fa-49f4-acb7-461cb0769b50', 'fb2b69bb-edab-45b0-a56d-7b6248445757', 'ff57c879-4c67-4a7b-b550-6c2b373955be', 'dd748672-d3b1-45e5-a840-e61615901646', '4aec0cc1-cf74-4fbc-b88c-5f628dd8f4d0', 'cf38602e-3071-4e35-b4f5-532752cf0b86', '74246516-06c7-4adb-a212-656c063dde89', '3e972463-1919-46c9-94ce-751fc9689188', '1f76cce4-ecaa-483f-aa1c-731b146fae51', '5face032-faa3-4b38-a5c8-35072a34adda']`
- Generation: INSUFFICIENT_EVIDENCE; citation validation: PASS
- Cited chunks: `[]`

### v2_bank_scope_ratios

- Question: Thông tư 40/2026/TT-NHNN điều chỉnh năm nhóm hạn chế, giới hạn và tỷ lệ an toàn chính nào?
- Expected documents: `['78e54e57-fc2e-47b2-919c-c7120776226d']`
- Expected evidence: `[['48109bc6-e5cb-4c25-89be-b6ed2d85e066', '283fc8f6-8d90-4a6b-8a8c-d7f31d8935d2', '5faec617-7237-4dc8-a01a-bc4ade33ac31', '5c3fd83c-0fb0-4cd7-9d52-b346c203c28a', '30e14c4c-d8fd-4d68-9382-4d96bef43392']]`
- Retrieval complete/partial/recall: False / True / 0.2
- Dense complete rank: None
- Lexical complete rank / mode: None / NO_MATCH
- Required chunk ranks: `[{'chunk_id': '48109bc6-e5cb-4c25-89be-b6ed2d85e066', 'dense_rank': 5, 'lexical_rank': None, 'final_rank': 5}, {'chunk_id': '283fc8f6-8d90-4a6b-8a8c-d7f31d8935d2', 'dense_rank': 23, 'lexical_rank': None, 'final_rank': None}, {'chunk_id': '5faec617-7237-4dc8-a01a-bc4ade33ac31', 'dense_rank': 34, 'lexical_rank': None, 'final_rank': None}, {'chunk_id': '5c3fd83c-0fb0-4cd7-9d52-b346c203c28a', 'dense_rank': 21, 'lexical_rank': None, 'final_rank': None}, {'chunk_id': '30e14c4c-d8fd-4d68-9382-4d96bef43392', 'dense_rank': None, 'lexical_rank': None, 'final_rank': None}]`
- Selected chunks: `['7ad5a22b-089a-4afe-85c4-77be8f5a98d4', '13566529-a241-4568-a651-b95a14bb0f9f', '4e7a93e5-a04d-4d74-b3c1-0a7c5ae3f354', 'c4f0d74c-a06b-4e50-9303-c148f2899272', '48109bc6-e5cb-4c25-89be-b6ed2d85e066', '46193291-fcb4-4458-8fa3-85dfbb321e59', '5965373c-7e11-4fe7-b179-42365b4eedc9', '39bf860e-d459-48a5-ac28-17380c5cf9c5', '6919c16f-5507-48c0-9fd6-f893a7a125ff', 'e268e6d3-9f77-415a-b27e-7518a20a9254']`
- Generation: INSUFFICIENT_EVIDENCE; citation validation: PASS
- Cited chunks: `[]`


## RETRIEVAL_MISS (4)

### v2_social_scope

- Question: Thông tư về thực hành công tác xã hội quy định chi tiết ba nhóm nội dung nào của Nghị định 110/2024/NĐ-CP?
- Expected documents: `['3fb22b9b-ed46-4e04-97e2-b8c854f8252b']`
- Expected evidence: `[['36343b2e-1725-4697-877b-9e33526db4d2', 'db824433-8240-447b-89a8-0d20a1a88349', '69bf65cc-80b1-41d1-86a3-8714b13f2924']]`
- Retrieval complete/partial/recall: False / False / 0.0
- Dense complete rank: None
- Lexical complete rank / mode: None / NO_MATCH
- Required chunk ranks: `[{'chunk_id': '36343b2e-1725-4697-877b-9e33526db4d2', 'dense_rank': None, 'lexical_rank': None, 'final_rank': None}, {'chunk_id': 'db824433-8240-447b-89a8-0d20a1a88349', 'dense_rank': 36, 'lexical_rank': None, 'final_rank': None}, {'chunk_id': '69bf65cc-80b1-41d1-86a3-8714b13f2924', 'dense_rank': 38, 'lexical_rank': None, 'final_rank': None}]`
- Selected chunks: `['63641a91-76dd-4007-add6-9a22234ce020', '5face032-faa3-4b38-a5c8-35072a34adda', '783aac1c-9c44-4095-a63a-6adc9ba0e209', 'fac9f444-c203-4ef7-aa90-acdba56a486d', '425f59be-f2fa-49f4-acb7-461cb0769b50', '461bda71-d08d-45e4-afee-17809d626cc0', '4aec0cc1-cf74-4fbc-b88c-5f628dd8f4d0', '644205fc-d6cc-4833-9638-b783d1c1e00b', 'fb2b69bb-edab-45b0-a56d-7b6248445757', 'aebafad2-e8a0-49e6-82e0-2cd27270e54d']`
- Generation: INSUFFICIENT_EVIDENCE; citation validation: PASS
- Cited chunks: `[]`

### v2_social_applicable_groups

- Question: Bốn nhóm đối tượng nào thuộc phạm vi áp dụng của Thông tư về thực hành và cập nhật kiến thức công tác xã hội?
- Expected documents: `['3fb22b9b-ed46-4e04-97e2-b8c854f8252b']`
- Expected evidence: `[['23d10632-6b5f-4e82-a9eb-a91f3f1fa878', 'f160106c-f98a-4935-b076-16389967e868', 'd3421519-8b8b-44a9-b4b1-25a0c47b8515', 'b5d4ed5c-0914-4e73-97af-d655047006bb']]`
- Retrieval complete/partial/recall: False / False / 0.0
- Dense complete rank: None
- Lexical complete rank / mode: None / NO_MATCH
- Required chunk ranks: `[{'chunk_id': '23d10632-6b5f-4e82-a9eb-a91f3f1fa878', 'dense_rank': None, 'lexical_rank': None, 'final_rank': None}, {'chunk_id': 'f160106c-f98a-4935-b076-16389967e868', 'dense_rank': 38, 'lexical_rank': None, 'final_rank': None}, {'chunk_id': 'd3421519-8b8b-44a9-b4b1-25a0c47b8515', 'dense_rank': 31, 'lexical_rank': None, 'final_rank': None}, {'chunk_id': 'b5d4ed5c-0914-4e73-97af-d655047006bb', 'dense_rank': None, 'lexical_rank': None, 'final_rank': None}]`
- Selected chunks: `['30096d45-61c8-46b9-beb2-ef9b189f37ef', '4aec0cc1-cf74-4fbc-b88c-5f628dd8f4d0', 'aaea503a-39f3-43b5-985e-318a9dd5ee7c', 'fb2b69bb-edab-45b0-a56d-7b6248445757', '461bda71-d08d-45e4-afee-17809d626cc0', '616c1e16-25dc-479c-b230-467b1cbef660', '1f76cce4-ecaa-483f-aa1c-731b146fae51', 'ee9f8c97-ff12-463a-ba91-e2f97c82ee76', '85df846b-61a4-43ca-9bb2-93ec66b6244e', '6b3831bc-e211-4587-976c-42d35814c2ea']`
- Generation: INSUFFICIENT_EVIDENCE; citation validation: PASS
- Cited chunks: `[]`

### v2_social_course_modes

- Question: Khóa bồi dưỡng ngắn hạn về công tác xã hội có thể tổ chức theo những hình thức nào?
- Expected documents: `['3fb22b9b-ed46-4e04-97e2-b8c854f8252b']`
- Expected evidence: `[['d390e530-9beb-41d8-90a3-be46d512a08b']]`
- Retrieval complete/partial/recall: False / False / 0.0
- Dense complete rank: None
- Lexical complete rank / mode: None / NO_MATCH
- Required chunk ranks: `[{'chunk_id': 'd390e530-9beb-41d8-90a3-be46d512a08b', 'dense_rank': None, 'lexical_rank': None, 'final_rank': None}]`
- Selected chunks: `['ee9f8c97-ff12-463a-ba91-e2f97c82ee76', 'cc773a06-52ce-481f-bb33-a12943a7e006', 'f1761f38-ec3b-40be-a100-b140a29ab0b9', '2d98dad7-84db-418d-a572-f9506442892b', '616c1e16-25dc-479c-b230-467b1cbef660', '33b78d6f-6bc1-4d25-82cb-2a2cff00c7ef', '85df846b-61a4-43ca-9bb2-93ec66b6244e', '1f76cce4-ecaa-483f-aa1c-731b146fae51', 'fb2b69bb-edab-45b0-a56d-7b6248445757', '566cc2e6-d38d-433a-b915-b40743072d14']`
- Generation: INSUFFICIENT_EVIDENCE; citation validation: PASS
- Cited chunks: `[]`

### v2_bank_loan_limit_exceptions

- Question: Hai trường hợp nào không áp dụng giới hạn cho vay tại điểm b khoản 1 Điều 12?
- Expected documents: `['78e54e57-fc2e-47b2-919c-c7120776226d']`
- Expected evidence: `[['022d0872-1a53-43ba-bc11-a4474db0cea9', 'e57b1bc6-2105-4404-bda1-4472cf6e2574']]`
- Retrieval complete/partial/recall: False / False / 0.0
- Dense complete rank: None
- Lexical complete rank / mode: None / NO_MATCH
- Required chunk ranks: `[{'chunk_id': '022d0872-1a53-43ba-bc11-a4474db0cea9', 'dense_rank': 18, 'lexical_rank': None, 'final_rank': None}, {'chunk_id': 'e57b1bc6-2105-4404-bda1-4472cf6e2574', 'dense_rank': None, 'lexical_rank': None, 'final_rank': None}]`
- Selected chunks: `['9c264672-b50d-453e-ac83-96c548afd31c', '4fe6d518-19e8-479b-b3a7-45d0ac23707b', 'bf524416-5ecf-4b63-9c41-e3ab6d3942ab', '5c3fd83c-0fb0-4cd7-9d52-b346c203c28a', '4b96b40c-0843-4137-a211-5707ccf4a8fa', 'e5c0d671-484a-4582-a71a-88ba13a3201a', 'e5e4e2cc-3efa-40a1-873d-8496090e8238', 'e8fa9eca-63c7-4953-a84b-6ab6852ee465', '3eb658b7-ecf8-4e7e-a04e-f709eed2e4ab', '9f866b06-cf8b-46fe-a3c2-7f9e23ffc3d7']`
- Generation: INSUFFICIENT_EVIDENCE; citation validation: PASS
- Cited chunks: `[]`


## WRONG_DOCUMENT (1)

### v2_bank_board_loan_threshold

- Question: Khoản cho vay đối với người thẩm định hoặc người xét duyệt phải được Hội đồng quản trị thông qua từ mức giá trị nào?
- Expected documents: `['78e54e57-fc2e-47b2-919c-c7120776226d']`
- Expected evidence: `[['5e06c2be-ef51-475a-8190-5ab9e6e1f404']]`
- Retrieval complete/partial/recall: False / False / 0.0
- Dense complete rank: None
- Lexical complete rank / mode: None / NO_MATCH
- Required chunk ranks: `[{'chunk_id': '5e06c2be-ef51-475a-8190-5ab9e6e1f404', 'dense_rank': None, 'lexical_rank': None, 'final_rank': None}]`
- Selected chunks: `['566cc2e6-d38d-433a-b915-b40743072d14', 'e3e507f6-cba8-400b-ac8c-476e357bbd7f', 'ccd34da4-dcca-409b-a7ad-7d7b8500436c', '2f06e025-945a-415b-be8f-003f21ae698d', 'ec3805c0-70d0-4a24-b3d6-3a9584c537b7', '458d58d2-9444-48c0-ab4f-e8c0cb560c7d', 'e5ee0d41-20fe-4e3b-87b7-a829ad955cea', 'a680dabb-9e28-4cd5-80e6-9527d030f10f', 'c468402b-22bd-40eb-b980-abdbfbcd8166', '2f2925d6-3fbf-4737-8280-e139dfef2fa8']`
- Generation: INSUFFICIENT_EVIDENCE; citation validation: PASS
- Cited chunks: `[]`

## Difficult PASS control

- Case: `v2_social_research_credit`
- Expected-evidence final rank: 9
- Diagnosis: PASS
