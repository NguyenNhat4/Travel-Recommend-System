"""Raw response cache: ``data/raw/<source>/<yyyy-mm-dd>/<sha256>.<ext>.gz``.

Spec section 0 item 2 and the handbook's strongest advice: cache every raw page
to disk **before** parsing it. When the parser turns out to be wrong on Thursday
— and it will — re-parsing is free instead of a second crawl at 0.5 rps.

Two invariants this module enforces rather than documents:

1. ``content_path`` is always a POSIX-relative path. On Windows
   ``str(Path('data/raw') / ...)`` produces backslashes; stored that way the
   same rows are unreadable from the collector container, which mounts
   ``./data-collection/data`` at ``/app/data``.
2. Writes are atomic (temp file + ``os.replace``). A half-written ``.gz`` that a
   ``raw_pages`` row points at is worse than no file, because it looks fetched.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

log = logging.getLogger("cache")

GZIP_LEVEL = 6  # 9 costs noticeably more CPU for a few percent on HTML

_EXT_BY_TYPE = (
    ("json", ".json.gz"),
    ("xml", ".xml.gz"),
    ("html", ".html.gz"),
    ("text/plain", ".txt.gz"),
)


@dataclass(frozen=True)
class CacheWrite:
    content_path: str
    """POSIX-relative, e.g. ``raw/vinpearl/2026-09-15/ab12...ef.html.gz``."""
    sha256: str
    raw_bytes: int
    stored_bytes: int
    deduped: bool
    """True when an identical body was already cached (same sha, same day)."""


class Cache:
    def __init__(self, data_root: str | Path) -> None:
        self.data_root = Path(data_root)

    # -- paths -------------------------------------------------------------
    def absolute(self, content_path: str) -> Path:
        """Resolve a stored ``content_path`` back to a real file.

        ``PurePosixPath`` on the way in, so a path written on Linux resolves on
        Windows and vice versa.
        """
        return self.data_root / PurePosixPath(content_path)

    def _relative(self, p: Path) -> str:
        return p.relative_to(self.data_root).as_posix()

    @staticmethod
    def extension_for(content_type: str | None, url: str = "") -> str:
        ct = (content_type or "").lower()
        for needle, ext in _EXT_BY_TYPE:
            if needle in ct:
                return ext
        lowered = url.lower()
        if lowered.endswith((".json",)):
            return ".json.gz"
        if lowered.endswith((".xml", ".xml.gz")) or "sitemap" in lowered:
            return ".xml.gz"
        return ".html.gz"

    # -- write -------------------------------------------------------------
    def write(
        self,
        content: bytes,
        *,
        source: str,
        content_type: str | None = None,
        url: str = "",
        day: str | None = None,
    ) -> CacheWrite:
        """Gzip ``content`` to disk and return its identity.

        The filename is the sha256 of the **uncompressed** body, so an identical
        page fetched twice on the same day maps to one file. That is a
        deduplication, not an error: both ``raw_pages`` rows point at it, and
        re-parsing either reproduces the same bytes.
        """
        if not isinstance(content, (bytes, bytearray)):
            raise TypeError(f"cache.write needs bytes, got {type(content).__name__}")
        content = bytes(content)
        sha = hashlib.sha256(content).hexdigest()
        day = day or time.strftime("%Y-%m-%d", time.gmtime())
        ext = self.extension_for(content_type, url)

        directory = self.data_root / "raw" / source / day
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{sha}{ext}"

        if target.exists():
            return CacheWrite(
                content_path=self._relative(target),
                sha256=sha,
                raw_bytes=len(content),
                stored_bytes=target.stat().st_size,
                deduped=True,
            )

        tmp = directory / f".{sha}{ext}.{os.getpid()}.tmp"
        try:
            # The file object is opened and closed by us, not by GzipFile:
            # GzipFile only closes a fileobj it opened itself, and on Windows
            # os.replace fails while a handle is still open.
            # mtime=0 keeps the gzip header byte-stable for a given body, which
            # makes committed test fixtures reproducible.
            with tmp.open("wb") as fh:
                with gzip.GzipFile(fileobj=fh, mode="wb", compresslevel=GZIP_LEVEL, mtime=0) as gz:
                    gz.write(content)
            os.replace(tmp, target)
        finally:
            tmp.unlink(missing_ok=True)

        return CacheWrite(
            content_path=self._relative(target),
            sha256=sha,
            raw_bytes=len(content),
            stored_bytes=target.stat().st_size,
            deduped=False,
        )

    # -- read --------------------------------------------------------------
    def read(self, content_path: str) -> bytes:
        """Read cached bytes by the path stored in ``raw_pages.content_path``.

        Note ``parse`` enumerates work from ``raw_pages`` rows, never by walking
        this directory: the row carries the url, the source, the quote context
        and the http status, none of which are recoverable from a filename.
        """
        p = self.absolute(content_path)
        if not p.exists():
            raise FileNotFoundError(
                f"cached page missing: {content_path} (looked in {p}). "
                "If the raw cache was cleared, re-run fetch; if the DB was "
                "restored from elsewhere, run `cli adopt-orphans`."
            )
        with gzip.open(p, "rb") as fh:
            return fh.read()

    def read_text(self, content_path: str, encoding: str = "utf-8") -> str:
        return self.read(content_path).decode(encoding, errors="replace")

    def exists(self, content_path: str) -> bool:
        return self.absolute(content_path).exists()

    # -- crash consistency -------------------------------------------------
    def write_pending_marker(self, cw: CacheWrite, meta: dict) -> None:
        """Record that a file exists whose ``raw_pages`` row was not written.

        ``fetch`` writes the ``.gz`` first and the DB row second — that ordering
        is what makes the cache trustworthy. The gap between them is the failure
        nobody plans for: a laptop that sleeps mid-crawl, or
        ``docker compose restart`` while 0.5 rps of work is in flight. Without
        this marker those bytes are unreferenced forever and
        ``cli adopt-orphans`` has no url to attach them to.
        """
        p = self.absolute(cw.content_path).with_suffix(".pending.json")
        payload = {"content_path": cw.content_path, "sha256": cw.sha256, **meta}
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def clear_pending_marker(self, content_path: str) -> None:
        self.absolute(content_path).with_suffix(".pending.json").unlink(missing_ok=True)

    def iter_pending_markers(self):
        root = self.data_root / "raw"
        if not root.exists():
            return
        for p in root.rglob("*.pending.json"):
            try:
                yield json.loads(p.read_text(encoding="utf-8")), p
            except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover
                log.warning("unreadable pending marker %s: %s", p, exc)

    # -- housekeeping ------------------------------------------------------
    def iter_files(self):
        root = self.data_root / "raw"
        if not root.exists():
            return
        for p in root.rglob("*.gz"):
            yield self._relative(p)

    def total_bytes(self) -> int:
        root = self.data_root / "raw"
        if not root.exists():
            return 0
        return sum(p.stat().st_size for p in root.rglob("*.gz"))


def strip_nul(data: bytes) -> bytes:
    """Remove NUL bytes.

    Real crawled HTML contains stray ``\\x00``; PostgreSQL rejects it in ``text``
    and ``jsonb`` and psycopg raises before the insert. Stripping at the
    boundary is cheaper than discovering it 1,800 pages in.
    """
    return data.replace(b"\x00", b"") if b"\x00" in data else data
