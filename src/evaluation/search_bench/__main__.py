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
           model: str = typer.Option("cohere-v3", "--model", help="model Cohere có tokenizer, hoặc model local (hf_model)"),
           top: int = typer.Option(10, "--top", min=0, help="in N text dài nhất")):
    """Đếm token offline → p50/p90/p99/max; gate p99 ≤ token_p99_max, max < token_hard_max. Model Cohere: tokenizer tải một
    lần; model local (e5, bge-m3): tokenizer HF của model, đếm cả prefix `passage: `, hard max = max_seq_length."""
    import os
    from . import tokens as tk
    from .catalog import CatalogError
    from .textbuild import TextBuildError, VariantError, VariantNotImplemented, load_texts
    ctx = _ctx(c)
    cfg = ctx.cfg()
    try:
        mcfg = cfg.model_cfg(model)
        df, meta = load_texts(cfg, ctx.dataset, variant)
        if mcfg.hf_model:
            from .embed.local_hf import LocalHFEmbedder
            local = LocalHFEmbedder(model, mcfg)
            counts = local.count_tokens(df["text"].tolist(), "document")
            hard_max, note = local.max_seq_length, f"tính cả prefix {local.prefix['document']!r} và token đặc biệt; hard max = max_seq_length"
        else:
            if not mcfg.api_model:
                raise ValueError(f"model {model} không có api_model lẫn hf_model — không đếm token được")
            counter = tk.TokenCounter(tk.ensure_tokenizer(mcfg.api_model, os.environ.get("COHERE_API_KEY")))
            counts = counter.count(df["text"].tolist())
            hard_max, note = cfg.text.token_hard_max, "tính cả 2 token đặc biệt/text; Cohere tính tiền không gồm chúng"
    except (VariantError, VariantNotImplemented, ValueError) as e:
        _fail(str(e), 2)
    except (TextBuildError, CatalogError, tk.TokenizerUnavailable) as e:
        _fail(str(e))
    except Exception as e:  # noqa: BLE001 — tokenizer HF thiếu / lỗi tải
        _fail(f"không đếm được token của {model}: {type(e).__name__}: {str(e)[:200]}")
    st = tk.token_stats(counts)
    typer.echo(f"{meta['variant']} · {model}: n={st['n']} p50={st['p50']:.0f} p90={st['p90']:.0f} p99={st['p99']:.0f} max={st['max']}"
               f"  ({note})")
    over = sorted(((n, pid) for n, pid in zip(counts, df["product_id"]) if n > cfg.text.token_p99_max), reverse=True)
    if over:
        typer.echo(f"{len(over)} text > {cfg.text.token_p99_max} token:")
    for n, pid in (over or sorted(zip(counts, df["product_id"]), reverse=True))[:top]:
        typer.echo(f"  {n:4d}  {pid}")
    why = tk.gate(st, cfg.text.token_p99_max, hard_max)
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


# ------------------------------------------------------------------ Part 8: run --arm, compare
def _run_id_or_latest(ctx: Ctx) -> str:
    from .runner import RunnerError, latest_run_id
    if ctx.run_id:
        return ctx.run_id
    rid = latest_run_id()
    if rid is None:
        raise RunnerError("chưa có run nào trong bench_out/search/runs — chạy `sb run --arm …` trước, hoặc truyền --run-id")
    return rid


@app.command()
def run(c: typer.Context,
        arms: list[str] = typer.Option(..., "--arm", help="id arm (arms/<id>.yaml), lặp lại để chạy nhiều arm"),
        gold_p: Optional[Path] = typer.Option(None, "--gold", help="mặc định gold/gold.jsonl (phải khớp tag gold_v*)"),
        allow_untagged: bool = typer.Option(False, "--allow-untagged", help="gold trong gold/ chưa khớp tag nào: chỉ chạy "
                                                                            "thử — kết quả ghi gold_version null, không "
                                                                            "được trích dẫn / promote"),
        model: Optional[str] = typer.Option(None, "--model", help="ghi đè model của arm (vd fake) để thử khung"),
        force: bool = typer.Option(False, "--force", help="chạy lại dù đã có kết quả cùng cấu hình + gold_version")):
    """Chạy các arm trên gold (spec Part 8): truy xuất top-k từng câu → metric → runs/<run_id>/<arm>/results.json +
    per_query.parquet. run_id mặc định <YYYYMMDD-HHMM>-<git sha> (--run-id để ghi tiếp vào run cũ). Mã thoát: 0 ·
    1 lỗi truy xuất / embed · 2 arm, gold, catalog chưa sẵn sàng."""
    from rich.table import Table
    from . import runner as R
    from .arms import ArmError, load_arm
    from .catalog import CatalogError, read_stats
    from .embed import EmbedBatchError, EmbedderUnavailable, make_embedder
    from .gold import GoldError
    from .metrics import MetricsError
    from .store.weaviate_store import StoreError, collection_name
    ctx = _ctx(c)
    cfg = ctx.cfg()
    run_id = ctx.run_id or R.new_run_id()
    try:
        loaded = [load_arm(a) for a in arms]
        env = R.load_env(cfg, ctx.dataset, gold_p or paths_gold(), run_id=run_id, allow_untagged=allow_untagged)
        items_sha = read_stats(ctx.dataset)["items_sha256"]
        from .textbuild import text_inputs
        now = text_inputs(cfg, ctx.dataset)
    except (ArmError, R.RunnerError, GoldError, MetricsError, StoreError) as e:
        _fail(str(e), 2)
    except CatalogError as e:
        _fail(str(e))
    k = cfg.metrics.k
    con = _console()
    con.print(f"run [bold]{run_id}[/] · gold {env.gold_version or 'CHƯA TAG (chạy thử)'} · {len(env.gold)} câu active · "
              f"dataset {ctx.dataset} · {env.n_items} item", highlight=False)
    if env.gold_version is None:
        con.print("  cảnh báo: gold chưa khớp tag gold_v* — kết quả không được trích dẫn hay promote (spec §1.5)", style="yellow")
    app_ctx = None
    if any(a.engine == "app" for a in loaded):
        from .app_adapter import PRODUCT_BENCH, AppAdapterError, AppContext
        try:
            app_ctx = AppContext.open(cfg, ctx.dataset)          # dựng UnitIndex + nạp ProductBench nếu thiếu (0 Cohere)
        except (AppAdapterError, CatalogError) as e:
            _fail(f"cổng APP: {e}", 2)
        con.print(f"  cổng APP: SearchProducts thật · collection {PRODUCT_BENCH} ({len(app_ctx.cat.texts)} unit, hnsw)", highlight=False)
    with _store(cfg) as st:
        for a in loaded:
            m = model or a.model
            try:
                if a.engine == "app":
                    logical, phys = f"app:{app_ctx.collection}", app_ctx.collection
                else:
                    logical, phys = collection_name(a.text_variant, m, ctx.dataset)
            except StoreError as e:
                _fail(str(e), 2)
            a_eff = a.model_copy(update={"model": m}) if model else a      # --model ghi đè: hash + kết quả theo arm hiệu lực
            if not force:
                try:
                    prev = R.read_results(run_id, a.id)
                except R.RunnerError:
                    prev = None
                if prev and prev.get("resolved_config_hash") == R.config_hash(a_eff) and prev.get("gold_version") == env.gold_version:
                    con.print(f"[dim]{a.id}: đã có kết quả cùng cấu hình + gold_version trong run này — bỏ qua (--force để chạy lại)[/]")
                    continue

            def _emb(arm, _m=m, _phys=phys, _app=(a.engine == "app")):
                emb = make_embedder(cfg, _m, embedding_type=arm.embedding_types, preflight=False)
                from .app_adapter import MODEL_VERSION
                want = MODEL_VERSION.split(":")[0] if _app else st.description(_phys).get("cache_model")
                if emb.name != want:
                    emb.close()
                    raise StoreError(f"collection {_phys} nạp vector của {want}, query đang embed bằng {emb.name}")
                return emb
            try:
                desc = {"ascii_fold_mode": "shadow"} if a.engine == "app" else st.check_ready(phys, items_sha, now)
                results, rows = R.run_arm(env, a_eff, store=st, embedder_factory=_emb, physical=phys, collection=logical,
                                          fold_mode=desc["ascii_fold_mode"], app_ctx=app_ctx)
            except (R.RunnerError, MetricsError) as e:
                _fail(f"{a.id}: {e}", 2)
            except (EmbedderUnavailable, EmbedBatchError, *_weaviate_errors()) as e:
                _fail(f"{a.id}: {e}")
            o = results["overall"]
            t = Table(title=f"{a.id} · {logical} · gold {env.gold_version} · k={k}", show_lines=False)
            for col in ("slice", "n", f"recall@{k}", f"ndcg@{k}", f"mrr@{k}", f"judged@{k}", "zero_result"):
                t.add_column(col, justify="right" if col != "slice" else "left")

            def _f(v):
                return "-" if v is None else f"{v:.3f}"
            t.add_row("[bold]overall[/]", str(results["n_queries"]), _f(o[f"recall@{k}"]), _f(o[f"ndcg@{k}"]), _f(o[f"mrr@{k}"]),
                      _f(o[f"judged@{k}"]), f"in {_f(o['zero_result_in_catalog'])} / ooc {_f(o['zero_result_out_of_catalog'])}")
            for s, v in results["by_slice"].items():
                t.add_row(s, str(v["n"]), _f(v[f"recall@{k}"]), _f(v[f"ndcg@{k}"]), _f(v[f"mrr@{k}"]), _f(v[f"judged@{k}"]),
                          _f(v["zero_result"]))
            con.print(t)
            e = results.get("embed") or {}
            lat = results["latency_ms"]
            con.print(f"  constraint_precision {_f(o['constraint_precision'])} · parent_dup_rate {_f(o['parent_dup_rate'])} · "
                      f"weaviate p50/p95 {_f(lat['weaviate_p50'])}/{_f(lat['weaviate_p95'])} ms · query embed: mới {e.get('n_new', 0)} "
                      f"/ cache {e.get('n_cached', 0)} · hash {results['resolved_config_hash'][:8]}", highlight=False)
            if results.get("vs_parent") and "verdict" in results["vs_parent"]:
                vp = results["vs_parent"]
                con.print(f"  vs {a.parent}: {vp['verdict']} — {vp['reason']}", highlight=False)
            for w in results["needs_labels"]:
                con.print(f"  NEEDS_LABELS: {w}", style="yellow")
            if results["needs_labels"]:
                con.print("  → `sb gold holes --arms …` → gán → `holes import` → tag → `sb rescore` (Part 11)", style="yellow")
            con.print(f"  → {R.arm_dir(run_id, a.id, create=False)}", style="dim", highlight=False)
    if app_ctx is not None:
        app_ctx.close()


@app.command()
def sanity(c: typer.Context,
           arms: str = typer.Option("B0", "--arms", help="arm, cách nhau bằng phẩy — lấy model + collection của chúng"),
           gold_p: Optional[Path] = typer.Option(None, "--gold", help="mặc định gold/gold.jsonl (câu để embed thử)"),
           n_queries: Optional[int] = typer.Option(None, "--n-queries", help="số câu cho input_type check; mặc định min(200, active)")):
    """Kiểm tra cứng của pipeline (spec 12.2), chạy rời trước khi tin số của bất kỳ arm nào: input_type_vectors_differ,
    cache_recheck (tốn 1 lượt embed/model), collection_counts, gold_append_ok. Mã thoát: 0 PASS · 1 SANITY_FAIL · 2 lỗi đầu vào."""
    from rich.table import Table
    from . import paths, sanity as S
    from .arms import ArmError, load_arm
    from .catalog import CatalogError, read_stats
    from .embed import EmbedBatchError, EmbedderUnavailable, make_embedder
    from .metrics import MetricsError, load_gold
    from .store.weaviate_store import StoreError, collection_name
    ctx = _ctx(c)
    cfg = ctx.cfg()
    gp = gold_p or paths.GOLD_JSONL
    try:
        loaded = [load_arm(a.strip()) for a in arms.split(",") if a.strip()]
        texts = [g.text for g in load_gold(gp)] if gp.exists() else []
        n_items = read_stats(ctx.dataset)["n_search_units"]
    except (ArmError, MetricsError) as e:
        _fail(str(e), 2)
    except CatalogError as e:
        _fail(str(e))
    limit = n_queries or min(200, len(texts))
    sample = texts[:limit]
    pc = cfg.stages.pipeline_checks
    checks: list[S.Check] = []
    for m in sorted({a.model for a in loaded}):
        try:
            cached = make_embedder(cfg, m, preflight=False)
            fresh = make_embedder(cfg, m, no_cache=True, preflight=False)
            try:
                model_cfg = cfg.embedding.models[m]
                if model_cfg.input_type_mode == "symmetric":
                    checks.append(S.input_type_vectors_match(cached, sample, max_gap=1e-5, model=m))
                else:
                    checks.append(S.input_type_vectors_differ(cached, sample, min_gap=pc["input_type_min_cos_gap"], model=m))
                checks.append(S.cache_recheck(cached, fresh, texts, n=pc["cache_recheck_n"], seed=cfg.run.seed, model=m))
            finally:
                cached.close()
                fresh.close()
        except (EmbedderUnavailable, EmbedBatchError) as e:
            _fail(f"{m}: {e}")
    counts: dict[str, int] = {}
    with _store(cfg) as st:
        for a in loaded:
            phys = "ProductBench" if a.engine == "app" else collection_name(a.text_variant, a.model, ctx.dataset)[1]
            try:
                counts[phys] = st.count(phys) if st.exists(phys) else 0
            except (StoreError, *_weaviate_errors()) as e:
                _fail(f"{phys}: {e}")
    checks.append(S.collection_counts(counts, n_items))
    checks.append(S.gold_append_ok(gp))
    state, failed = S.summary(checks)
    t = Table(title=f"sanity · {', '.join(a.id for a in loaded)} · {len(sample)} câu · gold {gp.name}")
    for col in ("kiểm tra", "model", "kết quả", "chi tiết"):
        t.add_column(col)
    for ck in checks:
        res = "[green]PASS[/]" if ck.ok else ("[red]FAIL[/]" if ck.ok is False else "[yellow]bỏ qua[/]")
        t.add_row(ck.name, ck.model or "-", res, ck.detail)
    con = _console()
    con.print(t)
    if failed:
        _fail(f"SANITY_FAIL: {', '.join(ck.name for ck in failed)} — sửa pipeline trước khi đọc bất kỳ số nào (spec 12.2)", 1)
    con.print("[green]PASS[/]: kiểm tra cứng đạt", highlight=False)


@app.command("app-load")
def app_load(c: typer.Context, recreate: bool = typer.Option(False, "--recreate", help="xoá và nạp lại ProductBench")):
    """Cổng APP: dựng collection `ProductBench` (hình dạng production: WeaviateClient của backend, hnsw, nameAscii /
    searchTextAscii) trên Weaviate của bench và nạp vector B0 đã embed (`vec_T3+R_cohere-v3.npy`, 0 Cohere). Đủ và đúng
    textHash thì không làm gì. `sb run --arm APP.*` tự gọi bước này."""
    from .app_adapter import PRODUCT_BENCH, AppAdapterError, build_app_catalog, load_product_bench
    from .catalog import CatalogError
    ctx = _ctx(c)
    cfg = ctx.cfg()
    try:
        cat = build_app_catalog(cfg, ctx.dataset)
        s = load_product_bench(cfg, ctx.dataset, cat, recreate=recreate)
    except (AppAdapterError, CatalogError) as e:
        _fail(str(e), 2)
    except Exception as e:  # noqa: BLE001 — lỗi Weaviate / vector
        _fail(f"{type(e).__name__}: {str(e)[:300]}")
    typer.echo(f"{PRODUCT_BENCH}: {s['n']} object · khớp textHash {s['matching']} · thiếu {s['missing']} · text cũ {s['stale']} · "
               f"nạp mới {s['loaded']} · index hnsw (backend không nhận flat) · {len(cat.index.units)} unit, "
               f"{int(cat.index.available.sum())} available")


def paths_gold() -> Path:
    from . import paths
    return paths.GOLD_JSONL


@app.command()
def compare(c: typer.Context, arm_a: str = typer.Argument(..., help="arm mốc (A)"), arm_b: str = typer.Argument(..., help="arm so (B)"),
            gold_version: Optional[str] = typer.Option(None, "--gold", help="gold_vN; mặc định bản mới nhất có ở cả hai arm"),
            condensed: bool = typer.Option(False, "--condensed", help="Bỏ kết quả chưa nhãn rồi dồn hạng; vẫn báo coverage full")):
    """So hai arm trong cùng run (--run-id; mặc định run mới nhất): paired bootstrap Δrecall / Δndcg, Δ theo slice và kết luận
    win_rule (WIN / TIE / LOSE — spec Part 8). Hai arm phải cùng gold_version. Mã thoát: 0 · 1 khác gold_version · 2 thiếu kết quả."""
    from rich.table import Table
    from . import runner as R
    ctx = _ctx(c)
    cfg = ctx.cfg()
    k = cfg.metrics.k
    try:
        run_id = _run_id_or_latest(ctx)
        versions_a = R.available_versions(run_id, arm_a)
        versions_b = R.available_versions(run_id, arm_b)
        if not versions_a or not versions_b:
            missing = arm_a if not versions_a else arm_b
            raise R.RunnerError(f"chưa có kết quả {missing} trong run {run_id} — chạy `sb run --arm {missing}` trước")
        if gold_version is None:
            common = set(versions_a) & set(versions_b)
            if not common:
                raise R.RunnerError(f"{arm_a} và {arm_b} không có chung gold_version — chạy sb rescore cho cả hai")
            selected = max(common, key=R._version_key)
        else:
            selected = gold_version
        ra, rows_a, _ = R.read_results_at(run_id, arm_a, selected)
        rb, rows_b, _ = R.read_results_at(run_id, arm_b, selected)
    except R.RunnerError as e:
        _fail(str(e), 2)
    if condensed and (not ra.get("condensed") or not rb.get("condensed")):
        _fail("artifact chưa có condensed metrics; chạy sb rescore bằng code hiện tại", 2)
    cmp = R.compare(rows_a, rows_b, cfg, condensed=condensed)
    aa = ra["condensed"] if condensed else ra
    bb = rb["condensed"] if condensed else rb
    con = _console()

    def _f(v):
        return "-" if v is None else f"{v:.3f}"
    mode = "condensed" if condensed else "full"
    t = Table(title=f"run {run_id} · gold {ra.get('gold_version')} · {mode} · {arm_a} → {arm_b} (Δ = B − A, điểm %)")
    for col in ("metric", arm_a, arm_b, "Δ", "CI95", "p (một phía)"):
        t.add_column(col, justify="left" if col == "metric" else "right")
    for mname in (f"recall@{k}", f"ndcg@{k}"):
        b = cmp[mname]
        t.add_row(mname, _f(aa["overall"][mname]), _f(bb["overall"][mname]), "-" if b["delta"] is None else f"{b['delta']:+.2f}",
                  "-" if b["ci95"][0] is None else f"[{b['ci95'][0]:+.2f}, {b['ci95'][1]:+.2f}]",
                  "-" if b["p_one_sided"] is None else f"{b['p_one_sided']:.3f} (n={b['n']})")
    for mname in (f"mrr@{k}", f"judged@{k}", "constraint_precision", "zero_result_in_catalog", "zero_result_out_of_catalog"):
        t.add_row(mname, _f(aa["overall"].get(mname)), _f(bb["overall"].get(mname)), "", "", "")
    if condensed:
        t.add_row(f"full judged@{k}", _f(ra["overall"].get(f"judged@{k}")), _f(rb["overall"].get(f"judged@{k}")), "", "", "")
        t.add_row("retained ratio", _f(aa["coverage"].get("retained_ratio")), _f(bb["coverage"].get("retained_ratio")), "", "", "")
    con.print(t)
    ts = Table(title=f"theo slice: ndcg@{k} (Δ điểm %) · judged@{k}")
    for col in ("slice", "n", f"{arm_a} ndcg", f"{arm_b} ndcg", "Δ ndcg", f"{arm_a} judged", f"{arm_b} judged"):
        ts.add_column(col, justify="left" if col == "slice" else "right")
    for s in sorted(set(aa["by_slice"]) | set(bb["by_slice"])):
        va, vb = aa["by_slice"].get(s, {}), bb["by_slice"].get(s, {})
        full_va, full_vb = ra["by_slice"].get(s, {}), rb["by_slice"].get(s, {})
        d = cmp["slice_delta_ndcg"].get(s)
        ts.add_row(s, str(va.get("n", vb.get("n", "-"))), _f(va.get(f"ndcg@{k}")), _f(vb.get(f"ndcg@{k}")),
                   "-" if d is None else f"{d:+.2f}", _f(full_va.get(f"judged@{k}")), _f(full_vb.get(f"judged@{k}")))
    con.print(ts)
    style = {"WIN": "green", "TIE": "yellow", "LOSE": "red"}[cmp["verdict"]]
    con.print(f"[{style}]{cmp['verdict']}[/]: {cmp['reason']}", highlight=False)
    low = [a for a, r in ((arm_a, ra), (arm_b, rb)) if r.get("needs_labels")]
    if low:
        con.print(f"  cảnh báo: {', '.join(low)} chưa đạt judged@{k} (NEEDS_LABELS) — đọc condensed cùng coverage", style="yellow")
    if condensed:
        con.print("  condensed chỉ chấm kết quả đã có nhãn; đọc cùng full judged và retained ratio ở trên", style="yellow")


# ------------------------------------------------------------------ Part 5 (ngày 2: pool, split)
# ------------------------------------------------------------------ Part 9 (30/09): latency http, parity
latency_app = typer.Typer(no_args_is_help=True, help="Part 9: latency đường nóng — `http` đo /search thật qua HTTP "
                                                     "(embed / e2e / load chưa làm)")
app.add_typer(latency_app, name="latency")


def _open_section(section, key: str) -> dict:
    d = section.model_dump() if hasattr(section, "model_dump") else dict(section)
    if not d.get(key):
        _fail(f"config sbench.yaml thiếu latency.{key} (spec Part 9)", 2)
    return dict(d[key])


def _dsn_label(url: str) -> str:
    """host:port/db của một DSN — không bao giờ in user / mật khẩu."""
    from urllib.parse import urlparse
    u = urlparse(url)
    return f"{u.hostname or '?'}:{u.port or '?'}{u.path or ''}"


def _p(v):
    return "-" if v is None else f"{v:.0f}"


@latency_app.command("http")
def latency_http(c: typer.Context,
                 base_url: Optional[str] = typer.Option(None, "--base-url", envvar="SBENCH_CLOUD_BASE_URL",
                                                        help="gốc URL, vd https://v-ota.duckdns.org hoặc http://127.0.0.1:8000"),
                 queries: Optional[Path] = typer.Option(None, "--queries", help="mặc định config/latency_queries.yaml"),
                 runs: Optional[int] = typer.Option(None, "--runs", help="số lượt qua hết mọi câu (config latency.http.runs)"),
                 drop_first: Optional[bool] = typer.Option(None, "--drop-first/--keep-first",
                                                           help="bỏ lượt 1 khỏi p50/p95 (lượt 1 vẫn là nguồn mẫu miss)"),
                 limit: Optional[int] = typer.Option(None, "--limit"),
                 label: Optional[str] = typer.Option(None, "--label", help="vd cache-off / cache-on → latency-<label>.json")):
    """Đo `/search` thật qua HTTP (spec Part 9, 30/09): 25 câu prewarmed + 25 câu cold × runs lượt, tuần tự. Bảng p50/p95
    theo nhóm và theo stage (`diagnostics.stageMs`, contract 1.11.0), tách hit/miss theo `embedCache` (1.12.0); ghi
    runs/<run_id>/latency[-label].json. Mã thoát 1 khi không có mẫu 200 nào."""
    from rich.table import Table
    from . import latency as L, paths, runner as R
    ctx = _ctx(c)
    cfg = ctx.cfg()
    hc = _open_section(cfg.latency, "http")
    if not base_url:
        _fail("thiếu --base-url (hoặc SBENCH_CLOUD_BASE_URL trong .env)", 2)
    qp = queries or paths.PKG_DIR / str(hc["queries"])
    n_runs, lim = int(runs or hc["runs"]), int(limit or hc["limit"])
    df = bool(hc["drop_first"]) if drop_first is None else drop_first
    try:
        groups = L.load_queries(qp)
    except (L.LatencyError, OSError) as e:
        _fail(str(e), 2)
    run_id = ctx.run_id or R.new_run_id()
    con = _console()
    con.print(f"latency http · {base_url} · {len(groups['prewarmed'])} prewarmed + {len(groups['cold'])} cold · {n_runs} lượt · "
              f"limit {lim} · drop_first {df} · run {run_id}", highlight=False)
    samples = L.measure(base_url, groups, runs=n_runs, limit=lim, timeout_s=float(hc["timeout_s"]),
                        progress=lambda s: con.print(f"  [red]lỗi[/] lượt {s.run} «{s.text}»: {s.error}") if s.error else None)
    summary = L.summarize(samples, drop_first=df, percentiles=tuple(int(x) for x in hc.get("percentiles", [50, 95])))
    t = Table(title=f"/search · {base_url} · ms server (latencyMs, stageMs) · lượt {'≥ 2' if df and n_runs > 1 else 'mọi'}")
    for col in ("nhóm", "n", "latencyMs p50", "p95", "client p50", "p95", *(f"{st} p50/p95" for st in L.STAGES)):
        t.add_column(col, justify="left" if col == "nhóm" else "right")
    for g, d in summary["by_group"].items():
        st = d["stage_ms"]
        t.add_row(g, str(d["latency_ms"]["n"]), _p(d["latency_ms"]["p50"]), _p(d["latency_ms"]["p95"]),
                  _p(d["client_ms"]["p50"]), _p(d["client_ms"]["p95"]),
                  *(f"{_p(st[x]['p50'])}/{_p(st[x]['p95'])}" if x in st else "-" for x in L.STAGES))
    con.print(t)
    if summary["by_cache"]:
        t2 = Table(title="theo embedCache (miss = lần gặp đầu của câu, mọi lượt)")
        for col in ("cache", "n", "latencyMs p50", "p95", "embed p50", "p95", "client p50", "p95"):
            t2.add_column(col, justify="left" if col == "cache" else "right")
        for name, d in summary["by_cache"].items():
            t2.add_row(name, str(d["latency_ms"]["n"]), _p(d["latency_ms"]["p50"]), _p(d["latency_ms"]["p95"]),
                       _p(d["embed_ms"]["p50"]), _p(d["embed_ms"]["p95"]), _p(d["client_ms"]["p50"]), _p(d["client_ms"]["p95"]))
        con.print(t2)
    con.print(f"  mẫu {summary['n_ok']}/{summary['n_samples']} OK · searchMode {summary['search_modes'] or '-'} · embedCache "
              f"{summary['embed_cache_seen'] or 'không có (contract < 1.12.0)'} · top-10 giống nhau ở mọi lượt "
              f"{summary['top10_stable']}/{summary['top10_total']}", highlight=False)
    p = L.write_latency(run_id, base_url=base_url, queries_path=qp, samples=samples, summary=summary, label=label,
                        meta={"runs": n_runs, "limit": lim, "drop_first": df})
    con.print(f"  → {p}", style="dim", highlight=False)
    if summary["n_ok"] == 0:
        raise typer.Exit(1)


@latency_app.command("embed")
def latency_embed(c: typer.Context,
                  models: str = typer.Option(..., "--models", help="model IDs, cách nhau bằng dấu phẩy"),
                  gold_p: Optional[Path] = typer.Option(None, "--gold", help="mặc định gold/gold.jsonl"),
                  warmup: int = typer.Option(20, "--warmup", min=0, help="số query làm nóng, không tính vào p50/p95"),
                  delay_ms: float = typer.Option(0.0, "--delay-ms", min=0.0,
                                                 help="nghỉ giữa request, không tính vào latency; dùng để tránh rate limit API")):
    """Đo p50/p95 embed query từng model trên gold active, mỗi câu một request không qua cache."""
    import hashlib
    import json
    from . import latency as L, paths, runner as R
    from .embed import EmbedBatchError, EmbedderUnavailable, make_embedder
    from .metrics import MetricsError, load_gold
    from .holes import gold_version_of
    ctx = _ctx(c)
    cfg = ctx.cfg()
    gp = gold_p or paths.GOLD_JSONL
    names = list(dict.fromkeys(x.strip() for x in models.split(",") if x.strip()))
    if not names:
        _fail("--models cần ít nhất một model", 2)
    try:
        texts = [q.text for q in load_gold(gp)]
    except (OSError, MetricsError) as e:
        _fail(str(e), 2)
    run_id = ctx.run_id or R.new_run_id()
    rows = []
    for model in names:
        try:
            embedder = make_embedder(cfg, model, no_cache=True, preflight=False)
            try:
                result = L.measure_embed_queries(embedder, texts, warmup=warmup, delay_s=delay_ms / 1000.0)
                result.update(model=model, dim=cfg.model_cfg(model).dim, model_version=embedder.name)
            finally:
                embedder.close()
        except (EmbedderUnavailable, EmbedBatchError, L.LatencyError, ValueError) as e:
            _fail(f"{model}: {e}")
        rows.append(result)
        typer.echo(f"{model}: n={result['n']} warmup={result['warmup']} "
                   f"p50={result['p50_ms']:.1f} ms p95={result['p95_ms']:.1f} ms")
    path = paths.run_dir(run_id) / "latency-embed.json"
    gold_sha = hashlib.sha256(gp.read_bytes()).hexdigest()
    previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    if previous and (previous.get("gold_sha256") != gold_sha or previous.get("warmup") != warmup):
        _fail(f"{path}: gold/warmup khác phép đo cũ — dùng --run-id khác", 2)
    all_rows = {r["model"]: r for r in (previous or {}).get("models", [])}
    all_rows.update({r["model"]: r for r in rows})
    payload = {"run_id": run_id, "gold_path": str(gp), "gold_version": gold_version_of(gp),
               "gold_sha256": gold_sha, "warmup": warmup,
               "method": "sequential one query per uncached request; wall clock; no concurrent benchmark; inter-request delay excluded",
               "models": list(all_rows.values())}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    typer.echo(f"→ {path}")


@app.command()
def parity(c: typer.Context,
           mode: str = typer.Option("http", "--mode", help="http (A = /search Cloud, B = /search local) | weaviate "
                                                            "(cùng SearchProducts trên catalog VM: A = Product@Cloud, B = ProductVM@bench)"),
           base_a: Optional[str] = typer.Option(None, "--base-url-a", envvar="SBENCH_CLOUD_BASE_URL"),
           base_b: Optional[str] = typer.Option(None, "--base-url-b", envvar="SBENCH_LOCAL_BASE_URL"),
           queries: Optional[Path] = typer.Option(None, "--queries", help="mặc định config/parity_queries.yaml"),
           k: Optional[int] = typer.Option(None, "--k"),
           cloud_url: Optional[str] = typer.Option(None, "--cloud-weaviate-url", envvar="SBENCH_CLOUD_WEAVIATE_URL"),
           cloud_key: Optional[str] = typer.Option(None, "--cloud-weaviate-api-key", envvar="SBENCH_CLOUD_WEAVIATE_API_KEY",
                                                   show_default=False),
           database_url: Optional[str] = typer.Option(None, "--database-url", envvar="SBENCH_VM_DATABASE_URL", show_default=False,
                                                      help="DSN catalog VM (qua tunnel SSH); chỉ in host:port/db"),
           cloud_collection: str = typer.Option("Product", "--collection", help="collection trên Weaviate Cloud"),
           arm: str = typer.Option("APP.hybrid_norm", "--arm", help="arm APP quyết định tham số SearchProducts (mode weaviate)"),
           recreate: bool = typer.Option(False, "--recreate", help="mode weaviate: nạp lại ProductVM dù đã đủ")):
    """Parity Cloud vs local trên 20 câu cố định (spec Part 9, 30/09; lịch 10 ngày Day 2 C): top-1 trùng ≥ 18/20 và
    overlap@10 ≥ 8/10 ở mọi câu (config latency.parity). Ghi runs/<run_id>/parity-<mode>.json; mã thoát 1 khi không đạt."""
    from rich.table import Table
    from . import parity as P, paths, runner as R
    ctx = _ctx(c)
    cfg = ctx.cfg()
    pc = _open_section(cfg.latency, "parity")
    kk = int(k or pc["k"])
    try:
        qs = P.load_parity_queries(queries or paths.PKG_DIR / str(pc["queries"]))
    except (P.ParityError, OSError) as e:
        _fail(str(e), 2)
    run_id = ctx.run_id or R.new_run_id()
    con = _console()
    if mode == "http":
        if not base_a or not base_b:
            _fail("mode http cần --base-url-a và --base-url-b (SBENCH_CLOUD_BASE_URL / SBENCH_LOCAL_BASE_URL)", 2)
        con.print(f"parity http · A {base_a} · B {base_b} · {len(qs)} câu · k={kk}", highlight=False)
        rows = P.parity_http(base_a, base_b, qs, k=kk, timeout_s=float(_open_section(cfg.latency, "http")["timeout_s"]))
        meta = {"a": base_a, "b": base_b, "arm": None}
    elif mode == "weaviate":
        if not (cloud_url and cloud_key and database_url):
            _fail("mode weaviate cần --cloud-weaviate-url, --cloud-weaviate-api-key và --database-url "
                  "(SBENCH_CLOUD_WEAVIATE_URL / SBENCH_CLOUD_WEAVIATE_API_KEY / SBENCH_VM_DATABASE_URL)", 2)
        from .app_adapter import AppAdapterError, build_vm_catalog, parity_contexts
        from .arms import ArmError, load_arm
        from .embed import EmbedderUnavailable, make_embedder
        try:
            arm_o = load_arm(arm)
            if arm_o.engine != "app":
                _fail(f"{arm}: mode weaviate cần arm `engine: app`", 2)
            con.print(f"parity weaviate · catalog VM {_dsn_label(database_url)} · A {cloud_collection}@{_dsn_label(cloud_url)} · "
                      f"B {pc['vm_collection']}@{_dsn_label(cfg.weaviate.url)} · arm {arm} · {len(qs)} câu · k={kk}", highlight=False)
            cat = build_vm_catalog(database_url)
            a_ctx, b_ctx, stats = parity_contexts(cfg, cat, cloud_url=cloud_url, cloud_api_key=cloud_key,
                                                  cloud_collection=cloud_collection, vm_collection=str(pc["vm_collection"]),
                                                  recreate=recreate)
            con.print(f"  catalog VM {stats['vm_units']} unit · Cloud {stats['cloud_objects']} object · có vector {stats['with_vector']} · "
                      f"không vector {stats['without_vector']} · mồ côi {stats['orphans']} · thiếu BM25 {stats['missing_lexical']} · "
                      f"text cũ {stats['stale_text']} · nạp ProductVM {stats['vm_loaded']}", highlight=False)
            emb = make_embedder(cfg, arm_o.model, embedding_type=arm_o.embedding_types, preflight=False)
            try:
                sa, sb_ = a_ctx.make_search(arm_o.app, emb), b_ctx.make_search(arm_o.app, emb)
                rows = P.parity_engines(lambda q: sa.search(q, limit=kk), lambda q: sb_.search(q, limit=kk), qs)
            finally:
                emb.close()
                a_ctx.close()
                b_ctx.close()
        except (ArmError, AppAdapterError, EmbedderUnavailable, *_weaviate_errors()) as e:
            _fail(f"parity weaviate: {e}", 2)
        meta = {"a": f"{cloud_collection}@{_dsn_label(cloud_url)}", "b": f"{pc['vm_collection']}@bench", "arm": arm,
                "catalog": _dsn_label(database_url), "stats": stats}
    else:
        _fail("--mode phải là http hoặc weaviate", 2)
    res = P.verdict(rows, k=kk, top1_min=int(pc["top1_min"]), overlap_min=int(pc["overlap_min"]))
    t = Table(title=f"parity {mode} · top-1 trùng {res['top1_same']}/{res['n']} (cần ≥ {res['top1_min']}) · overlap@{kk} min "
                    f"{res['overlap_min_full']} trên {res['n_full']} câu đủ {res['overlap_min']} kết quả (cần ≥ {res['overlap_min']}); "
                    f"câu ngắn hơn phải trùng hết")
    for col in ("slice", "câu", "top-1", f"overlap@{kk}", "cần", "A top-1", "B top-1", "ghi chú"):
        t.add_column(col, justify="right" if col in ("top-1", f"overlap@{kk}", "cần") else "left")
    for r in rows:
        note = r.error or (f"A {r.a_diag.get('searchMode', '')} / B {r.b_diag.get('searchMode', '')}".strip() if mode == "http" else "")
        ok = r.error is None and r.overlap_ok(kk, int(pc["overlap_min"]))
        t.add_row(r.slice, r.text, "✓" if r.top1_same else "[red]✗[/]",
                  (str(r.overlap(kk)) if ok else f"[red]{r.overlap(kk)}[/]") if not r.error else "-",
                  str(r.overlap_need(kk, int(pc["overlap_min"]))) if not r.error else "-",
                  (r.a_ids or ["-"])[0], (r.b_ids or ["-"])[0], note)
    con.print(t)
    con.print(f"  {'[green]PASS[/]' if res['pass'] else '[red]FAIL[/]'} · lỗi {res['n_error']}", highlight=False)
    p = P.write_parity(run_id, mode=mode, rows=rows, result=res, meta=meta)
    con.print(f"  → {p}", style="dim", highlight=False)
    if not res["pass"]:
        raise typer.Exit(1)


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
    from .gold import (GoldError, apply_overrides, local_only_edits, read_draft_cases, read_overrides,
                       render_drafts_report, resolve_decisions, select_drafts, slices_below_min, write_drafts)
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
    local = local_only_edits(rows, cases, overrides)
    if local:
        typer.secho(f"  {len(local)} câu sửa chỉ có trong kho nhãn local (không commit) — `sb gold pool --qid case` và máy "
                    "khác không map được sang case_id. App: Bộ câu đã chọn → nút “Chép vào overrides.tsv”; hoặc thêm tay "
                    "dòng `case_id  NEEDS_EDIT  <đúng câu dưới>  (trống)  <note ghi nguồn>`:", fg=typer.colors.YELLOW)
        for r in local:
            typer.echo(f"      {r['case_id']} [{r['slice']}] ({r.get('annotator', '')}): {r['query']}")
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
               force: bool = typer.Option(False, "--force", help="ghi đè pool_meta.json dù đã có file nhãn"),
               show_shared: bool = typer.Option(False, "--show-shared",
                                                help="in qid các câu chung — chỉ dùng khi người chạy lệnh không gán nhãn")):
    """pool.csv → pool_A.csv, pool_B.csv + pool_meta.json. Câu chung phân tầng theo slice (slice ≥ 2 câu có ≥ 1 câu chung);
    câu riêng cân theo số cặp; mỗi người đi slice theo khối, B lệch nửa vòng, trong khối câu riêng xáo và câu chung rải
    đều (thứ tự không lộ câu chung, không gán cùng lúc); ứng viên xáo riêng từng người. Mặc định chỉ in số câu chung,
    không in qid (người chạy có thể là người gán). Mã thoát: 0 · 2 lỗi đầu vào / pool lệch sha."""
    from . import paths
    from .gold import GoldError, pool_build_path, read_pool_build, split_pool, split_report, write_split
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
    rep = split_report(a, b, shared)
    typer.echo(f"pool_A.csv: {fa.n_queries} query / {fa.n_pairs} dòng · pool_B.csv: {fb.n_queries} query / {fb.n_pairs} dòng · "
               f"chung {len(shared)} câu / {rep['overlap_pairs']} cặp · lệch số cặp A−B: {rep['delta_pairs']:+d}")
    typer.echo("  câu chung theo slice: " + ", ".join(f"{s} {v}" for s, v in rep["overlap_by_slice"].items()))
    if show_shared:
        typer.echo(f"  qid câu chung (--show-shared; đừng cho người gán xem): {', '.join(shared)}")
    else:
        typer.echo("  không in qid câu chung để người gán không biết câu nào được chấm κ (`--show-shared` nếu người "
                   "chạy lệnh không gán nhãn)")
    if rep["apart"]:
        typer.echo(f"  A bắt đầu ở slice {rep['first_slice']['A']}, B ở slice {rep['first_slice']['B']} — thứ tự câu của hai "
                   "người khác nhau có chủ đích (không gán cùng một câu chung cùng lúc)")
    else:
        typer.secho("  có slice chiếm quá nửa số câu (hoặc chỉ một slice): A và B không lệch nhau được nửa vòng, một số câu "
                    "chung có thể được hai người gán gần cùng lúc", fg=typer.colors.YELLOW)
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
                overwrite: bool = typer.Option(False, "--overwrite", help="ghi đè gold.jsonl khác nội dung (chỉ trước tag)"),
                version: Optional[str] = typer.Option(None, "--version", help="version ghi vào changelog; mặc định tag "
                                                                                "gold_v* mới nhất + 1 (chưa có tag: gold_v1)")):
    """merged.csv → gold.jsonl (GoldRecord) + một mục `changelog.yaml` cạnh file (Part 11). Từ chối nếu còn
    needs_discussion, thiếu / thừa cặp, id lạ với catalog, nhãn sai luật (exit 1) hoặc sha pool lệch meta, file thiếu /
    sai định dạng (exit 2)."""
    from . import paths
    from .catalog import CatalogError, _jsonl_path
    from .gold import GoldError, build_gold, load_pool_set, read_catalog_parents, write_gold_checked
    from .gold_schema import read_merged_csv
    from .holes import append_changelog, changelog_entry, list_gold_tags, next_version
    out_p = out or paths.GOLD_JSONL
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
        if changed:
            ver = version or next_version(list_gold_tags())
            append_changelog(changelog_entry(ver, "import", records, source=provenance, merged=str(merged.name),
                                             snapshot=ps.meta.snapshot), out_p.parent / paths.GOLD_CHANGELOG.name)
    n = sum(len(r.judgments) for r in records)
    typer.echo(f"{out_p}: {len(records)} câu · {n} nhãn · provenance {provenance}" + ("" if changed else " (không đổi)"))
    typer.echo("  tiếp: `sb gold check`")


@gold_app.command("retire")
def gold_retire(qid: str = typer.Argument(..., help="qid cần loại khỏi metric, vd c0463"),
                reason: str = typer.Option(..., "--reason", help="lý do, vd pool_miss: … / catalog đã có Sapa"),
                gold_p: Optional[Path] = typer.Option(None, "--gold", help="mặc định gold/gold.jsonl"),
                version: Optional[str] = typer.Option(None, "--version", help="version ghi vào changelog; mặc định tag "
                                                                                "gold_v* mới nhất + 1 (chưa có tag: gold_v1)")):
    """`status: active → retired` cho một câu (Part 11): câu không vào metric từ version này, nhãn đã gán giữ nguyên;
    ghi một mục vào changelog.yaml cạnh gold.jsonl. Trước tag gold_v1 dùng khi pool bỏ sót sản phẩm đúng (pool_miss).
    Mã thoát: 0 · 1 câu không có / đã retired · 2 lỗi đầu vào."""
    from . import paths
    from .gold import GoldError
    from .gold_schema import read_gold_jsonl
    from .holes import append_changelog, changelog_entry, list_gold_tags, next_version, retire, write_gold
    p = gold_p or paths.GOLD_JSONL
    with _gold_errors():
        if not p.exists():
            raise GoldError(f"không thấy {p} — chạy `sb gold import` trước")
        records = retire(read_gold_jsonl(p), qid)
        write_gold(records, p)
        ver = version or next_version(list_gold_tags())
        append_changelog(changelog_entry(ver, "retire", records, retired=[{"qid": qid, "reason": reason}]),
                         p.parent / paths.GOLD_CHANGELOG.name)
    active = sum(1 for r in records if r.status == "active")
    typer.echo(f"{p}: {qid} active → retired · còn {active}/{len(records)} câu active · changelog {ver}: {reason}")
    typer.echo("  tiếp: `sb gold check` rồi commit + `git tag " + ver + "` (nếu chưa tag version này)")


@gold_app.command("verify-append")
def gold_verify_append(old: str = typer.Argument(..., help="tag / commit (vd gold_v1) hoặc đường dẫn gold.jsonl cũ"),
                       new: Optional[str] = typer.Argument(None, help="tag / commit hoặc đường dẫn; mặc định gold/gold.jsonl "
                                                                       "đang có")):
    """Bản mới chỉ được THÊM so với bản cũ (Part 11): mọi qid cũ còn, nhãn cũ giữ nguyên giá trị và provenance, status chỉ
    đổi active → retired. Chạy trước mọi promote và trong CI. Mã thoát: 0 · 1 vi phạm · 2 lỗi đầu vào."""
    from . import paths
    from .gold import RuleViolation
    from .holes import gold_at, verify_append
    with _gold_errors():
        o = gold_at(old)
        n = gold_at(new or str(paths.GOLD_JSONL))
        problems = verify_append(o, n)
        if problems:
            raise RuleViolation(f"verify-append {old} → {new or 'gold.jsonl'}", problems)
    added_q = len({r.qid for r in n} - {r.qid for r in o})
    old_pairs = {(r.qid, p) for r in o for p in r.judgments}
    added_l = sum(1 for r in n for p in r.judgments if (r.qid, p) not in old_pairs)
    retired = sum(1 for r in n if r.status == "retired") - sum(1 for r in o if r.status == "retired")
    typer.secho(f"verify-append xanh: {old} → {new or 'gold.jsonl'} · +{added_q} câu · +{added_l} nhãn · "
                f"+{retired} retired", fg=typer.colors.GREEN)


holes_app = typer.Typer(no_args_is_help=False, invoke_without_command=True,
                        help="Part 11: cặp chưa nhãn lọt top-k của arm → thư mục gán; `import` đưa nhãn vào gold")
gold_app.add_typer(holes_app, name="holes")


@holes_app.callback()
def gold_holes(c: typer.Context,
               arms: Optional[str] = typer.Option(None, "--arms", help="danh sách arm, cách nhau bằng phẩy (vd B0,E2.e5)"),
               stage: Optional[str] = typer.Option(None, "--stage", help="cổng (Part 12) — chưa cài, dùng --arms"),
               tag: Optional[str] = typer.Option(None, "--tag", help="tên đợt, mặc định = --stage hoặc arm nối bằng +"),
               k: Optional[int] = typer.Option(None, "--k", help="mặc định holes.k"),
               cap: Optional[int] = typer.Option(None, "--cap", min=1,
                                                  help="giới hạn cặp người gán; round-robin theo slice/query"),
               split: bool = typer.Option(False, "--split", help="chia câu xen kẽ A/B (hai người gán, không câu chung)"),
               gold_p: Optional[Path] = typer.Option(None, "--gold", help="mặc định gold/gold.jsonl"),
               out_dir: Optional[Path] = typer.Option(None, "--out-dir", help="mặc định gold/holes/<gold_version>__<tag>/"),
               variant: str = typer.Option("T3+R", "--variant", help="text lấy snippet (B0)")):
    """Quét per_query của các arm trong run (--run-id, mặc định run mới nhất): cặp trong top-k chưa có nhãn → thư mục
    hole để gán (app: nhập pool_meta.json của thư mục đó). Câu out_of_catalog tự gán 0 (auto_ooc). Mã thoát: 0 ·
    1 không có hole · 2 lỗi đầu vào."""
    if c.invoked_subcommand:
        return
    from . import holes as H, paths, runner as R
    from .catalog import CatalogError, read_stats
    from .gold import GoldError, load_pool_view, snapshot_of
    from .gold_schema import read_gold_jsonl
    ctx = _ctx(c)
    cfg = ctx.cfg()
    if stage and not arms:
        _fail("--stage chưa cài (Part 12) — dùng --arms A,B", 2)
    if not arms:
        _fail("cần --arms A,B", 2)
    arm_ids = [a.strip() for a in arms.split(",") if a.strip()]
    tag_ = tag or stage or "+".join(arm_ids)
    p = gold_p or paths.GOLD_JSONL
    try:
        run_id = _run_id_or_latest(ctx)
        records = read_gold_jsonl(p) if p.exists() else _fail(f"không thấy {p}", 2)
        gv = H.gold_version_of(p) if p.resolve().parent == paths.GOLD_DIR.resolve() else f"fixture:{H.file_sha256(p)[:8]}"
        rows_by_arm = {a: R.read_rows(run_id, a) for a in arm_ids}
        collection = R.read_results(run_id, arm_ids[0]).get("collection") or ""
        view = load_pool_view(cfg, ctx.dataset, variant)
        snapshot = snapshot_of(read_stats(ctx.dataset), ctx.dataset)
    except (R.RunnerError, GoldError) as e:
        _fail(str(e), 2)
    except CatalogError as e:
        _fail(str(e))
    kk = k or cfg.holes.k
    to_label, auto = H.find_holes(records, rows_by_arm, kk)
    n_uncapped = len(to_label)
    if cap is not None:
        to_label = H.cap_holes(to_label, records, cap, seed=cfg.run.seed)
    if not to_label and not auto:
        _fail(f"không có hole: mọi cặp top-{kk} của {', '.join(arm_ids)} đã có nhãn", 1)
    out = out_dir or paths.HOLES_DIR / f"{gv or 'untagged'}__{tag_}"
    with _gold_errors():
        s = H.write_holes(to_label, auto, records, view, out, seed=cfg.run.seed, split=split, snapshot=snapshot,
                          collection=collection, k=kk, run_id=run_id, arms=arm_ids, gold_version=gv, tag=tag_)
    typer.echo(f"{out}: {s['n_to_label']} cặp cần gán / {s['n_queries']} câu · {s['n_auto_ooc']} hole out_of_catalog tự gán 0 · "
               f"gold {gv} · run {run_id}")
    if cap is not None and n_uncapped > len(to_label):
        typer.echo(f"  cap: {n_uncapped} → {len(to_label)} cặp, round-robin theo slice/query")
    for x, f in s["files"].items():
        typer.echo(f"  pool_{x}.csv: {f['n_queries']} câu · {f['n_pairs']} cặp")
    typer.echo(f"  gán trong app (nhập {out / 'pool_meta.json'}), rồi: sb gold holes import {out}")


@holes_app.command("import")
def gold_holes_import(c: typer.Context,
                      holes_dir: Path = typer.Argument(..., help="thư mục do `sb gold holes` tạo (có labels/labels_X.csv)"),
                      gold_p: Optional[Path] = typer.Option(None, "--gold", help="mặc định gold/gold.jsonl"),
                      version: Optional[str] = typer.Option(None, "--version", help="mặc định tag gold_v* mới nhất + 1"),
                      partial: bool = typer.Option(False, "--partial", help="cho phép còn cặp chưa gán (chỉ thêm phần đã gán)")):
    """Thêm nhãn hole vào gold.jsonl (provenance holes:<tag>@<version>; hole out_of_catalog: auto_ooc). Từ chối cặp đã có
    nhãn (gold chỉ thêm), nhãn sai luật, thiếu nhãn (trừ --partial). In lệnh `git tag` cần chạy. Mã thoát: 0 · 1 · 2."""
    from . import holes as H, paths
    from .gold import GoldError
    from .gold_schema import read_gold_jsonl
    p = gold_p or paths.GOLD_JSONL
    with _gold_errors():
        if not p.exists():
            raise GoldError(f"không thấy {p}")
        s = H.read_holes_summary(holes_dir)
        ver = version or H.next_version(H.list_gold_tags())
        records, stats = H.import_holes(read_gold_jsonl(p), holes_dir, version=ver, tag=s["tag"], partial=partial)
        H.write_gold(records, p)
        H.append_changelog(H.changelog_entry(ver, "holes_import", records, tag=s["tag"], new_labels_by_source=stats,
                                             holes_dir=str(holes_dir.name), run_id=s.get("run_id"), arms=s.get("arms")),
                           p.parent / paths.GOLD_CHANGELOG.name)
    typer.echo(f"{p}: +{stats['human']} nhãn người · +{stats['auto_ooc']} auto_ooc · {stats['queries']} câu · version {ver}")
    typer.echo(f"  tiếp: `sb gold check` → `sb gold verify-append <tag cũ> {p}` → commit → `git tag {ver}` → `sb rescore`")


@app.command()
def rescore(c: typer.Context,
            arms: Optional[str] = typer.Option(None, "--arms", help="mặc định mọi arm trong run"),
            gold_p: Optional[Path] = typer.Option(None, "--gold", help="mặc định gold/gold.jsonl"),
            allow_untagged: bool = typer.Option(False, "--allow-untagged", help="gold chưa tag: chỉ chạy thử")):
    """Tính lại metric của các arm trong run (--run-id, mặc định run mới nhất) từ `top_ids` đã lưu trên gold hiện tại →
    `results@<gold_version>.json` + `per_query@<gold_version>.parquet`. Không gọi Weaviate / Cohere (Part 11)."""
    from . import paths, runner as R
    from .catalog import CatalogError
    from .gold import GoldError
    from .metrics import MetricsError
    ctx = _ctx(c)
    cfg = ctx.cfg()
    k = cfg.metrics.k
    try:
        run_id = _run_id_or_latest(ctx)
        env = R.load_env(cfg, ctx.dataset, gold_p or paths.GOLD_JSONL, run_id=run_id, allow_untagged=allow_untagged)
        arm_ids = [a.strip() for a in arms.split(",")] if arms else R.arms_in_run(run_id)
        if not arm_ids:
            raise R.RunnerError(f"run {run_id} không có arm nào")
    except (R.RunnerError, GoldError, MetricsError) as e:
        _fail(str(e), 2)
    except CatalogError as e:
        _fail(str(e))
    con = _console()
    con.print(f"rescore run [bold]{run_id}[/] → gold {env.gold_version or 'CHƯA TAG'} ({len(env.gold)} câu active)", highlight=False)
    for a in arm_ids:
        try:
            res, _, info = R.rescore_arm(env, run_id, a)
        except (R.RunnerError, MetricsError) as e:
            _fail(f"{a}: {e}", 2)
        o = res["overall"]
        miss = f" · {len(info['missing'])} câu mới chưa có trong run" if info["missing"] else ""
        con.print(f"  {a}: {res['rescored_from']} → {env.gold_version}: recall@{k} {o[f'recall@{k}']:.3f} · ndcg@{k} {o[f'ndcg@{k}']:.3f} · "
                  f"judged@{k} {o[f'judged@{k}']:.3f}{miss}" + ("  NEEDS_LABELS" if res["needs_labels"] else ""), highlight=False)


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


# ------------------------------------------------------------------ nhãn máy (máy gán phần còn lại, người duyệt trong app)
@gold_app.command("machine-import")
def gold_machine_import(files: list[Path] = typer.Argument(..., help="JSON: list {labeler, qid, product_id, label, "
                                                                       "children_ok, note}"),
                        model: str = typer.Option(..., "--model", help="ghi vào provenance, vd. claude-opus-5-5 (phiên)"),
                        meta: Optional[Path] = typer.Option(None, "--meta", help="mặc định gold/pool_meta.json"),
                        port: int = typer.Option(8502, "--port", help="cổng app dùng chung phải đang TẮT"),
                        dry_run: bool = typer.Option(False, "--dry-run", help="chỉ kiểm, không ghi")):
    """Nhãn máy → gold/labels/labels_<X>.csv + provenance_<X>.csv (source=machine, chưa duyệt). Chỉ ghi cặp còn trống
    (cặp người đã gán giữ nguyên), từ chối câu chung (dành cho người — κ). Chạy khi app dùng chung đã dừng: app và lệnh
    này là hai tiến trình, khoá ghi file của app không che được lệnh này. Mã thoát: 0 · 1 có dòng bị từ chối · 2 lỗi đầu vào."""
    import json
    import socket

    from . import labeling_core as L
    from . import paths
    meta_p = meta or paths.GOLD_DIR / "pool_meta.json"
    with socket.socket() as sock:
        sock.settimeout(0.5)
        if sock.connect_ex(("127.0.0.1", port)) == 0 and not dry_run:
            _fail(f"app đang nghe ở 127.0.0.1:{port} — dừng app dùng chung trước rồi chạy lại (tránh hai tiến trình cùng "
                  "ghi file nhãn)", 2)
    rows: list[dict] = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            _fail(f"{f}: {e}", 2)
        if not isinstance(data, list):
            _fail(f"{f}: cần một list", 2)
        rows += data
    keys = [(r.get("labeler"), r.get("qid"), r.get("product_id")) for r in rows]
    if len(keys) != len(set(keys)):
        _fail("trùng cặp (labeler, qid, product_id) giữa các file", 2)
    bad = [r for r in rows if r.get("labeler") not in ("A", "B") or r.get("label") not in (0, 1, 2)]
    if bad:
        _fail(f"{len(bad)} dòng sai labeler / label, vd. {bad[0]}", 2)
    rejected = 0
    for x in ("A", "B"):
        mine = [r for r in rows if r["labeler"] == x]
        if not mine:
            continue
        try:
            s = L.open_session(meta_p, x)
        except L.SessionError as e:
            _fail(str(e), 2)
        if dry_run:
            labels = L.load_labels(s)
            free = [r for r in mine if (r["qid"], r["product_id"]) not in labels]
            typer.echo(f"{x}: {len(mine)} dòng · {len(free)} cặp còn trống sẽ ghi · {len(mine) - len(free)} đã có nhãn người")
            continue
        res = L.import_machine_labels(s, mine, model=model)
        rejected += len(res["rejected"])
        typer.echo(f"{x}: ghi {len(res['written'])} nhãn máy · bỏ qua {len(res['skipped_labeled'])} cặp đã có nhãn người · "
                   f"từ chối {len(res['rejected'])}")
        for e in res["rejected"][:20]:
            typer.echo(f"   - {e}")
    if rejected:
        raise typer.Exit(1)


# ------------------------------------------------------------------ gán nhãn chung qua một link
SHARE_LAUNCHER = '''"""Launcher app gán nhãn dùng chung (sinh bởi `sb gold share`) — đặt NGOÀI repo git: Streamlit gửi thông tin git
(repo, nhánh, file chưa commit) và đường dẫn script cho mọi trình duyệt mở link, kể cả trước khi nhập mã."""
import os
import runpy
import sys

APP = os.environ["SBENCH_SHARE_APP"]
if os.path.dirname(APP) not in sys.path:
    sys.path.insert(0, os.path.dirname(APP))
runpy.run_path(APP, run_name="__main__")
'''
SHARE_SECRET_ENV = ("KEY", "TOKEN", "SECRET", "PASSWORD")


def _inside_git(p: Path) -> bool:
    return any((d / ".git").exists() for d in (p, *p.parents))


@gold_app.command("share")
def gold_share(port: int = typer.Option(8502, "--port", help="cổng trên 127.0.0.1 (cloudflared trỏ vào đây)"),
               launcher_dir: Optional[Path] = typer.Option(None, "--launcher-dir",
                                                           help="thư mục ngoài repo git; mặc định <ổ đĩa của repo>/vota-label-share"),
               codes: Optional[Path] = typer.Option(None, "--codes", help="mặc định bench_out/search/label_share/codes.env"),
               dry_run: bool = typer.Option(False, "--dry-run", help="chỉ chuẩn bị launcher + mã, in lệnh, không chạy")):
    """App gán nhãn dùng chung qua một link: mỗi người gán một mã truy cập (tạo lần đầu, lưu ở `codes.env` — gitignore),
    chỉ chế độ gán nhãn, nhãn ghi vào gold/labels/ của máy này. Chỉ nghe ở 127.0.0.1 — link công khai do
    `cloudflared tunnel --url http://127.0.0.1:<port>` tạo. Launcher đặt ngoài repo git để Streamlit không lộ repo /
    nhánh / file chưa commit; tiến trình không mang biến môi trường bí mật (*KEY*, *TOKEN*, *SECRET*, *PASSWORD*)."""
    import os
    import secrets
    import subprocess
    import sys

    from . import paths
    codes_p = codes or paths.sbench_home() / "label_share" / "codes.env"
    if not codes_p.exists():
        codes_p.parent.mkdir(parents=True, exist_ok=True)
        codes_p.write_text(f"LABELING_CODE_A={secrets.token_urlsafe(16)}\nLABELING_CODE_B={secrets.token_urlsafe(16)}\n",
                           encoding="utf-8")
        typer.echo(f"đã tạo mã truy cập mới: {codes_p}")
    kv = dict(ln.split("=", 1) for ln in codes_p.read_text(encoding="utf-8").split() if "=" in ln)
    if any(len(kv.get(f"LABELING_CODE_{x}", "")) < 12 for x in "AB") or kv.get("LABELING_CODE_A") == kv.get("LABELING_CODE_B"):
        _fail(f"{codes_p}: cần LABELING_CODE_A và LABELING_CODE_B khác nhau, mỗi mã ≥ 12 ký tự", 2)
    if not (paths.GOLD_DIR / "pool_meta.json").exists():
        _fail("chưa có gold/pool_meta.json — chạy `sb gold pool` và `sb gold split` trước", 2)
    ldir = (launcher_dir or Path(paths.repo_root().anchor) / "vota-label-share").resolve()
    if _inside_git(ldir):
        _fail(f"{ldir} nằm trong một repo git — chọn thư mục khác bằng --launcher-dir", 2)
    ldir.mkdir(parents=True, exist_ok=True)
    launcher = ldir / "app.py"
    launcher.write_text(SHARE_LAUNCHER, encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not any(t in k.upper() for t in SHARE_SECRET_ENV)}
    env.update(LABELING_SHARED="1", LABELING_CODE_A=kv["LABELING_CODE_A"], LABELING_CODE_B=kv["LABELING_CODE_B"],
               SBENCH_SHARE_APP=str(paths.PKG_DIR / "streamlit_app.py"), SBENCH_GOLD_DIR=str(paths.GOLD_DIR),
               PYTHONUTF8="1")
    cmd = [sys.executable, "-m", "streamlit", "run", str(launcher), "--server.address", "127.0.0.1",
           "--server.port", str(port), "--server.headless", "true", "--browser.gatherUsageStats", "false",
           "--client.showErrorDetails", "type", "--client.toolbarMode", "viewer", "--server.fileWatcherType", "none",
           "--server.runOnSave", "false",
           # app không có ô tải file: tắt hẳn /_stcore/upload_file (mở thì khách chưa có mã cũng đẩy được file vào RAM)
           "--server.maxUploadSize", "0"]
    typer.echo(f"launcher: {launcher} (ngoài repo git) · mã truy cập: {codes_p} · nhãn ghi vào: {paths.GOLD_DIR / 'labels'}")
    typer.echo(f"app dùng chung: http://127.0.0.1:{port} — link công khai: cloudflared tunnel --url http://127.0.0.1:{port}")
    if dry_run:
        typer.echo("--dry-run: " + " ".join(cmd[1:]))
        return
    raise typer.Exit(subprocess.call(cmd, cwd=str(ldir), env=env))


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
