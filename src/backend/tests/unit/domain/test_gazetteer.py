"""Bảng địa danh/điểm vui chơi (`domain/search/gazetteer.py`): luật vệ sinh alias, bảng dẫn xuất, khoá entity từ tên unit;
thuần, không catalog."""
import pytest

from src.backend.app.domain.search.constraints import BRAND_CUES, POI_BRAND_CUES, VERTICAL_CUES
from src.backend.app.domain.search.gazetteer import (AIRPORT, AREA, DISTRICT, ENTITY_TAXONOMIES, KINDS, LANDMARK,
                                                     MAX_ALIAS_TOKENS, PLACES, VENUE, Place, entities_of_name,
                                                     entity_table, place, place_table)
from src.backend.app.domain.search.lexical import fold
from src.backend.app.domain.search.normalize import DESTINATION_ALIASES

#: Điểm đến catalog mà seed P0 được phép trỏ tới (đúng chính tả catalog).
CATALOG_DESTINATIONS = ["Hà Nội", "Đà Nẵng", "Hội An", "Nha Trang", "Phú Quốc", "TP. Hồ Chí Minh", "Hạ Long", "Đà Lạt",
                        "Sa Pa", "Huế", "Phan Thiết", "Ninh Bình", "Nghệ An", "Hải Phòng"]
BRANDS = {"vinwonders", "safari", "grand_world", "aquafield"}
ALL_ALIASES = [(p.key, a) for p in PLACES for a in p.aliases]


# ------------------------------------------------------------------------------------------------ luật vệ sinh bảng
def test_keys_unique_and_kinds_valid():
    assert len({p.key for p in PLACES}) == len(PLACES)
    assert {p.kind for p in PLACES} <= KINDS
    assert KINDS == {LANDMARK, AREA, DISTRICT, AIRPORT, VENUE}
    assert ENTITY_TAXONOMIES == {"attraction", "combo"}
    for p in PLACES:
        assert p.aliases and p.name and p.key == fold(p.key).replace(" ", "_")


@pytest.mark.parametrize("key, alias", ALL_ALIASES)
def test_alias_is_folded(key, alias):
    assert fold(alias) == alias and alias == alias.strip() and "  " not in alias


def test_aliases_unique_across_places():
    aliases = [a for _, a in ALL_ALIASES]
    dupes = {a for a in aliases if aliases.count(a) > 1}
    assert not dupes, dupes


@pytest.mark.parametrize("key, alias", ALL_ALIASES)
def test_alias_does_not_collide_with_destination_or_brand_vocab(key, alias):
    assert alias not in DESTINATION_ALIASES
    assert alias not in {fold(d) for d in CATALOG_DESTINATIONS}
    assert alias not in BRAND_CUES                          # "vinpearl" là thương hiệu khách sạn, không phải entity
    assert alias not in {"thuy cung", "pho co", "old quarter", "long beach"}


@pytest.mark.parametrize("key, alias", ALL_ALIASES)
def test_alias_is_not_a_vertical_cue_except_poi_brand_cues(key, alias):
    # Ngoại lệ duy nhất: cue yếu "vinwonders"/"safari"/"grand world" vừa là cue F4 vừa là alias của entry có entity.
    if alias in VERTICAL_CUES:
        assert alias in POI_BRAND_CUES and place(key).entity is not None, (key, alias)


@pytest.mark.parametrize("p", PLACES, ids=lambda p: p.key)
def test_entity_and_destination_rules(p: Place):
    if p.kind == VENUE:
        assert p.entity is not None
    else:
        assert p.entity is None
    if p.key in BRANDS:
        assert p.destination is None and p.entity == p.key
    else:
        assert p.destination in CATALOG_DESTINATIONS
    if p.entity is not None and p.entity != p.key:
        assert p.entity in BRANDS                               # entry site → khoá thương hiệu


def test_seed_shape_from_plan():
    assert place("ho_hoan_kiem").destination == "Hà Nội" and "ho guom" in place("ho_hoan_kiem").aliases
    assert place("cau_rong").destination == "Đà Nẵng" and "dragon bridge" in place("cau_rong").aliases
    assert place("ba_na").kind == LANDMARK and "sun world ba na" in place("ba_na").aliases
    assert place("noi_bai").kind == AIRPORT and place("tan_son_nhat").kind == AIRPORT and place("cam_ranh").kind == AIRPORT
    assert place("quan_1").kind == DISTRICT and place("quan_hoan_kiem").kind == DISTRICT
    assert place("pho_co_hoi_an").kind == AREA and "hoi an ancient town" in place("pho_co_hoi_an").aliases
    assert place("vinwonders_cua_hoi").destination == "Nghệ An" and place("vinwonders_vu_yen").destination == "Hải Phòng"
    assert place("safari_phu_quoc").entity == "safari" and place("grand_park").destination == "TP. Hồ Chí Minh"
    assert not any(p.destination == "Vũng Tàu" for p in PLACES)
    assert MAX_ALIAS_TOKENS == max(len(a.split()) for _, a in ALL_ALIASES) >= 4   # "vinpearl safari phu quoc"


# ------------------------------------------------------------------------------------------------ bảng dẫn xuất
def test_place_table_only_entries_with_destination():
    table = place_table()
    assert set(table.values()) == {p for p in PLACES if p.destination is not None}
    assert "vinwonders" not in table and "safari" not in table           # thương hiệu không định vị
    assert table["ho guom"].key == "ho_hoan_kiem" and table["hon tam"].key == "hon_tam"
    assert table["vinwonders nam hoi an"].destination == "Hội An"


def test_place_table_drops_destinations_outside_catalog():
    table = place_table({"Nha Trang"})
    assert {p.destination for p in table.values()} == {"Nha Trang"}
    assert "hon tam" in table and table["hon tam"].key == "hon_tam"
    assert "ho guom" not in table and "vinwonders phu quoc" not in table
    assert place_table(set()) == {}
    assert place_table(["Nha Trang", "", None]) == place_table({"Nha Trang"})


def test_entity_table_only_entries_with_entity():
    table = entity_table()
    assert set(table.values()) == {p.entity for p in PLACES if p.entity}
    assert table["vinwonders"] == table["vinwonders nha trang"] == table["vinpearl land"] == "vinwonders"
    assert table["safari phu quoc"] == table["vinpearl safari"] == "safari"
    assert table["grand world ha noi"] == "grand_world" and table["hon tam"] == "hon_tam"
    assert "ho guom" not in table and "cau rong" not in table           # địa danh không phải entity


# ------------------------------------------------------------------------------------------------ khoá entity từ tên unit
@pytest.mark.parametrize("name, expected", [
    ("[VinWonders Nha Trang] - Combo Vé VinWonders + Buffet", {"vinwonders"}),
    ("Vinpearl Safari Phú Quốc", {"safari"}),
    ("Khách sạn Sweet Lavender - Ngay Chợ Đêm", set()),
    ("Vinpearl Resort Nha Trang", set()),                               # "vinpearl" trần không phải entity (c0709)
    ("Grand World Phú Quốc – Tinh Hoa Việt Nam", {"grand_world"}),
    ("Vé VinWonders Wave Park & Water Park", {"vinwonders", "wave_park"}),
    ("Vé VinKE & Vinpearl Aquarium Times City", {"vinke"}),
    ("Combo Hòn Tằm + Vinpearl Harbour", {"hon_tam", "vinpearl_harbour"}),
    ("Aquafield Ocean City - Vé Jjimjilbang", {"aquafield"}),
    ("Vé cáp treo Bà Nà Hills", set()),                                 # địa danh, không gate
    ("Vinpearl Golf Nha Trang - Voucher 18 hố", set()),                 # golf không là entity
    ("", set()),
])
def test_entities_of_name(name, expected):
    assert set(entities_of_name(name, entity_table())) == expected


def test_entities_of_name_respects_given_table():
    assert entities_of_name("Vé VinWonders Nha Trang", {"vinwonders": "vinwonders"}) == {"vinwonders"}
    assert entities_of_name("Vé VinWonders Nha Trang", {}) == frozenset()
