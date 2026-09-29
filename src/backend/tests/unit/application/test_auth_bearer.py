"""Bearer → AuthPrincipal dùng chung cho api/deps.py và tool itinerary trong tiến trình (auth §3.5, §3.11)."""
import asyncio

import pytest

from src.backend.app.application.auth.bearer import bearer_token, principal_from_header, verified_principal
from src.backend.app.application.auth.errors import TokenExpired, TokenInvalid
from src.backend.app.application.auth.principal import AuthenticatedUser
from src.backend.tests.fakes.auth import jwt_issuer
from src.backend.tests.fakes.auth_app import AuthWorld

USER = AuthenticatedUser("u-1", "minh.anh@example.com", "x", "Minh Anh", "VP0000001")


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def world():
    return AuthWorld([USER])


def token_for(issuer) -> str:
    return issuer.issue_access_token(USER, session_id="s_abc", amr=("pwd",))[0]


def test_missing_header_is_guest_without_touching_the_verifier():
    assert bearer_token(None) is None
    # verifier None: nếu bị gọi thì AttributeError, nghĩa là khách không đi qua bước kiểm token.
    assert run(principal_from_header(None, None, None)) is None


@pytest.mark.parametrize("header", ["Basic x", "Bearer ", "Bearer    ", "", "Token abc"])
def test_non_bearer_or_empty_token_is_invalid_not_guest(header, world):
    with pytest.raises(TokenInvalid):
        bearer_token(header)
    with pytest.raises(TokenInvalid):
        run(principal_from_header(header, world.issuer, world))


def test_scheme_is_case_insensitive_and_token_is_stripped():
    assert bearer_token("bearer  abc.def.ghi ") == "abc.def.ghi"


def test_valid_token_yields_principal(world):
    principal = run(principal_from_header(f"Bearer {token_for(world.issuer)}", world.issuer, world))
    assert (principal.user_id, principal.cdp_user_id, principal.session_id) == ("u-1", "VP0000001", "s_abc")
    assert principal.token_id


def test_valid_token_without_revocation_store(world):
    principal = run(verified_principal(token_for(world.issuer), world.issuer, None))
    assert principal.cdp_user_id == "VP0000001"


def test_revoked_jti_is_rejected(world):
    token = token_for(world.issuer)
    world.revoked_jti.add(world.issuer.verify(token).token_id)
    with pytest.raises(TokenInvalid) as caught:
        run(principal_from_header(f"Bearer {token}", world.issuer, world))
    assert not isinstance(caught.value, TokenExpired)


def test_forged_token_is_invalid(world):
    with pytest.raises(TokenInvalid):
        run(principal_from_header("Bearer not.a.jwt", world.issuer, world))


def test_expired_token_raises_the_verifier_expiry_error(world):
    # Cùng cặp khoá với world.issuer; exp đã qua 120 giây, vượt leeway 60 giây.
    expired = token_for(jwt_issuer(access_ttl_seconds=-120))
    with pytest.raises(TokenExpired):
        run(principal_from_header(f"Bearer {expired}", world.issuer, world))
