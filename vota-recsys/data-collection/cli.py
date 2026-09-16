"""``python -m cli`` — the command surface from spec section 2.

The eight spec commands are the contract:

    discover  fetch  parse  normalize  dedup  load  seed-histories  report

Everything else is support tooling. Each command lazily imports the module it
drives so a half-built tree still runs the commands that exist.

Exit codes are the single table in exitcodes.py.
"""

from __future__ import annotations

import functools
import json
import logging
import sys
from pathlib import Path
from typing import Optional

import typer

import exitcodes
import runtime

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
    help="V-OTA RecSys — Week 1 data collection pipeline.",
)
log = logging.getLogger("cli")

HERE = Path(__file__).resolve().parent


# =============================================================================
# shared setup
# =============================================================================
def _cfg():
    from config import load_config

    return load_config()


def _die(code: int, message: str) -> None:
    log.error(message)
    raise typer.Exit(code)


def _guard(fn):
    """Map exceptions to exit codes so every command behaves the same."""

    @functools.wraps(fn)
    def wrapper(*a, **kw):
        from config import ConfigError

        try:
            return fn(*a, **kw)
        except typer.Exit:
            raise
        except ConfigError as exc:
            _die(exitcodes.CONFIG_OR_DB, str(exc))
        except KeyboardInterrupt:
            log.warning("interrupted")
            raise typer.Exit(exitcodes.INTERRUPTED)
        except Exception as exc:  # noqa: BLE001
            log.exception("unexpected error: %s", exc)
            raise typer.Exit(exitcodes.UNEXPECTED)

    return wrapper


@app.callback()
def _main(
    ctx: typer.Context,
    verbose: int = typer.Option(0, "-v", "--verbose", count=True, help="-v debug, -vv SQL echo"),
    quiet: bool = typer.Option(False, "-q", "--quiet"),
    no_log_file: bool = typer.Option(False, "--no-log-file"),
) -> None:
    runtime.setup_encoding()
    command = ctx.invoked_subcommand or "cli"
    try:
        from config import load_config

        lg = load_config().section("logging")
    except Exception:  # config errors surface in the command itself
        lg = {}
    runtime.setup_logging(
        command=command,
        level=str(lg.get("level", "INFO")),
        to_file=bool(lg.get("to_file", True)) and not no_log_file,
        log_dir=HERE / str(lg.get("dir", "logs")),
        max_bytes=int(lg.get("max_bytes", 20_000_000)),
        backup_count=int(lg.get("backup_count", 5)),
        verbose=verbose,
        quiet=quiet,
    )
    runtime.shutdown.install()


def _preflight_source(cfg, source: str, *, allow_blocked: bool = False):
    """Everything discover/fetch must check before touching the network."""
    import db

    src = cfg.source(source)
    if not src.enabled:
        _die(exitcodes.USAGE, f"source {source!r} is disabled in config.yaml")
    if src.respect_robots or src.base_url:
        # Only for sources that actually make requests: a placeholder contact
        # address means a site operator has no way to reach us (spec section 11).
        cfg.assert_contactable_user_agent()
    db.check_connection(cfg)
    db.assert_migrated(cfg)
    blocked = db.is_source_blocked(cfg, source)
    if blocked and not allow_blocked:
        fallback = "amadeus" if source != "amadeus" else "manual"
        _die(
            exitcodes.BLOCKED,
            f"source {source!r} is latched as BLOCKED since {blocked['blocked_at']}: "
            f"{blocked['reason']}\n"
            "Spec section 1: do not circumvent anti-bot. Switch to the fallback:\n"
            f"    python -m cli discover --source {fallback}\n"
            f"    python -m cli fetch --source {fallback}\n"
            "A human may clear the latch with:  python -m cli unblock --source "
            f"{source} --reason '<why it is safe now>'",
        )
    return src


# =============================================================================
# migrate
# =============================================================================
@app.command()
@_guard
def migrate(
    list_only: bool = typer.Option(False, "--list", help="Show state, apply nothing"),
    force_deferred: bool = typer.Option(
        False, "--force-deferred", help="Also apply 003_pgvector.sql (Week 2 only)"
    ),
    dry_run: bool = typer.Option(False, "--dry-run"),
    verify: bool = typer.Option(False, "--verify", help="Compare models.py with the live schema"),
) -> None:
    """Apply migrations 001, 002, 004, 005. 003 (pgvector) is deferred to Week 2."""
    import db

    cfg = _cfg()
    db.check_connection(cfg)
    if list_only:
        for row in db.migration_status(cfg):
            flag = " DRIFTED" if row["drifted"] else ""
            miss = " MISSING-FILE" if row["missing_file"] else ""
            why = f"  ({row['reason']})" if row["reason"] else ""
            typer.echo(f"{row['state']:>17}  {row['filename']}{flag}{miss}{why}")
        return
    applied = db.run_migrations(cfg, force_deferred=force_deferred, dry_run=dry_run)
    typer.echo(("would apply: " if dry_run else "applied: ") + (", ".join(applied) or "nothing"))
    if verify:
        import models

        problems = models.verify_models_against_db(db.get_engine(cfg))
        for p in problems:
            typer.echo(f"  drift: {p}")
        if problems:
            raise typer.Exit(exitcodes.GATE_FAILED)
        typer.echo("models.py matches the database")


# =============================================================================
# the eight spec commands
# =============================================================================
@app.command()
@_guard
def discover(
    source: str = typer.Option(..., "--source"),
    limit: Optional[int] = typer.Option(None, "--limit", help="Stop after N targets"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Fetch sitemaps, write no targets"),
    dump_unmatched: bool = typer.Option(
        False, "--dump-unmatched", help="Print URLs no url_pattern matched (fix config, not code)"
    ),
    from_cache: bool = typer.Option(
        False, "--from-cache", help="Harvest links from already-fetched pages instead of sitemaps"
    ),
) -> None:
    """Populate crawl_targets from sitemaps / listings / API budgets."""
    from collectors.runner import run_discover

    cfg = _cfg()
    _preflight_source(cfg, source)
    if not dry_run:
        cfg.require_anchor_date()
    code = run_discover(
        cfg,
        source,
        limit=limit,
        dry_run=dry_run,
        dump_unmatched=dump_unmatched,
        from_cache=from_cache,
        argv=sys.argv[1:],
    )
    raise typer.Exit(code)


@app.command()
@_guard
def fetch(
    source: str = typer.Option(..., "--source"),
    concurrency: Optional[int] = typer.Option(None, "--concurrency", help="<= config cap (2)"),
    limit: Optional[int] = typer.Option(None, "--limit"),
    run_id: Optional[str] = typer.Option(None, "--run-id", help="Resume an interrupted run"),
    retry_failed: bool = typer.Option(
        False, "--retry-failed", help="Re-queue failed targets (never those failed under a block)"
    ),
    page_type: Optional[str] = typer.Option(None, "--page-type"),
) -> None:
    """Fetch pending targets: bytes to disk, then raw_pages row, then status. Never parses."""
    from collectors.runner import run_fetch

    cfg = _cfg()
    _preflight_source(cfg, source)
    code = run_fetch(
        cfg,
        source,
        concurrency=concurrency,
        limit=limit,
        run_id=run_id,
        retry_failed=retry_failed,
        page_type=page_type,
        argv=sys.argv[1:],
    )
    raise typer.Exit(code)


@app.command()
@_guard
def parse(
    source: str = typer.Option(..., "--source"),
    reparse: bool = typer.Option(
        False, "--reparse", help="Re-parse every cached page (after a parser_version bump)"
    ),
    limit: Optional[int] = typer.Option(None, "--limit"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print payloads as JSON, write nothing"),
    overwrite_same_version: bool = typer.Option(
        False,
        "--overwrite-same-version",
        help="DEV ONLY: replace staging rows at the same parser_version",
    ),
    raw_page_id: Optional[int] = typer.Option(None, "--raw-page-id", help="Parse one page"),
) -> None:
    """Parse cached pages into products_staging. Never fetches."""
    import db
    from collectors.runner import run_parse

    cfg = _cfg()
    db.check_connection(cfg)
    db.assert_migrated(cfg)
    code = run_parse(
        cfg,
        source,
        reparse=reparse,
        limit=limit,
        dry_run=dry_run,
        overwrite_same_version=overwrite_same_version,
        raw_page_id=raw_page_id,
        argv=sys.argv[1:],
    )
    raise typer.Exit(code)


@app.command()
@_guard
def normalize(
    source: Optional[str] = typer.Option(None, "--source", help="Only this source"),
    force: bool = typer.Option(False, "--force", help="Re-normalise rows already at this version"),
    limit: Optional[int] = typer.Option(None, "--limit"),
) -> None:
    """products_staging -> products_normalised (spec section 6)."""
    from normalise import run_normalise

    cfg = _cfg()
    code = run_normalise(cfg, source=source, force=force, limit=limit, argv=sys.argv[1:])
    raise typer.Exit(code)


@app.command()
@_guard
def dedup(
    destination: Optional[str] = typer.Option(None, "--destination"),
    taxonomy: Optional[str] = typer.Option(None, "--taxonomy"),
) -> None:
    """Cluster products_normalised across sources (spec section 7)."""
    from dedup import run_dedup

    cfg = _cfg()
    code = run_dedup(cfg, destination=destination, taxonomy=taxonomy, argv=sys.argv[1:])
    raise typer.Exit(code)


@app.command()
@_guard
def load(
    max_products_per_source: Optional[int] = typer.Option(None, "--max-products-per-source"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Merge clusters and upsert into products + product_sources. Idempotent."""
    from load import run_load

    cfg = _cfg()
    code = run_load(
        cfg, max_products_per_source=max_products_per_source, dry_run=dry_run, argv=sys.argv[1:]
    )
    raise typer.Exit(code)


@app.command("seed-histories")
@_guard
def seed_histories(
    users: Optional[int] = typer.Option(None, "--users"),
    seed: Optional[int] = typer.Option(None, "--seed"),
    now: Optional[str] = typer.Option(None, "--now", help="Reference date YYYY-MM-DD"),
    truncate: bool = typer.Option(
        False, "--truncate", help="Required to replace existing profiles/events/users/bookings"
    ),
    no_sanity: bool = typer.Option(False, "--no-sanity", help="Skip the popularity sanity check"),
) -> None:
    """Generate profiles/events/users/bookings with real structure (spec section 10)."""
    from seed_histories import run_seed

    cfg = _cfg()
    code = run_seed(
        cfg,
        users=users,
        seed=seed,
        now=now,
        truncate=truncate,
        run_sanity=not no_sanity,
        argv=sys.argv[1:],
    )
    raise typer.Exit(code)


@app.command()
@_guard
def report(
    as_json: bool = typer.Option(False, "--json"),
    strict: bool = typer.Option(False, "--strict", help="Fail (exit 7) on unmet DoD checks"),
    extraction_table: bool = typer.Option(
        False, "--extraction-table", help="README section 12 item 1: field -> source -> how"
    ),
    update_readme: bool = typer.Option(False, "--update-readme"),
    runbook: bool = typer.Option(False, "--runbook", help="Print the full rebuild command list"),
    unknown_limit: int = typer.Option(50, "--unknown-limit"),
) -> None:
    """Numbers for the Friday demo + README section 12 (spec section 0 item 7)."""
    from report import run_report

    cfg = _cfg()
    code = run_report(
        cfg,
        as_json=as_json,
        strict=strict,
        extraction_table=extraction_table,
        update_readme=update_readme,
        runbook=runbook,
        unknown_limit=unknown_limit,
    )
    raise typer.Exit(code)


# =============================================================================
# support commands
# =============================================================================
@app.command("robots-check")
@_guard
def robots_check(source: str = typer.Option(..., "--source")) -> None:
    """Fetch robots.txt for a source and show what our UA may crawl. No other requests."""
    from collectors.net import robots_report

    cfg = _cfg()
    src = cfg.source(source)
    if src.respect_robots:
        cfg.assert_contactable_user_agent()
    for line in robots_report(cfg, src):
        typer.echo(line)


@app.command()
@_guard
def unblock(
    source: str = typer.Option(..., "--source"),
    reason: str = typer.Option(..., "--reason", help="Who decided it is safe to retry, and why"),
) -> None:
    """Clear a blocked-source latch. Requires a human reason; there is no timer."""
    import db

    cfg = _cfg()
    if len(reason.strip()) < 10:
        _die(exitcodes.USAGE, "--reason must say who and why (>= 10 chars)")
    if db.unblock_source(cfg, source, reason):
        typer.echo(f"{source}: latch cleared ({reason})")
    else:
        typer.echo(f"{source}: no active latch")


@app.command("adopt-orphans")
@_guard
def adopt_orphans(dry_run: bool = typer.Option(False, "--dry-run")) -> None:
    """Insert raw_pages rows for cached files whose DB write was lost mid-crawl."""
    from collectors.runner import run_adopt_orphans

    cfg = _cfg()
    n = run_adopt_orphans(cfg, dry_run=dry_run)
    typer.echo(f"{'would adopt' if dry_run else 'adopted'} {n} orphaned page(s)")


@app.command("sanity-check")
@_guard
def sanity_check(k: Optional[int] = typer.Option(None, "--k")) -> None:
    """Popularity baseline over seeded events (spec section 10 sanity check)."""
    from sanity import run_sanity

    cfg = _cfg()
    code = run_sanity(cfg, k=k)
    raise typer.Exit(code)


@app.command("sample-descriptions")
@_guard
def sample_descriptions(
    n: int = typer.Option(20, "--n"),
    mark: bool = typer.Option(False, "--mark", help="Record that the review happened"),
    reviewed_by: Optional[str] = typer.Option(None, "--by"),
    verdict: Optional[str] = typer.Option(None, "--verdict", help="ok|generic|truncated|mixed"),
    seed: Optional[int] = typer.Option(None, "--seed"),
) -> None:
    """Print N random descriptions to read by hand (spec sections 7, 13 — mandatory)."""
    from report import run_sample_descriptions

    cfg = _cfg()
    code = run_sample_descriptions(
        cfg, n=n, mark=mark, reviewed_by=reviewed_by, verdict=verdict, seed=seed
    )
    raise typer.Exit(code)


@app.command("save-fixture")
@_guard
def save_fixture(
    raw_page_id: int = typer.Option(..., "--raw-page-id"),
    name: Optional[str] = typer.Option(None, "--name"),
) -> None:
    """Copy a cached page into tests/fixtures/<source>/ for offline parser tests."""
    from collectors.runner import run_save_fixture

    cfg = _cfg()
    path = run_save_fixture(cfg, raw_page_id=raw_page_id, name=name)
    typer.echo(f"saved {path}")


@app.command("amadeus-probe")
@_guard
def amadeus_probe() -> None:
    """~20 requests: how many hotels/activities/flights does the test tier have for VN?

    Run this FIRST on Monday. Its row counts, not vinpearl, decide the week.
    """
    from collectors.amadeus import run_probe

    cfg = _cfg()
    _preflight_source(cfg, "amadeus")
    code = run_probe(cfg)
    raise typer.Exit(code)


@app.command("config-check")
@_guard
def config_check() -> None:
    """Load and validate config.yaml; print the effective politeness settings."""
    cfg = _cfg()
    typer.echo(f"config {cfg.path} sha256={cfg.sha256[:12]}")
    typer.echo(f"user_agent: {cfg.user_agent}")
    typer.echo(f"anchor_date: {cfg.anchor_date}")
    for name in cfg.source_names():
        s = cfg.source(name)
        typer.echo(
            f"  {name:9} enabled={str(s.enabled):5} rps={s.rate_limit_rps:<4} "
            f"conc={s.concurrency} prio={s.source_priority:<3} parser={s.parser_version}"
        )
    typer.echo(f"destinations: {len(cfg.destinations)}  aliases: {len(cfg.destination_index)}")
    typer.echo(json.dumps(cfg.fx_provenance(), ensure_ascii=False))


if __name__ == "__main__":
    app()
