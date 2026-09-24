"""Part 2 — text builder: variant `<base>[+<modifier>…]` → embed_text cho từng search unit.

`T3+R` (= B0) là text builder production của backend (`src/backend/app/domain/catalog/text_builder.py::build_text`,
`catalog-text-v2`, spec §1.1, `text_builder: app`), gọi đúng như `PostgresCatalogReader` của production: truyền phòng /
chuyến bay con, `combo_items` và thuộc tính combo (`nights`…) mà job seed tính — ở đây tính trong bộ nhớ bằng
`catalog.combo_enrichment` (người dùng chốt 24/09). Base T0–T3 và modifier còn lại làm ngày 4 — gọi tới thì báo rõ, exit 2.
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import structlog

from evaluation.vector_bench.paths import src_dir
from evaluation.vector_bench.results import dump_json

from . import catalog, paths
from .config import SBenchConfig

log = structlog.get_logger("sbench.text")

BASES = ("T0", "T1", "T2", "T3")
MODIFIER_ORDER = ("R", "DF", "w30", "w60", "w150", "wfull", "KV", "NUM")
LENGTH_MODIFIERS = ("w30", "w60", "w150", "wfull")
DEFAULT_LENGTH = "w60"            # mặc định, không ghi trong tên variant
APP_VARIANTS = ("T3+R",)          # dựng bằng text builder backend

TEXT_SCHEMA = pa.schema([("product_id", pa.string()), ("text", pa.string()), ("text_hash", pa.string())])


class VariantError(ValueError):
    """Chuỗi variant sai cú pháp / tổ hợp bị cấm."""


class VariantNotImplemented(NotImplementedError):
    pass


class TextBuildError(RuntimeError):
    pass


def normalize_variant(variant: str) -> str:
    """`T3+DF+R` → `T3+R+DF`; bỏ `w60` (mặc định); từ chối base lạ, modifier lạ/trùng, hai modifier độ dài, T1 + wN."""
    parts = [p.strip() for p in variant.split("+")]
    if not parts or parts[0] not in BASES:
        raise VariantError(f"variant {variant!r}: base phải là một trong {', '.join(BASES)}")
    base, mods = parts[0], parts[1:]
    bad = [m for m in mods if m not in MODIFIER_ORDER]
    if bad:
        raise VariantError(f"variant {variant!r}: modifier lạ {bad} (có: {', '.join(MODIFIER_ORDER)})")
    if len(set(mods)) != len(mods):
        raise VariantError(f"variant {variant!r}: modifier lặp")
    lengths = [m for m in mods if m in LENGTH_MODIFIERS]
    if len(lengths) > 1:
        raise VariantError(f"variant {variant!r}: chỉ được một modifier độ dài ({', '.join(LENGTH_MODIFIERS)})")
    if base == "T1" and lengths:
        raise VariantError(f"variant {variant!r}: T1 không có description nên không nhận modifier độ dài {lengths[0]}")
    mods = [m for m in mods if m != DEFAULT_LENGTH]
    return "+".join([base, *sorted(mods, key=MODIFIER_ORDER.index)])


def text_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


# Mã nguồn quyết định text của B0 (và của production mà B0 phải khớp) — đổi file nào thì text/vector/collection cũ bị coi là cũ.
FINGERPRINT_SOURCES = (
    "src/backend/app/domain/catalog/text_builder.py", "src/backend/app/domain/catalog/models.py",
    "src/data_collection/seed/parse_combos.py", "src/data_collection/collectors/textutil.py",
    "src/data_collection/seed/load_products.py", "src/data_collection/seed/catalog_meta.py",
    "src/evaluation/search_bench/catalog.py", "src/evaluation/search_bench/textbuild.py",
)


def builder_fingerprint(cfg: SBenchConfig) -> str:
    """Dấu của mọi thứ quyết định text: config `text` + search_unit_variants + mã nguồn ở FINGERPRINT_SOURCES."""
    h = hashlib.sha256()
    h.update(json.dumps({"text": cfg.text.model_dump(), "units": cfg.catalog.search_unit_variants}, sort_keys=True).encode())
    for rel in FINGERPRINT_SOURCES:
        src = paths.repo_root() / rel
        h.update(rel.encode() + b"|" + (src.read_bytes() if src.exists() else b"missing"))
    return h.hexdigest()[:16]


def combo_manual_sha256(dataset: str) -> str | None:
    """sha256 của `combo_items_manual.jsonl` đi kèm nguồn của dataset (None nếu không có) — soát tay đổi thì text combo đổi."""
    mp = catalog.source_manual_path(dataset)
    return hashlib.sha256(mp.read_bytes()).hexdigest() if mp else None


def text_inputs(cfg: SBenchConfig, dataset: str) -> dict:
    """Đầu vào (ngoài items) quyết định text hiện tại — ghi vào meta text / vector / mô tả collection để lệnh sau so."""
    return {"builder_fingerprint": builder_fingerprint(cfg), "combo_manual_sha256": combo_manual_sha256(dataset)}


def text_file(dataset: str, variant: str) -> Path:
    return paths.data_dir(dataset) / f"text_{normalize_variant(variant)}.parquet"


def _meta_file(dataset: str, variant: str) -> Path:
    return text_file(dataset, variant).with_suffix(".meta.json")


APP_BUILDER_NAME = "backend:src/backend/app/domain/catalog/text_builder.py::build_text"


def _import_backend():
    """Module catalog của backend (tầng domain thuần Python — không kéo FastAPI/DB)."""
    import importlib
    import sys
    src = str(src_dir())
    if src not in sys.path:
        sys.path.insert(0, src)
    return importlib.import_module("backend.app.domain.catalog")


def app_builder():
    """(build_text, Product, TEXT_BUILDER_VERSION) của backend; thiếu thì lỗi cứng — B0 không được rơi về builder khác."""
    try:
        mod = _import_backend()
        return mod.build_text, mod.Product, getattr(mod, "TEXT_BUILDER_VERSION", "unknown")
    except Exception as e:  # noqa: BLE001
        raise TextBuildError(f"không import được {APP_BUILDER_NAME} ({type(e).__name__}: {e}) — "
                             "T3+R (B0) bắt buộc dùng bản production") from None


def build_texts(cfg: SBenchConfig, dataset: str, variant: str, *, limit: int | None = None) -> tuple[pd.DataFrame, dict]:
    v = normalize_variant(variant)
    if v not in APP_VARIANTS:
        raise VariantNotImplemented(f"variant {v}: Part 2 đầy đủ (T0–T3 + modifier) làm ngày 4 — hiện chỉ có {', '.join(APP_VARIANTS)}")
    build_text, Product, version = app_builder()
    stats = catalog.read_stats(dataset)
    items = catalog.read_items(dataset)
    records = catalog.reload_records(cfg, dataset)
    units, children, _, _ = catalog.group_children(records, cfg.catalog.search_unit_variants)
    by_id = {r["productId"]: r for r in units}
    ids = items["product_id"].tolist()
    if limit is not None:
        ids = ids[:limit]
    missing = [pid for pid in ids if pid not in by_id]
    if missing:
        raise TextBuildError(f"{len(missing)} search unit của items không có trong nguồn, ví dụ {missing[:3]} — chạy lại `sb catalog build`")
    manual = catalog.source_manual_path(dataset)
    if dataset == "jsonl" and manual is None:
        raise TextBuildError("snapshot thiếu combo_items_manual.jsonl cạnh products.jsonl — production luôn áp bản soát tay "
                             "combo (manifest bắt buộc comboManual); bung lại snapshot bằng `sb catalog build`")
    combo_items, combo_attrs, combo_info = catalog.combo_enrichment(records, manual)

    def product(rec: dict):
        extra = combo_attrs.get(rec["productId"])       # như load_products: attributes combo += priceBasis / nights / minPax
        return Product.from_cdp({**rec, "attributes": {**(rec.get("attributes") or {}), **extra}} if extra else rec)

    # gọi y như PostgresCatalogReader: không truyền max_desc_words (mặc định của build_text), không chuẩn hoá thêm
    texts = [build_text(product(by_id[pid]), [product(k) for k in children.get(pid, [])], combo_items=combo_items.get(pid, []))
             for pid in ids]
    not_nfc = [pid for pid, t in zip(ids, texts) if unicodedata.normalize("NFC", t) != t]
    if not_nfc:
        log.warning("text production không ở dạng NFC — B0 giữ nguyên như production", n=len(not_nfc), example=not_nfc[:3])
    empty = [pid for pid, t in zip(ids, texts) if not t.strip()]
    if empty:
        raise TextBuildError(f"{len(empty)} text rỗng, ví dụ {empty[:3]}")
    df = pd.DataFrame({"product_id": ids, "text": texts, "text_hash": [text_hash(t) for t in texts]})
    meta = {"variant": v, "dataset": dataset, "text_builder": f"app:{APP_BUILDER_NAME}", "text_builder_version": version,
            "combo_items": combo_info, "items_sha256": stats["items_sha256"], **text_inputs(cfg, dataset),
            "n": len(df), "complete": len(df) == len(items), "max_description_words": "mặc định của build_text",
            "created_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")}
    return df, meta


def write_texts(dataset: str, df: pd.DataFrame, meta: dict) -> Path:
    p = text_file(dataset, meta["variant"])
    pq.write_table(pa.Table.from_pandas(df, schema=TEXT_SCHEMA, preserve_index=False), p)
    dump_json(_meta_file(dataset, meta["variant"]), meta)
    stats_p = paths.data_dir(dataset) / paths.STATS              # spec §1.1: text_builder ghi vào stats.json
    stats = json.loads(stats_p.read_text(encoding="utf-8"))
    stats.setdefault("text_builders", {})[meta["variant"]] = meta["text_builder"]
    dump_json(stats_p, stats)
    return p


def load_texts(cfg: SBenchConfig, dataset: str, variant: str, *, need: int | None = None) -> tuple[pd.DataFrame, dict]:
    """Đọc text đã dựng nếu còn khớp items hiện tại và đủ dòng; không thì dựng lại toàn bộ và ghi đè."""
    v = normalize_variant(variant)
    p, mp = text_file(dataset, v), _meta_file(dataset, v)
    stats = catalog.read_stats(dataset)
    if p.exists() and mp.exists():
        meta = json.loads(mp.read_text(encoding="utf-8"))
        enough = meta.get("complete") or (need is not None and meta.get("n", 0) >= need)
        now = text_inputs(cfg, dataset)
        fresh = meta.get("items_sha256") == stats["items_sha256"] and all(meta.get(k) == val for k, val in now.items())
        if fresh and enough:
            return pq.read_table(p).to_pandas(), meta
        log.info("text cũ (items / builder / soát tay combo / config đổi) hoặc thiếu dòng — dựng lại", variant=v, dataset=dataset)
    df, meta = build_texts(cfg, dataset, v)
    write_texts(dataset, df, meta)
    return df, meta
