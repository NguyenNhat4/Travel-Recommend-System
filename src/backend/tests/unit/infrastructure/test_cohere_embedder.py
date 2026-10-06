import threading

import httpx
import numpy as np
import pytest

from src.backend.app.application.ports.embedder import EmbeddingUnavailableError
from src.backend.app.infrastructure.embeddings.cohere_embedder import CallLimiter, CohereEmbedder


def test_cohere_uses_document_and_query_input_types_and_normalizes():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = __import__("json").loads(request.content)
        seen.append(payload)
        vectors = [[3.0, 4.0] + [0.0] * 1022 for _ in payload["texts"]]
        return httpx.Response(200, json={"embeddings": {"float": vectors}})

    client = httpx.Client(base_url="https://cohere.test", transport=httpx.MockTransport(handler))
    embedder = CohereEmbedder("test-key", client=client)

    docs = embedder.embed_docs([f"doc {i}" for i in range(97)])
    query = embedder.embed_query("nha trang")

    assert docs.shape == (97, 1024)
    assert np.allclose(np.linalg.norm(docs, axis=1), 1.0)
    assert np.isclose(np.linalg.norm(query), 1.0)
    assert [call["input_type"] for call in seen] == ["search_document", "search_document", "search_query"]
    assert [len(call["texts"]) for call in seen] == [96, 1, 1]
    assert all(call["model"] == "embed-multilingual-v3.0" for call in seen)


def test_embed_queries_batches_with_search_query_input_type():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = __import__("json").loads(request.content)
        seen.append(payload)
        return httpx.Response(200, json={"embeddings": {"float": [[3.0, 4.0] + [0.0] * 1022 for _ in payload["texts"]]}})
    embedder = CohereEmbedder("test-key", client=httpx.Client(base_url="https://cohere.test", transport=httpx.MockTransport(handler)))

    vectors = embedder.embed_queries([f"câu {i}" for i in range(97)])

    assert vectors.shape == (97, 1024) and np.allclose(np.linalg.norm(vectors, axis=1), 1.0)
    assert [(call["input_type"], len(call["texts"])) for call in seen] == [("search_query", 96), ("search_query", 1)]
    assert embedder.embed_queries([]).shape == (0, 1024) and len(seen) == 2


def test_cohere_rejects_wrong_dimension():
    client = httpx.Client(
        base_url="https://cohere.test",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"embeddings": {"float": [[1.0, 2.0]]}})),
    )
    with pytest.raises(RuntimeError, match="expected .*1024"):
        CohereEmbedder("test-key", client=client).embed_query("query")


# ---------------------------------------------------------------- P5.1: giới hạn tốc độ dùng chung (CallLimiter)
class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(round(seconds, 3))
        self.now += seconds


def ok_handler(request: httpx.Request) -> httpx.Response:
    texts = __import__("json").loads(request.content)["texts"]
    return httpx.Response(200, json={"embeddings": {"float": [[1.0] + [0.0] * 1023 for _ in texts]}})


def test_limiter_keeps_calls_per_sliding_minute():
    clock = FakeClock()
    limiter = CallLimiter(3, clock=clock, sleep=clock.sleep)
    times = []
    for _ in range(7):
        limiter.acquire()
        times.append(clock.now)
        clock.now += 1.0  # mỗi lần gọi mất 1 s
    # 3 lần đầu ở 0, 1, 2 s; lần 4 phải chờ tới khi lần 1 ra khỏi cửa sổ (60 s)
    assert times == [0.0, 1.0, 2.0, 60.0, 61.0, 62.0, 120.0]
    assert limiter.calls == 7
    for start in range(len(times) - 3):  # không cửa sổ 60 s nào có hơn 3 lần gọi
        assert times[start + 3] - times[start] >= 60.0


def test_zero_means_unlimited():
    clock = FakeClock()
    limiter = CallLimiter(0, clock=clock, sleep=clock.sleep)
    for _ in range(500):
        limiter.acquire()
    assert clock.sleeps == [] and limiter.calls == 500


def test_pause_after_429_holds_every_caller_and_honours_retry_after():
    clock = FakeClock()
    limiter = CallLimiter(90, clock=clock, sleep=clock.sleep)
    answers = iter([httpx.Response(429, headers={"Retry-After": "5"}, json={}), None, None])

    def handler(request):
        return next(answers) or ok_handler(request)

    client = httpx.Client(base_url="https://cohere.test", transport=httpx.MockTransport(handler))
    embedder = CohereEmbedder("k", client=client, limiter=limiter)
    embedder.embed_docs(["a"])  # 429 → pause 5 s → gọi lại thành công
    assert (limiter.rate_limited, clock.sleeps, clock.now) == (1, [5.0], 5.0)
    limiter.pause(10)  # một luồng khác vừa bị 429: luồng này cũng phải chờ
    embedder.embed_docs(["b"])
    assert clock.sleeps == [5.0, 10.0]


def test_without_limiter_backoff_is_unchanged(monkeypatch):
    slept = []
    monkeypatch.setattr("src.backend.app.infrastructure.embeddings.cohere_embedder.time.sleep", slept.append)
    answers = iter([httpx.Response(503, json={}), None])
    client = httpx.Client(base_url="https://cohere.test",
                          transport=httpx.MockTransport(lambda r: next(answers) or ok_handler(r)))
    CohereEmbedder("k", client=client).embed_query("q")
    assert slept == [2.0]  # như trước P5: backoff 2^(attempt+1)


def test_threads_sharing_a_limiter_never_exceed_the_limit():
    lock = threading.Lock()
    clock = FakeClock()

    def sleep(seconds):  # nhiều luồng cùng "chờ": đồng hồ giả tiến tới thời điểm được gọi
        with lock:
            clock.now = max(clock.now, clock.now + seconds)
    limiter = CallLimiter(5, clock=lambda: clock.now, sleep=sleep)
    stamps = []

    def worker():
        for _ in range(4):
            limiter.acquire()
            with lock:
                stamps.append(clock.now)
    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    stamps.sort()
    assert len(stamps) == 16
    for start in range(len(stamps) - 5):
        assert stamps[start + 5] - stamps[start] >= 60.0


# ------------------------------------------------------------------ lỗi Cohere không được im lặng

QUOTA_BODY = {"message": "You are using a Trial key, which is limited to 1000 API calls / month."}


def failing_client(*responses):
    calls = []

    def handler(request):
        calls.append(request)
        return responses[min(len(calls), len(responses)) - 1]
    return httpx.Client(base_url="https://cohere.test", transport=httpx.MockTransport(handler)), calls


def test_monthly_quota_fails_at_once_with_a_named_reason(monkeypatch, caplog):
    slept = []
    monkeypatch.setattr("src.backend.app.infrastructure.embeddings.cohere_embedder.time.sleep", slept.append)
    client, calls = failing_client(httpx.Response(429, json=QUOTA_BODY))
    with caplog.at_level("WARNING", logger="uvicorn.error"), pytest.raises(EmbeddingUnavailableError) as caught:
        CohereEmbedder("secret-key", client=client).embed_query("khách sạn bí mật")
    assert (caught.value.reason, caught.value.retryable, caught.value.status) == ("quota_exhausted", False, 429)
    assert len(calls) == 1 and slept == []  # hạn mức tháng: thử lại vô ích
    assert "cohere.embed.failed status=429 reason=quota_exhausted" in caplog.text
    assert "cohere.embed.gave_up reason=quota_exhausted" in caplog.text
    # Không lộ key, câu truy vấn hay thông điệp của Cohere.
    assert "secret-key" not in caplog.text and "bí mật" not in caplog.text and "Trial" not in caplog.text


def test_query_retries_stay_within_the_wait_budget(monkeypatch, caplog):
    slept = []
    monkeypatch.setattr("src.backend.app.infrastructure.embeddings.cohere_embedder.time.sleep", slept.append)
    client, calls = failing_client(httpx.Response(429, json={"message": "too many requests"}))
    with caplog.at_level("WARNING", logger="uvicorn.error"), pytest.raises(EmbeddingUnavailableError) as caught:
        CohereEmbedder("k", client=client, max_wait_seconds=2).embed_query("q")
    assert (caught.value.reason, caught.value.retryable) == ("rate_limited", True)
    assert slept == [2.0] and len(calls) == 2  # lần chờ kế (4 s) vượt ngân sách 2 s nên dừng
    assert caplog.text.count("cohere.embed.failed") == 2


def test_without_budget_5xx_still_gives_up_with_a_named_error(monkeypatch):
    slept = []
    monkeypatch.setattr("src.backend.app.infrastructure.embeddings.cohere_embedder.time.sleep", slept.append)
    client, calls = failing_client(httpx.Response(503, json={}))
    with pytest.raises(EmbeddingUnavailableError) as caught:
        CohereEmbedder("k", client=client).embed_query("q")
    assert (caught.value.reason, caught.value.status) == ("upstream_5xx", 503)
    assert len(calls) == CohereEmbedder.max_attempts  # job index: vẫn thử đủ lượt như trước
    assert slept == [2.0, 4.0, 8.0, 16.0, 32.0]


def test_other_4xx_and_network_errors_are_named():
    client, _ = failing_client(httpx.Response(401, json={"message": "invalid api token"}))
    with pytest.raises(EmbeddingUnavailableError) as caught:
        CohereEmbedder("k", client=client).embed_query("q")
    assert (caught.value.reason, caught.value.status) == ("http_error", 401)

    def timeout(request):
        raise httpx.ReadTimeout("slow", request=request)
    client = httpx.Client(base_url="https://cohere.test", transport=httpx.MockTransport(timeout))
    with pytest.raises(EmbeddingUnavailableError) as caught:
        CohereEmbedder("k", client=client).embed_query("q")
    assert caught.value.reason == "timeout"
