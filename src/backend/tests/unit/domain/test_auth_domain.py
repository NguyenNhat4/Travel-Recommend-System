"""Domain auth: cdp_user_id, chính sách mật khẩu, máy trạng thái phiên, rút gọn định danh (auth §20.1)."""
import pytest

from src.backend.app.domain.auth.identifiers import (
    SEED_PATTERN,
    is_seed_cdp_user_id,
    is_web_cdp_user_id,
    new_web_cdp_user_id,
)
from src.backend.app.domain.auth.password import PasswordPolicy, WeakPasswordError
from src.backend.app.domain.auth.privacy import hash_email, ip_prefix, short_sid
from src.backend.app.domain.auth.rate_limits import RULES, rule_for
from src.backend.app.domain.auth.session import (
    InvalidTransition,
    SessionEvent as E,
    SessionState as S,
    apply,
    new_session_id,
)


def test_web_cdp_user_id_never_falls_in_seed_range():
    ids = {new_web_cdp_user_id() for _ in range(500)}
    assert len(ids) == 500
    for value in ids:
        assert is_web_cdp_user_id(value)
        assert not is_seed_cdp_user_id(value)
        assert not SEED_PATTERN.match(value)
    assert is_seed_cdp_user_id("VP0000001") and not is_web_cdp_user_id("VP0000001")


@pytest.mark.parametrize("password, reason", [
    ("short1", "ít nhất 8"),
    ("x" * 129, "quá 128"),
    ("password123", "danh sách bị lộ"),
    ("minhanh-2026", "email"),
    ("NguyenVanAn!", "tên"),
])
def test_password_policy_rejects(password, reason):
    with pytest.raises(WeakPasswordError) as caught:
        PasswordPolicy().validate(password, email="minhanh@example.vn", full_name="Nguyenvanan")
    assert any(reason in r for r in caught.value.reasons)


def test_password_policy_accepts_without_composition_rules_and_normalizes_nfkc():
    # Không ép hoa/số/ký tự đặc biệt (NIST SP 800-63B).
    assert PasswordPolicy().validate("ngựa ô chạy trên đê") == "ngựa ô chạy trên đê"
    # Ký tự full-width chuẩn hoá về ASCII trước khi băm.
    assert PasswordPolicy().validate("ｃｏｒｒｅｃｔhorse") == "correcthorse"


# (trạng thái, sự kiện) → (trạng thái sau, xoay sid, mang danh tính) — 12 dòng bảng auth §3.8.
ROWS = [
    ("A", S.ANONYMOUS, E.VISIT, S.ANONYMOUS, False, False),
    ("B", S.ANONYMOUS, E.REGISTER, S.AUTHENTICATED, True, True),
    ("C", S.ANONYMOUS, E.LOGIN, S.AUTHENTICATED, True, True),
    ("D", S.ANONYMOUS, E.LOGIN_NEEDS_MFA, S.PENDING_MFA, True, False),
    ("E", S.PENDING_MFA, E.MFA_VERIFIED, S.AUTHENTICATED, True, True),
    ("F", S.AUTHENTICATED, E.SWITCH_ACCOUNT, S.AUTHENTICATED, True, True),
    ("G", S.AUTHENTICATED, E.LOGOUT, None, True, False),
    ("H", S.PENDING_MFA, E.UA_MISMATCH, None, True, False),
    ("I", S.ANONYMOUS, E.EXPIRED, None, True, False),
    ("J", S.AUTHENTICATED, E.PASSWORD_CHANGED, S.AUTHENTICATED, True, True),
    ("K", S.AUTHENTICATED, E.MFA_CHANGED, S.AUTHENTICATED, True, True),
    ("L", S.AUTHENTICATED, E.EMAIL_VERIFIED, S.AUTHENTICATED, False, True),
]


@pytest.mark.parametrize("row, state, event, after, rotate, identity", ROWS, ids=[r[0] for r in ROWS])
def test_session_transitions(row, state, event, after, rotate, identity):
    t = apply(state, event)
    assert (t.state, t.rotate_sid, t.carries_identity) == (after, rotate, identity)


@pytest.mark.parametrize("state, event", [
    (S.PENDING_MFA, E.LOGIN),          # phiên nửa-đăng-nhập không được nhảy thẳng lên authenticated
    (S.ANONYMOUS, E.PASSWORD_CHANGED),
    (S.PENDING_MFA, E.SWITCH_ACCOUNT),
])
def test_undeclared_transitions_fail_loudly(state, event):
    with pytest.raises(InvalidTransition):
        apply(state, event)


def test_session_id_is_random_and_prefixed():
    ids = {new_session_id() for _ in range(100)}
    assert len(ids) == 100 and all(i.startswith("s_") and len(i) >= 20 for i in ids)


def test_privacy_helpers_never_keep_raw_identifiers():
    assert hash_email(" Minh.Anh@Example.com ") == hash_email("minh.anh@example.com")
    assert "minh" not in hash_email("minh.anh@example.com")
    assert ip_prefix("203.0.113.77") == "203.0.113.0/24"
    assert ip_prefix("2001:db8:abcd:12::1") == "2001:db8:abcd::/48"
    assert ip_prefix("not-an-ip") == "unknown"
    assert short_sid("s_abcdefghijklmnop") == "s_abcdef" and short_sid(None) == "-"


def test_rate_limit_rules_match_spec():
    assert (RULES["login:email"].limit, RULES["login:email"].window_seconds, RULES["login:email"].lockout_seconds) == (5, 900, 900)
    assert (RULES["login:ip"].limit, RULES["login:ipwide"].limit, RULES["register:ip"].limit) == (20, 100, 5)
    with pytest.raises(ValueError):
        rule_for("unknown")
