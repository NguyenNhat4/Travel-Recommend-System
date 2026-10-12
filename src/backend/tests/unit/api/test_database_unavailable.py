"""503 DATABASE_UNAVAILABLE ở biên HTTP (contract 1.14.0)."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.backend.app.api.errors import install_error_handlers
from src.backend.app.api.middleware import install_request_id
from src.backend.app.application.errors import DatabaseUnavailableError


class _DriverError(Exception):
    """Đại diện cho psycopg.OperationalError: composition root truyền vào, api không import driver."""


def _client() -> TestClient:
    app = FastAPI()
    install_request_id(app)
    install_error_handlers(app, (_DriverError,))

    @app.get("/needs-db")
    async def needs_db():
        raise DatabaseUnavailableError("PostgreSQL không với tới được: OperationalError")

    @app.get("/dropped-midway")
    async def dropped_midway():
        raise _DriverError("server closed the connection unexpectedly")

    @app.get("/fine")
    async def fine():
        return {"ok": True}

    return TestClient(app, raise_server_exceptions=False)


def test_unavailable_database_is_a_retryable_503_envelope() -> None:
    response = _client().get("/needs-db", headers={"X-Request-ID": "req-123"})
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "5"
    error = response.json()["error"]
    assert error["code"] == "DATABASE_UNAVAILABLE"
    assert error["retryable"] is True
    assert error["requestId"] == "req-123"
    assert error["message"]


def test_driver_error_raised_midway_gets_the_same_envelope() -> None:
    response = _client().get("/dropped-midway")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"


def test_response_never_leaks_connection_details() -> None:
    body = _client().get("/needs-db").text
    assert "OperationalError" not in body and "PostgreSQL" not in body


def test_unrelated_routes_are_unaffected() -> None:
    assert _client().get("/fine").json() == {"ok": True}
