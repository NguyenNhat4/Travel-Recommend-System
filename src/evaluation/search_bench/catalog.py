"""Part 1 — products.jsonl → data_dir(dataset)/{items.parquet, amenity_vocab.json, amenity_fuzzy_hits.csv, stats.json, vocab.json}.

Search unit = variant ∈ catalog.search_unit_variants; variant suy như view `catalog.product_meta`
(`vector_bench.dataset.catalog.variant_of`). Phòng / chuyến bay không thành item mà góp vào cha qua
`attributes.parentProductId`: từ vựng hạng phòng, hãng bay, amenity (theo amenity_scope), giá min.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import structlog

from evaluation.vector_bench.dataset.catalog import read_jsonl, variant_of
from evaluation.vector_bench.lexical import fold
from evaluation.vector_bench.results import dump_json, sha256_file

from . import amenities, paths
from .config import SBenchConfig

log = structlog.get_logger("sbench.catalog")

CHILD_VARIANTS = ("hotel_room", "flight")

ITEM_SCHEMA = pa.schema([
    ("product_id", pa.string()), ("taxonomy", pa.string()), ("variant", pa.string()), ("name", pa.string()),
    ("brand", pa.string()), ("destination", pa.string()), ("province", pa.string()), ("city", pa.string()),
    ("property_type", pa.string()), ("star_rating", pa.float32()), ("audience", pa.list_(pa.string())),
    ("family_friendly", pa.bool_()), ("ocean_view", pa.bool_()), ("ticketed", pa.bool_()), ("nights", pa.int16()),
    ("amenities_raw", pa.list_(pa.string())), ("amenity_ids", pa.list_(pa.int16())),
    ("room_vocab", pa.list_(pa.string())), ("airlines", pa.list_(pa.string())),
    ("description", pa.string()), ("description_is_derived", pa.bool_()), ("description_source", pa.string()),
    ("unit_price_min", pa.float64()), ("review_score", pa.float32()), ("available", pa.bool_()),
    ("lat", pa.float64()), ("lon", pa.float64()), ("parent_product_id", pa.string()), ("n_children", pa.int16()),
])


class CatalogError(RuntimeError):
    pass


# ------------------------------------------------------------------ nguồn
def _records_sha256(records: list[dict]) -> str:
    h = hashlib.sha256()
    for r in records:
        h.update(json.dumps(r, ensure_ascii=False, sort_keys=True).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def _jsonl_path(cfg: SBenchConfig) -> Path:
    p = paths.resolve_repo_path(cfg.catalog.products_path)
    if p.exists():
        return p
    snap = paths.resolve_repo_path(cfg.catalog.snapshot_path)
    if not snap.exists():
        raise CatalogError(f"không thấy {p} lẫn snapshot {snap} — sửa catalog.products_path / snapshot_path")
    from data_collection.seed.snapshot import materialize_snapshot   # kiểm checksum manifest, bung vào data/ (gitignore)
    out = materialize_snapshot(snap)
    log.info("đã bung snapshot", snapshot=str(snap), to=str(out))
    if out.resolve() != p.resolve():
        log.warning("snapshot bung ra chỗ khác catalog.products_path — dùng bản vừa bung", path=str(out))
    return out


def load_records(cfg: SBenchConfig, source: str) -> tuple[list[dict], dict[str, Any]]:
    paths.check_dataset(source)
    if source == "fake":
        from evaluation.vector_bench.dataset.fake import generate_products
        records = generate_products(cfg.catalog.fake_n, cfg.run.seed)
        return records, {"source": "fake", "fake_n": cfg.catalog.fake_n, "seed": cfg.run.seed,
                         "records_sha256": _records_sha256(records)}
    p = _jsonl_path(cfg) if source == "jsonl" else paths.resolve_repo_path(cfg.catalog.sample_path)
    if not p.exists():
        raise CatalogError(f"không thấy {p}")
    records = read_jsonl(p)
    return records, {"source": source, "path": str(p.relative_to(paths.repo_root()) if p.is_relative_to(paths.repo_root()) else p),
                     "file_sha256": sha256_file(p), "records_sha256": _records_sha256(records)}


def reload_records(cfg: SBenchConfig, dataset: str) -> list[dict]:
    """Đọc lại đúng nguồn đã dựng items của dataset (kiểm sha) — cho vocab và text builder."""
    stats = read_stats(dataset)
    records, info = load_records(cfg, stats["source"])
    if info["records_sha256"] != stats["records_sha256"]:
        raise CatalogError(f"nguồn của dataset {dataset} đã đổi kể từ `catalog build` — chạy lại `sb catalog build`")
    return records


def read_stats(dataset: str) -> dict:
    p = paths.data_dir(dataset, create=False) / paths.STATS
    if not p.exists():
        raise CatalogError(f"chưa có {p} — chạy `sb --dataset {dataset} catalog build` trước")
    return json.loads(p.read_text(encoding="utf-8"))


def read_items(dataset: str) -> pd.DataFrame:
    p = paths.data_dir(dataset, create=False) / paths.ITEMS
    if not p.exists():
        raise CatalogError(f"chưa có {p} — chạy `sb --dataset {dataset} catalog build` trước")
    return pq.read_table(p).to_pandas()


def group_children(records: list[dict], unit_variants: list[str]) -> tuple[list[dict], dict[str, list[dict]], dict[str, str], int]:
    by_id = {r["productId"]: r for r in records}
    variants = {r["productId"]: variant_of(r) for r in records}
    children: dict[str, list[dict]] = {}
    orphans = 0
    for r in records:
        if variants[r["productId"]] in CHILD_VARIANTS:
            parent = (r.get("attributes") or {}).get("parentProductId")
            if parent in by_id and variants[parent] in unit_variants:
                children.setdefault(parent, []).append(r)
            else:
                orphans += 1
    units = [r for r in records if variants[r["productId"]] in unit_variants]
    return units, children, variants, orphans


# ------------------------------------------------------------------ cột
def _num(v: Any) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(f) else f


def _bool(v: Any) -> bool | None:
    return v if isinstance(v, bool) else None


def _str(v: Any) -> str | None:
    return v.strip() if isinstance(v, str) and v.strip() else None


def _uniq(xs: list[str]) -> list[str]:
    seen, out = set(), []
    for x in xs:
        if isinstance(x, str) and x.strip() and x.strip() not in seen:
            seen.add(x.strip())
            out.append(x.strip())
    return out


def _review_score(a: dict) -> float | None:
    """Thang 10: reviewScore/reviewScoreScale (khách sạn), fallback rating/ratingScale (điểm tham quan)."""
    for score_k, scale_k in (("reviewScore", "reviewScoreScale"), ("rating", "ratingScale")):
        s = _num(a.get(score_k))
        if s is not None:
            scale = _num(a.get(scale_k)) or 10.0
            return round(s * 10.0 / scale, 3)
    return None


def _room_name(child: dict) -> str | None:
    a = child.get("attributes") or {}
    return _str(a.get("roomName")) or _str((child.get("name") or "").split(" - ")[-1])


def unit_row(r: dict, variant: str, kids: list[dict], amenities_raw: list[str]) -> tuple[dict, bool]:
    a = r.get("attributes") or {}
    own = _num(r.get("unitPrice"))
    prices = [p for p in [own, *(_num(k.get("unitPrice")) for k in kids)] if p is not None]
    ticketed = _bool(a.get("ticketed"))
    inferred = False
    if ticketed is None and variant == "attraction" and own is None:
        ticketed, inferred = False, True     # schema.md §2: unitPrice null chỉ còn ở điểm công cộng không bán vé
    airlines: list[str] = []
    if variant == "flight_route":
        airlines = sorted(set(_uniq([(k.get("attributes") or {}).get("airline") for k in kids] + list(a.get("airlines") or []))))
    nights = _num(a.get("nights"))
    row = {
        "product_id": r["productId"], "taxonomy": r["taxonomy"], "variant": variant, "name": r["name"],
        "brand": _str(a.get("brand")), "destination": r.get("destination") or "UNKNOWN",
        "province": _str(a.get("province")), "city": _str(a.get("city")), "property_type": _str(a.get("propertyType")),
        "star_rating": _num(a.get("starRating")), "audience": _uniq(list(a.get("audience") or [])),
        "family_friendly": _bool(a.get("familyFriendly")), "ocean_view": _bool(a.get("oceanView")),
        "ticketed": ticketed, "nights": int(nights) if nights is not None else None,
        "amenities_raw": amenities_raw, "amenity_ids": [],
        "room_vocab": sorted(set(filter(None, (_room_name(k) for k in kids)))) if variant == "hotel_property" else [],
        "airlines": airlines,
        "description": r.get("description") or "", "description_is_derived": a.get("descriptionSource") is not None,
        "description_source": _str(a.get("descriptionSource")),
        "unit_price_min": min(prices) if prices else None, "review_score": _review_score(a),
        "available": bool(r.get("available", True)),
        "lat": _num(a.get("latitude")), "lon": _num(a.get("longitude")),
        "parent_product_id": _str(a.get("parentProductId")), "n_children": len(kids),
    }
    return row, inferred


def build_items(records: list[dict], cfg: SBenchConfig) -> tuple[pd.DataFrame, amenities.AmenityVocab,
                                                                 amenities.TrigramAmenityMatcher, dict]:
    cc = cfg.catalog
    units, children, variants, orphans = group_children(records, cc.search_unit_variants)
    if not units:
        raise CatalogError("không có search unit nào — kiểm catalog.search_unit_variants")

    unit_raws: list[list[str]] = []
    for r in units:
        raws = list((r.get("attributes") or {}).get("amenities") or [])
        if variants[r["productId"]] == "hotel_property" and cc.amenity_scope == "property_plus_rooms":
            for k in children.get(r["productId"], []):
                raws += list((k.get("attributes") or {}).get("amenities") or [])
        unit_raws.append(_uniq(raws))
    matcher = amenities.TrigramAmenityMatcher(amenities.load_seed(paths.resolve_repo_path(cc.amenity_seed_path)),
                                              cc.amenity_fuzzy_min)
    vocab, ids_per_unit = amenities.build_vocab(unit_raws, matcher, cc.amenity_min_freq)

    rows, n_inferred = [], 0
    for r, raws, ids in zip(units, unit_raws, ids_per_unit):
        row, inferred = unit_row(r, variants[r["productId"]], children.get(r["productId"], []), raws)
        row["amenity_ids"] = ids
        rows.append(row)
        n_inferred += inferred
    df = pd.DataFrame(rows, columns=[f.name for f in ITEM_SCHEMA])

    problems = []
    if df["product_id"].duplicated().any():
        problems.append(f"product_id trùng: {int(df['product_id'].duplicated().sum())}")
    if (df["name"].str.strip() == "").any():
        problems.append("name rỗng")
    if df["parent_product_id"].notna().any():
        problems.append(f"search unit có parentProductId: {int(df['parent_product_id'].notna().sum())}")
    if problems:
        raise CatalogError("catalog không hợp lệ: " + "; ".join(problems))

    n_children = df["n_children"]
    hp = df[df["variant"] == "hotel_property"]
    stats = {
        "n_records": len(records),
        "records_by_variant": dict(Counter(variants.values()).most_common()),
        "n_search_units": len(df),
        "search_units_by_variant": dict(Counter(df["variant"]).most_common()),
        "search_units_by_taxonomy": dict(Counter(df["taxonomy"]).most_common()),
        "orphan_children": orphans,
        "n_destinations": int(df["destination"].nunique()),
        "amenity": {
            "scope": cc.amenity_scope,
            "coverage_all": round(float((df["amenity_ids"].str.len() > 0).mean()), 4),
            "coverage_hotel_property": round(float((hp["amenity_ids"].str.len() > 0).mean()), 4) if len(hp) else None,
            "n_ids_seed": sum(1 for e in vocab.entries.values() if e["source"] == "seed"),
            "n_ids_raw": sum(1 for e in vocab.entries.values() if e["source"] == "raw"),
            "n_fuzzy_hits": len(matcher.fuzzy_hits()),
            "dropped": {"distinct": vocab.dropped_distinct, "occurrences": vocab.dropped_occurrences},
        },
        "description_derived_rate": round(float(df["description_is_derived"].mean()), 4),
        "n_children": {"max": int(n_children.max()), "mean": round(float(n_children.mean()), 3),
                       "buckets": {"0": int((n_children == 0).sum()), "1-2": int(n_children.between(1, 2).sum()),
                                   "3-5": int(n_children.between(3, 5).sum()), "6-10": int(n_children.between(6, 10).sum()),
                                   ">10": int((n_children > 10).sum())}},
        "null_rate": {c: round(float(df[c].isna().mean()), 4) for c in ("unit_price_min", "star_rating", "lat", "review_score")},
        "ticketed_inferred_false": n_inferred,
    }
    return df, vocab, matcher, stats


def write_items(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pandas(df, schema=ITEM_SCHEMA, preserve_index=False), path)


def build_catalog(cfg: SBenchConfig, source: str, *, allow_id_drift: bool = False) -> dict:
    """Dựng items của dataset `source` (jsonl | sample | fake). Ghi đè thư mục data của đúng dataset đó."""
    records, src_info = load_records(cfg, source)
    df, vocab, matcher, stats = build_items(records, cfg)
    out = paths.data_dir(source)

    vocab_json = vocab.to_json()
    old_vocab_path = out / paths.AMENITY_VOCAB
    if old_vocab_path.exists():
        changed, removed = amenities.id_drift(json.loads(old_vocab_path.read_text(encoding="utf-8")), vocab_json)
        if changed and not allow_id_drift:
            raise CatalogError(f"amenity id đổi cho {len(changed)} khoá (ví dụ {changed[:5]}) — filter/gold dùng id sẽ sai. "
                               "Chạy lại với --allow-id-drift nếu chủ động chấp nhận.")
        stats["amenity"]["id_drift"] = {"changed": changed, "removed": removed, "allowed": bool(changed)}

    write_items(df, out / paths.ITEMS)
    dump_json(old_vocab_path, vocab_json)
    matcher.write_hits(out / paths.AMENITY_FUZZY_HITS)
    stats = {"dataset": source, **src_info, **stats, "items_sha256": sha256_file(out / paths.ITEMS)}
    dump_json(out / paths.STATS, stats)
    log.info("catalog xong", dataset=source, out=str(out), search_units=stats["n_search_units"])
    return stats


# ------------------------------------------------------------------ vocab
def _entries(values: Counter) -> list[dict]:
    return [{"value": v, "folded": fold(v), "n": n} for v, n in sorted(values.items(), key=lambda kv: (-kv[1], kv[0]))]


def build_vocab_file(cfg: SBenchConfig, dataset: str) -> dict:
    """vocab.json cho Part 5 (draft gold), 6 (gazetteer, SymSpell), 7 (synthetic) + filter_fields cho filter JSON."""
    df = read_items(dataset)
    stats = read_stats(dataset)
    records = reload_records(cfg, dataset)
    amen = json.loads((paths.data_dir(dataset) / paths.AMENITY_VOCAB).read_text(encoding="utf-8"))

    iata: dict[str, str | None] = {}
    for r in records:
        a = r.get("attributes") or {}
        for code_k, city_k in (("originAirport", "originCity"), ("destinationAirport", "destinationCity")):
            code = _str(a.get(code_k))
            if code:
                iata.setdefault(code, _str(a.get(city_k)))
        for list_k, city_k in (("originAirports", "originCity"), ("destinationAirports", "destinationCity")):
            for code in a.get(list_k) or []:
                if isinstance(code, str) and code.strip():
                    iata.setdefault(code.strip(), _str(a.get(city_k)))

    stars = df["star_rating"].dropna()
    prices = df["unit_price_min"].dropna()
    vocab = {
        "generated_from": {"dataset": dataset, "items_sha256": stats["items_sha256"], "records_sha256": stats["records_sha256"]},
        "destinations": _entries(Counter(df["destination"])),
        "provinces": _entries(Counter(df["province"].dropna())),
        "brands": _entries(Counter(df["brand"].dropna())),
        "products": [{"product_id": r.product_id, "name": r.name, "folded": fold(r.name), "variant": r.variant,
                      "destination": r.destination, "brand": r.brand} for r in df.itertuples()],
        "amenities": [{"id": int(i), "key": e["key"], "label": e["label"], "folded": fold(e["label"]),
                       "source": e["source"], "freq": e["freq"]} for i, e in amen.items()],
        "room_classes": _entries(Counter(x for xs in df["room_vocab"] for x in xs)),
        "airlines": _entries(Counter(x for xs in df["airlines"] for x in xs)),
        "iata": [{"code": c, "city": city, "city_folded": fold(city) if city else None} for c, city in sorted(iata.items())],
        "filter_fields": {
            "taxonomy": sorted(df["taxonomy"].unique().tolist()),
            "variant": sorted(df["variant"].unique().tolist()),
            "destination": sorted(df["destination"].unique().tolist()),
            "province": sorted(df["province"].dropna().unique().tolist()),
            "star_rating": {"min": float(stars.min()), "max": float(stars.max()),
                            "values": sorted(float(x) for x in stars.unique())} if len(stars) else None,
            "unit_price_min": {"min": float(prices.min()), "p50": float(prices.median()), "max": float(prices.max())}
            if len(prices) else None,
            "bool": ["available", "family_friendly", "ocean_view", "ticketed"],
            "amenity_keys": sorted(e["key"] for e in amen.values()),
            "note": "filter JSON trong gold ghi khoá amenity (vd kids_club, raw:<slug>), không ghi id",
        },
    }
    dump_json(paths.data_dir(dataset) / paths.VOCAB, vocab)
    return vocab
