"""Logger JSON một dòng cho crawler (schema: docs/spec/logging-schema.md, plan: docs/plan/2026-10-06-logging-he-thong.md).

Mỗi sự kiện = một dòng JSON ra stdout của container (Ops Agent đọc): `ts` giờ Hà Nội +07:00, `ts_utc`, `severity`,
`service="crawler"`, `event`, `message`, `run_id`, `flow` (full|daily|index|resume), `step` (tên trong pipeline_graph.py),
`source`. Mọi giá trị đi qua `redact()` trước khi ghi (khoá và mẫu giá trị ở mục 4 của schema).

job.log của lượt KHÔNG đổi: monitor đọc nó bằng regex trên dòng text có giờ + tiền tố `[nhóm]`. Khi stdout là `Tee` của
RunRecorder (fresh_run_log.py), dòng JSON chỉ đi ra luồng gốc (container) còn `message` được ghi vào job.log đúng như
`print` cũ. Ngoài lượt (lệnh `due`, `status`, daily.py…) chỉ có dòng JSON. Lệnh có stdout là dữ liệu cho script khác
(`due` → tên chế độ) gọi `configure(stream=sys.stderr)` để log không lẫn vào stdout.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import sys
import threading
from datetime import datetime, timedelta, timezone

SERVICE = "crawler"
HANOI = timezone(timedelta(hours=7), "Asia/Ho_Chi_Minh")  # VN không có DST; không phụ thuộc tzdata của image
LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
MASK = "***"
FLOWS = ("full", "daily", "index", "resume")

# ---------------------------------------------------------------------------------------------------- redact

SENSITIVE_KEYS = ("password", "passwd", "token", "secret", "authorization", "cookie", "api_key", "apikey", "dsn",
                  "connection", "email", "phone", "mobile", "passport", "idnumber", "cccd", "dob", "birth", "address",
                  "card", "cvv", "cvc", "iban")
_VALUE_PATTERNS = (
    re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*://[^\s/@:]+:[^\s/@]*@[^\s]+"),                   # DSN scheme://user:pass@host
    re.compile(r"eyJ[A-Za-z0-9_\-]{5,}\.[A-Za-z0-9_\-]{5,}(?:\.[A-Za-z0-9_\-]*)?"),         # JWT
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/\-]+=*", re.I),
    re.compile(r"\b(?:sk|pk|rk)_(?:live|test)?_?[A-Za-z0-9]{8,}|\bwhsec_[A-Za-z0-9]{8,}"),  # Stripe
    re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),                        # email
    re.compile(r"(?<![\w.])(?:\+84|0)(?:[\s.\-]?\d){8,10}(?!\d)"),                           # số điện thoại VN
    re.compile(r"(?<!\d)\d{13,19}(?!\d)"),                                                   # số thẻ
    # khoá=giá trị lẫn trong chuỗi: `api_key=abc`, `"token": "abc"`, `password=hunter2`
    re.compile(r"(?i)\b([A-Za-z_\-]*(?:" + "|".join(SENSITIVE_KEYS) + r")[A-Za-z_\-]*)(\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;&\"']+)"),
)
_KV = _VALUE_PATTERNS[-1]
_URL = re.compile(r"https?://[^\s\"'<>)]+")


def _sensitive_key(key: str) -> bool:
    low = key.lower()
    return any(part in low for part in SENSITIVE_KEYS)


def clean_url(url: str) -> str:
    """URL nguồn chỉ giữ `scheme://host/path`: bỏ query, fragment và userinfo (token, key nằm ở đó)."""
    match = re.match(r"^(https?://)(?:[^/@]*@)?([^/?#]*)([^?#]*)", url)
    return f"{match.group(1)}{match.group(2)}{match.group(3)}" if match else url


def redact_text(text: str) -> str:
    text = _URL.sub(lambda m: clean_url(m.group(0)), text)
    for pattern in _VALUE_PATTERNS[:-1]:
        text = pattern.sub(MASK, text)
    return _KV.sub(lambda m: f"{m.group(1)}{m.group(2)}{MASK}", text)


def redact(value, key: str | None = None):
    """Che đệ quy: khoá nhạy cảm → `***`; chuỗi → bỏ query của URL và che mẫu giá trị."""
    if key is not None and _sensitive_key(key) and value not in (None, ""):
        return MASK
    if isinstance(value, dict):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return redact_text(str(value))


# ---------------------------------------------------------------------------------------------------- ngữ cảnh

_lock = threading.Lock()
_ctx = {"run_id": None, "flow": None}
_local = threading.local()          # step/source theo luồng (các nguồn cào chạy song song)
_stream = None                      # None: sys.stdout hiện tại (có thể là Tee của RunRecorder)


def configure(*, run_id=None, flow=None, stream=None, reset: bool = False) -> None:
    """`reset=True` xoá ngữ cảnh lượt (cuối lượt / test)."""
    global _stream
    with _lock:
        if reset:
            _ctx.update(run_id=None, flow=None)
            _stream = None
        if run_id is not None:
            _ctx["run_id"] = run_id
        if flow is not None:
            _ctx["flow"] = flow
        if stream is not None:
            _stream = stream


@contextlib.contextmanager
def use_stream(stream):
    """Tạm đổi luồng ghi (lệnh có stdout là dữ liệu cho script khác ghi log ra stderr)."""
    global _stream
    old, _stream = _stream, stream
    try:
        yield
    finally:
        _stream = old


def _min_level() -> int:
    return LEVELS.get(os.environ.get("LOG_LEVEL", "INFO").strip().upper(), 20)


def current() -> dict:
    return {**_ctx, "step": getattr(_local, "step", None), "source": getattr(_local, "source", None)}


@contextlib.contextmanager
def scope(step: str | None = None, source: str | None = None):
    """Gắn `step`/`source` cho mọi dòng log trong khối (theo luồng)."""
    old = (getattr(_local, "step", None), getattr(_local, "source", None))
    if step is not None:
        _local.step = step
    if source is not None:
        _local.source = source
    try:
        yield
    finally:
        _local.step, _local.source = old


# ---------------------------------------------------------------------------------------------------- ghi


def _timestamps() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    return (now.astimezone(HANOI).isoformat(timespec="milliseconds"),
            now.isoformat(timespec="milliseconds").replace("+00:00", "Z"))


def _write(json_line: str, human: str | None) -> None:
    out = _stream or sys.stdout
    if os.environ.get("CRAWL_LOG_PLAIN") == "1":
        # Tiến trình con (crawl.py, normalise): cha đọc từng dòng, bọc thành JSON `source.output` và ghi job.log.
        # Con in đúng dòng text cũ để không bị bọc hai lớp và để regex của monitor vẫn khớp.
        if human is not None:
            with _lock:
                try:
                    out.write(human + "\n")
                    out.flush()
                except (ValueError, OSError):
                    pass
        return
    with _lock:
        if hasattr(out, "stream_only") and hasattr(out, "file_only"):   # Tee của RunRecorder
            out.stream_only(json_line + "\n")
            if human is not None:
                out.file_only(human + "\n")
            return
        try:
            out.write(json_line + "\n")
            out.flush()
        except (ValueError, OSError):
            pass


def emit(event: str, message: str | None = None, severity: str = "INFO", *, human: str | None = None,
         flow: str | None = None, run_id: str | None = None, step: str | None = None, source: str | None = None,
         error: BaseException | dict | None = None, **fields) -> None:
    """Một dòng JSON. `human`: dòng text ghi vào job.log (mặc định = `message`; monitor đọc dòng này, giữ nguyên chữ).
    Trường truyền thêm (`records`, `duration_ms`, `status`…) được che theo `redact()`."""
    severity = severity.upper()
    if LEVELS.get(severity, 20) < _min_level():
        return
    ctx = current()
    ts, ts_utc = _timestamps()
    record = {"ts": ts, "ts_utc": ts_utc, "severity": severity, "service": SERVICE, "event": event}
    if message is not None:
        record["message"] = redact_text(message)
    for key, value in (("run_id", run_id or ctx["run_id"]), ("flow", flow or ctx["flow"]),
                       ("step", step or ctx["step"]), ("source", source or ctx["source"])):
        if value:
            record[key] = value
    for key, value in fields.items():
        if value is not None and key not in record:
            record[key] = redact(value, key)
    if isinstance(error, dict):
        record["error"] = redact(error, "error_detail")
    elif error is not None:
        import traceback
        stack = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        record["error"] = {"type": type(error).__name__, "message": redact_text(str(error))[:1000],
                           "stack": redact_text(stack)[-4000:]}
    human_line = message if human is None else human
    _write(json.dumps(record, ensure_ascii=False, default=str),
           None if human_line in (None, "") else human_line)


def debug(event, message=None, **kw): emit(event, message, "DEBUG", **kw)
def info(event, message=None, **kw): emit(event, message, "INFO", **kw)
def warning(event, message=None, **kw): emit(event, message, "WARNING", **kw)
def error(event, message=None, **kw): emit(event, message, "ERROR", **kw)


_EVENT_RE = re.compile(r"^(?:\[(?P<group>[a-z_\-]+)\] )?(?P<event>[a-z][a-z0-9_]*(?:\.[a-z0-9_:\-]+)+)\b")
_LEVEL_RE = re.compile(r"^(?:\[[a-z_\-]+\] )?(?:\d{2}:\d{2}:\d{2} )?(WARNING|ERROR|CRITICAL)\b")


def say(line: str, severity: str | None = None, event: str | None = None, **fields) -> None:
    """Thay cho `print(line)`: giữ nguyên dòng cho job.log và phát JSON. Tên sự kiện suy từ từ đầu dạng `a.b.c`
    (`catalog.index.start`, `[trip] catalog.source.timeout …`); dòng tự do là `crawler.output` (nguồn lấy từ tiền tố `[nhóm]`).
    Mức: `WARNING|ERROR|CRITICAL` ở đầu dòng của tiến trình con, hoặc từ khoá `.failed` / `Traceback` → ERROR."""
    line = line.rstrip("\n")
    match = _EVENT_RE.match(line)
    group = None
    if match:
        group = match.group("group")
        event = event or match.group("event")
    else:
        grouped = re.match(r"^\[([a-z_\-]+)\] ", line)
        group = grouped.group(1) if grouped else None
    if severity is None:
        level = _LEVEL_RE.match(line)
        if level:
            severity = level.group(1)
        elif re.search(r"\.failed\b|^Traceback|\bError: ", line):
            severity = "ERROR"
        elif re.search(r"\.timeout\b|\.deferred\b|\.skip\b", line):
            severity = "WARNING"
        else:
            severity = "INFO"
    if group:
        fields.setdefault("source", group)
    emit(event or "crawler.output", line, severity, **fields)


@contextlib.contextmanager
def step(name: str, source: str | None = None, *, human_start: str | None = None, human_end: str | None = None):
    """`step.start` / `step.end` (duration_ms, status ok|error) quanh một khối; lỗi → status error + severity ERROR.
    Dùng ở chỗ không đi qua `RunRecorder.step` (đã gọi hàm này giùm)."""
    import time
    with scope(step=name, source=source):
        started = time.monotonic()
        emit("step.start", human_start if human_start is not None else f"step.start name={name}", human=human_start)
        result = {"status": "ok"}
        try:
            yield result
        except BaseException as exc:
            result["status"] = "error"
            emit("step.end", f"step.end name={name} status=error", "ERROR", human=human_end, error=exc,
                 duration_ms=round((time.monotonic() - started) * 1000), status="error")
            raise
        else:
            emit("step.end", f"step.end name={name} status={result['status']}",
                 human=human_end, duration_ms=round((time.monotonic() - started) * 1000),
                 status=result["status"], records=result.get("records"))
