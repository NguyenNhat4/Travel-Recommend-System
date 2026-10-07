"""Durable quota cooldown for indexing, separate from successful catalog writes.

The embedder follows EMBED_PROVIDER (backend Settings): `local` e5-small runs in-process and never hits a quota, so the
cooldown only engages for the `cohere` rollback provider (HTTP 429).
"""
from __future__ import annotations

import fcntl
import json
import re
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import log

_MUTEX = threading.Lock()


def rate_limit(exc: BaseException) -> tuple[bool, float]:
    """Inspect the exception chain without persisting response bodies or credentials."""
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        response = getattr(exc, 'response', None)
        if response is not None and getattr(response, 'status_code', None) == 429:
            try:
                retry = max(0.0, float(response.headers.get('Retry-After', 0)))
            except (TypeError, ValueError):
                retry = 0.0
            return True, retry
        if re.search(r'\b429\b|too many requests', str(exc), re.I):
            return True, 0.0
        exc = exc.__cause__ or exc.__context__
    return False, 0.0


def pending(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return {}


def due(path: Path, now: datetime | None = None) -> bool:
    state = pending(path)
    return bool(state.get('pending')) and datetime.fromisoformat(state['retryAfter']) <= (now or datetime.now(timezone.utc))


def guarded_index(path: Path, fn, *, cooldown_seconds: int = 3600,
                  now: datetime | None = None) -> dict:
    """Only quota exhaustion is recoverable here; other errors keep their failure semantics."""
    now = now or datetime.now(timezone.utc)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _MUTEX, path.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = pending(path)
        if state.get('pending') and datetime.fromisoformat(state['retryAfter']) > now:
            return {**state, 'deferred': True}
        try:
            report = fn() or {}
        except Exception as exc:
            limited, retry_after = rate_limit(exc)
            if not limited:
                raise
            failures = int(state.get('rateLimitFailures', 0)) + 1
            # Repeated 429s back off across cron ticks, up to 24 hours. Retry-After wins.
            seconds = max(retry_after, min(max(60, cooldown_seconds) * 2 ** min(failures - 1, 8), 86400))
            report = {'pending': True, 'deferred': True, 'reason': 'provider_rate_limit',
                      'rateLimitFailures': failures, 'retryAfter': (now + timedelta(seconds=seconds)).isoformat(),
                      'lastAttemptAt': now.isoformat()}
            temp = path.with_suffix('.tmp')
            temp.write_text(json.dumps(report) + '\n')
            temp.replace(path)
            return report
        path.unlink(missing_ok=True)
        return report


def main(argv=None):
    import argparse
    from src.backend.app.core.config import get_settings
    from src.backend.jobs.embed_products import run
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-file', required=True, type=Path)
    args = parser.parse_args(argv)
    log.configure(flow='index')
    report = guarded_index(args.state_file, lambda: run(settings=get_settings()))
    with log.use_stream(sys.stderr):  # stdout = báo cáo JSON của lệnh
        log.emit('index.backlog.report', 'index.backlog.report', report=report)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
