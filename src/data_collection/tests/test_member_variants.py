"""Biến thể giá thành viên Vinpearl ([VIN33 - Gold/Platinum/Diamond]) gộp về một vé không được để lại dòng trùng trong DB.

Production 08/10/2026: 10 vé, 12 dòng thừa đang bán trùng tên (vd. "[Grand World Phú Quốc] - Vé đi thuyền Venice (Water Taxi)"
VW02818 188.000 đ và VW02833 182.000 đ): biến thể được nạp riêng ở lượt 01–02/10, lượt sau gộp vào vé khác nên không bao giờ
được làm mới hay tắt.
"""
import normalise as nm
from fresh_catalog_db import prepare_rows

NAME = "[Grand World Phú Quốc] - Vé đi thuyền Venice (Water Taxi)"


def ticket(code, price, tier=None):
    name = f"[{tier}] - {NAME}" if tier else NAME
    attrs = {"memberTier": tier} if tier else {}
    return nm.make_product(meta={"src": "vinpearl"}, name=name, taxonomy="attraction", destination="Phú Quốc",
                           description="vé", attributes=attrs, unitPrice=price, currency="VND", available=True,
                           imageUrl=None, sourceRef=f"vinpearl:tour:{code}")


def test_merged_variants_go_into_keeper_same_as():
    gold, platinum, diamond = ticket("VW02818", 188000, "VIN33 - Gold"), ticket("VW02833", 182000, "VIN33 - Platinum"), \
        ticket("VW02900", 170000, "VIN33 - Diamond")
    kept, dropped = nm.merge_member_variants([platinum, gold, diamond])
    assert dropped == 2 and [p["sourceRef"] for p in kept] == ["vinpearl:tour:VW02818"]  # không có vé thường: giá cao nhất
    keeper = kept[0]
    assert keeper["name"] == NAME
    # hạng được chọn làm vé đại diện là unitPrice của vé (như production: VW02818 188.000 đ, memberPrices Platinum/Diamond)
    assert keeper["unitPrice"] == 188000
    assert keeper["attributes"]["memberPrices"] == {"VIN33 - Platinum": 182000, "VIN33 - Diamond": 170000}
    assert keeper["attributes"]["sameAs"] == ["vinpearl:tour:VW02833", "vinpearl:tour:VW02900"]


def test_plain_ticket_keeps_its_own_ref_and_absorbs_variants():
    plain, gold = ticket("VW01054", 200000), ticket("VW02818", 188000, "VIN33 - Gold")
    plain["attributes"]["sameAs"] = ["vinpearl:tour:VW02818", "trip:attraction:1"]  # đã có từ lượt trước: không lặp
    kept, _ = nm.merge_member_variants([plain, gold])
    assert kept == [plain]
    assert plain["attributes"]["sameAs"] == ["vinpearl:tour:VW02818", "trip:attraction:1"]


def db_row(product):
    return {"product_id": product["productId"], "source_ref": product["sourceRef"], "name": NAME, "taxonomy": "attraction",
            "destination": "Phú Quốc", "description": "vé", "attributes": {"lastSeenAt": "2026-10-02"},
            "unit_price": product["unitPrice"], "currency": "VND", "available": True, "available_from": None,
            "available_to": None, "image_url": None}


def test_old_variant_row_in_db_is_merged_away_and_hidden():
    gold, platinum = ticket("VW02818", 188000, "VIN33 - Gold"), ticket("VW02833", 182000, "VIN33 - Platinum")
    existing = [db_row(gold), db_row(platinum)]  # cả hai đang bán trong DB (production 08/10)
    kept, _ = nm.merge_member_variants([gold, platinum])
    fresh = [{k: v for k, v in p.items() if not k.startswith("_")} for p in kept]
    rows, counts = prepare_rows(fresh, existing, set(), "2026-10-08")
    by_ref = {r["source_ref"]: r for r in rows}
    assert counts["mergedAway"] == 1
    assert by_ref["vinpearl:tour:VW02818"]["available"] is True
    old = by_ref["vinpearl:tour:VW02833"]
    assert old["available"] is False and old["attributes"]["mergedInto"] == gold["productId"]
