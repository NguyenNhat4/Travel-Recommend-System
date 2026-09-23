from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.backend.app.api.middleware import install_request_id
from src.backend.app.core.request_context import current_request_id


def make_client():
    app = FastAPI()
    install_request_id(app)

    @app.get("/echo")
    async def echo():
        return {"requestId": current_request_id()}

    return TestClient(app)


def test_reuses_incoming_request_id():
    response = make_client().get("/echo", headers={"X-Request-ID": "01JXYZ"})
    assert response.json() == {"requestId": "01JXYZ"}
    assert response.headers["X-Request-ID"] == "01JXYZ"


def test_generates_request_id_when_missing():
    response = make_client().get("/echo")
    assert response.json()["requestId"].startswith("api-")
    assert response.headers["X-Request-ID"] == response.json()["requestId"]
    assert current_request_id() is None
