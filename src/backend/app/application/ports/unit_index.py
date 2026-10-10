"""Metadata các search unit mà ba engine Search / Similar / Recommendation cùng đọc để lọc trước."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from src.backend.app.domain.catalog import Product, StayDates, UnitAttributes
from src.backend.app.domain.catalog.stay_dates import calendar_open
from src.backend.app.domain.catalog.unit_attributes import ChildRow


@dataclass
class UnitIndex:
    """Ảnh chụp search unit từ Postgres; vector không nằm ở đây mà truy vấn qua `VectorSearchPort`."""
    units: list[Product]
    taxonomy: np.ndarray               # (n,) str
    destination: np.ndarray            # (n,) str
    available: np.ndarray              # (n,) bool
    recommendable: np.ndarray          # (n,) bool  — is_recommendable của product_meta
    parent_of: dict[str, str]          # child product_id → parent product_id
    model_version: str
    attrs: UnitAttributes | None = None  # thuộc tính lọc Phase A (F3/F5/F6); None → dựng từ unit, không có con
    #: combo product_id → product_id thành phần đã map tin cậy (`catalog.combo_items`, xem `postgres_store.combo_members_of`).
    #: Chỉ để loại trừ sản phẩm đã mua (FR-REC-02, chốt 09/10); {} → combo không kéo theo gì.
    combo_members: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def __post_init__(self):
        self.idx = {p.product_id: i for i, p in enumerate(self.units)}
        if self.attrs is None:
            self.attrs = UnitAttributes.build(self.units)
        # Quan hệ combo ↔ thành phần theo chỉ số search unit (phòng → khách sạn, chuyến → tuyến qua `resolve`); bỏ thành phần
        # ngoài catalog và tự tham chiếu.
        components: dict[int, set[int]] = {}
        combos: dict[int, set[int]] = {}
        for combo_id, members in self.combo_members.items():
            c = self.resolve(combo_id)
            if c is None:
                continue
            for member_id in members:
                m = self.resolve(member_id)
                if m is None or m == c:
                    continue
                components.setdefault(c, set()).add(m)
                combos.setdefault(m, set()).add(c)
        self.components_of = {c: frozenset(v) for c, v in components.items()}
        self.combos_with = {m: frozenset(v) for m, v in combos.items()}

    def resolve(self, product_id: str) -> int | None:
        """Phòng/chuyến → index của cha."""
        return self.idx.get(self.parent_of.get(product_id, product_id))

    def purchase_closure(self, units: Iterable[int]) -> set[int]:
        """Tập unit coi là "đã mua" sau luật combo của FR-REC-02 (chốt 2026-10-09): mua một sản phẩm → mọi combo chứa nó;
        mua một combo → mọi thành phần của nó. Chỉ một bậc: mua combo A không kéo theo combo B chỉ vì chung thành phần."""
        bought = set(units)
        out = set(bought)
        for u in bought:
            out |= self.combos_with.get(u, frozenset())
            out |= self.components_of.get(u, frozenset())
        return out

    def mask(self, taxonomy=None, destination=None, only_available=True, only_recommendable=False, *,
             origin_city: str | None = None, destination_city: str | None = None,
             price_min: float | None = None, price_max: float | None = None,
             star_min: float | None = None, exclude_amenities: Iterable[str] = (),
             exclude_brands: Iterable[str] = (), exclude_taxonomies: Iterable[str] = (),
             exclude_flags: Iterable[str] = (), min_occupancy: int | None = None,
             require_entities: Iterable[str] = (),
             stay: StayDates | None = None) -> np.ndarray:
        """Mask bool theo index unit; mọi tham số mới mặc định tắt nên không đổi hành vi cũ.

        Quy ước "không biết" (spec §2.7 [C2]):
        - giá: có một trong hai biên thì unit giá NaN bị LOẠI (contract: giá null bị loại khi áp filter giá);
        - sao: chỉ loại unit sao ĐÃ BIẾT và < `star_min`; NaN giữ lại (mềm — demote ở `soft_star_order`);
        - tiện ích: chỉ loại unit CÓ khoá nằm trong `exclude_amenities`; vắng khoá = không biết → giữ;
        - cờ (`exclude_flags`, `UnitAttributes.FLAGS`): chỉ loại unit CÓ cờ; không cờ = không biết → giữ;
        - sức chứa: chỉ loại unit sức chứa ĐÃ BIẾT và < `min_occupancy`; NaN giữ (không biết ≠ "quá nhỏ").
        - ngày (`stay`, `_stay_mask`): chỉ loại khi BIẾT không dùng được; không có cửa sổ / lịch thì giữ.
        - đơn vị có phòng/chuyến con (`_rooms_ok`): khi có lọc giá, số khách hoặc ngày, phải có ÍT NHẤT MỘT con đang bán được thoả
          ĐỒNG THỜI các điều kiện đó (cùng một phòng, như trang chi tiết chọn hạng phòng); không con nào → loại.
        `exclude_taxonomies`: loại unit có taxonomy nằm trong tập (kiến trúc §6 — chặn cross-vertical).
        `require_entities` (contract 1.18.0, entity gate CỨNG): chỉ giữ unit có ít nhất một khoá entity trong tập
        (`UnitAttributes.entities` — dựng từ TÊN unit, chỉ attraction/combo có khoá); unit không có khoá bị loại — đây là gate,
        không phải quy ước "không biết → giữ". Rỗng = không gate.
        """
        m = np.ones(len(self.units), dtype=bool)
        if only_available:
            m &= self.available
        if only_recommendable:
            m &= self.recommendable
        if taxonomy:
            m &= np.isin(self.taxonomy, [taxonomy] if isinstance(taxonomy, str) else list(taxonomy))
        if destination:
            m &= self.destination == destination
        a = self.attrs
        if origin_city:
            m &= a.origin_city == origin_city
        if destination_city:
            m &= a.destination_city == destination_city
        if price_min is not None or price_max is not None:
            m &= ~np.isnan(a.min_price)
            if price_min is not None:
                m &= a.min_price >= price_min
            if price_max is not None:
                m &= a.min_price <= price_max
        if star_min is not None:
            m &= np.isnan(a.star_rating) | (a.star_rating >= star_min)
        excluded = frozenset(exclude_amenities)
        if excluded:
            m &= np.array([not (keys & excluded) for keys in a.amenities], dtype=bool)
        brands = [b for b in exclude_brands if b]
        if brands:   # "không phải Vinpearl": chỉ loại unit có ghi brand đó; brand rỗng = không biết → giữ
            m &= ~np.isin(a.brand, brands)
        drop_tax = sorted({t for t in exclude_taxonomies if t})
        if drop_tax:
            m &= ~np.isin(self.taxonomy, drop_tax)
        drop_flags = frozenset(f for f in exclude_flags if f)
        if drop_flags:
            m &= np.array([not (f & drop_flags) for f in a.flags], dtype=bool)
        if min_occupancy is not None:
            m &= np.isnan(a.max_occupancy) | (a.max_occupancy >= min_occupancy)
        req = frozenset(k for k in require_entities if k)
        if req:
            m &= np.array([bool(e & req) for e in a.entities], dtype=bool)
        if stay is not None:
            m &= self._stay_mask(stay)
        if price_min is not None or price_max is not None or min_occupancy is not None or stay is not None:
            m &= self._rooms_ok(price_min, price_max, min_occupancy, stay)
        return m

    def _stay_mask(self, stay: StayDates) -> np.ndarray:
        """Bộ lọc ngày (FR-SRC-03 / FR-CAT-03, `domain/catalog/stay_dates.py`), theo loại:
        - khách sạn: ngày nhận và số đêm theo luật đặt phòng (lịch từng hạng phòng xét ở `_rooms_ok`);
        - vé tham quan, golf: `checkIn` trong [available_from, available_to] và ký tự lịch của ngày đó không phải `0`;
        - combo: `checkIn` trong [available_from, available_to];
        - còn lại (route bay): không lọc theo ngày."""
        a, tax = self.attrs, self.taxonomy
        ok = np.ones(len(self.units), dtype=bool)
        start, end = stay.start, stay.end
        in_sale = (np.isnan(a.sale_from) | (a.sale_from <= start)) & (np.isnan(a.sale_to) | (a.sale_to >= start))
        dated = np.isin(tax, ["attraction", "golf", "combo"])
        ok[dated] = in_sale[dated]
        hotels = tax == "hotel"
        window_ok = stay.hotel_window_ok()
        ok[hotels] = window_ok
        for i in np.flatnonzero(ok & np.isin(tax, ["attraction", "golf"])):
            cal = a.calendars[i][0] if a.calendars[i] else None
            ok[i] = cal is None or calendar_open(cal, start, start + 1)
        return ok

    def _rooms_ok(self, price_min: float | None, price_max: float | None, min_occupancy: int | None,
                  stay: StayDates | None) -> np.ndarray:
        """Đơn vị có phòng/chuyến con: True khi có ít nhất một con thoả mọi điều kiện cấp phòng đang áp. Đơn vị không có con:
        True (giá / sức chứa của chính nó đã qua các điều kiện ở `mask`). Ngày chỉ xét ở khách sạn."""
        ok = np.ones(len(self.units), dtype=bool)
        for i, rows in enumerate(self.attrs.children):
            if rows:
                ok[i] = any(_room_matches(row, price_min, price_max, min_occupancy,
                                          stay if self.taxonomy[i] == "hotel" else None) for row in rows)
        return ok

    def matched_children(self, i: int, *, price_min: float | None = None, price_max: float | None = None,
                         min_occupancy: int | None = None, stay: StayDates | None = None, limit: int = 5) -> list[str]:
        """productId các phòng/chuyến con ĐANG BÁN của unit `i` thoả MỌI điều kiện được truyền (kiến trúc §6 parent–child
        filter), theo thứ tự đã lưu (giá tăng dần, giá null cuối), tối đa `limit`. Không truyền điều kiện nào → [].

        Giá: có biên thì con giá null bị loại (như `mask`). Sức chứa: con không biết sức chứa được giữ. Ngày (chỉ khách sạn): con
        không có lịch hoặc đêm ngoài khoảng lịch được giữ, chỉ loại con BIẾT kín."""
        if (price_min is None and price_max is None and min_occupancy is None and stay is None) or limit <= 0:
            return []
        when = stay if self.taxonomy[i] == "hotel" else None
        out: list[str] = []
        for row in self.attrs.children[i]:
            if _room_matches(row, price_min, price_max, min_occupancy, when):
                out.append(row[0])
                if len(out) >= limit:
                    break
        return out

    def star_known_ok(self, star_min: float) -> np.ndarray:
        """True ở unit có sao ĐÃ BIẾT và >= `star_min`; NaN → False (dùng để đẩy unit chưa biết sao xuống sau)."""
        star = self.attrs.star_rating
        return ~np.isnan(star) & (star >= star_min)

    def allowed_ids(self, mask: np.ndarray) -> list[str] | None:
        """productId của các unit trong mask; None khi mask phủ toàn bộ (khỏi gửi filter)."""
        if mask.all():
            return None
        return [self.units[i].product_id for i in np.flatnonzero(mask)]

def _room_matches(row: ChildRow, price_min: float | None, price_max: float | None, min_occupancy: int | None,
                  stay: StayDates | None) -> bool:
    """Một phòng/chuyến con có dùng được cho truy vấn không: đang bán được (`available` + có giá, như `isBookable` ở trang chi
    tiết) và thoả đồng thời giá, số khách, ngày. Cái gì không biết (sức chứa, lịch) thì không loại."""
    _, price, occupancy, cal, sellable = row
    if not sellable:
        return False
    if price_min is not None and price < price_min:
        return False
    if price_max is not None and price > price_max:
        return False
    if min_occupancy is not None and occupancy is not None and occupancy < min_occupancy:
        return False
    return stay is None or cal is None or calendar_open(cal, stay.start, stay.end)


class VectorStorePort(Protocol):
    def load(self) -> UnitIndex: ...


class CdpClientPort(Protocol):
    """Cửa duy nhất vào CDP (handbook §6). Trả dict theo tên trường CDP (camelCase)."""

    def events_for_user(self, cdp_user_id: str) -> list[dict]: ...
    def purchase_events(self, since_days: int = 730) -> list[dict]: ...
    def all_events(self) -> list[dict]: ...
