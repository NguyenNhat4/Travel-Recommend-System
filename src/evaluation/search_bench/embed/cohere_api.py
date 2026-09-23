"""Part 3 — Cohere embed qua API trực tiếp (`cohere.ClientV2`).

- `input_type` map từ config (`search_document` / `search_query`) — spec §1.7: không đổi mặc định; E3 là arm duy nhất sai cố ý.
- `truncate="NONE"`: text vượt giới hạn là lỗi của text builder, không cắt ngầm. Có bộ đếm token offline thì từ chối trước
  khi gọi API; không có thì API trả 400 và lỗi nêu đúng lô.
- Lô ≤ min(max_batch, 96). Pacer giữ tổng input/phút ≤ embedding.max_inputs_per_min (không chạy hai embed song song).
- Retry của SDK tắt (`max_retries: 0`); tự retry 429 / 5xx / timeout theo `embedding.retry`: `max_attempts` = số lần
  thử LẠI sau lượt đầu, lần thử lại thứ i chờ `backoff_s[i-1]` (dùng đủ mọi mức, 6 mức = 63 s > cửa sổ rate limit 60 s),
  ưu tiên header Retry-After.
- Mọi lượt gọi HTTP đều ghi cost.jsonl — thành công (`meta.billed_units.input_tokens`) lẫn thất bại (`failed: true`,
  0 token) — vì quota key trial tính theo lượt gọi. Key không bao giờ vào log.
"""
from __future__ import annotations

import time
from collections import deque
from typing import Any, Callable

import httpx
import numpy as np
import structlog

from .. import costlog
from ..config import EmbeddingConfig, ModelConfig
from .base import EmbedBatchError, EmbedStats, InputType, TokenLimitError, check_input_type, l2_normalize

log = structlog.get_logger("sbench.cohere")

RETRYABLE_STATUS = (429, 500, 502, 503, 504)
MAX_API_BATCH = 96                       # giới hạn cứng của Cohere embed


class Pacer:
    """Cửa sổ trượt 60 s: trước khi gửi n input, chờ tới khi tổng input trong 60 s gần nhất + n ≤ giới hạn."""

    def __init__(self, max_per_min: int, *, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep, window_s: float = 60.0):
        self.max_per_min, self.clock, self.sleep, self.window_s = max_per_min, clock, sleep, window_s
        self._sent: deque[tuple[float, int]] = deque()

    def wait(self, n: int) -> float:
        waited = 0.0
        while True:
            now = self.clock()
            while self._sent and now - self._sent[0][0] >= self.window_s:
                self._sent.popleft()
            used = sum(k for _, k in self._sent)
            if not self._sent or used + n <= self.max_per_min:
                self._sent.append((now, n))
                return waited
            pause = self.window_s - (now - self._sent[0][0])
            self.sleep(pause)
            waited += pause


def _retry_after(err: Exception) -> float | None:
    headers = getattr(err, "headers", None) or {}
    for k, v in headers.items():
        if k.lower() == "retry-after":
            try:
                return float(v)
            except (TypeError, ValueError):
                return None
    return None


def _body_snippet(err: Exception, secret: str | None) -> str:
    body = getattr(err, "body", None)
    msg = str(body if body is not None else err)
    if secret:
        msg = msg.replace(secret, "***")
    return msg[:300]


class CohereEmbedder:
    def __init__(self, model_key: str, mcfg: ModelConfig, ecfg: EmbeddingConfig, *, api_key: str,
                 embedding_type: str = "float", client: Any = None, sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic, token_counter: Any = None, token_hard_max: int | None = None):
        if not mcfg.api_model:
            raise ValueError(f"model {model_key} thiếu api_model")
        if embedding_type not in ("float", "int8"):
            raise ValueError(f"embedding_type {embedding_type!r} chưa hỗ trợ (float | int8)")
        self.model_key, self.mcfg, self.ecfg = model_key, mcfg, ecfg
        self.api_model = mcfg.api_model
        self.embedding_type = embedding_type
        self.dim = mcfg.output_dimension or mcfg.dim
        self.batch = min(mcfg.max_batch or MAX_API_BATCH, MAX_API_BATCH)
        self.name = self.api_model + (f"@d{mcfg.output_dimension}" if mcfg.output_dimension else "") + \
            ("@int8" if embedding_type == "int8" else "")
        self.price = ecfg.cost_per_1m_tokens_usd.get(model_key)
        if self.price is None:
            raise ValueError(f"thiếu embedding.cost_per_1m_tokens_usd.{model_key}")
        self._secret = api_key
        self._http = None
        if client is None:
            import cohere
            self._http = httpx.Client(timeout=60)
            client = cohere.ClientV2(api_key=api_key, httpx_client=self._http)
        self.client = client
        self.sleep = sleep
        self.pacer = Pacer(ecfg.max_inputs_per_min, clock=clock, sleep=sleep)
        self.token_counter = token_counter
        self.token_hard_max = token_hard_max
        self.stats = EmbedStats()

    def close(self) -> None:
        if self._http is not None:
            self._http.close()

    # ------------------------------------------------------------------
    def preflight(self, texts: list[str]) -> None:
        if self.token_counter is None or self.token_hard_max is None:
            return
        counts = self.token_counter.count(texts)
        over = [(i, c) for i, c in enumerate(counts) if c > self.token_hard_max]
        if over:
            raise TokenLimitError(over, self.token_hard_max)

    def embed(self, texts: list[str], input_type: InputType) -> np.ndarray:
        check_input_type(input_type)
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        self.preflight(texts)
        api_it = self.ecfg.input_type[input_type]
        out = []
        for start in range(0, len(texts), self.batch):
            batch = texts[start:start + self.batch]
            self.pacer.wait(len(batch))
            resp, attempts = self._call(batch, api_it, start)
            vecs = self._vectors(resp, len(batch), start)
            tokens = int(getattr(getattr(getattr(resp, "meta", None), "billed_units", None), "input_tokens", 0) or 0)
            usd = tokens / 1e6 * self.price
            self.stats.n_calls += 1
            self.stats.n_tokens += tokens
            self.stats.usd += usd
            costlog.append(endpoint="embed", model=self.api_model, input_type=api_it, n_texts=len(batch), n_tokens=tokens,
                           usd=usd, embedding_type=self.embedding_type, attempts=attempts)
            out.append(vecs)
        return l2_normalize(np.vstack(out))

    def _call(self, batch: list[str], api_input_type: str, start: int):
        from cohere.core.api_error import ApiError
        kwargs: dict[str, Any] = dict(model=self.api_model, texts=batch, input_type=api_input_type,
                                      embedding_types=[self.embedding_type], truncate=self.mcfg.truncate or "NONE",
                                      request_options={"max_retries": 0})
        if self.mcfg.output_dimension:
            kwargs["output_dimension"] = self.mcfg.output_dimension
        retry = self.ecfg.retry
        for attempt in range(1, retry.max_attempts + 2):          # lượt đầu + max_attempts lần thử lại
            try:
                return self.client.embed(**kwargs), attempt
            except ApiError as e:
                status = e.status_code
                self._log_failure(batch, api_input_type, attempt, status)
                if status not in RETRYABLE_STATUS or attempt > retry.max_attempts:
                    raise EmbedBatchError(list(range(start, start + len(batch))), status, _body_snippet(e, self._secret)) from None
                wait = _retry_after(e) or self._backoff(attempt)
                log.warning("Cohere lỗi, thử lại", status=status, attempt=attempt, wait_s=wait)
            except (httpx.TimeoutException, httpx.TransportError) as e:
                self._log_failure(batch, api_input_type, attempt, None, error=type(e).__name__)
                if attempt > retry.max_attempts:
                    raise EmbedBatchError(list(range(start, start + len(batch))), None, type(e).__name__) from None
                wait = self._backoff(attempt)
                log.warning("Cohere mạng lỗi, thử lại", error=type(e).__name__, attempt=attempt, wait_s=wait)
            self.sleep(wait)
        raise AssertionError("unreachable")

    def _backoff(self, attempt: int) -> float:
        b = self.ecfg.retry.backoff_s
        return b[min(attempt - 1, len(b) - 1)]

    def _log_failure(self, batch: list[str], api_input_type: str, attempt: int, status: int | None, **extra) -> None:
        costlog.append(endpoint="embed", model=self.api_model, input_type=api_input_type, n_texts=len(batch), n_tokens=0,
                       usd=0.0, embedding_type=self.embedding_type, attempt=attempt, status=status, failed=True, **extra)

    def _vectors(self, resp: Any, n: int, start: int) -> np.ndarray:
        emb = getattr(resp, "embeddings", None)
        raw = getattr(emb, "float_", None) if self.embedding_type == "float" else getattr(emb, "int8", None)
        if raw is None and self.embedding_type == "float":
            raw = getattr(emb, "float", None)
        if raw is None or len(raw) != n:
            raise EmbedBatchError(list(range(start, start + n)), None, f"response thiếu embeddings.{self.embedding_type} ({n} text)")
        arr = np.asarray(raw, dtype=np.float32)
        if arr.shape != (n, self.dim):
            raise EmbedBatchError(list(range(start, start + n)), None, f"shape {arr.shape} ≠ ({n}, {self.dim})")
        return arr
