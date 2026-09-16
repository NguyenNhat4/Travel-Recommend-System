"""Engine, sessions, the migration runner, and the ``crawl_runs`` lifecycle."""

from __future__ import annotations

import contextlib
import json
import logging
import time
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

import exitcodes
from config import SENTINEL_SOURCES, Config, ConfigError, load_config
from runtime import shutdown

log = logging.getLogger("db")

HERE = Path(__file__).resolve().parent
MIGRATIONS_DIR = HERE / "migrations"

# =============================================================================
# migrations
# =============================================================================
# An EXPLICIT list, not a glob. A runner that globs `migrations/*.sql` and
# applies them in lexical order will happily run 003_pgvector.sql on its way to
# 004, create the `vector` extension and freeze the embedding dimension at 768 —
# before Week 2 has benchmarked a single model. Spec section 4.3 is blunt about
# this: "Không chạy migration này trong Week 1."
APPLY_ORDER: tuple[str, ...] = (
    "001_raw_and_staging.sql",
    "002_cdp_clone.sql",
    "004_normalise_dedup.sql",
    "005_crawl_indexes.sql",
)

DEFERRED: dict[str, str] = {
    "003_pgvector.sql": (
        "Week 2: the vector dimension is part of the schema, so applying this "
        "before the embedding model is chosen freezes the choice "
        "(spec section 4.3)."
    ),
}


class MigrationError(Exception):
    pass


# =============================================================================
# engine / session
# =============================================================================
_engine: Engine | None = None
_Session: sessionmaker[Session] | None = None


def get_engine(cfg: Config | None = None, *, reset: bool = False) -> Engine:
    global _engine, _Session
    if _engine is not None and not reset:
        return _engine
    cfg = cfg or load_config()
    url = cfg.database_url
    _engine = create_engine(
        url,
        future=True,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={
            # Docker Desktop routes through a WSL2 NAT that drops idle TCP. A
            # two-hour crawl holds connections that do nothing for long
            # stretches — exactly what gets dropped — and the failure surfaces
            # as an OperationalError when the run tries to record that it
            # succeeded.
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
            "application_name": "vota-data-collection",
        },
    )
    _Session = sessionmaker(bind=_engine, future=True, expire_on_commit=False)
    log.debug("engine created for %s", _redact(url))
    return _engine


def _redact(url: str) -> str:
    if "@" not in url:
        return url
    head, _, tail = url.rpartition("@")
    scheme, _, creds = head.partition("://")
    user = creds.split(":", 1)[0]
    return f"{scheme}://{user}:***@{tail}"


@contextlib.contextmanager
def session_scope(cfg: Config | None = None) -> Iterator[Session]:
    """Transactional scope. Commits on success, rolls back on any exception."""
    get_engine(cfg)
    assert _Session is not None
    s = _Session()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def check_connection(cfg: Config | None = None) -> None:
    try:
        with get_engine(cfg).connect() as c:
            c.execute(text("SELECT 1"))
    except Exception as exc:
        raise ConfigError(
            f"cannot reach Postgres: {exc}\n"
            "Is it up?  cd vota-recsys && docker compose up -d postgres"
        ) from exc


# =============================================================================
# migration runner
# =============================================================================
def _execute_script(conn, sql: str) -> None:  # noqa: ANN001
    """Run a whole .sql file as one statement, with no parameter processing.

    Two traps, both hit on the first real run:

    * The file is a multi-statement script and 004 contains a ``$$``-quoted
      function body, so it cannot be split on semicolons.
    * SQLAlchemy hands psycopg an empty parameter tuple rather than ``None``,
      which switches on client-side placeholder scanning — and then any literal
      ``%`` in the script (the pg_trgm similarity operator, a ``LIKE`` pattern,
      or merely a comment mentioning one) raises
      "only '%s', '%b', '%t' are allowed as placeholders".

    Going through the driver cursor with no parameters avoids both. It still
    runs inside the caller's transaction.
    """
    cursor = conn.connection.driver_connection.cursor()
    try:
        cursor.execute(sql)
    finally:
        cursor.close()


def _ensure_ledger(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename    TEXT PRIMARY KEY,
                sha256      TEXT NOT NULL,
                applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )


def applied_migrations(cfg: Config | None = None) -> dict[str, str]:
    with get_engine(cfg).begin() as conn:
        _ensure_ledger(conn)
        rows = conn.execute(text("SELECT filename, sha256 FROM schema_migrations")).all()
    return {r[0]: r[1] for r in rows}


def migration_status(cfg: Config | None = None) -> list[dict[str, Any]]:
    import hashlib

    done = applied_migrations(cfg)
    out: list[dict[str, Any]] = []
    for name in (*APPLY_ORDER, *DEFERRED):
        path = MIGRATIONS_DIR / name
        exists = path.exists()
        sha = (
            hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
            if exists
            else ""
        )
        state = "deferred" if name in DEFERRED else ("applied" if name in done else "pending")
        if name in done and name in DEFERRED:
            state = "applied-deferred"
        drifted = name in done and exists and done[name] != sha
        out.append(
            {
                "filename": name,
                "state": state,
                "drifted": drifted,
                "missing_file": not exists,
                "reason": DEFERRED.get(name, ""),
            }
        )
    return out


def run_migrations(
    cfg: Config | None = None, *, force_deferred: bool = False, dry_run: bool = False
) -> list[str]:
    """Apply pending migrations from APPLY_ORDER. Returns what was applied."""
    import hashlib

    cfg = cfg or load_config()
    engine = get_engine(cfg)
    done = applied_migrations(cfg)

    to_apply = list(APPLY_ORDER)
    if force_deferred:
        log.warning(
            "--force-deferred: applying %s. This freezes the embedding dimension.",
            ", ".join(DEFERRED),
        )
        to_apply += list(DEFERRED)

    applied: list[str] = []
    for name in to_apply:
        path = MIGRATIONS_DIR / name
        if not path.exists():
            raise MigrationError(f"migration file missing: {path}")
        sql = path.read_text(encoding="utf-8")
        sha = hashlib.sha256(sql.encode("utf-8")).hexdigest()

        if name in done:
            if done[name] != sha:
                # An applied migration whose text changed means the DB and the
                # repo disagree about the schema. Silently ignoring that is how
                # a column ends up missing in one environment only.
                log.warning(
                    "%s was applied with different content (db=%s repo=%s). "
                    "Add a new migration instead of editing an applied one.",
                    name,
                    done[name][:12],
                    sha[:12],
                )
            continue

        if dry_run:
            log.info("would apply %s", name)
            applied.append(name)
            continue

        log.info("applying %s", name)
        with engine.begin() as conn:
            _ensure_ledger(conn)
            _execute_script(conn, sql)
            conn.execute(
                text(
                    "INSERT INTO schema_migrations (filename, sha256) VALUES (:f, :s) "
                    "ON CONFLICT (filename) DO UPDATE SET sha256 = EXCLUDED.sha256, "
                    "applied_at = now()"
                ),
                {"f": name, "s": sha},
            )
        applied.append(name)

    return applied


def assert_migrated(cfg: Config | None = None) -> None:
    done = applied_migrations(cfg)
    missing = [m for m in APPLY_ORDER if m not in done]
    if missing:
        raise ConfigError(
            "schema is not up to date; missing: "
            + ", ".join(missing)
            + "\nRun:  python -m cli migrate"
        )


# =============================================================================
# crawl_runs lifecycle
# =============================================================================
@dataclass
class RunHandle:
    """Owns one ``crawl_runs`` row for the duration of a command.

    Counters live in memory and are flushed periodically, so a killed process
    still leaves numbers behind. On ``--run-id`` resume the counters are seeded
    from the stored row first: ``stats = stats || :delta`` is a shallow merge
    that *replaces* each key, so a fresh process starting at zero would write
    ``fetched_ok: 25`` over a stored ``1200``.
    """

    run_id: uuid.UUID
    source: str
    kind: str
    cfg: Config
    counters: dict[str, Any] = field(default_factory=dict)
    _last_flush: float = 0.0
    _fixed: dict[str, Any] = field(default_factory=dict)

    def bump(self, key: str, by: int = 1) -> None:
        self.counters[key] = int(self.counters.get(key, 0)) + by

    def set(self, key: str, value: Any) -> None:
        self.counters[key] = value

    def note(self, key: str, value: Any) -> None:
        """Set a value that is never aggregated (config hash, user agent, ...)."""
        self._fixed[key] = value

    def add_error_sample(self, sample: dict[str, Any], *, cap: int = 10) -> None:
        samples = self.counters.setdefault("error_samples", [])
        if len(samples) < cap:
            samples.append(sample)

    def flush(self, *, force: bool = False) -> None:
        every = float(self.cfg.section("logging").get("flush_interval_s", 30))
        now = time.monotonic()
        if not force and (now - self._last_flush) < every:
            return
        self._last_flush = now
        delta = {**self._fixed, **self.counters}
        with session_scope(self.cfg) as s:
            s.execute(
                text("UPDATE crawl_runs SET stats = stats || CAST(:d AS jsonb) WHERE id = :i"),
                {"d": json.dumps(delta, ensure_ascii=False, default=str), "i": str(self.run_id)},
            )

    def finish(self, status: str, **extra: Any) -> None:
        self.counters.update(extra)
        delta = {**self._fixed, **self.counters}
        with session_scope(self.cfg) as s:
            s.execute(
                text(
                    "UPDATE crawl_runs SET status = :st, finished_at = now(), "
                    "stats = stats || CAST(:d AS jsonb) WHERE id = :i"
                ),
                {
                    "st": status,
                    "d": json.dumps(delta, ensure_ascii=False, default=str),
                    "i": str(self.run_id),
                },
            )


@contextlib.contextmanager
def crawl_run(
    source: str,
    kind: str,
    cfg: Config,
    *,
    argv: list[str] | None = None,
    run_id: uuid.UUID | str | None = None,
) -> Iterator[RunHandle]:
    """Open a ``crawl_runs`` row and guarantee it gets closed.

    ``source`` may be a real collector name or one of ``SENTINEL_SOURCES``:
    ``normalize``, ``dedup``, ``load`` and the manual description review all
    open a row. They have to — README section 12 item 3 (the FX rate and the
    date it was applied) and the section 7 "read 20 descriptions" gate are both
    read back out of ``crawl_runs``, and with no rows they render empty and the
    gate can never pass.

    This context manager's ``finally`` is the only writer of ``status``.
    """
    if source not in SENTINEL_SOURCES:
        cfg.source(source)  # raises on an unknown source

    resumed = run_id is not None
    rid = uuid.UUID(str(run_id)) if run_id else uuid.uuid4()
    handle = RunHandle(run_id=rid, source=source, kind=kind, cfg=cfg)
    handle.note("kind", kind)
    handle.note("argv", argv or [])
    handle.note("config_sha256", cfg.sha256)
    started = time.monotonic()

    with session_scope(cfg) as s:
        if resumed:
            row = s.execute(
                text("SELECT stats FROM crawl_runs WHERE id = :i"), {"i": str(rid)}
            ).first()
            if row is None:
                raise ConfigError(f"no crawl_runs row with id {rid}")
            stored = dict(row[0] or {})
            resumed_at = list(stored.get("resumed_at") or [])
            resumed_at.append(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
            # Seed in-memory counters from the stored row (see RunHandle docstring).
            for k, v in stored.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    handle.counters[k] = v
            handle.counters["error_samples"] = list(stored.get("error_samples") or [])
            handle.counters["resumed_at"] = resumed_at
            s.execute(
                text(
                    "UPDATE crawl_runs SET status = 'running', finished_at = NULL WHERE id = :i"
                ),
                {"i": str(rid)},
            )
            log.info("resuming run %s (%s counters carried over)", rid, len(handle.counters))
        else:
            s.execute(
                text(
                    "INSERT INTO crawl_runs (id, source, status, stats) "
                    "VALUES (:i, :s, 'running', CAST(:d AS jsonb))"
                ),
                {
                    "i": str(rid),
                    "s": source,
                    "d": json.dumps({"kind": kind}, ensure_ascii=False),
                },
            )
            log.info("run %s started (%s / %s)", rid, source, kind)

    try:
        yield handle
    except KeyboardInterrupt:
        handle.finish("failed", interrupted=True, duration_s=round(time.monotonic() - started, 1))
        raise
    except Exception as exc:
        handle.finish(
            "failed",
            fatal=f"{type(exc).__name__}: {exc}",
            traceback_tail=traceback.format_exc()[-2000:],
            duration_s=round(time.monotonic() - started, 1),
        )
        raise
    else:
        if shutdown.requested:
            # A flag-only SIGINT handler with no post-loop check leaves an
            # interrupted run marked 'done', so a crawl that stopped at page
            # 1,200 of 4,000 is indistinguishable from a complete one and is
            # never offered for resume.
            handle.finish(
                "failed", interrupted=True, duration_s=round(time.monotonic() - started, 1)
            )
            log.warning("interrupted; resume with --run-id %s", rid)
            raise SystemExit(exitcodes.INTERRUPTED)
        handle.finish("done", duration_s=round(time.monotonic() - started, 1))


def stale_running_runs(cfg: Config, *, older_than_hours: int = 6) -> list[dict[str, Any]]:
    """Runs still marked ``running`` long after they started.

    Deliberately not auto-repaired: flipping them to ``failed`` would destroy
    the only evidence that the process was killed rather than finished.
    ``report`` prints them with the ``--run-id`` needed to resume.
    """
    with session_scope(cfg) as s:
        rows = s.execute(
            text(
                """
                SELECT id, source, started_at, stats->>'kind' AS kind
                  FROM crawl_runs
                 WHERE status = 'running'
                   AND started_at < now() - make_interval(hours => :h)
                   AND source <> ALL(:sentinels)
                 ORDER BY started_at
                """
            ),
            {"h": older_than_hours, "sentinels": list(SENTINEL_SOURCES)},
        ).mappings().all()
    return [dict(r) for r in rows]


# =============================================================================
# source_state latch (spec sections 1, 9, 13)
# =============================================================================
def is_source_blocked(cfg: Config, source: str) -> dict[str, Any] | None:
    with session_scope(cfg) as s:
        row = s.execute(
            text(
                "SELECT source, blocked_at, reason FROM source_state "
                "WHERE source = :s AND blocked_at IS NOT NULL AND cleared_at IS NULL"
            ),
            {"s": source},
        ).mappings().first()
    return dict(row) if row else None


def latch_source_blocked(cfg: Config, source: str, reason: dict[str, Any]) -> None:
    with session_scope(cfg) as s:
        s.execute(
            text(
                """
                INSERT INTO source_state (source, blocked_at, reason, updated_at)
                VALUES (:s, now(), CAST(:r AS jsonb), now())
                ON CONFLICT (source) DO UPDATE
                   SET blocked_at = now(),
                       reason     = EXCLUDED.reason,
                       cleared_by = NULL,
                       cleared_at = NULL,
                       updated_at = now()
                """
            ),
            {"s": source, "r": json.dumps(reason, ensure_ascii=False, default=str)},
        )
    log.error(
        "source %s latched as BLOCKED: %s. Not retrying. Spec section 1: do not "
        "circumvent anti-bot; switch to the fallback.",
        source,
        reason,
    )


def unblock_source(cfg: Config, source: str, reason: str) -> bool:
    """Clear the latch. Requires a human reason — never a timer.

    There is deliberately no cooldown: an automatic retry of a source that just
    served a CAPTCHA is mechanically indistinguishable from probing anti-bot.
    """
    with session_scope(cfg) as s:
        res = s.execute(
            text(
                "UPDATE source_state SET cleared_at = now(), cleared_by = :by, "
                "updated_at = now() WHERE source = :s AND cleared_at IS NULL"
            ),
            {"s": source, "by": reason},
        )
    return res.rowcount > 0


# =============================================================================
# advisory lock
# =============================================================================
@contextlib.contextmanager
def command_lock(cfg: Config, key: str) -> Iterator[None]:
    """Prevent two copies of the same command from racing each other.

    The lock is session-scoped in Postgres, so it is taken on a **dedicated**
    connection held open for the whole command. Taken on a pooled session it
    would be released the moment that connection went back to the pool, and a
    second process could start while the first was still running.
    """
    engine = get_engine(cfg)
    # AUTOCOMMIT so the lock-holding connection does not also hold an open
    # transaction for the two hours a crawl takes.
    conn = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    try:
        got = conn.execute(
            text("SELECT pg_try_advisory_lock(hashtext(:k))"), {"k": key}
        ).scalar()
        if not got:
            conn.close()
            raise ConfigError(
                f"another process already holds the {key!r} lock. "
                "Wait for it to finish, or check for a stale run with `cli report`."
            )
        yield
    finally:
        with contextlib.suppress(Exception):
            conn.execute(text("SELECT pg_advisory_unlock(hashtext(:k))"), {"k": key})
        with contextlib.suppress(Exception):
            conn.close()
