"""Part 3 — embedder local bằng `transformers` + `torch` (E2: `multilingual-e5-base`, `bge-m3`, `gte-multilingual-base`).

Không dùng sentence-transformers: gói này kéo scipy, mà DLL scipy bị Application Control chặn trên máy dev (30/09).
Pooling làm đúng model card: e5 = mean pooling trên `last_hidden_state` theo attention mask, bge-m3 / gte = vector
`[CLS]`; rồi L2-normalise. Config model: `pooling: mean | cls`, `query_prefix` / `passage_prefix` (e5 bắt buộc
`query: ` / `passage: `; thiếu prefix là arm E không công bằng), `max_seq_length`, `batch_size`, `device`.

- Prefix chỉ ghép lúc encode; khoá cache là text gốc + `input_type` + tên embedder (= `hf_model`).
- **Không cắt ngầm:** đếm token trước bằng tokenizer của model (kể cả prefix và token đặc biệt) và từ chối text vượt
  `max_seq_length` (`TokenLimitError`, spec §1.7 #2).
- Model và tokenizer nạp lười — `sb tokens` chỉ cần tokenizer, không nạp model. Test tiêm `encode_fn` / `tokenizer` giả.
- `stats` đếm lượt encode + token, USD = 0 (không ghi cost.jsonl).
"""
from __future__ import annotations

from typing import Any, Callable

import numpy as np

from ..config import ModelConfig
from .base import EmbedStats, InputType, TokenLimitError, check_input_type, l2_normalize

REQUIRED_LIBS = ("transformers", "torch")


class LocalHFEmbedder:
    def __init__(self, model_key: str, mcfg: ModelConfig, *, preflight: bool = True,
                 encode_fn: Callable[[list[str]], np.ndarray] | None = None, tokenizer: Any = None):
        if not mcfg.hf_model:
            raise ValueError(f"model {model_key} thiếu hf_model")
        self.model_key, self.mcfg = model_key, mcfg
        self.name = mcfg.hf_model
        self.dim = mcfg.dim
        self.batch = mcfg.batch_size or 32
        self.max_seq_length = mcfg.max_seq_length or 512
        self.pooling = mcfg.pooling or "mean"
        self.prefix: dict[str, str] = {"query": mcfg.query_prefix or "", "document": mcfg.passage_prefix or ""}
        self.stats = EmbedStats()
        self._preflight = preflight
        self._encode_fn, self._tokenizer, self._model = encode_fn, tokenizer, None

    # ------------------------------------------------------------------ nạp lười
    def tokenizer(self):
        if self._tokenizer is None:
            from transformers import AutoTokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(self.mcfg.hf_model, trust_remote_code=bool(self.mcfg.trust_remote_code))
        return self._tokenizer

    def _model_(self):
        if self._model is None:
            from transformers import AutoModel
            m = AutoModel.from_pretrained(self.mcfg.hf_model, trust_remote_code=bool(self.mcfg.trust_remote_code))
            m.eval()
            self._model = m.to(self.mcfg.device or "cpu")
        return self._model

    def _encode_hf(self, texts: list[str]) -> np.ndarray:
        """Một lô (đã ghép prefix) → (n, dim) float32 chưa normalise; padding tới text dài nhất lô, không cắt."""
        import torch
        tok, model = self.tokenizer(), self._model_()
        enc = tok(texts, padding=True, truncation=False, return_tensors="pt")
        enc = {k: v.to(model.device) for k, v in enc.items()}
        with torch.inference_mode():
            hidden = model(**enc).last_hidden_state
        if self.pooling == "cls":
            pooled = hidden[:, 0]
        else:
            mask = enc["attention_mask"].unsqueeze(-1).to(hidden.dtype)
            pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
        return pooled.float().cpu().numpy()

    # ------------------------------------------------------------------ token
    def with_prefix(self, texts: list[str], input_type: InputType) -> list[str]:
        p = self.prefix[input_type]
        return [p + t for t in texts]

    def count_tokens(self, texts: list[str], input_type: InputType = "document") -> list[int]:
        """Số token từng text kể cả prefix và token đặc biệt, không cắt."""
        if not texts:
            return []
        enc = self.tokenizer()(self.with_prefix(texts, input_type), add_special_tokens=True, truncation=False)
        return [len(ids) for ids in enc["input_ids"]]

    def preflight(self, texts: list[str]) -> list[int] | None:
        """Text vượt max_seq_length (đếm với prefix dài nhất) → TokenLimitError trước khi encode."""
        if not self._preflight or not texts:
            return None
        longest = "document" if len(self.prefix["document"]) >= len(self.prefix["query"]) else "query"
        counts = self.count_tokens(texts, longest)
        over = [(i, c) for i, c in enumerate(counts) if c > self.max_seq_length]
        if over:
            raise TokenLimitError(over, self.max_seq_length)
        return counts

    # ------------------------------------------------------------------ embed
    def embed(self, texts: list[str], input_type: InputType) -> np.ndarray:
        check_input_type(input_type)
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        counts = self.preflight(list(texts))
        encode = self._encode_fn or self._encode_hf
        prefixed = self.with_prefix(list(texts), input_type)
        parts = [encode(prefixed[s:s + self.batch]) for s in range(0, len(prefixed), self.batch)]
        arr = np.asarray(np.vstack(parts), dtype=np.float32)
        if arr.shape != (len(texts), self.dim):
            raise RuntimeError(f"{self.name}: shape {arr.shape} ≠ ({len(texts)}, {self.dim}) — kiểm dim / pooling trong config")
        self.stats.n_calls += len(parts)
        self.stats.n_tokens += sum(counts) if counts else 0
        return l2_normalize(arr)

    def close(self) -> None:
        return None
