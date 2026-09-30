"""Bộ luật kiểm đoàn khách, phân bổ theo dịch vụ và số khách của giỏ (spec checkout-nhieu-buoc-hanh-khach.md §5).

Web (`src/frontend/src/components/checkout/checkoutRules.ts`) và Backend chạy cùng một bộ ca kiểm thử
(`src/shared/contracts/tests/booking-rules-cases.json`): mã luật, `reason` và đường dẫn trường phải giống hệt nhau.

Mọi hàm trả về **danh sách** vi phạm chứ không dừng ở vi phạm đầu tiên. Đây là code thuần: không import framework, không
đụng database. Câu thông báo tiếng Việt do tầng application dựng từ `Violation` (`application/booking/messages.py`).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Mapping, Sequence

from .fares import PER_PERSON_TAXONOMIES, FareType
from .party import (
    ADULT_MIN_AGE, MAX_PARTY, Guests, Traveler, TravelerType, adult_from, age_on, fare_type_on, is_infant_on,
)

NAME_PART_MAX = 50
CONTACT_NAME_MAX = 100
PHONE_PATTERN = re.compile(r"0[0-9]{9}")
EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
ISO_DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


@dataclass(frozen=True)
class Violation:
    """Một vi phạm luật. `field` là đường dẫn trong request (ví dụ `travelers[2].birthDate`)."""

    field: str
    reason: str
    params: Mapping[str, Any] = field(default_factory=dict)  # dữ liệu để dựng câu thông báo
    cart_item_id: str | None = None  # có khi vi phạm thuộc một mục giỏ, để Web gắn lỗi vào đúng thẻ dịch vụ


# --- dữ liệu vào -----------------------------------------------------------------------------------

@dataclass(frozen=True)
class ContactInput:
    full_name: str
    email: str
    phone: str


@dataclass(frozen=True)
class TravelerInput:
    ref: str
    type: str  # "ADULT" | "CHILD" như trong API
    surname: str
    given_names: str
    birth_date: str | None = None  # chuỗi thô: ngày sinh sai định dạng là vi phạm chứ không phải lỗi kiểu dữ liệu


@dataclass(frozen=True)
class RoomInput:
    traveler_refs: Sequence[str]
    lead_traveler_ref: str | None


@dataclass(frozen=True)
class ItemInput:
    cart_item_id: str
    traveler_refs: Sequence[str] | None = None
    rooms: Sequence[RoomInput] | None = None
    guest_names: Sequence[str] = ()  # chỉ request cũ không có `travelers` (§7.6)


@dataclass(frozen=True)
class CartFacts:
    """Những gì luật cần biết về một mục giỏ (catalog + số khách người dùng đã thấy giá)."""

    cart_item_id: str
    name: str
    taxonomy: str
    using_date: date
    quantity: int
    adults: int
    children: int
    max_occupancy: int | None = None


# --- tiện ích chuỗi và ngày -------------------------------------------------------------------------

def normalize_name(value: str | None) -> str:
    """Bỏ khoảng trắng thừa và chuẩn hoá Unicode về NFC."""
    return " ".join(unicodedata.normalize("NFC", value or "").split())


def _letters_only(value: str) -> bool:
    return all(unicodedata.category(ch)[0] in ("L", "M") or ch in " '-" for ch in value)


def parse_iso_date(raw: str | None) -> date | None:
    """`YYYY-MM-DD` hợp lệ theo lịch, hoặc None. Không nhận các dạng khác mà `date.fromisoformat` chấp nhận."""
    if not raw or not ISO_DATE_PATTERN.fullmatch(raw.strip()):
        return None
    try:
        return date.fromisoformat(raw.strip())
    except ValueError:
        return None


# --- bước ①: người liên hệ và đoàn khách ------------------------------------------------------------

def check_contact(contact: ContactInput) -> list[Violation]:
    """R-CON-01."""
    out: list[Violation] = []
    name = normalize_name(contact.full_name)
    if not name:
        out.append(Violation("contact.fullName", "REQUIRED"))
    elif len(name) > CONTACT_NAME_MAX:
        out.append(Violation("contact.fullName", "NAME_INVALID"))
    email = (contact.email or "").strip()
    if not email:
        out.append(Violation("contact.email", "REQUIRED"))
    elif len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
        out.append(Violation("contact.email", "EMAIL_INVALID"))
    phone = (contact.phone or "").strip()
    if not phone:
        out.append(Violation("contact.phone", "REQUIRED"))
    elif not PHONE_PATTERN.fullmatch(phone):
        out.append(Violation("contact.phone", "PHONE_INVALID"))
    return out


def check_party(
    inputs: Sequence[TravelerInput], *, earliest: date | None, today: date
) -> tuple[list[Traveler], list[Violation]]:
    """R-TRV-01…06. Trả về đoàn đã chuẩn hoá (để luật theo dịch vụ dùng tiếp) cùng danh sách vi phạm.

    `earliest` là ngày sử dụng sớm nhất của đơn; `today` là ngày hôm nay theo giờ Việt Nam.
    """
    out: list[Violation] = []
    travelers: list[Traveler] = []
    if len(inputs) > MAX_PARTY:
        out.append(Violation("travelers", "PARTY_TOO_LARGE"))
    if not any(item.type == "ADULT" for item in inputs):
        out.append(Violation("travelers", "ADULT_REQUIRED", {"scope": "party"}))
    seen_refs: set[str] = set()
    for index, item in enumerate(inputs):
        base = f"travelers[{index}]"
        if item.ref in seen_refs:
            out.append(Violation(f"{base}.travelerRef", "TRAVELER_DUPLICATED"))
        seen_refs.add(item.ref)
        surname, given_names = normalize_name(item.surname), normalize_name(item.given_names)
        for part, value in (("surname", surname), ("givenNames", given_names)):
            if not value:
                out.append(Violation(f"{base}.{part}", "REQUIRED", {"part": part}))
            elif len(value) > NAME_PART_MAX or not _letters_only(value):
                out.append(Violation(f"{base}.{part}", "NAME_INVALID"))
        birth: date | None = None
        if item.type == "CHILD":
            raw = (item.birth_date or "").strip()
            if not raw:
                out.append(Violation(f"{base}.birthDate", "REQUIRED", {"part": "birthDate"}))
            else:
                parsed = parse_iso_date(raw)
                if parsed is None or parsed > today or (earliest is not None and parsed > earliest):
                    out.append(Violation(f"{base}.birthDate", "BIRTH_DATE_INVALID"))
                else:
                    birth = parsed
                    if earliest is not None and age_on(parsed, earliest) >= ADULT_MIN_AGE:
                        out.append(Violation(f"{base}.birthDate", "CHILD_AGE_INVALID",
                                             {"turned_12_on": adult_from(parsed).isoformat()}))
        travelers.append(Traveler(item.ref, TravelerType(item.type.lower()), surname, given_names, birth))
    return travelers, out


# --- bước ②: phân bổ theo dịch vụ -------------------------------------------------------------------

def check_items(
    travelers: Sequence[Traveler], details: Sequence[ItemInput], cart: Sequence[CartFacts]
) -> list[Violation]:
    """R-ITM-01…04, R-FLT-01, R-HTL-01…05."""
    by_ref: dict[str, Traveler] = {}
    for traveler in travelers:
        by_ref.setdefault(traveler.ref, traveler)
    cart_by_id = {c.cart_item_id: c for c in cart}
    out: list[Violation] = []
    seen: set[str] = set()
    handled: list[tuple[int, ItemInput, CartFacts]] = []
    for index, detail in enumerate(details):
        facts = cart_by_id.get(detail.cart_item_id)
        if facts is None:
            out.append(Violation(f"itemDetails[{index}]", "ITEM_DETAIL_UNKNOWN"))
        elif detail.cart_item_id in seen:
            out.append(Violation(f"itemDetails[{index}]", "ITEM_DETAIL_DUPLICATED", {"item_name": facts.name},
                                 facts.cart_item_id))
        else:
            seen.add(detail.cart_item_id)
            handled.append((index, detail, facts))
    for facts in cart:
        if facts.cart_item_id not in seen:
            out.append(Violation("itemDetails", "ITEM_DETAIL_MISSING", {"item_name": facts.name}, facts.cart_item_id))
    for index, detail, facts in handled:
        out.extend(_check_hotel(index, detail, facts, by_ref) if facts.taxonomy == "hotel"
                   else _check_per_person(index, detail, facts, by_ref))
    return out


def _check_per_person(index: int, detail: ItemInput, facts: CartFacts, by_ref: Mapping[str, Traveler]) -> list[Violation]:
    field_path = f"itemDetails[{index}].travelerRefs"
    cid, name = facts.cart_item_id, facts.name
    refs = list(detail.traveler_refs or [])
    if not refs:
        return [Violation(field_path, "ITEM_WITHOUT_TRAVELER", {"item_name": name}, cid)]
    out: list[Violation] = []
    seen: set[str] = set()
    reported: set[tuple[str, str]] = set()
    structural = True
    for ref in refs:
        if ref not in by_ref:
            reason = "TRAVELER_UNKNOWN"
        elif ref in seen:
            reason = "TRAVELER_DUPLICATED"
        else:
            seen.add(ref)
            continue
        structural = False
        if (reason, ref) not in reported:
            reported.add((reason, ref))
            out.append(Violation(field_path, reason,
                                 {"traveler_name": by_ref[ref].full_name if ref in by_ref else ""}, cid))
    if not structural:
        return out
    fares = [fare_type_on(by_ref[ref], facts.using_date) for ref in refs]
    adults, children = fares.count(FareType.ADULT), fares.count(FareType.CHILD)
    if children and not adults:
        out.append(Violation(field_path, "ADULT_REQUIRED", {"scope": "item"}, cid))
    if facts.taxonomy in PER_PERSON_TAXONOMIES and (adults, children) != (facts.adults, facts.children):
        out.append(Violation(f"itemDetails[{index}]", "GUEST_COUNT_MISMATCH", {"item_name": name}, cid))
    if facts.taxonomy == "flight":
        infants = sum(is_infant_on(by_ref[ref], facts.using_date) for ref in refs)
        if infants > adults:
            out.append(Violation(field_path, "INFANTS_EXCEED_ADULTS", {}, cid))
    return out


def _check_hotel(index: int, detail: ItemInput, facts: CartFacts, by_ref: Mapping[str, Traveler]) -> list[Violation]:
    base = f"itemDetails[{index}]"
    cid = facts.cart_item_id
    rooms = list(detail.rooms or [])
    out: list[Violation] = []
    if len(rooms) != facts.quantity:
        out.append(Violation(f"{base}.rooms", "ROOM_COUNT_MISMATCH", {"rooms": facts.quantity}, cid))
    seen_in_item: set[str] = set()
    for k, room in enumerate(rooms):
        room_path = f"{base}.rooms[{k}]"
        refs = list(room.traveler_refs)
        reported: set[tuple[str, str]] = set()
        for ref in refs:
            reason = None
            if ref not in by_ref:
                reason = "TRAVELER_UNKNOWN"
            elif ref in seen_in_item:
                reason = "TRAVELER_DUPLICATED"
            else:
                seen_in_item.add(ref)
            if reason and (reason, ref) not in reported:
                reported.add((reason, ref))
                out.append(Violation(f"{room_path}.travelerRefs", reason,
                                     {"traveler_name": by_ref[ref].full_name if ref in by_ref else ""}, cid))
        adults = [ref for ref in refs if ref in by_ref and fare_type_on(by_ref[ref], facts.using_date) is FareType.ADULT]
        if not adults:
            out.append(Violation(room_path, "ADULT_REQUIRED", {"scope": "room", "room_no": k + 1}, cid))
        if facts.max_occupancy and len(refs) > facts.max_occupancy:
            out.append(Violation(room_path, "OCCUPANCY_EXCEEDED",
                                 {"room_no": k + 1, "max_occupancy": facts.max_occupancy}, cid))
        if adults and room.lead_traveler_ref not in adults:
            out.append(Violation(f"{room_path}.leadTravelerRef", "LEAD_GUEST_INVALID", {"room_no": k + 1}, cid))
    return out


def check_checkout(
    contact: ContactInput, inputs: Sequence[TravelerInput], details: Sequence[ItemInput], cart: Sequence[CartFacts],
    *, today: date,
) -> tuple[list[Traveler], list[Violation]]:
    """Toàn bộ luật của `POST /bookings` khi request có `travelers` (§8.3 bước 5)."""
    earliest = min((c.using_date for c in cart), default=None)
    travelers, violations = check_party(inputs, earliest=earliest, today=today)
    return travelers, [*check_contact(contact), *violations, *check_items(travelers, details, cart)]


# --- request cũ không có `travelers` (§7.6) ---------------------------------------------------------

def check_legacy(details: Sequence[ItemInput], cart: Sequence[CartFacts]) -> list[Violation]:
    """Quy tắc tên hiện có, nay được Backend kiểm thật (sửa lỗi L5): mọi mục có `itemDetails`; vé máy bay đủ `quantity`
    tên không rỗng; khách sạn có ít nhất một tên. Chỉ nhận đơn không có trẻ em."""
    cart_by_id = {c.cart_item_id: c for c in cart}
    out: list[Violation] = []
    seen: set[str] = set()
    for index, detail in enumerate(details):
        facts = cart_by_id.get(detail.cart_item_id)
        if facts is None:
            out.append(Violation(f"itemDetails[{index}]", "ITEM_DETAIL_UNKNOWN"))
        elif detail.cart_item_id in seen:
            out.append(Violation(f"itemDetails[{index}]", "ITEM_DETAIL_DUPLICATED", {"item_name": facts.name},
                                 facts.cart_item_id))
        else:
            seen.add(detail.cart_item_id)
            names = [n for n in (normalize_name(n) for n in detail.guest_names) if n]
            if facts.taxonomy == "flight" and len(names) != facts.quantity:
                out.append(Violation(f"itemDetails[{index}].guestNames", "REQUIRED",
                                     {"part": "guestNames", "item_name": facts.name}, facts.cart_item_id))
            elif facts.taxonomy == "hotel" and not names:
                out.append(Violation(f"itemDetails[{index}].guestNames", "REQUIRED",
                                     {"part": "guestNames", "item_name": facts.name}, facts.cart_item_id))
    for facts in cart:
        if facts.cart_item_id not in seen:
            out.append(Violation("itemDetails", "ITEM_DETAIL_MISSING", {"item_name": facts.name}, facts.cart_item_id))
        if facts.children:
            out.append(Violation("travelers", "TRAVELERS_REQUIRED", {"item_name": facts.name}, facts.cart_item_id))
    return out


# --- luật khi thêm hoặc sửa mục giỏ (§5.5) ----------------------------------------------------------

@dataclass(frozen=True)
class CartGuestsResult:
    quantity: int
    guests: Guests
    violations: list[Violation]


def default_guests(taxonomy: str, quantity: int) -> Guests:
    """R-CRT-05: client không gửi `guests`. Khách sạn và dịch vụ tính theo người: mỗi phòng/vé một người lớn; combo: 1."""
    return Guests(1, 0) if taxonomy == "combo" else Guests(quantity, 0)


def _merge_guests(taxonomy: str, existing: Guests, added: Guests) -> Guests:
    """R-CRT-04. Combo: `guests` chỉ để ghi nhận nên lấy giá trị lớn hơn theo từng loại thay vì cộng dồn."""
    if taxonomy == "combo":
        return Guests(max(existing.adults, added.adults), max(existing.children, added.children))
    return Guests(existing.adults + added.adults, existing.children + added.children)


def check_cart_guests(taxonomy: str, quantity: int, guests: Guests, max_occupancy: int | None) -> list[Violation]:
    """R-CRT-01, R-CRT-03."""
    out: list[Violation] = []
    if guests.adults < 1:
        out.append(Violation("guests.adults", "ADULT_REQUIRED", {"scope": "party"}))
    if guests.total > MAX_PARTY:
        out.append(Violation("guests", "PARTY_TOO_LARGE"))
    if taxonomy == "hotel":
        if 1 <= guests.adults < quantity:
            out.append(Violation("guests.adults", "ADULT_REQUIRED", {"scope": "room"}))
        if max_occupancy and guests.total > max_occupancy * quantity:
            out.append(Violation("guests", "OCCUPANCY_EXCEEDED", {"max_occupancy": max_occupancy}))
    return out


def resolve_cart_guests(
    taxonomy: str, *, mode: str, request_quantity: int | None, request_guests: Guests | None,
    existing_quantity: int | None, existing_guests: Guests | None, max_occupancy: int | None,
) -> CartGuestsResult:
    """Tính `quantity` và `guests` sau khi thêm (`mode="add"`) hoặc sửa (`mode="update"`) một mục giỏ, rồi kiểm R-CRT-01…05."""
    per_person = taxonomy in PER_PERSON_TAXONOMIES
    empty = Guests(1, 0)

    def reject(violation: Violation) -> CartGuestsResult:
        return CartGuestsResult(request_quantity or existing_quantity or 1, request_guests or existing_guests or empty,
                                [violation])

    if mode == "add":
        if request_guests is None:
            if request_quantity is None:
                return reject(Violation("quantity", "REQUIRED", {"part": "quantity"}))
            quantity, guests = request_quantity, default_guests(taxonomy, request_quantity)
        elif per_person:
            quantity = request_guests.total
            if request_quantity is not None and request_quantity != quantity:
                return reject(Violation("quantity", "GUEST_COUNT_MISMATCH"))
            guests = request_guests
        else:
            if request_quantity is None:
                return reject(Violation("quantity", "REQUIRED", {"part": "quantity"}))
            quantity, guests = request_quantity, request_guests
        if existing_quantity is not None and existing_guests is not None:
            quantity, guests = quantity + existing_quantity, _merge_guests(taxonomy, existing_guests, guests)
    else:
        assert existing_quantity is not None and existing_guests is not None
        quantity, guests = existing_quantity, existing_guests
        if request_guests is not None:
            guests = request_guests
            if per_person:
                quantity = guests.total
                if request_quantity is not None and request_quantity != quantity:
                    return reject(Violation("quantity", "GUEST_COUNT_MISMATCH"))
            elif request_quantity is not None:
                quantity = request_quantity
        elif request_quantity is not None and request_quantity != existing_quantity:
            quantity = request_quantity
            if per_person:
                guests = Guests(quantity - existing_guests.children, existing_guests.children)
            elif taxonomy == "hotel":
                guests = Guests(max(existing_guests.adults, quantity), existing_guests.children)
    return CartGuestsResult(quantity, guests, check_cart_guests(taxonomy, quantity, guests, max_occupancy))
