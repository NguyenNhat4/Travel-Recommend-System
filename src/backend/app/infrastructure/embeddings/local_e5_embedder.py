"""EmbedderPort chạy model `intfloat/multilingual-e5-small` trong tiến trình backend (FR-SRC-02, chốt 06/10).

`transformers` + `torch` CPU, không dùng sentence-transformers (gói này kéo scipy, DLL scipy bị Application Control chặn trên
máy dev). Làm đúng như bench `src/evaluation/search_bench/embed/local_hf.py` để vector của backend bằng vector bench đã đo:

- tiền tố `query: ` cho câu truy vấn, `passage: ` cho text catalog — thiếu/sai tiền tố làm giảm chất lượng mà không báo lỗi;
- mean pooling trên `last_hidden_state` theo `attention_mask`, rồi L2-normalize, float32;
- docs đi theo lô `batch_size` (bench: 32), padding tới text dài nhất lô.

Khác bench đúng một chỗ: bench từ chối text > 512 token, backend cắt ở `max_length` (512) và log cảnh báo — catalog hiện
tại không có text nào chạm trần (bench embed đủ 3.183 search unit không lỗi), nên vector không đổi.

Model và tokenizer nạp lười (import `torch` / `transformers` trong hàm), revision ghim theo `EMBED_MODEL_REVISION`.
Một khoá bao trọn tokenize + forward: tokenizer "fast" không an toàn khi nhiều luồng dùng chung, và forward song song chỉ
tranh nhau cùng số lõi CPU. Pooling làm bằng numpy (`mean_pool`) trên `last_hidden_state` float32 để test được không cần
torch: test tiêm `forward` giả (texts → hidden, mask), không tải model.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

import numpy as np

logger = logging.getLogger("uvicorn.error")

QUERY_PREFIX = "query: "
PASSAGE_PREFIX = "passage: "
PROBE_QUERY = "khách sạn gần biển Nha Trang"


def mean_pool(hidden: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Mean pooling theo attention mask (model card e5): (n, L, d) × (n, L) → (n, d) float32. Token đệm không được tính."""
    hidden = np.asarray(hidden, dtype=np.float32)
    m = np.asarray(mask, dtype=np.float32)[..., None]
    return (hidden * m).sum(axis=1) / np.clip(m.sum(axis=1), 1e-9, None)


def l2_normalize(x: np.ndarray) -> np.ndarray:
    """Giống `search_bench.embed.base.l2_normalize`: vector 0 giữ nguyên thay vì chia cho 0."""
    x = np.asarray(x, dtype=np.float32)
    n = np.linalg.norm(x, axis=1, keepdims=True)
    n[n == 0] = 1.0
    return x / n


class LocalE5Embedder:
    """`EmbedderPort` cho họ e5: `embed_docs` (passage), `embed_query` / `embed_queries` (query)."""

    def __init__(
        self,
        model_name: str = "intfloat/multilingual-e5-small",
        *,
        revision: str,
        dimension: int = 384,
        threads: int = 0,
        batch_size: int = 32,
        max_length: int = 512,
        cache_dir: str | None = None,
        device: str = "cpu",
        tokenizer: Any = None,
        model: Any = None,
        forward: Callable[[list[str]], tuple[np.ndarray, np.ndarray]] | None = None,
    ):
        if not revision:
            raise ValueError("EMBED_MODEL_REVISION phải ghim một commit Hugging Face cho model local")
        self.name = model_name
        self.revision = revision
        self.dimension = dimension
        self.threads = max(0, int(threads))
        self.batch_size = max(1, int(batch_size))
        self.max_length = max(8, int(max_length))
        self.cache_dir = cache_dir or None
        self.device = device
        self._tokenizer, self._model = tokenizer, model
        self._forward = forward
        self._load_lock = threading.Lock()
        self._encode_lock = threading.Lock()
        self._warned_truncation = False

    # ------------------------------------------------------------------ nạp lười
    def _load(self) -> tuple[Any, Any]:
        if self._tokenizer is not None and self._model is not None:
            return self._tokenizer, self._model
        with self._load_lock:
            if self._tokenizer is None or self._model is None:
                started = time.monotonic()
                try:
                    import torch
                    from transformers import AutoModel, AutoTokenizer
                except ImportError as exc:  # backend .venv chưa cài torch/transformers
                    raise RuntimeError(
                        "EMBED_PROVIDER=local cần torch + transformers: "
                        "pip install -r src/backend/requirements-embed.txt (xem src/backend/README.md)"
                    ) from exc
                if self.threads:
                    torch.set_num_threads(self.threads)
                logger.info("startup.recsys.embedding_model.load.start model=%s revision=%s threads=%s",
                            self.name, self.revision, self.threads or torch.get_num_threads())
                if self._tokenizer is None:
                    self._tokenizer = AutoTokenizer.from_pretrained(
                        self.name, revision=self.revision, cache_dir=self.cache_dir)
                if self._model is None:
                    model = AutoModel.from_pretrained(
                        self.name, revision=self.revision, cache_dir=self.cache_dir, use_safetensors=True)
                    model.eval()
                    self._model = model.to(self.device)
                logger.info("startup.recsys.embedding_model.load.ready model=%s seconds=%.1f",
                            self.name, time.monotonic() - started)
        return self._tokenizer, self._model

    # ------------------------------------------------------------------ encode
    def _torch_forward(self, texts: list[str]) -> tuple[np.ndarray, np.ndarray]:
        """Một lô (đã ghép tiền tố) → (`last_hidden_state` float32 (n, L, d), `attention_mask` (n, L)).

        Như `LocalHFEmbedder._encode_hf` của bench: padding tới text dài nhất lô; khác duy nhất là cắt ở `max_length`."""
        tok, model = self._load()   # trước `import torch`: thiếu torch thì _load báo lỗi kèm cách cài
        import torch

        with self._encode_lock:
            enc = tok(texts, padding=True, truncation=True, max_length=self.max_length, return_tensors="pt")
            if not self._warned_truncation and int(enc["attention_mask"].sum(1).max()) >= self.max_length:
                self._warned_truncation = True
                logger.warning("embedding.truncated model=%s max_length=%d — text chạm trần token, có thể bị cắt",
                               self.name, self.max_length)
            enc = {k: v.to(model.device) for k, v in enc.items()}
            with torch.inference_mode():
                hidden = model(**enc).last_hidden_state
            return hidden.float().cpu().numpy(), enc["attention_mask"].cpu().numpy()

    def _encode(self, texts: list[str]) -> np.ndarray:
        """Một lô (đã ghép tiền tố) → (n, dim) float32 chưa normalize."""
        hidden, mask = (self._forward or self._torch_forward)(texts)
        return mean_pool(hidden, mask)

    def _embed(self, texts: list[str], prefix: str) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)
        prefixed = [prefix + t for t in texts]
        parts = [self._encode(prefixed[s:s + self.batch_size]) for s in range(0, len(prefixed), self.batch_size)]
        arr = np.asarray(np.vstack(parts), dtype=np.float32)
        if arr.shape != (len(texts), self.dimension):
            raise RuntimeError(f"{self.name}: shape {arr.shape} ≠ ({len(texts)}, {self.dimension}) — kiểm EMBED_DIMENSION")
        return l2_normalize(arr)

    # ------------------------------------------------------------------ EmbedderPort
    def embed_docs(self, texts: list[str]) -> np.ndarray:
        return self._embed(list(texts), PASSAGE_PREFIX)

    def embed_query(self, q: str) -> np.ndarray:
        return self._embed([q], QUERY_PREFIX)[0]

    def embed_queries(self, texts: list[str]) -> np.ndarray:
        """Cả lô câu truy vấn (prewarm cache) — tiền tố `query: `, không dùng cho text catalog."""
        return self._embed(list(texts), QUERY_PREFIX)

    def warmup(self) -> float:
        """Nạp model và embed thử một câu (health: "model đã tải và embed thử một câu"); trả số mili-giây của câu thử."""
        if self._forward is None:
            self._load()
        started = time.perf_counter()
        vector = self.embed_query(PROBE_QUERY)
        ms = (time.perf_counter() - started) * 1000
        if vector.shape != (self.dimension,) or not np.isfinite(vector).all():
            raise RuntimeError(f"{self.name}: câu thử trả vector không hợp lệ shape={vector.shape}")
        logger.info("startup.recsys.embedding_model.probe model=%s ms=%.1f", self.name, ms)
        return ms

    def close(self) -> None:
        return None
