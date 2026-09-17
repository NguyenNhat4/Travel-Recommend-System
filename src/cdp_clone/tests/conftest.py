import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from src.cdp_clone.app.config import Settings
from src.cdp_clone.app.infrastructure.tables import metadata
from src.cdp_clone.app.main import create_app

SERVICE_TOKEN = "test-service-token-0123456789abcdef"
SERVICE_HEADERS = {"X-Service-Token": SERVICE_TOKEN}


@pytest.fixture
def engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    metadata.create_all(engine)
    return engine


@pytest.fixture
def client(engine):
    settings = Settings(app_env="test", database_url="sqlite://", service_token=SERVICE_TOKEN)
    with TestClient(create_app(settings, engine), raise_server_exceptions=False, headers=SERVICE_HEADERS) as client:
        yield client
