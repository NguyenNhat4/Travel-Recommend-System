"""Ghi kết quả một lượt chạy ra `bench_out/recsys/runs/<run_id>/` và dựng bảng markdown để dán vào spec."""
from __future__ import annotations

import csv
import json
from pathlib import Path

COLUMNS = [
    ("users", "Khách", "{:.0f}"),
    ("recall@5", "Recall@5", "{:.4f}"),
    ("ndcg@5", "NDCG@5", "{:.4f}"),
    ("recall@10", "Recall@10", "{:.4f}"),
    ("recall@20", "Recall@20", "{:.4f}"),
    ("ndcg@10", "NDCG@10", "{:.4f}"),
    ("catalog_coverage", "Coverage", "{:.3f}"),
    ("availability_precision", "Availability", "{:.3f}"),
    ("cross_category_rate", "Cross-category", "{:.3f}"),
    ("vertical_diversity@10", "Diversity@10", "{:.3f}"),
    ("returned_mean", "Trả về (TB)", "{:.1f}"),
    ("p95_runtime_ms", "p95 ms", "{:.1f}"),
    ("p99_runtime_ms", "p99 ms", "{:.1f}"),
]


def _cell(row: dict, key: str, fmt: str) -> str:
    if key not in row:
        return "—"
    text = fmt.format(row[key])
    std = row.get(f"{key}_std")
    return f"{text} ± {fmt.format(std)}" if std else text


def markdown_table(rows: list[dict]) -> str:
    head = "| Arm | " + " | ".join(label for _, label, _ in COLUMNS) + " |"
    sep = "|---|" + "---|" * len(COLUMNS)
    body = []
    for row in rows:
        name = row["arm"] + (f" ({row['seeds']} seed)" if row.get("seeds") else "")
        body.append(f"| {name} | " + " | ".join(_cell(row, key, fmt) for key, _, fmt in COLUMNS) + " |")
    return "\n".join([head, sep, *body])


def header(summary: dict) -> str:
    """Dòng đầu report (B3): run, mốc, model, configHash, split đóng băng — để hai bảng chỉ được so khi cùng các số này."""
    split = summary.get("split") or {}
    parts = [f"run {summary.get('runId')}", f"as_of {summary.get('asOf')}", f"model {summary.get('modelVersion')}",
             f"configHash {summary.get('configHash')}" + (f" / prod {summary['configHashProd']}" if summary.get("configHashProd") else ""),
             f"split {split.get('kind')} " + (f"frozen {split['frozenSha256'][:12]}" if split.get("frozenSha256") else "KHÔNG đóng băng")
             + (f" · SUBSET {summary.get('usersEvaluated')}/{split.get('usersTest')} khách" if summary.get("limitUsers") else ""),
             f"vectors {summary.get('vectors')}" + (f" (thiếu {summary['vectorsMissing']})" if summary.get("vectorsMissing") is not None else "")]
    return " · ".join(parts)


class RunConflict(ValueError):
    """Run đã có nhưng cấu hình / split khác — không gộp arm mới vào."""


def read_run(directory: Path) -> tuple[dict | None, list[dict]]:
    """(summary.json, per_user.jsonl) của một run đã ghi; (None, []) khi chưa có."""
    p = directory / "summary.json"
    if not p.exists():
        return None, []
    summary = json.loads(p.read_text(encoding="utf-8"))
    q = directory / "per_user.jsonl"
    rows = [json.loads(line) for line in q.read_text(encoding="utf-8").splitlines() if line.strip()] if q.exists() else []
    return summary, rows


def merge_run(old: dict, old_rows: list[dict], summary: dict, per_user: list[dict]) -> tuple[dict, list[dict]]:
    """Gộp arm mới vào run cũ (`run --run-id` chạy thêm arm): arm trùng tên thì thay; khác `configHash` / `frozenSha256` /
    `modelVersion` / `asOf` thì `RunConflict`."""
    for key in ("configHash", "modelVersion", "asOf", "k", "limitUsers"):
        if old.get(key) != summary.get(key):
            raise RunConflict(f"run đã có {key}={old.get(key)!r}, lần này {summary.get(key)!r} — dùng --run-id khác")
    old_split, new_split = old.get("split") or {}, summary.get("split") or {}
    for key in ("kind", "eventsSha256", "usersTest", "minPurchases", "minTrips", "T"):
        if old_split.get(key) != new_split.get(key):
            raise RunConflict(f"run đã có split.{key}={old_split.get(key)!r}, lần này {new_split.get(key)!r} — dùng --run-id khác")
    a, b = old_split.get("frozenSha256"), new_split.get("frozenSha256")
    if a and not b:
        raise RunConflict(f"run đã đóng băng split {a[:12]} — chạy thêm arm phải kèm --split-file")
    if a and b and a != b:
        raise RunConflict(f"run đã có split đóng băng {a[:12]}, lần này {b[:12]} — dùng --run-id khác")
    old_vec, new_vec = old.get("vectors"), summary.get("vectors")
    if old_vec not in (None, "none") and new_vec not in (None, "none") and old_vec != new_vec:
        raise RunConflict(f"run đã có vectors={old_vec!r}, lần này {new_vec!r} — dùng --run-id khác")
    new_arms = {r["arm"] for r in summary.get("rows", [])} | {r["arm"] for r in summary.get("rawRows", [])}
    new_keys = {r["arm"] for r in per_user}
    merged = {**old, **summary,
              "rows": [r for r in old.get("rows", []) if r["arm"] not in new_arms] + summary.get("rows", []),
              "rawRows": [r for r in old.get("rawRows", []) if r["arm"] not in new_arms] + summary.get("rawRows", [])}
    if new_vec in (None, "none") and old_vec not in (None, "none"):    # arm không cần vector không được hạ cấp run engine
        merged["vectors"], merged["vectorsMissing"] = old_vec, old.get("vectorsMissing")
    if not b and a:
        merged["split"] = {**new_split, "frozenSha256": a, "splitFile": old_split.get("splitFile")}
    return merged, [r for r in old_rows if r["arm"] not in new_keys] + per_user


def write_run(directory: Path, summary: dict, per_user: list[dict], *, merge: bool = False) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    if merge:
        old, old_rows = read_run(directory)
        if old is not None:
            summary, per_user = merge_run(old, old_rows, summary, per_user)
    (directory / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str),
                                            encoding="utf-8")
    if per_user:
        with open(directory / "per_user.jsonl", "w", encoding="utf-8") as f:   # giữ `ids` nguyên dạng (B7)
            for row in per_user:
                f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        fields = sorted({key for row in per_user for key in row})
        with open(directory / "per_user.csv", "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for row in per_user:
                writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
                                 for k, v in row.items()})
    return directory
