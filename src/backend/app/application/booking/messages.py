"""Câu thông báo tiếng Việt cho vi phạm luật đoàn khách (spec checkout-nhieu-buoc-hanh-khach.md §5.6).

Domain chỉ trả `Violation(field, reason, params)`; câu chữ dựng ở đây để hiển thị được trực tiếp cho người dùng. Web dùng
cùng câu trong `checkoutRules.ts`; đổi câu ở một phía phải đổi phía kia.
"""
from __future__ import annotations

from datetime import date
from typing import Sequence

from src.backend.app.application.booking.errors import ValidationFailed
from src.backend.app.domain.booking.party_rules import Violation

CHECKOUT_MESSAGE = "Thông tin đặt chỗ chưa hợp lệ."
CART_MESSAGE = "Số khách của dịch vụ này chưa hợp lệ."


def _dmy(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%d/%m/%Y")


def _required(field: str, params: dict) -> str:
    if field.endswith(".surname"):
        return "Vui lòng nhập họ."
    if field.endswith(".givenNames"):
        return "Vui lòng nhập tên đệm và tên."
    if field.endswith(".birthDate"):
        return "Vui lòng nhập ngày sinh."
    if field.endswith(".documents.title"):
        return "Chọn danh xưng."
    if field.endswith(".documents.nationality"):
        return "Chọn quốc tịch."
    if field.endswith(".documents.docType"):
        return "Chọn loại giấy tờ."
    if field.endswith(".documents.docNumber"):
        return "Nhập số giấy tờ."
    if field.endswith(".documents.docExpiry"):
        return "Nhập ngày hết hạn hộ chiếu."
    if field.endswith(".documents.escortTravelerRef"):
        return "Chọn người lớn đi kèm em bé."
    if field == "contact.fullName":
        return "Vui lòng nhập họ và tên người liên hệ."
    if field == "contact.email":
        return "Vui lòng nhập email."
    if field == "contact.phone":
        return "Vui lòng nhập số điện thoại."
    if field.endswith(".guestNames"):
        return f"Vui lòng nhập họ tên khách của {params.get('item_name', 'dịch vụ này')}."
    if field == "quantity":
        return "Vui lòng nhập số lượng."
    return "Vui lòng nhập thông tin còn thiếu."


def _adult_required(params: dict) -> str:
    scope = params.get("scope")
    if scope == "item":
        return "Trẻ em cần đi cùng ít nhất 1 người lớn trong dịch vụ này."
    if scope == "room":
        return "Mỗi phòng cần ít nhất 1 người lớn."
    return "Cần ít nhất 1 người lớn (từ 12 tuổi)."


def _party_too_large(field: str, params: dict) -> str:
    if params.get("scope") == "mixed":
        return f"{params.get('item_name', 'Khách sạn')} trên 9 khách phải đặt riêng, không gộp với dịch vụ khác."
    cap = params.get("max_party", 9)
    if params.get("rooms"):
        return f"Mỗi phòng tối đa 9 khách ({cap} khách cho {params['rooms']} phòng). Vui lòng thêm phòng."
    if field == "travelers" and cap > 9:
        return f"Mỗi đơn tối đa {cap} khách. Vui lòng tách thành nhiều đơn."
    return "Mỗi đơn tối đa 9 khách. Vui lòng tách thành nhiều đơn."


def message_for(violation: Violation) -> str:
    reason, field, params = violation.reason, violation.field, dict(violation.params)
    name = params.get("item_name", "dịch vụ này")
    match reason:
        case "REQUIRED":
            return _required(field, params)
        case "NAME_INVALID":
            return ("Họ và tên người liên hệ tối đa 100 ký tự." if field.startswith("contact.")
                    else "Chỉ gồm chữ cái, đúng như trên giấy tờ.")
        case "PHONE_INVALID":
            return "Số điện thoại gồm 10 chữ số, bắt đầu bằng 0."
        case "EMAIL_INVALID":
            return "Email không hợp lệ."
        case "BIRTH_DATE_INVALID":
            return "Ngày sinh không hợp lệ."
        case "CHILD_AGE_INVALID":
            return f"Bé đã đủ 12 tuổi vào {_dmy(params['turned_12_on'])}. Vui lòng chọn loại Người lớn."
        case "ADULT_AGE_INVALID":
            return f"Người lớn phải từ 12 tuổi tại ngày bay {_dmy(params['flight_date'])}."
        case "TITLE_INVALID":
            return "Danh xưng không hợp lệ."
        case "NATIONALITY_INVALID":
            return "Quốc tịch không hợp lệ."
        case "DOC_TYPE_INVALID":
            return "Khách quốc tịch nước ngoài dùng hộ chiếu."
        case "DOC_NUMBER_INVALID":
            return ("Số CCCD gồm 12 chữ số." if params.get("doc_type") == "CCCD"
                    else "Số hộ chiếu gồm 6–9 chữ và số.")
        case "DOC_EXPIRY_INVALID":
            return "Ngày hết hạn không hợp lệ."
        case "DOC_EXPIRED":
            return f"Hộ chiếu hết hạn trước ngày bay cuối cùng ({_dmy(params['flight_date'])})."
        case "ESCORT_INVALID":
            return "Người lớn đi kèm phải là người lớn trong đoàn."
        case "ESCORT_NOT_ON_FLIGHT":
            who = params.get("traveler_name") or "em bé"
            return f"Người lớn đi kèm {who} không bay chuyến này."
        case "ESCORT_OVERLOADED":
            return "Mỗi người lớn chỉ đi kèm 1 em bé."
        case "ADULT_REQUIRED":
            return _adult_required(params)
        case "PARTY_TOO_LARGE":
            return _party_too_large(field, params)
        case "ROOMS_TOO_MANY":
            return f"Mỗi lần đặt tối đa {params.get('max_rooms', 9)} phòng."
        case "TRAVELER_UNKNOWN":
            return "Hành khách không có trong đoàn."
        case "TRAVELER_DUPLICATED":
            if field.endswith(".travelerRef"):
                return "Mã hành khách bị trùng."
            who = params.get("traveler_name") or "Hành khách này"
            return f"{who} đã được chọn ở chỗ khác trong dịch vụ này."
        case "ITEM_DETAIL_MISSING":
            return f"Thiếu thông tin cho {name}."
        case "ITEM_DETAIL_UNKNOWN" | "ITEM_DETAIL_DUPLICATED":
            return "Thông tin dịch vụ không khớp giỏ hàng. Vui lòng tải lại giỏ."
        case "ITEM_WITHOUT_TRAVELER":
            return f"Chọn ít nhất 1 khách dùng {name}, hoặc xoá dịch vụ khỏi giỏ."
        case "GUEST_COUNT_MISMATCH":
            if field == "quantity":
                return "Số lượng phải bằng số người lớn cộng số trẻ em."
            return f"Số khách của {name} vừa thay đổi. Vui lòng xem lại giá."
        case "INFANTS_EXCEED_ADULTS":
            return "Mỗi em bé dưới 2 tuổi cần một người lớn đi kèm trên chuyến bay."
        case "ROOM_COUNT_MISMATCH":
            n = params.get("rooms", 1)
            return f"Bạn đã đặt {n} phòng. Hãy xếp khách vào đủ {n} phòng hoặc giảm số phòng."
        case "OCCUPANCY_EXCEEDED":
            x = params.get("max_occupancy")
            if params.get("room_no"):
                return f"Phòng {params['room_no']} chứa tối đa {x} khách."
            return f"Mỗi phòng chứa tối đa {x} khách. Vui lòng thêm phòng."
        case "LEAD_GUEST_INVALID":
            return "Người đại diện nhận phòng phải là người lớn ở trong phòng."
        case "TRAVELERS_REQUIRED":
            return "Đơn có trẻ em cần khai thông tin hành khách. Vui lòng tải lại trang và thử lại."
    return "Thông tin chưa hợp lệ."


def field_error(violation: Violation) -> dict:
    """Một phần tử của `details.fields[]` trong `VALIDATION_ERROR`."""
    out = {"field": violation.field, "reason": violation.reason, "message": message_for(violation)}
    if violation.cart_item_id:
        out["cartItemId"] = violation.cart_item_id
    return out


def validation_failed(violations: Sequence[Violation], *, user_message: str = CHECKOUT_MESSAGE) -> ValidationFailed:
    """`400 VALIDATION_ERROR` liệt kê mọi vi phạm trong một lần."""
    error = ValidationFailed(user_message, {"fields": [field_error(v) for v in violations]})
    error.user_message = user_message
    return error
