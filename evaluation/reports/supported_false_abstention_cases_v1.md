# Supported Complete-Context False Abstentions V1

Dataset SHA-256: `ba102b9b05e28633fd0475da558abd1f647e808749a2025c15d5c1be315ae842`

Derived cases: **4**. Frozen ground truth was not changed.

## v2_bank_scope_ratios

- Category: `MULTI_EVIDENCE`
- Support mode: `DIRECT_MULTI`
- Human source review: `CLEAR_SUPPORT`
- Question: Thông tư 40/2026/TT-NHNN điều chỉnh năm nhóm hạn chế, giới hạn và tỷ lệ an toàn chính nào?
- Context: 1750 / 4096 tokens
- Taxonomy: `EVIDENCE_PRESENT_BUT_DISTRIBUTED`, `MULTI_CHUNK_SYNTHESIS_REQUIRED`, `HIERARCHY_CHILD_SOURCE_CONFUSION`, `OVER_CONSERVATIVE_PROMPT_RULE`, `STATUS_PROTOCOL_BIAS`
- Review rationale: The five requested groups are stated verbatim across five selected chunks; four are hierarchy children and one is a retrieval anchor.

Expected evidence excerpts:

- `S3` / `283fc8f6-8d90-4a6b-8a8c-d7f31d8935d2` / `HIERARCHY_CHILD`: b) Tỷ lệ khả năng chi trả;
- `S4` / `5faec617-7237-4dc8-a01a-bc4ade33ac31` / `HIERARCHY_CHILD`: c) Tỷ lệ nguồn vốn ngắn hạn được sử dụng để cho vay trung hạn và dài hạn;
- `S5` / `5c3fd83c-0fb0-4cd7-9d52-b346c203c28a` / `HIERARCHY_CHILD`: d) Hạn chế, giới hạn cho vay;
- `S6` / `30e14c4c-d8fd-4d68-9382-4d96bef43392` / `HIERARCHY_CHILD`: đ) Tỷ lệ tổng mức nhận tiền gửi so với vốn chủ sở hữu.
- `S9` / `48109bc6-e5cb-4c25-89be-b6ed2d85e066` / `RETRIEVAL`: a) Tỷ lệ an toàn vốn tối thiểu;

Current-prompt repeats:

- Run 1: `INSUFFICIENT_EVIDENCE`; validation `PASS`; citations none; 10649.8 ms.
- Run 2: `INSUFFICIENT_EVIDENCE`; validation `PASS`; citations none; 689.0 ms.
- Run 3: `INSUFFICIENT_EVIDENCE`; validation `PASS`; citations none; 678.3 ms.

The JSON artifact contains every selected source, full text, metadata, provenance, ranks, origins, raw provider output, and citations.

## v2_bank_below_80_measures

- Category: `PARTIAL_SUPPORT`
- Support mode: `CONDITIONAL`
- Human source review: `CLEAR_SUPPORT`
- Question: Khi giá trị thực của vốn điều lệ xuống dưới 80% vốn pháp định, chi nhánh Ngân hàng Nhà nước có thể áp dụng những nhóm biện pháp nào?
- Context: 1399 / 4096 tokens
- Taxonomy: `LEGAL_EXCEPTION_OR_CONDITION`, `OVER_CONSERVATIVE_PROMPT_RULE`, `STATUS_PROTOCOL_BIAS`
- Review rationale: One selected chunk directly enumerates the measure groups and the below-80% condition; a qualified answer is possible without outside facts.

Expected evidence excerpts:

- `S4` / `31b2230f-aa0e-47e3-86a7-2c2f3d162c97` / `RETRIEVAL`: d) Tùy theo mức độ giảm giá trị thực của vốn điều lệ so với mức vốn pháp định, Ngân hàng Nhà nước chi nhánh Khu vực quyết định cụ thể các biện pháp xử lý sau đây đối với quỹ tín dụng nhân dân: (i) Xem xét áp dụng các biện pháp khi giá trị thực của vốn điều lệ giảm xuống dưới 80% của mức vốn pháp định, bao gồm: Hạn chế chia lãi; Hạn chế việc mở rộng phạm vi, quy mô và địa bàn hoạt động; Hạn chế, đình chỉ, tạm đình chỉ một số nội dung hoạt động; Yêu cầu Quỹ tín dụng nhân dân tăng vốn điều lệ; Quyết định giới hạn tăng trưởng tín dụng trong những trường hợp cần thiết bảo đảm an toàn cho quỹ tín dụng nhân dân và hệ thống các tổ chức tín dụng; Áp dụng một hoặc một số tỷ lệ an toàn chặt chẽ hơn mức quy định; (ii) Xem xét áp dụng can thiệp sớm, kiểm soát đặc biệt, cơ cấu lại theo quy định của pháp luật.

Current-prompt repeats:

- Run 1: `INSUFFICIENT_EVIDENCE`; validation `PASS`; citations none; 1421.6 ms.
- Run 2: `INSUFFICIENT_EVIDENCE`; validation `PASS`; citations none; 704.3 ms.
- Run 3: `INSUFFICIENT_EVIDENCE`; validation `PASS`; citations none; 730.8 ms.

The JSON artifact contains every selected source, full text, metadata, provenance, ranks, origins, raw provider output, and citations.

## v2_civil_scope

- Category: `DOCUMENT_DISAMBIGUATION`
- Support mode: `DIRECT_SINGLE`
- Human source review: `CLEAR_SUPPORT`
- Question: Văn bản hợp nhất 10/2026/VBHN-NĐ-BNV quy định phạm vi nào?
- Context: 4049 / 4096 tokens
- Taxonomy: `LONG_CONTEXT_INSTRUCTION_FADING`, `EVIDENCE_ORDERING_EFFECT`, `OVER_CONSERVATIVE_PROMPT_RULE`, `STATUS_PROTOCOL_BIAS`
- Review rationale: S1 directly names the consolidated instrument and its scope; the remaining long context is mostly distractor material.

Expected evidence excerpts:

- `S1` / `7239888d-6b34-417a-bb1d-4da08ebb5b67` / `RETRIEVAL`: VĂN BẢN HỢP NHẤT CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM Số: 10 /2026/VBHN-NĐ-BNV Độc lập - Tự do - Hạnh phúc Hà Nội, ngày 14 tháng 8 năm 2026 NGHỊ ĐỊNH Quy định về tuyển dụng, sử dụng và quản lý công chức Nghị định số 170/2025/NĐ-CP ngày 30 tháng 6 năm 2025 của Chính phủ quy định về tuyển dụng, sử dụng và quản lý công chức, có hiệu lực kể từ ngày 01 tháng 7 năm 2025, được sửa đổi, bổ sung bởi: Nghị định số 300/2026/NĐ-CP ngày 29 tháng 7 năm 2026 của Chính phủ sửa đổi, bổ sung một số điều của Nghị định số 170/2025/NĐ-CP ngày 30 tháng 6 năm 2025 của Chính phủ quy định về tuyển dụng, sử dụng và quản lý công chức, có hiệu lực kể từ ngày 01 tháng 8 năm 2026. Căn cứ Luật Tổ chức Chính phủ ngày 18 tháng 02 năm 2025; Căn cứ Luật Cán bộ, công chức ngày 24 tháng 6 năm 2025; Theo đề nghị của Bộ trưởng Bộ Nội vụ1; Chính phủ ban hành Nghị định quy định về tuyển dụng, sử dụng và quản lý công chức.

Current-prompt repeats:

- Run 1: `INSUFFICIENT_EVIDENCE`; validation `PASS`; citations none; 2303.6 ms.
- Run 2: `INSUFFICIENT_EVIDENCE`; validation `PASS`; citations none; 690.9 ms.
- Run 3: `INSUFFICIENT_EVIDENCE`; validation `PASS`; citations none; 711.7 ms.

The JSON artifact contains every selected source, full text, metadata, provenance, ranks, origins, raw provider output, and citations.

## v2_cross_document_effective_dates

- Category: `MULTI_DOCUMENT_EVIDENCE`
- Support mode: `COMPOSITIONAL`
- Human source review: `CLEAR_SUPPORT`
- Question: So sánh ngày hiệu lực của Thông tư về thực hành công tác xã hội và Thông tư 40/2026/TT-NHNN: văn bản nào có hiệu lực trước?
- Context: 1545 / 4096 tokens
- Taxonomy: `EVIDENCE_PRESENT_BUT_DISTRIBUTED`, `MULTI_CHUNK_SYNTHESIS_REQUIRED`, `OVER_CONSERVATIVE_PROMPT_RULE`, `STATUS_PROTOCOL_BIAS`
- Review rationale: Two selected chunks provide the two dates; answering requires only comparing 25 August 2026 with 1 November 2026.

Expected evidence excerpts:

- `S2` / `fc3ce1a3-88e0-46dd-a694-d3ab54512d68` / `RETRIEVAL`: 1. Thông tư này có hiệu lực thi hành kể từ ngày 01 tháng 11 năm 2026.
- `S5` / `70100659-7c0f-4617-ad9f-7ce2a3b44f2e` / `RETRIEVAL`: Điều 17. Hiệu lực thi hành Thông tư này có hiệu lực từ ngày 25 tháng 8 năm 2026.

Current-prompt repeats:

- Run 1: `ANSWERABLE`; validation `PASS`; citations ['S5', 'S2']; 2768.3 ms.
- Run 2: `ANSWERABLE`; validation `PASS`; citations ['S5', 'S2']; 2014.4 ms.
- Run 3: `ANSWERABLE`; validation `PASS`; citations ['S5', 'S2']; 1994.3 ms.

The JSON artifact contains every selected source, full text, metadata, provenance, ranks, origins, raw provider output, and citations.
