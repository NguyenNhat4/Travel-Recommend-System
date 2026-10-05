"""Quyết định lọc cứng điểm đến cho /search từ địa danh trong câu (FR-SRC-03: trang /search không có bộ lọc điểm đến,
"điểm đến do câu truy vấn ngữ nghĩa quyết định"; spec tích hợp §2.2, §2.5).

Bước chuẩn hoá (`normalize.py`) đã nhận ra địa danh trong câu (`NormalizedQuery.destinations`, khớp dài nhất trên token đã fold
với gazetteer của catalog). Hàm ở đây chỉ chọn có đưa địa danh đó vào mask hay không — thuần, không đọc catalog:

- Tham số `destination` tường minh của request luôn thắng (`source = param`); không giao với địa danh suy ra.
- Đúng **một** địa danh trong câu → lọc theo nó (`source = query`).
- Hai địa danh trở lên → **không** lọc (`skipped = multi`): "Hà Nội hoặc Hạ Long", "SG đi DN" (nơi đi + nơi đến), thương hiệu
  "Saigon …" ở một điểm đến khác. OR hai nơi mơ hồ với vé máy bay nên không làm.
- Câu về vé máy bay (`taxonomy = flight` hoặc có cụm `vé máy bay` / `chuyến bay` / `đường bay` / `chặng bay`) → không lọc
  (`skipped = flight`): `destination` của tuyến là nơi đến, câu thường nêu cả hai đầu; khoá theo một địa danh dễ lấy nhầm nơi đi.
- Không chuẩn hoá (`nq = None`) hoặc cờ tắt → không suy ra.

Khi F sau khi lọc rỗng, `SearchProducts` chạy lại không lọc (FR-SRC-04: không có kết quả khớp thì trả kết quả gần nhất) và khai
`fallback = dropped_empty`. Thuần stdlib.
"""
from __future__ import annotations

from dataclasses import dataclass

from .lexical import fold
from .normalize import NormalizedQuery

#: Cụm (đã fold) báo câu hỏi về vé máy bay — dùng substring trên câu đã fold.
FLIGHT_CUES = ("ve may bay", "chuyen bay", "duong bay", "chang bay", "may bay")

SOURCE_PARAM, SOURCE_QUERY = "param", "query"
SKIPPED_MULTI, SKIPPED_FLIGHT = "multi", "flight"


@dataclass(frozen=True)
class DestinationDecision:
    value: str | None                      # điểm đến đưa vào mask; None = không lọc theo điểm đến
    source: str | None                     # "param" | "query" | None
    skipped: str | None = None             # "multi" | "flight" — vì sao không suy ra dù câu có địa danh
    candidates: tuple[str, ...] = ()       # địa danh nhận ra trong câu (NormalizedQuery.destinations)

    def as_dict(self, fallback: str | None = None) -> dict:
        """Khối `diagnostics.destinationFilter` (contract 1.14.0): chỉ phát khi cờ lọc bật."""
        out: dict = {"source": self.source or "none", "value": self.value}
        if self.skipped:
            out["skipped"] = self.skipped
        if fallback:
            out["fallback"] = fallback
        return out


def is_flight_query(query: str, taxonomy: str | None) -> bool:
    if taxonomy == "flight":
        return True
    folded = f" {fold(query)} "
    return any(f" {cue} " in folded for cue in FLIGHT_CUES)


def decide_destination(nq: NormalizedQuery | None, explicit: str | None, taxonomy: str | None, enabled: bool,
                       *, query: str = "") -> DestinationDecision:
    """`explicit` = tham số request; `enabled` = cờ lọc; `query` = câu gốc (để nhận cue bay, không phụ thuộc chuẩn hoá)."""
    candidates = tuple(nq.destinations) if nq is not None else ()
    if explicit:
        return DestinationDecision(explicit, SOURCE_PARAM, None, candidates)
    if not enabled or not candidates:
        return DestinationDecision(None, None, None, candidates)
    if is_flight_query(query or (nq.text if nq is not None else ""), taxonomy):
        return DestinationDecision(None, None, SKIPPED_FLIGHT, candidates)
    if len(candidates) > 1:
        return DestinationDecision(None, None, SKIPPED_MULTI, candidates)
    return DestinationDecision(candidates[0], SOURCE_QUERY, None, candidates)
