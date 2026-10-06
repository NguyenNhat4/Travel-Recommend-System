"""Bảo đảm test không đọc `.env` và không chạy nhầm vào staging/dịch vụ từ xa."""
import pytest

from src.backend.app.core.config import Settings
from src.backend.tests.guard import remote_dependency_violations as violations


def test_env_file_is_disabled_for_tests():
    assert Settings.model_config["env_file"] is None


def test_local_docker_urls_are_allowed():
    env = {"DATABASE_URL": "postgresql://u:p@localhost:5432/vota", "AUTH_REDIS_URL": "redis://:p@127.0.0.1:6379/1",
           "WEAVIATE_URL": "http://localhost:8080"}
    assert violations(env) == []


@pytest.mark.parametrize("name,value", [
    ("DATABASE_URL", "postgresql://u:p@127.0.0.1:15432/vota"),        # tunnel staging primary
    ("CDP_DATABASE_URL", "postgresql://u:p@127.0.0.1:15433/vota"),    # tunnel staging replica
    ("DATABASE_URL", "postgresql://u:p@10.148.0.2:5432/vota"),        # IP private staging
    ("WEAVIATE_URL", "https://abc.c0.eu-central-1.aws.weaviate.cloud"),
    ("AUTH_REDIS_URL", "redis://:p@redis.example.com:6379/1"),
])
def test_remote_or_staging_targets_are_rejected(name, value):
    assert violations({name: value}) and name in violations({name: value})[0]


def test_override_allows_remote():
    assert violations({"DATABASE_URL": "postgresql://u@db.example.com/vota", "ALLOW_REMOTE_TEST_DEPS": "1"}) == []


def test_blank_values_are_ignored():
    assert violations({"WEAVIATE_URL": "  ", "DATABASE_URL": ""}) == []
