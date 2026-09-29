"""Part 3 — ngôn ngữ filter DUY NHẤT (AST JSON), validator, evaluator tham chiếu numpy ("sự thật").

Filter := null | {"and": [F…]} | {"or": [F…]} | {"not": F} | {"eq": [field, v]} | {"in": [field, [v…]]}
        | {"range": [field, {"gte"|"gt"|"lte"|"lt": number…}]} | {"all": ["amenity_ids", [int…]]}
        | {"any": ["amenity_ids", [int…]]} | {"geo": {"lat", "lon", "radius_m"}} | {"id_in": [uuid…]}

Ngữ nghĩa bắt buộc giống nhau ở mọi engine (spec P3.1):
1. NULL không bao giờ khớp range.  2. all/any rỗng là AST không hợp lệ.
3. not chỉ bọc eq trên trường không null, hoặc any trên amenity_ids (mảng rỗng thoả not any).
4. geo: haversine R = 6.371.008,8 m, khớp khi d ≤ r; |d − r| ≤ tol·r là vùng biên (không tính vi phạm / miss).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import pyarrow.parquet as pq
import scipy.sparse as sp

EARTH_R_M = 6_371_008.8
KEYWORD_FIELDS = ("taxonomy", "destination", "variant")
BOOL_FIELDS = ("available",)
NUM_FIELDS = ("unit_price", "star_rating")      # nullable
ARRAY_FIELDS = ("amenity_ids",)
RANGE_OPS = ("gte", "gt", "lte", "lt")
OPS = ("and", "or", "not", "eq", "in", "range", "all", "any", "geo", "id_in")


class InvalidFilter(ValueError):
    pass


# ---------------------------------------------------------------- validator
def validate(f: Any) -> None:
    if f is None:
        return
    _validate(f, top=True)


def _one(node: Any) -> tuple[str, Any]:
    if not isinstance(node, dict) or len(node) != 1:
        raise InvalidFilter(f"node phải là dict một khoá: {node!r}")
    (op, arg), = node.items()
    if op not in OPS:
        raise InvalidFilter(f"toán tử lạ: {op}")
    return op, arg


def _validate(node: Any, top: bool = False) -> None:
    op, arg = _one(node)
    if op in ("and", "or"):
        if not isinstance(arg, list) or not arg:
            raise InvalidFilter(f"{op} cần danh sách khác rỗng")
        for ch in arg:
            _validate(ch)
    elif op == "not":
        cop, carg = _one(arg)
        if cop == "eq" and isinstance(carg, list) and len(carg) == 2 and carg[0] in KEYWORD_FIELDS + BOOL_FIELDS:
            _validate(arg)
        elif cop == "any" and isinstance(carg, list) and len(carg) == 2 and carg[0] in ARRAY_FIELDS:
            _validate(arg)
        else:
            raise InvalidFilter(f"not chỉ được bọc eq trên trường không null hoặc any trên amenity_ids, gặp: {arg!r}")
    elif op == "eq":
        if not (isinstance(arg, list) and len(arg) == 2):
            raise InvalidFilter("eq cần [field, value]")
        fld, v = arg
        if fld in KEYWORD_FIELDS:
            if not isinstance(v, str):
                raise InvalidFilter(f"eq {fld} cần chuỗi")
        elif fld in BOOL_FIELDS:
            if not isinstance(v, bool):
                raise InvalidFilter(f"eq {fld} cần bool")
        else:
            raise InvalidFilter(f"eq không hỗ trợ trường {fld}")
    elif op == "in":
        if not (isinstance(arg, list) and len(arg) == 2 and arg[0] in KEYWORD_FIELDS and isinstance(arg[1], list) and arg[1]):
            raise InvalidFilter("in cần [keyword_field, [giá trị…]] khác rỗng")
        if not all(isinstance(v, str) for v in arg[1]):
            raise InvalidFilter("in chỉ nhận chuỗi")
    elif op == "range":
        if not (isinstance(arg, list) and len(arg) == 2 and arg[0] in NUM_FIELDS and isinstance(arg[1], dict) and arg[1]):
            raise InvalidFilter("range cần [unit_price|star_rating, {gte|gt|lte|lt: số}]")
        for k, v in arg[1].items():
            if k not in RANGE_OPS or isinstance(v, bool) or not isinstance(v, (int, float)):
                raise InvalidFilter(f"range: khoá/giá trị không hợp lệ {k}={v!r}")
    elif op in ("all", "any"):
        if not (isinstance(arg, list) and len(arg) == 2 and arg[0] in ARRAY_FIELDS):
            raise InvalidFilter(f"{op} cần ['amenity_ids', [id…]]")
        ids = arg[1]
        if not isinstance(ids, list) or not ids:
            raise InvalidFilter(f"{op} với danh sách rỗng là AST không hợp lệ")
        if not all(isinstance(i, int) and not isinstance(i, bool) for i in ids):
            raise InvalidFilter(f"{op}: id amenity phải là int")
    elif op == "geo":
        if not (isinstance(arg, dict) and set(arg) == {"lat", "lon", "radius_m"}):
            raise InvalidFilter("geo cần {lat, lon, radius_m}")
        if not (-90 <= arg["lat"] <= 90 and -180 <= arg["lon"] <= 180 and arg["radius_m"] > 0):
            raise InvalidFilter("geo: toạ độ/bán kính ngoài miền")
    elif op == "id_in":
        if not (isinstance(arg, list) and arg and all(isinstance(x, str) for x in arg)):
            raise InvalidFilter("id_in cần danh sách uuid khác rỗng")


def ops_used(f: Any) -> set[str]:
    out: set[str] = set()
    for op, _ in walk(f):
        out.add(op)
    return out


def walk(f: Any) -> Iterator[tuple[str, Any]]:
    if f is None:
        return
    op, arg = _one(f)
    yield op, arg
    if op in ("and", "or"):
        for ch in arg:
            yield from walk(ch)
    elif op == "not":
        yield from walk(arg)


def has_geo(f: Any) -> bool:
    return any(op == "geo" for op, _ in walk(f))


# ---------------------------------------------------------------- bảng metadata
@dataclass
class Table:
    n: int
    cat_codes: dict[str, np.ndarray]
    cat_index: dict[str, dict[str, int]]
    available: np.ndarray
    num: dict[str, np.ndarray]
    lat: np.ndarray
    lon: np.ndarray
    amen: sp.csc_matrix                     # N × (max_id + 1), bool
    ids: np.ndarray | None = None           # object (uuid chuỗi) — chỉ để id_in
    _cache: dict = field(default_factory=dict, repr=False)
    _lat_order: np.ndarray | None = field(default=None, repr=False)
    _amen_csr: sp.csr_matrix | None = field(default=None, repr=False)     # dạng theo dòng, dựng MỘT lần cho take()

    @classmethod
    def from_parquet(cls, path: Path, with_ids: bool = True) -> "Table":
        cols = ["variant", "taxonomy", "destination", "available", "amenity_ids", "unit_price", "star_rating", "lat", "lon"]
        if with_ids:
            cols.append("id")
        t = pq.read_table(path, columns=cols)
        n = t.num_rows
        codes, index = {}, {}
        for f in KEYWORD_FIELDS:
            arr = t.column(f).combine_chunks().dictionary_encode()
            codes[f] = arr.indices.to_numpy(zero_copy_only=False).astype(np.int32)
            index[f] = {v: i for i, v in enumerate(arr.dictionary.to_pylist())}
        la = t.column("amenity_ids").combine_chunks()
        offs = la.offsets.to_numpy()
        vals = la.flatten().to_numpy(zero_copy_only=False).astype(np.int32)
        return cls._build(n, codes, index,
                          t.column("available").to_numpy().astype(bool),
                          {f: t.column(f).to_numpy(zero_copy_only=False).astype(np.float64) for f in NUM_FIELDS},
                          t.column("lat").to_numpy().astype(np.float64), t.column("lon").to_numpy().astype(np.float64),
                          offs, vals, t.column("id").to_numpy(zero_copy_only=False) if with_ids else None)

    @classmethod
    def from_records(cls, recs: list[dict]) -> "Table":
        """Cho unit test: mỗi record có variant, taxonomy, destination, available, amenity_ids, unit_price, star_rating, lat, lon, id."""
        n = len(recs)
        codes, index = {}, {}
        for f in KEYWORD_FIELDS:
            vals = sorted({r[f] for r in recs})
            index[f] = {v: i for i, v in enumerate(vals)}
            codes[f] = np.array([index[f][r[f]] for r in recs], dtype=np.int32)
        offs = np.zeros(n + 1, dtype=np.int64)
        flat: list[int] = []
        for i, r in enumerate(recs):
            flat.extend(r["amenity_ids"])
            offs[i + 1] = len(flat)
        num = {f: np.array([np.nan if r[f] is None else r[f] for r in recs], dtype=np.float64) for f in NUM_FIELDS}
        return cls._build(n, codes, index, np.array([r["available"] for r in recs], dtype=bool), num,
                          np.array([r["lat"] for r in recs], dtype=np.float64), np.array([r["lon"] for r in recs], dtype=np.float64),
                          offs, np.array(flat, dtype=np.int32), np.array([r.get("id", str(i)) for i, r in enumerate(recs)], dtype=object))

    @classmethod
    def _build(cls, n, codes, index, available, num, lat, lon, offs, vals, ids) -> "Table":
        width = int(vals.max()) + 1 if len(vals) else 1
        rows = np.repeat(np.arange(n, dtype=np.int32), np.diff(offs).astype(np.int64))
        amen = sp.csc_matrix((np.ones(len(vals), dtype=bool), (rows, vals)), shape=(n, width))
        amen.sum_duplicates()
        return cls(n=n, cat_codes=codes, cat_index=index, available=available, num=num, lat=lat, lon=lon, amen=amen, ids=ids)

    # -- truy cập có cache (Part 3 sinh nhiều filter trên cùng bảng)
    def eq_mask(self, fld: str, v: Any) -> np.ndarray:
        key = ("eq", fld, v)
        m = self._cache.get(key)
        if m is None:
            if fld in KEYWORD_FIELDS:
                code = self.cat_index[fld].get(v, -1)
                m = self.cat_codes[fld] == code
            elif fld == "available":
                m = self.available == bool(v)
            else:
                raise InvalidFilter(f"eq không hỗ trợ {fld}")
            self._cache[key] = m
        return m

    def amen_mask(self, aid: int) -> np.ndarray:
        """Mask mới (không cache: ở 1M mỗi mask 1 MB × vài trăm id)."""
        m = np.zeros(self.n, dtype=bool)
        m[self.amen_rows(aid)] = True
        return m

    def amen_rows(self, aid: int) -> np.ndarray:
        if 0 <= aid < self.amen.shape[1]:
            return self.amen.indices[self.amen.indptr[aid]:self.amen.indptr[aid + 1]]
        return np.empty(0, dtype=np.int32)

    def distance_m(self, lat: float, lon: float, rows: np.ndarray | None = None) -> np.ndarray:
        la = self.lat if rows is None else self.lat[rows]
        lo = self.lon if rows is None else self.lon[rows]
        return haversine_m(lat, lon, la, lo)

    def geo_candidates(self, lat: float, lon: float, radius_m: float) -> np.ndarray:
        """Dòng nằm trong dải vĩ độ ± r (lọc thô trước khi tính haversine)."""
        if self._lat_order is None:
            self._lat_order = np.argsort(self.lat, kind="stable")
            self._lat_sorted = self.lat[self._lat_order]
        dlat = np.degrees(radius_m / EARTH_R_M) * 1.0001
        a = np.searchsorted(self._lat_sorted, lat - dlat, side="left")
        b = np.searchsorted(self._lat_sorted, lat + dlat, side="right")
        return self._lat_order[a:b]

    def take(self, rows: np.ndarray) -> "Table":
        """Bảng con gồm các dòng cho trước (kiểm vi phạm trên kết quả engine mà không đánh giá lại cả N dòng)."""
        rows = np.asarray(rows, dtype=np.int64)
        if len(rows):
            if self._amen_csr is None:          # ở 1M: tocsr() ~0,6 s — không làm lại cho mỗi query
                self._amen_csr = self.amen.tocsr()
            amen = self._amen_csr[rows].tocsc()
        else:
            amen = self.amen[:0]
        return Table(n=len(rows), cat_codes={k: v[rows] for k, v in self.cat_codes.items()}, cat_index=self.cat_index,
                     available=self.available[rows], num={k: v[rows] for k, v in self.num.items()}, lat=self.lat[rows],
                     lon=self.lon[rows], amen=amen, ids=None if self.ids is None else self.ids[rows])

    def id_mask(self, ids: list[str]) -> np.ndarray:
        if self.ids is None:
            raise InvalidFilter("bảng không có cột id")
        return np.isin(self.ids, np.array(ids, dtype=object))


def haversine_m(lat1, lon1, lat2, lon2) -> np.ndarray:
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dl = np.radians(np.asarray(lon2) - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * EARTH_R_M * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


# ---------------------------------------------------------------- evaluator
def mask(f: Any, t: Table, geo_scale: float = 1.0) -> np.ndarray:
    """Tập thoả filter (mảng bool MỚI, caller sửa tại chỗ được). geo_scale ≠ 1 chỉ để tính vùng biên."""
    return np.array(_mask(f, t, geo_scale), dtype=bool, copy=True)


def _mask(f: Any, t: Table, geo_scale: float) -> np.ndarray:
    """Có thể trả mảng đang nằm trong cache của Table — KHÔNG sửa tại chỗ kết quả."""
    if f is None:
        return np.ones(t.n, dtype=bool)
    op, arg = _one(f)
    if op == "and":
        m = _mask(arg[0], t, geo_scale).copy()
        for ch in arg[1:]:
            m &= _mask(ch, t, geo_scale)
        return m
    if op == "or":
        m = _mask(arg[0], t, geo_scale).copy()
        for ch in arg[1:]:
            m |= _mask(ch, t, geo_scale)
        return m
    if op == "not":
        return ~_mask(arg, t, geo_scale)
    if op == "eq":
        return t.eq_mask(arg[0], arg[1])
    if op == "in":
        fld, vals = arg
        codes = [t.cat_index[fld][v] for v in vals if v in t.cat_index[fld]]
        return np.isin(t.cat_codes[fld], np.array(codes, dtype=np.int32))
    if op == "range":
        fld, cond = arg
        x = t.num[fld]
        m = ~np.isnan(x)                       # NULL không bao giờ khớp range
        for k, v in cond.items():
            m &= {"gte": x >= v, "gt": x > v, "lte": x <= v, "lt": x < v}[k]
        return m
    if op == "all":
        rows = t.amen_rows(arg[1][0])
        for a in arg[1][1:]:
            rows = np.intersect1d(rows, t.amen_rows(a), assume_unique=True)
        m = np.zeros(t.n, dtype=bool)
        m[rows] = True
        return m
    if op == "any":
        m = np.zeros(t.n, dtype=bool)
        for a in arg[1]:
            m[t.amen_rows(a)] = True
        return m
    if op == "geo":
        r = arg["radius_m"] * geo_scale
        cand = t.geo_candidates(arg["lat"], arg["lon"], r)
        m = np.zeros(t.n, dtype=bool)
        if len(cand):
            m[cand[t.distance_m(arg["lat"], arg["lon"], cand) <= r]] = True
        return m
    if op == "id_in":
        return t.id_mask(arg)
    raise InvalidFilter(op)


def boundary(f: Any, t: Table, tol: float) -> np.ndarray:
    """Dòng mà kết quả có thể đổi khi bán kính geo lệch ±tol·r (geo chỉ xuất hiện dương vì not không bọc geo → đơn điệu)."""
    if f is None or not has_geo(f):
        return np.zeros(t.n, dtype=bool)
    return mask(f, t, 1.0 + tol) & ~mask(f, t, 1.0 - tol)


def strict_mask(f: Any, t: Table, tol: float) -> tuple[np.ndarray, np.ndarray]:
    """(mask, boundary) — tập chặt của GT = mask & ~boundary."""
    m = mask(f, t)
    b = boundary(f, t, tol)
    return m, b
