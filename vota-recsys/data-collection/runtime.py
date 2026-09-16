"""Process-wide runtime concerns: encoding, logging, and cooperative shutdown.

This module exists separately from cli.py on purpose. The spec's entry point is
`python -m cli`, which imports the module twice (once as ``__main__``, once as
``cli``). Module-level mutable state in cli.py would therefore exist in two
copies, and a shutdown flag set in one would be invisible to the other.
"""

from __future__ import annotations

import logging
import logging.config
import logging.handlers
import os
import signal
import sys
import threading
import time
from pathlib import Path

log = logging.getLogger("runtime")


# =============================================================================
# encoding
# =============================================================================
def setup_encoding() -> None:
    """Force UTF-8 on stdout and stderr.

    On Windows ``locale.getpreferredencoding(False)`` is ``cp1252`` and
    ``sys.flags.utf8_mode`` is 0 unless ``PYTHONUTF8=1`` is set. With a real
    console attached Python uses the wide-char console writer and survives; the
    moment output is piped or redirected it falls back to cp1252 and any
    Vietnamese character raises ``UnicodeEncodeError``. That kills
    ``python -m cli report > report.txt`` and every ``| Select-String``.

    stdout is ``strict`` so machine-readable output is never silently corrupted;
    stderr is ``replace`` so logging can never be the thing that kills a
    two-hour crawl.
    """
    for stream, errors in ((sys.stdout, "strict"), (sys.stderr, "replace")):
        try:
            stream.reconfigure(encoding="utf-8", errors=errors, newline="\n")
        except (AttributeError, ValueError):  # pragma: no cover - non-TextIO stream
            pass


# =============================================================================
# cooperative shutdown
# =============================================================================
class _Shutdown:
    """Ctrl-C sets a flag; the worker loop finishes the page it is on.

    Raising KeyboardInterrupt inside a worker would abandon the write ordering
    that makes the cache trustworthy (bytes to disk, then the raw_pages row,
    then the target status). The flag lets the in-flight item complete, which is
    at most one page at 0.5 rps.

    The caller MUST check :meth:`requested` after its loop and finish the run as
    failed/interrupted. A flag-only handler with no post-loop check leaves an
    interrupted run marked ``done``, which is worse than crashing: a crawl that
    stopped at page 1,200 of 4,000 becomes indistinguishable from a complete one
    and is never offered for resume.
    """

    def __init__(self) -> None:
        self._event = threading.Event()
        self._count = 0
        self._installed = False

    def install(self) -> None:
        if self._installed:
            return
        self._installed = True
        try:
            signal.signal(signal.SIGINT, self._handle)
            if hasattr(signal, "SIGTERM"):
                signal.signal(signal.SIGTERM, self._handle)
        except ValueError:  # pragma: no cover - not the main thread
            pass

    def _handle(self, signum, frame) -> None:  # noqa: ANN001, ARG002
        self._count += 1
        self._event.set()
        if self._count == 1:
            print(
                "\n[shutdown] finishing the current item, then stopping. "
                "Ctrl-C again to abort immediately.",
                file=sys.stderr,
                flush=True,
            )
        else:
            print("\n[shutdown] aborting now.", file=sys.stderr, flush=True)
            raise KeyboardInterrupt

    @property
    def requested(self) -> bool:
        return self._event.is_set()

    def wait(self, seconds: float) -> bool:
        """Sleep, but wake early on Ctrl-C. Returns True if shutdown was requested.

        Used by the rate limiter: a plain ``time.sleep(2)`` inside a worker
        thread on Windows is not interruptible, so a Ctrl-C during a rate-limit
        pause would appear to hang.
        """
        return self._event.wait(seconds)

    def reset(self) -> None:
        self._event.clear()
        self._count = 0


shutdown = _Shutdown()


# =============================================================================
# logging
# =============================================================================
def setup_logging(
    *,
    command: str,
    level: str = "INFO",
    to_file: bool = True,
    log_dir: str | Path = "logs",
    max_bytes: int = 20_000_000,
    backup_count: int = 5,
    verbose: int = 0,
    quiet: bool = False,
) -> None:
    """Configure stdlib logging. No rich, no tqdm, no loguru.

    Logs go to **stderr**, never stdout, so ``report --json`` stays pipeable.

    The log filename includes the PID because two ``fetch`` processes for
    different sources are expected to run at once, and two processes sharing one
    RotatingFileHandler filename hit ``PermissionError: [WinError 32]`` on every
    rollover once the file passes max_bytes.
    """
    if quiet:
        console_level = "WARNING"
    elif verbose >= 1:
        console_level = "DEBUG"
    else:
        console_level = level.upper()

    handlers: dict = {
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
            "formatter": "console",
            "level": console_level,
        }
    }
    root_handlers = ["console"]

    if to_file:
        d = Path(log_dir)
        d.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d", time.gmtime())
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(d / f"{command}-{stamp}-{os.getpid()}.log"),
            "maxBytes": max_bytes,
            "backupCount": backup_count,
            "encoding": "utf-8",  # diacritics in log files
            "formatter": "file",
            "level": "DEBUG",
            "delay": True,
        }
        root_handlers.append("file")

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "console": {
                    "format": "%(asctime)s %(levelname)-7s %(name)-14s %(message)s",
                    "datefmt": "%H:%M:%S",
                },
                "file": {
                    "format": (
                        "%(asctime)s %(levelname)-7s %(name)-14s "
                        "%(threadName)-10s %(message)s"
                    ),
                },
            },
            "handlers": handlers,
            "loggers": {
                # httpx logs one INFO line per request; we log our own, richer one.
                "httpx": {"level": "WARNING"},
                "httpcore": {"level": "WARNING"},
                "sqlalchemy.engine": {"level": "INFO" if verbose >= 2 else "WARNING"},
            },
            "root": {"handlers": root_handlers, "level": "DEBUG"},
        }
    )
    logging.captureWarnings(True)
    # Log timestamps and TIMESTAMPTZ values are then both UTC.
    logging.Formatter.converter = time.gmtime
    _install_secret_filter()


class _SecretFilter(logging.Filter):
    """Redact credential values that reach a log record by any path."""

    def __init__(self) -> None:
        super().__init__()
        self._secrets = [
            v
            for k, v in os.environ.items()
            if v
            and len(v) >= 8
            and any(t in k.upper() for t in ("SECRET", "PASSWORD", "TOKEN", "CLIENT_ID"))
        ]

    def filter(self, record: logging.LogRecord) -> bool:
        if not self._secrets:
            return True
        try:
            msg = record.getMessage()
        except Exception:  # pragma: no cover - broken format args
            return True
        redacted = msg
        for s in self._secrets:
            redacted = redacted.replace(s, "***REDACTED***")
        if redacted != msg:
            record.msg = redacted
            record.args = ()
        return True


def _install_secret_filter() -> None:
    f = _SecretFilter()
    for h in logging.getLogger().handlers:
        h.addFilter(f)
