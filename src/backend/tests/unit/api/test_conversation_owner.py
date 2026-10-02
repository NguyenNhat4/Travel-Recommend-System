"""Chủ hội thoại của trợ lý đi theo user đã xác thực, không theo access token.

BFF làm mới access token mỗi ~9 phút (TTL 600s, làm mới khi còn ≤ 60s). Trước đây chủ = hash của cả
header Authorization, nên lượt chat ngay sau lần làm mới trả 404 CONVERSATION_NOT_FOUND.
"""
from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace

from src.backend.app.agents.runtime_dependencies import RuntimeAgentDependencies
from src.backend.app.api.deps import conversation_owner
from src.backend.app.application.auth.errors import TokenInvalid
from src.backend.app.application.auth.principal import AuthPrincipal


class Verifier:
    """Token dạng `good-<cdp_user_id>-<n>`: cùng user, nhiều token khác nhau."""

    def verify(self, token: str) -> AuthPrincipal:
        if not token.startswith("good-"):
            raise TokenInvalid("hỏng")
        cdp_user_id = token.split("-")[1]
        return AuthPrincipal(user_id=f"u-{cdp_user_id}", cdp_user_id=cdp_user_id, email="a@b.c")


def request(verifier=Verifier()):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(token_verifier=verifier, revoked_tokens=None)))


def owner_of(authorization, verifier=Verifier()):
    return asyncio.run(conversation_owner(request(verifier), authorization))


class ConversationOwnerTests(unittest.TestCase):
    def test_refreshed_token_of_the_same_user_keeps_the_same_owner(self):
        before, after = owner_of("Bearer good-p1-1"), owner_of("Bearer good-p1-2")
        self.assertEqual(before, "p1")
        self.assertEqual(before, after)
        runtime = [RuntimeAgentDependencies(None, None, authorization=f"Bearer good-p1-{n}", owner="p1")
                   for n in (1, 2)]
        self.assertEqual(runtime[0].owner, runtime[1].owner)

    def test_another_user_gets_another_owner(self):
        self.assertNotEqual(owner_of("Bearer good-p1-1"), owner_of("Bearer good-p2-1"))

    def test_guest_and_bad_token_have_no_verified_owner(self):
        self.assertIsNone(owner_of(None))
        self.assertIsNone(owner_of("Bearer broken"))
        self.assertIsNone(owner_of("Basic abc"))
        self.assertIsNone(owner_of("Bearer good-p1-1", verifier=None))

    def test_unverified_token_never_shares_the_guest_or_a_user_bucket(self):
        guest = RuntimeAgentDependencies(None, None).owner
        broken = RuntimeAgentDependencies(None, None, authorization="Bearer broken").owner
        user = RuntimeAgentDependencies(None, None, authorization="Bearer good-p1-1", owner="p1").owner
        self.assertEqual(len({guest, broken, user}), 3)
        self.assertEqual(guest, "anonymous")


if __name__ == "__main__":
    unittest.main()
