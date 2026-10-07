"""EmbedderPort chạy `intfloat/multilingual-e5-small` trong tiến trình (PRD FR-SRC-02, chốt 06/10/2026).

Cùng cách với embedder bench đã đo (`src/evaluation/search_bench/embed/local_hf.py`): `transformers` + `torch` CPU, mean
pooling trên `last_hidden_state` theo attention mask, L2-normalize; không dùng sentence-transformers (kéo scipy).

- Tiền tố bắt buộc của e5: `passage: ` cho văn bản sản phẩm, `query: ` cho câu truy vấn. Hai lời gọi nằm chung adapter
  để caller không tráo được (như `input_type` của các API embedding); thiếu tiền tố làm giảm chất lượng mà không báo lỗi.
- Revision ghim (`EMBED_MODEL_REVISION`) để vector query và document luôn từ cùng trọng số; chỉ đọc `safetensors`.
- Văn bản dài hơn `max_tokens` (kể cả tiền tố) bị cắt đuôi (cắt đuôi).
- Model nạp lười, một lần, có khoá: lần gọi đầu (prewarm hoặc request đầu) trả chi phí nạp. Test tiêm `encode_fn`.
"""
from __future__ import annotations

import threading
from typing import Callable

import numpy as np

QUERY_PREFIX = "query: "
PASSAGE_PREFIX = "passage: "


class LocalE5Embedder:
    def __init__(
        self,
        model_name: str = "intfloat/multilingual-e5-small",
        *,
        revision: str | None = None,
        dimension: int = 384,
        device: str = "cpu",
        batch_size: int = 32,
        max_tokens: int = 512,
        encode_fn: Callable[[list[str]], np.ndarray] | None = None,
    ):
        self.name = model_name
        self.revision = revision
        self.dimension = dimension
        self.device = device
        self.batch_size = batch_size
        self.max_tokens = max_tokens
        self._encode_fn = encode_fn
        self._lock = threading.Lock()
        self._tokenizer = None
        self._model = None

    def _load(self):
        with self._lock:
            if self._model is None:
                from transformers import AutoModel, AutoTokenizer

                tokenizer = AutoTokenizer.from_pretrained(self.name, revision=self.revision)
                model = AutoModel.from_pretrained(self.name, revision=self.revision, use_safetensors=True)
                model.eval()
                self._tokenizer, self._model = tokenizer, model.to(self.device)
        return self._tokenizer, self._model

    def _encode_hf(self, texts: list[str]) -> np.ndarray:
        """Một lô đã ghép tiền tố → (n, dim) float32 chưa normalize."""
        import torch

        tokenizer, model = self._load()
        batch = tokenizer(texts, padding=True, truncation=True, max_length=self.max_tokens, return_tensors="pt")
        batch = {key: value.to(model.device) for key, value in batch.items()}
        with torch.inference_mode():
            hidden = model(**batch).last_hidden_state
        mask = batch["attention_mask"].unsqueeze(-1).to(hidden.dtype)
        pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
        return pooled.float().cpu().numpy()

    def _embed(self, texts: list[str], prefix: str) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)
        encode = self._encode_fn or self._encode_hf
        prefixed = [prefix + text for text in texts]
        parts = [encode(prefixed[i : i + self.batch_size]) for i in range(0, len(prefixed), self.batch_size)]
        vectors = np.asarray(np.vstack(parts), dtype=np.float32)
        if vectors.shape != (len(texts), self.dimension):
            raise RuntimeError(f"{self.name} trả shape {vectors.shape}; cần ({len(texts)}, {self.dimension})")
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        if np.any(norms == 0):
            raise RuntimeError(f"{self.name} trả vector độ dài 0")
        return vectors / norms

    def embed_docs(self, texts: list[str]) -> np.ndarray:
        return self._embed(list(texts), PASSAGE_PREFIX)

    def embed_query(self, q: str) -> np.ndarray:
        return self._embed([q], QUERY_PREFIX)[0]

    def embed_queries(self, texts: list[str]) -> np.ndarray:
        """Cả lô câu truy vấn (prewarm cache): tiền tố `query: ` — không dùng cho văn bản catalog."""
        return self._embed(list(texts), QUERY_PREFIX)

    def close(self) -> None:
        return None
