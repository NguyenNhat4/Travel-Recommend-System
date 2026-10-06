"""Day 5 (plan Day 4–5 §2.3, lịch 10 ngày Day 6) — chia gold thành `dev` / `test` cố định.

`dev` dùng để chỉnh tham số (S1/S2/S9/S10 của hợp đồng search §9), `test` chỉ để báo cáo cuối. Gold chỉ có 131 câu active
nên không chia 100/100 như plan; chia đôi **phân tầng theo slice** (quyết định người dùng 05/10).

`gold.jsonl` append-only và đã tag (spec §1.5) → không thêm trường `split` vào gold; phân chia nằm ở file riêng
`gold/splits/devtest@<gold_version>.json`, ghi kèm sha của gold để phát hiện gold đổi sau khi chia.

Thuật toán (tất định theo seed): duyệt slice theo tên; trong slice sắp qid rồi xáo bằng RNG riêng của slice
(`seed`, crc32 tên slice); câu thứ i vào dev nếu i chẵn, test nếu lẻ — riêng câu dư của slice lẻ vào bên đang ít câu hơn
(hoà → dev), để tổng hai bên lệch ≤ 1.
"""
from __future__ import annotations

import json
import zlib
from datetime import datetime
from pathlib import Path
from typing import Iterable

import numpy as np

from . import metrics as M, paths

SPLITS = ("dev", "test")
SPLITS_DIR = paths.GOLD_DIR / "splits"


class DevTestError(ValueError):
    pass


def split_path(gold_version: str, splits_dir: Path | None = None) -> Path:
    return (splits_dir or SPLITS_DIR) / f"devtest@{gold_version}.json"


def make_split(gold: Iterable[M.GoldQuery], *, seed: int) -> dict[str, str]:
    """{qid: "dev" | "test"} phân tầng theo slice."""
    by_slice: dict[str, list[str]] = {}
    for g in gold:
        by_slice.setdefault(g.slice, []).append(g.qid)
    out: dict[str, str] = {}
    n = {"dev": 0, "test": 0}
    for s in sorted(by_slice):
        qids = sorted(by_slice[s])
        rng = np.random.default_rng([seed, zlib.crc32(s.encode("utf-8"))])
        order = [qids[i] for i in rng.permutation(len(qids))]
        pairs = len(order) // 2 * 2
        for i, q in enumerate(order[:pairs]):
            out[q] = SPLITS[i % 2]
        for q in order[pairs:]:                       # câu dư của slice lẻ → bên ít hơn
            out[q] = "dev" if n["dev"] <= n["test"] else "test"
        for q in order:
            n[out[q]] += 1
    return out


def summary(gold: Iterable[M.GoldQuery], assignment: dict[str, str]) -> dict:
    by_slice: dict[str, dict[str, int]] = {}
    for g in gold:
        d = by_slice.setdefault(g.slice, {"dev": 0, "test": 0})
        d[assignment[g.qid]] += 1
    return {"n_dev": sum(v["dev"] for v in by_slice.values()), "n_test": sum(v["test"] for v in by_slice.values()),
            "by_slice": dict(sorted(by_slice.items()))}


def build_file(gold: list[M.GoldQuery], *, gold_version: str, gold_sha256: str, seed: int) -> dict:
    assignment = make_split(gold, seed=seed)
    return {"gold_version": gold_version, "gold_sha256": gold_sha256, "seed": seed,
            "method": "stratified-by-slice, alternate after per-slice shuffle (devtest.py)",
            "created_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
            **summary(gold, assignment), "assignment": dict(sorted(assignment.items()))}


def write(data: dict, *, splits_dir: Path | None = None, force: bool = False) -> Path:
    p = split_path(data["gold_version"], splits_dir)
    if p.exists() and not force:
        raise DevTestError(f"{p.name} đã có — phân chia là cố định; chỉ ghi đè bằng --force khi chủ động chia lại")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return p


def load(gold_version: str, *, splits_dir: Path | None = None) -> dict:
    p = split_path(gold_version, splits_dir)
    if not p.exists():
        raise DevTestError(f"chưa có {p} — chạy `sb gold devtest` trước")
    return json.loads(p.read_text(encoding="utf-8"))


def filter_rows(rows: list[dict], split: dict, which: str | None) -> list[dict]:
    """Giữ các dòng per_query thuộc `which` (dev | test); `which` None/"all" → giữ nguyên. Câu không có trong file
    phân chia (gold thêm câu sau khi chia) → lỗi, vì không được tự xếp vào bên nào."""
    if which in (None, "all"):
        return rows
    if which not in SPLITS:
        raise DevTestError(f"--split phải là dev | test | all, nhận {which!r}")
    a = split["assignment"]
    unknown = sorted({r["qid"] for r in rows} - set(a))
    if unknown:
        raise DevTestError(f"{len(unknown)} câu không có trong phân chia {split['gold_version']} (vd {unknown[:3]}) — "
                           "gold đã thêm câu: chia lại cho version mới")
    return [r for r in rows if a[r["qid"]] == which]
