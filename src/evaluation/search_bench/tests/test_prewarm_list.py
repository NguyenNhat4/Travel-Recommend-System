"""Danh sách prewarm của backend (`src/backend/data/search_prewarm_queries.txt`, đóng băng theo tag gold_v*) phải khớp
gold active hiện tại: evaluation được phụ thuộc backend, không ngược lại, nên phép đối chiếu nằm ở đây. File chưa có
trên nhánh này (PR cache chưa gộp) → skip, không fail."""
from __future__ import annotations

import hashlib
import re
import subprocess

import pytest

from evaluation.search_bench import paths
from evaluation.search_bench.gold_schema import read_gold_jsonl
from evaluation.search_bench.latency import canonical

PREWARM = paths.repo_root() / "src" / "backend" / "data" / "search_prewarm_queries.txt"


def _tag_blob_sha(tag: str) -> str | None:
    try:
        r = subprocess.run(["git", "show", f"{tag}:src/evaluation/search_bench/gold/gold.jsonl"], cwd=paths.repo_root(),
                           capture_output=True, timeout=10)
    except Exception:  # noqa: BLE001
        return None
    return hashlib.sha256(r.stdout).hexdigest() if r.returncode == 0 else None


def test_prewarm_list_matches_gold_active_of_its_tag():
    if not PREWARM.exists():
        pytest.skip(f"chưa có {PREWARM} trên nhánh này (PR cache/prewarm chưa gộp)")
    lines = PREWARM.read_text(encoding="utf-8").splitlines()
    m = re.match(r"^# (gold_v\d+) ([0-9a-f]{64}) ", lines[0])
    assert m, "dòng đầu phải là `# gold_vN <sha256> <ngày>`"
    tag, sha = m.group(1), m.group(2)
    queries = [canonical(x) for x in lines if x.strip() and not x.lstrip().startswith("#")]
    tag_sha = _tag_blob_sha(tag)
    if tag_sha is not None:
        assert tag_sha == sha, f"sha trong header khác blob gold.jsonl ở tag {tag}"
    gold = {canonical(r.text) for r in read_gold_jsonl(paths.GOLD_JSONL) if r.status == "active"}
    assert len(queries) == len(set(queries)) and set(queries) == gold, \
        f"prewarm ≠ gold active: thiếu {sorted(gold - set(queries))[:3]} · thừa {sorted(set(queries) - gold)[:3]} — sinh lại file khi gold đổi tag"
