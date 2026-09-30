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


def write_run(directory: Path, summary: dict, per_user: list[dict]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
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
