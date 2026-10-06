"""Reranker offline (kiến trúc search OTA, Phase D "reranker offline") — CHỈ trong bench, không chạm backend / production.

Arm APP khai `rerank: {model, top_n, parent_engine: app, query, batch_size, max_length}`: `app_adapter.retrieve_app` gọi
`SearchProducts` với `limit = top_n` (cùng khối `app` của arm cha → cùng mask / filter / cutoff), chấm từng cặp
(câu hỏi, text T3+R của unit — `AppCatalog.texts` = `text_T3+R.parquet`) bằng cross-encoder trên CPU, sắp lại theo điểm
(hoà điểm → giữ thứ tự cũ của engine) rồi cắt top-k. Trường `score` (cosine) của từng unit đi theo unit, không đổi nghĩa.

- Model: `transformers` `AutoModelForSequenceClassification` (không dùng sentence-transformers — gói kéo scipy, DLL scipy bị
  Application Control chặn trên máy dev, xem `embed/local_hf.py`), trọng số safetensors, `eval()`, CPU. bge-reranker trả một
  logit mỗi cặp = điểm (không sigmoid: thứ tự như nhau).
- Cặp vượt `max_length` token bị cắt phía text unit (`truncation="only_second"`, cách dùng chuẩn của cross-encoder — khác
  embedder của bench vốn cấm cắt ngầm); số cặp bị cắt ghi vào `extra.rerank.truncated`.
- Cache sqlite `bench_out/search/cache/rerank.sqlite`: khoá (model, query, product_id, sha1 text unit, max_length) → logit
  + thời gian model chia đều theo cặp lúc chấm. Chạy lại = 0 lượt model; `modelMs` của câu = tổng thời gian đã ghi của N
  cặp (ước lượng CPU lạnh, ổn định qua các lần chạy), `ms` = thời gian tường thật của lượt này (gần 0 khi cache trúng);
  cả hai không gồm lần nạp model đầu tiên (~8 s cho bge-reranker-v2-m3).
- Model nạp lười, một lần mỗi tiến trình cho mỗi (model, max_length) — hai arm rerank trong cùng `sb run` dùng chung.
"""
from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

import numpy as np

from . import paths

RERANK_CACHE = "rerank.sqlite"
#: khoá bắt buộc của `rerank:` trong arm yaml (spec §1.5: mọi con số vào config, không mặc định ngầm trong code)
RERANK_KEYS = ("model", "top_n", "parent_engine", "query", "batch_size", "max_length")
RERANK_QUERY_MODES = ("raw", "normalized")
#: `SearchProducts.max_limit` của backend — top_n lớn hơn sẽ bị engine cắt im lặng
MAX_TOP_N = 50
_CHUNK = 500


class RerankError(ValueError):
    pass


def rerank_params(arm_rerank: dict | None, *, k: int) -> dict:
    """Tham số `rerank:` của arm đã kiểm: đủ khoá, `parent_engine: app`, k ≤ top_n ≤ MAX_TOP_N, query raw | normalized."""
    p = dict(arm_rerank or {})
    missing = [key for key in RERANK_KEYS if key not in p]
    if missing:
        raise RerankError(f"arm rerank thiếu rerank.{', rerank.'.join(missing)} (xem arms/APP.*_rr.yaml)")
    if p["parent_engine"] != "app":
        raise RerankError(f"rerank.parent_engine = {p['parent_engine']!r} — hôm nay chỉ cài cho cổng APP (app)")
    if p["query"] not in RERANK_QUERY_MODES:
        raise RerankError(f"rerank.query = {p['query']!r} ({' | '.join(RERANK_QUERY_MODES)})")
    top_n = int(p["top_n"])
    if not k <= top_n <= MAX_TOP_N:
        raise RerankError(f"rerank.top_n = {top_n}: phải trong [{k} (k của metric), {MAX_TOP_N} (max_limit của /search)]")
    if int(p["batch_size"]) < 1 or int(p["max_length"]) < 16:
        raise RerankError(f"rerank.batch_size ≥ 1, rerank.max_length ≥ 16 (đang {p['batch_size']}, {p['max_length']})")
    return {**p, "top_n": top_n, "batch_size": int(p["batch_size"]), "max_length": int(p["max_length"])}


def text_sha(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def pair_key(model: str, query: str, product_id: str, text: str, max_length: int) -> str:
    """Khoá cache của một cặp: đổi model / câu / unit / text unit / max_length → khoá khác (không dùng điểm cũ)."""
    return hashlib.sha1(f"{model}|{max_length}|{query}|{product_id}|{text_sha(text)}".encode("utf-8")).hexdigest()


class RerankCache:
    """sqlite: key → (score, ms). `ms` = thời gian model của lô chia đều cho số cặp lúc chấm."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._db = sqlite3.connect(str(path))
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("CREATE TABLE IF NOT EXISTS rerank (key TEXT PRIMARY KEY, model TEXT NOT NULL, query TEXT NOT NULL, "
                         "product_id TEXT NOT NULL, score REAL NOT NULL, ms REAL NOT NULL, created_at TEXT NOT NULL)")
        self._db.commit()

    def get_many(self, keys: list[str]) -> dict[str, tuple[float, float]]:
        out: dict[str, tuple[float, float]] = {}
        for i in range(0, len(keys), _CHUNK):
            chunk = keys[i:i + _CHUNK]
            q = f"SELECT key, score, ms FROM rerank WHERE key IN ({','.join('?' * len(chunk))})"
            for key, score, ms in self._db.execute(q, chunk):
                out[key] = (float(score), float(ms))
        return out

    def put_many(self, rows: list[tuple[str, str, str, str, float, float]]) -> None:
        """rows: (key, model, query, product_id, score, ms)."""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._db.executemany("INSERT OR REPLACE INTO rerank (key, model, query, product_id, score, ms, created_at) "
                             "VALUES (?, ?, ?, ?, ?, ?, ?)", [(*r, now) for r in rows])
        self._db.commit()

    def count(self, model: str | None = None) -> int:
        if model is None:
            return self._db.execute("SELECT COUNT(*) FROM rerank").fetchone()[0]
        return self._db.execute("SELECT COUNT(*) FROM rerank WHERE model = ?", (model,)).fetchone()[0]

    def close(self) -> None:
        self._db.close()


#: chấm một lô cặp → (logit từng cặp, số cặp bị cắt vì vượt max_length)
ScoreFn = Callable[[list[tuple[str, str]]], tuple[np.ndarray, int]]


class CrossEncoderScorer:
    """Cross-encoder HF nạp lười trên CPU; `__call__(pairs)` → (logit float32, số cặp bị cắt)."""

    def __init__(self, model: str, *, max_length: int, device: str = "cpu"):
        self.model_name, self.max_length, self.device = model, max_length, device
        self._tok: Any = None
        self._model: Any = None

    def load(self) -> None:
        """Nạp tokenizer + model (một lần); `Reranker` gọi trước khi bấm giờ để `modelMs` không gồm thời gian nạp."""
        if self._model is None:
            try:
                from transformers import AutoModelForSequenceClassification, AutoTokenizer
            except Exception as e:  # noqa: BLE001
                raise RerankError(f"rerank cần transformers + torch trong .venv-sbench: {type(e).__name__}: {e}") from None
            self._tok = AutoTokenizer.from_pretrained(self.model_name)
            m = AutoModelForSequenceClassification.from_pretrained(self.model_name, use_safetensors=True)
            m.eval()
            self._model = m.to(self.device)

    def __call__(self, pairs: list[tuple[str, str]]) -> tuple[np.ndarray, int]:
        import torch
        self.load()
        full = self._tok([q for q, _ in pairs], [t for _, t in pairs], truncation=False)["input_ids"]
        truncated = sum(1 for ids in full if len(ids) > self.max_length)
        enc = self._tok([q for q, _ in pairs], [t for _, t in pairs], padding=True, truncation="only_second",
                        max_length=self.max_length, return_tensors="pt")
        enc = {k: v.to(self._model.device) for k, v in enc.items()}
        with torch.inference_mode():
            logits = self._model(**enc).logits
        return logits.view(len(pairs), -1)[:, 0].float().cpu().numpy().astype(np.float32), truncated


@dataclass
class RerankResult:
    order: list[int]              # chỉ số trong danh sách đầu vào, theo điểm giảm dần (hoà → thứ tự engine)
    scores: list[float]           # logit theo `order`
    ms: float                     # thời gian tường của lượt này (cache + model)
    model_ms: float               # tổng thời gian model đã ghi của mọi cặp (ước lượng CPU lạnh)
    n_scored: int                 # cặp chấm mới bằng model
    n_cached: int                 # cặp lấy từ cache
    n_truncated: int              # cặp bị cắt (chỉ đếm được ở cặp chấm mới)


class Reranker:
    def __init__(self, model: str, *, batch_size: int, max_length: int, cache: RerankCache | None,
                 score_fn: ScoreFn | None = None):
        self.model, self.batch_size, self.max_length = model, batch_size, max_length
        self.cache = cache
        self.score_fn: ScoreFn = score_fn or CrossEncoderScorer(model, max_length=max_length)
        self.n_scored = 0
        self.n_cached = 0

    def rerank(self, query: str, ids: list[str], texts: list[str]) -> RerankResult:
        if len(ids) != len(texts):
            raise RerankError(f"{len(ids)} id nhưng {len(texts)} text")
        t0 = perf_counter()
        keys = [pair_key(self.model, query, pid, t, self.max_length) for pid, t in zip(ids, texts)]
        got = self.cache.get_many(keys) if self.cache is not None else {}
        todo = [i for i, key in enumerate(keys) if key not in got]
        if todo and hasattr(self.score_fn, "load"):
            tl = perf_counter()
            self.score_fn.load()                       # nạp model không tính vào thời gian chấm của câu
            t0 += perf_counter() - tl
        truncated = 0
        rows = []
        for s in range(0, len(todo), self.batch_size):
            part = todo[s:s + self.batch_size]
            tb = perf_counter()
            scores, n_trunc = self.score_fn([(query, texts[i]) for i in part])
            per = (perf_counter() - tb) * 1000.0 / len(part)
            truncated += n_trunc
            for i, sc in zip(part, np.asarray(scores, dtype=np.float32).tolist()):
                got[keys[i]] = (float(sc), per)
                rows.append((keys[i], self.model, query, ids[i], float(sc), per))
        if rows and self.cache is not None:
            self.cache.put_many(rows)
        self.n_scored += len(todo)
        self.n_cached += len(ids) - len(todo)
        sc = [got[key][0] for key in keys]
        order = sorted(range(len(ids)), key=lambda i: (-sc[i], i))
        return RerankResult(order=order, scores=[sc[i] for i in order], ms=(perf_counter() - t0) * 1000.0,
                            model_ms=float(sum(got[key][1] for key in keys)), n_scored=len(todo),
                            n_cached=len(ids) - len(todo), n_truncated=truncated)

    def close(self) -> None:
        if self.cache is not None:
            self.cache.close()
            self.cache = None


_SCORERS: dict[tuple[str, int], CrossEncoderScorer] = {}


def open_reranker(p: dict, *, cache_path: Path | None = None) -> Reranker:
    """Reranker cho tham số arm đã kiểm (`rerank_params`); model dùng chung trong tiến trình theo (model, max_length)."""
    key = (str(p["model"]), int(p["max_length"]))
    scorer = _SCORERS.get(key)
    if scorer is None:
        scorer = _SCORERS[key] = CrossEncoderScorer(key[0], max_length=key[1])
    return Reranker(key[0], batch_size=int(p["batch_size"]), max_length=key[1],
                    cache=RerankCache(cache_path or paths.cache_dir() / RERANK_CACHE), score_fn=scorer)
