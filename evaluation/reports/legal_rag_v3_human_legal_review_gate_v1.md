# Legal-RAG-V3 Human Legal Review Gate V1

Status: **READY FOR HUMAN REVIEW — LEGAL DECISIONS UNFILLED**

This artifact uses no LLM judge and supplies no final legal judgment. The queue is copied from the existing production-validation report; evaluation was not rerun and frozen labels were not changed.

## Integrity and queue

- evaluation_v1: `afb5b2692aefe9e682a1483ce3ff86c885d0527de3a20d7a709fc9274d9f0245` — MATCH
- evaluation_v2: `ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842` — MATCH
- legal_rag_v2: `a41efc38ab53ad84550de27d913b13b4b6742aabe7a55a67f92685d132f303ee` — MATCH
- legal_rag_v3: `35b0abd69608ef574ac7bbf5c314eadb6ef9decd0dda3dd60e0a170aad243ebf` — MATCH

Authoritative queue: **8 cases**; unexpected source 3, qualified answer 1, V3 gains 3, multi-evidence 3, unresolved abstentions 3.

## Reviewer instructions

Determine whether each actual citation supports the proposition, whether expected and actual sources are legally equivalent/supplementary/conflicting, whether the answer introduces unsupported propositions, and whether qualification and multi-source synthesis are legally justified. Structural validity and expected-source matching are engineering signals only.

## v2_bank_actual_capital_formula — SEMANTIC_PARAPHRASE

**Review reasons:** `["V3_UNRESOLVED_FALSE_ABSTENTION"]`

**Question:** Giá trị thực của vốn điều lệ được tính từ vốn điều lệ, lợi nhuận và lỗ lũy kế như thế nào?

**Expected behavior/reference:** được xác định bằng vốn điều lệ cộng lợi nhuận lũy kế chưa phân phối, trừ lỗ lũy kế chưa xử lý

| Version | Status | Expected-source complete | Answer |
|---|---|---:|---|
| V2 | `INSUFFICIENT_EVIDENCE` | `False` | (abstained) |
| V3 | `INSUFFICIENT_EVIDENCE` | `False` | (abstained) |

**Engineering assessment:** retrieval expected complete `False`; context expected complete `False`; status valid `True`; citation structurally valid `True`. Legal correctness remains unfilled.

**Evidence shape:** base 10; hierarchy recovered 4; multi-evidence `False`; multi-document `False`; context tokens 2269.

### Required evidence matrix

| Chunk | Source ID | Selected | Cited | Origin | Legal unit |
|---|---|---:|---:|---|---|
| `aae40b26-6c1a-4ed3-9a44-cfd13fdd545d` | `not selected` | False | False | `NOT_IN_FINAL_CONTEXT_CANDIDATES` | Điều 6, Khoản 3, Điểm — |

### Expected source text

**Acceptable solution 1**

#### Expected: `aae40b26-6c1a-4ed3-9a44-cfd13fdd545d`

- Document: `78e54e57-fc2e-47b2-919c-c7120776226d` — Nghị định 40/2026/TT-NHNN; `Thông tư 40.2026.TT-NHNN.pdf`
- Title/authority/date: not available; Chính phủ; 2026-08-10
- Legal unit: Điều 6, Khoản 3, tr. 5–5; legal_unit_id `97898f19-cbc2-472c-81c7-48664ac7447a`
- Origin: `NOT_IN_FINAL_CONTEXT_CANDIDATES`; selected: `False`; retrieval rank: `None`

> 3. Cách tính giá trị thực của vốn điều lệ:
> Giá trị thực của vốn điều lệ được xác định bằng vốn điều lệ cộng lợi nhuận
> lũy kế chưa phân phối, trừ lỗ lũy kế chưa xử lý được phản ánh trên sổ sách kế
> toán.

### Actual cited source text

No V3 source was cited because the model abstained.

### Unresolved abstention

- Engineering classification: `EXPECTED_EVIDENCE_NOT_IN_CONTEXT`
- Out of scope for V3 activation fix: `False`
- Future target: `RETRIEVAL_OR_CONTEXT_DIAGNOSIS`

### Selected context inventory

| Source | Chunk | Origin | Rank | Legal unit | Text preview |
|---|---|---|---:|---|---|
| `S1` | `02f35d2d-3776-4561-b629-840d8e7b69bc` | `RETRIEVAL` | 1 | Điều 7, Khoản 5, tr. 5–5 | 5. Trong vòng 03 năm kể từ ngày Nghị định này có hiệu lực, Đơn vị vận hành hệ thống điện và thị trường điện được bổ sung và duy trì vốn điều lệ tối thiểu là 3.000 tỷ đồng để bảo đảm năng lực tài chính trong việc thu xếp… |
| `S2` | `c0bfae75-c2b2-45f7-86fd-4ccd8ba79a2a` | `RETRIEVAL` | 2 | Điều 7, Khoản 5, tr. 5–5 | 5. Trong vòng 03 năm kể từ ngày Nghị định này có hiệu lực, Đơn vị vận hành hệ thống điện và thị trường điện được bổ sung và duy trì vốn điều lệ tối thiểu là 3.000 tỷ đồng để bảo đảm năng lực tài chính trong việc thu xếp… |
| `S3` | `74d3ce60-a97f-46ce-9f55-7e1824f31a68` | `RETRIEVAL` | 3 | Điều 7, Khoản 5, tr. 5–5 | 5. Trong vòng 03 năm kể từ ngày Nghị định này có hiệu lực, Đơn vị vận hành hệ thống điện và thị trường điện được bổ sung và duy trì vốn điều lệ tối thiểu là 3.000 tỷ đồng để bảo đảm năng lực tài chính trong việc thu xếp… |
| `S4` | `237ad4a6-81fc-4524-99d9-d9a4bf822365` | `RETRIEVAL` | 4 | Điều 7, Khoản 5, tr. 5–5 | 5. Trong vòng 03 năm kể từ ngày Nghị định này có hiệu lực, Đơn vị vận hành hệ thống điện và thị trường điện được bổ sung và duy trì vốn điều lệ tối thiểu là 3.000 tỷ đồng để bảo đảm năng lực tài chính trong việc thu xếp… |
| `S5` | `d5227ce1-cff9-492b-b542-5022be73931d` | `RETRIEVAL` | 5 | Điều 7, Khoản 1, Điểm a, tr. 4–4 | a) Vốn chủ sở hữu; |
| `S6` | `9ce0df39-a325-4056-b626-5e4d5ce23148` | `RETRIEVAL` | 6 | Điều 7, Khoản 1, Điểm a, tr. 4–4 | a) Vốn chủ sở hữu; |
| `S7` | `545d22fd-5067-44e7-a796-ace682344a9c` | `RETRIEVAL` | 7 | Điều 7, Khoản 1, Điểm a, tr. 4–4 | a) Vốn chủ sở hữu; |
| `S8` | `97961e9d-dab6-428f-898c-33f8d9aa5e5e` | `RETRIEVAL` | 8 | Điều 7, Khoản 1, Điểm a, tr. 4–4 | a) Vốn chủ sở hữu; |
| `S9` | `0f048ed3-b2f5-4262-be73-3bb00c0efaf1` | `RETRIEVAL` | 9 | Điều 7, Khoản 1, Điểm a, tr. 4–4 | a) Vốn chủ sở hữu; |
| `S10` | `abdf4475-fa62-47bd-83a7-36aec6df506a` | `RETRIEVAL` | 10 | Điều 7, tr. 4–4 | Điều 7. Nguồn vốn đầu tư và cơ chế, chính sách ưu đãi huy động vốn |
| `S11` | `7ef3b873-84ef-414f-9615-b341cb94f1cc` | `HIERARCHY_CHILD` | None | Điều 7, Khoản 1, tr. 4–4 | 1. Nguồn vốn đầu tư các dự án cơ sở hạ tầng và các hệ thống thiết yếu khác bao gồm: |
| `S12` | `8b3f9a09-d190-4c38-8b2f-c5e3cc689f2f` | `HIERARCHY_CHILD` | None | Điều 7, Khoản 2, tr. 4–4 | 2. Đơn vị vận hành hệ thống điện và thị trường điện được ưu tiên tiếp nhận và khai thác các khoản viện trợ không hoàn lại không thuộc nguồn hỗ trợ phát triển chính thức của các cơ quan, tổ chức, cá nhân nước ngoài, các … |
| `S13` | `1a6b7744-8a26-4f62-8eca-207bdd065151` | `HIERARCHY_CHILD` | None | Điều 7, Khoản 3, tr. 4–4 | 3. Đơn vị vận hành hệ thống điện và thị trường điện được ưu tiên tiếp cận, sử dụng vốn ODA, vay ưu đãi nước ngoài của Chính phủ để thực hiện các dự án được cơ quan nhà nước có thẩm quyền phê duyệt theo pháp luật về đầu … |
| `S14` | `bfae2ca5-6855-4583-83db-841870e5a379` | `HIERARCHY_CHILD` | None | Điều 7, Khoản 4, tr. 4–4 | 4. Đối với các dự án đầu tư cơ sở hạ tầng và các hệ thống thiết yếu khác phục vụ công tác điều độ, vận hành hệ thống điện và điều hành giao dịch thị trường điện, trường hợp vay vốn thương mại trong nước hoặc vay vốn nướ… |

**Human judgment required:** answer support, citation acceptability, source mismatch, qualification, unsupported propositions, severity, and final decision. No field is pre-filled.

---

## v2_bank_below_80_measures — PARTIAL_SUPPORT

**Review reasons:** `["V3_ANSWERABILITY_GAIN", "QUALIFIED_PARTIAL_SUPPORT"]`

**Question:** Khi giá trị thực của vốn điều lệ xuống dưới 80% vốn pháp định, chi nhánh Ngân hàng Nhà nước có thể áp dụng những nhóm biện pháp nào?

**Expected behavior/reference:** giá trị thực của vốn điều lệ giảm xuống dưới 80% của mức vốn pháp định — One long chunk contains the measured list; answer quality still requires careful grounding.

| Version | Status | Expected-source complete | Answer |
|---|---|---:|---|
| V2 | `INSUFFICIENT_EVIDENCE` | `False` | (abstained) |
| V3 | `ANSWERABLE` | `True` | Khi giá trị thực của vốn điều lệ giảm xuống dưới 80% vốn pháp định, Ngân hàng Nhà nước chi nhánh Khu vực có thể áp dụng các biện pháp sau [S4]: Hạn chế chia lãi; Hạn chế việc mở rộng phạm vi, quy mô và địa bàn hoạt động; Hạn chế, đình chỉ, tạm đình chỉ một số nội dung hoạt động; Yêu cầu Quỹ tín dụng nhân dân tăng vốn điều lệ; Quyết định giới hạn tăng trưởng tín dụng; Áp dụng tỷ lệ an toàn chặt chẽ hơn. Ngoài ra, Ngân hàng Nhà nước chi nhánh Khu vực còn có thể yêu cầu quỹ tín dụng nhân dân thực hiện kiểm toán độc lập [S1], giám sát việc triển khai phương án xử lý [S3], yêu cầu sửa đổi biện pháp xử lý [S13] và yêu cầu duy trì các hạn chế, giới hạn chặt chẽ hơn [S12]. |

**Engineering assessment:** retrieval expected complete `True`; context expected complete `True`; status valid `True`; citation structurally valid `True`. Legal correctness remains unfilled.

**Evidence shape:** base 10; hierarchy recovered 3; multi-evidence `False`; multi-document `False`; context tokens 1399.

### Required evidence matrix

| Chunk | Source ID | Selected | Cited | Origin | Legal unit |
|---|---|---:|---:|---|---|
| `31b2230f-aa0e-47e3-86a7-2c2f3d162c97` | `S4` | True | True | `RETRIEVAL` | Điều 7, Khoản 2, Điểm d |

### Expected source text

**Acceptable solution 1**

#### Expected: `31b2230f-aa0e-47e3-86a7-2c2f3d162c97` / S4

- Document: `78e54e57-fc2e-47b2-919c-c7120776226d` — Nghị định 40/2026/TT-NHNN; `Thông tư 40.2026.TT-NHNN.pdf`
- Title/authority/date: not available; Chính phủ; 2026-08-10
- Legal unit: Điều 7, Khoản 2, Điểm d, tr. 6–6; legal_unit_id `7acf21a0-e347-42af-9b67-1bd0f1fe75da`
- Origin: `RETRIEVAL`; selected: `True`; retrieval rank: `2`

> d) Tùy theo mức độ giảm giá trị thực của vốn điều lệ so với mức vốn pháp
> định, Ngân hàng Nhà nước chi nhánh Khu vực quyết định cụ thể các biện pháp
> xử lý sau đây đối với quỹ tín dụng nhân dân:
> (i) Xem xét áp dụng các biện pháp khi giá trị thực của vốn điều lệ giảm
> xuống dưới 80% của mức vốn pháp định, bao gồm: Hạn chế chia lãi; Hạn chế việc
> mở rộng phạm vi, quy mô và địa bàn hoạt động; Hạn chế, đình chỉ, tạm đình chỉ
> một số nội dung hoạt động; Yêu cầu Quỹ tín dụng nhân dân tăng vốn điều lệ;
> Quyết định giới hạn tăng trưởng tín dụng trong những trường hợp cần thiết bảo
> đảm an toàn cho quỹ tín dụng nhân dân và hệ thống các tổ chức tín dụng; Áp dụng
> một hoặc một số tỷ lệ an toàn chặt chẽ hơn mức quy định;
> (ii) Xem xét áp dụng can thiệp sớm, kiểm soát đặc biệt, cơ cấu lại theo quy
> định của pháp luật.

### Actual cited source text

#### Actual: `31b2230f-aa0e-47e3-86a7-2c2f3d162c97` / S4

- Document: `78e54e57-fc2e-47b2-919c-c7120776226d` — Nghị định 40/2026/TT-NHNN; `Thông tư 40.2026.TT-NHNN.pdf`
- Title/authority/date: not available; Chính phủ; 2026-08-10
- Legal unit: Điều 7, Khoản 2, Điểm d, tr. 6–6; legal_unit_id `7acf21a0-e347-42af-9b67-1bd0f1fe75da`
- Origin: `RETRIEVAL`; selected: `True`; retrieval rank: `2`

> d) Tùy theo mức độ giảm giá trị thực của vốn điều lệ so với mức vốn pháp
> định, Ngân hàng Nhà nước chi nhánh Khu vực quyết định cụ thể các biện pháp
> xử lý sau đây đối với quỹ tín dụng nhân dân:
> (i) Xem xét áp dụng các biện pháp khi giá trị thực của vốn điều lệ giảm
> xuống dưới 80% của mức vốn pháp định, bao gồm: Hạn chế chia lãi; Hạn chế việc
> mở rộng phạm vi, quy mô và địa bàn hoạt động; Hạn chế, đình chỉ, tạm đình chỉ
> một số nội dung hoạt động; Yêu cầu Quỹ tín dụng nhân dân tăng vốn điều lệ;
> Quyết định giới hạn tăng trưởng tín dụng trong những trường hợp cần thiết bảo
> đảm an toàn cho quỹ tín dụng nhân dân và hệ thống các tổ chức tín dụng; Áp dụng
> một hoặc một số tỷ lệ an toàn chặt chẽ hơn mức quy định;
> (ii) Xem xét áp dụng can thiệp sớm, kiểm soát đặc biệt, cơ cấu lại theo quy
> định của pháp luật.

#### Actual: `7e83f98a-6cd0-4d86-9596-f9868aa3ac7b` / S1

- Document: `78e54e57-fc2e-47b2-919c-c7120776226d` — Nghị định 40/2026/TT-NHNN; `Thông tư 40.2026.TT-NHNN.pdf`
- Title/authority/date: not available; Chính phủ; 2026-08-10
- Legal unit: Điều 7, Khoản 2, tr. 6–6; legal_unit_id `5d755254-73ed-4361-a6ff-0e4b506d8e78`
- Origin: `RETRIEVAL`; selected: `True`; retrieval rank: `1`

> 2. Các biện pháp Ngân hàng Nhà nước chi nhánh Khu vực áp dụng để xử
> lý khi giá trị thực của vốn điều lệ của quỹ tín dụng nhân dân giảm thấp hơn mức
> vốn pháp định:

#### Actual: `b4840ba2-673c-42af-9e3f-8f3150e4e9ab` / S3

- Document: `78e54e57-fc2e-47b2-919c-c7120776226d` — Nghị định 40/2026/TT-NHNN; `Thông tư 40.2026.TT-NHNN.pdf`
- Title/authority/date: not available; Chính phủ; 2026-08-10
- Legal unit: Điều 7, Khoản 2, Điểm c, tr. 6–6; legal_unit_id `4536a5fb-ddae-45bf-a7f9-34842ccc5cc5`
- Origin: `HIERARCHY_CHILD`; selected: `True`; retrieval rank: `None`

> c) Giám sát, thanh tra, kiểm tra việc tổ chức, triển khai thực hiện các biện
> pháp tại phương án xử lý, bao gồm cả các biện pháp xử lý theo yêu cầu của Ngân
> hàng Nhà nước chi nhánh Khu vực;

#### Actual: `ab568a7d-b862-4b3b-aebc-b5d37e75b2e0` / S13

- Document: `78e54e57-fc2e-47b2-919c-c7120776226d` — Nghị định 40/2026/TT-NHNN; `Thông tư 40.2026.TT-NHNN.pdf`
- Title/authority/date: not available; Chính phủ; 2026-08-10
- Legal unit: Điều 7, Khoản 2, Điểm b, tr. 6–6; legal_unit_id `1483f814-1fea-429a-a454-b40460ff99e3`
- Origin: `RETRIEVAL`; selected: `True`; retrieval rank: `10`

> b) Yêu cầu sửa đổi, bổ sung, hoàn thiện các biện pháp xử lý của quỹ tín
> dụng nhân dân khi giá trị thực của vốn điều lệ thấp hơn mức vốn pháp định nêu
> tại phương án quy định tại khoản 1 Điều này trong trường hợp cần thiết;

#### Actual: `1a51b6cd-f9ac-4cde-9065-a8bd90e60d74` / S12

- Document: `78e54e57-fc2e-47b2-919c-c7120776226d` — Nghị định 40/2026/TT-NHNN; `Thông tư 40.2026.TT-NHNN.pdf`
- Title/authority/date: not available; Chính phủ; 2026-08-10
- Legal unit: Điều 1, Khoản 3, tr. 1–2; legal_unit_id `ae8e244b-9a37-4521-9c1f-e90322dbd557`
- Origin: `RETRIEVAL`; selected: `True`; retrieval rank: `9`

> 3. Căn cứ kết quả giám sát, thanh tra, kiểm tra đối với quỹ tín dụng nhân
> dân, trong trường hợp cần thiết để bảo đảm an toàn trong hoạt động của quỹ tín
> dụng nhân dân, tùy theo tính chất, mức độ rủi ro, Ngân hàng Nhà nước chi nhánh
> Khu vực nơi quỹ tín dụng nhân dân đặt trụ sở chính (sau đây gọi là Ngân hàng
> Nhà nước chi nhánh Khu vực) yêu cầu quỹ tín dụng nhân dân duy trì một hoặc
> một số hạn chế, giới hạn, tỷ lệ bảo đảm an toàn chặt chẽ hơn so với mức quy định
> tại Thông tư này.

### Qualified-answer focus

- Direct expected chunks cited: `["31b2230f-aa0e-47e3-86a7-2c2f3d162c97"]`
- Additional cited chunks: `["1a51b6cd-f9ac-4cde-9065-a8bd90e60d74", "7e83f98a-6cd0-4d86-9596-f9868aa3ac7b", "ab568a7d-b862-4b3b-aebc-b5d37e75b2e0", "b4840ba2-673c-42af-9e3f-8f3150e4e9ab"]`
- Review focus: Determine whether propositions citing only additional selected evidence are responsive supplementary measures or overbroad relative to the specific threshold in the question.
- Human choice: **ACCEPT QUALIFIED ANSWER / REJECT QUALIFIED ANSWER**

- `EXPECTED_EVIDENCE_PRESENT` — Khi giá trị thực của vốn điều lệ giảm xuống dưới 80% vốn pháp định, Ngân hàng Nhà nước chi nhánh Khu vực có thể áp dụng các biện pháp sau [S4]: Hạn chế chia lãi; Hạn chế việc mở rộng phạm vi, quy mô và địa bàn hoạt động; Hạn chế, đình chỉ, tạm đình chỉ một số nội dung hoạt động; Yêu cầu Quỹ tín dụng nhân dân tăng vốn điều lệ; Quyết định giới hạn tăng trưởng tín dụng; Áp dụng tỷ lệ an toàn chặt chẽ hơn.
- `ONLY_ADDITIONAL_SELECTED_EVIDENCE` — Ngoài ra, Ngân hàng Nhà nước chi nhánh Khu vực còn có thể yêu cầu quỹ tín dụng nhân dân thực hiện kiểm toán độc lập [S1], giám sát việc triển khai phương án xử lý [S3], yêu cầu sửa đổi biện pháp xử lý [S13] và yêu cầu duy trì các hạn chế, giới hạn chặt chẽ hơn [S12].

### Selected context inventory

| Source | Chunk | Origin | Rank | Legal unit | Text preview |
|---|---|---|---:|---|---|
| `S1` | `7e83f98a-6cd0-4d86-9596-f9868aa3ac7b` | `RETRIEVAL` | 1 | Điều 7, Khoản 2, tr. 6–6 | 2. Các biện pháp Ngân hàng Nhà nước chi nhánh Khu vực áp dụng để xử lý khi giá trị thực của vốn điều lệ của quỹ tín dụng nhân dân giảm thấp hơn mức vốn pháp định: |
| `S2` | `0297543e-678d-4927-b127-df8df7a82ae5` | `HIERARCHY_CHILD` | None | Điều 7, Khoản 2, Điểm a, tr. 6–6 | a) Đánh giá, kiểm tra, thanh tra hoặc yêu cầu quỹ tín dụng nhân dân thực hiện kiểm toán độc lập để xác định giá trị thực của vốn điều lệ tại phương án xử lý do quỹ tín dụng nhân dân báo cáo theo quy định tại khoản 1 Điề… |
| `S3` | `b4840ba2-673c-42af-9e3f-8f3150e4e9ab` | `HIERARCHY_CHILD` | None | Điều 7, Khoản 2, Điểm c, tr. 6–6 | c) Giám sát, thanh tra, kiểm tra việc tổ chức, triển khai thực hiện các biện pháp tại phương án xử lý, bao gồm cả các biện pháp xử lý theo yêu cầu của Ngân hàng Nhà nước chi nhánh Khu vực; |
| `S4` | `31b2230f-aa0e-47e3-86a7-2c2f3d162c97` | `RETRIEVAL` | 2 | Điều 7, Khoản 2, Điểm d, tr. 6–6 | d) Tùy theo mức độ giảm giá trị thực của vốn điều lệ so với mức vốn pháp định, Ngân hàng Nhà nước chi nhánh Khu vực quyết định cụ thể các biện pháp xử lý sau đây đối với quỹ tín dụng nhân dân: (i) Xem xét áp dụng các bi… |
| `S5` | `932b1b44-40ae-44d4-958b-05230449c7ae` | `RETRIEVAL` | 3 | Điều 7, Khoản 1, Điểm b, tr. 5–5 | b) Trong thời gian tối đa 30 ngày kể từ ngày giá trị thực của vốn điều lệ giảm thấp hơn mức vốn pháp định, phải có văn bản báo cáo kèm phương án xử lý và cam kết thực hiện phương án xử lý gửi trực tiếp hoặc qua dịch vụ … |
| `S6` | `9ec69474-9e90-4db5-8b84-1bd95977b3a0` | `RETRIEVAL` | 4 | Điều 1, Khoản 2, tr. 1–1 | 2. Việc xử lý trường hợp giá trị thực của vốn điều lệ giảm thấp hơn mức vốn pháp định. |
| `S7` | `e2c8222e-f180-407e-9e75-08eef8bbf896` | `RETRIEVAL` | 5 | Điều 7, tr. 5–5 | Điều 7. Xử lý khi giá trị thực của vốn điều lệ giảm thấp hơn mức vốn pháp định |
| `S8` | `924006cf-616a-426c-9591-f7e7d37d20c4` | `RETRIEVAL` | 6 | Điều 7, Khoản 1, tr. 5–5 | 1. Khi giá trị thực của vốn điều lệ của quỹ tín dụng nhân dân giảm thấp hơn mức vốn pháp định, quỹ tín dụng nhân dân phải: |
| `S9` | `432f5e1d-c7fc-49ae-8119-7b61885e4253` | `HIERARCHY_CHILD` | None | Điều 7, Khoản 1, Điểm c, tr. 6–6 | c) Tổ chức triển khai thực hiện các biện pháp xử lý theo yêu cầu của Ngân hàng Nhà nước chi nhánh Khu vực (nếu có). |
| `S10` | `bcfee01d-d09b-4ffc-b477-4def4a83406c` | `RETRIEVAL` | 7 | Điều 7, Khoản 1, Điểm a, tr. 5–5 | a) Xây dựng và triển khai thực hiện phương án xử lý để đảm bảo giá trị thực của vốn điều lệ tối thiểu bằng mức vốn pháp định; |
| `S11` | `b6e32b7e-2d37-4ae0-bdcd-ba970e6ee943` | `RETRIEVAL` | 8 | Điều 14, Khoản 2, tr. 11–11 | 2. Thanh tra, kiểm tra, giám sát, thực hiện các biện pháp xử lý đối với các hành vi vi phạm của quỹ tín dụng nhân dân trên địa bàn trong việc thực hiện các quy định tại Thông tư này, bao gồm cả các biện pháp xử lý đối v… |
| `S12` | `1a51b6cd-f9ac-4cde-9065-a8bd90e60d74` | `RETRIEVAL` | 9 | Điều 1, Khoản 3, tr. 1–2 | 3. Căn cứ kết quả giám sát, thanh tra, kiểm tra đối với quỹ tín dụng nhân dân, trong trường hợp cần thiết để bảo đảm an toàn trong hoạt động của quỹ tín dụng nhân dân, tùy theo tính chất, mức độ rủi ro, Ngân hàng Nhà nư… |
| `S13` | `ab568a7d-b862-4b3b-aebc-b5d37e75b2e0` | `RETRIEVAL` | 10 | Điều 7, Khoản 2, Điểm b, tr. 6–6 | b) Yêu cầu sửa đổi, bổ sung, hoàn thiện các biện pháp xử lý của quỹ tín dụng nhân dân khi giá trị thực của vốn điều lệ thấp hơn mức vốn pháp định nêu tại phương án quy định tại khoản 1 Điều này trong trường hợp cần thiế… |

**Human judgment required:** answer support, citation acceptability, source mismatch, qualification, unsupported propositions, severity, and final decision. No field is pre-filled.

---

## v2_bank_scope_ratios — MULTI_EVIDENCE

**Review reasons:** `["V3_ANSWERABILITY_GAIN"]`

**Question:** Thông tư 40/2026/TT-NHNN điều chỉnh năm nhóm hạn chế, giới hạn và tỷ lệ an toàn chính nào?

**Expected behavior/reference:** Tỷ lệ an toàn vốn tối thiểu — Complete answer requires all five scope items.

| Version | Status | Expected-source complete | Answer |
|---|---|---:|---|
| V2 | `INSUFFICIENT_EVIDENCE` | `False` | (abstained) |
| V3 | `ANSWERABLE` | `True` | Thông tư quy định năm nhóm hạn chế, giới hạn và tỷ lệ an toàn chính bao gồm: a) Tỷ lệ an toàn vốn tối thiểu [S9], b) Tỷ lệ khả năng chi trả [S3], c) Tỷ lệ nguồn vốn ngắn hạn được sử dụng để cho vay trung hạn và dài hạn [S4], d) Hạn chế, giới hạn cho vay [S5], đ) Tỷ lệ tổng mức nhận tiền gửi so với vốn chủ sở hữu [S6]. |

**Engineering assessment:** retrieval expected complete `True`; context expected complete `True`; status valid `True`; citation structurally valid `True`. Legal correctness remains unfilled.

**Evidence shape:** base 10; hierarchy recovered 11; multi-evidence `True`; multi-document `False`; context tokens 1750.

### Required evidence matrix

| Chunk | Source ID | Selected | Cited | Origin | Legal unit |
|---|---|---:|---:|---|---|
| `48109bc6-e5cb-4c25-89be-b6ed2d85e066` | `S9` | True | True | `RETRIEVAL` | Điều 1, Khoản 1, Điểm a |
| `283fc8f6-8d90-4a6b-8a8c-d7f31d8935d2` | `S3` | True | True | `HIERARCHY_CHILD` | Điều 1, Khoản 1, Điểm b |
| `5faec617-7237-4dc8-a01a-bc4ade33ac31` | `S4` | True | True | `HIERARCHY_CHILD` | Điều 1, Khoản 1, Điểm c |
| `5c3fd83c-0fb0-4cd7-9d52-b346c203c28a` | `S5` | True | True | `HIERARCHY_CHILD` | Điều 1, Khoản 1, Điểm d |
| `30e14c4c-d8fd-4d68-9382-4d96bef43392` | `S6` | True | True | `HIERARCHY_CHILD` | Điều 1, Khoản 1, Điểm đ |

### Expected source text

**Acceptable solution 1**

#### Expected: `48109bc6-e5cb-4c25-89be-b6ed2d85e066` / S9

- Document: `78e54e57-fc2e-47b2-919c-c7120776226d` — Nghị định 40/2026/TT-NHNN; `Thông tư 40.2026.TT-NHNN.pdf`
- Title/authority/date: not available; Chính phủ; 2026-08-10
- Legal unit: Điều 1, Khoản 1, Điểm a, tr. 1–1; legal_unit_id `9719bc4b-93a7-4ff1-9403-72e69ee03c35`
- Origin: `RETRIEVAL`; selected: `True`; retrieval rank: `5`

> a) Tỷ lệ an toàn vốn tối thiểu;

#### Expected: `283fc8f6-8d90-4a6b-8a8c-d7f31d8935d2` / S3

- Document: `78e54e57-fc2e-47b2-919c-c7120776226d` — Nghị định 40/2026/TT-NHNN; `Thông tư 40.2026.TT-NHNN.pdf`
- Title/authority/date: not available; Chính phủ; 2026-08-10
- Legal unit: Điều 1, Khoản 1, Điểm b, tr. 1–1; legal_unit_id `ce883772-9824-40ee-8631-902c5b24712a`
- Origin: `HIERARCHY_CHILD`; selected: `True`; retrieval rank: `None`

> b) Tỷ lệ khả năng chi trả;

#### Expected: `5faec617-7237-4dc8-a01a-bc4ade33ac31` / S4

- Document: `78e54e57-fc2e-47b2-919c-c7120776226d` — Nghị định 40/2026/TT-NHNN; `Thông tư 40.2026.TT-NHNN.pdf`
- Title/authority/date: not available; Chính phủ; 2026-08-10
- Legal unit: Điều 1, Khoản 1, Điểm c, tr. 1–1; legal_unit_id `6f682fce-7151-472e-a3bc-cd30e4521636`
- Origin: `HIERARCHY_CHILD`; selected: `True`; retrieval rank: `None`

> c) Tỷ lệ nguồn vốn ngắn hạn được sử dụng để cho vay trung hạn và dài hạn;

#### Expected: `5c3fd83c-0fb0-4cd7-9d52-b346c203c28a` / S5

- Document: `78e54e57-fc2e-47b2-919c-c7120776226d` — Nghị định 40/2026/TT-NHNN; `Thông tư 40.2026.TT-NHNN.pdf`
- Title/authority/date: not available; Chính phủ; 2026-08-10
- Legal unit: Điều 1, Khoản 1, Điểm d, tr. 1–1; legal_unit_id `ce74388c-8090-4faa-8c26-82fd35b01d1d`
- Origin: `HIERARCHY_CHILD`; selected: `True`; retrieval rank: `None`

> d) Hạn chế, giới hạn cho vay;

#### Expected: `30e14c4c-d8fd-4d68-9382-4d96bef43392` / S6

- Document: `78e54e57-fc2e-47b2-919c-c7120776226d` — Nghị định 40/2026/TT-NHNN; `Thông tư 40.2026.TT-NHNN.pdf`
- Title/authority/date: not available; Chính phủ; 2026-08-10
- Legal unit: Điều 1, Khoản 1, Điểm đ, tr. 1–1; legal_unit_id `7cdb85c2-bec6-4e17-a0a2-19fcdd604466`
- Origin: `HIERARCHY_CHILD`; selected: `True`; retrieval rank: `None`

> đ) Tỷ lệ tổng mức nhận tiền gửi so với vốn chủ sở hữu.

### Actual cited source text

#### Actual: `48109bc6-e5cb-4c25-89be-b6ed2d85e066` / S9

- Document: `78e54e57-fc2e-47b2-919c-c7120776226d` — Nghị định 40/2026/TT-NHNN; `Thông tư 40.2026.TT-NHNN.pdf`
- Title/authority/date: not available; Chính phủ; 2026-08-10
- Legal unit: Điều 1, Khoản 1, Điểm a, tr. 1–1; legal_unit_id `9719bc4b-93a7-4ff1-9403-72e69ee03c35`
- Origin: `RETRIEVAL`; selected: `True`; retrieval rank: `5`

> a) Tỷ lệ an toàn vốn tối thiểu;

#### Actual: `283fc8f6-8d90-4a6b-8a8c-d7f31d8935d2` / S3

- Document: `78e54e57-fc2e-47b2-919c-c7120776226d` — Nghị định 40/2026/TT-NHNN; `Thông tư 40.2026.TT-NHNN.pdf`
- Title/authority/date: not available; Chính phủ; 2026-08-10
- Legal unit: Điều 1, Khoản 1, Điểm b, tr. 1–1; legal_unit_id `ce883772-9824-40ee-8631-902c5b24712a`
- Origin: `HIERARCHY_CHILD`; selected: `True`; retrieval rank: `None`

> b) Tỷ lệ khả năng chi trả;

#### Actual: `5faec617-7237-4dc8-a01a-bc4ade33ac31` / S4

- Document: `78e54e57-fc2e-47b2-919c-c7120776226d` — Nghị định 40/2026/TT-NHNN; `Thông tư 40.2026.TT-NHNN.pdf`
- Title/authority/date: not available; Chính phủ; 2026-08-10
- Legal unit: Điều 1, Khoản 1, Điểm c, tr. 1–1; legal_unit_id `6f682fce-7151-472e-a3bc-cd30e4521636`
- Origin: `HIERARCHY_CHILD`; selected: `True`; retrieval rank: `None`

> c) Tỷ lệ nguồn vốn ngắn hạn được sử dụng để cho vay trung hạn và dài hạn;

#### Actual: `5c3fd83c-0fb0-4cd7-9d52-b346c203c28a` / S5

- Document: `78e54e57-fc2e-47b2-919c-c7120776226d` — Nghị định 40/2026/TT-NHNN; `Thông tư 40.2026.TT-NHNN.pdf`
- Title/authority/date: not available; Chính phủ; 2026-08-10
- Legal unit: Điều 1, Khoản 1, Điểm d, tr. 1–1; legal_unit_id `ce74388c-8090-4faa-8c26-82fd35b01d1d`
- Origin: `HIERARCHY_CHILD`; selected: `True`; retrieval rank: `None`

> d) Hạn chế, giới hạn cho vay;

#### Actual: `30e14c4c-d8fd-4d68-9382-4d96bef43392` / S6

- Document: `78e54e57-fc2e-47b2-919c-c7120776226d` — Nghị định 40/2026/TT-NHNN; `Thông tư 40.2026.TT-NHNN.pdf`
- Title/authority/date: not available; Chính phủ; 2026-08-10
- Legal unit: Điều 1, Khoản 1, Điểm đ, tr. 1–1; legal_unit_id `7cdb85c2-bec6-4e17-a0a2-19fcdd604466`
- Origin: `HIERARCHY_CHILD`; selected: `True`; retrieval rank: `None`

> đ) Tỷ lệ tổng mức nhận tiền gửi so với vốn chủ sở hữu.

### Selected context inventory

| Source | Chunk | Origin | Rank | Legal unit | Text preview |
|---|---|---|---:|---|---|
| `S1` | `7ad5a22b-089a-4afe-85c4-77be8f5a98d4` | `RETRIEVAL` | 1 | tr. 1–1 | NGÂN HÀNG NHÀ NƯỚC CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM VIỆT NAM Độc lập - Tự do - Hạnh phúc Số: 40/2026/TT-NHNN Hà Nội, ngày 10 tháng 8 năm 2026 THÔNG TƯ Quy định các giới hạn, tỷ lệ bảo đảm an toàn trong hoạt động của q… |
| `S2` | `13566529-a241-4568-a651-b95a14bb0f9f` | `RETRIEVAL` | 2 | Điều 1, Khoản 1, tr. 1–1 | 1. Thông tư này quy định về các hạn chế, giới hạn, tỷ lệ bảo đảm an toàn trong hoạt động của quỹ tín dụng nhân dân bao gồm: |
| `S3` | `283fc8f6-8d90-4a6b-8a8c-d7f31d8935d2` | `HIERARCHY_CHILD` | None | Điều 1, Khoản 1, Điểm b, tr. 1–1 | b) Tỷ lệ khả năng chi trả; |
| `S4` | `5faec617-7237-4dc8-a01a-bc4ade33ac31` | `HIERARCHY_CHILD` | None | Điều 1, Khoản 1, Điểm c, tr. 1–1 | c) Tỷ lệ nguồn vốn ngắn hạn được sử dụng để cho vay trung hạn và dài hạn; |
| `S5` | `5c3fd83c-0fb0-4cd7-9d52-b346c203c28a` | `HIERARCHY_CHILD` | None | Điều 1, Khoản 1, Điểm d, tr. 1–1 | d) Hạn chế, giới hạn cho vay; |
| `S6` | `30e14c4c-d8fd-4d68-9382-4d96bef43392` | `HIERARCHY_CHILD` | None | Điều 1, Khoản 1, Điểm đ, tr. 1–1 | đ) Tỷ lệ tổng mức nhận tiền gửi so với vốn chủ sở hữu. |
| `S7` | `4e7a93e5-a04d-4d74-b3c1-0a7c5ae3f354` | `RETRIEVAL` | 3 | Điều 15, Khoản 2, Điểm b, tr. 12–12 | b) Thông tư số 13/2024/TT-NHNN ngày 28 tháng 6 năm 2024 của Thống đốc Ngân hàng Nhà nước Việt Nam sửa đổi, bổ sung một số điều của Thông tư số 32/2015/TT-NHNN ngày 31 tháng 12 năm 2015 của Thống đốc Ngân hàng Nhà nước V… |
| `S8` | `c4f0d74c-a06b-4e50-9303-c148f2899272` | `RETRIEVAL` | 4 | Điều 15, Khoản 2, Điểm a, tr. 12–12 | a) Thông tư số 32/2015/TT-NHNN ngày 31 tháng 12 năm 2015 của Thống đốc Ngân hàng Nhà nước Việt Nam quy định về các giới hạn, tỷ lệ bảo đảm an toàn trong hoạt động của quỹ tín dụng nhân dân; |
| `S9` | `48109bc6-e5cb-4c25-89be-b6ed2d85e066` | `RETRIEVAL` | 5 | Điều 1, Khoản 1, Điểm a, tr. 1–1 | a) Tỷ lệ an toàn vốn tối thiểu; |
| `S10` | `46193291-fcb4-4458-8fa3-85dfbb321e59` | `RETRIEVAL` | 6 | Điều 5, Khoản 3, Điểm c, tr. 3–3 | c) Phương pháp cảnh báo sớm các nguy cơ làm giảm tỷ lệ an toàn vốn hoặc vi phạm tỷ lệ an toàn vốn tối thiểu; |
| `S11` | `5965373c-7e11-4fe7-b179-42365b4eedc9` | `RETRIEVAL` | 7 | Điều 14, Khoản 1, tr. 11–11 | 1. Quyết định việc quỹ tín dụng nhân dân phải duy trì các hạn chế, giới hạn, tỷ lệ bảo đảm an toàn theo quy định tại khoản 3 Điều 1 Thông tư này. |
| `S12` | `39bf860e-d459-48a5-ac28-17380c5cf9c5` | `RETRIEVAL` | 8 | Điều 5, Khoản 3, Điểm đ, tr. 3–3 | đ) Hướng dẫn, kiểm tra, kiểm soát, kiểm toán nội bộ đối với việc duy trì tỷ lệ an toàn vốn tối thiểu. |
| `S13` | `6919c16f-5507-48c0-9fd6-f893a7a125ff` | `RETRIEVAL` | 9 | Điều 5, Khoản 3, tr. 3–3 | 3. Quy định nội bộ về quản lý tỷ lệ an toàn vốn tối thiểu, trong đó tối thiểu bao gồm các nội dung sau: |
| `S14` | `14afd6dc-087d-4d5c-b5dc-ae1cb089e083` | `HIERARCHY_CHILD` | None | Điều 5, Khoản 3, Điểm a, tr. 3–3 | a) Quy định về cơ cấu tổ chức, phân cấp, ủy quyền, chức năng, nhiệm vụ của các cá nhân, bộ phận liên quan trong việc theo dõi và thực hiện các biện pháp để đảm bảo duy trì tỷ lệ an toàn vốn tối thiểu; |
| `S15` | `060cc781-36b0-4634-8b64-ff3458fb1469` | `HIERARCHY_CHILD` | None | Điều 5, Khoản 3, Điểm b, tr. 3–3 | b) Quy trình, phương pháp theo dõi tỷ lệ an toàn vốn tối thiểu; |
| `S16` | `d3083e78-7cde-4dd8-a8c1-dc9fedb7d64b` | `HIERARCHY_CHILD` | None | Điều 5, Khoản 3, Điểm d, tr. 3–3 | d) Phương án xử lý khi tỷ lệ an toàn vốn thấp hơn mức tối thiểu, tối thiểu bao gồm: (i) Các biện pháp tăng tỷ lệ an toàn vốn; (ii) Trách nhiệm, quyền hạn và sự phối hợp của các bộ phận, cá nhân trong việc thực hiện phươ… |
| `S17` | `e268e6d3-9f77-415a-b27e-7518a20a9254` | `RETRIEVAL` | 10 | Điều 8, tr. 6–6 | Điều 8. Tỷ lệ an toàn vốn tối thiểu |
| `S18` | `e39582dd-80a7-491b-9712-4bcbb672bac8` | `HIERARCHY_CHILD` | None | Điều 8, Khoản 1, tr. 6–6 | 1. Quỹ tín dụng nhân dân phải duy trì tỷ lệ an toàn vốn tối thiểu 8%. |
| `S19` | `7ebf604f-0baf-41eb-a2c9-3a5862827197` | `HIERARCHY_CHILD` | None | Điều 8, Khoản 2, tr. 6–6 | 2. Tỷ lệ an toàn vốn tối thiểu được xác định bằng công thức sau: Vốn tự có Tỷ lệ an toàn vốn tối thiểu (%) = × 100 Tổng tài sản "Có" rủi ro Trong đó: - Vốn tự có được xác định theo quy định tại khoản 3 Điều này; - Tổng … |
| `S20` | `04437512-309a-475a-b020-073b8ce8f146` | `HIERARCHY_CHILD` | None | Điều 8, Khoản 3, tr. 6–6 | 3. Vốn tự có bao gồm tổng Vốn cấp 1 và Vốn cấp 2 trừ đi Khoản phải trừ khỏi vốn tự có tại thời điểm xác định vốn tự có, cụ thể: |
| `S21` | `4975e6cd-6c11-4456-b90b-af50862d332d` | `HIERARCHY_CHILD` | None | Điều 8, Khoản 4, tr. 7–7 | 4. Tài sản "Có" được phân nhóm theo các mức độ rủi ro như sau: |

**Human judgment required:** answer support, citation acceptability, source mismatch, qualification, unsupported propositions, severity, and final decision. No field is pre-filled.

---

## v2_civil_scope — DOCUMENT_DISAMBIGUATION

**Review reasons:** `["V3_UNRESOLVED_FALSE_ABSTENTION"]`

**Question:** Văn bản hợp nhất 10/2026/VBHN-NĐ-BNV quy định phạm vi nào?

**Expected behavior/reference:** quy định về tuyển dụng, sử dụng và quản lý công chức

| Version | Status | Expected-source complete | Answer |
|---|---|---:|---|
| V2 | `INSUFFICIENT_EVIDENCE` | `False` | (abstained) |
| V3 | `INSUFFICIENT_EVIDENCE` | `False` | (abstained) |

**Engineering assessment:** retrieval expected complete `True`; context expected complete `True`; status valid `True`; citation structurally valid `True`. Legal correctness remains unfilled.

**Evidence shape:** base 10; hierarchy recovered 7; multi-evidence `False`; multi-document `False`; context tokens 4049.

### Required evidence matrix

| Chunk | Source ID | Selected | Cited | Origin | Legal unit |
|---|---|---:|---:|---|---|
| `7239888d-6b34-417a-bb1d-4da08ebb5b67` | `S1` | True | False | `RETRIEVAL` | Điều —, Khoản —, Điểm — |

### Expected source text

**Acceptable solution 1**

#### Expected: `7239888d-6b34-417a-bb1d-4da08ebb5b67` / S1

- Document: `ed9f3e56-f3cd-41f6-9ed9-8b70e7f44c25` — Nghị định 10; `VBHN 10.2026.pdf`
- Title/authority/date: Quy định về tuyển dụng, sử dụng và quản lý công chức Nghị định số 170/2025/NĐ-CP ngày 30 tháng 6 năm 2025 của Chính phủ quy định về tuyển dụng, sử dụng và quản lý công chức, có hiệu lực kể từ ngày 01 tháng 7 năm 2025, được sửa đổi, bổ sung bởi: Nghị định số 300/2026/NĐ-CP ngày 29 tháng 7 năm 2026 của Chính phủ sửa đổi, bổ sung một số điều của Nghị định số 170/2025/NĐ-CP ngày 30 tháng 6 năm 2025 của Chính phủ quy định về tuyển dụng, sử dụng và quản lý công chức, có hiệu lực kể từ ngày 01 tháng 8 năm 2026.; Chính phủ; 2026-08-14
- Legal unit: tr. 1–1; legal_unit_id `2fe37308-78f0-4efd-a875-96d23cc5a4be`
- Origin: `RETRIEVAL`; selected: `True`; retrieval rank: `1`

> VĂN BẢN HỢP NHẤT CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
> Số: 10 /2026/VBHN-NĐ-BNV Độc lập - Tự do - Hạnh phúc
>
> Hà Nội, ngày 14 tháng 8 năm 2026
>
> NGHỊ ĐỊNH
> Quy định về tuyển dụng, sử dụng và quản lý công chức
>
> Nghị định số 170/2025/NĐ-CP ngày 30 tháng 6 năm 2025 của Chính phủ
> quy định về tuyển dụng, sử dụng và quản lý công chức, có hiệu lực kể từ ngày
> 01 tháng 7 năm 2025, được sửa đổi, bổ sung bởi:
> Nghị định số 300/2026/NĐ-CP ngày 29 tháng 7 năm 2026 của Chính phủ
> sửa đổi, bổ sung một số điều của Nghị định số 170/2025/NĐ-CP ngày 30 tháng 6
> năm 2025 của Chính phủ quy định về tuyển dụng, sử dụng và quản lý công
> chức, có hiệu lực kể từ ngày 01 tháng 8 năm 2026.
> Căn cứ Luật Tổ chức Chính phủ ngày 18 tháng 02 năm 2025;
> Căn cứ Luật Cán bộ, công chức ngày 24 tháng 6 năm 2025;
> Theo đề nghị của Bộ trưởng Bộ Nội vụ1;
> Chính phủ ban hành Nghị định quy định về tuyển dụng, sử dụng và quản
> lý công chức.

### Actual cited source text

No V3 source was cited because the model abstained.

### Unresolved abstention

- Engineering classification: `FALSE_ABSTENTION`
- Out of scope for V3 activation fix: `True`
- Future target: `CONTEXT_SELECTION_V2`

### Selected context inventory

| Source | Chunk | Origin | Rank | Legal unit | Text preview |
|---|---|---|---:|---|---|
| `S1` | `7239888d-6b34-417a-bb1d-4da08ebb5b67` | `RETRIEVAL` | 1 | tr. 1–1 | VĂN BẢN HỢP NHẤT CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM Số: 10 /2026/VBHN-NĐ-BNV Độc lập - Tự do - Hạnh phúc Hà Nội, ngày 14 tháng 8 năm 2026 NGHỊ ĐỊNH Quy định về tuyển dụng, sử dụng và quản lý công chức Nghị định số 170/2… |
| `S2` | `7ad5a22b-089a-4afe-85c4-77be8f5a98d4` | `RETRIEVAL` | 2 | tr. 1–1 | NGÂN HÀNG NHÀ NƯỚC CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM VIỆT NAM Độc lập - Tự do - Hạnh phúc Số: 40/2026/TT-NHNN Hà Nội, ngày 10 tháng 8 năm 2026 THÔNG TƯ Quy định các giới hạn, tỷ lệ bảo đảm an toàn trong hoạt động của q… |
| `S3` | `0e4c09e1-e442-48f4-a386-b3ef04dec969` | `RETRIEVAL` | 3 | Điều 64, Khoản 1, Điểm đ, tr. 54–54 | đ) Sử dụng, phân công, bố trí, kiểm tra, đánh giá, xây dựng phương án thay đổi vị trí việc làm xếp ngạch cao hơn; đào tạo, bồi dưỡng, thi đua, khen thưởng; tạm đình chỉ công tác, tạm đình chỉ chức vụ; thực hiện chế độ t… |
| `S4` | `c02689a4-1596-45c9-86d9-d2f48e8247a0` | `RETRIEVAL` | 4 | Điều 1, tr. 1–1 | Điều 1. Phạm vi điều chỉnh |
| `S5` | `13566529-a241-4568-a651-b95a14bb0f9f` | `HIERARCHY_CHILD` | None | Điều 1, Khoản 1, tr. 1–1 | 1. Thông tư này quy định về các hạn chế, giới hạn, tỷ lệ bảo đảm an toàn trong hoạt động của quỹ tín dụng nhân dân bao gồm: |
| `S6` | `9ec69474-9e90-4db5-8b84-1bd95977b3a0` | `HIERARCHY_CHILD` | None | Điều 1, Khoản 2, tr. 1–1 | 2. Việc xử lý trường hợp giá trị thực của vốn điều lệ giảm thấp hơn mức vốn pháp định. |
| `S7` | `1a51b6cd-f9ac-4cde-9065-a8bd90e60d74` | `HIERARCHY_CHILD` | None | Điều 1, Khoản 3, tr. 1–2 | 3. Căn cứ kết quả giám sát, thanh tra, kiểm tra đối với quỹ tín dụng nhân dân, trong trường hợp cần thiết để bảo đảm an toàn trong hoạt động của quỹ tín dụng nhân dân, tùy theo tính chất, mức độ rủi ro, Ngân hàng Nhà nư… |
| `S8` | `86532d17-b3a6-4663-824d-d66bff3e828a` | `HIERARCHY_CHILD` | None | Điều 1, Khoản 4, tr. 2–2 | 4. Quỹ tín dụng nhân dân được kiểm soát đặc biệt không phải tuân thủ quy định tại các Điều 136, 137, 138 và khoản 3 Điều 144 của Luật Các tổ chức tín dụng và các quy định liên quan tại Thông tư này. |
| `S9` | `9406cd83-efed-4c66-845b-f008e2f16d56` | `RETRIEVAL` | 5 | Điều 20, Khoản 3, tr. 16–17 | 3. Trường hợp người được tiếp nhận vào làm công chức có thời gian công tác theo đúng quy định của pháp luật, có đóng bảo hiểm xã hội bắt buộc (nếu không liên tục mà chưa nhận trợ cấp bảo hiểm xã hội một lần hoặc chưa hư… |
| `S10` | `e02400d2-80f5-404e-9337-22a787e192dd` | `RETRIEVAL` | 6 | Điều 67, Khoản 1, Điểm a, tr. 56–56 | a) Thống nhất quản lý công chức trên địa bàn tỉnh; thực hiện quản lý cán bộ trong cơ quan nhà nước trên địa bàn tỉnh theo phân cấp thẩm quyền quản lý; 35 Điều này được sửa đổi, bổ sung theo quy định tại Điều 32 Nghị địn… |
| `S11` | `34f2e2e3-b5ec-48cb-97c8-c48a68b1ba91` | `RETRIEVAL` | 7 | Điều 70, Khoản 2, tr. 58–58 | 2. Chậm nhất đến ngày 01 tháng 7 năm 2027, các Bộ, ngành, cơ quan trung ương, địa phương phải hoàn thành việc bố trí vào vị trí việc làm và xếp ngạch tương ứng với vị trí việc làm đối với công chức được tuyển dụng trước… |
| `S12` | `4fe6d518-19e8-479b-b3a7-45d0ac23707b` | `RETRIEVAL` | 8 | Điều 12, Khoản 6, tr. 10–10 | 6. Các giới hạn quy định tại điểm b khoản 1 Điều này không áp dụng đối với: |
| `S13` | `022d0872-1a53-43ba-bc11-a4474db0cea9` | `HIERARCHY_CHILD` | None | Điều 12, Khoản 6, Điểm a, tr. 10–10 | a) Khoản cho vay từ nguồn vốn ủy thác của tổ chức, cá nhân mà quỹ tín dụng nhân dân nhận ủy thác không chịu rủi ro; |
| `S14` | `e57b1bc6-2105-4404-bda1-4472cf6e2574` | `HIERARCHY_CHILD` | None | Điều 12, Khoản 6, Điểm b, tr. 11–11 | b) Các khoản cho vay được bảo đảm toàn bộ bằng tiền gửi tại chính quỹ tín dụng nhân dân. |
| `S15` | `631d3b99-b80c-40d6-b08b-6e66758bb626` | `RETRIEVAL` | 9 | Điều 24, Khoản 3, Điểm b, tr. 20–21 | b) Trường hợp ngạch tương ứng với vị trí việc làm mới có hệ số lương cùng bậc cao hơn ngạch hiện giữ thì căn cứ vào hệ số lương cộng phụ cấp thâm 10 Điều này được sửa đổi, bổ sung theo quy định tại Điều 9 Nghị định số 3… |
| `S16` | `44522c41-0190-4c0c-bce6-80efab7104b1` | `RETRIEVAL` | 10 | Điều 13, Khoản 2, tr. 9–10 | 2. Tiêu chuẩn, điều kiện tiếp nhận: Căn cứ vào tỷ lệ công chức cần bố trí theo từng vị trí việc làm đã được cấp có thẩm quyền phê duyệt trong cơ quan sử dụng công chức, chỉ tiêu biên chế được giao và yêu cầu của vị trí … |
| `S17` | `cac2f5d7-1b59-44c0-9e3b-070c4b34e51a` | `HIERARCHY_CHILD` | None | Điều 13, Khoản 2, Điểm a, tr. 10–10 | a) Đáp ứng đủ tiêu chuẩn, điều kiện đăng ký dự tuyển công chức quy định tại khoản 1 Điều 19 Luật Cán bộ, công chức số 80/2025/QH15; |

**Human judgment required:** answer support, citation acceptability, source mismatch, qualification, unsupported propositions, severity, and final decision. No field is pre-filled.

---

## v2_social_applicable_groups — MULTI_EVIDENCE

**Review reasons:** `["MULTI_EVIDENCE_FAILURE", "V3_UNRESOLVED_FALSE_ABSTENTION"]`

**Question:** Bốn nhóm đối tượng nào thuộc phạm vi áp dụng của Thông tư về thực hành và cập nhật kiến thức công tác xã hội?

**Expected behavior/reference:** Cơ sở thực hành công tác xã hội — Complete answer requires four separately chunked groups.

| Version | Status | Expected-source complete | Answer |
|---|---|---:|---|
| V2 | `INSUFFICIENT_EVIDENCE` | `False` | (abstained) |
| V3 | `INSUFFICIENT_EVIDENCE` | `False` | (abstained) |

**Engineering assessment:** retrieval expected complete `False`; context expected complete `False`; status valid `True`; citation structurally valid `True`. Legal correctness remains unfilled.

**Evidence shape:** base 10; hierarchy recovered 8; multi-evidence `True`; multi-document `False`; context tokens 2186.

### Required evidence matrix

| Chunk | Source ID | Selected | Cited | Origin | Legal unit |
|---|---|---:|---:|---|---|
| `23d10632-6b5f-4e82-a9eb-a91f3f1fa878` | `not selected` | False | False | `NOT_IN_FINAL_CONTEXT_CANDIDATES` | Điều 2, Khoản 1, Điểm — |
| `f160106c-f98a-4935-b076-16389967e868` | `not selected` | False | False | `NOT_IN_FINAL_CONTEXT_CANDIDATES` | Điều 2, Khoản 2, Điểm — |
| `d3421519-8b8b-44a9-b4b1-25a0c47b8515` | `not selected` | False | False | `NOT_IN_FINAL_CONTEXT_CANDIDATES` | Điều 2, Khoản 3, Điểm — |
| `b5d4ed5c-0914-4e73-97af-d655047006bb` | `not selected` | False | False | `NOT_IN_FINAL_CONTEXT_CANDIDATES` | Điều 2, Khoản 4, Điểm — |

### Expected source text

**Acceptable solution 1**

#### Expected: `23d10632-6b5f-4e82-a9eb-a91f3f1fa878`

- Document: `3fb22b9b-ed46-4e04-97e2-b8c854f8252b` — Nghị định 29; `Thong tu quy dinh thuc hanh cong tac xa hoi va cap nhat kien thuc cong.pdf`
- Title/authority/date: not available; Chính phủ; 2026-07-06
- Legal unit: Điều 2, Khoản 1, tr. 1–1; legal_unit_id `ca207212-e495-47d5-ab72-2b83eb6eaced`
- Origin: `NOT_IN_FINAL_CONTEXT_CANDIDATES`; selected: `False`; retrieval rank: `None`

> 1. Cơ sở thực hành công tác xã hội;

#### Expected: `f160106c-f98a-4935-b076-16389967e868`

- Document: `3fb22b9b-ed46-4e04-97e2-b8c854f8252b` — Nghị định 29; `Thong tu quy dinh thuc hanh cong tac xa hoi va cap nhat kien thuc cong.pdf`
- Title/authority/date: not available; Chính phủ; 2026-07-06
- Legal unit: Điều 2, Khoản 2, tr. 1–1; legal_unit_id `f7fd5dab-c339-4541-9e1b-b7d3fce9de55`
- Origin: `NOT_IN_FINAL_CONTEXT_CANDIDATES`; selected: `False`; retrieval rank: `None`

> 2. Cơ sở cập nhật kiến thức công tác xã hội;

#### Expected: `d3421519-8b8b-44a9-b4b1-25a0c47b8515`

- Document: `3fb22b9b-ed46-4e04-97e2-b8c854f8252b` — Nghị định 29; `Thong tu quy dinh thuc hanh cong tac xa hoi va cap nhat kien thuc cong.pdf`
- Title/authority/date: not available; Chính phủ; 2026-07-06
- Legal unit: Điều 2, Khoản 3, tr. 1–1; legal_unit_id `da1d04a8-7a1a-48f7-9b1d-1b499fe265de`
- Origin: `NOT_IN_FINAL_CONTEXT_CANDIDATES`; selected: `False`; retrieval rank: `None`

> 3. Người thực hành công tác xã hội, người hành nghề công tác xã hội;

#### Expected: `b5d4ed5c-0914-4e73-97af-d655047006bb`

- Document: `3fb22b9b-ed46-4e04-97e2-b8c854f8252b` — Nghị định 29; `Thong tu quy dinh thuc hanh cong tac xa hoi va cap nhat kien thuc cong.pdf`
- Title/authority/date: not available; Chính phủ; 2026-07-06
- Legal unit: Điều 2, Khoản 4, tr. 1–1; legal_unit_id `9b8bf3eb-71f4-4f07-88fb-4f012b136e59`
- Origin: `NOT_IN_FINAL_CONTEXT_CANDIDATES`; selected: `False`; retrieval rank: `None`

> 4. Các cơ quan, tổ chức, cá nhân có liên quan.

### Actual cited source text

No V3 source was cited because the model abstained.

### Multi-evidence review

Required pieces: 4; selected: 0; cited: 0. Whether the answer combines them correctly is **PENDING HUMAN REVIEW**.

### Unresolved abstention

- Engineering classification: `EXPECTED_EVIDENCE_NOT_IN_CONTEXT`
- Out of scope for V3 activation fix: `False`
- Future target: `RETRIEVAL_OR_CONTEXT_DIAGNOSIS`

### Selected context inventory

| Source | Chunk | Origin | Rank | Legal unit | Text preview |
|---|---|---|---:|---|---|
| `S1` | `30096d45-61c8-46b9-beb2-ef9b189f37ef` | `RETRIEVAL` | 1 | Điều 16, Khoản 3, tr. 7–7 | 3. Tổ chức hoạt động cập nhật kiến thức công tác xã hội theo quy định tại Thông tư này và chịu trách nhiệm về chất lượng cập nhật kiến thức công tác xã hội do cơ sở thực hiện. |
| `S2` | `4aec0cc1-cf74-4fbc-b88c-5f628dd8f4d0` | `RETRIEVAL` | 2 | Điều 11, Khoản 2, tr. 6–6 | 2. Người hành nghề công tác xã hội cập nhật kiến thức công tác xã hội bằng hình thức tự cập nhật kiến thức công tác xã hội và các hình thức khác được Người đứng đầu cơ sở chủ trì các hoạt động hoặc quản lý trực tiếp ngư… |
| `S3` | `aaea503a-39f3-43b5-985e-318a9dd5ee7c` | `RETRIEVAL` | 3 | Điều 8, Khoản 4, tr. 4–4 | 4. Người đứng đầu cơ sở cập nhật kiến thức công tác xã hội lựa chọn và bố trí đội ngũ giảng viên, chuyên gia về công tác xã hội hoặc phối hợp với cơ sở khác để đáp ứng theo yêu cầu của chương trình đào tạo. |
| `S4` | `fb2b69bb-edab-45b0-a56d-7b6248445757` | `RETRIEVAL` | 4 | Điều 11, Khoản 2, Điểm a, tr. 6–6 | a) Người hành nghề công tác xã hội được phân công hoặc mời tham gia giảng dạy các khóa đào tạo cấp văn bằng hoặc các khóa đào tạo để cấp chứng chỉ, giấy chứng nhận trong lĩnh vực công tác xã hội phù hợp với nội dung hàn… |
| `S5` | `461bda71-d08d-45e4-afee-17809d626cc0` | `RETRIEVAL` | 5 | Khoản 1, tr. 3–3 | 1. Cơ sở cập nhật kiến thức công tác xã hội là cơ sở thực hành công tác xã hội và cơ sở quy định tại khoản 4 Điều 34 Nghị định số 110/2024/NĐ-CP. |
| `S6` | `616c1e16-25dc-479c-b230-467b1cbef660` | `RETRIEVAL` | 6 | Điều 16, Khoản 4, tr. 7–7 | 4. Quản lý và lưu trữ hồ sơ, chương trình và tài liệu các khóa đào tạo, bồi dưỡng ngắn hạn, hồ sơ hội nghị, hội thảo, tọa đàm cập nhật kiến thức công tác xã hội của cơ sở; quản lý việc cấp giấy chứng nhận cập nhật kiến … |
| `S7` | `1f76cce4-ecaa-483f-aa1c-731b146fae51` | `RETRIEVAL` | 7 | tr. 4–4 | Chương trình, tài liệu đào tạo, bồi dưỡng cập nhật kiến thức công tác xã hội được rà soát, cập nhật định kỳ tối thiểu 03 năm một lần hoặc khi có thay đổi quan trọng về chính sách, pháp luật, khoa học, công nghệ và thực … |
| `S8` | `f1761f38-ec3b-40be-a100-b140a29ab0b9` | `HIERARCHY_CHILD` | None | Điều 8, tr. 4–4 | Điều 8. Cập nhật kiến thức công tác xã hội bằng hình thức tham gia các khóa đào tạo, bồi dưỡng ngắn hạn về công tác xã hội |
| `S9` | `54882ff1-3008-41e9-ad17-ed5a35836da1` | `HIERARCHY_CHILD` | None | Điều 9, tr. 5–5 | Điều 9. Cập nhật kiến thức công tác xã hội bằng hình thức tham gia hội nghị, hội thảo, tọa đàm về công tác xã hội 17:03:43 1. Hội nghị, hội thảo, tọa đàm về công tác xã hội do cơ sở quy định tại khoản 4 Điều 34 Nghị địn… |
| `S10` | `d0ec3830-dadc-4212-a8ea-bcfb029ed62f` | `HIERARCHY_CHILD` | None | Điều 10, tr. 5–5 | Điều 10. Cập nhật kiến thức công tác xã hội bằng hình thức tham giavanthu.pc_Van biên soạn giáo trình, tài liệu giảng dạy, tài liệu chuyên môn về công tác xã hội |
| `S11` | `2a3f00e3-1193-40be-b893-b9216c7a9de2` | `HIERARCHY_CHILD` | None | Điều 11, tr. 5–5 | Điều 11. Cập nhật kiến thức công tác xã hội bằng hình thức thực hiện các nghiên cứu khoa học, giảng dạy về công tác xã hội |
| `S12` | `ee9f8c97-ff12-463a-ba91-e2f97c82ee76` | `RETRIEVAL` | 8 | Điều 8, Khoản 1, tr. 4–4 | 1. Khóa đào tạo, bồi dưỡng ngắn hạn về công tác xã hội là các khóa đào tạo sử dụng chương trình, tài liệu đào tạo được xây dựng, thẩm định và ban hành theo quy định tại khoản 3 Điều 7 Thông tư này. Cơ sở cập nhật kiến t… |
| `S13` | `85df846b-61a4-43ca-9bb2-93ec66b6244e` | `RETRIEVAL` | 9 | Khoản 3, tr. 3–3 | 3. Các trường, trung tâm, cơ sở đào tạo về công tác xã hội (sau đây gọi là cơ sở đào tạo) xây dựng và ban hành khung chương trình, tài liệu đào tạo, bồi dưỡng cập nhật kiến thức công tác xã hội theo Phụ lục 03 ban hành … |
| `S14` | `33b78d6f-6bc1-4d25-82cb-2a2cff00c7ef` | `HIERARCHY_CHILD` | None | Khoản 3, Điểm b, tr. 3–3 | b) Thành lập Ban hoặc Tổ soạn thảo chương trình, tài liệu đào tạo, bồi dưỡng cập nhật kiến thức công tác xã hội: Người đứng đầu cơ sở đào tạo quyết định thành lập Ban hoặc Tổ soạn thảo chương trình, tài liệu đào tạo, bồ… |
| `S15` | `13705e94-5393-4533-b783-05a8b936dff4` | `HIERARCHY_CHILD` | None | Khoản 3, Điểm c, tr. 3–4 | c) Tổ chức xây dựng chương trình, tài liệu đào tạo, bồi dưỡng cập nhật kiến thức công tác xã hội: Ban hoặc Tổ soạn thảo chương trình, tài liệu đào tạo, bồi dưỡng cập nhật kiến thức công tác xã hội xây dựng chương trình,… |
| `S16` | `566cc2e6-d38d-433a-b915-b40743072d14` | `HIERARCHY_CHILD` | None | Khoản 3, Điểm d, tr. 4–4 | d) Thẩm định chương trình, tài liệu đào tạo, bồi dưỡng cập nhật kiến thức công tác xã hội: Người đứng đầu cơ sở đào tạo thành lập Hội đồng thẩm định chương 17:03:43 trình, tài liệu đào tạo, bồi dưỡng cập nhật kiến thức … |
| `S17` | `f478ce98-c1c7-4462-b0ac-626f2221f941` | `HIERARCHY_CHILD` | None | Khoản 3, Điểm đ, tr. 4–4 | đ) Ban hành chương trình, tài liệu đào tạo, bồi dưỡng cập nhật kiến thức côngvanthu.pc_Vantác xã hội: Người đứng đầu cơ sở đào tạo ký quyết định ban hành chương trình, tài liệu đào tạo, bồi dưỡng cập nhật kiến thức công… |
| `S18` | `6b3831bc-e211-4587-976c-42d35814c2ea` | `RETRIEVAL` | 10 | Khoản 3, Điểm a, tr. 3–3 | a) Xác định nhu cầu, nội dung cập nhật: Cơ sở đào tạo tiến hành khảo sát, xác định nội dung để xây dựng chương trình, tài liệu đào tạo, bồi dưỡng cập nhật kiến thức công tác xã hội. Việc xác định nhu cầu cập nhật kiến t… |

**Human judgment required:** answer support, citation acceptability, source mismatch, qualification, unsupported propositions, severity, and final decision. No field is pre-filled.

---

## v2_social_effective_transition — MULTI_EVIDENCE

**Review reasons:** `["V3_ANSWERABILITY_GAIN", "STRUCTURALLY_VALID_UNEXPECTED_SOURCE", "MULTI_EVIDENCE_FAILURE"]`

**Question:** Thông tư về công tác xã hội có hiệu lực ngày nào và người đã có giấy xác nhận thực hành có phải thực hành lại không?

**Expected behavior/reference:** có hiệu lực từ ngày 25 tháng 8 năm 2026 — Requires effective-date and transition evidence.

| Version | Status | Expected-source complete | Answer |
|---|---|---:|---|
| V2 | `INSUFFICIENT_EVIDENCE` | `False` | (abstained) |
| V3 | `ANSWERABLE` | `False` | Thông tư về công tác xã hội có hiệu lực từ ngày 01 tháng 08 năm 2025 [S1]. Người đã có giấy xác nhận thực hành công tác xã hội theo quy định tại Nghị định số 110/2024/NĐ-CP thì không phải thực hành lại [S1]. |

**Engineering assessment:** retrieval expected complete `False`; context expected complete `False`; status valid `True`; citation structurally valid `True`. Legal correctness remains unfilled.

**Evidence shape:** base 10; hierarchy recovered 4; multi-evidence `True`; multi-document `False`; context tokens 1824.

### Required evidence matrix

| Chunk | Source ID | Selected | Cited | Origin | Legal unit |
|---|---|---:|---:|---|---|
| `70100659-7c0f-4617-ad9f-7ce2a3b44f2e` | `not selected` | False | False | `NOT_IN_FINAL_CONTEXT_CANDIDATES` | Điều 17, Khoản —, Điểm — |
| `ff57c879-4c67-4a7b-b550-6c2b373955be` | `S3` | True | False | `RETRIEVAL` | Điều 15, Khoản 1, Điểm — |

### Expected source text

**Acceptable solution 1**

#### Expected: `70100659-7c0f-4617-ad9f-7ce2a3b44f2e`

- Document: `3fb22b9b-ed46-4e04-97e2-b8c854f8252b` — Nghị định 29; `Thong tu quy dinh thuc hanh cong tac xa hoi va cap nhat kien thuc cong.pdf`
- Title/authority/date: not available; Chính phủ; 2026-07-06
- Legal unit: Điều 17, tr. 7–7; legal_unit_id `5dc1f785-e776-4296-8984-cc9e6dd38c3e`
- Origin: `NOT_IN_FINAL_CONTEXT_CANDIDATES`; selected: `False`; retrieval rank: `None`

> Điều 17. Hiệu lực thi hành
> Thông tư này có hiệu lực từ ngày 25 tháng 8 năm 2026.

#### Expected: `ff57c879-4c67-4a7b-b550-6c2b373955be` / S3

- Document: `3fb22b9b-ed46-4e04-97e2-b8c854f8252b` — Nghị định 29; `Thong tu quy dinh thuc hanh cong tac xa hoi va cap nhat kien thuc cong.pdf`
- Title/authority/date: not available; Chính phủ; 2026-07-06
- Legal unit: Điều 15, Khoản 1, tr. 7–7; legal_unit_id `59ef60bf-2069-4ca0-9bcf-4668da864262`
- Origin: `RETRIEVAL`; selected: `True`; retrieval rank: `3`

> 1. Tổ chức hoạt động hướng dẫn thực hành theo nội dung và kế hoạch che_06/07/2026
> hướng dẫn thực hành của cơ sở. Phap
> Vu2. Trong thời gian 03 ngày làm việc, kể từ ngày người thực hành được cấp
> giấythuxác nhận quá trình thực hành công tác xã hội, cơ sở thực hành công tác xã hội
> phải gửi cơ quan chuyên môn về y tế thuộc Ủy ban nhân dân cấp tỉnh danh sách
> các đối tượng đã được cấp giấy xác nhận quá trình thực hành công tác xã hội để
> theo dõi, quản lý hoạt động hướng dẫn thực hành và đăng tải trên Trang thông tinvanthu.pc_Van điện tử của cơ sở các thông tin người thực hành, bao gồm cả người hướng dẫn thực
> hành và thời gian người đó thực hành tại cơ sở (Họ và tên; ngày, tháng, năm sinh;
> đơn vị công tác; thời gian thực hành).

### Actual cited source text

#### Actual: `425f59be-f2fa-49f4-acb7-461cb0769b50` / S1

- Document: `3fb22b9b-ed46-4e04-97e2-b8c854f8252b` — Nghị định 29; `Thong tu quy dinh thuc hanh cong tac xa hoi va cap nhat kien thuc cong.pdf`
- Title/authority/date: not available; Chính phủ; 2026-07-06
- Legal unit: Điều 18, tr. 7–8; legal_unit_id `d399af80-5618-4b8e-8c25-caabf15db5e8`
- Origin: `RETRIEVAL`; selected: `True`; retrieval rank: `1`

> Điều 18. Điều khoản chuyển tiếp
> Đối với trường hợp người thực hành công tác xã hội đã được cấp Giấy xác
> nhận quá trình thực hành công tác xã hội theo quy định tại Nghị định số
> 110/2024/NĐ-CP thì không phải thực hành lại. Người đang trong quá trình thực
> hành công tác xã hội trước ngày Thông tư này có hiệu lực thì tiếp tục thực hành
> theo quy định tại Nghị định số 110/2024/NĐ-CP.

### Unexpected-source deterministic comparison

- Document relationship: `SAME_DOCUMENT_SET`
- Article/clause relationship: `DIFFERENT_ARTICLES`
- Overlapping legal proposition: **PENDING HUMAN REVIEW**
- Differing legal proposition: **PENDING HUMAN REVIEW**
- Review label: **INSUFFICIENT FOR AUTOMATIC DETERMINATION**

### Multi-evidence review

Required pieces: 2; selected: 1; cited: 0. Whether the answer combines them correctly is **PENDING HUMAN REVIEW**.

### Selected context inventory

| Source | Chunk | Origin | Rank | Legal unit | Text preview |
|---|---|---|---:|---|---|
| `S1` | `425f59be-f2fa-49f4-acb7-461cb0769b50` | `RETRIEVAL` | 1 | Điều 18, tr. 7–8 | Điều 18. Điều khoản chuyển tiếp Đối với trường hợp người thực hành công tác xã hội đã được cấp Giấy xác nhận quá trình thực hành công tác xã hội theo quy định tại Nghị định số 110/2024/NĐ-CP thì không phải thực hành lại… |
| `S2` | `fb2b69bb-edab-45b0-a56d-7b6248445757` | `RETRIEVAL` | 2 | Điều 11, Khoản 2, Điểm a, tr. 6–6 | a) Người hành nghề công tác xã hội được phân công hoặc mời tham gia giảng dạy các khóa đào tạo cấp văn bằng hoặc các khóa đào tạo để cấp chứng chỉ, giấy chứng nhận trong lĩnh vực công tác xã hội phù hợp với nội dung hàn… |
| `S3` | `ff57c879-4c67-4a7b-b550-6c2b373955be` | `RETRIEVAL` | 3 | Điều 15, Khoản 1, tr. 7–7 | 1. Tổ chức hoạt động hướng dẫn thực hành theo nội dung và kế hoạch che_06/07/2026 hướng dẫn thực hành của cơ sở. Phap Vu2. Trong thời gian 03 ngày làm việc, kể từ ngày người thực hành được cấp giấythuxác nhận quá trình … |
| `S4` | `dd748672-d3b1-45e5-a840-e61615901646` | `RETRIEVAL` | 4 | Điều 10, Khoản 2, tr. 5–5 | 2. Chứng nhận tham gia biên soạn giáo trình, tài liệu giảng dạy, tài liệu chuyên môn: Người hành nghề công tác xã hội được Người đứng đầu cơ sở cập nhật kiến thức công tác xã hội tính giờ tín chỉ và cấp giấy chứng nhận … |
| `S5` | `4aec0cc1-cf74-4fbc-b88c-5f628dd8f4d0` | `RETRIEVAL` | 5 | Điều 11, Khoản 2, tr. 6–6 | 2. Người hành nghề công tác xã hội cập nhật kiến thức công tác xã hội bằng hình thức tự cập nhật kiến thức công tác xã hội và các hình thức khác được Người đứng đầu cơ sở chủ trì các hoạt động hoặc quản lý trực tiếp ngư… |
| `S6` | `cf38602e-3071-4e35-b4f5-532752cf0b86` | `RETRIEVAL` | 6 | Điều 4, Khoản 5, tr. 2–2 | 5. Trong quá trình thực hành công tác xã hội, người thực hành được tham gia tập huấn các quy định pháp luật về công tác xã hội, an sinh xã hội, chuyên môn về công tác xã hội, đạo đức nghề nghiệp công tác xã hội, kỹ năng… |
| `S7` | `74246516-06c7-4adb-a212-656c063dde89` | `RETRIEVAL` | 7 | Điều 13, Khoản 2, tr. 6–6 | 2. Đối với việc cập nhật kiến thức công tác xã hội của người hành nghề công tác xã hội do cơ sở nước ngoài tổ chức: Việc xác nhận thời gian tham gia cập nhật kiến thức công tác xã hội do Người đứng đầu cơ sở cập nhật ki… |
| `S8` | `3e972463-1919-46c9-94ce-751fc9689188` | `RETRIEVAL` | 8 | Điều 11, Khoản 1, Điểm b, tr. 5–5 | b) Chứng nhận thực hiện các nghiên cứu khoa học: Người hành nghề công tác xã hội được Người đứng đầu cơ sở cập nhật kiến thức công tác xã hội tính giờ tín chỉ và được cấp giấy chứng nhận cập nhật kiến thức công tác xã h… |
| `S9` | `1f76cce4-ecaa-483f-aa1c-731b146fae51` | `RETRIEVAL` | 9 | tr. 4–4 | Chương trình, tài liệu đào tạo, bồi dưỡng cập nhật kiến thức công tác xã hội được rà soát, cập nhật định kỳ tối thiểu 03 năm một lần hoặc khi có thay đổi quan trọng về chính sách, pháp luật, khoa học, công nghệ và thực … |
| `S10` | `f1761f38-ec3b-40be-a100-b140a29ab0b9` | `HIERARCHY_CHILD` | None | Điều 8, tr. 4–4 | Điều 8. Cập nhật kiến thức công tác xã hội bằng hình thức tham gia các khóa đào tạo, bồi dưỡng ngắn hạn về công tác xã hội |
| `S11` | `54882ff1-3008-41e9-ad17-ed5a35836da1` | `HIERARCHY_CHILD` | None | Điều 9, tr. 5–5 | Điều 9. Cập nhật kiến thức công tác xã hội bằng hình thức tham gia hội nghị, hội thảo, tọa đàm về công tác xã hội 17:03:43 1. Hội nghị, hội thảo, tọa đàm về công tác xã hội do cơ sở quy định tại khoản 4 Điều 34 Nghị địn… |
| `S12` | `d0ec3830-dadc-4212-a8ea-bcfb029ed62f` | `HIERARCHY_CHILD` | None | Điều 10, tr. 5–5 | Điều 10. Cập nhật kiến thức công tác xã hội bằng hình thức tham giavanthu.pc_Van biên soạn giáo trình, tài liệu giảng dạy, tài liệu chuyên môn về công tác xã hội |
| `S13` | `2a3f00e3-1193-40be-b893-b9216c7a9de2` | `HIERARCHY_CHILD` | None | Điều 11, tr. 5–5 | Điều 11. Cập nhật kiến thức công tác xã hội bằng hình thức thực hiện các nghiên cứu khoa học, giảng dạy về công tác xã hội |
| `S14` | `5face032-faa3-4b38-a5c8-35072a34adda` | `RETRIEVAL` | 10 | Điều 6, Khoản 1, tr. 3–3 | 1. Cơ sở tổ chức việc thực hành công tác xã hội được thực hiện theo Điều 36 Nghị định số 110/2024/NĐ-CP. Trường hợp có nhiều người hướng dẫn thực hành cho một người thực hành 17:03:43 thì người đứng đầu cơ sở thực hành … |

**Human judgment required:** answer support, citation acceptability, source mismatch, qualification, unsupported propositions, severity, and final decision. No field is pre-filled.

---

## v2_social_plan_submission_filter — DOCUMENT_FILTER

**Review reasons:** `["STRUCTURALLY_VALID_UNEXPECTED_SOURCE"]`

**Question:** Theo Thông tư về công tác xã hội, kế hoạch hướng dẫn thực hành phải gửi cơ quan chuyên môn về y tế cấp tỉnh trước ngày nào?

**Expected behavior/reference:** trước ngày 01 tháng 02 hằng năm

| Version | Status | Expected-source complete | Answer |
|---|---|---:|---|
| V2 | `ANSWERABLE` | `True` | Cơ sở thực hành công tác xã hội gửi kế hoạch hướng dẫn thực hành đến cơ quan chuyên môn về y tế thuộc Ủy ban nhân dân cấp tỉnh trước ngày 01 tháng 02 hằng năm [S1]. |
| V3 | `ANSWERABLE` | `False` | Cơ sở thực hành công tác xã hội phải gửi kế hoạch hướng dẫn thực hành đến cơ quan chuyên môn về y tế thuộc Ủy ban nhân dân cấp tỉnh trước ngày 15 tháng 01 hằng năm [S4]. |

**Engineering assessment:** retrieval expected complete `True`; context expected complete `True`; status valid `True`; citation structurally valid `True`. Legal correctness remains unfilled.

**Evidence shape:** base 10; hierarchy recovered 0; multi-evidence `False`; multi-document `False`; context tokens 2116.

### Required evidence matrix

| Chunk | Source ID | Selected | Cited | Origin | Legal unit |
|---|---|---:|---:|---|---|
| `76a4ed3a-5929-4a51-8d76-b58792f9a277` | `S1` | True | False | `RETRIEVAL` | Điều 5, Khoản 3, Điểm — |

### Expected source text

**Acceptable solution 1**

#### Expected: `76a4ed3a-5929-4a51-8d76-b58792f9a277` / S1

- Document: `3fb22b9b-ed46-4e04-97e2-b8c854f8252b` — Nghị định 29; `Thong tu quy dinh thuc hanh cong tac xa hoi va cap nhat kien thuc cong.pdf`
- Title/authority/date: not available; Chính phủ; 2026-07-06
- Legal unit: Điều 5, Khoản 3, tr. 2–2; legal_unit_id `09576a51-486d-4d1f-8095-cbea73a1ff1a`
- Origin: `RETRIEVAL`; selected: `True`; retrieval rank: `1`

> 3. Cơ sở thực hành công tác xã hội gửi kế hoạch hướng dẫn thực hành công
> tác xã hội hằng năm đến cơ quan chuyên môn về y tế thuộc Ủy ban nhân dân cấp
> tỉnh trước ngày 01 tháng 02 hằng năm để tổng hợp, theo dõi và quản lý hoạt động
> hướng dẫn thực hành. Đồng thời, cơ sở thực hành công tác xã hội phải đăng tải
> công khai trên Trang thông tin điện tử của cơ sở đó (nếu có).

### Actual cited source text

#### Actual: `11944445-90ec-4013-81a0-952889e8a837` / S4

- Document: `3fb22b9b-ed46-4e04-97e2-b8c854f8252b` — Nghị định 29; `Thong tu quy dinh thuc hanh cong tac xa hoi va cap nhat kien thuc cong.pdf`
- Title/authority/date: not available; Chính phủ; 2026-07-06
- Legal unit: Điều 5, Khoản 1, tr. 2–2; legal_unit_id `b6e70b5b-0b52-4bdb-9c04-229cbf6d12bc`
- Origin: `RETRIEVAL`; selected: `True`; retrieval rank: `4`

> 1. Dựa trên tổng hợp nhu cầu của người thực hành, khả năng tiếp nhận
> người thực hành, cơ sở thực hành công tác xã hội xây dựng kế hoạch hướng dẫn
> thực hành trước ngày 15 tháng 01 hằng năm.

### Unexpected-source deterministic comparison

- Document relationship: `SAME_DOCUMENT_SET`
- Article/clause relationship: `SAME_ARTICLE_PRESENT`
- Overlapping legal proposition: **PENDING HUMAN REVIEW**
- Differing legal proposition: **PENDING HUMAN REVIEW**
- Review label: **INSUFFICIENT FOR AUTOMATIC DETERMINATION**

### Selected context inventory

| Source | Chunk | Origin | Rank | Legal unit | Text preview |
|---|---|---|---:|---|---|
| `S1` | `76a4ed3a-5929-4a51-8d76-b58792f9a277` | `RETRIEVAL` | 1 | Điều 5, Khoản 3, tr. 2–2 | 3. Cơ sở thực hành công tác xã hội gửi kế hoạch hướng dẫn thực hành công tác xã hội hằng năm đến cơ quan chuyên môn về y tế thuộc Ủy ban nhân dân cấp tỉnh trước ngày 01 tháng 02 hằng năm để tổng hợp, theo dõi và quản lý… |
| `S2` | `ff57c879-4c67-4a7b-b550-6c2b373955be` | `RETRIEVAL` | 2 | Điều 15, Khoản 1, tr. 7–7 | 1. Tổ chức hoạt động hướng dẫn thực hành theo nội dung và kế hoạch che_06/07/2026 hướng dẫn thực hành của cơ sở. Phap Vu2. Trong thời gian 03 ngày làm việc, kể từ ngày người thực hành được cấp giấythuxác nhận quá trình … |
| `S3` | `0ce1626e-2af0-4ebd-b744-8a16dedebfd1` | `RETRIEVAL` | 3 | Điều 19, Khoản 2, tr. 8–8 | 2. Uỷ ban nhân dân các cấp chỉ đạo triển khai, tổ chức thực hiện Thông tư này tại địa phương. Cơ quan chuyên môn về y tế thuộc Ủy ban nhân dân cấp tỉnh che_06/07/2026 chịu trách nhiệm tổ chức triển khai, hướng dẫn thực … |
| `S4` | `11944445-90ec-4013-81a0-952889e8a837` | `RETRIEVAL` | 4 | Điều 5, Khoản 1, tr. 2–2 | 1. Dựa trên tổng hợp nhu cầu của người thực hành, khả năng tiếp nhận người thực hành, cơ sở thực hành công tác xã hội xây dựng kế hoạch hướng dẫn thực hành trước ngày 15 tháng 01 hằng năm. |
| `S5` | `5face032-faa3-4b38-a5c8-35072a34adda` | `RETRIEVAL` | 5 | Điều 6, Khoản 1, tr. 3–3 | 1. Cơ sở tổ chức việc thực hành công tác xã hội được thực hiện theo Điều 36 Nghị định số 110/2024/NĐ-CP. Trường hợp có nhiều người hướng dẫn thực hành cho một người thực hành 17:03:43 thì người đứng đầu cơ sở thực hành … |
| `S6` | `783aac1c-9c44-4095-a63a-6adc9ba0e209` | `RETRIEVAL` | 6 | tr. 1–1 | BỘ Y TẾ CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM Độc lập - Tự do - Hạnh phúc Số: 29 /2026/TT-BYT Hà Nội, ngày 06 tháng 7 năm 2026 17:03:43 THÔNG TƯ Quy định về thực hành công tác xã hội và cập nhật kiến thức công tác xã hội c… |
| `S7` | `2349c31a-5383-4dc2-a783-b4c122a210cd` | `RETRIEVAL` | 7 | Điều 19, Khoản 3, tr. 8–8 | 3. Chánh Văn phòng Bộ, Thủ trưởng các Vụ, Cục thuộc Bộ Y tế và các cơ quan, tổ chức, cá nhân có liên quan chịu trách nhiệm thi hành Thông tư này. Trong quá trình thực hiện Thông tư, nếu có khó khăn vướng mắc, đề nghịvan… |
| `S8` | `36c0859d-517b-4a62-91c7-500b76c4df73` | `RETRIEVAL` | 8 | Điều 19, Khoản 5, Điểm d, tr. 11–12 | d) Phối hợp với17:03:43các cơ quan, đơn vị, tổ chức, cá Có Có nhân trong quá trình xây dựng kế hoạch và thực hiện các công việc theo kế hoạch trợ giúp đối tượng. che_06/07/2026 Phap Vu thu vanthu.pc_Van PHỤ LỤC 02 NỘI D… |
| `S9` | `f5798adf-bed3-455e-9e9a-6a80b27754b3` | `RETRIEVAL` | 9 | Điều 19, Khoản 3, tr. 9–9 | PHỤ LỤC 01 NỘI DUNG CƠ BẢN THỰC HÀNH CÔNG TÁC XÃ HỘI (Ban hành kèm theo Thông tư số 29 /2026/TT-BYT ngày 06 tháng 7 năm 2026 của Bộ trưởng Bộ Y tế) 17:03:43 TRÌNH ĐỘ ĐÀO TẠO STT che_06/07/2026NỘI DUNG THỰC HÀNH Trung cấ… |
| `S10` | `4bc48d33-4ba8-43e1-81b6-2b6e37ec5258` | `RETRIEVAL` | 10 | Điều 14, Khoản 3, tr. 7–7 | 3. Không được tự ý thực hiện các hoạt động chuyên môn cung cấp dịch vụ 17:03:43 công tác xã hội cho đối tượng khi chưa được người hướng dẫn thực hành cho phép, trừ trường hợp khẩn cấp nhằm bảo đảm an toàn, bí mật thông … |

**Human judgment required:** answer support, citation acceptability, source mismatch, qualification, unsupported propositions, severity, and final decision. No field is pre-filled.

---

## v2_social_practice_content — MULTI_EVIDENCE

**Review reasons:** `["STRUCTURALLY_VALID_UNEXPECTED_SOURCE", "MULTI_EVIDENCE_FAILURE"]`

**Question:** Nội dung thực hành công tác xã hội bao gồm những nhóm năng lực và kỹ năng nào?

**Expected behavior/reference:** Đạo đức nghề nghiệp công tác xã hội — The fourth chunk also contains the coordination-skill item.

| Version | Status | Expected-source complete | Answer |
|---|---|---:|---|
| V2 | `ANSWERABLE` | `True` | Nội dung thực hành công tác xã hội bao gồm các nhóm năng lực và kỹ năng sau: - Đạo đức nghề nghiệp công tác xã hội [S3]. - Năng lực, trình độ chuyên môn về công tác xã hội [S4]. - Kỹ năng, nghiệp vụ công tác xã hội trong phạm vi nội dung thực hành [S8]. - Kỹ năng cung cấp, thực hiện các dịch vụ công tác xã hội có yêu cầu đơn giản về lý thuyết, phương pháp và kỹ năng thực hành theo sự phân công gồm: tư vấn, tham vấn, trị liệu, phục hồi chức năng, giáo dục, đàm phán, hoà giải, tuyên truyền [S9]. - Kỹ năng thực hiện các hoạt động chuyên môn phòng ngừa, can thiệp, trị liệu, chăm sóc, phục hồi, hỗ trợ phát triển, tư vấn, tham vấn, hỗ trợ tâm lý và các hoạt động công tác xã hội khác trong phạm vi nội dung thực hành [S10]. - Kỹ năng thực hiện quy trình cung cấp dịch vụ công tác xã hội gồm: Tiếp nhận, thu thập thông tin và đánh giá nhu cầu trợ giúp của đối tượng; Xây dựng kế hoạch trợ giúp đối với đối tượng; Thực hiện kế hoạch trợ giúp đối tượng; Theo dõi, rà soát, đánh giá và điều chỉnh kế hoạch trợ giúp; Kết thúc quá trình trợ giúp và lưu trữ hồ sơ [S6]. - Kỹ năng truyền thông, vận động nguồn lực, kết nối thực hiện các hoạt động công tác xã hội [S1]. - Kỹ năng phối hợp thực hiện các hoạt động công tác xã hội [S2]. - Kỹ năng thực hành về công tác xã hội [S11]. |
| V3 | `ANSWERABLE` | `False` | Nội dung thực hành công tác xã hội bao gồm các nhóm năng lực và kỹ năng sau: 1. Đạo đức nghề nghiệp công tác xã hội [S3]. 2. Năng lực, trình độ chuyên môn về công tác xã hội [S4]. 3. Kỹ năng cung cấp, thực hiện các dịch vụ công tác xã hội (tư vấn, tham vấn, trị liệu, phục hồi chức năng, giáo dục, đàm phán, hoà giải, tuyên truyền) [S9]. 4. Kỹ năng thực hiện quy trình cung cấp dịch vụ công tác xã hội (tiếp nhận thông tin, đánh giá nhu cầu, xây dựng và thực hiện kế hoạch trợ giúp, theo dõi đánh giá, kết thúc và lưu trữ hồ sơ) [S6]. 5. Kỹ năng truyền thông, vận động nguồn lực, kết nối thực hiện các hoạt động công tác xã hội [S1], [S4]. 6. Kỹ năng phối hợp thực hiện các hoạt động công tác xã hội [S2]. 7. Kỹ năng nghiệp vụ công tác xã hội trong phạm vi nội dung thực hành [S8]. 8. Kỹ năng thực hiện các hoạt động chuyên môn (phòng ngừa, can thiệp, chăm sóc, hỗ trợ phát triển, tư vấn, tham vấn, hỗ trợ tâm lý) [S10]. |

**Engineering assessment:** retrieval expected complete `True`; context expected complete `True`; status valid `True`; citation structurally valid `True`. Legal correctness remains unfilled.

**Evidence shape:** base 10; hierarchy recovered 2; multi-evidence `True`; multi-document `False`; context tokens 1132.

### Required evidence matrix

| Chunk | Source ID | Selected | Cited | Origin | Legal unit |
|---|---|---:|---:|---|---|
| `77d1986c-82a4-4ef3-a215-08e1c2250d9d` | `S3` | True | True | `HIERARCHY_CHILD` | Điều 3, Khoản 2, Điểm a |
| `bb5ff3eb-1831-4df5-a40f-0b8cfb4444bf` | `S4` | True | True | `HIERARCHY_CHILD` | Điều 3, Khoản 2, Điểm b |
| `e044e3d1-b910-4d49-ab4e-10b049acc42a` | `S11` | True | False | `RETRIEVAL` | Điều 3, Khoản 2, Điểm c |
| `aebafad2-e8a0-49e6-82e0-2cd27270e54d` | `S1` | True | True | `RETRIEVAL` | Điều 3, Khoản 2, Điểm d |

### Expected source text

**Acceptable solution 1**

#### Expected: `77d1986c-82a4-4ef3-a215-08e1c2250d9d` / S3

- Document: `3fb22b9b-ed46-4e04-97e2-b8c854f8252b` — Nghị định 29; `Thong tu quy dinh thuc hanh cong tac xa hoi va cap nhat kien thuc cong.pdf`
- Title/authority/date: not available; Chính phủ; 2026-07-06
- Legal unit: Điều 3, Khoản 2, Điểm a, tr. 2–2; legal_unit_id `d0ba484b-147d-4910-b8d0-86850faeb618`
- Origin: `HIERARCHY_CHILD`; selected: `True`; retrieval rank: `None`

> a) Đạo đức nghề nghiệp công tác xã hội; 17:03:43

#### Expected: `bb5ff3eb-1831-4df5-a40f-0b8cfb4444bf` / S4

- Document: `3fb22b9b-ed46-4e04-97e2-b8c854f8252b` — Nghị định 29; `Thong tu quy dinh thuc hanh cong tac xa hoi va cap nhat kien thuc cong.pdf`
- Title/authority/date: not available; Chính phủ; 2026-07-06
- Legal unit: Điều 3, Khoản 2, Điểm b, tr. 2–2; legal_unit_id `b1e9febc-3284-4a93-9862-a64978722613`
- Origin: `HIERARCHY_CHILD`; selected: `True`; retrieval rank: `None`

> b) Năng lực, trình độ chuyên môn về công tác xã hội;

#### Expected: `e044e3d1-b910-4d49-ab4e-10b049acc42a` / S11

- Document: `3fb22b9b-ed46-4e04-97e2-b8c854f8252b` — Nghị định 29; `Thong tu quy dinh thuc hanh cong tac xa hoi va cap nhat kien thuc cong.pdf`
- Title/authority/date: not available; Chính phủ; 2026-07-06
- Legal unit: Điều 3, Khoản 2, Điểm c, tr. 2–2; legal_unit_id `f6702837-5d07-4fa3-a547-1a12fd5828a3`
- Origin: `RETRIEVAL`; selected: `True`; retrieval rank: `9`

> c) Kỹ năng thực hành về công tác xã hội;

#### Expected: `aebafad2-e8a0-49e6-82e0-2cd27270e54d` / S1

- Document: `3fb22b9b-ed46-4e04-97e2-b8c854f8252b` — Nghị định 29; `Thong tu quy dinh thuc hanh cong tac xa hoi va cap nhat kien thuc cong.pdf`
- Title/authority/date: not available; Chính phủ; 2026-07-06
- Legal unit: Điều 3, Khoản 2, Điểm d, tr. 2–2; legal_unit_id `6450aff8-08d9-4132-aa89-d899473f22bf`
- Origin: `RETRIEVAL`; selected: `True`; retrieval rank: `1`

> d) Kỹ năng truyền thông, vận động nguồn lực, kết nối thực hiện các hoạt động côngche_06/07/2026tác xã hội;
> đ)PhapKỹ năng phối hợp thực hiện các hoạt động công tác xã hội.
> Vu 3. Nội dung cơ bản thực hành công tác xã hội cụ thể quy định tại Phụ lục thu 01 ban hành kèm theo Thông tư này.

### Actual cited source text

#### Actual: `77d1986c-82a4-4ef3-a215-08e1c2250d9d` / S3

- Document: `3fb22b9b-ed46-4e04-97e2-b8c854f8252b` — Nghị định 29; `Thong tu quy dinh thuc hanh cong tac xa hoi va cap nhat kien thuc cong.pdf`
- Title/authority/date: not available; Chính phủ; 2026-07-06
- Legal unit: Điều 3, Khoản 2, Điểm a, tr. 2–2; legal_unit_id `d0ba484b-147d-4910-b8d0-86850faeb618`
- Origin: `HIERARCHY_CHILD`; selected: `True`; retrieval rank: `None`

> a) Đạo đức nghề nghiệp công tác xã hội; 17:03:43

#### Actual: `bb5ff3eb-1831-4df5-a40f-0b8cfb4444bf` / S4

- Document: `3fb22b9b-ed46-4e04-97e2-b8c854f8252b` — Nghị định 29; `Thong tu quy dinh thuc hanh cong tac xa hoi va cap nhat kien thuc cong.pdf`
- Title/authority/date: not available; Chính phủ; 2026-07-06
- Legal unit: Điều 3, Khoản 2, Điểm b, tr. 2–2; legal_unit_id `b1e9febc-3284-4a93-9862-a64978722613`
- Origin: `HIERARCHY_CHILD`; selected: `True`; retrieval rank: `None`

> b) Năng lực, trình độ chuyên môn về công tác xã hội;

#### Actual: `4d0db85b-6496-47f8-a336-af7cec513cef` / S9

- Document: `3fb22b9b-ed46-4e04-97e2-b8c854f8252b` — Nghị định 29; `Thong tu quy dinh thuc hanh cong tac xa hoi va cap nhat kien thuc cong.pdf`
- Title/authority/date: not available; Chính phủ; 2026-07-06
- Legal unit: Điều 19, Khoản 5, Điểm a, tr. 10–10; legal_unit_id `c3be402e-5c16-419d-a749-f8dc09cc7cc9`
- Origin: `RETRIEVAL`; selected: `True`; retrieval rank: `7`

> a) Kỹ năng cung cấp, thực hiện các dịch vụ công tác Có Có
> xã hội có yêu cầu đơn giản về lý thuyết, phương
> pháp và kỹ năng thực hành theo sự phân công gồm:
> tư vấn, tham vấn, trị liệu, phục hồi chức năng, giáo
> dục, đàm phán, hoà giải, tuyên truyền.

#### Actual: `0b2b4b29-e108-47c8-8bc1-3a774fa455da` / S6

- Document: `3fb22b9b-ed46-4e04-97e2-b8c854f8252b` — Nghị định 29; `Thong tu quy dinh thuc hanh cong tac xa hoi va cap nhat kien thuc cong.pdf`
- Title/authority/date: not available; Chính phủ; 2026-07-06
- Legal unit: Điều 19, Khoản 3, Điểm b, tr. 10–10; legal_unit_id `d30d5cdb-3270-45b0-a4f5-2b2ba0dcb2c5`
- Origin: `RETRIEVAL`; selected: `True`; retrieval rank: `4`

> b) Kỹ năng thực hiện quy trình cung cấp dịch vụ Có Có 17:03:43
> công tác xã hội
> - Tiếp nhận, thu thập thông tin và đánh giá nhu cầu
> trợ giúp của đối tượng. che_06/07/2026
> - XâyPhapdựng kế hoạch trợ giúp đối với đối tượng.
> -VuThực hiện kế hoạch trợ giúp đối tượng.
> thu- Theo dõi, rà soát, đánh giá và điều chỉnh kế hoạch
> trợ giúp.
> - Kết thúc quá trình trợ giúp và lưu trữ hồ sơ.vanthu.pc_Van 4. Kỹ năng truyền thông, vận động nguồn lực,
> kết nối thực hiện các hoạt động công tác xã hội

#### Actual: `aebafad2-e8a0-49e6-82e0-2cd27270e54d` / S1

- Document: `3fb22b9b-ed46-4e04-97e2-b8c854f8252b` — Nghị định 29; `Thong tu quy dinh thuc hanh cong tac xa hoi va cap nhat kien thuc cong.pdf`
- Title/authority/date: not available; Chính phủ; 2026-07-06
- Legal unit: Điều 3, Khoản 2, Điểm d, tr. 2–2; legal_unit_id `6450aff8-08d9-4132-aa89-d899473f22bf`
- Origin: `RETRIEVAL`; selected: `True`; retrieval rank: `1`

> d) Kỹ năng truyền thông, vận động nguồn lực, kết nối thực hiện các hoạt động côngche_06/07/2026tác xã hội;
> đ)PhapKỹ năng phối hợp thực hiện các hoạt động công tác xã hội.
> Vu 3. Nội dung cơ bản thực hành công tác xã hội cụ thể quy định tại Phụ lục thu 01 ban hành kèm theo Thông tư này.

#### Actual: `aa4b26d2-0a3a-4b57-82fd-76531d8d9791` / S2

- Document: `3fb22b9b-ed46-4e04-97e2-b8c854f8252b` — Nghị định 29; `Thong tu quy dinh thuc hanh cong tac xa hoi va cap nhat kien thuc cong.pdf`
- Title/authority/date: not available; Chính phủ; 2026-07-06
- Legal unit: Điều 3, Khoản 2, tr. 2–2; legal_unit_id `0d357c5e-98c5-44ff-9c3f-c95200e8c6cd`
- Origin: `RETRIEVAL`; selected: `True`; retrieval rank: `2`

> 2. Nội dung thực hành công tác xã hội bao gồm:

#### Actual: `c1b373eb-3a7e-423b-bd68-ffd339ff9af2` / S8

- Document: `3fb22b9b-ed46-4e04-97e2-b8c854f8252b` — Nghị định 29; `Thong tu quy dinh thuc hanh cong tac xa hoi va cap nhat kien thuc cong.pdf`
- Title/authority/date: not available; Chính phủ; 2026-07-06
- Legal unit: Điều 19, Khoản 2, Điểm a, tr. 9–9; legal_unit_id `d0175758-6d11-44bc-b36a-46b7baa8e35d`
- Origin: `RETRIEVAL`; selected: `True`; retrieval rank: `6`

> a) Kỹ năng, nghiệp vụ công tác xã hội trong phạm
> Có Có
> vi nội dung thực hành.

#### Actual: `98d4b7c3-ae85-4422-8abd-d18fb2962fc2` / S10

- Document: `3fb22b9b-ed46-4e04-97e2-b8c854f8252b` — Nghị định 29; `Thong tu quy dinh thuc hanh cong tac xa hoi va cap nhat kien thuc cong.pdf`
- Title/authority/date: not available; Chính phủ; 2026-07-06
- Legal unit: Điều 19, Khoản 2, Điểm e, tr. 9–9; legal_unit_id `56e97005-f7a5-49ba-a33c-ebf1a1a8d876`
- Origin: `RETRIEVAL`; selected: `True`; retrieval rank: `8`

> e) Kỹ năng thực hiện các hoạt động chuyên môn
> phòng ngừa, can thiệp, trị liệu, chăm sóc, phục hồi,
> Không áp
> hỗ trợ phát triển, tư vấn, tham vấn, hỗ trợ tâm lý Có
> dụng
> và các hoạt động công tác xã hội khác trong phạm
> vi nội dung thực hành.

### Unexpected-source deterministic comparison

- Document relationship: `SAME_DOCUMENT_SET`
- Article/clause relationship: `SAME_ARTICLE_PRESENT`
- Overlapping legal proposition: **PENDING HUMAN REVIEW**
- Differing legal proposition: **PENDING HUMAN REVIEW**
- Review label: **INSUFFICIENT FOR AUTOMATIC DETERMINATION**

### Multi-evidence review

Required pieces: 4; selected: 4; cited: 3. Whether the answer combines them correctly is **PENDING HUMAN REVIEW**.

### Selected context inventory

| Source | Chunk | Origin | Rank | Legal unit | Text preview |
|---|---|---|---:|---|---|
| `S1` | `aebafad2-e8a0-49e6-82e0-2cd27270e54d` | `RETRIEVAL` | 1 | Điều 3, Khoản 2, Điểm d, tr. 2–2 | d) Kỹ năng truyền thông, vận động nguồn lực, kết nối thực hiện các hoạt động côngche_06/07/2026tác xã hội; đ)PhapKỹ năng phối hợp thực hiện các hoạt động công tác xã hội. Vu 3. Nội dung cơ bản thực hành công tác xã hội … |
| `S2` | `aa4b26d2-0a3a-4b57-82fd-76531d8d9791` | `RETRIEVAL` | 2 | Điều 3, Khoản 2, tr. 2–2 | 2. Nội dung thực hành công tác xã hội bao gồm: |
| `S3` | `77d1986c-82a4-4ef3-a215-08e1c2250d9d` | `HIERARCHY_CHILD` | None | Điều 3, Khoản 2, Điểm a, tr. 2–2 | a) Đạo đức nghề nghiệp công tác xã hội; 17:03:43 |
| `S4` | `bb5ff3eb-1831-4df5-a40f-0b8cfb4444bf` | `HIERARCHY_CHILD` | None | Điều 3, Khoản 2, Điểm b, tr. 2–2 | b) Năng lực, trình độ chuyên môn về công tác xã hội; |
| `S5` | `cf38602e-3071-4e35-b4f5-532752cf0b86` | `RETRIEVAL` | 3 | Điều 4, Khoản 5, tr. 2–2 | 5. Trong quá trình thực hành công tác xã hội, người thực hành được tham gia tập huấn các quy định pháp luật về công tác xã hội, an sinh xã hội, chuyên môn về công tác xã hội, đạo đức nghề nghiệp công tác xã hội, kỹ năng… |
| `S6` | `0b2b4b29-e108-47c8-8bc1-3a774fa455da` | `RETRIEVAL` | 4 | Điều 19, Khoản 3, Điểm b, tr. 10–10 | b) Kỹ năng thực hiện quy trình cung cấp dịch vụ Có Có 17:03:43 công tác xã hội - Tiếp nhận, thu thập thông tin và đánh giá nhu cầu trợ giúp của đối tượng. che_06/07/2026 - XâyPhapdựng kế hoạch trợ giúp đối với đối tượng… |
| `S7` | `fac9f444-c203-4ef7-aa90-acdba56a486d` | `RETRIEVAL` | 5 | Điều 3, Khoản 1, tr. 1–2 | 1. Thực hành công tác xã hội được thực hiện tại các đơn vị, cơ sở có cung cấp dịch vụ công tác xã hội theo quy định tại điểm b khoản 2 Điều 35 Nghị định số 110/2024/NĐ-CP (sau đây gọi tắt là cơ sở thực hành công tác xã … |
| `S8` | `c1b373eb-3a7e-423b-bd68-ffd339ff9af2` | `RETRIEVAL` | 6 | Điều 19, Khoản 2, Điểm a, tr. 9–9 | a) Kỹ năng, nghiệp vụ công tác xã hội trong phạm Có Có vi nội dung thực hành. |
| `S9` | `4d0db85b-6496-47f8-a336-af7cec513cef` | `RETRIEVAL` | 7 | Điều 19, Khoản 5, Điểm a, tr. 10–10 | a) Kỹ năng cung cấp, thực hiện các dịch vụ công tác Có Có xã hội có yêu cầu đơn giản về lý thuyết, phương pháp và kỹ năng thực hành theo sự phân công gồm: tư vấn, tham vấn, trị liệu, phục hồi chức năng, giáo dục, đàm ph… |
| `S10` | `98d4b7c3-ae85-4422-8abd-d18fb2962fc2` | `RETRIEVAL` | 8 | Điều 19, Khoản 2, Điểm e, tr. 9–9 | e) Kỹ năng thực hiện các hoạt động chuyên môn phòng ngừa, can thiệp, trị liệu, chăm sóc, phục hồi, Không áp hỗ trợ phát triển, tư vấn, tham vấn, hỗ trợ tâm lý Có dụng và các hoạt động công tác xã hội khác trong phạm vi … |
| `S11` | `e044e3d1-b910-4d49-ab4e-10b049acc42a` | `RETRIEVAL` | 9 | Điều 3, Khoản 2, Điểm c, tr. 2–2 | c) Kỹ năng thực hành về công tác xã hội; |
| `S12` | `5face032-faa3-4b38-a5c8-35072a34adda` | `RETRIEVAL` | 10 | Điều 6, Khoản 1, tr. 3–3 | 1. Cơ sở tổ chức việc thực hành công tác xã hội được thực hiện theo Điều 36 Nghị định số 110/2024/NĐ-CP. Trường hợp có nhiều người hướng dẫn thực hành cho một người thực hành 17:03:43 thì người đứng đầu cơ sở thực hành … |

**Human judgment required:** answer support, citation acceptability, source mismatch, qualification, unsupported propositions, severity, and final decision. No field is pre-filled.

---

## Human activation gate

- No reviewed case contains a confirmed unsupported legal proposition.
- No unexpected-source case is judged materially misleading.
- Qualified-answer wording is accepted or determined non-blocking.
- No V3 answerability gain is a hallucinated gain.
- No BLOCKER decision remains unresolved.
- UNCLEAR decisions receive expert legal review before activation.

An expected-source mismatch does not automatically fail V3. Frozen datasets and metrics remain unchanged. V3 is not ready for activation until the editable review form contains no unresolved BLOCKER and every UNCLEAR case has received expert legal review.

## Existing UI inspection

Open `http://localhost:5173/evaluation`, select **Evaluation V2**, and open a queued case to inspect frozen expected/measured artifacts. The existing drawer can launch a real rerun, but the current production default is V2; do not treat such a rerun as a V3 review result. Use this packet for the recorded V3 output. The chunk-detail drawer can inspect exact chunk metadata. No UI change is required.
