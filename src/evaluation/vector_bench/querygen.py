"""Part 3 — sinh filter theo bucket selectivity (P3.2) + text query (P3.3) → queries.jsonl, queries_stats.json.

Tất định: numpy default_rng(seed + offset). Cùng seed + cùng items.parquet → cùng sha256 của queries.jsonl.
Query ghép ĐỘC LẬP với filter (A1 đo recall của engine, không đo độ liên quan).
Scale lớn (fasttrack): `queries --scale 1m --reuse-query-vectors catalog` — filter sinh lại trên metadata 1M,
query vector = đúng query_vectors.npy của catalog (cùng không gian bge-m3), text chép từ catalog để tham chiếu.
"""
from __future__ import annotations

import json
import logging
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from . import paths
from .config import VBenchConfig
from .filters import Table, mask, validate
from .lexical import strip_accents
from .results import dump_json, sha256_file

log = logging.getLogger("vbench.querygen")

SEED_OFFSET_FILTERS = 3000
SEED_OFFSET_TEXT = 3001
SEED_OFFSET_ORDER = 3002
SEED_OFFSET_GATE = 9003
FILTER_TYPES = ("dest_tax", "all_amenity", "not_amenity", "range", "geo", "combo")


class FilterGen:
    """Sinh một filter của loại cho trước, tham số lấy từ dữ liệu (spec P3.2)."""

    def __init__(self, t: Table, cfg: VBenchConfig, rng: np.random.Generator):
        self.t, self.cfg, self.rng = t, cfg, rng
        q = cfg.queries
        self.dest_names = {i: v for v, i in t.cat_index["destination"].items()}
        self.tax_names = {i: v for v, i in t.cat_index["taxonomy"].items()}
        # tần suất amenity trong hotel_property
        hp = t.eq_mask("variant", "hotel_property")
        hp_rows = np.flatnonzero(hp)
        self.hotel_amen_ids, self.hotel_amen_p = self._amen_freq(hp_rows)
        self._group_rows: dict[tuple[int, int], np.ndarray] = {}
        self._group_amen: dict[tuple[int, int], tuple[np.ndarray, np.ndarray]] = {}
        self.radii = [float(r) for r in q.geo_radius_m]
        self.quantiles = [float(p) for p in q.price_quantiles]
        self.stars = [float(s) for s in q.star_min_values]

    def _amen_freq(self, rows: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if len(rows) == 0:
            return np.empty(0, dtype=np.int64), np.empty(0)
        sub = self.t.amen[rows]
        cnt = np.asarray(sub.sum(axis=0)).ravel()
        ids = np.flatnonzero(cnt)
        if len(ids) == 0:
            return ids, np.empty(0)
        p = cnt[ids].astype(np.float64)
        return ids, p / p.sum()

    def _random_row(self) -> int:
        return int(self.rng.integers(self.t.n))

    def _dest_tax_of(self, row: int) -> tuple[str, str]:
        return (self.dest_names[int(self.t.cat_codes["destination"][row])],
                self.tax_names[int(self.t.cat_codes["taxonomy"][row])])

    def _group(self, dest: str, tax: str) -> np.ndarray:
        key = (self.t.cat_index["destination"][dest], self.t.cat_index["taxonomy"][tax])
        rows = self._group_rows.get(key)
        if rows is None:
            rows = np.flatnonzero(self.t.eq_mask("destination", dest) & self.t.eq_mask("taxonomy", tax))
            self._group_rows[key] = rows
        return rows

    def _pick_ids(self, ids: np.ndarray, p: np.ndarray, k: int) -> list[int] | None:
        if len(ids) < k:
            return None
        return sorted(int(x) for x in self.rng.choice(ids, size=k, replace=False, p=p))

    def _price_q(self, rows: np.ndarray) -> float | None:
        prices = self.t.num["unit_price"][rows]
        prices = prices[~np.isnan(prices)]
        if len(prices) == 0:
            return None
        p = self.quantiles[int(self.rng.integers(len(self.quantiles)))]
        return float(np.quantile(prices, p))

    def gen(self, ftype: str) -> dict | None:
        t, rng = self.t, self.rng
        if ftype == "dest_tax":
            d, x = self._dest_tax_of(self._random_row())
            return {"and": [{"eq": ["destination", d]}, {"eq": ["taxonomy", x]}]}
        if ftype == "all_amenity":
            ids = self._pick_ids(self.hotel_amen_ids, self.hotel_amen_p, int(rng.integers(2, 4)))
            if ids is None:
                return None
            parts: list[dict] = [{"eq": ["taxonomy", "hotel"]}, {"all": ["amenity_ids", ids]}]
            if rng.random() < 0.5:
                hp_rows = np.flatnonzero(t.eq_mask("variant", "hotel_property"))
                d, _ = self._dest_tax_of(int(hp_rows[rng.integers(len(hp_rows))]))
                parts.insert(0, {"eq": ["destination", d]})
            return {"and": parts}
        if ftype == "not_amenity":
            hp_rows = np.flatnonzero(t.eq_mask("variant", "hotel_property"))
            if len(hp_rows) == 0:
                return None
            d, _ = self._dest_tax_of(int(hp_rows[rng.integers(len(hp_rows))]))
            ids = self._pick_ids(self.hotel_amen_ids, self.hotel_amen_p, 1)
            if ids is None:
                return None
            return {"and": [{"eq": ["destination", d]}, {"eq": ["taxonomy", "hotel"]},
                            {"not": {"any": ["amenity_ids", ids]}}]}
        if ftype == "range":
            d, x = self._dest_tax_of(self._random_row())
            if rng.random() < 0.5:
                q = self._price_q(self._group(d, x))
                if q is None:
                    return None
                cond = {"range": ["unit_price", {"lte": q}]}
            else:
                cond = {"range": ["star_rating", {"gte": self.stars[int(rng.integers(len(self.stars)))]}]}
            return {"and": [{"eq": ["destination", d]}, cond]}
        if ftype == "geo":
            row = self._random_row()
            g = {"geo": {"lat": float(t.lat[row]), "lon": float(t.lon[row]),
                         "radius_m": self.radii[int(rng.integers(len(self.radii)))]}}
            if rng.random() < 0.5:
                _, x = self._dest_tax_of(self._random_row())
                return {"and": [g, {"eq": ["taxonomy", x]}]}
            return g
        if ftype == "combo":
            d, x = self._dest_tax_of(self._random_row())
            rows = self._group(d, x)
            key = (t.cat_index["destination"][d], t.cat_index["taxonomy"][x])
            if key not in self._group_amen:
                self._group_amen[key] = self._amen_freq(rows)
            gids, gp = self._group_amen[key]
            ids = self._pick_ids(gids, gp, int(rng.integers(1, 3)))
            q = self._price_q(rows)
            if ids is None or q is None:
                return None
            return {"and": [{"eq": ["destination", d]}, {"eq": ["taxonomy", x]}, {"all": ["amenity_ids", ids]},
                            {"range": ["unit_price", {"lte": q}]}]}
        raise ValueError(f"loại filter lạ: {ftype}")

    def with_available(self, f: dict) -> dict:
        if self.rng.random() < self.cfg.queries.available_true_rate:
            if "and" in f:
                return {"and": [*f["and"], {"eq": ["available", True]}]}
            return {"and": [f, {"eq": ["available", True]}]}
        return f


def generate_filters(t: Table, cfg: VBenchConfig, seed: int) -> tuple[list[dict], dict]:
    q = cfg.queries
    rng = np.random.default_rng(seed + SEED_OFFSET_FILTERS)
    gen = FilterGen(t, cfg, rng)
    types = list(q.filter_type_weights)
    w = np.array([q.filter_type_weights[k] for k in types], dtype=np.float64)
    w = w / w.sum()
    out: list[dict] = []
    remaining: dict[str, int] = {}
    for b, bc in q.buckets.items():
        if bc.range is None:
            out += [{"filter": None, "filter_type": "none", "bucket": b, "selectivity": 1.0, "n_match": t.n}
                    for _ in range(bc.quota)]
        else:
            remaining[b] = bc.quota
    attempts = 0
    seen: set[str] = set()
    while any(v > 0 for v in remaining.values()) and attempts < q.max_attempts:
        attempts += 1
        ftype = types[int(rng.choice(len(types), p=w))]
        f = gen.gen(ftype)
        if f is None:
            continue
        f = gen.with_available(f)
        key = json.dumps(f, sort_keys=True, ensure_ascii=False)
        if key in seen:
            continue
        m = mask(f, t)
        nm = int(m.sum())
        s = nm / t.n
        for b, left in remaining.items():
            bc = q.buckets[b]
            lo, hi = bc.range
            if left > 0 and lo <= s <= hi and nm >= bc.min_matches:
                validate(f)
                out.append({"filter": f, "filter_type": ftype, "bucket": b, "selectivity": round(s, 8), "n_match": nm})
                remaining[b] -= 1
                seen.add(key)
                break
    shortfall = {b: v for b, v in remaining.items() if v > 0}
    info = {"attempts": attempts, "shortfall": shortfall}
    if shortfall:
        log.warning("bucket thiếu quota sau %d lần thử: %s", attempts, shortfall)
    return out, info


# ---------------------------------------------------------------- text query (catalog)
def _load_templates() -> dict:
    return yaml.safe_load((paths.CONFIG_DIR / "query_templates.yaml").read_text(encoding="utf-8"))


def _fill(tpl: str, item: dict, labels: dict[int, dict], rnd: random.Random, default_type: str) -> str | None:
    vals: dict[str, str] = {"destination": item["destination"], "name": item["name"],
                            "loai": item.get("property_type") or default_type}
    if "{sao}" in tpl:
        s = item.get("star_rating")
        if s is None or s != s:
            return None
        vals["sao"] = str(int(s)) if float(s).is_integer() else str(s)
    if "{amenity}" in tpl:
        raw_ids = item.get("amenity_ids")
        ids = [] if raw_ids is None else [int(x) for x in raw_ids]
        seed_ids = [i for i in ids if labels.get(int(i), {}).get("source") == "seed"]
        pool = seed_ids or ids
        if not pool:
            return None
        vals["amenity"] = labels[int(pool[rnd.randrange(len(pool))])]["label"].lower()
    try:
        return tpl.format(**vals)
    except KeyError:
        return None


def _abbreviate(text: str, abbr: dict[str, str]) -> str | None:
    out, changed = text, False
    for full, short in sorted(abbr.items(), key=lambda kv: -len(kv[0])):
        lower = out.lower()
        idx = lower.find(full.lower())
        while idx >= 0:
            out = out[:idx] + short + out[idx + len(full):]
            changed = True
            lower = out.lower()
            idx = lower.find(full.lower(), idx + len(short))
    return out if changed else None


def generate_texts(items: pd.DataFrame, labels: dict[int, dict], cfg: VBenchConfig, n: int, seed: int) -> list[dict]:
    tpls = _load_templates()
    rnd = random.Random(seed + SEED_OFFSET_TEXT)
    slices = list(cfg.queries.text_slices)
    sw = [cfg.queries.text_slices[s] for s in slices]
    recs = items.to_dict("records")
    out: list[dict] = []
    guard = 0
    while len(out) < n:
        guard += 1
        if guard > n * 200:
            raise RuntimeError("không sinh đủ text query — kiểm query_templates.yaml")
        item = recs[rnd.randrange(len(recs))]            # variant theo tỷ lệ search unit
        cands = list(tpls["templates"].get(item["variant"], []))
        rnd.shuffle(cands)
        text = None
        for tpl in cands:
            text = _fill(tpl, item, labels, rnd, tpls.get("default_property_type", "khách sạn"))
            if text:
                break
        if not text:
            continue
        sl = rnd.choices(slices, weights=sw, k=1)[0]
        if sl == "khong_dau":
            text = strip_accents(text)
        elif sl == "viet_tat":
            ab = _abbreviate(text, tpls.get("abbreviations") or {})
            if ab is None:
                sl = "normal"                      # không có gì để viết tắt → ghi normal
            else:
                text = ab
        out.append({"text": text, "slice": sl, "source_row": int(item["row"])})
    return out


# ---------------------------------------------------------------- main
def _write_jsonl(p: Path, rows: list[dict]) -> None:
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False, sort_keys=False) + "\n")


def read_queries(scale: str) -> list[dict]:
    p = paths.data_dir(scale, create=False) / paths.QUERIES
    with open(p, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def run_queries(cfg: VBenchConfig, *, scale: str, reuse_query_vectors: str | None = None) -> int:
    d = paths.data_dir(scale)
    t = Table.from_parquet(d / paths.ITEMS, with_ids=False)
    seed = cfg.run.seed
    filters, info = generate_filters(t, cfg, seed)
    order = np.random.default_rng(seed + SEED_OFFSET_ORDER).permutation(len(filters))
    filters = [filters[i] for i in order]
    prefix = "c" if scale == "catalog" else "q"

    text_src: list[dict] | None = None
    if reuse_query_vectors:
        src_dir = paths.data_dir(reuse_query_vectors, create=False)
        cat_q = read_queries(reuse_query_vectors)
        qv = np.load(src_dir / paths.QUERY_VECTORS)
        if qv.shape[0] != len(cat_q):
            raise ValueError(f"{reuse_query_vectors}: query_vectors {qv.shape[0]} ≠ queries {len(cat_q)}")
        n = min(len(cat_q), len(filters))
        text_src = [{"text": x["text"], "slice": x["slice"], "src_qid": x["qid"]} for x in cat_q[:n]]
        filters = filters[:n]
        if n == qv.shape[0]:
            shutil.copyfile(src_dir / paths.QUERY_VECTORS, d / paths.QUERY_VECTORS)
        else:
            np.save(d / paths.QUERY_VECTORS, qv[:n])
    elif scale == "catalog":
        items = pd.read_parquet(d / paths.ITEMS, columns=["row", "variant", "destination", "name", "property_type",
                                                          "star_rating", "amenity_ids"])
        labels = {int(k): v for k, v in json.loads((d / paths.AMENITY_VOCAB).read_text(encoding="utf-8")).items()}
        text_src = generate_texts(items, labels, cfg, len(filters), seed)

    rows = []
    for i, f in enumerate(filters):
        r: dict[str, Any] = {"qid": f"{prefix}{i + 1:04d}"}
        if text_src is not None:
            tx = text_src[i]
            r.update({"text": tx["text"], "slice": tx["slice"],
                      "source": "catalog" if reuse_query_vectors else "gen"})
            if reuse_query_vectors:
                r["src_qid"] = tx["src_qid"]
        else:
            r.update({"text": None, "slice": None, "source": "dataset"})
        r.update({"filter": f["filter"], "filter_type": f["filter_type"], "bucket": f["bucket"],
                  "selectivity": f["selectivity"], "n_match": f["n_match"], "gold_filter": None})
        rows.append(r)
    qp = d / paths.QUERIES
    _write_jsonl(qp, rows)

    by = defaultdict(Counter)
    srange: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        by[r["bucket"]][r["filter_type"]] += 1
        srange[r["bucket"]].append(r["selectivity"])
    stats = {
        "scale": scale, "n": len(rows), "n_items": t.n, "seed": seed,
        "by_bucket_type": {b: dict(c) for b, c in by.items()},
        "selectivity_range": {b: [min(v), max(v)] for b, v in srange.items()},
        "n_match_range": {b: [min(r["n_match"] for r in rows if r["bucket"] == b),
                              max(r["n_match"] for r in rows if r["bucket"] == b)] for b in srange},
        "by_slice": dict(Counter(r.get("slice") for r in rows)),
        "attempts": info["attempts"], "shortfall": info["shortfall"],
        "reuse_query_vectors": reuse_query_vectors,
        "queries_sha256": sha256_file(qp),
    }
    dump_json(d / paths.QUERIES_STATS, stats)
    print(f"queries.jsonl: {len(rows)} dòng · theo bucket {dict((b, sum(c.values())) for b, c in by.items())} · "
          f"shortfall {info['shortfall'] or 'không'} · {info['attempts']} lần thử · sha256 {stats['queries_sha256'][:12]}")
    for b in sorted(by):
        print(f"  {b}: {dict(by[b])} · S ∈ [{min(srange[b]):.5f}, {max(srange[b]):.5f}] · n_match ∈ {stats['n_match_range'][b]}")
    return 0


# ---------------------------------------------------------------- dùng cho gate G3
def generate_of_type(t: Table, cfg: VBenchConfig, ftype: str, n: int, exclude: set[str], seed_offset: int = SEED_OFFSET_GATE) -> list[dict]:
    """Sinh thêm n filter của một loại (không ràng buộc bucket, tập khớp khác rỗng) — G3 thiếu query thì dùng."""
    rng = np.random.default_rng(cfg.run.seed + seed_offset + FILTER_TYPES.index(ftype))
    gen = FilterGen(t, cfg, rng)
    out: list[dict] = []
    tries = 0
    while len(out) < n and tries < cfg.queries.max_attempts:
        tries += 1
        f = gen.gen(ftype)
        if f is None:
            continue
        f = gen.with_available(f)
        key = json.dumps(f, sort_keys=True, ensure_ascii=False)
        if key in exclude:
            continue
        nm = int(mask(f, t).sum())
        if nm == 0:
            continue
        exclude.add(key)
        out.append({"filter": f, "filter_type": ftype, "n_match": nm, "selectivity": round(nm / t.n, 8)})
    return out

