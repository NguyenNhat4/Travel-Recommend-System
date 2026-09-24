"""JWT RS256 (auth §10.3), Argon2id/bcrypt (§8), rate limiter (§9)."""
import asyncio
import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
import pytest

from src.backend.app.application.auth.errors import RateLimited, TokenExpired, TokenInvalid
from src.backend.app.application.auth.principal import AuthenticatedUser
from src.backend.app.infrastructure.auth.keys import generate_rsa_pem_pair, load_rsa_pem_pair
from src.backend.app.infrastructure.auth.rate_limiter import InMemoryRateLimiter
from src.backend.tests.fakes.auth import fast_hasher, jwt_issuer, rsa_keys

USER = AuthenticatedUser("u-1", "minh.anh@example.com", "x", "Minh Anh", "VP0000001")
PRIVATE, PUBLIC = rsa_keys()


def claims(**overrides):
    now = datetime.now(timezone.utc)
    payload = {"iss": "https://api.vota.test", "aud": "vota-api", "sub": "u-1", "cdp_user_id": "VP0000001",
               "email": "minh.anh@example.com", "iat": now, "nbf": now, "exp": now + timedelta(minutes=5)}
    payload.update(overrides)
    return {k: v for k, v in payload.items() if v is not None}


def signed(payload=None, *, key=PRIVATE, alg="RS256", kid="vota-1", headers=None):
    return jwt.encode(payload or claims(), key, algorithm=alg, headers={"kid": kid, **(headers or {})})


def test_issue_then_verify_round_trip():
    issuer = jwt_issuer()
    token, ttl = issuer.issue_access_token(USER, session_id="s_abc", amr=("pwd",))
    principal = issuer.verify(token)
    assert ttl == 600
    assert (principal.user_id, principal.cdp_user_id, principal.session_id, principal.amr) == (
        "u-1", "VP0000001", "s_abc", ("pwd",))
    assert jwt.get_unverified_header(token)["alg"] == "RS256"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _handmade(alg: str, sign) -> str:
    """Dựng token tay: PyJWT tự chặn ký alg:none/HS256-bằng-PEM, nhưng kẻ tấn công thì không."""
    body = {k: (int(v.timestamp()) if isinstance(v, datetime) else v) for k, v in claims().items()}
    signing_input = f"{_b64(json.dumps({'alg': alg, 'kid': 'vota-1', 'typ': 'JWT'}).encode())}.{_b64(json.dumps(body).encode())}"
    return f"{signing_input}.{sign(signing_input.encode())}"


def _unsigned_none_token():
    return _handmade("none", lambda _: "")


def _hs256_with_public_key():
    return _handmade("HS256", lambda data: _b64(hmac.new(PUBLIC.encode(), data, hashlib.sha256).digest()))


BAD_TOKENS = {
    "alg-none": _unsigned_none_token,
    # Đánh tráo RS256→HS256: ký HMAC bằng chính public key.
    "hs256-with-public-key": _hs256_with_public_key,
    "wrong-signature": lambda: signed(key=generate_rsa_pem_pair()[0]),
    "wrong-iss": lambda: signed(claims(iss="https://evil")),
    "wrong-aud": lambda: signed(claims(aud="other")),
    "nbf-future": lambda: signed(claims(nbf=datetime.now(timezone.utc) + timedelta(minutes=5))),
    "unknown-kid": lambda: signed(kid="attacker"),
    "missing-sub": lambda: signed(claims(sub=None)),
    "missing-cdp-user-id": lambda: signed(claims(cdp_user_id=None)),
    "empty-cdp-user-id": lambda: signed(claims(cdp_user_id="  ")),
    "missing-exp": lambda: signed(claims(exp=None)),
    "typ-not-jwt": lambda: signed(headers={"typ": "at+jwt"}),
    "garbage": lambda: "not.a.jwt",
}


@pytest.mark.parametrize("name", BAD_TOKENS)
def test_verify_rejects(name):
    with pytest.raises(TokenInvalid) as caught:
        jwt_issuer().verify(BAD_TOKENS[name]())
    assert not isinstance(caught.value, TokenExpired)


def test_expired_beyond_leeway_is_token_expired_but_within_leeway_passes():
    issuer = jwt_issuer()
    with pytest.raises(TokenExpired):
        issuer.verify(signed(claims(exp=datetime.now(timezone.utc) - timedelta(seconds=61))))
    assert issuer.verify(signed(claims(exp=datetime.now(timezone.utc) - timedelta(seconds=30))))


def test_jwks_exposes_public_key_that_verifies_tokens():
    issuer = jwt_issuer()
    jwks = issuer.jwks()
    (key,) = jwks["keys"]
    assert (key["kid"], key["use"], key["alg"], key["kty"]) == ("vota-1", "sig", "RS256", "RSA")
    assert "d" not in key  # không bao giờ lộ phần private
    public = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
    token, _ = issuer.issue_access_token(USER, session_id=None, amr=("pwd",))
    assert jwt.decode(token, public, algorithms=["RS256"], audience="vota-api")["cdp_user_id"] == "VP0000001"


def test_config_rejects_symmetric_algorithm():
    with pytest.raises(ValueError):
        jwt_issuer(algorithm="HS256")


def test_key_loader_fails_closed_in_production(tmp_path):
    with pytest.raises(RuntimeError):
        load_rsa_pem_pair("missing.pem", "missing.pub", base_dir=tmp_path, allow_ephemeral=False)
    private, public = load_rsa_pem_pair("missing.pem", "missing.pub", base_dir=tmp_path, allow_ephemeral=True)
    assert "PRIVATE KEY" in private and "PUBLIC KEY" in public
    (tmp_path / "k.pem").write_text(private)
    (tmp_path / "k.pub").write_text(public)
    assert load_rsa_pem_pair("k.pem", "k.pub", base_dir=tmp_path, allow_ephemeral=False) == (private, public)


# --- mật khẩu ---------------------------------------------------------------------------------

def test_argon2id_hash_and_verify():
    hasher = fast_hasher()
    stored = hasher.hash("Demo@2026")
    assert stored.startswith("$argon2id$")
    assert hasher.verify("Demo@2026", stored) and not hasher.verify("demo@2026", stored)


def test_bcrypt_legacy_hash_verifies_and_needs_rehash():
    hasher = fast_hasher()
    legacy = bcrypt.hashpw(b"Demo@2026", bcrypt.gensalt(rounds=4)).decode()
    assert hasher.verify("Demo@2026", legacy) and hasher.needs_rehash(legacy)
    assert not hasher.needs_rehash(hasher.hash("Demo@2026"))


def test_unknown_hash_format_is_rejected(caplog):
    assert not fast_hasher().verify("x", "md5:abc")
    assert "auth.unknown_hash_format" in caplog.text


# --- rate limiter -----------------------------------------------------------------------------

class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def run(coro):
    return asyncio.run(coro)


def test_lockout_after_threshold_expires_after_fifteen_minutes():
    clock = Clock()
    limiter = InMemoryRateLimiter(clock=clock)
    for _ in range(4):
        run(limiter.register_failure("login:email", "a@b.vn"))
    run(limiter.check("login:email", "a@b.vn"))
    run(limiter.register_failure("login:email", "a@b.vn"))
    with pytest.raises(RateLimited) as caught:
        run(limiter.check("login:email", "a@b.vn"))
    assert caught.value.retry_after_seconds == 900
    clock.now += 901
    run(limiter.check("login:email", "a@b.vn"))


def test_email_and_ip_axes_are_independent():
    limiter = InMemoryRateLimiter(clock=Clock())
    for _ in range(5):
        run(limiter.register_failure("login:email", "a@b.vn"))
    run(limiter.check("login:ip", "a@b.vn"))
    run(limiter.check("login:email", "c@d.vn"))


def test_sliding_window_forgets_old_hits():
    clock = Clock()
    limiter = InMemoryRateLimiter(clock=clock)
    for _ in range(5):
        run(limiter.hit("register:ip", "1.1.1.1"))
    with pytest.raises(RateLimited):
        run(limiter.hit("register:ip", "1.1.1.1"))
    clock.now += 3601
    run(limiter.hit("register:ip", "1.1.1.1"))
