"""Log JSON một dòng ra stdout theo `docs/spec/logging-schema.md`.

Chỉ dùng `logging` chuẩn. Ba phần:
  * `configure_logging()` — gắn formatter JSON vào root logger, kéo `uvicorn`/`uvicorn.error` qua cùng formatter.
  * `log_event()` — ghi một sự kiện có tên `domain.action`; chỉ nhận trường khai báo trong `EVENT_FIELDS` (allowlist).
  * `redact()` — che khoá nhạy cảm và mẫu giá trị (email, thẻ, JWT, DSN...). Mọi giá trị đi qua đây trước khi ghi.

Không import FastAPI (docs/prd/architecture.md §2, quy tắc 9): application và agents gọi được `log_event`.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import sys
import traceback
from datetime import datetime, timedelta, timezone
from typing import Any

SERVICE = "backend"
# Asia/Ho_Chi_Minh không có giờ mùa hè: offset cố định +07:00, không cần tzdata trong image slim.
VN_TZ = timezone(timedelta(hours=7))
MASK = "***"
MAX_BODY_BYTES = 2048
MAX_STACK_CHARS = 4000

_LEVELS = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING, "ERROR": logging.ERROR,
           "CRITICAL": logging.CRITICAL}

# --- Che dữ liệu (schema §4) -----------------------------------------------------------------------

#: Khoá bị che khi tên khoá (không phân biệt hoa thường) CHỨA một trong các chuỗi này.
SENSITIVE_KEYS = (
    "password", "passwd", "token", "secret", "authorization", "cookie", "api_key", "apikey", "dsn", "connection",
    "email", "phone", "mobile", "passport", "idnumber", "cccd", "dob", "birth", "address", "card", "cvv", "cvc",
    "iban", "signature", "client_secret",
)
#: `name` chỉ bị che khi nằm dưới nhánh hành khách / liên hệ.
_PERSON_BRANCHES = ("traveler", "traveller", "passenger", "contact", "guest", "customer")

_SCHEME_CREDENTIALS = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*)://[^\s/@:]+:[^\s@]*@")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]*")
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_API_KEY = re.compile(r"\b(?:sk|pk|rk|whsec)_[A-Za-z0-9_]{6,}")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
_CARD_SPACED = re.compile(r"(?<![\d.])(?:\d[ -]?){12,18}\d(?![\d.])")
_PHONE_VN = re.compile(r"(?<![\w.])(?:\+84|0)(?:[ .-]?\d){8,10}(?![\w.])")
_KEY_VALUE = re.compile(
    r"(?i)\b(password|passwd|pwd|secret|token|access_token|refresh_token|api[_-]?key|authorization|cookie|"
    r"client_secret|stripe-signature)(\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;&}]+)")


def mask_text(value: str) -> str:
    """Che mẫu giá trị trong chuỗi tự do (thông điệp, stack, giá trị trong body)."""
    if not value:
        return value
    value = _SCHEME_CREDENTIALS.sub(lambda m: f"{m.group(1)}://{MASK}@", value)
    value = _KEY_VALUE.sub(lambda m: f"{m.group(1)}{m.group(2)}{MASK}", value)
    value = _BEARER.sub(f"Bearer {MASK}", value)
    value = _JWT.sub(MASK, value)
    value = _API_KEY.sub(MASK, value)
    value = _EMAIL.sub(MASK, value)
    value = _CARD_SPACED.sub(MASK, value)
    value = _PHONE_VN.sub(MASK, value)
    return value


def _sensitive_key(key: str, path: tuple[str, ...]) -> bool:
    low = key.lower()
    if any(part in low for part in SENSITIVE_KEYS):
        return True
    return low in ("name", "fullname", "full_name", "givennames", "surname", "title") and any(
        any(branch in p.lower() for branch in _PERSON_BRANCHES) for p in path)


def redact(value: Any, _path: tuple[str, ...] = ()) -> Any:
    """Bản sao đã che của `value`: che theo khoá, rồi theo mẫu giá trị. Không sửa đối tượng gốc."""
    if isinstance(value, dict):
        return {str(k): (MASK if _sensitive_key(str(k), _path) else redact(v, (*_path, str(k))))
                for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [redact(v, _path) for v in value]
    if isinstance(value, bool) or value is None or isinstance(value, float):
        return value
    if isinstance(value, int):
        return MASK if 13 <= len(str(abs(value))) <= 19 else value
    if isinstance(value, (bytes, bytearray)):
        return redact(bytes(value).decode("utf-8", "replace"), _path)
    return mask_text(str(value))


def hash_user_id(user_id: str | None) -> str | None:
    """Băm một chiều (sha256 + muối, 16 hex đầu) để nối log theo người dùng mà không lộ định danh."""
    if not user_id:
        return None
    salt = os.environ.get("LOG_HASH_SALT", "vota-log")
    return hashlib.sha256(f"{salt}:{user_id}".encode("utf-8")).hexdigest()[:16]


def truncate_json(value: Any, limit: int = MAX_BODY_BYTES) -> tuple[str, bool]:
    """Chuỗi JSON của `value`, cắt ở `limit` byte; trả cờ `truncated`."""
    text = json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))
    raw = text.encode("utf-8")
    if len(raw) <= limit:
        return text, False
    return raw[:limit].decode("utf-8", "ignore"), True


# --- Allowlist trường theo sự kiện (schema §2) -----------------------------------------------------

_COMMON = {"message"}
_BOOKING = {"booking_ref", "booking_id", "amount_vnd", "item_count"}
_ASSISTANT = {"conversation_id", "run_id", "transport"}
EVENT_FIELDS: dict[str, set[str]] = {
    "http.request": {"method", "route", "status", "duration_ms", "user_kind", "user_id_hash", "request_bytes",
                     "response_bytes", "query", "request_body", "response_body", "body_truncated", "streaming",
                     "error.code"},
    "auth.login": {"outcome", "user_id_hash", "reason", "amr"},
    "auth.register": {"outcome", "user_id_hash"},
    "auth.session.revoke": {"outcome"},
    "auth.password.change": {"outcome", "user_id_hash", "revoked_tokens"},
    "auth.mfa.verify": {"outcome", "user_id_hash"},
    "search.run": {"mode", "query_text", "result_count", "engine_ms", "degraded", "total"},
    "search.embed.failed": {"error_kind"},
    "recsys.recommend": {"persona", "branch", "result_count", "duration_ms", "cache", "stage_ms", "events_read"},
    "recsys.fallback": {"reason", "persona"},
    "recsys.explore_fill": {"filled"},
    "cart.item.add": {"product_id", "quantity", "using_date", "owner_kind"},
    "cart.item.remove": {"cart_item_id", "owner_kind"},
    "draft.create": {"draft_id", "item_count", "owner_kind"},
    "draft.update": {"draft_id", "item_count", "owner_kind"},
    "guest.merge": {"item_count", "user_id_hash"},
    "booking.create_hold": _BOOKING | {"adults", "children"},
    "booking.checkout.start": _BOOKING,
    "booking.cdp.record_purchase": _BOOKING | {"outcome", "duration_ms"},
    "booking.commit": _BOOKING | {"outcome"},
    "booking.cdp.cancel_purchase": _BOOKING | {"outcome"},
    "booking.cancel": _BOOKING | {"decision"},
    "booking.reconcile.deferred": _BOOKING | {"reason"},
    "booking.reconcile.failed": _BOOKING | {"reason"},
    "payment.webhook.received": {"stripe_event_type", "event_id"},
    "payment.signature.invalid": {"client_ip_prefix"},
    "payment.settled": _BOOKING | {"event_id"},
    "payment.failed": _BOOKING | {"decline_code", "failed_attempts", "event_id"},
    "assistant.run.start": _ASSISTANT,
    "assistant.node": _ASSISTANT | {"node", "duration_ms", "outcome", "sequence"},
    "assistant.tool.call": _ASSISTANT | {"tool", "duration_ms", "outcome", "error_code"},
    "assistant.llm.call": _ASSISTANT | {"schema", "duration_ms", "outcome"},
    "assistant.grounding": _ASSISTANT | {"checked", "violations", "issues"},
    "assistant.run.end": _ASSISTANT | {"status", "http_status", "duration_ms", "retry_count"},
    "assistant.stream.open": _ASSISTANT,
    "assistant.stream.close": _ASSISTANT | {"outcome", "duration_ms"},
    "events.ingest": {"count", "cdp_ok", "event_name"},
    "app.startup": {"app", "env", "stage", "adapter", "mode", "search_units", "workers"},
    "app.shutdown": {"stage"},
    "db.unavailable": {"component", "error_kind"},
    "readiness.degraded": {"recsys", "db", "ready"},
    "log": {"logger"},
}

_EVENT_NAME = re.compile(r"^([a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+)(?:\s|$)")


def _stringify_error(exc_info) -> dict[str, str]:
    etype, evalue, tb = exc_info
    stack = "".join(traceback.format_exception(etype, evalue, tb))
    return {"error.type": getattr(etype, "__name__", str(etype)),
            "error.message": mask_text(str(evalue))[:1000],
            "error.stack": mask_text(stack)[-MAX_STACK_CHARS:]}


class JsonFormatter(logging.Formatter):
    """Một dòng JSON: ts (+07:00, ms), ts_utc, severity, service, event, request_id, message, error.*."""

    def format(self, record: logging.LogRecord) -> str:
        from src.backend.app.core.request_context import current_request_id  # tránh vòng import lúc nạp module

        moment = datetime.fromtimestamp(record.created, tz=timezone.utc)
        explicit = getattr(record, "event", None)
        message = record.getMessage()
        event = explicit
        fields: dict[str, Any] = dict(getattr(record, "fields", None) or {})
        if event is None:
            # Log cũ dạng "startup.recsys.ready search_units=3": tên sự kiện là từ đầu có dấu chấm.
            match = _EVENT_NAME.match(message)
            event = match.group(1) if match else "log"
            if event == "log":
                fields["logger"] = record.name
        payload: dict[str, Any] = {
            "ts": moment.astimezone(VN_TZ).isoformat(timespec="milliseconds"),
            "ts_utc": moment.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "severity": record.levelname if record.levelname in _LEVELS else "INFO",
            "service": SERVICE,
            "event": event,
        }
        rid = fields.pop("request_id", None) or current_request_id()
        if rid:
            payload["request_id"] = rid
        if explicit is None or message != explicit:
            payload["message"] = mask_text(message)[:1000]
        payload.update(fields)
        if record.exc_info and record.exc_info[0] is not None:
            payload.update(_stringify_error(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, default=str, separators=(",", ":"))


def log_event(logger: logging.Logger | str, event: str, level: str = "INFO", message: str | None = None,
              exc_info: Any = None, **fields: Any) -> None:
    """Ghi một sự kiện. Trường ngoài allowlist của `event` bị bỏ; giá trị đã qua `redact()`.

    `request_id` mặc định lấy từ `current_request_id()`. `level` theo tên Cloud Logging (INFO, WARNING, ERROR...).
    """
    log = logging.getLogger(logger) if isinstance(logger, str) else logger
    severity = _LEVELS.get(level.upper(), logging.INFO)
    if not log.isEnabledFor(severity):
        return
    allowed = EVENT_FIELDS.get(event, set()) | _COMMON | {"request_id"}
    clean = {k: redact(v, (k,)) if not isinstance(v, str) else mask_text(v)
             for k, v in fields.items() if v is not None and k in allowed and k != "message"}
    text = mask_text(message) if message else event
    if exc_info is True:
        exc_info = sys.exc_info()
    log.log(severity, text, exc_info=exc_info, extra={"event": event, "fields": clean})


def log_bodies_enabled() -> bool:
    return os.environ.get("LOG_BODIES", "true").strip().lower() in ("1", "true", "yes", "on")


def configure_logging() -> None:
    """Gọi một lần ở đầu `main.py`. `LOG_LEVEL` mặc định INFO; gọi lại thì thay handler, không nhân đôi dòng."""
    level = _LEVELS.get(os.environ.get("LOG_LEVEL", "INFO").strip().upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)
    # uvicorn tự cấu hình handler riêng (định dạng chữ thường): bỏ để mọi dòng đi qua formatter JSON.
    for name in ("uvicorn", "uvicorn.error"):
        lg = logging.getLogger(name)
        lg.handlers = []
        lg.propagate = True
        lg.setLevel(level)
    access = logging.getLogger("uvicorn.access")  # thay bằng sự kiện `http.request`
    access.handlers = []
    access.propagate = False
    access.disabled = True
    for noisy in ("httpx", "httpcore", "urllib3"):  # URL ngoài có thể mang key/token trong query
        logging.getLogger(noisy).setLevel(logging.WARNING)
