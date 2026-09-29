"""cost.jsonl (spec §1.5): mỗi lượt gọi API trả phí / tính quota một dòng `ts, endpoint, model, input_type, n_texts,
n_tokens, usd`. Dùng chung mọi dataset (cache_dir). `sb cost` đọc lại để in tổng — kể cả số lượt gọi, vì key trial
Cohere giới hạn 1.000 lượt/tháng."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from . import paths


def append(*, endpoint: str, model: str, input_type: str | None, n_texts: int, n_tokens: int, usd: float,
           **extra: Any) -> None:
    row = {"ts": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"), "endpoint": endpoint,
           "model": model, "input_type": input_type, "n_texts": n_texts, "n_tokens": n_tokens, "usd": round(usd, 8), **extra}
    with open(paths.cache_dir() / paths.COST_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def read() -> list[dict]:
    p = paths.cache_dir(create=False) / paths.COST_LOG
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def summarize(rows: list[dict] | None = None) -> list[dict]:
    """Gộp theo (endpoint, model, input_type): calls, texts, tokens, usd."""
    acc: dict[tuple, dict] = defaultdict(lambda: {"calls": 0, "texts": 0, "tokens": 0, "usd": 0.0})
    for r in rows if rows is not None else read():
        a = acc[(r["endpoint"], r["model"], r.get("input_type"))]
        a["calls"] += 1
        a["texts"] += int(r.get("n_texts") or 0)
        a["tokens"] += int(r.get("n_tokens") or 0)
        a["usd"] += float(r.get("usd") or 0.0)
    return [{"endpoint": k[0], "model": k[1], "input_type": k[2], **v, "usd": round(v["usd"], 6)}
            for k, v in sorted(acc.items(), key=lambda kv: tuple(str(x) for x in kv[0]))]
