"""Mã nguyên nhân khi lượt dừng sớm hoặc dùng câu dự phòng (`docs/plan/2026-10-12-go-luong-cu-orchestrator-chinh.md`, D2).

Trước đây một event gộp nhiều nguyên nhân ("execution budget exhausted" cho cả trần vòng, trần tool và hết giờ). Mã
nằm trong metadata `reason` của event và trong `turn_limit_reason`; không đổi chữ của event, node path hay mã lỗi trả ra
ngoài. Trần vòng và trần tool là hành vi tất định, snapshot giữ và kiểm chúng. Các mã còn lại phụ thuộc tốc độ mạng hay
trạng thái của provider, nên lượt có chúng không phát lại được.
"""
TIME_LIMIT = "TIME_LIMIT"
ROUND_LIMIT = "ROUND_LIMIT"
TOOL_LIMIT = "TOOL_LIMIT"
MODEL_TIMEOUT = "MODEL_TIMEOUT"
MODEL_ERROR = "MODEL_ERROR"
TOOL_TIMEOUT = "TOOL_TIMEOUT"

#: Không phát lại được: snapshot từ chối lượt có các mã này khi ghi.
UNREPLAYABLE = frozenset({TIME_LIMIT, MODEL_TIMEOUT, MODEL_ERROR, TOOL_TIMEOUT})


def model_failure(exc: BaseException | None) -> str:
    """Model quá hạn (`asyncio.wait_for`) hay lỗi khác."""
    return MODEL_TIMEOUT if isinstance(exc, TimeoutError) else MODEL_ERROR
