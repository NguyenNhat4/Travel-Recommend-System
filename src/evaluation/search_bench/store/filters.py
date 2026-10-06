"""Part 4 — filter AST (JSON) → weaviate Filter, kèm evaluator tham chiếu trên pandas ("sự thật" để kiểm Weaviate).

AST (spec Part 4):
    F := {"and": [F…]} | {"or": [F…]} | {"not": F}
       | {"eq": [field, v]} | {"in": [field, [v…]]}
       | {"contains_all": ["amenity_ids", [k…]]} | {"contains_any": ["amenity_ids", [k…]]}
       | {"lte"|"lt"|"gte"|"gt": [field, number]}

Ngữ nghĩa (giống `vector_bench/filters.py`): NULL không khớp eq / in / so sánh; `not` chỉ được bọc `eq` trên trường
không bao giờ null hoặc `contains_any` trên amenity_ids (mảng rỗng thoả "không chứa"). Amenity ghi bằng **khoá**
(`kids_club`, `raw:<slug>`) hoặc id int; `resolve` đổi khoá → id theo `amenity_vocab.json` của dataset.

Phase A (05/10, kiến trúc search OTA §4–§6) — chỉ cho evaluator pandas `mask()` (filter `forbidden` của gold / overrides):
- `origin_city`, `destination_city`: keyword CÓ THỂ null ("" ngoài tuyến bay — cột RAM `runner.load_env` gắn thêm, không nằm
  trong items.parquet); `not` được bọc `eq` trên hai trường này ("không phải chặng A→B" giữ cả unit không có chặng).
- `brand`: keyword có thể null của items.parquet; `not(eq brand)` cho `appliedFilters.hard.mustNotBrands` của arm APP ("không
  phải thương hiệu X" giữ cả unit không ghi thương hiệu). `to_weaviate` vẫn dựng `eq brand` nhưng từ chối `not(eq brand)`.
- `features`: mảng **khoá tiện ích của backend** (`domain/search/amenities.py`, vd `pool`, `kitchen`) — `contains_any` /
  `contains_all` so chuỗi, `resolve` KHÔNG đổi sang id.
- `not` được bọc `and` / `or` (filter tuyến: `not(and(origin, destination))`).
`to_weaviate` không diễn đạt được các hình dạng này và báo `FilterError` rõ — nó chỉ dùng cho filter gold của arm không
phải APP (vẫn đơn giản).
"""
from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd

KEYWORD_FIELDS = ("product_id", "taxonomy", "variant", "destination", "province", "brand", "parent_product_id",
                  "origin_city", "destination_city")
NON_NULL_KEYWORDS = ("product_id", "taxonomy", "variant", "destination")
#: keyword có thể null nhưng vẫn được `not(eq)` (ngữ nghĩa "không phải X" giữ cả dòng không có giá trị) — chỉ evaluator pandas
NOT_EQ_NULLABLE = ("origin_city", "destination_city", "brand")
#: cột RAM của bench (`runner.load_env` gắn), không có trong collection Weaviate — `to_weaviate` từ chối mọi toán tử trên chúng
RAM_ONLY_FIELDS = ("origin_city", "destination_city")
NUMBER_FIELDS = ("star_rating", "unit_price_min")
BOOL_FIELDS = ("ticketed", "family_friendly", "ocean_view", "available")
ARRAY_FIELDS = ("amenity_ids", "features")
#: mảng chuỗi (khoá backend) — `resolve` giữ nguyên, `mask` so chuỗi
STRING_ARRAY_FIELDS = ("features",)
RANGE_OPS = ("lte", "lt", "gte", "gt")
OPS = ("and", "or", "not", "eq", "in", "contains_all", "contains_any", *RANGE_OPS)


class FilterError(ValueError):
    pass


def _one(node: Any) -> tuple[str, Any]:
    if not isinstance(node, dict) or len(node) != 1:
        raise FilterError(f"mỗi node phải là dict một khoá: {node!r}")
    (op, arg), = node.items()
    if op not in OPS:
        raise FilterError(f"toán tử lạ {op!r} (có: {', '.join(OPS)})")
    return op, arg


def _pair(op: str, arg: Any) -> tuple[str, Any]:
    if not (isinstance(arg, list) and len(arg) == 2 and isinstance(arg[0], str)):
        raise FilterError(f"{op} cần [trường, giá trị], gặp {arg!r}")
    return arg[0], arg[1]


def validate(node: Any) -> None:
    op, arg = _one(node)
    if op in ("and", "or"):
        if not isinstance(arg, list) or not arg:
            raise FilterError(f"{op} cần danh sách khác rỗng")
        for ch in arg:
            validate(ch)
    elif op == "not":
        cop, carg = _one(arg)
        ok = cop in ("and", "or") or \
             (cop == "eq" and _pair(cop, carg)[0] in (*NON_NULL_KEYWORDS, *NOT_EQ_NULLABLE)) or \
             (cop == "contains_any" and _pair(cop, carg)[0] in ARRAY_FIELDS)
        if not ok:
            raise FilterError(f"not chỉ bọc and/or, eq trên {', '.join((*NON_NULL_KEYWORDS, *NOT_EQ_NULLABLE))} hoặc "
                              f"contains_any trên {', '.join(ARRAY_FIELDS)}, gặp {arg!r}")
        validate(arg)
    elif op == "eq":
        f, v = _pair(op, arg)
        if f in KEYWORD_FIELDS and isinstance(v, str):
            return
        if f in BOOL_FIELDS and isinstance(v, bool):
            return
        raise FilterError(f"eq {f}: trường phải là keyword (giá trị chuỗi) hoặc bool (giá trị true/false), gặp {v!r}")
    elif op == "in":
        f, v = _pair(op, arg)
        if f not in KEYWORD_FIELDS or not isinstance(v, list) or not v or not all(isinstance(x, str) for x in v):
            raise FilterError(f"in cần [keyword, [chuỗi…]] khác rỗng, gặp {arg!r}")
    elif op in ("contains_all", "contains_any"):
        f, v = _pair(op, arg)
        if f not in ARRAY_FIELDS or not isinstance(v, list) or not v or not all(isinstance(x, (str, int)) and not isinstance(x, bool) for x in v):
            raise FilterError(f"{op} cần [{'|'.join(ARRAY_FIELDS)}, [khoá|id…]] khác rỗng, gặp {arg!r}")
        if f in STRING_ARRAY_FIELDS and not all(isinstance(x, str) for x in v):
            raise FilterError(f"{op} {f}: giá trị phải là khoá chuỗi (từ vựng backend amenities.py), gặp {v!r}")
    else:  # range
        f, v = _pair(op, arg)
        if f not in NUMBER_FIELDS or isinstance(v, bool) or not isinstance(v, (int, float)):
            raise FilterError(f"{op} cần [{'|'.join(NUMBER_FIELDS)}, số], gặp {arg!r}")


def parse(raw: str | dict | None) -> dict | None:
    if raw is None or raw == "" or raw == {}:
        return None
    try:
        node = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError as e:
        raise FilterError(f"filter không phải JSON: {e}") from None
    validate(node)
    return node


def amenity_key_index(amenity_vocab: dict[str, dict]) -> dict[str, int]:
    """amenity_vocab.json ({id: {key, …}}) → {key: id}."""
    return {e["key"]: int(i) for i, e in amenity_vocab.items()}


def resolve(node: dict, key_to_id: dict[str, int]) -> dict:
    """Bản sao của AST với khoá amenity đổi sang id int; khoá lạ → FilterError."""
    op, arg = _one(node)
    if op in ("and", "or"):
        return {op: [resolve(ch, key_to_id) for ch in arg]}
    if op == "not":
        return {op: resolve(arg, key_to_id)}
    if op in ("contains_all", "contains_any"):
        if arg[0] in STRING_ARRAY_FIELDS:            # khoá backend giữ nguyên chuỗi, chỉ bỏ trùng
            return {op: [arg[0], sorted(set(arg[1]))]}
        out = []
        for x in arg[1]:
            if isinstance(x, int):
                out.append(x)
            elif x in key_to_id:
                out.append(key_to_id[x])
            else:
                raise FilterError(f"khoá amenity lạ {x!r} — xem filter_fields.amenity_keys trong vocab.json")
        return {op: [arg[0], sorted(set(out))]}
    return {op: list(arg)}


# ------------------------------------------------------------------ Weaviate
def to_weaviate(node: dict | None):
    if node is None:
        return None
    from weaviate.classes.query import Filter
    op, arg = _one(node)
    if op == "and":
        return Filter.all_of([to_weaviate(ch) for ch in arg])
    if op == "or":
        return Filter.any_of([to_weaviate(ch) for ch in arg])
    if op == "not":
        cop, carg = _one(arg)
        if cop in ("and", "or") or (cop == "eq" and carg[0] not in NON_NULL_KEYWORDS) or carg[0] in STRING_ARRAY_FIELDS:
            raise FilterError(f"to_weaviate không diễn đạt được not{{{cop}}} trên {carg!r} — hình dạng này chỉ dành cho evaluator "
                              "pandas (filter forbidden của gold)")
        f, v = carg
        return Filter.by_property(f).not_equal(v) if cop == "eq" else Filter.by_property(f).contains_none(list(v))
    f, v = arg
    if f in STRING_ARRAY_FIELDS or f in RAM_ONLY_FIELDS:
        raise FilterError(f"to_weaviate: trường {f!r} là cột RAM của bench, không có trong collection Weaviate")
    p = Filter.by_property(f)
    if op == "eq":
        return p.equal(v)
    if op == "in":
        return p.contains_any(list(v))
    if op == "contains_all":
        return p.contains_all(list(v))
    if op == "contains_any":
        return p.contains_any(list(v))
    return {"lte": p.less_or_equal, "lt": p.less_than, "gte": p.greater_or_equal, "gt": p.greater_than}[op](v)


# ------------------------------------------------------------------ pandas (tham chiếu)
def _col_eq(s: pd.Series, v: Any) -> np.ndarray:
    return np.array([x is not None and not (isinstance(x, float) and np.isnan(x)) and x == v for x in s], dtype=bool)


def _as_set(x: Any) -> set:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return set()
    return {int(i) for i in x}


def _as_str_set(x: Any) -> set:
    """Mảng khoá chuỗi (`features`): None / NaN → rỗng; phần tử về str."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return set()
    return {str(i) for i in x}


def mask(node: dict | None, df: pd.DataFrame) -> np.ndarray:
    """Evaluator tham chiếu: True cho dòng thoả filter (AST đã resolve sang id)."""
    if node is None:
        return np.ones(len(df), dtype=bool)
    op, arg = _one(node)
    if op == "and":
        return np.logical_and.reduce([mask(ch, df) for ch in arg])
    if op == "or":
        return np.logical_or.reduce([mask(ch, df) for ch in arg])
    if op == "not":
        return ~mask(arg, df)
    f, v = arg
    col = df[f]
    if op == "eq":
        return _col_eq(col, v)
    if op == "in":
        vals = set(v)
        return np.array([x in vals for x in col], dtype=bool)
    as_set = _as_str_set if f in STRING_ARRAY_FIELDS else _as_set
    if op == "contains_all":
        need = set(v)
        return np.array([need <= as_set(x) for x in col], dtype=bool)
    if op == "contains_any":
        need = set(v)
        return np.array([bool(need & as_set(x)) for x in col], dtype=bool)
    num = pd.to_numeric(col, errors="coerce").to_numpy(dtype=float)
    with np.errstate(invalid="ignore"):
        res = {"lte": num <= v, "lt": num < v, "gte": num >= v, "gt": num > v}[op]
    return np.where(np.isnan(num), False, res)
