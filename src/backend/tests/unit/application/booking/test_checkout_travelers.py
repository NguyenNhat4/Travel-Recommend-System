"""Checkout nhiều bước ở tầng use case: đoàn khách, giá theo loại khách, kiểm hai phía (spec checkout-nhieu-buoc-hanh-khach.md).

Chạy trên bản giả (`tests/fakes/booking.py`), không cần mạng hay database.
"""
import asyncio
import logging
from datetime import date
from pathlib import Path

import pytest

from src.backend.app.application.booking import Contact, DocumentsInput, ItemDetail, RoomInput, TravelerInput
from src.backend.app.application.booking.errors import LineRejected, ValidationFailed
from src.backend.app.application.booking.messages import message_for
from src.backend.app.domain.booking import Guests
from src.backend.app.domain.booking.party_rules import Violation
from src.backend.tests.fakes.booking import HOTEL, PRINCIPAL, TICKET, USER, World, product

FLIGHT = "44444444-4444-4444-4444-444444444444"
CONTACT = Contact("Nguyễn Minh Anh", "minhanh@example.vn", "0912345678")
run = asyncio.run

# Giỏ có vé máy bay nên mỗi hành khách khai giấy tờ (FR-BKG-13).
A1 = TravelerInput("t1", "ADULT", "Nguyễn", "Minh Anh", "1988-03-14",
                   DocumentsInput("MS", "VN", "CCCD", "079188001234"))
A2 = TravelerInput("t2", "ADULT", "Trần", "Thu Hà", "1990-09-02",
                   DocumentsInput("MRS", "VN", "PASSPORT", "C1234567", "2031-01-01"))
KID = TravelerInput("t3", "CHILD", "Nguyễn", "Gia Bảo", "2019-05-12", DocumentsInput("MSTR", "VN"))


def family_world() -> World:
    """Catalog của ví dụ spec §4.5: phòng 777.192 ₫ sức chứa 3; vé VinWonders 1.500.000 ₫, trẻ em 504.000 ₫; bay 634.000 ₫."""
    return World(products=[
        product(HOTEL, "hotel", 777_192, attributes={"level": "room", "maxOccupancy": 3}),
        product(TICKET, "attraction", 1_500_000, attributes={"childPrice": 504000.0}),
        product(FLIGHT, "flight", 634_000, available_from=date(2026, 10, 19), available_to=date(2026, 10, 19)),
    ])


async def fill_family(w: World, guests=Guests(2, 1)):
    await w.basket.add(PRINCIPAL, product_id=HOTEL, using_date=date(2026, 10, 17), quantity=1, nights=2, guests=guests)
    await w.basket.add(PRINCIPAL, product_id=TICKET, using_date=date(2026, 10, 18), quantity=None, nights=None, guests=guests)
    await w.basket.add(PRINCIPAL, product_id=FLIGHT, using_date=date(2026, 10, 19), quantity=None, nights=None, guests=guests)
    return (await w.lines())


def family_details(lines, refs=("t1", "t2", "t3")):
    by = {l.product_id: l.cart_item_id for l in lines}
    return [
        ItemDetail(by[HOTEL], rooms=[RoomInput(tuple(refs), "t1")], special_request="Phòng tầng cao"),
        ItemDetail(by[TICKET], traveler_refs=list(refs)),
        ItemDetail(by[FLIGHT], traveler_refs=list(refs)),
    ]


# --- AC-BKG-05: giá theo loại khách, tổng khớp mọi nơi ------------------------------------------

def test_family_of_three_is_priced_by_traveler_type_and_every_total_agrees():
    async def go():
        w = family_world()
        lines = await fill_family(w)
        cart = await w.basket.get(PRINCIPAL)
        ticket = next(i for i in cart["items"] if i["product"]["productId"] == TICKET)
        assert ticket["quantity"] == 3 and ticket["guests"] == {"adults": 2, "children": 1}
        assert ticket["fares"] == [
            {"fareType": "ADULT", "unitPrice": 1_500_000, "count": 2, "nights": None, "amount": 3_000_000},
            {"fareType": "CHILD", "unitPrice": 504_000, "count": 1, "nights": None, "amount": 504_000}]
        assert ticket["lineTotal"] == 3_504_000 and cart["total"] == 6_960_384        # không còn 4.500.000 (lỗi L2)
        hotel = next(i for i in cart["items"] if i["product"]["productId"] == HOTEL)
        assert hotel["product"]["attributes"] == {"maxOccupancy": 3}

        res = await w.create(PRINCIPAL, CONTACT, family_details(lines), [A1, A2, KID])
        assert res["total"] == res["payment"]["amount"] == cart["total"] == 6_960_384
        stripe = next(iter(w.gateway.sessions.values()))
        assert stripe["amount"] == 6_960_384                                          # tổng line item Stripe = tổng đơn
        assert sorted((l.name.rsplit(" · ", 1)[1], l.unit_amount, l.quantity) for l in stripe["lines"]) == sorted([
            ("2 đêm", 1_554_384, 1), ("Người lớn", 1_500_000, 2), ("Trẻ em", 504_000, 1),
            ("Người lớn", 634_000, 2), ("Trẻ em", 634_000, 1)])
        assert w.booking(res["referenceCode"]).total_amount == 6_960_384
    run(go())


def test_response_lists_travelers_per_item_without_birth_dates_and_stores_them():
    async def go():
        w = family_world()
        lines = await fill_family(w)
        res = await w.create(PRINCIPAL, CONTACT, family_details(lines), [A1, A2, KID])
        items = {i["product"]["taxonomy"]: i for i in res["groups"][0]["items"]}
        docs = [{"title": "MS", "nationality": "VN", "docType": "CCCD", "docNumberLast4": "1234"},
                {"title": "MRS", "nationality": "VN", "docType": "PASSPORT", "docNumberLast4": "4567"},
                {"title": "MSTR", "nationality": "VN", "docType": None, "docNumberLast4": None}]
        assert items["hotel"]["travelers"] == [
            {"fullName": "Nguyễn Minh Anh", "type": "ADULT", "roomNo": 1, "isLead": True, "documents": docs[0]},
            {"fullName": "Trần Thu Hà", "type": "ADULT", "roomNo": 1, "isLead": False, "documents": docs[1]},
            {"fullName": "Nguyễn Gia Bảo", "type": "CHILD", "roomNo": 1, "isLead": False, "documents": docs[2]}]
        assert items["attraction"]["travelers"][2] == {"fullName": "Nguyễn Gia Bảo", "type": "CHILD", "roomNo": None,
                                                       "isLead": False, "documents": docs[2]}
        assert items["flight"]["guestNames"] == ["Nguyễn Minh Anh", "Trần Thu Hà", "Nguyễn Gia Bảo"]
        assert items["hotel"]["specialRequest"] == "Phòng tầng cao"
        assert "2019-05-12" not in repr(res) and "birth" not in repr(res).lower()   # ngày sinh không ra khỏi Backend
        assert "079188001234" not in repr(res) and "C1234567" not in repr(res) and "2031-01-01" not in repr(res)
        stored = w.booking(res["referenceCode"])
        assert [t.ref for t in stored.travelers] == ["t1", "t2", "t3"] and str(stored.travelers[2].birth_date) == "2019-05-12"
        assert stored.travelers[0].documents.doc_number == "079188001234"         # số giấy tờ đầy đủ chỉ nằm ở Backend
        assert str(stored.travelers[1].documents.doc_expiry) == "2031-01-01"
        again = await w.get(PRINCIPAL, res["referenceCode"])
        assert again["groups"][0]["items"] == res["groups"][0]["items"]
    run(go())


def test_child_who_turns_twelve_mid_trip_pays_the_adult_price_on_later_days():
    async def go():
        w = family_world()
        w.clock.now = w.clock.now.replace(month=9, day=29)
        turning = TravelerInput("t3", "CHILD", "Trần", "Bảo Châu", "2014-10-18")   # tròn 12 tuổi ngày 18/10, sau ngày nhận phòng
        await w.basket.add(PRINCIPAL, product_id=HOTEL, using_date=date(2026, 10, 17), quantity=1, nights=2, guests=Guests(2, 1))
        await w.basket.add(PRINCIPAL, product_id=TICKET, using_date=date(2026, 10, 18), quantity=None, nights=None,
                         guests=Guests(3, 0))
        lines = (await w.lines())
        by = {l.product_id: l.cart_item_id for l in lines}
        details = [ItemDetail(by[HOTEL], rooms=[RoomInput(("t1", "t2", "t3"), "t1")]),
                   ItemDetail(by[TICKET], traveler_refs=["t1", "t2", "t3"])]
        res = await w.create(PRINCIPAL, CONTACT, details, [A1, A2, turning])
        ticket = next(i for i in res["groups"][0]["items"] if i["product"]["taxonomy"] == "attraction")
        assert ticket["fares"] == [{"fareType": "ADULT", "unitPrice": 1_500_000, "count": 3, "nights": None,
                                    "amount": 4_500_000}]
        assert [t["type"] for t in ticket["travelers"]] == ["ADULT", "ADULT", "CHILD"]   # loại khai báo giữ nguyên
    run(go())


# --- AC-BKG-06: mọi vi phạm trong một lần, không tạo đơn, không gọi Stripe ------------------------

def test_direct_api_call_with_bad_data_lists_every_violation_and_creates_nothing():
    async def go():
        w = family_world()
        lines = await fill_family(w)
        twelve = TravelerInput("t4", "CHILD", "Nguyễn", "Bảo Vy", "2014-10-01")      # đã đủ 12 tuổi vào 01/10/2026
        blank = [TravelerInput(f"t{i}", "ADULT", "", "") for i in (1, 2, 3)]          # ba khách không có tên
        by = {l.product_id: l.cart_item_id for l in lines}
        details = [ItemDetail(by[HOTEL], rooms=[RoomInput(("t1", "t2", "t3", "t4"), "t1")]),   # phòng sức chứa 3 xếp 4 khách
                   ItemDetail(by[TICKET], traveler_refs=["t1", "t2", "t3"]),
                   ItemDetail(by[FLIGHT], traveler_refs=["t1", "t2", "t3"])]
        with pytest.raises(ValidationFailed) as e:
            await w.create(PRINCIPAL, CONTACT, details, [*blank, twelve])
        fields = e.value.details["fields"]
        reasons = {(f["field"], f["reason"]) for f in fields}
        assert ("travelers[0].surname", "REQUIRED") in reasons and ("travelers[2].givenNames", "REQUIRED") in reasons
        assert ("travelers[3].birthDate", "CHILD_AGE_INVALID") in reasons
        assert ("itemDetails[0].rooms[0]", "OCCUPANCY_EXCEEDED") in reasons
        assert all(f["message"] for f in fields)                                       # thông điệp tiếng Việt cho từng lỗi
        assert e.value.http_status == 400 and e.value.code == "VALIDATION_ERROR"
        assert w.store.bookings == {} and w.gateway.sessions == {}
        assert len((await w.lines())) == 3                               # giỏ còn nguyên
    run(go())


def test_validation_messages_are_readable_vietnamese():
    async def go():
        w = family_world()
        lines = await fill_family(w)
        bad_child = TravelerInput("t3", "CHILD", "Nguyễn", "Gia Bảo", "2014-10-17")
        with pytest.raises(ValidationFailed) as e:
            await w.create(PRINCIPAL, CONTACT, family_details(lines), [A1, A2, bad_child])
        (field,) = [f for f in e.value.details["fields"] if f["reason"] == "CHILD_AGE_INVALID"]
        assert field["field"] == "travelers[2].birthDate"
        assert field["message"] == "Bé đã đủ 12 tuổi vào 17/10/2026. Vui lòng chọn loại Người lớn."
    run(go())


# Mọi `reason` nêu trong contract (`ValidationFieldError`) phải có câu thông báo riêng, và các biến thể theo trường/ngữ cảnh
# đúng với bảng ở spec §5.6. Web dùng cùng câu ở `checkoutRules.ts`; đổi một phía phải đổi phía kia.
CONTRACT_REASONS = [
    "REQUIRED", "NAME_INVALID", "PHONE_INVALID", "EMAIL_INVALID", "BIRTH_DATE_INVALID", "CHILD_AGE_INVALID", "ADULT_REQUIRED",
    "PARTY_TOO_LARGE", "TRAVELER_UNKNOWN", "TRAVELER_DUPLICATED", "ITEM_DETAIL_MISSING", "ITEM_DETAIL_UNKNOWN",
    "ITEM_DETAIL_DUPLICATED", "ITEM_WITHOUT_TRAVELER", "GUEST_COUNT_MISMATCH", "INFANTS_EXCEED_ADULTS", "ROOM_COUNT_MISMATCH",
    "OCCUPANCY_EXCEEDED", "LEAD_GUEST_INVALID", "TRAVELERS_REQUIRED",
]


def test_every_reason_named_in_the_contract_has_its_own_vietnamese_message():
    contract = (Path(__file__).resolve().parents[5] / "shared/contracts/schemas/common.yaml").read_text(encoding="utf-8")
    params = {"turned_12_on": "2026-10-17", "item_name": "Vé VinWonders", "room_no": 1, "max_occupancy": 3, "rooms": 2,
              "traveler_name": "Trần Thu Hà"}
    for reason in CONTRACT_REASONS:
        assert reason in contract, f"{reason} không còn trong contract"
        message = message_for(Violation("travelers[0].surname", reason, params))
        assert message and message != "Thông tin chưa hợp lệ.", f"{reason} chưa có câu thông báo riêng"


@pytest.mark.parametrize("violation,expected", [
    (Violation("travelers[0].surname", "REQUIRED"), "Vui lòng nhập họ."),
    (Violation("travelers[0].givenNames", "REQUIRED"), "Vui lòng nhập tên đệm và tên."),
    (Violation("travelers[2].birthDate", "REQUIRED"), "Vui lòng nhập ngày sinh."),
    (Violation("contact.fullName", "REQUIRED"), "Vui lòng nhập họ và tên người liên hệ."),
    (Violation("contact.phone", "REQUIRED"), "Vui lòng nhập số điện thoại."),
    (Violation("contact.email", "REQUIRED"), "Vui lòng nhập email."),
    (Violation("contact.fullName", "NAME_INVALID"), "Họ và tên người liên hệ tối đa 100 ký tự."),
    (Violation("travelers[0].givenNames", "NAME_INVALID"), "Chỉ gồm chữ cái, đúng như trên giấy tờ."),
    (Violation("travelers[1].travelerRef", "TRAVELER_DUPLICATED"), "Mã hành khách bị trùng."),
    (Violation("itemDetails[0].travelerRefs", "TRAVELER_DUPLICATED", {"traveler_name": "Trần Thu Hà"}),
     "Trần Thu Hà đã được chọn ở chỗ khác trong dịch vụ này."),
    (Violation("quantity", "GUEST_COUNT_MISMATCH"), "Số lượng phải bằng số người lớn cộng số trẻ em."),
    (Violation("itemDetails[2]", "GUEST_COUNT_MISMATCH", {"item_name": "VJ601"}), "Số khách của VJ601 vừa thay đổi. Vui lòng xem lại giá."),
    (Violation("guests", "OCCUPANCY_EXCEEDED", {"max_occupancy": 3}), "Mỗi phòng chứa tối đa 3 khách. Vui lòng thêm phòng."),
    (Violation("itemDetails[0].rooms[1]", "OCCUPANCY_EXCEEDED", {"room_no": 2, "max_occupancy": 3}), "Phòng 2 chứa tối đa 3 khách."),
    (Violation("guests.adults", "ADULT_REQUIRED", {"scope": "party"}), "Cần ít nhất 1 người lớn (từ 12 tuổi)."),
    (Violation("itemDetails[1].travelerRefs", "ADULT_REQUIRED", {"scope": "item"}),
     "Trẻ em cần đi cùng ít nhất 1 người lớn trong dịch vụ này."),
    (Violation("itemDetails[0].rooms[0]", "ADULT_REQUIRED", {"scope": "room"}), "Mỗi phòng cần ít nhất 1 người lớn."),
    (Violation("itemDetails[1]", "ITEM_WITHOUT_TRAVELER", {"item_name": "Vé VinWonders"}),
     "Chọn ít nhất 1 khách dùng Vé VinWonders, hoặc xoá dịch vụ khỏi giỏ."),
    (Violation("itemDetails[0].rooms", "ROOM_COUNT_MISMATCH", {"rooms": 2}),
     "Bạn đã đặt 2 phòng. Hãy xếp khách vào đủ 2 phòng hoặc giảm số phòng."),
])
def test_message_variants_follow_the_field_and_context(violation, expected):
    assert message_for(violation) == expected


def test_allocation_that_does_not_match_the_prices_the_customer_saw_is_rejected():
    async def go():
        w = family_world()
        lines = await fill_family(w)                       # giỏ tính vé cho 2 người lớn + 1 trẻ em
        with pytest.raises(ValidationFailed) as e:
            await w.create(PRINCIPAL, CONTACT, family_details(lines, refs=("t1", "t2")), [A1, A2, KID])
        assert ("itemDetails[1]", "GUEST_COUNT_MISMATCH") in {(f["field"], f["reason"]) for f in e.value.details["fields"]}
        mismatch = next(f for f in e.value.details["fields"] if f["reason"] == "GUEST_COUNT_MISMATCH")
        assert mismatch["cartItemId"] and "vừa thay đổi" in mismatch["message"]
    run(go())


# --- PRICE_CHANGED cho giá vé trẻ em --------------------------------------------------------------

def test_child_price_change_is_reported_with_fare_type_child_after_the_data_rules():
    async def go():
        w = family_world()
        lines = await fill_family(w)
        w.catalog.products[TICKET].attributes["childPrice"] = 550_000.0
        with pytest.raises(LineRejected) as e:
            await w.create(PRINCIPAL, CONTACT, family_details(lines), [A1, A2, KID])
        assert e.value.code == "PRICE_CHANGED" and e.value.http_status == 409
        assert e.value.details == {"productId": TICKET, "oldPrice": 504_000, "newPrice": 550_000, "fareType": "CHILD"}
        assert w.gateway.sessions == {}
        # khách xem giá mới bằng PATCH (ghi lại snapshot) rồi đặt lại được
        item = next(l for l in (await w.lines()) if l.product_id == TICKET)
        await w.basket.update(PRINCIPAL, item.cart_item_id, using_date=None, quantity=item.quantity, nights=None,
                            nights_given=False)
        res = await w.create(PRINCIPAL, CONTACT, family_details(lines), [A1, A2, KID])
        assert res["total"] == 6_960_384 + (550_000 - 504_000)
    run(go())


def test_child_price_becoming_invalid_means_children_now_pay_the_adult_price_and_that_is_a_price_change():
    async def go():
        w = family_world()
        lines = await fill_family(w)
        w.catalog.products[TICKET].attributes["childPrice"] = 0
        with pytest.raises(LineRejected) as e:
            await w.create(PRINCIPAL, CONTACT, family_details(lines), [A1, A2, KID])
        assert e.value.details["fareType"] == "CHILD" and (e.value.details["oldPrice"], e.value.details["newPrice"]) == (
            504_000, 1_500_000)
    run(go())


def test_a_child_price_change_does_not_block_an_order_with_no_children_on_that_item():
    async def go():
        w = family_world()
        await w.basket.add(PRINCIPAL, product_id=TICKET, using_date=date(2026, 10, 18), quantity=None, nights=None,
                         guests=Guests(2, 0))
        w.catalog.products[TICKET].attributes["childPrice"] = 550_000.0
        line = (await w.lines())[0]
        res = await w.create(PRINCIPAL, CONTACT, [ItemDetail(line.cart_item_id, traveler_refs=["t1", "t2"])], [A1, A2])
        assert res["total"] == 3_000_000
    run(go())


# --- giỏ: guests, gộp, sửa, luật số khách ---------------------------------------------------------

def test_cart_merges_guests_and_rejects_over_capacity_and_over_nine_guests_with_reasons():
    async def go():
        w = family_world()
        d = date(2026, 10, 18)
        await w.cart.add(PRINCIPAL, product_id=TICKET, using_date=d, quantity=None, nights=None, guests=Guests(2, 1))
        cart = await w.cart.add(PRINCIPAL, product_id=TICKET, using_date=d, quantity=None, nights=None, guests=Guests(1, 0))
        item = cart["items"][0]
        assert item["quantity"] == 4 and item["guests"] == {"adults": 3, "children": 1}    # R-CRT-04
        with pytest.raises(ValidationFailed) as e:                                          # 4 + 6 = 10 khách
            await w.cart.add(PRINCIPAL, product_id=TICKET, using_date=d, quantity=None, nights=None, guests=Guests(6, 0))
        assert [(f["field"], f["reason"]) for f in e.value.details["fields"]] == [("guests", "PARTY_TOO_LARGE")]
        # Khách sạn không vào giỏ; luật sức chứa áp ngay khi tạo đơn nháp (R-DRF-01).
        with pytest.raises(ValidationFailed) as e:                                          # phòng sức chứa 3, 4 khách
            await w.basket.add(PRINCIPAL, product_id=HOTEL, using_date=date(2026, 10, 17), quantity=1, nights=2,
                             guests=Guests(2, 2))
        assert e.value.details["fields"][0]["reason"] == "OCCUPANCY_EXCEEDED" and e.value.http_status == 400
        assert "tối đa 3 khách" in e.value.details["fields"][0]["message"]
    run(go())


def test_patching_only_the_quantity_of_an_item_with_children_keeps_the_children():
    async def go():
        w = family_world()
        cart = await w.basket.add(PRINCIPAL, product_id=TICKET, using_date=date(2026, 10, 18), quantity=None, nights=None,
                                guests=Guests(2, 1))
        cid = cart["items"][0]["cartItemId"]
        cart = await w.basket.update(PRINCIPAL, cid, using_date=None, quantity=4, nights=None, nights_given=False)
        assert cart["items"][0]["guests"] == {"adults": 3, "children": 1} and cart["items"][0]["quantity"] == 4
        with pytest.raises(ValidationFailed) as e:
            await w.basket.update(PRINCIPAL, cid, using_date=None, quantity=1, nights=None, nights_given=False)
        assert e.value.details["fields"][0] == {
            "field": "guests.adults", "reason": "ADULT_REQUIRED", "message": "Cần ít nhất 1 người lớn (từ 12 tuổi)."}
    run(go())


def test_add_requires_quantity_or_guests():
    async def go():
        w = family_world()
        with pytest.raises(ValidationFailed) as e:
            await w.basket.add(PRINCIPAL, product_id=TICKET, using_date=date(2026, 10, 18), quantity=None, nights=None)
        assert e.value.details["fields"][0]["reason"] == "REQUIRED"
    run(go())


# --- request cũ không có `travelers` (§7.6) --------------------------------------------------------

def test_old_client_checkout_still_works_when_names_are_complete_and_prices_do_not_change():
    async def go():
        w = family_world()
        await w.basket.add(PRINCIPAL, product_id=HOTEL, using_date=date(2026, 10, 17), quantity=1, nights=2)
        await w.basket.add(PRINCIPAL, product_id=TICKET, using_date=date(2026, 10, 18), quantity=2, nights=None)
        res = await w.create(PRINCIPAL, CONTACT, await w.details())
        assert res["total"] == 777_192 * 2 + 2 * 1_500_000
        assert res["groups"][0]["items"][0]["travelers"] == []       # đơn kiểu cũ: chỉ có guestNames
        assert res["groups"][0]["items"][0]["guestNames"] == ["Nguyễn Minh Anh"]
    run(go())


def test_old_client_cannot_check_out_a_cart_that_has_children():
    async def go():
        w = family_world()
        await fill_family(w)
        with pytest.raises(ValidationFailed) as e:
            await w.create(PRINCIPAL, CONTACT, await w.details())
        assert "TRAVELERS_REQUIRED" in {f["reason"] for f in e.value.details["fields"]}
    run(go())


# --- dữ liệu cá nhân (NFR-SEC-01, spec §8.6) -------------------------------------------------------

def test_personal_data_is_never_logged_and_never_sent_to_stripe_or_cdp(caplog):
    async def go():
        w = family_world()
        lines = await fill_family(w)
        with caplog.at_level(logging.DEBUG):
            res = await w.create(PRINCIPAL, CONTACT, family_details(lines), [A1, A2, KID])
        await w.handler(w.gateway.pay(next(iter(w.gateway.sessions))))
        return w, res
    w, res = run(go())
    log = caplog.text
    for secret in ("Nguyễn", "Minh Anh", "Gia Bảo", "2019-05-12", "0912345678", "minhanh@example.vn"):
        assert secret not in log
    stripe = next(iter(w.gateway.sessions.values()))
    assert all(secret not in l.name for l in stripe["lines"] for secret in ("Nguyễn", "Minh Anh", "Gia Bảo"))
    purchases = w.cdp.recorded[0]
    assert len(purchases) == 3 and all("Nguyễn" not in repr(p) and "2019" not in repr(p) for p in purchases)
    hotel = next(p for p in purchases if p.taxonomy == "hotel")
    assert (hotel.quantity, hotel.unit_price) == (1, 777_192)         # purchase vẫn 1 event/mục, đơn giá người lớn
    ticket = next(p for p in purchases if p.taxonomy == "attraction")
    assert (ticket.quantity, ticket.unit_price) == (3, 1_500_000)


# --- FR-BKG-13: giấy tờ hành khách cho vé máy bay ----------------------------------------------

def test_flight_in_cart_requires_documents_and_reports_every_missing_field_in_one_response():
    async def go():
        w = family_world()
        lines = await fill_family(w)
        bare = [TravelerInput("t1", "ADULT", "Nguyễn", "Minh Anh"), TravelerInput("t2", "ADULT", "Trần", "Thu Hà"),
                TravelerInput("t3", "CHILD", "Nguyễn", "Gia Bảo", "2019-05-12")]
        with pytest.raises(ValidationFailed) as caught:
            await w.create(PRINCIPAL, CONTACT, family_details(lines), bare)
        fields = {(f["field"], f["reason"]) for f in caught.value.details["fields"]}
        assert ("travelers[0].birthDate", "REQUIRED") in fields
        assert ("travelers[0].documents.docNumber", "REQUIRED") not in fields  # chưa chọn loại giấy tờ thì chỉ báo docType
        assert ("travelers[0].documents.docType", "REQUIRED") in fields
        assert ("travelers[2].documents.title", "REQUIRED") in fields
        assert not w.gateway.sessions                                          # chưa gọi Stripe, chưa ghi gì
    run(go())


def test_documents_are_not_required_without_a_flight_in_the_cart():
    async def go():
        w = World(products=[product(HOTEL, "hotel", 777_192, attributes={"level": "room", "maxOccupancy": 3})])
        await w.basket.add(PRINCIPAL, product_id=HOTEL, using_date=date(2026, 10, 17), quantity=1, nights=2, guests=Guests(1, 0))
        line = (await w.lines())[0]
        res = await w.create(PRINCIPAL, CONTACT, [ItemDetail(line.cart_item_id, rooms=[RoomInput(("t1",), "t1")])],
                             [TravelerInput("t1", "ADULT", "Nguyễn", "Minh Anh")])
        assert "documents" not in res["groups"][0]["items"][0]["travelers"][0]
    run(go())
