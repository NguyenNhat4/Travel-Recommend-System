"""Giới hạn tin gửi trợ lý (NFR-SEC-04): vượt ngưỡng trả 429 đã khai báo trong contract, kèm `Retry-After`."""
from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from src.backend.app.application.auth.errors import RateLimited
from src.backend.app.domain.auth.rate_limits import rule_for
from src.backend.app.infrastructure.auth.rate_limiter import InMemoryRateLimiter
from src.backend.app.main import app
from src.backend.tests.contract.test_assistant_contract import (
    ITINERARIES,
    STREAM,
    AssistantContractTests,
    Clients,
    ScriptedLlm,
)


class ExhaustedLimiter:
    async def hit(self, scope: str, key: str) -> None:
        raise RateLimited(42)


class AssistantRateLimitTests(unittest.TestCase):
    assert_conforms = AssistantContractTests.assert_conforms

    def test_both_assistant_routes_return_a_declared_429_with_retry_after(self):
        for path in (ITINERARIES, STREAM):
            with self.subTest(path=path), TestClient(app) as client:
                app.state.rate_limiter = ExhaustedLimiter()
                app.state.itinerary_llm = ScriptedLlm()
                app.state.itinerary_http_clients = Clients()
                response = client.post(f"/api/v1{path}", json={"message": "lên lịch giúp mình"})
            body = response.json()
            self.assertEqual(response.status_code, 429, body)
            self.assertEqual(response.headers["Retry-After"], "42")
            self.assertEqual(body["error"]["code"], "TOO_MANY_ATTEMPTS")
            self.assertTrue(body["error"]["retryable"])
            self.assert_conforms(path, 429, body, f"rate limit {path}")

    def test_the_sender_is_cut_off_only_after_the_rule_limit(self):
        limit = rule_for("assistant:sender").limit
        with TestClient(app) as client:
            app.state.rate_limiter = InMemoryRateLimiter()
            app.state.itinerary_llm = ScriptedLlm()
            app.state.itinerary_http_clients = Clients()
            codes = [client.post(f"/api/v1{ITINERARIES}", json={"message": "lên lịch giúp mình"}).status_code
                     for _ in range(limit + 1)]
        self.assertNotIn(429, codes[:limit])
        self.assertEqual(codes[-1], 429)


# Chỉ mượn `assert_conforms`; bỏ tên lớp khỏi module để test runner không chạy lại cả lớp đó ở đây.
del AssistantContractTests


if __name__ == "__main__":
    unittest.main()
