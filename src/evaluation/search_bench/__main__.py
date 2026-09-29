"""CLI sbench (spec §1.3). Chạy từ `src/`: `python -m evaluation.search_bench <lệnh>` (trên Windows đặt PYTHONUTF8=1).

Mã thoát: 0 ok · 1 lỗi · 2 gate trượt / variant, arm chưa cài. Nhóm `sb gold`: 0 đạt · 1 dữ liệu vi phạm luật ·
2 lỗi đầu vào.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(add_completion=False, no_args_is_help=True,
                  help="sbench — benchmark embedding + search (Weaviate + Cohere) cho V-OTA")
catalog_app = typer.Typer(no_args_is_help=True, help="Part 1: products.jsonl → items.parquet, vocab")
app.add_typer(catalog_app, name="catalog")


@dataclass
class Ctx:
    run_id: Optional[str]
    config_path: Optional[str]
    dataset: str
    verbose: bool
    _cfg: object = field(default=None, repr=False)

    def cfg(self):
        if self._cfg is None:
            from .config import load_config
            self._cfg = load_config(self.config_path)
        return self._cfg


def _ctx(c: typer.Context) -> Ctx:
    return c.obj


def _console():
    """Console rich; khi không phải terminal (pipe, log) dùng bề rộng cố định để bảng không bị bẻ ở 80 cột."""
    import sys
    from rich.console import Console
    return Console(width=None if sys.stdout.isatty() else 180, soft_wrap=True)


def _fail(msg: str, code: int = 1) -> None:
    typer.secho(msg, fg=typer.colors.RED, err=True)
    raise typer.Exit(code)


@app.callback()
def main(c: typer.Context,
         run_id: Optional[str] = typer.Option(None, "--run-id", help="RUN_ID (mặc định run.default_run_id)"),
         config: Optional[str] = typer.Option(None, "--config", help="đường dẫn sbench.yaml"),
         dataset: str = typer.Option("jsonl", "--dataset", help="jsonl (catalog thật) | sample | fake"),
         verbose: bool = typer.Option(False, "-v", "--verbose")):
    from . import paths
    from .config import load_env
    from .logsetup import setup_logging
    setup_logging(verbose)
    load_env()
    try:
        paths.check_dataset(dataset)
    except ValueError as e:
        _fail(str(e), 2)
    c.obj = Ctx(run_id=run_id, config_path=config, dataset=dataset, verbose=verbose)


# ------------------------------------------------------------------ Part 0
@app.command()
def doctor(c: typer.Context, skip_api: bool = typer.Option(False, "--skip-api", help="không gọi Cohere tokenize")):
    """Kiểm môi trường: Docker, Weaviate, ascii_fold, key Cohere, catalog, đĩa."""
    from .doctor import print_checks, run_doctor
    code = print_checks(run_doctor(_ctx(c).cfg(), skip_api=skip_api))
    if code:
        raise typer.Exit(code)


# ------------------------------------------------------------------ Part 1
@catalog_app.command("build")
def catalog_build(c: typer.Context,
                  source: Optional[str] = typer.Option(None, "--source", help="jsonl | sample | fake (mặc định = --dataset)"),
                  allow_id_drift: bool = typer.Option(False, "--allow-id-drift", help="chấp nhận amenity id đổi so với lần trước")):
    """Dựng items.parquet + amenity_vocab.json + stats.json cho một dataset."""
    from .catalog import CatalogError, build_catalog
    ctx = _ctx(c)
    try:
        stats = build_catalog(ctx.cfg(), source or ctx.dataset, allow_id_drift=allow_id_drift)
    except CatalogError as e:
        _fail(str(e))
    am = stats["amenity"]
    con = _console()
    con.print(f"[bold]{stats['n_search_units']}[/] search unit / {stats['n_records']} bản ghi  ·  dataset {stats['dataset']}",
              highlight=False)
    con.print(f"  theo variant: {stats['search_units_by_variant']}", highlight=False)
    con.print(f"  con bị mồ côi: {stats['orphan_children']}  ·  điểm đến: {stats['n_destinations']}  ·  "
              f"description derived: {stats['description_derived_rate']:.1%}", highlight=False)
    con.print(f"  amenity: phủ {am['coverage_all']:.1%} · id seed {am['n_ids_seed']} · raw {am['n_ids_raw']} · "
              f"khớp trigram {am['n_fuzzy_hits']} · raw bỏ {am['dropped']['distinct']}", highlight=False)
    con.print(f"  n_children: {stats['n_children']['buckets']}", highlight=False)


@catalog_app.command("vocab")
def catalog_vocab(c: typer.Context):
    """vocab.json: điểm đến, tên, amenity, hạng phòng, hãng bay, IATA (+ bản bỏ dấu) và filter_fields."""
    from .catalog import CatalogError, build_vocab_file
    ctx = _ctx(c)
    try:
        v = build_vocab_file(ctx.cfg(), ctx.dataset)
    except CatalogError as e:
        _fail(str(e))
    typer.echo(f"vocab.json: {len(v['destinations'])} điểm đến · {len(v['products'])} sản phẩm · "
               f"{len(v['amenities'])} amenity · {len(v['room_classes'])} hạng phòng · {len(v['airlines'])} hãng bay · "
               f"{len(v['iata'])} mã IATA")


# ------------------------------------------------------------------ Part 2
@app.command()
def text(c: typer.Context,
         variant: str = typer.Option(..., "--variant", help="vd T3+R"),
         limit: Optional[int] = typer.Option(None, "--limit", min=1, help="chỉ dựng N search unit đầu"),
         show: int = typer.Option(0, "--show", min=0, help="in N văn bản đầu")):
    """Dựng embed_text cho variant → data/text_<variant>.parquet."""
    from .catalog import CatalogError
    from .textbuild import TextBuildError, VariantError, VariantNotImplemented, build_texts, write_texts
    ctx = _ctx(c)
    try:
        df, meta = build_texts(ctx.cfg(), ctx.dataset, variant, limit=limit)
    except (VariantError, VariantNotImplemented) as e:
        _fail(str(e), 2)
    except (TextBuildError, CatalogError) as e:
        _fail(str(e))
    p = write_texts(ctx.dataset, df, meta)
    words = df["text"].str.split().str.len()
    typer.echo(f"{meta['variant']}: {len(df)} text ({meta['text_builder']}) → {p}  ·  số từ p50 {words.median():.0f} / max {words.max()}")
    for row in df.head(show).itertuples():
        typer.echo(f"\n[{row.product_id}]\n{row.text}")


@app.command()
def tokens(c: typer.Context, variant: str = typer.Option(..., "--variant"),
           model: str = typer.Option("cohere-v3", "--model", help="model Cohere có tokenizer"),
           top: int = typer.Option(10, "--top", min=0, help="in N text dài nhất")):
    """Đếm token offline (tokenizer Cohere tải một lần) → p50/p90/p99/max; gate p99 ≤ token_p99_max, max < token_hard_max."""
    import os
    from . import tokens as tk
    from .catalog import CatalogError
    from .textbuild import TextBuildError, VariantError, VariantNotImplemented, load_texts
    ctx = _ctx(c)
    cfg = ctx.cfg()
    try:
        api_model = cfg.model_cfg(model).api_model
        if not api_model:
            raise ValueError(f"model {model} không phải Cohere — tokenizer offline chỉ có cho cohere-v3 / cohere-v4")
        df, meta = load_texts(cfg, ctx.dataset, variant)
        counter = tk.TokenCounter(tk.ensure_tokenizer(api_model, os.environ.get("COHERE_API_KEY")))
    except (VariantError, VariantNotImplemented, ValueError) as e:
        _fail(str(e), 2)
    except (TextBuildError, CatalogError, tk.TokenizerUnavailable) as e:
        _fail(str(e))
    counts = counter.count(df["text"].tolist())
    st = tk.token_stats(counts)
    typer.echo(f"{meta['variant']} · {model}: n={st['n']} p50={st['p50']:.0f} p90={st['p90']:.0f} p99={st['p99']:.0f} max={st['max']}"
               f"  (tính cả 2 token đặc biệt/text; Cohere tính tiền không gồm chúng)")
    over = sorted(((n, pid) for n, pid in zip(counts, df["product_id"]) if n > cfg.text.token_p99_max), reverse=True)
    if over:
        typer.echo(f"{len(over)} text > {cfg.text.token_p99_max} token:")
    for n, pid in (over or sorted(zip(counts, df["product_id"]), reverse=True))[:top]:
        typer.echo(f"  {n:4d}  {pid}")
    why = tk.gate(st, cfg.text.token_p99_max, cfg.text.token_hard_max)
    if why:
        _fail("TOKEN GATE TRƯỢT: " + "; ".join(why) + " — sửa text builder, không bật truncate", 2)
    typer.echo("token gate: qua")


# ------------------------------------------------------------------ Part 3
@app.command()
def embed(c: typer.Context,
          variant: str = typer.Option(..., "--variant"),
          model: str = typer.Option(..., "--model", help="cohere-v3 | cohere-v4 | fake"),
          limit: Optional[int] = typer.Option(None, "--limit", min=1, help="chỉ embed N search unit đầu"),
          input_type: str = typer.Option("document", "--input-type", help="document (mặc định) | query"),
          no_cache: bool = typer.Option(False, "--no-cache", help="không đọc/ghi cache (đo RTT)"),
          fake_ignore_input_type: bool = typer.Option(False, "--fake-ignore-input-type", help="fake: bỏ input_type (giả lập lỗi)")):
    """Embed text của variant → data/vec_<variant>_<model>.npy + .ids.json + .meta.json; in text mới / từ cache / lượt gọi / token / USD."""
    import time
    from . import vectors
    from .catalog import CatalogError
    from .embed import EmbedBatchError, EmbedderUnavailable, TokenLimitError, make_embedder
    from .textbuild import TextBuildError, VariantError, VariantNotImplemented, load_texts
    ctx = _ctx(c)
    cfg = ctx.cfg()
    if input_type not in ("document", "query"):
        _fail("--input-type phải là document | query", 2)
    try:
        df, tmeta = load_texts(cfg, ctx.dataset, variant, need=limit)
        emb = make_embedder(cfg, model, no_cache=no_cache, fake_ignore_input_type=fake_ignore_input_type)
    except (VariantError, VariantNotImplemented) as e:
        _fail(str(e), 2)
    except (TextBuildError, CatalogError, EmbedderUnavailable) as e:
        _fail(str(e))
    if limit is not None:
        df = df.head(limit)
    ids, texts = df["product_id"].tolist(), df["text"].tolist()
    t0 = time.perf_counter()
    try:
        vecs = emb.embed(texts, input_type)
    except TokenLimitError as e:
        _fail(f"{e}\n  product_id: {[ids[i] for i, _ in e.over[:10]]}", 2)
    except EmbedBatchError as e:
        _fail(f"{e}\n  product_id trong lô: {[ids[i] for i in e.positions[:10]]}… (lô đã thành công trước đó vẫn nằm trong cache)")
    finally:
        emb.close()
    dt = time.perf_counter() - t0
    st = emb.stats
    tag = vectors.tag_of(emb.name)
    meta = vectors.write(ctx.dataset, tmeta["variant"], model, input_type, ids, vecs, tag=tag, extra={
        "cache_model": emb.name, "items_sha256": tmeta["items_sha256"], "text_builder": tmeta["text_builder"],
        "builder_fingerprint": tmeta.get("builder_fingerprint"), "combo_manual_sha256": tmeta.get("combo_manual_sha256"),
        "text_builder_version": tmeta.get("text_builder_version"),
        "text_sha256": vectors.texts_digest(df["text_hash"].tolist()), "limit": limit, "no_cache": no_cache,
        "n_new": emb.n_new, "n_cached": emb.n_cached, "n_calls": st.n_calls if st else None,
        "n_tokens": st.n_tokens if st else None, "usd": round(st.usd, 6) if st else None, "seconds": round(dt, 2)})
    typer.echo(f"{meta['file']}: {len(ids)} vector × {vecs.shape[1]}  ·  mới {emb.n_new} · từ cache {emb.n_cached}  ·  "
               f"lượt gọi {meta['n_calls']} · token {meta['n_tokens']} · ${meta['usd']}  ·  {dt:.2f} s")


# ------------------------------------------------------------------ Part 4
collection_app = typer.Typer(no_args_is_help=True, help="Part 4: collection Weaviate")
app.add_typer(collection_app, name="collection")


def _store(cfg):
    from .store.weaviate_store import WeaviateStore
    try:
        return WeaviateStore(cfg.weaviate)
    except Exception as e:  # noqa: BLE001 — lỗi kết nối của client
        _fail(f"không kết nối được Weaviate {cfg.weaviate.url}: {str(e)[:200]} — chạy `sb doctor`")


def _weaviate_errors():
    from weaviate.exceptions import WeaviateBaseError
    from .store.weaviate_store import StoreError
    return (StoreError, WeaviateBaseError)


def _collection_description(ctx: Ctx, variant: str, model: str, *, n: int | None, cache_model: str | None,
                            text_builder: str | None, builder_fingerprint: str | None,
                            combo_manual_sha256: str | None = None) -> dict:
    from .catalog import read_stats
    from .store.weaviate_store import collection_name
    logical, _ = collection_name(variant, model, ctx.dataset)
    return {"logical_name": logical, "dataset": ctx.dataset, "variant": variant, "model": model, "cache_model": cache_model,
            "items_sha256": read_stats(ctx.dataset)["items_sha256"], "n": n, "text_builder": text_builder,
            "builder_fingerprint": builder_fingerprint, "combo_manual_sha256": combo_manual_sha256}


@collection_app.command("create")
def collection_create(c: typer.Context, variant: str = typer.Option(..., "--variant"), model: str = typer.Option(..., "--model"),
                      recreate: bool = typer.Option(False, "--recreate", help="xoá collection cùng tên nếu có")):
    """Tạo collection rỗng: named vector `content` (self-provided, flat, cosine), BM25 word + ascii fold, amenity_ids[].
    `sb load` luôn dựng lại collection này rồi mới nạp."""
    from .catalog import CatalogError
    from .embed import EmbedderUnavailable, embedder_name
    from .store.weaviate_store import StoreError, collection_name
    from .textbuild import VariantError, normalize_variant
    ctx = _ctx(c)
    cfg = ctx.cfg()
    try:
        v = normalize_variant(variant)
        logical, phys = collection_name(v, model, ctx.dataset)
        desc = _collection_description(ctx, v, model, n=None, cache_model=embedder_name(cfg, model), text_builder=None,
                                       builder_fingerprint=None)
    except (VariantError, StoreError, EmbedderUnavailable) as e:
        _fail(str(e), 2)
    except CatalogError as e:
        _fail(str(e))
    with _store(cfg) as st:
        try:
            mode = st.create_collection(phys, description=desc, recreate=recreate)
        except _weaviate_errors() as e:
            _fail(str(e))
    typer.echo(f"{phys} (logic {logical}) · ascii_fold {mode} · index {cfg.weaviate.vector_index} · "
               f"stopwords {cfg.weaviate.bm25.stopwords_preset}")


@collection_app.command("list")
def collection_list(c: typer.Context):
    """Liệt kê collection Products__* kèm số object và nguồn gốc."""
    with _store(_ctx(c).cfg()) as st:
        try:
            rows = st.list_collections()
        except _weaviate_errors() as e:
            _fail(str(e))
    for name, n, d in rows:
        typer.echo(f"{name:<45} {n:>6}  {d.get('logical_name', '?')}  dataset={d.get('dataset')}  complete={d.get('complete')}  "
                   f"embedder={d.get('cache_model')}  fold={d.get('ascii_fold_mode')}  items={str(d.get('items_sha256'))[:10]}")
    if not rows:
        typer.echo("(chưa có collection)")


@collection_app.command("drop")
def collection_drop(c: typer.Context, name: str = typer.Argument(..., help="tên vật lý, vd Products__T3_R__cohere_v3"),
                    yes: bool = typer.Option(False, "--yes", help="xác nhận xoá")):
    """Xoá một collection (spec: không xoá collection thua trước khi FINAL.md commit)."""
    if not yes:
        _fail("thêm --yes để xác nhận xoá", 2)
    with _store(_ctx(c).cfg()) as st:
        try:
            st.drop(name)
        except _weaviate_errors() as e:
            _fail(str(e))
    typer.echo(f"đã xoá {name}")


@app.command()
def load(c: typer.Context, variant: str = typer.Option(..., "--variant"), model: str = typer.Option(..., "--model")):
    """Dựng lại collection của (variant, model) và nạp vector đã embed; kiểm count == số id, rồi mới đánh dấu complete."""
    import time
    from . import vectors
    from .catalog import CatalogError, read_items, read_stats
    from .embed import EmbedderUnavailable, embedder_name
    from .store.weaviate_store import StoreError, collection_name
    from .textbuild import TextBuildError, VariantError, load_texts, normalize_variant
    ctx = _ctx(c)
    cfg = ctx.cfg()
    try:
        v = normalize_variant(variant)
        expected = embedder_name(cfg, model)
        logical, phys = collection_name(v, model, ctx.dataset)
        ids, vecs, vmeta = vectors.read(ctx.dataset, v, model, "document")
        stats = read_stats(ctx.dataset)
        tdf, tmeta = load_texts(cfg, ctx.dataset, v, need=len(ids))
        items = read_items(ctx.dataset)
    except (VariantError, StoreError, EmbedderUnavailable) as e:
        _fail(str(e), 2)
    except (CatalogError, TextBuildError, vectors.VectorsMissing) as e:
        _fail(str(e))
    if not ids:
        _fail("file vector rỗng — chạy lại `sb embed`")
    if vmeta.get("cache_model") != expected:
        _fail(f"vector do embedder {vmeta.get('cache_model')} sinh, collection {logical} cần {expected} — embed lại đúng model")
    if vmeta.get("items_sha256") != stats["items_sha256"]:
        _fail("vector được embed từ items cũ — chạy lại `sb embed`")
    texts = dict(zip(tdf["product_id"], tdf["text"]))
    hashes = dict(zip(tdf["product_id"], tdf["text_hash"]))
    if any(pid not in hashes for pid in ids) or vectors.texts_digest([hashes[pid] for pid in ids]) != vmeta.get("text_sha256"):
        _fail("text hiện tại khác text đã embed (builder / config / catalog đổi) — chạy lại `sb embed`")
    desc = _collection_description(ctx, v, model, n=len(ids), cache_model=expected, text_builder=tmeta.get("text_builder"),
                                   builder_fingerprint=tmeta.get("builder_fingerprint"),
                                   combo_manual_sha256=tmeta.get("combo_manual_sha256"))
    t0 = time.perf_counter()
    with _store(cfg) as st:
        try:
            mode = st.create_collection(phys, description=desc, recreate=True)
            try:
                n = st.load(phys, items, texts, ids, vecs, fold_mode=mode)
            except BaseException:
                st.drop(phys)                          # không để lại collection nạp dở
                raise
            st.mark_complete(phys)
        except _weaviate_errors() as e:
            _fail(f"{e} (collection {phys} đã bị xoá, không để lại bản nạp dở)")
    typer.echo(f"{phys} (logic {logical}): {n} object · ascii_fold {mode} · stopwords {cfg.weaviate.bm25.stopwords_preset} · "
               f"{time.perf_counter() - t0:.1f} s")


@app.command()
def query(c: typer.Context, q: str = typer.Argument(..., help="câu truy vấn"),
          arm: str = typer.Option("B0", "--arm"),
          mode: Optional[str] = typer.Option(None, "--mode", help="dense | bm25 (mặc định theo arm)"),
          model: Optional[str] = typer.Option(None, "--model", help="ghi đè model của arm (vd fake để thử khung)"),
          limit: int = typer.Option(10, "--limit", min=1, max=1000)):
    """Chạy một truy vấn theo arm, in top-k với distance (dense) hoặc score (bm25)."""
    from rich.table import Table
    from .arms import ArmError, load_arm
    from .catalog import CatalogError, read_stats
    from .embed import EmbedBatchError, EmbedderUnavailable, make_embedder
    from .store.weaviate_store import StoreError, collection_name
    ctx = _ctx(c)
    cfg = ctx.cfg()
    try:
        a = load_arm(arm)
        m = model or a.model
        how = mode or a.retrieval
        if how not in ("dense", "bm25"):
            raise ArmError(f"retrieval {how} chưa cài (ngày 1: dense | bm25)")
        logical, phys = collection_name(a.text_variant, m, ctx.dataset)
        items_sha = read_stats(ctx.dataset)["items_sha256"]
        from .textbuild import text_inputs
        now = text_inputs(cfg, ctx.dataset)
    except (ArmError, StoreError) as e:
        _fail(str(e), 2)
    except CatalogError as e:
        _fail(str(e))
    with _store(cfg) as st:
        try:
            desc = st.check_ready(phys, items_sha, now)
            if how == "dense":
                emb = make_embedder(cfg, m, embedding_type=a.embedding_types, preflight=False)
                try:
                    if emb.name != desc.get("cache_model"):
                        raise StoreError(f"collection {phys} nạp vector của {desc.get('cache_model')}, query đang embed bằng {emb.name}")
                    qvec = emb.embed([q], a.query_input_type)[0]
                finally:
                    emb.close()
                hits = st.dense(phys, qvec, limit)
                note = f"query embed ({emb.name}): {'từ cache' if emb.n_cached else 'mới'} · input_type={a.query_input_type}"
            else:
                hits = st.bm25(phys, q, limit, fold_mode=desc["ascii_fold_mode"])
                note = f"bm25 {desc.get('bm25')} · fold={desc.get('ascii_fold_mode')}"
        except (EmbedderUnavailable, EmbedBatchError, *_weaviate_errors()) as e:
            _fail(str(e))
    t = Table(title=f"{arm} · {how} · {logical} ({desc.get('n')} object) · “{q}”")
    for col in ("#", "product_id", "name", "destination", "variant", "distance" if how == "dense" else "score"):
        t.add_column(col, overflow="fold")
    for h in hits:
        val = h.distance if how == "dense" else h.score
        t.add_row(str(h.rank), h.product_id[:8], h.name, h.destination, h.variant, f"{val:.4f}" if val is not None else "-")
    con = _console()
    con.print(t)
    con.print(note, style="dim", highlight=False)


# ------------------------------------------------------------------ Part 5 (ngày 2: pool, split)
gold_app = typer.Typer(no_args_is_help=True, help="Part 5: gold — drafts, pool, split, kappa, merge, import, check. "
                        "Mã thoát: 0 đạt · 1 dữ liệu vi phạm luật · 2 lỗi đầu vào (file thiếu, sai định dạng, sai sha)")
app.add_typer(gold_app, name="gold")


def _fill_guard(ctx):
    """Chặn --fill lấp ý định đã chết vì catalog trôi: nguồn không còn, hoặc filter khớp 0 sản phẩm."""
    import pandas as pd

    from . import paths
    from .gold import make_fill_guard
    return make_fill_guard(pd.read_parquet(paths.data_dir(ctx.dataset) / paths.ITEMS))


@gold_app.command("drafts")
def gold_drafts(c: typer.Context,
                labels: Optional[Path] = typer.Option(None, "--labels", help="mặc định bench_out/search/labels/labels.jsonl"),
                raw: Optional[Path] = typer.Option(None, "--raw", help="mặc định gold/drafts_raw.tsv"),
                out: Optional[Path] = typer.Option(None, "--out", help="mặc định gold/drafts.txt"),
                fill: bool = typer.Option(False, "--fill", help="slice dưới mục tiêu gold.slices: tự lấp 1 cách nói của ý "
                                                               "định chưa chọn (chưa gán, hoặc loại vì duplicate/unnatural), "
                                                               "có kiểm grounding — mặc định TẮT: chỉ lấy câu người soát chọn"),
                dry_run: bool = typer.Option(False, "--dry-run", help="chỉ in báo cáo, không ghi file")):
    """Nhãn của app soát draft (KEEP/REJECT/NEEDS_EDIT) + overrides.tsv → gold/drafts.txt: giữ 1 cách nói mỗi ý định,
    lấy **mọi** câu người soát chọn (không cắt theo quota — quota là mục tiêu tham khảo); mỗi slice nên ≥
    gold.min_per_slice câu (thiếu thì cảnh báo, vẫn ghi — `gold check` chặn ở bước cuối)."""
    from collections import Counter

    from . import paths
    from .gold import (GoldError, apply_overrides, read_draft_cases, read_overrides, render_drafts_report,
                       resolve_decisions, select_drafts, slices_below_min, write_drafts)
    from .labeling import JsonlLabelStore
    ctx = _ctx(c)
    cfg = ctx.cfg()
    overrides_p = paths.GOLD_DIR / "overrides.tsv"
    labels_p = labels or paths.sbench_home() / "labels" / "labels.jsonl"
    raw_p = raw or paths.GOLD_DIR / "drafts_raw.tsv"
    out_p = out or paths.GOLD_DIR / "drafts.txt"
    if not labels_p.exists():
        _fail(f"không thấy kho nhãn {labels_p} — chạy app soát draft (streamlit_app.py) trước", 2)
    guard = _fill_guard(ctx) if fill else None
    try:
        cases = read_draft_cases(raw_p)
        decisions, conflicts = resolve_decisions(JsonlLabelStore(labels_p).load_events())
        overrides = read_overrides(overrides_p, {r["case_id"] for r in cases})
        decisions, conflicts = apply_overrides(decisions, conflicts, overrides)
        rows, report = select_drafts(cases, decisions, dict(cfg.gold.slices), fill=fill, fill_guard=guard, cap=False)
    except GoldError as e:
        _fail(str(e), 2)
    n_min = int(cfg.gold.min_per_slice)
    typer.echo(render_drafts_report(report, n_min))
    if overrides:
        typer.secho(f"  ghi đè từ {overrides_p.name}: {len(overrides)} case "
                    f"({dict(Counter(o['verdict'] for o in overrides.values()))})", fg=typer.colors.CYAN)
    if report["filled"]:
        typer.secho(f"  --fill: lấp {len(report['filled'])} ý định (nguồn: "
                    f"{dict(Counter(f['kind'].split(' (')[0] for f in report['filled']))})", fg=typer.colors.CYAN)
        for f in report["filled"]:
            typer.echo(f"      + {f['case_id']} [{f['slice']}] {f['kind']}: {f['query']}")
    if report["skipped_fill"]:
        typer.secho(f"  --fill bỏ qua {len(report['skipped_fill'])} ý định:", fg=typer.colors.YELLOW)
        for s in report["skipped_fill"][:40]:
            typer.echo(f"      - {s['case_id']} [{s['slice']}] {s['why']}")
    typer.echo(f"  nhãn: {len(decisions)}/{len(cases)} case đã gán · loại {sum(report['reject_reasons'].values())} "
               f"({report['reject_reasons']}) · gộp {len(report['dropped_duplicate'])} cách nói trùng ý định")
    if conflicts:
        typer.secho(f"  BẤT ĐỒNG giữa annotator, không chọn: {', '.join(conflicts)}", fg=typer.colors.YELLOW)
    short = slices_below_min(report, n_min)
    if short:
        typer.secho(f"  {len(short)} slice dưới {n_min} câu: {', '.join(short)} — chọn thêm (app: Bộ câu đã chọn / Bổ sung "
                    "câu hỏi) trước khi tag gold", fg=typer.colors.YELLOW)
    if dry_run:
        typer.echo("  --dry-run: không ghi file")
        return
    write_drafts(out_p, rows)
    typer.echo(f"{out_p}: {len(rows)} dòng")


@gold_app.command("pool")
def gold_pool(c: typer.Context,
              drafts: Optional[Path] = typer.Option(None, "--drafts", help="mặc định gold/drafts.txt của package"),
              depth: Optional[int] = typer.Option(None, "--depth", min=1, help="mặc định gold.pool_depth"),
              slice_: Optional[str] = typer.Option(None, "--slice", help="chỉ lấy draft của một slice"),
              out: Optional[Path] = typer.Option(None, "--out", help="mặc định gold/pool.csv của package"),
              arm: str = typer.Option("B0", "--arm", help="arm cung cấp collection + cách embed query"),
              qid_mode: str = typer.Option("case", "--qid", help="case: case_id của drafts_raw.tsv · line: q001… theo dòng"),
              raw: Optional[Path] = typer.Option(None, "--raw", help="mặc định gold/drafts_raw.tsv (cho --qid case)"),
              allow_empty: bool = typer.Option(False, "--allow-empty", help="vẫn ghi khi câu thường không có ứng viên nào")):
    """Dense top-depth ∪ BM25 top-depth (filter đầy đủ của draft) trên collection B0 → pool.csv đúng hợp đồng
    gold_schema + pool.build.json. Mã thoát: 0 · 1 câu thường không có ứng viên · 2 lỗi đầu vào."""
    from datetime import datetime

    from . import paths
    from .arms import ArmError, load_arm
    from .catalog import CatalogError, read_stats
    from .embed import EmbedBatchError, EmbedderUnavailable, make_embedder
    from .gold import (GoldError, PoolBuild, build_pool, case_ids_for, load_key_index, load_pool_view, parse_drafts,
                       pool_build_path, pool_summary, read_draft_cases, read_overrides, snapshot_of, write_pool_build)
    from .gold_schema import OUT_OF_CATALOG_SLICE, file_sha256, write_pool_csv
    from .store.weaviate_store import StoreError, collection_name
    ctx = _ctx(c)
    cfg = ctx.cfg()
    drafts_p = drafts or paths.GOLD_DIR / "drafts.txt"
    out_p = out or paths.GOLD_DIR / "pool.csv"
    if qid_mode not in ("case", "line"):
        _fail("--qid phải là case hoặc line", 2)
    try:
        a = load_arm(arm)
        ds = parse_drafts(drafts_p, list(cfg.gold.slices), load_key_index(paths.data_dir(ctx.dataset) / paths.AMENITY_VOCAB))
        if qid_mode == "case":
            raw_p = raw or paths.GOLD_DIR / "drafts_raw.tsv"
            cases = read_draft_cases(raw_p)
            overrides = read_overrides(paths.GOLD_DIR / "overrides.tsv", {r["case_id"] for r in cases})
            ds = [d.with_qid(q) for d, q in zip(ds, case_ids_for(ds, cases, overrides))]
        if slice_:
            ds = [d for d in ds if d.slice == slice_]
            if not ds:
                raise GoldError(f"không có draft nào thuộc slice {slice_}")
        logical, phys = collection_name(a.text_variant, a.model, ctx.dataset)
        stats = read_stats(ctx.dataset)
        from .textbuild import text_inputs
        now = text_inputs(cfg, ctx.dataset)
        view = load_pool_view(cfg, ctx.dataset, a.text_variant)
    except (ArmError, GoldError, StoreError, CatalogError) as e:
        _fail(str(e), 2)
    with _store(cfg) as st:
        try:
            desc = st.check_ready(phys, stats["items_sha256"], now)
            emb = make_embedder(cfg, a.model, embedding_type=a.embedding_types, preflight=False)
            try:
                if emb.name != desc.get("cache_model"):
                    raise StoreError(f"collection {phys} nạp vector của {desc.get('cache_model')}, query embed bằng {emb.name}")
                rows = build_pool(ds, store=st, embedder=emb, physical=phys, fold_mode=desc["ascii_fold_mode"],
                                  depth=depth or cfg.gold.pool_depth, query_input_type=a.query_input_type, view=view)
            finally:
                emb.close()
        except GoldError as e:
            _fail(str(e), 2)
        except (EmbedderUnavailable, EmbedBatchError, *_weaviate_errors()) as e:
            _fail(str(e))
    s = pool_summary(ds, rows)
    slice_of = {d.qid: d.slice for d in ds}
    bad_empty = [q for q in s["empty_queries"] if slice_of[q] != OUT_OF_CATALOG_SLICE]
    if bad_empty and not allow_empty:
        _fail(f"câu thường không có ứng viên nào (filter quá chặt?): {', '.join(bad_empty)} — sửa drafts hoặc --allow-empty", 1)
    write_pool_csv(rows, out_p)
    build = PoolBuild(snapshot=snapshot_of(stats, ctx.dataset), collection=logical, depth=depth or cfg.gold.pool_depth,
                      seed=cfg.run.seed, qid_mode=qid_mode, drafts_sha256=file_sha256(drafts_p),
                      pool_sha256=file_sha256(out_p), qids=[d.qid for d in ds], empty_qids=s["empty_queries"],
                      slice_filter=slice_, created_at=datetime.now().astimezone().replace(microsecond=0))
    write_pool_build(build, pool_build_path(out_p))
    typer.echo(f"{out_p}: {s['n_queries']} query · {s['n_rows']} dòng · doc/query p50 {s['docs_per_query']['p50']:.0f} "
               f"max {s['docs_per_query']['max']} · from {s['from']} · collection {logical} · snapshot {build.snapshot}")
    typer.echo(f"  query embed: mới {emb.n_new} · từ cache {emb.n_cached}")
    if s["empty_queries"]:
        typer.secho(f"  query không có ứng viên: {s['empty_queries']}", fg=typer.colors.YELLOW)


@gold_app.command("split")
def gold_split(c: typer.Context,
               pool: Optional[Path] = typer.Option(None, "--pool", help="mặc định gold/pool.csv"),
               overlap: Optional[int] = typer.Option(None, "--overlap", min=0, help="mặc định gold.overlap_queries"),
               out_dir: Optional[Path] = typer.Option(None, "--out-dir", help="mặc định gold/"),
               force: bool = typer.Option(False, "--force", help="ghi đè pool_meta.json dù đã có file nhãn")):
    """pool.csv → pool_A.csv, pool_B.csv (câu chung phân tầng theo slice, còn lại xen kẽ A/B trong từng slice, mỗi người
    một thứ tự xáo) + pool_meta.json. Mã thoát: 0 · 2 lỗi đầu vào / pool lệch sha."""
    from . import paths
    from .gold import GoldError, pool_build_path, read_pool_build, split_pool, write_split
    from .gold_schema import SchemaError, file_sha256, read_pool_csv
    cfg = _ctx(c).cfg()
    pool_p = pool or paths.GOLD_DIR / "pool.csv"
    d = out_dir or paths.GOLD_DIR
    try:
        if not pool_p.exists():
            raise GoldError(f"không thấy {pool_p} — chạy `sb gold pool` trước")
        build = read_pool_build(pool_build_path(pool_p))
        if file_sha256(pool_p) != build.pool_sha256:
            raise GoldError(f"{pool_p.name} đã đổi sau khi `sb gold pool` ghi (sha khác {pool_build_path(pool_p).name})")
        rows = read_pool_csv(pool_p)
        a, b, shared = split_pool(rows, cfg.gold.overlap_queries if overlap is None else overlap, build.seed)
        meta = write_split(a, b, shared, build, d, force=force)
    except (GoldError, SchemaError) as e:
        _fail(str(e), 2)
    if build.slice_filter:
        typer.secho(f"  pool chỉ gồm slice {build.slice_filter} — không dùng làm gold thật", fg=typer.colors.YELLOW)
    fa, fb = meta.files["A"], meta.files["B"]
    typer.echo(f"pool_A.csv: {fa.n_queries} query / {fa.n_pairs} dòng · pool_B.csv: {fb.n_queries} query / {fb.n_pairs} dòng · "
               f"chung {len(shared)}: {', '.join(shared)}")
    typer.echo(f"{d / 'pool_meta.json'}: snapshot {meta.snapshot} · {meta.collection} · depth {meta.depth} · seed {meta.seed}")


@contextmanager
def _gold_errors():
    """Nhóm lệnh gold: RuleViolation → exit 1 (in từng lỗi); lỗi đầu vào → exit 2."""
    from pydantic import ValidationError

    from .gold import GoldError, RuleViolation
    from .gold_schema import SchemaError
    try:
        yield
    except RuleViolation as e:
        for p in e.problems[:60]:
            typer.secho(f"  ✗ {p}", fg=typer.colors.RED, err=True)
        if len(e.problems) > 60:
            typer.secho(f"  … và {len(e.problems) - 60} lỗi nữa", fg=typer.colors.RED, err=True)
        _fail(f"{e.title}: {len(e.problems)} vi phạm", 1)
    except (GoldError, SchemaError, ValidationError, OSError) as e:
        _fail(str(e), 2)


def _meta_path(meta: Optional[Path]) -> Path:
    from . import paths
    return meta or paths.GOLD_DIR / "pool_meta.json"


@gold_app.command("kappa")
def gold_kappa(c: typer.Context,
               labels_a: Path = typer.Argument(..., help="gold/labels/labels_A.csv"),
               labels_b: Path = typer.Argument(..., help="gold/labels/labels_B.csv"),
               meta: Optional[Path] = typer.Option(None, "--meta", help="mặc định gold/pool_meta.json"),
               kmin: Optional[float] = typer.Option(None, "--min", help="mặc định gold.kappa_min")):
    """Cohen κ trên các câu chung: ma trận nhầm (A theo hàng), κ linear (quyết định), không trọng số, quadratic, các cặp
    lệch 2 bậc. Mã thoát: 0 đạt · 1 thiếu nhãn / κ < min · 2 lỗi đầu vào."""
    from .gold import RuleViolation, cohen_kappa, load_labels, load_pool_set, overlap_pairs
    threshold = _ctx(c).cfg().gold.kappa_min if kmin is None else kmin
    with _gold_errors():
        ps = load_pool_set(_meta_path(meta))
        la, lb = load_labels(labels_a, "A", ps), load_labels(labels_b, "B", ps)
        pairs, missing = overlap_pairs(ps, la, lb)
        if missing:
            raise RuleViolation("kappa: câu chung còn thiếu nhãn", missing)
        k = cohen_kappa([(a, b) for _, a, b in pairs])
    typer.echo(f"{k.n} cặp chung ({len(ps.meta.overlap_qids)} câu) · ma trận nhầm (A hàng × B cột, nhãn 0/1/2):")
    for i, row in enumerate(k.confusion):
        typer.echo(f"  A={i}: " + "  ".join(f"{v:>4}" for v in row))
    fmt = lambda v: "không xác định" if v is None else f"{v:.6f}"          # noqa: E731
    typer.echo(f"κ linear {fmt(k.linear)} (quyết định, ngưỡng {threshold}) · không trọng số {fmt(k.unweighted)} · "
               f"quadratic {fmt(k.quadratic)}")
    gap2 = [(key, a, b) for key, a, b in pairs if abs(a - b) == 2]
    for (q, p), a, b in gap2:
        r = ps.row((q, p))
        typer.echo(f"  lệch 2 bậc: {q}/{p} A={a} B={b} · {r.query} → {r.name}")
    if k.linear is None or k.linear < threshold:
        _fail(f"κ linear {fmt(k.linear)} < {threshold} — sửa gold-guide, gán lại câu chung", 1)


@gold_app.command("merge")
def gold_merge(c: typer.Context,
               labels_a: Path = typer.Argument(..., help="gold/labels/labels_A.csv"),
               labels_b: Path = typer.Argument(..., help="gold/labels/labels_B.csv"),
               out: Optional[Path] = typer.Option(None, "-o", "--out", help="mặc định gold/labels/merged.csv"),
               meta: Optional[Path] = typer.Option(None, "--meta", help="mặc định gold/pool_meta.json")):
    """Hoà nhãn hai người → merged.csv: lệch 1 bậc lấy nhãn thấp; lệch 2 bậc → needs_discussion; hạng phòng lấy phần giao.
    Mã thoát: 0 (kể cả khi còn needs_discussion) · 1 thiếu / thừa / sai nhãn · 2 lỗi đầu vào."""
    from . import paths
    from .gold import load_labels, load_pool_set, merge_labels
    from .gold_schema import write_merged_csv
    out_p = out or paths.GOLD_DIR / "labels" / "merged.csv"
    with _gold_errors():
        ps = load_pool_set(_meta_path(meta))
        merged = merge_labels(ps, load_labels(labels_a, "A", ps), load_labels(labels_b, "B", ps))
        write_merged_csv(merged, out_p)
    nd = [m for m in merged if m.needs_discussion]
    src = dict(sorted(Counter(m.source for m in merged).items()))
    typer.echo(f"{out_p}: {len(merged)} cặp · nguồn {src} · needs_discussion {len(nd)}")
    for m in nd:
        typer.echo(f"  cần thảo luận: {m.qid}/{m.product_id} A={m.label_A} B={m.label_B} · {m.note}")
    if nd:
        typer.secho("  sửa các dòng trên trong merged.csv (điền label, needs_discussion=false, ghi lý do) rồi `sb gold import`",
                    fg=typer.colors.YELLOW)


@gold_app.command("import")
def gold_import(c: typer.Context,
                merged: Path = typer.Argument(..., help="gold/labels/merged.csv đã thảo luận xong"),
                meta: Optional[Path] = typer.Option(None, "--meta", help="mặc định gold/pool_meta.json"),
                catalog_p: Optional[Path] = typer.Option(None, "--catalog", help="products.jsonl của snapshot (mặc định "
                                                                                  "catalog.products_path)"),
                out: Optional[Path] = typer.Option(None, "-o", "--out", help="mặc định gold/gold.jsonl"),
                provenance: str = typer.Option("pool@gold_v1", "--provenance"),
                overwrite: bool = typer.Option(False, "--overwrite", help="ghi đè gold.jsonl khác nội dung (chỉ trước tag)")):
    """merged.csv → gold.jsonl (GoldRecord). Từ chối nếu còn needs_discussion, thiếu / thừa cặp, id lạ với catalog, nhãn
    sai luật (exit 1) hoặc sha pool lệch meta, file thiếu / sai định dạng (exit 2)."""
    from . import paths
    from .catalog import CatalogError, _jsonl_path
    from .gold import GoldError, build_gold, load_pool_set, read_catalog_parents, write_gold_checked
    from .gold_schema import read_merged_csv
    out_p = out or paths.GOLD_DIR / "gold.jsonl"
    with _gold_errors():
        ps = load_pool_set(_meta_path(meta))
        try:
            cat = catalog_p or _jsonl_path(_ctx(c).cfg())
        except CatalogError as e:
            raise GoldError(str(e)) from None
        if ps.meta.snapshot not in str(cat):
            typer.secho(f"  cảnh báo: pool dựng từ snapshot {ps.meta.snapshot}, catalog đang kiểm là {cat}",
                        fg=typer.colors.YELLOW)
        records = build_gold(ps, read_merged_csv(merged), read_catalog_parents(cat), provenance)
        changed = write_gold_checked(records, out_p, overwrite=overwrite)
    n = sum(len(r.judgments) for r in records)
    typer.echo(f"{out_p}: {len(records)} câu · {n} nhãn · provenance {provenance}" + ("" if changed else " (không đổi)"))
    typer.echo("  tiếp: `sb gold check`")


@gold_app.command("check")
def gold_check(c: typer.Context,
               gold_p: Optional[Path] = typer.Argument(None, help="mặc định gold/gold.jsonl"),
               min_per_slice: Optional[int] = typer.Option(None, "--min-per-slice", min=1,
                                                           help="mặc định gold.min_per_slice")):
    """Luật gold trên câu active: câu thường có nhãn 2 · out_of_catalog không có nhãn 2 và có expected_no_result ·
    parent_child nhãn 2 có expected_children · mỗi slice ≥ N câu. Mã thoát: 0 xanh · 1 đỏ · 2 lỗi đầu vào."""
    from . import paths
    from .gold import GoldError, check_gold
    from .gold_schema import read_gold_jsonl
    cfg = _ctx(c).cfg()
    p = gold_p or paths.GOLD_DIR / "gold.jsonl"
    n_min = cfg.gold.min_per_slice if min_per_slice is None else min_per_slice
    with _gold_errors():
        if not p.exists():
            raise GoldError(f"không thấy {p} — chạy `sb gold import` trước")
        rep = check_gold(read_gold_jsonl(p), n_min, list(cfg.gold.slices))
    typer.echo(f"{'slice':22} {'câu':>5} {'nhãn 0':>7} {'nhãn 1':>7} {'nhãn 2':>7}")
    for s in sorted(rep.n_queries):
        cn = rep.per_slice.get(s, Counter())
        typer.echo(f"{s:22} {rep.n_queries[s]:>5} {cn[0]:>7} {cn[1]:>7} {cn[2]:>7}")
    for w in rep.warnings:
        typer.secho(f"  cảnh báo: {w}", fg=typer.colors.YELLOW)
    if rep.problems:
        for pr in rep.problems:
            typer.secho(f"  ✗ {pr}", fg=typer.colors.RED, err=True)
        _fail(f"gold check đỏ: {len(rep.problems)} lỗi (min_per_slice = {n_min})", 1)
    typer.secho(f"gold check xanh ({sum(rep.n_queries.values())} câu, min_per_slice = {n_min}) — chốt bằng: git tag gold_v1 "
                "(lần thêm sau: gold_vN+1, spec Part 11)", fg=typer.colors.GREEN)


# ------------------------------------------------------------------ chi phí API
@app.command()
def cost():
    """Tổng lượt gọi / text / token / USD theo endpoint × model × input_type (cache/cost.jsonl)."""
    from rich.table import Table
    from .costlog import summarize
    rows = summarize()
    t = Table(title="cost.jsonl")
    for col in ("endpoint", "model", "input_type", "calls", "texts", "tokens", "usd"):
        t.add_column(col, justify="right" if col in ("calls", "texts", "tokens", "usd") else "left")
    for r in rows:
        t.add_row(r["endpoint"], r["model"], str(r["input_type"] or "-"), str(r["calls"]), str(r["texts"]),
                  str(r["tokens"]), f"{r['usd']:.6f}")
    t.add_row("[bold]tổng[/]", "", "", str(sum(r["calls"] for r in rows)), str(sum(r["texts"] for r in rows)),
              str(sum(r["tokens"] for r in rows)), f"{sum(r['usd'] for r in rows):.6f}")
    _console().print(t)


if __name__ == "__main__":
    app()
