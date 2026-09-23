"""CLI sbench (spec §1.3). Chạy từ `src/`: `python -m evaluation.search_bench <lệnh>` (trên Windows đặt PYTHONUTF8=1).

Mã thoát: 0 ok · 1 lỗi · 2 gate trượt / variant, arm chưa cài.
"""
from __future__ import annotations

from dataclasses import dataclass, field
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
    from rich.console import Console
    from .catalog import CatalogError, build_catalog
    ctx = _ctx(c)
    try:
        stats = build_catalog(ctx.cfg(), source or ctx.dataset, allow_id_drift=allow_id_drift)
    except CatalogError as e:
        _fail(str(e))
    am = stats["amenity"]
    con = Console(soft_wrap=True)
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


# ------------------------------------------------------------------ chi phí API
@app.command()
def cost():
    """Tổng lượt gọi / text / token / USD theo endpoint × model × input_type (cache/cost.jsonl)."""
    from rich.console import Console
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
    Console().print(t)


if __name__ == "__main__":
    app()
