"""The discover / fetch / parse runners.

Two invariants are structural here rather than advisory:

* **fetch never parses, parse never fetches** (spec section 2). ``parse`` gets a
  :class:`~collectors.net.NoNetFetcher` that raises on any request, so a parser
  reaching for a lazy-loaded gallery fails loudly instead of quietly turning
  ``parse --reparse`` into a second crawl.
* **bytes to disk, then the raw_pages row, then the target status** (spec
  section 0 item 2). Written in that order, a crash leaves at worst an
  unreferenced file, which ``adopt-orphans`` can recover. In the other order a
  crash leaves a row pointing at nothing, which looks fetched and is not.

Per-item failures are the expected case (spec section 8): increment ``attempts``,
record ``last_error``, move on. Only a block or a config error stops a run.
"""

from __future__ import annotations

import json
import logging
import queue
import shutil
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import text

import db
import exitcodes
from collectors.base import (
    REQUIRED_PAYLOAD_KEYS,
    BlockedError,
    RawPage,
    RobotsDenied,
    RobotsUnavailable,
    Target,
    assert_no_personal_data,
    get_collector,
)
from cache import Cache, strip_nul
from collectors.net import NoNetFetcher, TransientExhausted, make_fetcher
from config import Config
from ids import url_hash
from runtime import shutdown

log = logging.getLogger("runner")


@dataclass
class Counters:
    seen: int = 0
    ok: int = 0
    failed: int = 0
    skipped: int = 0
    inserted: int = 0
    existing: int = 0
    unchanged: int = 0
    errors: list[str] = field(default_factory=list)


def _progress_every(cfg: Config) -> int:
    return int(cfg.section("logging").get("progress_every", 25))


# =============================================================================
# discover
# =============================================================================
def run_discover(
    cfg: Config,
    source: str,
    *,
    limit: int | None = None,
    dry_run: bool = False,
    dump_unmatched: bool = False,
    from_cache: bool = False,
    argv: list[str] | None = None,
) -> int:
    src = cfg.source(source)
    cache = Cache(cfg.data_root)
    fetcher = make_fetcher(cfg, src)
    collector = get_collector(cfg, source, fetcher=fetcher)
    collector.cache = cache  # type: ignore[attr-defined]
    collector.from_cache = from_cache  # type: ignore[attr-defined]
    collector.dump_unmatched = dump_unmatched  # type: ignore[attr-defined]

    c = Counters()
    every = _progress_every(cfg)

    with db.command_lock(cfg, f"discover:{source}"):
        with db.crawl_run(source, "discover", cfg, argv=argv) as run:
            run.note("user_agent", cfg.user_agent)
            run.note("parser_version", src.parser_version)
            run.note("dry_run", dry_run)
            if cfg.anchor_date:
                run.note("quote_anchor_date", cfg.anchor_date.isoformat())
            run.note(
                "quote_params",
                {
                    q: cfg.resolve_quote_context(q)
                    for q in cfg.enabled_quote_contexts()
                    if cfg.anchor_date
                },
            )

            def on_sitemap(url: str, result, body: bytes) -> None:  # noqa: ANN001
                """A sitemap is a fetched page: cache it and give it a raw_pages row.

                ``raw_pages.target_id`` is nullable in the section 4.1 DDL, so a
                discovery page needs no ``crawl_targets`` row — but it does need
                the file on disk before anything parses it, including here.
                """
                cw = cache.write(
                    strip_nul(body), source=source, content_type=result.content_type, url=url
                )
                if dry_run:
                    return
                with db.session_scope(cfg) as s:
                    s.execute(
                        text(
                            "INSERT INTO raw_pages (run_id, source, url, http_status, "
                            "content_path, content_sha256, content_type, meta) "
                            "VALUES (:r, :s, :u, :st, :cp, :sha, :ct, CAST(:m AS jsonb))"
                        ),
                        {
                            "r": str(run.run_id),
                            "s": source,
                            "u": url,
                            "st": result.status,
                            "cp": cw.content_path,
                            "sha": cw.sha256,
                            "ct": result.content_type,
                            "m": json.dumps({"role": "discovery"}),
                        },
                    )

            collector.on_discovery_page = on_sitemap  # type: ignore[attr-defined]

            try:
                for target in collector.discover():
                    c.seen += 1
                    if dry_run:
                        print(
                            f"{target.page_type:7} p={target.priority:<4} "
                            f"qc={target.quote_ctx or '-':5} {target.url}"
                        )
                    else:
                        inserted = _upsert_target(cfg, source, target)
                        if inserted:
                            c.inserted += 1
                        else:
                            c.existing += 1
                    if c.seen % every == 0:
                        log.info(
                            "progress discover %s seen=%d new=%d existing=%d",
                            source, c.seen, c.inserted, c.existing,
                        )
                    if limit and c.seen >= limit:
                        log.info("stopping at --limit %d", limit)
                        break
                    if shutdown.requested:
                        break
            except BlockedError as exc:
                db.latch_source_blocked(cfg, source, exc.detail)
                run.set("hard_stop", exc.detail)
                _print_fallback(source)
                return exitcodes.BLOCKED
            except RobotsUnavailable as exc:
                run.set("robots_unavailable", {"host": exc.host, "status": exc.status})
                log.error(
                    "CANNOT CRAWL %s: %s\n"
                    "  robots.txt is the one file that grants permission, and it is not\n"
                    "  readable — most likely an edge/WAF rule rejecting non-browser\n"
                    "  clients. Spec section 1 rules out working around that (a browser\n"
                    "  User-Agent here would be evasion, not a fix).\n"
                    "  This is the spec section 0 Wednesday checkpoint firing early.\n"
                    "  Use a fallback source (spec section 9):\n"
                    "      python -m cli discover --source manual   # curated golf/combo YAML\n"
                    "      python -m cli amadeus-probe              # needs AMADEUS_* in .env\n"
                    "      python -m cli discover --source osm      # enable sources.osm first\n"
                    "  If someone can confirm crawl permission for this host, record it in\n"
                    "  docs/decisions/ and set sources.%s.respect_robots deliberately.",
                    source, exc, source,
                )
                return exitcodes.ROBOTS_UNAVAILABLE

            unmatched = getattr(collector, "unmatched_urls", [])
            if dump_unmatched and unmatched:
                print(f"\n--- {len(unmatched)} URL(s) matched no url_pattern ---")
                print("Fix sources.%s.url_patterns in config.yaml, not the parser." % source)
                for u in unmatched[:200]:
                    print(f"  {u}")
            run.set("urls_seen", c.seen)
            run.set("targets_inserted", c.inserted)
            run.set("targets_existing", c.existing)
            run.set("urls_unmatched", len(unmatched))

    log.info(
        "discover %s done: seen=%d new=%d existing=%d unmatched=%d",
        source, c.seen, c.inserted, c.existing, len(getattr(collector, "unmatched_urls", [])),
    )
    if not dry_run and c.inserted == 0 and c.existing == 0:
        log.error(
            "discover found no targets. If the site shape differs from our guess, run "
            "`discover --dry-run --dump-unmatched` and fix sources.%s.url_patterns.",
            source,
        )
        return exitcodes.GATE_FAILED
    return exitcodes.OK


def _upsert_target(cfg: Config, source: str, target: Target) -> bool:
    """Insert a target, or report that it already existed.

    ``ON CONFLICT (source, url_hash, quote_ctx)`` is NULL-safe because
    005 adds a ``NULLS NOT DISTINCT`` unique index. Without it every re-run of
    discover would duplicate every date-independent target (attractions, golf,
    combos), re-fetch them at 0.5 rps, and inflate the product count.
    """
    with db.session_scope(cfg) as s:
        row = s.execute(
            text(
                """
                INSERT INTO crawl_targets
                       (source, url, url_hash, page_type, quote_ctx, priority)
                VALUES (:src, :url, :uh, :pt, :qc, :prio)
                ON CONFLICT (source, url_hash, quote_ctx) DO NOTHING
                RETURNING id
                """
            ),
            {
                "src": source,
                "url": target.url,
                "uh": url_hash(target.url),
                "pt": target.page_type,
                "qc": target.quote_ctx,
                "prio": target.priority,
            },
        ).first()
    return row is not None


def _print_fallback(source: str) -> None:
    fallback = "amadeus" if source != "amadeus" else "manual"
    log.error(
        "STOPPING. Spec section 1: do not circumvent anti-bot.\n"
        "  Switch to the fallback:\n"
        "      python -m cli discover --source %s\n"
        "      python -m cli fetch    --source %s\n"
        "  The latch is durable; a human clears it with `cli unblock`.",
        fallback, fallback,
    )


# =============================================================================
# fetch
# =============================================================================
def run_fetch(
    cfg: Config,
    source: str,
    *,
    concurrency: int | None = None,
    limit: int | None = None,
    run_id: str | None = None,
    retry_failed: bool = False,
    page_type: str | None = None,
    argv: list[str] | None = None,
) -> int:
    src = cfg.source(source)
    cache = Cache(cfg.data_root)
    conc = min(concurrency or src.concurrency, src.concurrency)

    if retry_failed:
        # Never re-queue targets that failed under a block: `fetch
        # --retry-failed` on a source that served a CAPTCHA is probing, which
        # spec section 1 forbids. The latch check in the CLI preflight covers
        # the source; this covers individual rows.
        n = _requeue_failed(cfg, source)
        log.info("re-queued %d failed target(s) (permanent failures skipped)", n)

    targets = _pending_targets(cfg, source, limit=limit, page_type=page_type)
    if not targets:
        log.info("nothing pending for %s. Run `discover --source %s` first.", source, source)
        return exitcodes.OK

    log.info("fetching %d target(s) for %s at %.2f rps, concurrency %d",
             len(targets), source, src.rate_limit_rps, conc)

    fetcher = make_fetcher(cfg, src)
    collector = get_collector(cfg, source, fetcher=fetcher)
    c = Counters()
    every = _progress_every(cfg)
    blocked_detail: dict[str, Any] | None = None
    robots_problem: list[RobotsUnavailable] = []
    work: queue.Queue = queue.Queue()
    for t in targets:
        work.put(t)
    lock = threading.Lock()
    started = time.monotonic()

    with db.command_lock(cfg, f"fetch:{source}"):
        with db.crawl_run(source, "fetch", cfg, argv=argv, run_id=run_id) as run:
            run.note("user_agent", cfg.user_agent)
            run.note("rate_limit_rps", src.rate_limit_rps)
            run.note("concurrency", conc)
            run.note("parser_version", src.parser_version)
            run.set("targets_claimed", len(targets))

            def worker() -> None:
                nonlocal blocked_detail
                while not shutdown.requested and blocked_detail is None and not robots_problem:
                    try:
                        row = work.get_nowait()
                    except queue.Empty:
                        return
                    try:
                        _fetch_one(cfg, collector, cache, run, row, c, lock)
                    except BlockedError as exc:
                        with lock:
                            blocked_detail = exc.detail
                        return
                    except RobotsUnavailable as exc:
                        with lock:
                            robots_problem.append(exc)
                        return
                    except KeyboardInterrupt:
                        return
                    finally:
                        work.task_done()
                    with lock:
                        done = c.ok + c.failed + c.skipped
                    if done % every == 0:
                        rate = done / max(time.monotonic() - started, 0.001)
                        log.info(
                            "progress fetch %s %d/%d ok=%d failed=%d skip=%d rps=%.2f",
                            source, done, len(targets), c.ok, c.failed, c.skipped, rate,
                        )

            threads = [
                threading.Thread(target=worker, name=f"fetch-{i}", daemon=True)
                for i in range(conc)
            ]
            for t in threads:
                t.start()
            for t in threads:
                # A join with no timeout is not Ctrl-C-interruptible on Windows.
                while t.is_alive():
                    t.join(timeout=0.5)

            run.set("fetched_ok", c.ok)
            run.set("failed", c.failed)
            run.set("skipped", c.skipped)
            run.set("rps_observed", round(
                (c.ok + c.failed) / max(time.monotonic() - started, 0.001), 3
            ))
            for e in c.errors[:10]:
                run.add_error_sample({"error": e})
            if blocked_detail is not None:
                db.latch_source_blocked(cfg, source, blocked_detail)
                run.set("hard_stop", blocked_detail)
            if robots_problem:
                run.set(
                    "robots_unavailable",
                    {"host": robots_problem[0].host, "status": robots_problem[0].status},
                )

    if blocked_detail is not None:
        _print_fallback(source)
        return exitcodes.BLOCKED
    if robots_problem:
        log.error(
            "CANNOT FETCH %s: %s. Permission cannot be established, so nothing was "
            "requested beyond robots.txt itself. See spec section 9 for fallbacks.",
            source, robots_problem[0],
        )
        return exitcodes.ROBOTS_UNAVAILABLE

    log.info(
        "fetch %s done: ok=%d failed=%d skipped=%d in %.0fs",
        source, c.ok, c.failed, c.skipped, time.monotonic() - started,
    )
    # Per-item failures exit OK: spec section 8 treats them as expected, and a
    # non-zero code here would make the documented fallback wrapper branch on
    # the wrong thing.
    return exitcodes.OK


def _pending_targets(
    cfg: Config, source: str, *, limit: int | None, page_type: str | None
) -> list[dict[str, Any]]:
    sql = (
        "SELECT id, url, page_type, quote_ctx, attempts FROM crawl_targets "
        "WHERE source = :s AND status = 'pending'"
    )
    params: dict[str, Any] = {"s": source}
    if page_type:
        sql += " AND page_type = :pt"
        params["pt"] = page_type
    sql += " ORDER BY priority, id"
    if limit:
        sql += " LIMIT :lim"
        params["lim"] = limit
    with db.session_scope(cfg) as s:
        rows = s.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


def _requeue_failed(cfg: Config, source: str) -> int:
    with db.session_scope(cfg) as s:
        res = s.execute(
            text(
                "UPDATE crawl_targets SET status = 'pending' "
                "WHERE source = :s AND status = 'failed' "
                "AND COALESCE(last_error, '') NOT LIKE 'permanent:%' "
                "AND COALESCE(last_error, '') NOT LIKE 'blocked:%'"
            ),
            {"s": source},
        )
    return res.rowcount


def _fetch_one(
    cfg: Config,
    collector,  # noqa: ANN001
    cache: Cache,
    run: db.RunHandle,
    row: dict[str, Any],
    c: Counters,
    lock: threading.Lock,
) -> None:
    target = Target(
        url=row["url"],
        page_type=row["page_type"],
        quote_ctx=row["quote_ctx"],
    )
    tid = row["id"]
    try:
        raw = collector.fetch(target)
    except RobotsDenied:
        _set_target(cfg, tid, "skipped", "robots: disallowed for our user agent")
        with lock:
            c.skipped += 1
        log.info("fetch skip target=%s reason=robots-disallow url=%s", tid, target.url)
        return
    except RobotsUnavailable:
        _set_target(cfg, tid, "skipped", "robots: robots.txt unreadable, permission unknown")
        raise
    except BlockedError:
        _set_target(cfg, tid, "failed", "blocked: source is challenging us")
        raise
    except (TransientExhausted, Exception) as exc:  # noqa: BLE001
        if isinstance(exc, KeyboardInterrupt):
            raise
        _mark_target_failed(cfg, tid, f"{type(exc).__name__}: {exc}", stage="fetch")
        with lock:
            c.failed += 1
            c.errors.append(f"{target.url}: {exc}")
        log.warning("fetch fail target=%s err=%s url=%s", tid, exc, target.url)
        return

    body = strip_nul(raw.content)
    # --- ordering invariant: file, then row, then status ---
    cw = cache.write(
        body, source=collector.source, content_type=raw.content_type, url=raw.url
    )
    # Keep whatever the collector recorded (an API source's endpoint, a manual
    # source's file path) alongside the standard provenance: parse reads
    # raw_pages.meta, and a collector that needs context at parse time has
    # nowhere else to put it.
    meta = {**raw.meta, "page_type": target.page_type}
    cache.write_pending_marker(cw, {"url": raw.url, "source": collector.source, "target_id": tid,
                                    "http_status": raw.http_status, "meta": meta})
    try:
        with db.session_scope(cfg) as s:
            s.execute(
                text(
                    "INSERT INTO raw_pages (run_id, target_id, source, url, http_status, "
                    "content_path, content_sha256, content_type, quote_ctx, meta) "
                    "VALUES (:r, :t, :s, :u, :st, :cp, :sha, :ct, :qc, CAST(:m AS jsonb))"
                ),
                {
                    "r": str(run.run_id),
                    "t": tid,
                    "s": collector.source,
                    "u": raw.url,
                    "st": raw.http_status,
                    "cp": cw.content_path,
                    "sha": cw.sha256,
                    "ct": raw.content_type,
                    "qc": raw.quote_ctx,
                    "m": json.dumps(meta, ensure_ascii=False, default=str),
                },
            )
            status = "fetched" if 200 <= raw.http_status < 300 else "failed"
            if status == "fetched":
                s.execute(
                    text("UPDATE crawl_targets SET status = 'fetched' WHERE id = :i"),
                    {"i": tid},
                )
            else:
                s.execute(
                    text(
                        "UPDATE crawl_targets SET status = 'failed', attempts = attempts + 1, "
                        "last_error = :e WHERE id = :i"
                    ),
                    {"i": tid, "e": f"permanent: http {raw.http_status}"},
                )
    finally:
        cache.clear_pending_marker(cw.content_path)

    with lock:
        if 200 <= raw.http_status < 300:
            c.ok += 1
        else:
            c.failed += 1
        run.bump("http_%dxx" % (raw.http_status // 100))
        run.bump("raw_bytes", len(body))
        run.bump("stored_bytes", cw.stored_bytes)
        if cw.deduped:
            run.bump("cache_deduped")
        run.flush()

    log.info(
        "fetch ok target=%s status=%s bytes=%d gz=%d sha=%s ms=%s wait=%s attempt=%s qc=%s url=%s",
        tid, raw.http_status, len(body), cw.stored_bytes, cw.sha256[:12],
        meta.get("elapsed_ms"), meta.get("waited_ms"), meta.get("attempts"),
        raw.quote_ctx or "-", raw.url,
    )


def _set_target(cfg: Config, target_id: int, status: str, error: str | None = None) -> None:
    with db.session_scope(cfg) as s:
        s.execute(
            text("UPDATE crawl_targets SET status = :st, last_error = :e WHERE id = :i"),
            {"st": status, "e": error, "i": target_id},
        )


def _mark_target_failed(cfg: Config, target_id: int, error: str, *, stage: str) -> None:
    """One helper for both runners, so spec section 8's ``attempts += 1`` holds on
    the parse path too.

    Once ``attempts`` reaches ``http.max_retries`` the error is prefixed
    ``permanent:`` and ``--retry-failed`` leaves it alone — otherwise a
    permanently broken page is re-attempted forever.
    """
    from config import load_config

    max_retries = int(load_config().section("http").get("max_retries", 3))
    with db.session_scope(cfg) as s:
        s.execute(
            text(
                """
                UPDATE crawl_targets
                   SET attempts   = attempts + 1,
                       status     = 'failed',
                       last_error = CASE WHEN attempts + 1 >= :mx
                                         THEN 'permanent: ' || :e
                                         ELSE :stage || ': ' || :e END
                 WHERE id = :i
                """
            ),
            {"i": target_id, "e": error[:2000], "mx": max_retries, "stage": stage},
        )


# =============================================================================
# parse
# =============================================================================
def run_parse(
    cfg: Config,
    source: str,
    *,
    reparse: bool = False,
    limit: int | None = None,
    dry_run: bool = False,
    overwrite_same_version: bool = False,
    raw_page_id: int | None = None,
    argv: list[str] | None = None,
) -> int:
    src = cfg.source(source)
    cache = Cache(cfg.data_root)
    # NoNetFetcher, not a real one: this is how "parse never fetches" is enforced.
    collector = get_collector(cfg, source, fetcher=NoNetFetcher())

    pages = _pages_to_parse(cfg, source, reparse=reparse, limit=limit, raw_page_id=raw_page_id)
    if not pages:
        log.info(
            "nothing to parse for %s. Fetch first, or pass --reparse to re-read "
            "every cached page.", source,
        )
        return exitcodes.OK

    log.info("parsing %d cached page(s) for %s at %s", len(pages), source, src.parser_version)
    c = Counters()
    every = _progress_every(cfg)

    with db.command_lock(cfg, f"parse:{source}"):
        with db.crawl_run(source, "parse", cfg, argv=argv) as run:
            run.note("parser_version", src.parser_version)
            run.note("reparse", reparse)
            for page in pages:
                c.seen += 1
                try:
                    body = cache.read(page["content_path"])
                except FileNotFoundError as exc:
                    log.warning("parse skip raw_page=%s: %s", page["id"], exc)
                    c.skipped += 1
                    continue

                raw = RawPage(
                    url=page["url"],
                    http_status=page["http_status"] or 0,
                    content=body,
                    content_type=page["content_type"] or "",
                    quote_ctx=page["quote_ctx"],
                    raw_page_id=page["id"],
                    target_id=page["target_id"],
                    meta=dict(page["meta"] or {}),
                )

                try:
                    payloads = collector.parse(raw)
                    _validate_payloads(payloads, source)
                except Exception as exc:  # noqa: BLE001 - one page must not kill the run
                    log.exception("parse fail raw_page=%s url=%s", page["id"], page["url"])
                    c.failed += 1
                    c.errors.append(f"{page['url']}: {exc}")
                    if page["target_id"]:
                        _mark_target_failed(
                            cfg, page["target_id"],
                            f"{src.parser_version}: {type(exc).__name__}: {exc}",
                            stage="parse",
                        )
                    continue

                if dry_run:
                    for p in payloads:
                        print(json.dumps(p, ensure_ascii=False, indent=2, default=str))
                    c.ok += 1
                    continue

                ins, unchanged = _write_staging(
                    cfg, source, src.parser_version, page["id"], payloads,
                    overwrite=overwrite_same_version,
                )
                c.inserted += ins
                c.unchanged += unchanged
                c.ok += 1
                if page["target_id"]:
                    _set_target(cfg, page["target_id"], "parsed", None)

                if c.seen % every == 0:
                    log.info(
                        "progress parse %s %d/%d rows=%d unchanged=%d failed=%d",
                        source, c.seen, len(pages), c.inserted, c.unchanged, c.failed,
                    )
                    run.flush()
                if shutdown.requested:
                    break

            run.set("pages_parsed", c.ok)
            run.set("pages_failed", c.failed)
            run.set("pages_skipped", c.skipped)
            run.set("staging_inserted", c.inserted)
            run.set("staging_unchanged", c.unchanged)
            for e in c.errors[:10]:
                run.add_error_sample({"error": e})

    log.info(
        "parse %s done: pages=%d rows=%d unchanged=%d failed=%d skipped=%d",
        source, c.ok, c.inserted, c.unchanged, c.failed, c.skipped,
    )
    return exitcodes.OK


def _pages_to_parse(
    cfg: Config, source: str, *, reparse: bool, limit: int | None, raw_page_id: int | None
) -> list[dict[str, Any]]:
    """Work comes from ``raw_pages`` rows, never from walking the cache directory.

    The row carries the url, the quote context and the http status; a filename
    (a sha256) carries none of those.
    """
    sql = [
        "SELECT rp.id, rp.url, rp.http_status, rp.content_path, rp.content_type,",
        "       rp.quote_ctx, rp.target_id, rp.meta",
        "  FROM raw_pages rp",
        "  LEFT JOIN crawl_targets ct ON ct.id = rp.target_id",
        " WHERE rp.source = :s",
        "   AND COALESCE(rp.meta->>'role', '') <> 'discovery'",
        "   AND (rp.http_status IS NULL OR rp.http_status BETWEEN 200 AND 299)",
    ]
    params: dict[str, Any] = {"s": source}
    if raw_page_id:
        sql.append("   AND rp.id = :rid")
        params["rid"] = raw_page_id
    elif not reparse:
        sql.append("   AND (ct.status = 'fetched' OR ct.status IS NULL)")
    sql.append(" ORDER BY rp.id")
    if limit:
        sql.append(" LIMIT :lim")
        params["lim"] = limit
    with db.session_scope(cfg) as s:
        rows = s.execute(text("\n".join(sql)), params).mappings().all()
    return [dict(r) for r in rows]


def _validate_payloads(payloads: list[dict], source: str) -> None:
    if not isinstance(payloads, list):
        raise TypeError(f"{source}.parse must return a list, got {type(payloads).__name__}")
    seen: set[str] = set()
    for p in payloads:
        if not isinstance(p, dict):
            raise TypeError(f"{source}.parse returned a {type(p).__name__}, expected dict")
        for key in REQUIRED_PAYLOAD_KEYS:
            if not p.get(key):
                raise ValueError(f"payload missing required key {key!r}: {list(p)[:12]}")
        ref = p["source_ref"]
        if not str(ref).startswith(f"{source}:"):
            raise ValueError(f"source_ref {ref!r} must start with '{source}:'")
        if ref in seen:
            raise ValueError(f"duplicate source_ref {ref!r} from one page")
        seen.add(ref)
        # spec section 5.4 — no review text, no reviewer names, no personal data
        assert_no_personal_data(p)


def _write_staging(
    cfg: Config,
    source: str,
    parser_version: str,
    raw_page_id: int,
    payloads: list[dict],
    *,
    overwrite: bool,
) -> tuple[int, int]:
    """Insert staging rows.

    Default conflict action is ``DO NOTHING``, so re-running ``parse`` at the
    same ``parser_version`` is a genuine no-op. Spec section 8 requires a
    parser change to *bump* the version and add rows rather than overwrite:
    replacing a payload in place would destroy the only record of what the
    previous parser extracted, which is exactly what the cache-and-reparse
    discipline exists to preserve. ``--overwrite-same-version`` is a dev escape
    hatch for iterating on a parser without burning version numbers.
    """
    action = (
        "DO UPDATE SET payload = EXCLUDED.payload, parsed_at = now(), "
        "raw_page_id = EXCLUDED.raw_page_id"
        if overwrite
        else "DO NOTHING"
    )
    inserted = unchanged = 0
    with db.session_scope(cfg) as s:
        for p in payloads:
            row = s.execute(
                text(
                    f"""
                    INSERT INTO products_staging
                           (source, source_ref, raw_page_id, parser_version, payload)
                    VALUES (:s, :ref, :rid, :pv, CAST(:pl AS jsonb))
                    ON CONFLICT (source, source_ref, parser_version) {action}
                    RETURNING id
                    """
                ),
                {
                    "s": source,
                    "ref": p["source_ref"],
                    "rid": raw_page_id,
                    "pv": parser_version,
                    "pl": json.dumps(p, ensure_ascii=False, default=str),
                },
            ).first()
            if row is None:
                unchanged += 1
            else:
                inserted += 1
    return inserted, unchanged


# =============================================================================
# support
# =============================================================================
def run_adopt_orphans(cfg: Config, *, dry_run: bool = False) -> int:
    """Insert ``raw_pages`` rows for cached files whose DB write was lost.

    The window is small but real: ``fetch`` writes the ``.gz`` and then the row,
    and a laptop that sleeps or a ``docker compose restart`` in between leaves
    bytes that cost 2 seconds each at 0.5 rps unreferenced forever. The sidecar
    marker written by ``cache.write_pending_marker`` carries the url and status
    needed to attach them.
    """
    cache = Cache(cfg.data_root)
    adopted = 0
    for payload, marker_path in list(cache.iter_pending_markers()):
        with db.session_scope(cfg) as s:
            exists = s.execute(
                text("SELECT 1 FROM raw_pages WHERE content_path = :cp"),
                {"cp": payload["content_path"]},
            ).first()
            if exists:
                if not dry_run:
                    Path(marker_path).unlink(missing_ok=True)
                continue
            log.info("adopting %s (%s)", payload["content_path"], payload.get("url"))
            if dry_run:
                adopted += 1
                continue
            s.execute(
                text(
                    "INSERT INTO raw_pages (target_id, source, url, http_status, "
                    "content_path, content_sha256, content_type, meta) "
                    "VALUES (:t, :s, :u, :st, :cp, :sha, NULL, CAST(:m AS jsonb))"
                ),
                {
                    "t": payload.get("target_id"),
                    "s": payload["source"],
                    "u": payload.get("url", ""),
                    "st": payload.get("http_status"),
                    "cp": payload["content_path"],
                    "sha": payload["sha256"],
                    "m": json.dumps({**(payload.get("meta") or {}), "adopted": True}),
                },
            )
            if payload.get("target_id"):
                s.execute(
                    text("UPDATE crawl_targets SET status = 'fetched' WHERE id = :i"),
                    {"i": payload["target_id"]},
                )
        if not dry_run:
            Path(marker_path).unlink(missing_ok=True)
        adopted += 1
    return adopted


def run_save_fixture(cfg: Config, *, raw_page_id: int, name: str | None = None) -> Path:
    """Copy a cached page into ``tests/fixtures/<source>/`` for offline tests.

    Committed on purpose, which is why ``.gitignore`` excludes the raw cache by
    path rather than by ``*.gz``.
    """
    cache = Cache(cfg.data_root)
    with db.session_scope(cfg) as s:
        row = s.execute(
            text("SELECT source, url, content_path FROM raw_pages WHERE id = :i"),
            {"i": raw_page_id},
        ).mappings().first()
    if row is None:
        raise ValueError(f"no raw_pages row with id {raw_page_id}")
    src_path = cache.absolute(row["content_path"])
    ext = "".join(src_path.suffixes[-2:])
    from ids import slugify

    fixture_name = name or slugify(row["url"].rsplit("/", 1)[-1] or f"page-{raw_page_id}")
    dest_dir = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / row["source"]
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{fixture_name}{ext}"
    shutil.copy2(src_path, dest)
    meta = dest_dir / f"{fixture_name}.url.txt"
    meta.write_text(f"{row['url']}\nraw_page_id={raw_page_id}\n", encoding="utf-8")
    return dest
