"""Adapter `LangChainQueryHypothesizer` (giả thuyết query plan cho /search, contract 1.17.0) với chat model giả — không gọi mạng."""
from types import SimpleNamespace

import pytest

from src.backend.app.application.search.query_plan_llm import hypothesis_context
from src.backend.app.domain.search import PlanGazetteers, QueryNormalizer
from src.backend.app.domain.search.hypothesis import HypothesisVocab, QueryHypothesis
from src.backend.app.infrastructure.llm import query_hypothesis as qh


class FakeChat:
    def __init__(self, out):
        self.out, self.kw, self.schema, self.messages = out, None, None, None

    def with_structured_output(self, schema, **kw):
        self.schema, self.kw = schema, kw
        return self

    def invoke(self, messages):
        self.messages = messages
        return self.out


def _context(q="khách sạn Nha Trang không có hồ bơi và không cần spa cho 2 người"):
    gaz = PlanGazetteers(flight_cities=("Hà Nội", "Nha Trang"))
    nq = QueryNormalizer(destinations={"Nha Trang", "Phú Quốc"}, names=["Vinpearl Resort Nha Trang"])(q)
    return nq.text, hypothesis_context(nq, q, gaz, HypothesisVocab.build(["Nha Trang", "Phú Quốc"], gaz.flight_cities))


def test_structured_output_becomes_a_query_hypothesis():
    out = qh.HypothesisSchema(taxonomy="hotel", destination="Nha Trang", must_not_amenities=["pool"], confidence=0.9)
    chat = FakeChat(out)
    adapter = qh.LangChainQueryHypothesizer(chat, model_name="gpt-4o-mini")
    query, ctx = _context()
    h = adapter.hypothesize(query, ctx)
    assert isinstance(h, QueryHypothesis) and h.taxonomy == "hotel" and h.must_not_amenities == ("pool",)
    assert chat.schema is qh.HypothesisSchema and chat.kw == {}
    assert adapter.version == f"gpt-4o-mini|{qh.PROMPT_VERSION}"
    (role_s, system), (role_h, human) = chat.messages
    assert (role_s, role_h) == ("system", "human")
    assert "KHÔNG bao giờ trả mã sản phẩm" in system and "Nha Trang; Phú Quốc" in system and "pool:" in system
    assert "hotel, flight, attraction, combo, golf" in system and "Hà Nội; Nha Trang" in system
    assert query in human and '"mustNotAmenities": ["pool"]' in human and "null" not in human   # tóm tắt rule bỏ ô rỗng


@pytest.mark.parametrize("out,expected", [
    ({"taxonomy": "golf", "price_max": 2000000}, ("golf", 2000000)),
    ('{"taxonomy": "combo"}', ("combo", None)),
    ("không phải json", None),
    (None, None),
])
def test_loose_outputs(out, expected):
    h = qh.LangChainQueryHypothesizer(FakeChat(out), model_name="m").hypothesize("q", {})
    assert (None if h is None else (h.taxonomy, h.price_max)) == expected


def test_structured_method_is_passed_through():
    chat = FakeChat(None)
    qh.LangChainQueryHypothesizer(chat, model_name="m", method="function_calling")
    assert chat.kw == {"method": "function_calling"}


def test_provider_is_chosen_by_model_name_then_by_available_key():
    keys = dict(openai_api_key="", gemini_api_key="", anthropic_api_key="")
    assert qh._provider("gpt-4o-mini", **keys) == "openai"
    assert qh._provider("gemini-2.5-flash", **keys) == "gemini"
    assert qh._provider("claude-haiku-4-5", **keys) == "anthropic"
    assert qh._provider("my-model", **{**keys, "anthropic_api_key": "k"}) == "anthropic"
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        qh.build_query_hypothesizer(model="gpt-4o-mini")


def test_openai_adapter_builds_without_network():
    pytest.importorskip("langchain_openai")
    a = qh.build_query_hypothesizer(model="gpt-4o-mini", openai_api_key="sk-test", timeout_seconds=2.0)
    assert isinstance(a, qh.LangChainQueryHypothesizer) and a.model_name == "gpt-4o-mini"
    s = SimpleNamespace(search_llm_fallback_model="gpt-4o-mini", search_llm_fallback_timeout_ms=1500,
                        openai_api_key="sk-test", gemini_api_key="", anthropic_api_key="")
    assert qh.query_hypothesizer_from_settings(s).version == f"gpt-4o-mini|{qh.PROMPT_VERSION}"
