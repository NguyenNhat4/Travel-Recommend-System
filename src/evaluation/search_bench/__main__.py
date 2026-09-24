"""CLI sbench (spec §1.3). Chạy từ `src/`: `python -m evaluation.search_bench <lệnh>` (trên Windows đặt PYTHONUTF8=1).

Mã thoát: 0 ok · 1 lỗi · 2 gate trượt / variant, arm chưa cài.
"""
from __future__ import annotations

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
        "builder_fingerprint": tmeta.get("builder_fingerprint"),
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
                            text_builder: str | None, builder_fingerprint: str | None) -> dict:
    from .catalog import read_stats
    from .store.weaviate_store import collection_name
    logical, _ = collection_name(variant, model, ctx.dataset)
    return {"logical_name": logical, "dataset": ctx.dataset, "variant": variant, "model": model, "cache_model": cache_model,
            "items_sha256": read_stats(ctx.dataset)["items_sha256"], "n": n, "text_builder": text_builder,
            "builder_fingerprint": builder_fingerprint}


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
                                   builder_fingerprint=tmeta.get("builder_fingerprint"))
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
    except (ArmError, StoreError) as e:
        _fail(str(e), 2)
    except CatalogError as e:
        _fail(str(e))
    with _store(cfg) as st:
        try:
            desc = st.check_ready(phys, items_sha)
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
gold_app = typer.Typer(no_args_is_help=True, help="Part 5: gold — pool, split (kappa/merge/import/check: ngày 3–4)")
app.add_typer(gold_app, name="gold")


@gold_app.command("drafts")
def gold_drafts(c: typer.Context,
                labels: Optional[Path] = typer.Option(None, "--labels", help="mặc định bench_out/search/labels/labels.jsonl"),
                raw: Optional[Path] = typer.Option(None, "--raw", help="mặc định gold/drafts_raw.tsv"),
                out: Optional[Path] = typer.Option(None, "--out", help="mặc định gold/drafts.txt"),
                dry_run: bool = typer.Option(False, "--dry-run", help="chỉ in báo cáo, không ghi file")):
    """Nhãn của app soát draft (KEEP/REJECT/NEEDS_EDIT) → gold/drafts.txt: giữ 1 cách nói mỗi ý định, cắt theo quota."""
    from . import paths
    from .gold import (GoldError, read_draft_cases, render_drafts_report, resolve_decisions, select_drafts,
                       write_drafts)
    from .labeling import JsonlLabelStore
    cfg = _ctx(c).cfg()
    labels_p = labels or paths.sbench_home() / "labels" / "labels.jsonl"
    raw_p = raw or paths.GOLD_DIR / "drafts_raw.tsv"
    out_p = out or paths.GOLD_DIR / "drafts.txt"
    if not labels_p.exists():
        _fail(f"không thấy kho nhãn {labels_p} — chạy app soát draft (streamlit_app.py) trước", 2)
    try:
        cases = read_draft_cases(raw_p)
        decisions, conflicts = resolve_decisions(JsonlLabelStore(labels_p).load_events())
        rows, report = select_drafts(cases, decisions, dict(cfg.gold.slices))
    except GoldError as e:
        _fail(str(e), 2)
    typer.echo(render_drafts_report(report))
    typer.echo(f"  nhãn: {len(decisions)}/{len(cases)} case đã gán · loại {sum(report['reject_reasons'].values())} "
               f"({report['reject_reasons']}) · gộp {len(report['dropped_duplicate'])} cách nói trùng ý định")
    if conflicts:
        typer.secho(f"  BẤT ĐỒNG giữa annotator, không chọn: {', '.join(conflicts)}", fg=typer.colors.YELLOW)
    for sl, ids in report["over_quota"].items():
        typer.secho(f"  {sl} thừa {len(ids)} ý định so với quota, bỏ: {', '.join(ids)}", fg=typer.colors.YELLOW)
    if dry_run:
        typer.echo("  --dry-run: không ghi file")
        return
    write_drafts(out_p, rows)
    typer.echo(f"{out_p}: {len(rows)} dòng")
    if report["selected"] < report["target"]:
        typer.secho(f"  chưa đủ {report['target']} — còn thiếu {report['target'] - report['selected']} ý định; "
                    f"`sb gold pool` vẫn chạy được nhưng gold sẽ mỏng hơn kế hoạch", fg=typer.colors.YELLOW)


@gold_app.command("pool")
def gold_pool(c: typer.Context,
              drafts: Optional[Path] = typer.Option(None, "--drafts", help="mặc định gold/drafts.txt của package"),
              depth: Optional[int] = typer.Option(None, "--depth", min=1, help="mặc định gold.pool_depth"),
              slice_: Optional[str] = typer.Option(None, "--slice", help="chỉ lấy draft của một slice"),
              out: Optional[Path] = typer.Option(None, "--out", help="mặc định gold/pool.csv của package"),
              arm: str = typer.Option("B0", "--arm", help="arm cung cấp collection + cách embed query")):
    """Dense top-depth ∪ BM25 top-depth (cùng filter của draft) trên collection của B0 → pool.csv, xáo trong mỗi qid."""
    from . import paths
    from .arms import ArmError, load_arm
    from .catalog import CatalogError, read_stats
    from .embed import EmbedBatchError, EmbedderUnavailable, make_embedder
    from .gold import GoldError, build_pool, load_key_index, parse_drafts, pool_summary, write_csv
    from .store.weaviate_store import StoreError, collection_name
    ctx = _ctx(c)
    cfg = ctx.cfg()
    drafts_p = drafts or paths.GOLD_DIR / "drafts.txt"
    out_p = out or paths.GOLD_DIR / "pool.csv"
    try:
        a = load_arm(arm)
        ds = parse_drafts(drafts_p, list(cfg.gold.slices), load_key_index(paths.data_dir(ctx.dataset) / paths.AMENITY_VOCAB))
        if slice_:
            ds = [d for d in ds if d.slice == slice_]
            if not ds:
                raise GoldError(f"không có draft nào thuộc slice {slice_}")
        logical, phys = collection_name(a.text_variant, a.model, ctx.dataset)
        items_sha = read_stats(ctx.dataset)["items_sha256"]
    except (ArmError, GoldError, StoreError) as e:
        _fail(str(e), 2)
    except CatalogError as e:
        _fail(str(e))
    with _store(cfg) as st:
        try:
            desc = st.check_ready(phys, items_sha)
            emb = make_embedder(cfg, a.model, embedding_type=a.embedding_types, preflight=False)
            try:
                if emb.name != desc.get("cache_model"):
                    raise StoreError(f"collection {phys} nạp vector của {desc.get('cache_model')}, query embed bằng {emb.name}")
                df = build_pool(ds, store=st, embedder=emb, physical=phys, fold_mode=desc["ascii_fold_mode"],
                                depth=depth or cfg.gold.pool_depth, query_input_type=a.query_input_type, seed=cfg.run.seed)
            finally:
                emb.close()
        except (EmbedderUnavailable, EmbedBatchError, *_weaviate_errors()) as e:
            _fail(str(e))
    write_csv(df, out_p)
    s = pool_summary(ds, df)
    typer.echo(f"{out_p}: {s['n_queries']} query · {s['n_rows']} dòng · doc/query p50 {s['docs_per_query']['p50']:.0f} "
               f"max {s['docs_per_query']['max']} · from {s['from']} · collection {logical}")
    typer.echo(f"  query embed: mới {emb.n_new} · từ cache {emb.n_cached}")
    if s["empty_queries"]:
        typer.secho(f"  query không có kết quả nào: {s['empty_queries']}", fg=typer.colors.YELLOW)


@gold_app.command("split")
def gold_split(c: typer.Context,
               pool: Optional[Path] = typer.Option(None, "--pool", help="mặc định gold/pool.csv"),
               overlap: Optional[int] = typer.Option(None, "--overlap", min=0, help="mặc định gold.overlap_queries"),
               out_dir: Optional[Path] = typer.Option(None, "--out-dir", help="mặc định gold/")):
    """pool_A.csv (qid lẻ + chung) và pool_B.csv (qid chẵn + chung); các qid chung chọn stratified theo slice."""
    from . import paths
    from .gold import GoldError, read_pool, split_pool, write_csv
    cfg = _ctx(c).cfg()
    try:
        df = read_pool(pool or paths.GOLD_DIR / "pool.csv")
        a, b, shared = split_pool(df, cfg.gold.overlap_queries if overlap is None else overlap, cfg.run.seed)
    except GoldError as e:
        _fail(str(e), 2)
    d = out_dir or paths.GOLD_DIR
    write_csv(a, d / "pool_A.csv")
    write_csv(b, d / "pool_B.csv")
    typer.echo(f"pool_A.csv: {a['qid'].nunique()} query / {len(a)} dòng · pool_B.csv: {b['qid'].nunique()} query / {len(b)} dòng · "
               f"chung {len(shared)}: {', '.join(shared)}")


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
