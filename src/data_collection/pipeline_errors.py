"""Phân loại lỗi của job cào/chuẩn hoá/nạp và chiến thuật cho từng loại (CP3 của
docs/plan/2026-09-28-normalize-on-dinh-theo-buoc.md).

| Loại        | Nhận ra từ                                                        | Chiến thuật                              |
|-------------|-------------------------------------------------------------------|------------------------------------------|
| transient   | timeout, mất kết nối, HTTP 429/5xx, SQLite "database is locked"   | thử lại, chờ tăng dần                    |
| blocked     | crawl.py mã 75, captcha/challenge, "bị chặn", HTTP 403            | không thử lại; đánh dấu nguồn bị chặn, nguồn khác chạy tiếp |
| timeout     | bước cào vượt hạn giờ `timeout.*` / `crawl.maxHours` (P4)          | dừng riêng bước đó, giữ phần đã cào, không thử lại; nguồn khác chạy tiếp |
| code        | TypeError/KeyError/…, quá nhiều bản ghi lỗi khi ánh xạ             | dừng ngay, báo tên bước + traceback      |
| quality     | catalog thiếu nhóm bắt buộc, số dòng tụt mạnh so với lượt trước   | không nạp DB, giữ dữ liệu cũ             |
| infra       | Postgres, Weaviate, Cohere không kết nối được                      | thử lại lâu hơn                          |
| unknown     | không khớp mẫu nào                                                 | dừng (như code), để người vận hành xem   |

Lỗi của từng bản ghi khi ánh xạ không đi qua đây: normalise.RecordGuard ghi chúng vào errors.jsonl.
Số lần thử lại và thời gian chờ nằm trong Cấu hình (`retry.*`).
"""
from __future__ import annotations

import re
import sqlite3

TRANSIENT, BLOCKED, TIMEOUT, CODE, QUALITY, INFRA, UNKNOWN = \
    "transient", "blocked", "timeout", "code", "quality", "infra", "unknown"
LABELS = {TRANSIENT: "lỗi tạm thời", BLOCKED: "bị chặn", TIMEOUT: "quá giờ", CODE: "lỗi code", QUALITY: "chặn chất lượng",
          INFRA: "lỗi hạ tầng", UNKNOWN: "chưa phân loại"}
EXIT_BLOCKED = 75  # crawl.py: bị chặn liên tiếp, đã lưu tiến độ
EXIT_TIMEOUT = 124  # job dừng tiến trình crawl.py vì vượt hạn giờ (cùng mã với lệnh `timeout` của coreutils)


class PipelineError(RuntimeError):
    kind = UNKNOWN
    step_status = "error"  # trạng thái bước trong run.json khi lỗi này thoát khỏi bước


class TransientError(PipelineError):
    kind = TRANSIENT


class BlockedError(PipelineError):
    kind = BLOCKED
    step_status = "blocked"


class StepTimeout(PipelineError):
    """Bước cào vượt hạn giờ: job đã dừng riêng bước đó (P4, docs/plan/2026-09-29-bo-cho-doi-giua-cac-buoc.md)."""
    kind = TIMEOUT
    step_status = "timeout"


class CodeError(PipelineError):
    kind = CODE


class QualityGateError(PipelineError):
    kind = QUALITY


class InfraError(PipelineError):
    kind = INFRA


ERROR_CLASS = {TRANSIENT: TransientError, BLOCKED: BlockedError, TIMEOUT: StepTimeout, CODE: CodeError, QUALITY: QualityGateError,
               INFRA: InfraError, UNKNOWN: PipelineError}

_TRANSIENT = re.compile(r"database is locked|timed? ?out|Timeout|Connection (reset|aborted|refused)|RemoteProtocolError|"
                        r"Temporary failure|Name or service not known|net::ERR_|HTTP (429|5\d\d)\b|trả (429|5\d\d)\b|"
                        r"Too Many Requests|ServerDisconnected|BrokenPipe", re.I)
_BLOCKED = re.compile(r"bị chặn|captcha|challenge|xác minh bạn là con người|HTTP 403\b|trả 403\b|Access Denied|"
                      r"0 nơi lưu trú", re.I)
_CODE = re.compile(r"\b(TypeError|AttributeError|KeyError|NameError|IndexError|ImportError|ModuleNotFoundError|"
                   r"SyntaxError|IndentationError|AssertionError|UnboundLocalError|ZeroDivisionError|"
                   r"RecordErrorRateExceeded)\b")
_EXCEPTION_LINE = re.compile(r"(?:^|\s)((?:[A-Za-z_][\w]*\.)*[A-Za-z_]\w*(?:Error|Exception|Exceeded|Blocked))(?::|$)")


def classify_exit(code: int, tail: list[str]) -> str:
    """Loại lỗi của một tiến trình crawl.py từ mã thoát và các dòng log cuối.

    Dòng exception cuối cùng (traceback) quyết định trước; không có traceback thì xét cả đoạn log cuối."""
    if code == 0:
        return "ok"
    if code == EXIT_BLOCKED:
        return BLOCKED
    if code == EXIT_TIMEOUT:
        return TIMEOUT
    lines = [line for line in tail if line.strip()]
    exception = next((line for line in reversed(lines) if _EXCEPTION_LINE.search(line)), "")
    if exception:
        if _TRANSIENT.search(exception):
            return TRANSIENT
        if _CODE.search(exception):
            return CODE
    text = "\n".join(lines[-40:])
    if _BLOCKED.search(text):
        return BLOCKED
    if _TRANSIENT.search("\n".join(lines[-10:])):
        return TRANSIENT
    return CODE if exception else UNKNOWN


def classify_exception(exc: BaseException) -> str:
    """Loại lỗi của một exception trong tiến trình job (maintain, normalize, validate, nạp DB, index)."""
    if isinstance(exc, PipelineError):
        return exc.kind
    kind = getattr(exc, "pipeline_kind", None)
    if kind:
        return kind
    if isinstance(exc, sqlite3.OperationalError) and "locked" in str(exc):
        return TRANSIENT
    name = f"{type(exc).__module__}.{type(exc).__name__}"
    if name.startswith("psycopg") and type(exc).__name__ in ("LockNotAvailable", "DeadlockDetected", "SerializationFailure"):
        return TRANSIENT
    if name.startswith("psycopg") and type(exc).__name__ == "QueryCanceled":
        return TIMEOUT
    if name.startswith("psycopg") and type(exc).__name__ in ("OperationalError", "InterfaceError", "ConnectionTimeout"):
        return INFRA
    if name.startswith(("httpx.", "httpcore.")):
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status is None or status == 429 or status >= 500:
            return INFRA
        return CODE
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return INFRA
    if type(exc).__name__ == "RecordErrorRateExceeded" or _CODE.search(type(exc).__name__):
        return CODE
    return UNKNOWN


def strategy(kind: str, values: dict) -> dict:
    """Việc cần làm với một loại lỗi: `retry` (kèm số lần, giây chờ lần đầu, hệ số tăng), `skip` hoặc `fail`."""
    if kind == TRANSIENT:
        return {"action": "retry", "retries": int(values["retry.transientAttempts"]),
                "delay": float(values["retry.transientDelay"]), "factor": 2.0}
    if kind == INFRA:
        return {"action": "retry", "retries": int(values["retry.infraAttempts"]),
                "delay": float(values["retry.infraDelay"]), "factor": 2.0}
    if kind in (BLOCKED, TIMEOUT):  # thử lại một bước quá giờ chỉ tốn thêm đúng chừng ấy thời gian
        return {"action": "skip", "retries": 0, "delay": 0.0, "factor": 1.0}
    return {"action": "fail", "retries": 0, "delay": 0.0, "factor": 1.0}


def describe(kind: str) -> str:
    return LABELS.get(kind, kind)
