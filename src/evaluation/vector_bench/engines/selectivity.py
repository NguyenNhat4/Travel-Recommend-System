"""Ước lượng kích thước tập lọc cho mode `auto` của adapter Postgres (spec P5.3, fasttrack §4).

KHÔNG chạy COUNT trước mỗi query (thêm một round trip = cộng thẳng vào P99). Thống kê dựng MỘT lần từ DB rồi cache:
- đếm chính xác theo destination × taxonomy × available (dùng chung cho các eq trên ba trường này);
- tần suất variant, tần suất từng amenity id (giả định độc lập);
- phân vị unit_price, phân bố star_rating (kèm tỷ lệ null) — range;
- mẫu ngẫu nhiên toạ độ — geo.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from ..filters import haversine_m

CELL_FIELDS = ("destination", "taxonomy", "available")


class SelectivityEstimator:
    def __init__(self, state: dict[str, Any]):
        self.state = state
        self.n = int(state["n"])
        self.cells = [((d, t, bool(a)), int(c)) for d, t, a, c in state["cells"]]
        self.variant = {k: int(v) for k, v in state["variant"].items()}
        self.amen = {int(k): int(v) for k, v in state["amenity"].items()}
        self.price_q = np.asarray(state["price_quantiles"], dtype=np.float64)
        self.price_nonnull = int(state["price_nonnull"])
        self.star = {float(k): int(v) for k, v in state["star"].items()}
        self.geo = np.asarray(state["geo_sample"], dtype=np.float64).reshape(-1, 2)

    # ---- xác suất một vị từ
    def _p_cells(self, cons: dict[str, set]) -> float:
        tot = 0
        for (d, t, a), c in self.cells:
            if ("destination" in cons and d not in cons["destination"]) or ("taxonomy" in cons and t not in cons["taxonomy"]) \
                    or ("available" in cons and a not in cons["available"]):
                continue
            tot += c
        return tot / self.n if self.n else 0.0

    def _p_range(self, fld: str, cond: dict) -> float:
        if fld == "unit_price":
            if self.price_nonnull == 0 or len(self.price_q) == 0:
                return 0.0
            lo, hi = -np.inf, np.inf
            for k, v in cond.items():
                if k in ("gte", "gt"):
                    lo = max(lo, v)
                else:
                    hi = min(hi, v)
            qs = self.price_q
            frac = (np.searchsorted(qs, hi, side="right") - np.searchsorted(qs, lo, side="left")) / len(qs)
            return float(np.clip(frac, 0, 1)) * self.price_nonnull / self.n
        tot = 0
        for s, c in self.star.items():
            ok = True
            for k, v in cond.items():
                ok &= {"gte": s >= v, "gt": s > v, "lte": s <= v, "lt": s < v}[k]
            tot += c if ok else 0
        return tot / self.n

    def _p_geo(self, g: dict) -> float:
        if len(self.geo) == 0:
            return 1.0
        d = haversine_m(g["lat"], g["lon"], self.geo[:, 0], self.geo[:, 1])
        return float((d <= g["radius_m"]).mean())

    def p(self, f: Any) -> float:
        if f is None:
            return 1.0
        (op, arg), = f.items()
        if op == "and":
            cons: dict[str, set] = {}
            rest = 1.0
            for ch in arg:
                (cop, carg), = ch.items()
                if cop == "eq" and carg[0] in CELL_FIELDS:
                    s = cons.setdefault(carg[0], {carg[1]})
                    s &= {carg[1]}
                elif cop == "in" and carg[0] in CELL_FIELDS:
                    s = cons.setdefault(carg[0], set(carg[1]))
                    s &= set(carg[1])
                else:
                    rest *= self.p(ch)
            return (self._p_cells(cons) if cons else 1.0) * rest
        if op == "or":
            q = 1.0
            for ch in arg:
                q *= 1.0 - self.p(ch)
            return 1.0 - q
        if op == "not":
            return 1.0 - self.p(arg)
        if op == "eq":
            fld, v = arg
            if fld in CELL_FIELDS:
                return self._p_cells({fld: {v}})
            return self.variant.get(v, 0) / self.n
        if op == "in":
            fld, vals = arg
            if fld in CELL_FIELDS:
                return self._p_cells({fld: set(vals)})
            return sum(self.variant.get(v, 0) for v in vals) / self.n
        if op == "range":
            return self._p_range(arg[0], arg[1])
        if op == "all":
            out = 1.0
            for a in arg[1]:
                out *= self.amen.get(int(a), 0) / self.n
            return out
        if op == "any":
            q = 1.0
            for a in arg[1]:
                q *= 1.0 - self.amen.get(int(a), 0) / self.n
            return 1.0 - q
        if op == "geo":
            return self._p_geo(arg)
        if op == "id_in":
            return min(1.0, len(arg) / self.n)
        raise ValueError(op)

    def estimate(self, f: Any) -> float:
        return self.p(f) * self.n


def collect_pg_stats(conn, table: str = "items", geo_sample: int = 20000, quantiles: int = 1001) -> dict[str, Any]:
    """Thống kê cache — chạy một lần (không nằm trên đường query)."""
    n = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    cells = conn.execute(f"SELECT destination, taxonomy, available, count(*) FROM {table} GROUP BY 1, 2, 3").fetchall()
    variant = dict(conn.execute(f"SELECT variant, count(*) FROM {table} GROUP BY 1").fetchall())
    amen = dict(conn.execute(f"SELECT a, count(*) FROM {table}, unnest(amenity_ids) AS a GROUP BY 1").fetchall())
    qs = [i / (quantiles - 1) for i in range(quantiles)]
    pq_row = conn.execute(f"SELECT percentile_disc(%s::float8[]) WITHIN GROUP (ORDER BY unit_price), count(unit_price) "
                          f"FROM {table} WHERE unit_price IS NOT NULL", (qs,)).fetchone()
    star = dict(conn.execute(f"SELECT star_rating, count(*) FROM {table} WHERE star_rating IS NOT NULL GROUP BY 1").fetchall())
    pct = min(100.0, 100.0 * geo_sample / max(n, 1))
    geo = conn.execute(f"SELECT lat, lon FROM {table} TABLESAMPLE BERNOULLI (%s) REPEATABLE (42) LIMIT %s",
                       (pct, geo_sample)).fetchall()
    return {"n": int(n), "cells": [[d, t, bool(a), int(c)] for d, t, a, c in cells],
            "variant": {k: int(v) for k, v in variant.items()}, "amenity": {str(k): int(v) for k, v in amen.items()},
            "price_quantiles": [float(x) for x in (pq_row[0] or [])], "price_nonnull": int(pq_row[1] or 0),
            "star": {str(float(k)): int(v) for k, v in star.items()}, "geo_sample": [[float(a), float(b)] for a, b in geo]}
