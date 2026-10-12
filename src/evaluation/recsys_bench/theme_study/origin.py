"""Điểm xuất phát chuyến bay của khách (bậc O1/O2 của plan `docs/plan/2026-10-09-recsys-cong-thuc-oph.md` §3.3).

`ô` = `originCity` của route đứng sau event chuyến bay gần nhất (purchase, cart hoặc view) trong lịch sử train. Engine production
chưa dùng điểm xuất phát dù `UnitIndex.attrs.origin_city` đã có (`domain/catalog/unit_attributes.py`); route không phải chuyến
bay có `origin_city == ""`.

`mis(i) = 1` khi `i` là chuyến bay, `ô` đã biết và `origin_city(i)` khác rỗng và khác `ô`.
"""
from __future__ import annotations

import numpy as np

FLIGHT = "flight"


def infer_origin(events, glob: list[int], index) -> tuple[str | None, int | None]:
    """(ô, unit toàn cục của event đã cho ô). `events`: ResolvedEvent (unit là chỉ số cục bộ của `_LocalSpace`)."""
    best = None
    for e in events:
        g = glob[e.unit]
        if str(index.taxonomy[g]) != FLIGHT:
            continue
        oc = str(index.attrs.origin_city[g] or "")
        if not oc:
            continue
        if best is None or e.days_ago < best[0]:
            best = (e.days_ago, oc, g)
    return (best[1], best[2]) if best else (None, None)


def mismatch(glob: list[int], index, origin: str | None) -> np.ndarray:
    """Vector bool trên không gian cục bộ: chuyến bay có điểm xuất phát khác `origin`."""
    if origin is None or not glob:
        return np.zeros(len(glob), dtype=bool)
    g = np.asarray(glob)
    oc = np.asarray([str(x or "") for x in index.attrs.origin_city[g]], dtype=object)
    return (index.taxonomy[g] == FLIGHT) & (oc != "") & (oc != origin)
