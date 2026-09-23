"""CLI vbench (spec §1.3). Chạy từ `src/`: `python -m evaluation.vector_bench <lệnh>`.

Mã thoát: 0 ok · 1 lỗi · 2 gate trượt / metric không đạt (khi lệnh có kiểm tra ngưỡng).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Optional

import typer

app = typer.Typer(add_completion=False, no_args_is_help=True, help="vbench — benchmark chọn vector database cho V-OTA")
engine_app = typer.Typer(no_args_is_help=True, help="Điều khiển container theo profile")
dataset_app = typer.Typer(no_args_is_help=True, help="Dựng dataset")
app.add_typer(engine_app, name="engine")
app.add_typer(dataset_app, name="dataset")


@dataclass
class Ctx:
    run_id: str
    config_path: Optional[str]
    profile: Optional[str]
    verbose: bool

    def cfg(self):
        from .config import load_config
        return load_config(self.config_path, self.profile)


def _ctx(c: typer.Context) -> Ctx:
    return c.obj


@app.callback()
def main(c: typer.Context,
         run: Optional[str] = typer.Option(None, "--run", help="RUN_ID (mặc định run.default_run_id)"),
         config: Optional[str] = typer.Option(None, "--config", help="đường dẫn vbench.yaml"),
         profile: Optional[str] = typer.Option(None, "--profile", help="local | full"),
         verbose: bool = typer.Option(False, "-v", "--verbose")):
    from .config import load_config
    from .results import setup_logging
    cfg = load_config(config, profile)
    run_id = run or cfg.run.default_run_id
    setup_logging(run_id, verbose)
    c.obj = Ctx(run_id=run_id, config_path=config, profile=profile, verbose=verbose)


def _exit(code: int) -> None:
    if code:
        raise typer.Exit(code)


# ------------------------------------------------------------------ Part 0
@app.command()
def doctor(c: typer.Context):
    """Kiểm tra môi trường, in bảng OK/WARN/FAIL."""
    from .doctor import print_checks, run_doctor
    _exit(print_checks(run_doctor(_ctx(c).cfg())))


@engine_app.command("up")
def engine_up(c: typer.Context, engine: str, timeout: float = typer.Option(300, help="giây chờ healthy")):
    from . import lifecycle
    cfg = _ctx(c).cfg()
    lifecycle.up(cfg, engine)
    s = lifecycle.wait_healthy(cfg, engine, timeout)
    typer.echo(f"{engine} healthy sau {s:.1f} s")


@engine_app.command("down")
def engine_down(c: typer.Context, engine: str, volumes: bool = typer.Option(False, "--volumes", help="xoá cả named volume của profile")):
    from . import lifecycle
    cfg = _ctx(c).cfg()
    lifecycle.down(cfg, engine, volumes=volumes)
    left = lifecycle.existing_volumes(engine)
    typer.echo(f"{engine} down" + (f"; volume còn lại: {left}" if left else ("; volume đã xoá" if volumes else "")))
    _exit(1 if (volumes and left) else 0)


@engine_app.command("restart")
def engine_restart(c: typer.Context, engine: str, timeout: float = typer.Option(300)):
    from . import lifecycle
    cfg = _ctx(c).cfg()
    lifecycle.restart(cfg, engine)
    typer.echo(f"{engine} healthy sau {lifecycle.wait_healthy(cfg, engine, timeout):.1f} s")


@engine_app.command("status")
def engine_status(c: typer.Context, engine: str):
    from rich.console import Console
    from rich.table import Table

    from . import lifecycle
    cfg = _ctx(c).cfg()
    cs = lifecycle.containers(engine)
    t = Table(title=f"engine {engine}")
    for col in ("container", "service", "image", "status"):
        t.add_column(col)
    for x in cs:
        t.add_row(x.name, x.service, x.image, x.status)
    Console().print(t)
    if not cs:
        typer.echo("không có container")
        _exit(1)
    healthy = lifecycle.is_healthy(cfg, engine)
    typer.echo(f"healthy: {healthy}")
    if healthy:
        for k, v in lifecycle.engine_versions(cfg, engine).items():
            typer.echo(f"{k}: {v}")
    vols = lifecycle.existing_volumes(engine)
    typer.echo(f"volume: {vols}")
    if healthy:
        try:
            st = lifecycle.stats(engine)
            typer.echo(f"RAM {st['mem_bytes'] / 2**30:.2f} GB · CPU {st['cpu_pct']:.1f}%")
        except Exception as e:  # noqa: BLE001
            typer.echo(f"docker stats lỗi: {e}")


# ------------------------------------------------------------------ Part 1
@dataset_app.command("catalog")
def dataset_catalog(c: typer.Context,
                    source: Optional[str] = typer.Option(None, "--source", help="jsonl | db | fake"),
                    products: Optional[str] = typer.Option(None, "--products", help="đường dẫn products.jsonl"),
                    n: Optional[int] = typer.Option(None, "--n", help="số search unit khi --source fake")):
    from .dataset.catalog import build_catalog
    build_catalog(_ctx(c).cfg(), source=source, products=products, n=n)


# ------------------------------------------------------------------ Part 2
@app.command()
def embed(c: typer.Context, scale: str = typer.Option("catalog", "--scale"),
          target: str = typer.Option("items", "--target", help="items | queries"),
          backend: Optional[str] = typer.Option(None, "--backend", help="st | fake")):
    from .embed import run_embed
    _exit(run_embed(_ctx(c).cfg(), scale=scale, target=target, backend=backend))


# ------------------------------------------------------------------ Part 3
@app.command()
def queries(c: typer.Context, scale: str = typer.Option("catalog", "--scale"),
            reuse_query_vectors: Optional[str] = typer.Option(None, "--reuse-query-vectors",
                                                              help="scale lấy query vector (fasttrack: catalog)")):
    from .querygen import run_queries
    _exit(run_queries(_ctx(c).cfg(), scale=scale, reuse_query_vectors=reuse_query_vectors))


# ------------------------------------------------------------------ Part 4
@app.command()
def gt(c: typer.Context, scale: str = typer.Option("catalog", "--scale")):
    from .groundtruth import run_gt
    _exit(run_gt(_ctx(c).cfg(), scale=scale))


# ------------------------------------------------------------------ Part 5
@app.command()
def load(c: typer.Context, engine: str, scale: str = typer.Option("catalog", "--scale"),
         index: Optional[str] = typer.Option(None, "--index", help="tên index config")):
    from .runners.load import run_load
    x = _ctx(c)
    _exit(run_load(x.cfg(), engine=engine, scale=scale, index_name=index, run_id=x.run_id))


@app.command()
def smoke(c: typer.Context, engine: str, scale: str = typer.Option("catalog", "--scale"),
          index: Optional[str] = typer.Option(None, "--index")):
    from .runners.smoke import run_smoke
    x = _ctx(c)
    _exit(run_smoke(x.cfg(), engine=engine, scale=scale, index_name=index, run_id=x.run_id))


# ------------------------------------------------------------------ Part 6 (lite)
@app.command()
def quality(c: typer.Context, engine: str, scale: str = typer.Option("catalog", "--scale"),
            only: str = typer.Option("A1,A3,A4", "--only", help="fast-track: A1,A3,A4(count)"),
            index: Optional[str] = typer.Option(None, "--index"),
            sweep: str = typer.Option("full", "--sweep", help="full = engines.<e>.query_sweep · fast = fast.query_sweep.<e>")):
    from .runners.quality import run_quality
    x = _ctx(c)
    _exit(run_quality(x.cfg(), engine=engine, scale=scale, run_id=x.run_id, only=only, index_name=index, sweep=sweep))


# ------------------------------------------------------------------ Part 9 (lite)
@app.command()
def gate(c: typer.Context, engine: str, only: str = typer.Option("g3", "--only"),
         scale: str = typer.Option("catalog", "--scale"), index: Optional[str] = typer.Option(None, "--index")):
    from .runners.gates import run_gates
    x = _ctx(c)
    _exit(run_gates(x.cfg(), engine=engine, run_id=x.run_id, only=only, scale=scale, index_name=index))


# ------------------------------------------------------------------ Part 10
@app.command("scale-data")
def scale_data(c: typer.Context, scale: str,
               vectors: Optional[str] = typer.Option(None, "--vectors", help="cohere-vi | fake | amplify"),
               correlation: Optional[str] = typer.Option(None, "--correlation", help="none | cluster")):
    from .dataset.scale import run_scale_data
    _exit(run_scale_data(_ctx(c).cfg(), scale=scale, vectors=vectors, correlation=correlation))


# ------------------------------------------------------------------ Part 11 (lite)
@app.command()
def perf(c: typer.Context, engine: str, scale: str = typer.Option("catalog", "--scale"),
         only: str = typer.Option("B1,B2,B3,C1", "--only"),
         rates: Optional[str] = typer.Option(None, "--rates", help="ví dụ 100,200 (mặc định perf.rates_qps)"),
         duration: Optional[float] = typer.Option(None, "--duration", help="giây mỗi mức (mặc định perf.duration_s)"),
         warmup: Optional[float] = typer.Option(None, "--warmup"),
         reps: Optional[int] = typer.Option(None, "--reps"),
         index: Optional[str] = typer.Option(None, "--index")):
    from .runners.perf import run_perf
    x = _ctx(c)
    rl = [float(r) for r in rates.split(",")] if rates else None
    _exit(run_perf(x.cfg(), engine=engine, scale=scale, run_id=x.run_id, only=only, rates=rl, duration_s=duration,
                   warmup_s=warmup, reps=reps, index_name=index))


# ------------------------------------------------------------------ fast-track
@app.command()
def fast(c: typer.Context, engines: Optional[str] = typer.Option(None, "--engines", help="mặc định fast.engines"),
         scales: Optional[str] = typer.Option(None, "--scales", help="mặc định fast.scales"),
         keep: bool = typer.Option(False, "--keep", help="không down --volumes sau mỗi engine"),
         perf_duration: Optional[float] = typer.Option(None, "--perf-duration", help="CHỈ để chạy thử: giây mỗi mức tải"),
         perf_warmup: Optional[float] = typer.Option(None, "--perf-warmup", help="CHỈ để chạy thử: giây warm-up")):
    """Điều phối fast-track (spec-fasttrack §4) có chặn thời gian mỗi engine."""
    from .runners.fast import run_fast
    x = _ctx(c)
    el = engines.split(",") if engines else None
    sl = scales.split(",") if scales else None
    _exit(run_fast(x.cfg(), run_id=x.run_id, engines=el, scales=sl, keep=keep, perf_duration=perf_duration,
                   perf_warmup=perf_warmup))


@app.command("fast-report")
def fast_report(c: typer.Context):
    """Bảng + quy tắc chốt §6 của spec-fasttrack → runs/<run>/fast_report.md."""
    from .fast_report import run_fast_report
    x = _ctx(c)
    _exit(run_fast_report(x.cfg(), run_id=x.run_id))


if __name__ == "__main__":
    sys.exit(app())
