"""Tra cứu catalog cho người soạn / gán nhãn gold (app Streamlit, chế độ "Tra cứu catalog" và "Bổ sung câu hỏi").

Chỉ đọc dữ liệu bench đã dựng (`sb catalog build`): `items.parquet` (search unit) và `amenity_vocab.json`. Không import
streamlit để test được thuần. Mọi so khớp chữ dùng `fold` (bỏ dấu, thường, bỏ ký tự lạ) như kênh BM25 của bench.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

from ..vector_bench.lexical import fold
from . import paths
from .catalog import CatalogError, read_items
from .store import filters as F

VARIANTS = ("hotel_property", "attraction", "combo", "flight_route", "golf")
PLACE_COLUMNS = ("destination", "province", "city")


@dataclass
class Catalog:
    items: pd.DataFrame                      # index = product_id
    vocab: dict[int, dict]                   # amenity id → {key, label, source, freq}
    key_to_id: dict[str, int]

    def amenity_label(self, i: int) -> str:
        return (self.vocab.get(int(i)) or {}).get("label", str(i))


def _folded(s: pd.Series) -> pd.Series:
    return s.fillna("").astype(str).map(fold)


def load_catalog(dataset: str = "jsonl") -> Catalog:
    p = paths.data_dir(dataset, create=False) / paths.AMENITY_VOCAB
    items = read_items(dataset)
    if not p.exists():
        raise CatalogError(f"chưa có {p} — chạy `sb --dataset {dataset} catalog build` trước")
    return catalog_from(items, json.loads(p.read_text(encoding="utf-8")))


def catalog_from(items: pd.DataFrame, amenity_vocab: dict[str, dict]) -> Catalog:
    """items.parquet (DataFrame) + amenity_vocab.json (dict) → Catalog có cột bỏ dấu để tìm nhanh."""
    raw = amenity_vocab
    vocab = {int(i): e for i, e in raw.items()}
    items = items.set_index("product_id", drop=False)
    items.index.name = None
    for c in ("brand", "province", "city", "room_vocab"):
        if c not in items.columns:
            items[c] = None
    items["_fold_name"] = _folded(items["name"] + " " + items["brand"].fillna(""))
    items["_fold_place"] = _folded(items["destination"].fillna("") + " | " + items["province"].fillna("") + " | "
                                   + items["city"].fillna(""))
    items["amenity_ids"] = items["amenity_ids"].map(lambda xs: [int(x) for x in (xs if xs is not None else [])])
    return Catalog(items=items, vocab=vocab, key_to_id=F.amenity_key_index(raw))


# ------------------------------------------------------------------ dashboard
def destination_table(cat: Catalog) -> pd.DataFrame:
    """Mỗi điểm đến: số search unit theo variant + tổng, sắp tổng giảm dần."""
    t = pd.crosstab(cat.items["destination"].fillna("—"), cat.items["variant"])
    for v in VARIANTS:
        if v not in t.columns:
            t[v] = 0
    t = t[list(VARIANTS)]
    t["tổng"] = t.sum(axis=1)
    t = t.sort_values(["tổng", "hotel_property"], ascending=False)
    t.index.name = "điểm đến"
    return t.reset_index()


def amenity_coverage(cat: Catalog, destination: str | None = None, variant: str = "hotel_property") -> pd.DataFrame:
    """Tỷ lệ sản phẩm (variant, tại destination nếu có) ghi nhận từng tiện ích — dùng chọn tiện ích cho câu hỏi
    (phủ định: nên 40–70% KHÔNG có; off-taxonomy: 15–40% có; tiện ích phủ > 80% thì câu hỏi không lọc được gì)."""
    df = cat.items[cat.items["variant"] == variant]
    if destination:
        df = df[df["destination"] == destination]
    n = len(df)
    counts: dict[int, int] = {}
    for ids in df["amenity_ids"]:
        for i in set(ids):
            counts[i] = counts.get(i, 0) + 1
    rows = [{"khoá": cat.vocab.get(i, {}).get("key", str(i)), "tiện ích": cat.amenity_label(i),
             "nguồn": cat.vocab.get(i, {}).get("source", ""), "số sản phẩm có": c, "tỷ lệ có": c / n if n else 0.0}
            for i, c in counts.items()]
    out = pd.DataFrame(rows, columns=["khoá", "tiện ích", "nguồn", "số sản phẩm có", "tỷ lệ có"])
    return out.sort_values(["tỷ lệ có", "khoá"], ascending=[False, True]).reset_index(drop=True)


# ------------------------------------------------------------------ tìm sản phẩm
def criteria_filter(*, destinations: Iterable[str] = (), variants: Iterable[str] = (), star_min: float | None = None,
                    price_max: float | None = None, amenities_all: Iterable[str] = (),
                    amenities_none: Iterable[str] = ()) -> dict | None:
    """Tiêu chí của ô tìm kiếm → filter AST (khoá amenity) đúng định dạng drafts / spec Part 4."""
    nodes: list[dict] = []
    dests, vars_ = sorted(set(destinations)), sorted(set(variants))
    if len(dests) == 1:
        nodes.append({"eq": ["destination", dests[0]]})
    elif dests:
        nodes.append({"in": ["destination", dests]})
    if len(vars_) == 1:
        nodes.append({"eq": ["variant", vars_[0]]})
    elif vars_:
        nodes.append({"in": ["variant", vars_]})
    if star_min is not None:
        nodes.append({"gte": ["star_rating", float(star_min) if not float(star_min).is_integer() else int(star_min)]})
    if price_max is not None:
        nodes.append({"lte": ["unit_price_min", int(price_max)]})
    if amenities_all:
        nodes.append({"contains_all": ["amenity_ids", sorted(set(amenities_all))]})
    if amenities_none:
        nodes.append({"not": {"contains_any": ["amenity_ids", sorted(set(amenities_none))]}})
    return None if not nodes else nodes[0] if len(nodes) == 1 else {"and": nodes}


def filter_mask(cat: Catalog, ast: dict | None) -> np.ndarray:
    """AST (khoá hoặc id amenity) → mask trên items; filter sai → FilterError."""
    if ast is None:
        return np.ones(len(cat.items), dtype=bool)
    node = F.parse(ast)
    return F.mask(F.resolve(node, cat.key_to_id), cat.items)


def search(cat: Catalog, *, text: str = "", filter_ast: dict | None = None, limit: int = 200) -> pd.DataFrame:
    """Sản phẩm khớp filter và chứa mọi từ của `text` (bỏ dấu) trong tên / brand / điểm đến — bảng cho người soạn /
    gán nhãn."""
    m = filter_mask(cat, filter_ast)
    df = cat.items[m]
    words = fold(text or "").split()
    if words:
        hay = " " + df["_fold_name"] + " " + df["_fold_place"] + " "
        keep = np.ones(len(df), dtype=bool)
        for w in words:
            keep &= hay.str.contains(w, regex=False).to_numpy()
        df = df[keep]
        name_hits = sum(df["_fold_name"].str.contains(w, regex=False).astype(int) for w in words)
    else:
        name_hits = pd.Series(0, index=df.index)
    rank = df["variant"].map({v: i for i, v in enumerate(VARIANTS)}).fillna(len(VARIANTS))
    df = df.assign(_hits=-name_hits, _rank=rank).sort_values(["_hits", "_rank", "destination", "name"])
    return _present(cat, df.head(limit))


def _present(cat: Catalog, df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "product_id": df["product_id"], "tên": df["name"], "loại": df["variant"], "điểm đến": df["destination"],
        "sao": df["star_rating"].astype(float).round(1), "giá từ": df["unit_price_min"],
        "số phòng": df["n_children"].astype(int),
        "tiện ích": df["amenity_ids"].map(lambda ids: ", ".join(cat.amenity_label(i) for i in ids[:12])
                                           + (f" … (+{len(ids) - 12})" if len(ids) > 12 else "")),
        "hạng phòng": df["room_vocab"].map(lambda xs: "; ".join(list(xs if xs is not None else [])[:8])),
    }).reset_index(drop=True)


def describe(cat: Catalog, ids: Iterable[str]) -> pd.DataFrame:
    """Bảng thông tin các product_id (bỏ id không có trong catalog) — hiện source_refs cho người soạn / soát."""
    known = [i for i in dict.fromkeys(ids) if i in cat.items.index]
    return _present(cat, cat.items.loc[known])


def short_label(cat: Catalog, pid: str) -> str:
    """Nhãn một dòng cho dropdown: tên · loại · điểm đến · sao · giá."""
    if pid not in cat.items.index:
        return f"{pid} (không có trong catalog)"
    r = cat.items.loc[pid]
    star = f" · {float(r['star_rating']):g}★" if pd.notna(r["star_rating"]) else ""
    price = f" · từ {int(r['unit_price_min']):,}đ".replace(",", ".") if pd.notna(r["unit_price_min"]) else ""
    return f"{r['name']} · {r['variant']} · {r['destination']}{star}{price}"


def context_of(cat: Catalog, ids: Iterable[str]) -> tuple[str | None, str | None]:
    """(điểm đến, loại) phổ biến nhất của các product_id — mặc định cho ô tìm source_refs khi viết câu thay thế."""
    df = cat.items.loc[[i for i in ids if i in cat.items.index]]
    if df.empty:
        return None, None
    return df["destination"].mode().iloc[0], df["variant"].mode().iloc[0]


def place_hits(cat: Catalog, place: str) -> pd.DataFrame:
    """Search unit nhắc tới `place` (bỏ dấu, nguyên cụm) ở tên, điểm đến, tỉnh hoặc thành phố — câu out_of_catalog chỉ
    hợp lệ khi bảng này rỗng (bài học c0571 "Ha Giang Loop Office", c0581 Côn Đảo thuộc "Bà Rịa - Vũng Tàu")."""
    q = fold(place or "")
    if not q:
        return cat.items.iloc[0:0][["product_id", "name", "variant", "destination"]]
    pat = f" {q} "
    hit = (" " + cat.items["_fold_name"] + " ").str.contains(pat, regex=False) | \
          (" " + cat.items["_fold_place"] + " ").str.contains(pat, regex=False)
    return cat.items[hit][["product_id", "name", "variant", "destination"]].reset_index(drop=True)


def known_refs(cat: Catalog, ids: Iterable[str]) -> tuple[list[str], list[str]]:
    """(id là search unit trong catalog, id lạ)."""
    ok, bad = [], []
    for i in ids:
        (ok if i in cat.items.index else bad).append(i)
    return ok, bad
