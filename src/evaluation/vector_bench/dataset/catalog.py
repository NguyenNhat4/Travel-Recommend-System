"""Part 1 — catalog → bench_out/data/catalog/{items.parquet, amenity_vocab.json, stats.json}.

Search unit = variant ∉ {hotel_room, flight}. Phòng/chuyến bay góp giá (min), amenity (hợp) và tên hạng phòng vào dòng cha
qua attributes.parentProductId (spec P1.2). variant suy giống view catalog.product_meta.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import logging
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .. import paths
from ..config import VBenchConfig
from ..results import dump_json, sha256_file
from . import amenities, textbuild

log = logging.getLogger("vbench.catalog")

NON_UNIT = ("hotel_room", "flight")

ITEM_SCHEMA = pa.schema([
    ("row", pa.int32()), ("id", pa.string()), ("variant", pa.string()), ("taxonomy", pa.string()),
    ("destination", pa.string()), ("province", pa.string()), ("name", pa.string()), ("available", pa.bool_()),
    ("amenity_ids", pa.list_(pa.int16())), ("unit_price", pa.float64()), ("star_rating", pa.float32()),
    ("lat", pa.float64()), ("lon", pa.float64()), ("embed_text", pa.string()), ("lex_text", pa.string()),
    ("text_hash", pa.string()), ("description_derived", pa.bool_()), ("n_children", pa.int16()),
    ("property_type", pa.string()),   # phụ trợ: placeholder {loai} của query template (P3.3)
])


def variant_of(rec: dict) -> str:
    a = rec.get("attributes") or {}
    t, lv = rec["taxonomy"], a.get("level")
    if t == "hotel":
        return "hotel_" + (lv or "property")
    if t == "flight":
        return "flight_route" if lv == "route" else "flight"
    return t


def read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def backend_text_builder() -> tuple[Callable[[dict, list[dict], int], str] | None, str]:
    """Text builder của Search (spec §1.1): src/backend/app/domain/catalog/text_builder.py::build_text.

    Domain layer thuần Python (không FastAPI/DB) nên import được trong venv riêng của bench.
    """
    src = str(paths.src_dir())
    if src not in sys.path:
        sys.path.insert(0, src)
    try:
        mod = importlib.import_module("backend.app.domain.catalog")
        Product, build_text = mod.Product, mod.build_text
    except Exception as e:  # noqa: BLE001
        log.warning("không import được text builder của backend (%s) → dùng fallback", e)
        return None, "fallback"

    def build(rec: dict, children: list[dict], max_desc_words: int) -> str:
        return build_text(Product.from_cdp(rec), [Product.from_cdp(c) for c in children], max_desc_words=max_desc_words)
    return build, "backend:src/backend/app/domain/catalog/text_builder.py::build_text"


def _num(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(f) else f


def build_items(records: list[dict], cfg: VBenchConfig, *, use_backend_builder: bool) -> tuple[pd.DataFrame, amenities.AmenityVocab, dict]:
    cc = cfg.dataset.catalog
    by_id = {r["productId"]: r for r in records}
    variants = {r["productId"]: variant_of(r) for r in records}
    children: dict[str, list[dict]] = {}
    orphans = 0
    for r in records:
        if variants[r["productId"]] in NON_UNIT:
            parent = (r.get("attributes") or {}).get("parentProductId")
            if parent and parent in by_id and variants[parent] not in NON_UNIT:
                children.setdefault(parent, []).append(r)
            else:
                orphans += 1
    units = [r for r in records if variants[r["productId"]] not in NON_UNIT]

    # amenity: property nhận hợp amenity của nó và phòng con (amenity_scope)
    unit_raws: list[list[str]] = []
    for r in units:
        raws = list((r.get("attributes") or {}).get("amenities") or [])
        if variants[r["productId"]] == "hotel_property" and cc.amenity_scope == "property_plus_rooms":
            for ch in children.get(r["productId"], []):
                raws += list((ch.get("attributes") or {}).get("amenities") or [])
        unit_raws.append(raws)
    matcher = amenities.AmenityMatcher(amenities.load_seed())
    vocab, ids_per_unit = amenities.build_vocab(unit_raws, matcher, cc.amenity_min_freq)

    builder, builder_name = (backend_text_builder() if use_backend_builder else (None, "fallback"))

    rows: list[dict] = []
    for i, r in enumerate(units):
        pid = r["productId"]
        v = variants[pid]
        a = r.get("attributes") or {}
        kids = children.get(pid, [])
        own = _num(r.get("unitPrice"))
        if v in ("hotel_property", "flight_route"):
            kp = [p for p in (_num(k.get("unitPrice")) for k in kids) if p is not None]
            price = min(kp) if kp else own
        else:
            price = own
        ids = ids_per_unit[i]
        if builder is not None:
            text = builder(r, kids, cc.max_description_words)
        else:
            labels = [vocab.entries[x]["label"] for x in ids]
            text = textbuild.build_text(r, kids, v, labels, max_amenities=cc.max_amenities_in_text,
                                        max_rooms=cc.max_room_names_in_text, max_desc_words=cc.max_description_words)
        lat, lon = _num(a.get("latitude")), _num(a.get("longitude"))
        rows.append({
            "row": i, "id": pid, "variant": v, "taxonomy": r["taxonomy"], "destination": r["destination"],
            "province": a.get("province") or "", "name": r["name"], "available": bool(r.get("available")),
            "amenity_ids": ids, "unit_price": price, "star_rating": _num(a.get("starRating")),
            "lat": lat, "lon": lon, "embed_text": text, "lex_text": text,
            "text_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "description_derived": bool(a.get("descriptionSource")), "n_children": len(kids),
            "property_type": a.get("propertyType"),
        })
    df = pd.DataFrame(rows)

    # kiểm tra bắt buộc (Part 1 Done khi)
    problems = []
    if df["id"].duplicated().any():
        problems.append(f"id trùng: {int(df['id'].duplicated().sum())}")
    if (df["embed_text"].str.strip() == "").any():
        problems.append(f"embed_text rỗng: {int((df['embed_text'].str.strip() == '').sum())}")
    if df["lat"].isna().any() or df["lon"].isna().any():
        problems.append(f"thiếu lat/lon: {int(df['lat'].isna().sum() + df['lon'].isna().sum())}")
    if problems:
        raise ValueError("catalog không hợp lệ: " + "; ".join(problems))

    words = df["embed_text"].str.split().str.len()
    hp = df[df["variant"] == "hotel_property"]
    top = sorted(vocab.entries.items(), key=lambda kv: (-kv[1]["freq"], kv[0]))[:30]
    stats = {
        "n_products": len(records),
        "products_by_variant": dict(Counter(variants.values()).most_common()),
        "n_search_units": len(df),
        "search_unit_ratio": round(len(df) / max(len(records), 1), 4),
        "search_units_by_variant": dict(Counter(df["variant"]).most_common()),
        "orphan_children": orphans,
        "text_builder": builder_name,
        "amenity": {
            "scope": cc.amenity_scope,
            "hotel_property_coverage": round(float((hp["amenity_ids"].str.len() > 0).mean()) if len(hp) else 0.0, 4),
            "n_ids_seed": sum(1 for e in vocab.entries.values() if e["source"] == "seed"),
            "n_ids_raw": sum(1 for e in vocab.entries.values() if e["source"] == "raw"),
            "dropped": {"distinct": vocab.dropped_distinct, "occurrences": vocab.dropped_occurrences},
            "top30": [{"id": i, **e} for i, e in top],
        },
        "n_destinations": int(df["destination"].nunique()),
        "null_rate": {"unit_price": round(float(df["unit_price"].isna().mean()), 4),
                      "star_rating": round(float(df["star_rating"].isna().mean()), 4)},
        "embed_text_words": {"p50": float(np.percentile(words, 50)), "p95": float(np.percentile(words, 95))},
        "description_derived_rate": round(float(df["description_derived"].mean()), 4),
        "available_rate": round(float(df["available"].mean()), 4),
    }
    return df, vocab, stats


def write_items(df: pd.DataFrame, path: Path) -> None:
    table = pa.Table.from_pandas(df[[f.name for f in ITEM_SCHEMA]], schema=ITEM_SCHEMA, preserve_index=False)
    pq.write_table(table, path)


def build_catalog(cfg: VBenchConfig, *, source: str | None = None, products: str | None = None, n: int | None = None) -> dict:
    cc = cfg.dataset.catalog
    source = source or cc.source
    out = paths.data_dir("catalog")
    src_info: dict[str, Any] = {"source": source}
    if source == "jsonl":
        p = paths.resolve_repo_path(products or cc.products_path)
        if not p.exists():
            raise FileNotFoundError(f"không thấy {p} — truyền --products hoặc sửa dataset.catalog.products_path")
        records = read_jsonl(p)
        src_info.update({"products_path": str(p), "products_sha256": sha256_file(p)})
        use_backend = True
    elif source == "fake":
        from .fake import generate_products
        nn = n or cc.fake_n
        records = generate_products(nn, cfg.run.seed)
        src_info.update({"fake_n": nn, "seed": cfg.run.seed})
        use_backend = False   # P1.5: văn bản fake sinh bằng template P1.4
    elif source == "db":
        raise NotImplementedError("--source db nằm ngoài fast-track (spec-fasttrack §4 Part 1); dùng --source jsonl")
    else:
        raise ValueError(f"source không hợp lệ: {source}")

    df, vocab, stats = build_items(records, cfg, use_backend_builder=use_backend)
    stats = {**src_info, **stats}
    write_items(df, out / paths.ITEMS)
    dump_json(out / paths.AMENITY_VOCAB, vocab.to_json())
    stats["items_sha256"] = sha256_file(out / paths.ITEMS)
    dump_json(out / paths.STATS, stats)
    _print_summary(stats, out)
    return stats


def _print_summary(stats: dict, out: Path) -> None:
    from rich.console import Console
    from rich.table import Table

    t = Table(title=f"catalog → {out}")
    t.add_column("mục")
    t.add_column("giá trị", overflow="fold")
    t.add_row("nguồn", str(stats["source"]))
    t.add_row("sản phẩm", f"{stats['n_products']} {stats['products_by_variant']}")
    t.add_row("[bold]search unit (số vector thật)[/]", f"[bold]{stats['n_search_units']}[/] (tỷ lệ {stats['search_unit_ratio']:.1%}) "
              f"{stats['search_units_by_variant']}")
    t.add_row("text builder", stats["text_builder"])
    am = stats["amenity"]
    t.add_row("amenity", f"coverage hotel_property {am['hotel_property_coverage']:.1%} · id seed {am['n_ids_seed']} · "
              f"id raw {am['n_ids_raw']} · raw bỏ {am['dropped']['distinct']} ({am['dropped']['occurrences']} lần)")
    t.add_row("top amenity", ", ".join(f"{x['label']}({x['freq']})" for x in am["top30"][:10]))
    t.add_row("điểm đến", str(stats["n_destinations"]))
    t.add_row("null giá / sao", f"{stats['null_rate']['unit_price']:.1%} / {stats['null_rate']['star_rating']:.1%}")
    t.add_row("số từ embed_text p50/p95", f"{stats['embed_text_words']['p50']:.0f} / {stats['embed_text_words']['p95']:.0f}")
    t.add_row("description_derived", f"{stats['description_derived_rate']:.1%}")
    Console().print(t)
