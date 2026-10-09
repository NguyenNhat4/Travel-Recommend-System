"""Bảng địa danh và điểm vui chơi của /search (FR-SRC-03 "địa điểm: điểm đến, thành phố, khu vực" suy từ câu; contract 1.18.0).

Hai việc, cùng một bảng `PLACES`:

1. **POI → điểm đến (F1)**: địa danh, khu vực, quận, sân bay hoặc điểm vui chơi có đúng một chỗ ("Hồ Hoàn Kiếm", "Cầu Rồng",
   "Hòn Tằm") trỏ về giá trị `destination` của catalog để F1 lọc như khi câu nêu thẳng tên thành phố. `place_table()` chỉ
   giữ entry CÓ `destination`; khi nhận tập điểm đến của catalog thì bỏ entry trỏ tới nơi catalog không có — cùng luật với
   `DESTINATION_ALIASES` ở `normalize.QueryNormalizer` (tính hợp lệ vẫn đến từ catalog).
2. **Entity**: thương hiệu điểm vui chơi nhiều site (`vinwonders`, `safari`, `grand_world`, `aquafield`; `destination=None`
   vì "safari" có cả Phú Quốc lẫn Hội An) và venue một site (`hon_tam`, `vinke`…; `entity` = chính khoá của nó). Entry site
   của một thương hiệu (`vinwonders_nha_trang`…) vừa có `destination` (để định vị) vừa có `entity` = khoá thương hiệu (để
   gate). `entity_table()` → alias → khoá entity; `entities_of_name()` gán khoá cho TÊN unit lúc dựng `UnitAttributes`
   (chỉ unit thuộc `ENTITY_TAXONOMIES`). Sân golf KHÔNG là entity (là sản phẩm `golf`).

Luật vệ sinh bảng (test `tests/unit/domain/test_gazetteer.py` ép):

- Alias đã fold (`lexical.fold(alias) == alias`) và duy nhất trên toàn `PLACES` — mỗi cụm chỉ trỏ một entry.
- Alias không trùng khoá `normalize.DESTINATION_ALIASES` ("hn", "sapa"…), không trùng tên điểm đến catalog đã fold
  ("ha noi", "hoi an"…), không trùng khoá `constraints.BRAND_CUES` ("vinpearl" — là thương hiệu khách sạn, không phải
  entity, c0709), không trùng khoá `constraints.VERTICAL_CUES` ("cong vien", "khach san"…). Ngoại lệ duy nhất: cue yếu trong
  `constraints.POI_BRAND_CUES` ("vinwonders", "safari", "grand world") vừa là cue F4 vừa là alias entity — chúng là tên sản
  phẩm, F4 không cắt chúng khỏi `lexical_text` (tiền lệ `query_plan.py`), nên chỉ entry có `entity` được dùng.
- Không alias trần "pho co" (Hà Nội lẫn Hội An), "thuy cung" (đụng "Thuỷ cung Hoà Bình"), "long beach", "old quarter".
- Mọi entry `VENUE` có `entity`; entry không phải `VENUE` có `entity=None`; entry thương hiệu có `destination=None`.
- Chỉ nhận địa danh của điểm đến có trong catalog (đối chiếu 38 điểm đến bench 07/10); không Vũng Tàu.

Seed P0 chép tay từ `src/data_collection/collectors/venues.csv` (không đọc file lúc chạy — Docker chỉ mang `src/backend`)
và danh sách địa danh của plan `docs/plan/2026-10-07-search-duration-entity-poi.md`. Thuần stdlib, không I/O.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .lexical import fold
from .normalize import find_phrases, spans

#: Loại entry (`Place.kind`); khớp enum `queryPlan.location.kind` của contract 1.18.0.
LANDMARK, AREA, DISTRICT, AIRPORT, VENUE = "landmark", "area", "district", "airport", "venue"
KINDS: frozenset[str] = frozenset({LANDMARK, AREA, DISTRICT, AIRPORT, VENUE})
#: Taxonomy của unit được gán entity từ tên (gate chỉ giữ attraction/combo; khách sạn tên "Grand World" không phải entity).
ENTITY_TAXONOMIES: frozenset[str] = frozenset({"attraction", "combo"})

#: Giá trị `destination` đúng chính tả catalog (so sánh bằng chuỗi, không fold).
HA_NOI, DA_NANG, HOI_AN, NHA_TRANG, PHU_QUOC = "Hà Nội", "Đà Nẵng", "Hội An", "Nha Trang", "Phú Quốc"
HCM, HA_LONG, DA_LAT, SA_PA, HUE = "TP. Hồ Chí Minh", "Hạ Long", "Đà Lạt", "Sa Pa", "Huế"
PHAN_THIET, NINH_BINH, NGHE_AN, HAI_PHONG = "Phan Thiết", "Ninh Bình", "Nghệ An", "Hải Phòng"


@dataclass(frozen=True)
class Place:
    key: str
    name: str
    kind: str
    aliases: tuple[str, ...]        # đã fold (`lexical.fold`), duy nhất trên toàn PLACES
    destination: str | None         # giá trị catalog; None = thương hiệu nhiều site (vinwonders, safari, grand_world, aquafield)
    entity: str | None = None       # khoá entity của venue (entry site → khoá thương hiệu); None cho landmark/area/district/airport


PLACES: tuple[Place, ...] = (
    # ------------------------------------------------------------------ thương hiệu nhiều site (entity, không định vị)
    Place("vinwonders", "VinWonders", VENUE, ("vinwonders", "vinwonder", "vin wonders", "vinpearl land"), None,
          entity="vinwonders"),
    # "safari" ở mức thương hiệu: bench 07/10 có 44 unit Phú Quốc, 6 Hội An (River Safari), 1 Rạch Giá → không khoá Phú Quốc
    Place("safari", "Vinpearl Safari", VENUE, ("safari", "vinpearl safari"), None, entity="safari"),
    Place("grand_world", "Grand World", VENUE, ("grand world", "mega grand world"), None, entity="grand_world"),
    Place("aquafield", "Aquafield", VENUE, ("aquafield", "aqua field", "jjimjilbang"), None, entity="aquafield"),
    # ------------------------------------------------------------------ venue một site (định vị + entity = chính nó)
    Place("hon_tam", "Hòn Tằm", VENUE, ("hon tam", "dao hon tam"), NHA_TRANG, entity="hon_tam"),
    Place("vinpearl_harbour", "Vinpearl Harbour Nha Trang", VENUE,
          ("vinpearl harbour", "vinpearl harbor", "cap treo vinpearl"), NHA_TRANG, entity="vinpearl_harbour"),
    Place("vinke", "VinKE & Vinpearl Aquarium Times City", VENUE,
          ("vinke", "vinpearl aquarium", "vin ke"), HA_NOI, entity="vinke"),
    Place("grand_park", "Công viên Grand Park", VENUE,
          ("grand park", "cong vien grand park", "vinhomes grand park"), HCM, entity="grand_park"),
    # không alias "vinwonders wave park": để tên unit nhận cả `vinwonders` lẫn `wave_park` ("vé VinWonders" vẫn thấy Wave Park)
    Place("wave_park", "VinWonders Wave Park & Water Park", VENUE, ("wave park",), HA_NOI, entity="wave_park"),
    # ------------------------------------------------------------------ site của thương hiệu (định vị + entity = thương hiệu)
    Place("vinwonders_nha_trang", "VinWonders Nha Trang", VENUE,
          ("vinwonders nha trang", "vinwonder nha trang", "vinpearl land nha trang"), NHA_TRANG, entity="vinwonders"),
    Place("vinwonders_phu_quoc", "VinWonders Phú Quốc", VENUE,
          ("vinwonders phu quoc", "vinwonder phu quoc"), PHU_QUOC, entity="vinwonders"),
    Place("vinwonders_nam_hoi_an", "VinWonders Nam Hội An", VENUE,
          ("vinwonders nam hoi an", "vinwonders hoi an", "vinwonder nam hoi an"), HOI_AN, entity="vinwonders"),
    Place("vinwonders_cua_hoi", "VinWonders Cửa Hội", VENUE,
          ("vinwonders cua hoi", "vinwonder cua hoi"), NGHE_AN, entity="vinwonders"),
    Place("vinwonders_vu_yen", "VinWonders Vũ Yên", VENUE,
          ("vinwonders vu yen", "vinwonder vu yen"), HAI_PHONG, entity="vinwonders"),
    Place("safari_phu_quoc", "Vinpearl Safari Phú Quốc", VENUE,
          ("vinpearl safari phu quoc", "safari phu quoc"), PHU_QUOC, entity="safari"),
    Place("grand_world_phu_quoc", "Grand World Phú Quốc", VENUE, ("grand world phu quoc",), PHU_QUOC,
          entity="grand_world"),
    Place("grand_world_ha_noi", "Mega Grand World Hà Nội", VENUE,
          ("grand world ha noi", "mega grand world ha noi"), HA_NOI, entity="grand_world"),
    Place("aquafield_nha_trang", "Aquafield Nha Trang", VENUE, ("aquafield nha trang",), NHA_TRANG, entity="aquafield"),
    Place("aquafield_ocean_city", "Aquafield Ocean City", VENUE, ("aquafield ocean city",), HA_NOI, entity="aquafield"),
    # ------------------------------------------------------------------ Hà Nội
    Place("ho_hoan_kiem", "Hồ Hoàn Kiếm", LANDMARK,
          ("ho hoan kiem", "ho guom", "hoan kiem lake", "hoan kiem"), HA_NOI),
    Place("quan_hoan_kiem", "Quận Hoàn Kiếm", DISTRICT, ("quan hoan kiem", "hoan kiem district"), HA_NOI),
    # không "pho co" trần (Hà Nội lẫn Hội An), không "old quarter" trần
    Place("pho_co_ha_noi", "Phố cổ Hà Nội", AREA,
          ("pho co ha noi", "khu pho co ha noi", "ha noi old quarter", "hanoi old quarter"), HA_NOI),
    Place("ho_tay", "Hồ Tây", LANDMARK, ("ho tay", "west lake", "tay ho"), HA_NOI),
    Place("times_city", "Times City", AREA, ("times city", "vinhomes times city"), HA_NOI),
    Place("ocean_city", "Ocean City", AREA, ("ocean city", "vinhomes ocean city", "ocean park", "vinhomes ocean park"),
          HA_NOI),
    Place("noi_bai", "Sân bay Nội Bài", AIRPORT, ("san bay noi bai", "noi bai", "noi bai airport"), HA_NOI),
    # ------------------------------------------------------------------ Đà Nẵng
    Place("cau_rong", "Cầu Rồng", LANDMARK, ("cau rong", "dragon bridge"), DA_NANG),
    Place("my_khe", "Bãi biển Mỹ Khê", LANDMARK, ("my khe", "bai bien my khe", "my khe beach", "bien my khe"), DA_NANG),
    Place("ba_na", "Bà Nà Hills", LANDMARK, ("ba na", "ba na hills", "ba na hill", "sun world ba na", "nui ba na"), DA_NANG),
    Place("son_tra", "Bán đảo Sơn Trà", LANDMARK, ("son tra", "ban dao son tra", "son tra peninsula"), DA_NANG),
    Place("ngu_hanh_son", "Ngũ Hành Sơn", LANDMARK, ("ngu hanh son", "marble mountains"), DA_NANG),
    # ------------------------------------------------------------------ Hội An
    Place("pho_co_hoi_an", "Phố cổ Hội An", AREA,
          ("pho co hoi an", "khu pho co hoi an", "hoi an ancient town", "hoi an old town"), HOI_AN),
    Place("an_bang", "Bãi biển An Bàng", LANDMARK, ("an bang", "bai bien an bang", "an bang beach"), HOI_AN),
    Place("cua_dai", "Bãi biển Cửa Đại", LANDMARK, ("cua dai", "bai bien cua dai", "cua dai beach"), HOI_AN),
    # ------------------------------------------------------------------ Nha Trang
    Place("hon_tre", "Đảo Hòn Tre", AREA, ("hon tre", "dao hon tre"), NHA_TRANG),
    Place("bai_dai", "Bãi Dài", LANDMARK, ("bai dai", "bai dai beach", "bai bien bai dai"), NHA_TRANG),
    Place("cam_ranh", "Sân bay Cam Ranh", AIRPORT, ("san bay cam ranh", "cam ranh", "cam ranh airport"), NHA_TRANG),
    # ------------------------------------------------------------------ Phú Quốc
    Place("bai_sao", "Bãi Sao", LANDMARK, ("bai sao", "sao beach", "bai bien bai sao"), PHU_QUOC),
    # không "long beach" trần (tên tiếng Anh chung của nhiều bãi)
    Place("bai_truong", "Bãi Trường", LANDMARK, ("bai truong", "truong beach", "long beach phu quoc"), PHU_QUOC),
    Place("duong_dong", "Dương Đông", AREA, ("duong dong", "thi tran duong dong"), PHU_QUOC),
    Place("an_thoi", "An Thới", AREA, ("an thoi", "thi tran an thoi"), PHU_QUOC),
    # ------------------------------------------------------------------ TP. Hồ Chí Minh
    Place("quan_1", "Quận 1", DISTRICT, ("quan 1", "quan nhat", "district 1"), HCM),
    Place("ben_thanh", "Chợ Bến Thành", LANDMARK, ("ben thanh", "cho ben thanh", "ben thanh market"), HCM),
    Place("tan_son_nhat", "Sân bay Tân Sơn Nhất", AIRPORT,
          ("tan son nhat", "san bay tan son nhat", "tan son nhat airport"), HCM),
    # ------------------------------------------------------------------ Hạ Long
    Place("bai_chay", "Bãi Cháy", AREA, ("bai chay",), HA_LONG),
    Place("tuan_chau", "Đảo Tuần Châu", AREA, ("tuan chau", "dao tuan chau"), HA_LONG),
    # ------------------------------------------------------------------ Đà Lạt
    Place("ho_xuan_huong", "Hồ Xuân Hương", LANDMARK, ("ho xuan huong", "xuan huong lake"), DA_LAT),
    # ------------------------------------------------------------------ Sa Pa
    Place("fansipan", "Fansipan", LANDMARK, ("fansipan", "dinh fansipan", "phan xi pang"), SA_PA),
    # ------------------------------------------------------------------ Huế
    Place("lang_co", "Lăng Cô", LANDMARK, ("lang co", "bai bien lang co", "vinh lang co"), HUE),
    # ------------------------------------------------------------------ Phan Thiết
    Place("mui_ne", "Mũi Né", AREA, ("mui ne",), PHAN_THIET),
    # ------------------------------------------------------------------ Ninh Bình
    Place("trang_an", "Tràng An", LANDMARK, ("trang an",), NINH_BINH),
    Place("tam_coc", "Tam Cốc", LANDMARK, ("tam coc", "tam coc bich dong"), NINH_BINH),
)

#: Số token dài nhất của một alias — cửa sổ khớp của `normalize.find_phrases`.
MAX_ALIAS_TOKENS: int = max(len(a.split()) for p in PLACES for a in p.aliases)
_BY_KEY: dict[str, Place] = {p.key: p for p in PLACES}


def place(key: str) -> Place:
    return _BY_KEY[key]


def place_table(destinations: Iterable[str] | None = None) -> dict[str, Place]:
    """alias → `Place` cho entry CÓ `destination` (định vị cho F1). `destinations` = tập giá trị catalog: entry trỏ tới
    nơi catalog không có bị bỏ (luật `normalize.QueryNormalizer`, dòng lọc `DESTINATION_ALIASES`). None = không lọc."""
    known = None if destinations is None else {str(d) for d in destinations if d}
    out: dict[str, Place] = {}
    for p in PLACES:
        if p.destination is None or (known is not None and p.destination not in known):
            continue
        for alias in p.aliases:
            out[alias] = p
    return out


def entity_table() -> dict[str, str]:
    """alias → khoá entity cho entry CÓ `entity` (thương hiệu, venue một site, site của thương hiệu). Không kiểm theo
    catalog: tên là tên — khoá không có sản phẩm bị loại ở tầng application (chỉ khoá có mặt trong `attrs.entities` gate)."""
    return {alias: p.entity for p in PLACES if p.entity for alias in p.aliases}


def entities_of_name(name: str, table: Mapping[str, str]) -> frozenset[str]:
    """Khoá entity xuất hiện trong TÊN unit — khớp dài nhất trước trên token đã fold (`normalize.find_phrases`), không
    chồng nhau. "[VinWonders Nha Trang] - Combo Vé VinWonders + Buffet" → {"vinwonders"}; "Vinpearl Resort Nha Trang" → ∅."""
    if not name:
        return frozenset()
    hits = find_phrases(spans(name), table.__contains__, MAX_ALIAS_TOKENS)
    return frozenset(table[key] for _, _, key in hits)
