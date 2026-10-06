"""Middleware HTTP: X-Request-ID, CORS và đo lần gọi web (docs/prd/deployment-plan.md §5)."""
import json
import logging
import time
import uuid
from urllib.parse import parse_qsl

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from src.backend.app.application.telemetry import summarize
from src.backend.app.core.call_context import call_scope
from src.backend.app.core.logging_config import (
    hash_user_id,
    log_bodies_enabled,
    log_event,
    mask_text,
    redact,
    truncate_json,
)
from src.backend.app.core.request_context import (
    REQUEST_ID_HEADER,
    bind_request_id,
    close_actor,
    open_actor,
    reset_request_id,
)

logger = logging.getLogger("backend.http")


def install_request_id(app: FastAPI) -> None:
    """Dùng lại ID của caller hoặc tạo mới, rồi trả lại trong response header."""

    @app.middleware("http")
    async def assign_request_id(request: Request, call_next):
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = incoming[:64] if incoming else f"api-{uuid.uuid4().hex[:12]}"
        token = bind_request_id(request_id)
        try:
            response = await call_next(request)
        finally:
            reset_request_id(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def install_cors(app: FastAPI, origins: str) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins.split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER],
    )


def route_template(request: Request) -> str:
    """Đường dẫn thật với giá trị tham số thay bằng `{tên}` (không lộ id / mã đơn trong tên chỉ số).

    Không dựa vào `route.path`: route gắn qua `include_router(prefix=…)` có thể chỉ giữ phần sau prefix."""
    values = {str(v): k for k, v in (request.path_params or {}).items()}
    return "/".join("{%s}" % values[part] if part in values else part for part in request.url.path.split("/"))


def install_call_telemetry(app: FastAPI, prefix: str = "/api/v1") -> None:
    """Mỗi request dưới `prefix` là một lần gọi nguồn `web`: route mẫu (không có giá trị tham số), mã trạng thái, thời
    gian và chi tiết use case ghi vào (`application/telemetry.py`). Không ghi query string hay body."""

    @app.middleware("http")
    async def record_call(request: Request, call_next):
        telemetry = getattr(request.app.state, "call_telemetry", None)
        if telemetry is None or not request.url.path.startswith(prefix):
            return await call_next(request)
        started = time.perf_counter()
        status = 500
        with call_scope("web") as detail:
            try:
                response = await call_next(request)
                status = response.status_code
                return response
            finally:
                name = f"{request.method} {route_template(request)}" if request.scope.get("route") else \
                    f"{request.method} (không khớp route)"
                telemetry.record({"source": "web", "kind": "http", "name": name, "status": status,
                                  "ms": round((time.perf_counter() - started) * 1000, 1), **detail})


# --- Sự kiện `http.request` (docs/spec/logging-schema.md §2, §3) ---------------------------------------------------

_CAPTURE_LIMIT = 64 * 1024  # giữ tối đa chừng này mỗi phía để parse JSON trước khi cắt về 2.048 byte
_BOOKING_REQUEST_KEYS = {"productId", "quantity", "usingDate", "nights", "draftId", "items", "allowPartial"}
_BOOKING_RESPONSE_KEYS = {"referenceCode", "status", "totalAmount", "currency", "items", "productId", "quantity",
                          "usingDate", "draftId", "lines", "cartItemId"}
_GROUPS = (("/auth", "auth"), ("/payments", "webhook"), ("/bookings", "booking"), ("/booking-drafts", "booking"),
           ("/cart", "booking"), ("/guest-bookings", "booking"), ("/search", "catalog"),
           ("/recommendations", "catalog"), ("/internal/recommendations", "catalog"), ("/products", "catalog"),
           ("/destinations", "catalog"), ("/similar", "catalog"), ("/assistant", "assistant"), ("/events", "events"))


def _group(path: str) -> str:
    path = path.removeprefix("/api/v1")
    for prefix, group in _GROUPS:
        if path == prefix or path.startswith(prefix + "/"):
            return group
    return "other"


def _pick(value, keys: set):
    """Chỉ giữ khoá cho phép (đệ quy): hành khách, liên hệ và mọi thứ khác bị bỏ."""
    if isinstance(value, dict):
        return {k: _pick(v, keys) for k, v in value.items() if k in keys}
    if isinstance(value, list):
        return [_pick(v, keys) for v in value]
    return value


def _parse(raw: bytes, content_type: str):
    """(giá trị đã parse, ok). Chỉ JSON và text; nhị phân thì bỏ."""
    ctype = content_type.lower()
    if "json" in ctype:
        try:
            return json.loads(raw.decode("utf-8")), True
        except ValueError:
            return mask_text(raw.decode("utf-8", "replace")), True
    if ctype.startswith("text/") and "event-stream" not in ctype:
        return mask_text(raw.decode("utf-8", "replace")), True
    return None, False


def body_view(group: str, direction: str, raw: bytes, content_type: str):
    """Phần body được phép ghi theo bảng ở schema §3, hoặc None. `direction`: request | response."""
    if not raw or group == "webhook" or (group == "auth" and direction == "request") \
            or (group == "events" and direction == "response"):
        return None
    value, ok = _parse(raw, content_type)
    if not ok:
        return None
    if group == "auth":  # response: chỉ giữ user.id băm và vai trò
        user = value.get("user") if isinstance(value, dict) else None
        if not isinstance(user, dict):
            return None
        return {"user": {"id_hash": hash_user_id(str(user.get("id") or user.get("userId") or "")),
                         "role": user.get("role")}}
    if group == "booking":
        return _pick(value, _BOOKING_REQUEST_KEYS if direction == "request" else _BOOKING_RESPONSE_KEYS)
    if group == "catalog" and direction == "response":
        found = summarize(value)
        return {"result_count": found.get("resultCount"), "productIds": (found.get("productIds") or [])[:10]}
    if group == "assistant":
        if not isinstance(value, dict):
            return None
        if direction == "request":
            return {"message": mask_text(str(value.get("message", "")))[:500]}
        err = value.get("error") if isinstance(value.get("error"), dict) else {}
        answer = value.get("message") or value.get("question") or err.get("message") or ""
        return {"status": value.get("status"), "answer": mask_text(str(answer))[:1000]}
    if group == "events":
        return {k: v for k, v in value.items() if k in ("eventName", "productId")} if isinstance(value, dict) else None
    return value


def _error_code(raw: bytes) -> str | None:
    try:
        err = json.loads(raw.decode("utf-8")).get("error")
        code = err.get("code") if isinstance(err, dict) else None
        return code if isinstance(code, str) else None
    except (ValueError, AttributeError):
        return None


def _query_view(scope, group: str) -> str | None:
    raw = scope.get("query_string", b"").decode("latin-1")
    if not raw or group in ("auth", "webhook"):
        return None
    return truncate_json(redact(dict(parse_qsl(raw, keep_blank_values=True))))[0]


class HttpLogMiddleware:
    """ASGI thuần: bọc receive/send để đếm byte và giữ tối đa 64 KiB mỗi phía; phát một dòng `http.request` khi xong."""

    def __init__(self, app, prefix: str = "/api/v1"):
        self.app = app
        self.prefix = prefix

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        started = time.perf_counter()
        path = scope.get("path", "")
        group = _group(path)
        want_bodies = log_bodies_enabled()
        keep_request = want_bodies and group not in ("auth", "webhook")  # không giữ body đăng nhập / webhook trong RAM
        actor, token = open_actor()
        req_raw, resp_raw = bytearray(), bytearray()
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        state = {"req_bytes": 0, "resp_bytes": 0, "status": 500, "req_ct": headers.get("content-type", ""),
                 "resp_ct": ""}

        async def recv():
            message = await receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                state["req_bytes"] += len(body)
                if keep_request and len(req_raw) < _CAPTURE_LIMIT:
                    req_raw.extend(body[:_CAPTURE_LIMIT - len(req_raw)])
            return message

        async def snd(message):
            if message["type"] == "http.response.start":
                state["status"] = message["status"]
                for key, value in message.get("headers", []):
                    if key.lower() == b"content-type":
                        state["resp_ct"] = value.decode("latin-1")
            elif message["type"] == "http.response.body":
                body = message.get("body", b"")
                state["resp_bytes"] += len(body)
                if "event-stream" not in state["resp_ct"] and len(resp_raw) < _CAPTURE_LIMIT:
                    resp_raw.extend(body[:_CAPTURE_LIMIT - len(resp_raw)])
            await send(message)

        failure: BaseException | None = None
        try:
            await self.app(scope, recv, snd)
        except BaseException as exc:  # ghi rồi ném lại: ServerErrorMiddleware vẫn trả 500
            failure = exc
            raise
        finally:
            try:
                self._emit(scope, path, group, want_bodies, actor, state, req_raw, resp_raw, started, failure)
            except Exception:  # log hỏng không được làm hỏng request
                logger.debug("http.request.emit_failed", exc_info=True)
            close_actor(token)

    def _emit(self, scope, path, group, want_bodies, actor, state, req_raw, resp_raw, started, failure):
        status = state["status"]
        streaming = "event-stream" in state["resp_ct"]
        health = path.startswith("/health")
        if health:
            route = path
        elif scope.get("route") is not None:
            route = route_template(Request(scope))
        else:
            route = "(không khớp route)"
        level = "DEBUG" if health else "ERROR" if status >= 500 else "WARNING" if status >= 400 else "INFO"
        fields = {
            "method": scope.get("method"), "route": route, "status": status,
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            "user_kind": actor["kind"], "user_id_hash": hash_user_id(actor["id"]),
            "request_bytes": state["req_bytes"], "response_bytes": state["resp_bytes"],
            "streaming": True if streaming else None, "query": _query_view(scope, group),
        }
        if status >= 400 and not streaming:
            fields["error.code"] = _error_code(bytes(resp_raw))
        if want_bodies and not health:
            truncated = False
            for name, raw, direction, ctype in (("request_body", req_raw, "request", state["req_ct"]),
                                                ("response_body", resp_raw, "response", state["resp_ct"])):
                if direction == "response" and streaming:
                    continue
                view = body_view(group, direction, bytes(raw), ctype)
                if view is not None:
                    text, cut = truncate_json(redact(view))
                    fields[name] = text
                    truncated = truncated or cut
            if truncated:
                fields["body_truncated"] = True
        exc_info = (type(failure), failure, failure.__traceback__) if failure is not None else None
        log_event(logger, "http.request", level, exc_info=exc_info, **fields)


def install_http_logging(app: FastAPI, prefix: str = "/api/v1") -> None:
    """Gọi TRƯỚC `install_request_id`: middleware này phải nằm trong để đọc được X-Request-ID đã gán."""
    app.add_middleware(HttpLogMiddleware, prefix=prefix)
