from __future__ import annotations

import pytest

from evaluation.search_bench import costlog, doctor, paths


def test_version_compare():
    assert doctor.version_at_least("1.37.3", "1.37")
    assert doctor.version_at_least("1.40.0", "1.37")
    assert not doctor.version_at_least("1.27.0", "1.37")
    assert doctor.version_at_least("1.37.0-rc.1", "1.37")


def test_missing_key_fails(cfg, monkeypatch):
    monkeypatch.delenv("COHERE_API_KEY", raising=False)
    ch = doctor.check_cohere(cfg, skip_api=False)
    assert ch.status == doctor.FAIL and ".env" in ch.hint


def test_probe_error_never_prints_key(cfg, monkeypatch):
    secret = "sk-test-SECRET-1234567890"
    monkeypatch.setenv("COHERE_API_KEY", secret)

    def boom(key, model):
        raise RuntimeError(f"401 invalid api token {key}")
    monkeypatch.setattr(doctor, "tokenize_probe", boom)
    ch = doctor.check_cohere(cfg, skip_api=False)
    assert ch.status == doctor.FAIL and secret not in ch.detail and "***" in ch.detail


def test_skip_api_does_not_call(cfg, monkeypatch):
    monkeypatch.setenv("COHERE_API_KEY", "x" * 40)
    monkeypatch.setattr(doctor, "tokenize_probe", lambda *a: pytest.fail("không được gọi API"))
    assert doctor.check_cohere(cfg, skip_api=True).status == doctor.INFO


def test_probe_logs_cost(cfg, home, monkeypatch):
    class Resp:
        tokens = [1, 2]

    class FakeClient:
        def __init__(self, **kw):
            pass

        def tokenize(self, **kw):
            assert kw["offline"] is False
            return Resp()
    import cohere
    monkeypatch.setattr(cohere, "ClientV2", FakeClient)
    assert doctor.tokenize_probe("k", "embed-multilingual-v3.0") == 2
    rows = costlog.read()
    assert rows[-1]["endpoint"] == "tokenize" and rows[-1]["usd"] == 0.0
    assert set(rows[-1]) == {"ts", "endpoint", "model", "input_type", "n_texts", "n_tokens", "usd", "source"}  # không có key


def test_ascii_fold_needs_137(cfg):
    ch = doctor.check_ascii_fold(cfg, "1.27.0")
    assert ch.status == doctor.FAIL and "shadow" in ch.hint
    assert doctor.check_ascii_fold(cfg, "1.37.3").status == doctor.OK


def test_ascii_fold_shadow_is_info(cfg):
    shadow = cfg.model_copy(update={"weaviate": cfg.weaviate.model_copy(update={"ascii_fold": "shadow"})})
    assert doctor.check_ascii_fold(shadow, None).status == doctor.INFO


def test_weaviate_down_fails_with_hint(cfg):
    down = cfg.model_copy(update={"weaviate": cfg.weaviate.model_copy(update={"url": "http://127.0.0.1:9"})})
    checks, ver = doctor.check_weaviate(down)
    assert ver is None and checks[0].status == doctor.FAIL and "docker compose" in checks[0].hint


def test_exit_code(capsys):
    assert doctor.print_checks([doctor.Check("a", doctor.OK, "x"), doctor.Check("b", doctor.WARN, "y", "h")]) == 0
    assert doctor.print_checks([doctor.Check("a", doctor.FAIL, "x", "fix")]) == 1


def test_cost_summary(home):
    costlog.append(endpoint="embed", model="m", input_type="search_document", n_texts=96, n_tokens=1000, usd=0.0001)
    costlog.append(endpoint="embed", model="m", input_type="search_document", n_texts=4, n_tokens=50, usd=0.000005)
    costlog.append(endpoint="embed", model="m", input_type="search_query", n_texts=1, n_tokens=5, usd=0.0000005)
    s = {r["input_type"]: r for r in costlog.summarize()}
    assert s["search_document"]["calls"] == 2 and s["search_document"]["texts"] == 100
    assert s["search_query"]["tokens"] == 5
    assert (paths.cache_dir() / paths.COST_LOG).exists()
