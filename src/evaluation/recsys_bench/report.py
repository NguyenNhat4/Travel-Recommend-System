"""Ghi kết quả một lượt chạy ra `bench_out/recsys/runs/<run_id>/` và dựng bảng markdown để dán vào spec / report.

Day 4 R6 (01/10): thêm ba cột handbook §12 (`Cross-cat chuyến mở`, `… có mua`, `Gini`), `footnote` (mẫu số của hai cột đó),
`header` in `git describe` của lượt chạy, `run_markdown` gộp mọi khối của một run (bảng + ceiling / phân khúc / so cặp) —
chỉ lệnh `report` ghi file `report.md`, `run` không ghi để file không cũ sau `analyze` / `compare`. `summary.json` có
`history[]` (mỗi lượt `run --run-id`: thời điểm, commit, tham số, arm) và `merge_run` **nối** `history` thay vì đè.
"""
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
    ("cross_category_open_trip", "Cross-cat chuyến mở", "{:.3f}"),
    ("cross_category_open_trip_bought", "Cross-cat chuyến mở, có mua", "{:.3f}"),
    ("exposure_gini", "Gini", "{:.3f}"),
    ("vertical_diversity@10", "Diversity@10", "{:.3f}"),
    ("returned_mean", "Trả về (TB)", "{:.1f}"),
    ("p95_runtime_ms", "p95 ms", "{:.1f}"),
    ("p99_runtime_ms", "p99 ms", "{:.1f}"),
    ("collab_coverage", "Collab cov.", "{:.3f}"),        # registry (R5): tỉ lệ item top-20 có vế co-occurrence > 0
    ("pool_truncated", "Pool cắt", "{:.2f}"),            # tỉ lệ khách có pool engine bị cắt ở pool_k (chỉ pool = engine)
    ("fit_seconds", "Fit s", "{:.1f}"),
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


def footnote(rows: list[dict]) -> str:
    """Mẫu số của hai cột cross-category theo chuyến mở (giống nhau ở mọi arm vì cùng split): số khách có chuyến mở tại as_of
    và số khách đã mua ≥ 1 món trong chuyến đó. Rỗng khi hàng chưa có khoá (run trước 01/10)."""
    row = next((r for r in rows if "users_open_trip" in r), None)
    if row is None:
        return ""
    return (f"Khách có chuyến mở tại as_of: {row['users_open_trip']:.0f} (trong đó đã mua ≥ 1 món trong chuyến: "
            f"{row.get('users_open_trip_bought', 0):.0f}) — mẫu số hai cột *Cross-cat chuyến mở*; chuyến chỉ có view thì mọi "
            f"item đều tính là cross. Gini và Coverage tính trên mọi unit recommendable.")


def header(summary: dict) -> str:
    """Dòng đầu report (B3): run, mốc, model, configHash, split đóng băng, commit — để hai bảng chỉ được so khi cùng các số này."""
    split = summary.get("split") or {}
    parts = [f"run {summary.get('runId')}", f"as_of {summary.get('asOf')}", f"model {summary.get('modelVersion')}",
             f"configHash {summary.get('configHash')}" + (f" / prod {summary['configHashProd']}" if summary.get("configHashProd") else ""),
             f"split {split.get('kind')} " + (f"frozen {split['frozenSha256'][:12]}" if split.get("frozenSha256") else "KHÔNG đóng băng")
             + (f" · SUBSET {summary.get('usersEvaluated')}/{split.get('usersTest')} khách" if summary.get("limitUsers") else ""),
             f"vectors {summary.get('vectors')}" + (f" (thiếu {summary['vectorsMissing']})" if summary.get("vectorsMissing") is not None else "")]
    if summary.get("gitDescribe"):
        parts.append(f"git {summary['gitDescribe']}")
    if summary.get("algosHash"):
        funnel = summary.get("funnel") or {}
        parts.append(f"algos {summary['algosHash']} mode {summary.get('algoMode')} pool {funnel.get('pool')} "
                     f"rerank {','.join(funnel.get('reranks') or [])}")
    return " · ".join(parts)


def fit_log_markdown(summary: dict) -> str:
    """Khối "Fit log" của run có `--algos` (spec recsys-algos-v1 §9): mỗi scorer/seed một dòng + thống kê ma trận + kết quả expect_equal_to."""
    logs = summary.get("fitLog") or {}
    if not logs:
        return ""
    skip = {"params", "rows", "nRows", "nnzB", "nnzU", "itemsWithNeighbour", "fitSeconds", "seed", "valuePercentiles", "note"}
    lines = [f"Fit log · algos `{summary.get('algosHash')}` · mode {summary.get('algoMode')} · funnel {json.dumps(summary.get('funnel'), ensure_ascii=False)} "
             f"· libs {json.dumps(summary.get('libs'), ensure_ascii=False)}", "",
             "| Algo | seed | rows | n hàng | nnz | item có láng giềng | tham số | khác | fit s |", "|---|---|---|---:|---:|---:|---|---|---:|"]
    for name, entries in logs.items():
        for log in entries:
            extra = {k: v for k, v in log.items() if k not in skip}
            cov = log.get("itemsWithNeighbour")
            lines.append(f"| {name} | {log.get('seed') if log.get('seed') is not None else ''} | {log.get('rows', '')} | {log.get('nRows', '')} | "
                         f"{log.get('nnzB', log.get('nnzU', ''))} | {f'{cov:.3f}' if isinstance(cov, (int, float)) else ''} | "
                         f"{json.dumps(log.get('params'), ensure_ascii=False)} | {json.dumps(extra, ensure_ascii=False)} | {log.get('fitSeconds', '')} |")
    stats = summary.get("matrixStats") or {}
    if stats:
        lines += ["", f"X_train: {stats.get('nEventsXTrain')} event · B {stats.get('nTrips')} trip × {len(summary.get('rows', [])) and ''}"
                  f"nnz {stats.get('nnzB')} · U {stats.get('nUsers')} user, nnz {stats.get('nnzU')} · ô theo event {json.dumps(stats.get('cellsByEvent'))} · "
                  f"bỏ orphan {stats.get('droppedOrphan')}, thiếu gid {stats.get('droppedNoGid')}, thiếu vector {stats.get('droppedNoVector')} · "
                  f"leak check {json.dumps(summary.get('leakCheck'))}"]
    expectations = summary.get("expectations") or {}
    if expectations:
        lines += ["", "expect_equal_to: " + "; ".join(
            f"`{arm}` vs `{e.get('ref')}` " + (e["skipped"] if e.get("skipped") else f"{e.get('equal')}/{e.get('n')} {'PASS' if e.get('pass') else 'FAIL'}")
            for arm, e in expectations.items())]
    if (summary.get("split") or {}).get("kind") == "llbo":
        lines += ["", "Caveat LLBO: ma trận item-item / MF fit **một lần toàn cục** trên X_train (khách test cắt < as_of riêng), nên chứa event của "
                  "khách khác xảy ra sau as_of của một khách; `pop_D` của engine thì cắt tại as_of — không rò rỉ target nhưng hai nguồn không đối "
                  "xứng về thời gian. Kết luận so scorer ưu tiên temporal (B10)."]
    return "\n".join(lines)


def run_markdown(summary: dict, extras: dict[str, str] | None = None) -> str:
    """Khối markdown đầy đủ của một run (lệnh `report`): header, split, bảng, strategy, footnote, rồi các khối thêm (ceiling /
    phân khúc / so cặp) đã có trong thư mục run. Chỉ trả chuỗi; không tính lại gì."""
    rows = summary.get("rows", [])
    split = summary.get("split") or {}
    frozen = split.get("frozenSha256")
    split_line = (f"Split `{split.get('kind')}` · {split.get('usersTest', '?')} khách test · event sha "
                  f"{str(split.get('eventsSha256') or '?')[:12]} · "
                  + (f"đóng băng `{split.get('splitFile')}` ({frozen[:12]})" if frozen else "KHÔNG đóng băng")
                  + (f" · T = {split['T']}" if split.get("T") else "")
                  + f" · k = {summary.get('k')} · {summary.get('searchUnits')} search unit / {summary.get('recommendable')} recommendable")
    lines = [f"### Run `{summary.get('runId')}`", "", header(summary), "", split_line, "", markdown_table(rows)]
    strategies = [f"- `{r['arm']}` strategy: {r['strategies']}" for r in rows if r.get("strategies")]
    if strategies:
        lines += ["", *strategies]
    note = footnote(rows)
    if note:
        lines += ["", note]
    if summary.get("openTripAssumesAllVectors"):
        lines += ["", "Chuyến mở tính với giả định mọi unit đều có vector (kho vector không khai metadata)."]
    fit_log = fit_log_markdown(summary)
    if fit_log:
        lines += ["", "#### Fit log", "", fit_log]
    for title, body in (extras or {}).items():
        lines += ["", f"#### {title}", "", body.strip()]
    return "\n".join(lines)


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
    `modelVersion` / `asOf` thì `RunConflict`. `history` nối thêm (provenance của mọi lượt), `gitDescribe` là của lượt mới."""
    for key in ("configHash", "modelVersion", "asOf", "k", "limitUsers"):
        if old.get(key) != summary.get(key):
            raise RunConflict(f"run đã có {key}={old.get(key)!r}, lần này {summary.get(key)!r} — dùng --run-id khác")
    if old.get("algosHash") and summary.get("algosHash") and old["algosHash"] != summary["algosHash"]:
        raise RunConflict(f"run đã có algosHash={old['algosHash']}, lần này {summary['algosHash']} (khác yaml / mode / funnel / lib) — dùng --run-id khác")
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
    if old.get("history") or summary.get("history"):
        merged["history"] = list(old.get("history") or []) + list(summary.get("history") or [])
    for key in ("fitLog", "expectations"):                 # run --algos gộp thêm algo: gộp theo tên, không đè
        if old.get(key) or summary.get(key):
            merged[key] = {**(old.get(key) or {}), **(summary.get(key) or {})}
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
