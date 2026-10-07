"""Log JSON: formatter, che dữ liệu nhạy cảm, allowlist và middleware `http.request` (docs/spec/logging-schema.md)."""
from __future__ import annotations

import io
import json
import logging
import re

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src.backend.app.api.middleware import install_http_logging, install_request_id
from src.backend.app.core.logging_config import JsonFormatter, configure_logging, log_event, redact
from src.backend.app.core.request_context import bind_request_id, note_actor, reset_request_id

JWT = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ1MSIsImV4cCI6MX0.c2lnbmF0dXJlMTIzNDU2"
DSN = "postgresql://vota_app:S3cretPw@db.internal:5432/vota"
SECRETS = ["hunter2", JWT, "S3cretPw", "an.nguyen@example.com", "4111111111111111", "4111 1111 1111 1111",
           "sk_live_abcdef123456", "whsec_abcdef123456", "0912345678", "+84912345678"]


@pytest.fixture
def stream():
    """Gắn handler JSON vào root logger, trả StringIO chứa stdout giả; khôi phục khi xong."""
    root = logging.getLogger()
    saved_handlers, saved_level = list(root.handlers), root.level
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setFormatter(JsonFormatter())
    root.handlers = [handler]
    root.setLevel(logging.DEBUG)
    yield buffer
    root.handlers, root.level = saved_handlers, saved_level


def lines(buffer: io.StringIO) -> list[dict]:
    return [json.loads(line) for line in buffer.getvalue().splitlines() if line.strip()]


# --- formatter -------------------------------------------------------------------------------------------------

def test_formatter_emits_one_json_line_with_required_fields(stream):
    token = bind_request_id("req-123")
    try:
        log_event("backend.test", "search.run", mode="HYBRID", query_text="khách sạn Đà Nẵng", result_count=3)
    finally:
        reset_request_id(token)
    raw = stream.getvalue()
    assert raw.count("\n") == 1
    entry = json.loads(raw)
    assert entry["event"] == "search.run" and entry["service"] == "backend" and entry["severity"] == "INFO"
    assert entry["request_id"] == "req-123"
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}\+07:00", entry["ts"])
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z", entry["ts_utc"])
    assert entry["result_count"] == 3 and entry["query_text"] == "khách sạn Đà Nẵng"


def test_legacy_message_gets_event_name_from_leading_token(stream):
    logging.getLogger("legacy").info("startup.recsys.ready search_units=3")
    entry = lines(stream)[0]
    assert entry["event"] == "startup.recsys.ready" and entry["message"] == "startup.recsys.ready search_units=3"


def test_error_is_structured_and_stack_is_sanitized(stream):
    try:
        raise RuntimeError(f"không kết nối được {DSN} password=hunter2")
    except RuntimeError:
        log_event("backend.test", "db.unavailable", "ERROR", exc_info=True, component="postgres")
    entry = lines(stream)[0]
    assert entry["severity"] == "ERROR" and entry["error.type"] == "RuntimeError"
    out = stream.getvalue()
    assert "S3cretPw" not in out and "hunter2" not in out
    assert "error.stack" in entry and "Traceback" in entry["error.stack"]


def test_fields_outside_allowlist_are_dropped(stream):
    log_event("backend.test", "auth.login", outcome="ok", password="hunter2", email="an.nguyen@example.com")
    entry = lines(stream)[0]
    assert "password" not in entry and "email" not in entry and entry["outcome"] == "ok"
    assert "hunter2" not in stream.getvalue()


def test_configure_logging_routes_uvicorn_and_quiets_http_clients(monkeypatch):
    root = logging.getLogger()
    saved = list(root.handlers), root.level
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    try:
        configure_logging()
        assert len(root.handlers) == 1 and isinstance(root.handlers[0].formatter, JsonFormatter)
        assert root.level == logging.WARNING
        assert logging.getLogger("uvicorn.error").handlers == [] and logging.getLogger("uvicorn.error").propagate
        assert logging.getLogger("httpx").level == logging.WARNING
        configure_logging()  # gọi lại không nhân đôi handler
        assert len(root.handlers) == 1
    finally:
        root.handlers, root.level = saved


# --- redact ----------------------------------------------------------------------------------------------------

def test_redact_masks_sensitive_keys_and_value_patterns(stream):
    payload = {
        "password": "hunter2", "nested": {"Authorization": f"Bearer {JWT}", "note": f"liên hệ an.nguyen@example.com"},
        "dsn": DSN, "text": f"thẻ 4111 1111 1111 1111 và {DSN} sk_live_abcdef123456 whsec_abcdef123456",
        "phone_text": "gọi 0912345678 hoặc +84912345678", "card": 4111111111111111, "count": 5,
        "contact": {"name": "Nguyen Van An", "fullName": "Nguyen Van An"}, "product": {"name": "Khách sạn Mường Thanh"},
        "travelers": [{"surname": "Nguyen", "name": "An", "dob": "1990-01-01"}],
    }
    out = redact(payload)
    dumped = json.dumps(out, ensure_ascii=False)
    for secret in SECRETS + ["Nguyen Van An", "1990-01-01"]:
        assert secret not in dumped, secret
    assert out["count"] == 5 and out["product"]["name"] == "Khách sạn Mường Thanh"
    assert out["password"] == "***" and "postgresql://***@" in out["text"]


def test_redact_does_not_mutate_input():
    original = {"password": "hunter2", "items": [{"token": "x"}]}
    redact(original)
    assert original == {"password": "hunter2", "items": [{"token": "x"}]}


# --- middleware ------------------------------------------------------------------------------------------------

def build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/api/v1/search")
    def search(body: dict):
        return {"results": [{"productId": f"P{i}"} for i in range(30)], "total": 30}

    @app.post("/api/v1/auth/login")
    def login(body: dict):
        note_actor("user", "cdp-u-1")
        return {"accessToken": JWT, "user": {"id": "cdp-u-1", "email": "an.nguyen@example.com", "role": "customer"}}

    @app.post("/api/v1/bookings")
    def booking(body: dict):
        return {"referenceCode": "VT-1", "status": "PENDING_PAYMENT", "totalAmount": 1200000,
                "contact": {"email": "an.nguyen@example.com", "phone": "0912345678"}}

    @app.get("/api/v1/bookings/{reference_code}")
    def booking_get(reference_code: str):
        raise HTTPException(status_code=404, detail={"error": {"code": "BOOKING_NOT_FOUND"}})

    @app.get("/api/v1/boom")
    def boom():
        raise RuntimeError(f"hỏng {DSN}")

    install_http_logging(app)
    install_request_id(app)
    return app


@pytest.fixture
def client(stream):
    return TestClient(build_app(), raise_server_exceptions=False)


def request_events(buffer) -> list[dict]:
    return [e for e in lines(buffer) if e["event"] == "http.request"]


def test_http_request_has_route_template_status_duration_and_request_id(client, stream):
    client.get("/api/v1/bookings/VT-2024", headers={"X-Request-ID": "rid-7"})
    entry = request_events(stream)[0]
    assert entry["route"] == "/api/v1/bookings/{reference_code}" and entry["status"] == 404
    assert entry["request_id"] == "rid-7" and entry["method"] == "GET" and entry["severity"] == "WARNING"
    assert isinstance(entry["duration_ms"], (int, float)) and entry["user_kind"] == "anon"
    assert "VT-2024" not in entry["route"]


def test_health_is_debug_and_dropped_at_info(client, stream):
    client.get("/health")
    entry = request_events(stream)[0]
    assert entry["severity"] == "DEBUG" and entry["route"] == "/health"
    stream.truncate(0), stream.seek(0)
    logging.getLogger().setLevel(logging.INFO)
    client.get("/health")
    assert request_events(stream) == []


def test_catalog_response_body_is_summarised_and_request_body_truncated(client, stream):
    client.post("/api/v1/search?q=bien", json={"query": "x" * 5000})
    entry = request_events(stream)[0]
    assert entry["body_truncated"] is True
    assert len(entry["request_body"].encode()) <= 2048
    response = json.loads(entry["response_body"])
    assert response["result_count"] == 30 and len(response["productIds"]) == 10
    assert json.loads(entry["query"]) == {"q": "bien"}


def test_auth_request_is_not_logged_and_response_keeps_only_hashed_user(client, stream):
    client.post("/api/v1/auth/login", json={"email": "an.nguyen@example.com", "password": "hunter2"})
    entry = request_events(stream)[0]
    assert "request_body" not in entry and entry["user_kind"] == "user" and entry["user_id_hash"]
    assert entry["user_id_hash"] != "cdp-u-1"
    assert "hunter2" not in stream.getvalue() and JWT not in stream.getvalue()
    assert "an.nguyen@example.com" not in stream.getvalue()
    assert json.loads(entry["response_body"])["user"]["role"] == "customer"


def test_booking_bodies_keep_only_whitelisted_fields(client, stream):
    client.post("/api/v1/bookings", json={"draftId": "d1", "contact": {"fullName": "Nguyen Van An",
                "email": "an.nguyen@example.com", "phone": "0912345678"}, "items": [{"productId": "P1", "quantity": 2}]})
    entry = request_events(stream)[0]
    assert json.loads(entry["request_body"]) == {"draftId": "d1", "items": [{"productId": "P1", "quantity": 2}]}
    assert json.loads(entry["response_body"]) == {"referenceCode": "VT-1", "status": "PENDING_PAYMENT",
                                                  "totalAmount": 1200000}
    for secret in ("Nguyen Van An", "an.nguyen@example.com", "0912345678"):
        assert secret not in stream.getvalue()


def test_log_bodies_off_skips_bodies(client, stream, monkeypatch):
    monkeypatch.setenv("LOG_BODIES", "false")
    client.post("/api/v1/search", json={"query": "bien"})
    entry = request_events(stream)[0]
    assert "request_body" not in entry and "response_body" not in entry and entry["request_bytes"] > 0


def test_unhandled_exception_logs_error_with_sanitized_stack(client, stream):
    response = client.get("/api/v1/boom")
    assert response.status_code == 500
    entry = request_events(stream)[0]
    assert entry["severity"] == "ERROR" and entry["status"] == 500 and entry["error.type"] == "RuntimeError"
    assert "S3cretPw" not in stream.getvalue()


def test_error_code_comes_from_envelope(stream):
    app = FastAPI()

    @app.get("/api/v1/x")
    def x():
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=409, content={"error": {"code": "BOOKING_PENDING_PAYMENT"}})

    install_http_logging(app)
    install_request_id(app)
    TestClient(app).get("/api/v1/x")
    assert request_events(stream)[0]["error.code"] == "BOOKING_PENDING_PAYMENT"
