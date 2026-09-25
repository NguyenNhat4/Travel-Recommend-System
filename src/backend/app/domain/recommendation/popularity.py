"""Popularity cho khách mới: điểm đến của tháng, theo mùa, sản phẩm được đặt nhiều. Chỉ đếm purchase, không cần vector."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone

# Mùa du lịch Việt Nam — fallback khi lịch sử chưa đủ; team kinh doanh chỉnh.
SEASONS = {
    "mùa khô miền Nam": {"months": [11, 12, 1, 2, 3, 4], "destinations": ["Phú Quốc", "Nha Trang", "Vũng Tàu", "Côn Đảo"]},
    "hè biển miền Trung": {"months": [5, 6, 7, 8], "destinations": ["Đà Nẵng", "Hội An", "Nha Trang", "Quy Nhơn", "Phú Yên"]},
    "thu đông vùng cao": {"months": [9, 10, 11, 12], "destinations": ["Sa Pa", "Hà Giang", "Đà Lạt", "Mộc Châu"]},
    "tết & lễ hội": {"months": [1, 2], "destinations": ["Hà Nội", "Huế", "Hội An", "Đà Lạt"]},
}


@dataclass
class Purchase:
    unit: int
    destination: str
    booked_at: float          # epoch giây
    using_at: float | None    # epoch giây của usingDate


def season_names(month: int) -> list[str]:
    return [n for n, s in SEASONS.items() if month in s["months"]]


class Popularity:
    def __init__(self, purchases: list[Purchase], catalog_destinations: set[str], now: datetime | None = None):
        self.p = purchases
        self.catalog_destinations = catalog_destinations
        self.now = now or datetime.now(timezone.utc)

    def top_destinations_month(self, k: int = 3, by: str = "booking", window_days: int = 30) -> list[dict]:
        t0, w = self.now.timestamp(), window_days * 86400
        if by == "travel":
            sel = [x for x in self.p if x.using_at and t0 <= x.using_at <= t0 + w]
        else:
            sel = [x for x in self.p if t0 - w <= x.booked_at <= t0]
        c = Counter(x.destination for x in sel)
        return [{"destination": d, "bookings": n,
                 "reason": {"type": "top_month", "by": by, "windowDays": window_days, "period": self.now.strftime("%m/%Y")}}
                for d, n in c.most_common(k)]

    def seasonal_destinations(self, k: int = 3, month: int | None = None) -> list[dict]:
        month = month or self.now.month
        months = {(month - 2) % 12 + 1, month, month % 12 + 1}
        c: Counter = Counter()
        for x in self.p:
            d = datetime.fromtimestamp(x.using_at or x.booked_at, tz=timezone.utc)
            if d.month in months and d.year < self.now.year:
                c[x.destination] += 1
        out = [{"destination": d, "bookings": n, "reason": {"type": "season", "month": month, "source": "history"}}
               for d, n in c.most_common(k)]
        for name in season_names(month):
            for d in SEASONS[name]["destinations"]:
                if len(out) >= k:
                    break
                if d in self.catalog_destinations and all(o["destination"] != d for o in out):
                    out.append({"destination": d, "bookings": 0,
                                "reason": {"type": "season", "month": month, "source": "season_table", "season": name}})
        return out

    def unit_scores(self, destination: str | None = None, window_days: int = 90) -> dict[int, float]:
        """unit index → điểm 0–1 (số lượt mua trong cửa sổ / max). Dùng làm thành phần pop trong recommend."""
        t0, w = self.now.timestamp(), window_days * 86400
        c = Counter(x.unit for x in self.p if t0 - w <= x.booked_at <= t0 and (destination is None or x.destination == destination))
        mx = max(c.values(), default=1)
        return {u: n / mx for u, n in c.items()}
