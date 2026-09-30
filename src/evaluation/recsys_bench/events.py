"""Chuẩn bị event CDP cho harness: lọc purchase không dùng được và chặn event sau mốc đánh giá.

Quy tắc (lịch 10 ngày §3 Day 1 B, đính chính 29/09):
- Loại `purchase` có `productId` không quy được về search unit (orphan; seed cố ý sinh 2 %) và `purchase` thiếu
  `eventGroupId` (seed cố ý sinh 3 %). Hai tập có thể chồng nhau.
- **Giữ** `product_view` / `add_to_cart` / `search` thiếu `eventGroupId`: seed chỉ gắn gid cho purchase
  (`docs/spec/MOCK_DATA_SPEC.md`), engine gom chúng thành trip `_solo_<productId>`.
- Event duyệt web trỏ sản phẩm không có trong catalog: giữ (engine tự bỏ), chỉ đếm.
- Event có `timestamp >= as_of` là lỗi: engine không loại event tương lai mà kẹp `days_ago` về 0
  (`application/recommendation/use_cases.py`), nên harness phải chặn từ đầu vào.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from src.backend.app.application.ports import UnitIndex

#: Persona cố định của seed (`docs/spec/MOCK_DATA_SPEC.md`): vẫn vào tập test nhưng được gắn cờ riêng.
PERSONA_IDS = frozenset({"VP0000001", "VP0000002", "VP0000003", "VP0000004"})


class FutureEventError(ValueError):
    """Có event ở hoặc sau mốc đánh giá — dữ liệu đó không được đi vào engine."""


def parse_ts(value) -> datetime:
    """ISO 8601 (có `Z` hoặc offset) → datetime có múi giờ; thiếu múi giờ thì coi là UTC."""
    dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


@dataclass
class EventFilterReport:
    as_of: str
    total: int = 0
    by_name: dict[str, int] = field(default_factory=dict)
    purchase_total: int = 0
    purchase_orphan: int = 0            # productId không quy được về search unit
    purchase_missing_group: int = 0     # thiếu eventGroupId
    purchase_dropped: int = 0           # hợp của hai tập trên
    browse_orphan: int = 0              # view/cart trỏ sản phẩm ngoài catalog — giữ, chỉ đếm
    search_without_product: int = 0     # search không có productId — giữ
    kept: int = 0
    users_before: int = 0
    users_after: int = 0
    min_timestamp: str | None = None
    max_timestamp: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)

    def lines(self) -> list[str]:
        def pct(n: int) -> str:
            return f"{100 * n / self.purchase_total:.1f} %" if self.purchase_total else "—"
        names = ", ".join(f"{k} {v:,}" for k, v in sorted(self.by_name.items()))
        return [
            f"as_of {self.as_of} · event {self.total:,} ({names}) · khoảng {self.min_timestamp} → {self.max_timestamp}",
            f"purchase {self.purchase_total:,}: orphan {self.purchase_orphan} ({pct(self.purchase_orphan)}) · "
            f"thiếu event_group_id {self.purchase_missing_group} ({pct(self.purchase_missing_group)}) · "
            f"loại (hợp) {self.purchase_dropped} ({pct(self.purchase_dropped)})",
            f"giữ {self.kept:,} event · view/cart ngoài catalog {self.browse_orphan} · search không productId "
            f"{self.search_without_product} · khách {self.users_before:,} → {self.users_after:,}",
            "kỳ vọng seed 42 (seed_report.md 2026-09-24): orphan 63/3.153 (2,0 %), thiếu gid 94/3.153 (3,0 %)",
        ]


def filter_events(events: list[dict], index: UnitIndex, as_of: datetime) -> tuple[list[dict], EventFilterReport]:
    """Trả (event giữ lại, báo cáo). Ném `FutureEventError` nếu có event `timestamp >= as_of`."""
    late = [e for e in events if parse_ts(e["timestamp"]) >= as_of]
    if late:
        first = min(late, key=lambda e: parse_ts(e["timestamp"]))
        raise FutureEventError(f"{len(late)} event có timestamp >= as_of {as_of.isoformat()} "
                               f"(sớm nhất: {first.get('cdpUserId')} {first['timestamp']})")
    report = EventFilterReport(as_of=as_of.isoformat(), total=len(events),
                               by_name=dict(Counter(str(e.get("eventName")) for e in events)))
    if events:
        stamps = sorted(parse_ts(e["timestamp"]) for e in events)
        report.min_timestamp, report.max_timestamp = stamps[0].isoformat(), stamps[-1].isoformat()
    kept: list[dict] = []
    for e in events:
        name, pid = e.get("eventName"), e.get("productId")
        resolvable = bool(pid) and index.resolve(str(pid)) is not None
        if name == "purchase":
            report.purchase_total += 1
            orphan, no_group = not resolvable, not e.get("eventGroupId")
            report.purchase_orphan += orphan
            report.purchase_missing_group += no_group
            if orphan or no_group:
                report.purchase_dropped += 1
                continue
        elif not pid:
            report.search_without_product += name == "search"
        elif not resolvable:
            report.browse_orphan += 1
        kept.append(e)
    report.kept = len(kept)
    report.users_before = len({e.get("cdpUserId") for e in events})
    report.users_after = len({e.get("cdpUserId") for e in kept})
    return kept, report
