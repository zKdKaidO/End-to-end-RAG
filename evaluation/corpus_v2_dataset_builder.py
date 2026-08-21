"""Build the grounded Legal Evaluation V2 dataset from persisted Corpus V2 chunks."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.db.database import SessionLocal
from evaluation.dataset_validator import load_dataset, validate_dataset


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "evaluation" / "corpus" / "legal_corpus_v2_manifest.json"
DATASET_PATH = ROOT / "evaluation" / "datasets" / "legal_eval_v2.json"
REVIEW_PATH = ROOT / "evaluation" / "reports" / "legal_eval_v2_review.md"
FREEZE_PATH = ROOT / "evaluation" / "reports" / "legal_eval_v2_dataset_freeze.md"


@dataclass(frozen=True)
class Evidence:
    document_key: str
    phrase: str


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    category: str
    question: str
    solutions: tuple[tuple[Evidence, ...], ...] = ()
    filter_documents: tuple[str, ...] = ()
    notes: str | None = None
    answerable: bool = True


def ev(document_key: str, phrase: str) -> Evidence:
    return Evidence(document_key, phrase)


SOCIAL = "social_work_practice_2026"
BANK = "people_credit_fund_safety_40_2026"
CIVIL = "civil_servants_consolidated_10_2026"


CASES: tuple[CaseSpec, ...] = (
    # Social-work instrument: 18 answerable cases.
    CaseSpec("v2_social_scope", "MULTI_EVIDENCE", "Thông tư về thực hành công tác xã hội quy định chi tiết ba nhóm nội dung nào của Nghị định 110/2024/NĐ-CP?", ((ev(SOCIAL, "Thực hành công tác xã hội tại điểm b khoản 1 Điều 45"), ev(SOCIAL, "Cập nhật kiến thức công tác xã hội tại Điều 34"), ev(SOCIAL, "Hướng dẫn xây dựng khung chương trình đào tạo, bồi dưỡng cập nhật kiến thức công tác xã hội tại khoản 2 Điều 37")),), notes="Complete answer requires all three scope items."),
    CaseSpec("v2_social_applicable_groups", "MULTI_EVIDENCE", "Bốn nhóm đối tượng nào thuộc phạm vi áp dụng của Thông tư về thực hành và cập nhật kiến thức công tác xã hội?", ((ev(SOCIAL, "Cơ sở thực hành công tác xã hội"), ev(SOCIAL, "Cơ sở cập nhật kiến thức công tác xã hội"), ev(SOCIAL, "Người thực hành công tác xã hội, người hành nghề công tác xã hội"), ev(SOCIAL, "Các cơ quan, tổ chức, cá nhân có liên quan")),), notes="Complete answer requires four separately chunked groups."),
    CaseSpec("v2_social_practice_content", "MULTI_EVIDENCE", "Nội dung thực hành công tác xã hội bao gồm những nhóm năng lực và kỹ năng nào?", ((ev(SOCIAL, "Đạo đức nghề nghiệp công tác xã hội"), ev(SOCIAL, "Năng lực, trình độ chuyên môn về công tác xã hội"), ev(SOCIAL, "Kỹ năng thực hành về công tác xã hội"), ev(SOCIAL, "Kỹ năng truyền thông, vận động nguồn lực")),), notes="The fourth chunk also contains the coordination-skill item."),
    CaseSpec("v2_social_university_duration", "SAME_ARTICLE_NUMBER", "Theo Điều 4 của Thông tư về công tác xã hội, người có trình độ đại học trở lên phải thực hành tối thiểu bao lâu và bao nhiêu giờ?", ((ev(SOCIAL, "trình độ đại học trở lên từ đủ 12 tháng"),),)),
    CaseSpec("v2_social_college_duration", "SEMANTIC_PARAPHRASE", "Người có trình độ cao đẳng cần hoàn thành thời lượng thực hành công tác xã hội thế nào?", ((ev(SOCIAL, "trình độ cao đẳng từ đủ 09 tháng"),),)),
    CaseSpec("v2_social_intermediate_duration", "KEYWORD_IDENTIFIER", "Mốc 06 tháng và 500 giờ tại Điều 4 áp dụng cho trình độ nào?", ((ev(SOCIAL, "trình độ trung cấp từ đủ 06 tháng"),),)),
    CaseSpec("v2_social_training_sessions", "DIRECT_FACT", "Trong thời gian thực hành, tổng thời lượng tập huấn là bao nhiêu buổi và mỗi buổi bao nhiêu tiết?", ((ev(SOCIAL, "tổng thời lượng là 10 buổi (mỗi buổi 04 tiết học"),),)),
    CaseSpec("v2_social_plan_deadline", "DIRECT_FACT", "Cơ sở thực hành phải xây dựng kế hoạch hướng dẫn thực hành trước ngày nào hằng năm?", ((ev(SOCIAL, "xây dựng kế hoạch hướng dẫn thực hành trước ngày 15 tháng 01 hằng năm"),),)),
    CaseSpec("v2_social_plan_submission_filter", "DOCUMENT_FILTER", "Theo Thông tư về công tác xã hội, kế hoạch hướng dẫn thực hành phải gửi cơ quan chuyên môn về y tế cấp tỉnh trước ngày nào?", ((ev(SOCIAL, "trước ngày 01 tháng 02 hằng năm"),),), (SOCIAL,)),
    CaseSpec("v2_social_multiple_instructors", "SEMANTIC_PARAPHRASE", "Khi một người thực hành có nhiều người hướng dẫn, người đứng đầu cơ sở phải phân công ra sao?", ((ev(SOCIAL, "phải phân công rõ phạm vi hướng dẫn và thời gian hướng dẫn thực hành cụ thể"),),)),
    CaseSpec("v2_social_program_review", "DEEPER_RANK", "Chương trình và tài liệu cập nhật kiến thức công tác xã hội phải được rà soát định kỳ tối thiểu bao lâu một lần?", ((ev(SOCIAL, "được rà soát, cập nhật định kỳ tối thiểu 03 năm một lần"),),)),
    CaseSpec("v2_social_course_modes", "SAME_TERM_DIFFERENT_DOCUMENT", "Khóa bồi dưỡng ngắn hạn về công tác xã hội có thể tổ chức theo những hình thức nào?", ((ev(SOCIAL, "Hình thức tổ chức: trực tiếp hoặc trực tuyến hoặc trực tiếp kết hợp trực tuyến"),),)),
    CaseSpec("v2_social_foreign_training", "DIRECT_FACT", "Người hành nghề có thể dùng khóa đào tạo ở nước ngoài để cập nhật kiến thức công tác xã hội không?", ((ev(SOCIAL, "tham gia các khóa đào tạo, bồi dưỡng ở nước ngoài về công tác xã hội"),),)),
    CaseSpec("v2_social_research_credit", "DEEPER_RANK", "Những hoạt động nghiên cứu, sáng kiến hoặc bài báo nào có thể được tính là cập nhật kiến thức công tác xã hội?", ((ev(SOCIAL, "chủ trì hoặc tham gia thực hiện nhiệm vụ khoa học, công nghệ và đổi mới sáng tạo"),),)),
    CaseSpec("v2_social_thesis_update", "KEYWORD_IDENTIFIER", "Việc hướng dẫn luận văn, luận án được tính là hình thức cập nhật kiến thức khi đáp ứng điều kiện gì?", ((ev(SOCIAL, "tham gia hướng dẫn luận văn, luận án"),),)),
    CaseSpec("v2_social_confidentiality", "DIRECT_FACT", "Người thực hành phải bảo đảm an toàn và giữ bí mật thông tin cho những đối tượng nào?", ((ev(SOCIAL, "Bảo đảm an toàn cho đối tượng được cung cấp dịch vụ công tác xã hội"),),)),
    CaseSpec("v2_social_confirmation_reporting", "DEEPER_RANK", "Sau khi cấp giấy xác nhận thực hành, cơ sở phải gửi danh sách đến cơ quan chuyên môn về y tế trong bao nhiêu ngày làm việc?", ((ev(SOCIAL, "Trong thời gian 03 ngày làm việc, kể từ ngày"),),)),
    CaseSpec("v2_social_effective_transition", "MULTI_EVIDENCE", "Thông tư về công tác xã hội có hiệu lực ngày nào và người đã có giấy xác nhận thực hành có phải thực hành lại không?", ((ev(SOCIAL, "có hiệu lực từ ngày 25 tháng 8 năm 2026"), ev(SOCIAL, "đã được cấp Giấy xác nhận quá trình thực hành công tác xã hội")),), notes="Requires effective-date and transition evidence."),

    # People-credit-fund safety instrument: 18 answerable cases.
    CaseSpec("v2_bank_scope_ratios", "MULTI_EVIDENCE", "Thông tư 40/2026/TT-NHNN điều chỉnh năm nhóm hạn chế, giới hạn và tỷ lệ an toàn chính nào?", ((ev(BANK, "Tỷ lệ an toàn vốn tối thiểu"), ev(BANK, "Tỷ lệ khả năng chi trả"), ev(BANK, "Tỷ lệ nguồn vốn ngắn hạn được sử dụng để cho vay trung hạn và dài hạn"), ev(BANK, "Hạn chế, giới hạn cho vay"), ev(BANK, "Tỷ lệ tổng mức nhận tiền gửi so với vốn chủ sở hữu")),), notes="Complete answer requires all five scope items."),
    CaseSpec("v2_bank_special_control_exception", "DIRECT_FACT", "Quỹ tín dụng nhân dân được kiểm soát đặc biệt có phải tuân thủ các Điều 136, 137, 138 và khoản 3 Điều 144 không?", ((ev(BANK, "được kiểm soát đặc biệt không phải tuân thủ"),),)),
    CaseSpec("v2_bank_actual_capital_formula", "SEMANTIC_PARAPHRASE", "Giá trị thực của vốn điều lệ được tính từ vốn điều lệ, lợi nhuận và lỗ lũy kế như thế nào?", ((ev(BANK, "được xác định bằng vốn điều lệ cộng lợi nhuận lũy kế chưa phân phối, trừ lỗ lũy kế chưa xử lý"),),)),
    CaseSpec("v2_bank_low_capital_report", "DEEPER_RANK", "Khi giá trị thực của vốn điều lệ thấp hơn vốn pháp định, quỹ phải báo cáo kèm phương án xử lý trong tối đa bao nhiêu ngày?", ((ev(BANK, "Trong thời gian tối đa 30 ngày kể từ ngày giá trị thực của vốn điều lệ giảm thấp hơn mức vốn pháp định"),),)),
    CaseSpec("v2_bank_below_80_measures", "PARTIAL_SUPPORT", "Khi giá trị thực của vốn điều lệ xuống dưới 80% vốn pháp định, chi nhánh Ngân hàng Nhà nước có thể áp dụng những nhóm biện pháp nào?", ((ev(BANK, "giá trị thực của vốn điều lệ giảm xuống dưới 80% của mức vốn pháp định"),),), notes="One long chunk contains the measured list; answer quality still requires careful grounding."),
    CaseSpec("v2_bank_min_capital_ratio_filter", "DOCUMENT_FILTER", "Theo Thông tư 40/2026/TT-NHNN, tỷ lệ an toàn vốn tối thiểu quỹ tín dụng nhân dân phải duy trì là bao nhiêu?", ((ev(BANK, "phải duy trì tỷ lệ an toàn vốn tối thiểu 8%"),),), (BANK,)),
    CaseSpec("v2_bank_zero_risk_assets", "KEYWORD_IDENTIFIER", "Tiền mặt và tiền gửi tại Ngân hàng Nhà nước thuộc nhóm tài sản có hệ số rủi ro bao nhiêu phần trăm?", ((ev(BANK, "Nhóm tài sản có hệ số rủi ro 0% bao gồm"),),)),
    CaseSpec("v2_bank_fifty_risk_assets", "SAME_ARTICLE_NUMBER", "Theo Điều 8 của Thông tư 40, khoản vay được bảo đảm toàn bộ bằng nhà ở hoặc quyền sử dụng đất có hệ số rủi ro bao nhiêu?", ((ev(BANK, "Nhóm tài sản có hệ số rủi ro 50%"),),)),
    CaseSpec("v2_bank_liquidity_100", "DIRECT_FACT", "Quỹ tín dụng nhân dân phải duy trì tỷ lệ khả năng chi trả cho ngày làm việc tiếp theo và bảy ngày tiếp theo ở mức tối thiểu nào?", ((ev(BANK, "trong khoảng thời gian 7 (bảy) ngày làm việc tiếp theo tối thiểu bằng 100%"),),)),
    CaseSpec("v2_bank_short_term_funding_30", "DIRECT_FACT", "Tỷ lệ nguồn vốn ngắn hạn dùng để cho vay trung và dài hạn tối đa là bao nhiêu?", ((ev(BANK, "tối đa là 30%"),),)),
    CaseSpec("v2_bank_ratio_zero_condition", "SEMANTIC_PARAPHRASE", "Khi tổng dư nợ trung, dài hạn nhỏ hơn tổng nguồn vốn trung, dài hạn thì tỷ lệ nguồn vốn ngắn hạn được tính bằng bao nhiêu?", ((ev(BANK, "tỷ lệ này có giá trị bằng 0"),),)),
    CaseSpec("v2_bank_deposit_multiple", "DIRECT_FACT", "Tổng mức nhận tiền gửi của quỹ tín dụng nhân dân không được vượt quá bao nhiêu lần vốn chủ sở hữu?", ((ev(BANK, "không được vượt quá 20 lần"),),)),
    CaseSpec("v2_bank_board_loan_threshold", "DEEPER_RANK", "Khoản cho vay đối với người thẩm định hoặc người xét duyệt phải được Hội đồng quản trị thông qua từ mức giá trị nào?", ((ev(BANK, "có giá trị từ 100 triệu đồng trở lên"),),)),
    CaseSpec("v2_bank_member_legal_entity_cap", "DOCUMENT_DISAMBIGUATION", "Dư nợ cho vay tối đa đối với một thành viên là pháp nhân được giới hạn theo các khoản nào của pháp nhân đó tại quỹ?", ((ev(BANK, "không được vượt quá tổng số vốn góp và số dư tiền gửi của pháp nhân đó"),),)),
    CaseSpec("v2_bank_nonmember_cap", "DOCUMENT_DISAMBIGUATION", "Dư nợ của khách hàng không phải thành viên bị giới hạn theo số dư nào?", ((ev(BANK, "không phải là thành viên không được vượt quá số dư của hợp đồng tiền gửi, sổ tiết kiệm"),),)),
    CaseSpec(
        "v2_bank_loan_limit_exceptions",
        "MULTI_EVIDENCE",
        "Hai trường hợp nào không áp dụng giới hạn cho vay tại điểm b khoản 1 Điều 12?",
        ((
            ev(BANK, "Khoản cho vay từ nguồn vốn ủy thác"),
            ev(BANK, "được bảo đảm toàn bộ bằng tiền gửi tại chính quỹ tín dụng nhân dân"),
        ),),
    ),
    CaseSpec("v2_bank_risk_of_illiquidity", "KEYWORD_IDENTIFIER", "Mức thiếu hụt và thời gian liên tục nào làm quỹ bị coi là có nguy cơ mất khả năng chi trả?", ((ev(BANK, "thiếu hụt Tài sản “Có” có thể thanh toán ngay ở mức 20% trở lên"),),)),
    CaseSpec(
        "v2_bank_illiquidity_reporting",
        "MULTI_EVIDENCE",
        "Khi nào quỹ được coi là mất khả năng chi trả và khi đó phải báo cáo, thông báo cho những cơ quan nào?",
        ((
            ev(BANK, "không thực hiện thanh toán nghĩa vụ nợ trong thời gian 01 tháng"),
            ev(BANK, "phải kịp thời báo cáo với Ngân hàng Nhà nước chi nhánh Khu vực và thông báo cho Ngân hàng Hợp tác xã chi nhánh"),
        ),),
    ),

    # Consolidated civil-service instrument: 18 answerable cases.
    CaseSpec("v2_civil_scope", "DOCUMENT_DISAMBIGUATION", "Văn bản hợp nhất 10/2026/VBHN-NĐ-BNV quy định phạm vi nào?", ((ev(CIVIL, "quy định về tuyển dụng, sử dụng và quản lý công chức"),),)),
    CaseSpec("v2_civil_training_nondiscrimination", "SAME_ARTICLE_NUMBER", "Theo Điều 4 của văn bản về công chức, điều kiện dự tuyển có được phân biệt loại hình đào tạo không?", ((ev(CIVIL, "không được phân biệt loại hình đào tạo"),),)),
    CaseSpec("v2_civil_hard_area_commitment", "DIRECT_FACT", "Người cam kết tình nguyện làm việc ở vùng đặc biệt khó khăn phải cam kết tối thiểu bao nhiêu năm để thuộc nhóm xét tuyển?", ((ev(CIVIL, "tình nguyện làm việc từ đủ 05 năm trở lên"),),)),
    CaseSpec("v2_civil_priority_75", "KEYWORD_IDENTIFIER", "Anh hùng Lực lượng vũ trang, Anh hùng Lao động và thương binh được cộng bao nhiêu điểm ưu tiên tuyển dụng?", ((ev(CIVIL, "Được cộng 7,5 điểm"),),)),
    CaseSpec("v2_civil_priority_5", "NEAR_DUPLICATE_EVIDENCE", "Người dân tộc thiểu số và các nhóm sĩ quan, quân nhân nêu tại Điều 6 được cộng bao nhiêu điểm?", ((ev(CIVIL, "Được cộng 5 điểm vào kết quả điểm thi hoặc xét nghiệp vụ chuyên ngành"),),), notes="Distinguishes this near-parallel priority clause from the 7.5-point clause."),
    CaseSpec("v2_civil_council_size", "DIRECT_FACT", "Hội đồng tuyển dụng công chức có bao nhiêu thành viên?", ((ev(CIVIL, "Hội đồng tuyển dụng có 05 hoặc 07 thành viên"),),)),
    CaseSpec("v2_civil_project_exam_time", "DEEPER_RANK", "Tổng thời gian chuẩn bị và bảo vệ Đề án trong thi tuyển không được vượt quá bao nhiêu phút?", ((ev(CIVIL, "không quá 90 phút"),),)),
    CaseSpec("v2_civil_exam_pass_score", "DIRECT_FACT", "Điểm thi nghiệp vụ chuyên ngành tối thiểu để trúng tuyển kỳ thi công chức là bao nhiêu?", ((ev(CIVIL, "điểm thi nghiệp vụ chuyên ngành đạt từ 50 điểm trở lên"),),)),
    CaseSpec("v2_civil_application_window", "DIRECT_FACT", "Thời hạn nhận Phiếu đăng ký dự tuyển công chức là bao nhiêu ngày?", ((ev(CIVIL, "Thời hạn nhận Phiếu đăng ký dự tuyển là 30 ngày"),),)),
    CaseSpec("v2_civil_result_notice", "DEEPER_RANK", "Sau quyết định phê duyệt kết quả trúng tuyển, Hội đồng tuyển dụng phải công khai và gửi thông báo trong bao nhiêu ngày làm việc?", ((ev(CIVIL, "Chậm nhất là 02 ngày làm việc kể từ ngày có quyết định phê duyệt kết quả trúng tuyển"),),)),
    CaseSpec("v2_civil_file_completion", "DIRECT_FACT", "Người trúng tuyển phải hoàn thiện hồ sơ trong bao nhiêu ngày kể từ ngày danh sách được công khai?", ((ev(CIVIL, "Chậm nhất là 15 ngày kể từ ngày danh sách trúng tuyển được công khai"),),)),
    CaseSpec("v2_civil_start_work", "DIRECT_FACT", "Người được tuyển dụng phải đến nhận việc trong bao nhiêu ngày kể từ khi nhận quyết định tuyển dụng?", ((ev(CIVIL, "Chậm nhất là 15 ngày kể từ ngày nhận được quyết định tuyển dụng"),),)),
    CaseSpec("v2_civil_secondment_duration", "SEMANTIC_PARAPHRASE", "Thời gian biệt phái công chức thông thường tối đa là bao lâu?", ((ev(CIVIL, "Thời gian biệt phái công chức không quá 03 năm"),),)),
    CaseSpec("v2_civil_appointment_term", "SAME_TERM_DIFFERENT_DOCUMENT", "Mỗi lần bổ nhiệm chức vụ lãnh đạo, quản lý công chức thường có thời hạn bao lâu?", ((ev(CIVIL, "Thời hạn giữ chức vụ lãnh đạo, quản lý cho mỗi lần bổ nhiệm là 05 năm"),),)),
    CaseSpec("v2_civil_rotation_duration", "DEEPER_RANK", "Một lần luân chuyển công chức kéo dài ít nhất bao nhiêu năm hoặc tháng?", ((ev(CIVIL, "Thời gian luân chuyển ít nhất 3 năm (36 tháng)"),),)),
    CaseSpec("v2_civil_severance_half_month", "DIRECT_FACT", "Trường hợp tự nguyện thôi việc thuộc điểm a được trợ cấp bao nhiêu tháng tiền lương cho mỗi năm làm việc?", ((ev(CIVIL, "mỗi năm làm việc được trợ cấp một nửa tháng tiền lương"),),)),
    CaseSpec("v2_civil_retirement_notice_filter", "DOCUMENT_FILTER", "Theo văn bản hợp nhất về công chức, thông báo nghỉ hưu phải được ban hành trước thời điểm nghỉ hưu bao lâu?", ((ev(CIVIL, "Trước 06 tháng tính đến thời điểm nghỉ hưu"),),), (CIVIL,)),
    CaseSpec("v2_civil_effect_and_repeal", "MULTI_EVIDENCE", "Nghị định 170/2025/NĐ-CP có hiệu lực từ ngày nào và Nghị định 138/2020/NĐ-CP có bị hết hiệu lực không?", ((ev(CIVIL, "có hiệu lực thi hành kể từ ngày 01 tháng 7 năm 2025"), ev(CIVIL, "Nghị định số 138/2020/NĐ-CP ngày 27 tháng 11 năm 2020")),), notes="Requires the effective-date clause and the enumerated repealed instrument."),

    # One defensible cross-document comparison.
    CaseSpec("v2_cross_document_effective_dates", "MULTI_DOCUMENT_EVIDENCE", "So sánh ngày hiệu lực của Thông tư về thực hành công tác xã hội và Thông tư 40/2026/TT-NHNN: văn bản nào có hiệu lực trước?", ((ev(SOCIAL, "có hiệu lực từ ngày 25 tháng 8 năm 2026"), ev(BANK, "có hiệu lực thi hành kể từ ngày 01 tháng 11 năm 2026")),), notes="Requires two documents; social-work instrument is earlier."),

    # Hard, topically close unsupported questions: verified absent from all Corpus V2 chunks.
    CaseSpec("v2_hard_social_practice_fee", "HARD_UNANSWERABLE", "Mức học phí tối đa người thực hành công tác xã hội phải trả cho cơ sở thực hành là bao nhiêu đồng mỗi tháng?", answerable=False, notes="Corpus regulates duration/content/responsibilities but provides no practice-fee amount."),
    CaseSpec("v2_hard_social_online_practice", "HARD_UNANSWERABLE", "Người thực hành công tác xã hội được thực hành trực tuyến tối đa bao nhiêu giờ trong tổng thời gian bắt buộc?", answerable=False, notes="Online modes are specified for knowledge-update activities, not an online-practice-hour maximum."),
    CaseSpec("v2_hard_bank_statutory_capital", "HARD_UNANSWERABLE", "Mức vốn pháp định cụ thể bằng bao nhiêu đồng đối với quỹ tín dụng nhân dân theo Thông tư 40/2026/TT-NHNN?", answerable=False, notes="The instrument refers to statutory capital but does not state its numeric amount."),
    CaseSpec("v2_hard_bank_administrative_fine", "HARD_UNANSWERABLE", "Quỹ tín dụng nhân dân vi phạm tỷ lệ khả năng chi trả bị phạt hành chính chính xác bao nhiêu tiền?", answerable=False, notes="No administrative fine schedule is present."),
    CaseSpec("v2_hard_civil_exam_fee", "HARD_UNANSWERABLE", "Lệ phí đăng ký dự tuyển công chức theo văn bản hợp nhất là bao nhiêu đồng?", answerable=False, notes="Recruitment procedure is present but no application-fee amount is supplied."),
    CaseSpec("v2_hard_civil_retirement_age", "HARD_UNANSWERABLE", "Tuổi nghỉ hưu chính xác của công chức nam trong năm 2026 là bao nhiêu tuổi, bao nhiêu tháng?", answerable=False, notes="The corpus incorporates labor/social-insurance law by reference but does not state the requested 2026 age."),
    # Clearly out-of-corpus controls.
    CaseSpec("v2_out_personal_income_tax", "OUT_OF_CORPUS", "Mức giảm trừ gia cảnh thuế thu nhập cá nhân hiện hành là bao nhiêu?", answerable=False),
    CaseSpec("v2_out_offshore_wind_license", "OUT_OF_CORPUS", "Hồ sơ xin giấy phép khảo sát dự án điện gió ngoài khơi gồm những tài liệu nào?", answerable=False),
    CaseSpec("v2_out_traffic_fine", "OUT_OF_CORPUS", "Mức phạt ô tô vượt đèn đỏ hiện hành là bao nhiêu tiền?", answerable=False),
    CaseSpec("v2_out_private_maternity", "OUT_OF_CORPUS", "Lao động nữ tại doanh nghiệp tư nhân được nghỉ thai sản bao nhiêu tháng?", answerable=False),
)


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def excerpt(content: str, phrase: str, width: int = 460) -> str:
    compact = normalized(content)
    location = compact.casefold().find(normalized(phrase).casefold())
    if location < 0:
        return compact[:width]
    start = max(0, location - 100)
    end = min(len(compact), location + len(phrase) + width - 100)
    return compact[start:end]


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    documents = {
        item["document_key"]: item
        for item in manifest["items"]
        if item.get("integrity_pass") and item.get("document_key")
    }
    db = SessionLocal()
    review_rows: list[dict[str, Any]] = []
    dataset_cases: list[dict[str, Any]] = []
    try:
        for spec in CASES:
            solutions: list[list[str]] = []
            expected_documents: list[str] = []
            evidence_details: dict[str, dict[str, Any]] = {}
            for solution in spec.solutions:
                ids: list[str] = []
                for selector in solution:
                    document = documents[selector.document_key]
                    document_id = document["ingestion_document_id"]
                    rows = db.execute(
                        text(
                            """SELECT id::text, document_id::text, chunk_index, content_text,
                                      page_start, page_end, metadata_json, provenance_json
                               FROM chunks
                               WHERE document_id = :document_id
                                 AND position(lower(:phrase) in lower(regexp_replace(content_text, '\\s+', ' ', 'g'))) > 0
                               ORDER BY chunk_index"""
                        ),
                        {"document_id": document_id, "phrase": normalized(selector.phrase)},
                    ).mappings().all()
                    if not rows:
                        raise RuntimeError(f"{spec.case_id}: evidence phrase not found: {selector.phrase}")
                    row = dict(rows[0])
                    chunk_id = row["id"]
                    ids.append(chunk_id)
                    if document_id not in expected_documents:
                        expected_documents.append(document_id)
                    evidence_details[chunk_id] = {
                        **row,
                        "document_key": selector.document_key,
                        "selector_phrase": selector.phrase,
                        "excerpt": excerpt(row["content_text"], selector.phrase),
                        "matching_chunk_count": len(rows),
                    }
                solutions.append(ids)
            filters = [documents[key]["ingestion_document_id"] for key in spec.filter_documents]
            source_reference = spec.solutions[0][0].phrase if spec.answerable else None
            dataset_cases.append(
                {
                    "case_id": spec.case_id,
                    "category": spec.category,
                    "question": spec.question,
                    "answerable": spec.answerable,
                    "document_ids": filters or None,
                    "expected_document_ids": expected_documents,
                    "acceptable_evidence_sets": solutions,
                    "source_reference": source_reference,
                    "notes": spec.notes,
                }
            )
            review_rows.append(
                {
                    "case_id": spec.case_id,
                    "category": spec.category,
                    "question": spec.question,
                    "answerable": spec.answerable,
                    "expected_document_ids": expected_documents,
                    "acceptable_evidence_sets": solutions,
                    "evidence": list(evidence_details.values()),
                    "notes": spec.notes,
                }
            )

        dataset = {
            "dataset_id": "legal_eval_v2",
            "version": "2.0.0",
            "description": "Grounded scale/generalization baseline over the user-supplied, text-native Legal Corpus V2; no quality tuning.",
            "cases": dataset_cases,
        }
        DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
        DATASET_PATH.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        validation = validate_dataset(load_dataset(DATASET_PATH), db)
    finally:
        db.close()

    lines = [
        "# Legal Evaluation V2 — Human Ground-Truth Review",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"Dataset cases: **{len(dataset_cases)}**; answerable: **{sum(item['answerable'] for item in dataset_cases)}**; unanswerable: **{sum(not item['answerable'] for item in dataset_cases)}**.",
        "",
        "Every positive evidence ID was resolved from an indexed `block3-v1` chunk. Excerpts are exact compacted source text. This artifact requires human legal review; it is not an LLM judgment.",
        "",
    ]
    for item in review_rows:
        lines.extend(
            [
                f"## {item['case_id']}",
                "",
                f"- Category: `{item['category']}`",
                f"- Question: {item['question']}",
                f"- Answerable: `{str(item['answerable']).lower()}`",
                f"- Expected documents: {', '.join(f'`{value}`' for value in item['expected_document_ids']) or 'none'}",
                f"- Acceptable evidence sets: `{json.dumps(item['acceptable_evidence_sets'], ensure_ascii=False)}`",
                f"- Ground-truth rationale: {item['notes'] or ('The exact persisted provision directly supplies the requested fact.' if item['answerable'] else 'No positive evidence is declared; corpus absence was verified by targeted text search and source review.')}",
                "",
            ]
        )
        for evidence in item["evidence"]:
            lines.extend(
                [
                    f"### Evidence `{evidence['id']}`",
                    "",
                    f"- Document: `{evidence['document_id']}` (`{evidence['document_key']}`)",
                    f"- Chunk index: {evidence['chunk_index']}",
                    f"- Pages: {evidence['page_start']}–{evidence['page_end']}",
                    f"- Provenance: `{json.dumps(evidence['provenance_json'], ensure_ascii=False)}`",
                    f"- Selector matches in document: {evidence['matching_chunk_count']}",
                    "",
                    f"> {evidence['excerpt']}",
                    "",
                ]
            )

    REVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    REVIEW_PATH.write_text("\n".join(lines), encoding="utf-8")
    digest = sha256(DATASET_PATH)
    categories: dict[str, int] = {}
    for item in dataset_cases:
        categories[item["category"]] = categories.get(item["category"], 0) + 1
    freeze = [
        "# Legal Evaluation V2 Dataset Freeze",
        "",
        f"Frozen: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"- Path: `evaluation/datasets/legal_eval_v2.json`",
        f"- SHA-256: `{digest}`",
        f"- Validation: **{validation['status']}**",
        f"- Total cases: {len(dataset_cases)}",
        f"- Answerable: {sum(item['answerable'] for item in dataset_cases)}",
        f"- Unanswerable: {sum(not item['answerable'] for item in dataset_cases)}",
        f"- Categories: `{json.dumps(categories, ensure_ascii=False, sort_keys=True)}`",
        "",
        "The dataset is frozen before baseline execution. Failures must not be removed or rewritten to improve metrics. Corrections require explicit human review, a new dataset version, and a new hash.",
        "",
    ]
    FREEZE_PATH.write_text("\n".join(freeze), encoding="utf-8")
    print(json.dumps({**validation, "sha256": digest, "categories": categories}, ensure_ascii=False))


if __name__ == "__main__":
    main()
