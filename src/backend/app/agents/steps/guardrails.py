"""Guardrail tất định: chặn chèn lệnh ở đầu vào, chặn lộ secret/tuyên bố đặt chỗ ở đầu ra.

Không gọi LLM — regex mẫu hẹp. Lớp phân luồng bằng LLM (`classification.route_result`) đã gắn
`out_of_scope` cho chèn lệnh, đòi secret, đặt chỗ (`prompts.CLASSIFY_PROMPT`); module này là lưới an
toàn tất định phía trước và phía sau, không thay thế lớp đó. Mẫu cố ý hẹp để không chặn nhầm câu du
lịch hợp lệ (vd. "bỏ qua khách sạn"); mở rộng mẫu thì thêm test âm tính đi kèm.
"""
from __future__ import annotations

import re

# Chèn lệnh / đòi lộ thông tin hệ thống, rõ ràng không phải yêu cầu du lịch.
_QUALIFIER = r"(all\s+|any\s+|the\s+|previous\s+|prior\s+)*"
_INPUT_PATTERNS = [
    re.compile(rf"ignore\s+{_QUALIFIER}instructions?", re.IGNORECASE),
    re.compile(rf"disregard\s+{_QUALIFIER}instructions?", re.IGNORECASE),
    re.compile(rf"forget\s+{_QUALIFIER}instructions?", re.IGNORECASE),
    re.compile(r"bỏ qua\s+(mọi\s+|các\s+|những\s+|hết\s+)?(hướng dẫn|chỉ dẫn|chỉ thị)\s+(trước|trên|đã)",
              re.IGNORECASE),
    re.compile(r"quên\s+(mọi\s+|các\s+|những\s+|hết\s+)?(hướng dẫn|chỉ dẫn|chỉ thị)\s+(trước|trên|đã)",
              re.IGNORECASE),
    re.compile(r"system\s*prompt|prompt\s*hệ thống|chỉ dẫn\s*hệ thống", re.IGNORECASE),
    re.compile(r"(in ra|hiện ra|hiển thị|show|reveal|print|tiết lộ|cho (tôi|mình) xem)\s+.{0,30}"
              r"(api[\s_-]?key|secret\s*key|secret|token|mật khẩu)", re.IGNORECASE),
]

# Câu chữ LLM tự viết không được phép chứa: chuỗi giống secret, hoặc tuyên bố đã đặt/đã thanh toán —
# grounding và trạng thái đặt chỗ chỉ do luật tất định quyết định, LLM không được tự nói thay (NFR-SEC-01).
_SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9]{10,}"),
    re.compile(r"bearer\s+[a-zA-Z0-9._-]{10,}", re.IGNORECASE),
    re.compile(r"AIzaSy[a-zA-Z0-9_-]{10,}"),
]
_BOOKING_CLAIM_PHRASES = ("đã đặt", "đã thanh toán", "đặt thành công", "booking confirmed")


def input_violation(query: str) -> str | None:
    """Mẫu chèn lệnh/đòi secret khớp đầu tiên trong `query`, hoặc `None` nếu câu sạch."""
    for pattern in _INPUT_PATTERNS:
        if pattern.search(query or ""):
            return pattern.pattern
    return None


def _llm_authored_text(response: dict) -> str:
    """Chỉ hai trường LLM tự viết chữ: `question` (`clarify`/`converse`) và `error.message` (từ chối
    của `converse`). Các trường `message` khác (`NO_RESULTS`, `FALLBACK`, …) là câu cố định, không quét.
    """
    parts = [response.get("question")]
    error = response.get("error")
    if isinstance(error, dict):
        parts.append(error.get("message"))
    return "\n".join(part for part in parts if part)


def output_violations(response: dict) -> list[str]:
    """Danh sách lý do vi phạm trong câu chữ LLM tự viết của `response`; rỗng nghĩa là sạch."""
    text = _llm_authored_text(response)
    lowered = text.lower()
    issues = [f"secret:{pattern.pattern}" for pattern in _SECRET_PATTERNS if pattern.search(text)]
    issues += [f"booking_claim:{phrase}" for phrase in _BOOKING_CLAIM_PHRASES if phrase in lowered]
    return issues
