"""Lõi app gán nhãn relevance 0/1/2 (docs/spec/bench/prompts/may2-label-app.md) — Python thuần, không import streamlit.

Một phiên = một người gán X ∈ {A, B}: chỉ mở `pool_X.csv` (theo `pool_meta.json`) và `labels/labels_X.csv`, không bao
giờ đọc file nhãn của người kia (25 câu chung phải gán độc lập). File nhãn là nguồn sự thật duy nhất: mỗi thay đổi ghi
ngay bằng `gold_schema.upsert_label` (ghi file tạm rồi đổi tên), tắt app giữa chừng không mất nhãn.
Định dạng file và luật kiểm tra lấy hết từ `gold_schema.py` — không tự viết parser CSV.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .gold_schema import (DISPLAY_COLUMNS, LABELERS, LabelRow, PoolRow, SchemaError, children_visible, file_sha256,
                          missing_pairs, read_labels_csv, read_pool_csv, read_pool_meta, upsert_label,
                          validate_label_against_pool, write_labels_csv)

HEADER_FIELDS = ("qid", "query", "slice", "filter_text", "expected_no_result")
CANDIDATE_FIELDS = tuple(c for c in DISPLAY_COLUMNS if c not in HEADER_FIELDS)   # name … children (không có giá)


class SessionError(ValueError):
    """Không mở được phiên gán: pool lệch sha, sai người gán, file hỏng…"""


@dataclass
class LabelSession:
    labeler: str
    meta_path: Path
    pool_path: Path
    labels_path: Path
    pool_sha: str
    rows: list[PoolRow]
    qids: list[str] = field(default_factory=list)                     # thứ tự câu trong file pool
    by_qid: dict[str, list[PoolRow]] = field(default_factory=dict)    # ứng viên theo đúng thứ tự trong file
    by_key: dict[tuple[str, str], PoolRow] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for r in self.rows:
            if r.qid not in self.by_qid:
                self.qids.append(r.qid)
            self.by_qid.setdefault(r.qid, []).append(r)
            self.by_key[r.key] = r


def default_paths(meta_path: Path, labeler: str) -> tuple[Path, Path]:
    """(pool_X.csv theo meta — đường dẫn tương đối tính từ thư mục meta, labels/labels_X.csv cạnh meta)."""
    meta = read_pool_meta(meta_path)
    p = Path(meta.files[labeler].path)
    return (p if p.is_absolute() else meta_path.parent / p), meta_path.parent / "labels" / f"labels_{labeler}.csv"


def open_session(meta_path: Path, labeler: str, *, pool_path: Path | None = None,
                 labels_path: Path | None = None) -> LabelSession:
    """Mở phiên của người gán X. Kiểm sha của pool **trước** khi đọc: pool bị sửa (hoặc git đổi xuống dòng) → chặn."""
    if labeler not in LABELERS:
        raise SessionError(f"người gán phải là A hoặc B, gặp {labeler!r}")
    if not meta_path.exists():
        raise SessionError(f"không thấy {meta_path} — chạy `gold pool` rồi `gold split` trước")
    try:
        meta = read_pool_meta(meta_path)
        pf = meta.files[labeler]
    except (ValueError, KeyError) as e:
        raise SessionError(f"{meta_path.name} không đọc được hoặc thiếu files.{labeler}: {e}") from None
    dpool, dlabels = default_paths(meta_path, labeler)
    pool_path = pool_path or dpool
    labels_path = labels_path or dlabels
    other = [x for x in LABELERS if x != labeler]
    if any(labels_path.name == f"labels_{o}.csv" for o in other):
        raise SessionError(f"{labels_path.name} là file của người gán khác — người {labeler} chỉ ghi labels_{labeler}.csv")
    if not pool_path.exists():
        raise SessionError(f"không thấy {pool_path}")
    sha = file_sha256(pool_path)
    if sha != pf.sha256:
        raise SessionError(f"{pool_path.name}: sha {sha[:12]}… khác pool_meta.json ({pf.sha256[:12]}…) — pool đã bị sửa, "
                           "mở nhầm file, hoặc git đổi ký tự xuống dòng khi pull (kiểm .gitattributes). Không gán trên "
                           "pool này.")
    try:
        rows = read_pool_csv(pool_path)
    except SchemaError as e:
        raise SessionError(str(e)) from None
    return LabelSession(labeler=labeler, meta_path=meta_path, pool_path=pool_path, labels_path=labels_path,
                        pool_sha=pf.sha256, rows=rows)


def load_labels(s: LabelSession) -> dict[tuple[str, str], LabelRow]:
    if not s.labels_path.exists():
        return {}
    try:
        rows = read_labels_csv(s.labels_path)
    except SchemaError as e:
        raise SessionError(str(e)) from None
    wrong = {r.labeler for r in rows} - {s.labeler}
    if wrong:
        raise SessionError(f"{s.labels_path.name} chứa nhãn của người gán {sorted(wrong)}, không phải {s.labeler}")
    return {r.key: r for r in rows}


# ------------------------------------------------------------------ tiến độ, vị trí tiếp tục
def question_done(s: LabelSession, labels: dict, qid: str) -> bool:
    return all(r.key in labels for r in s.by_qid[qid])


def progress(s: LabelSession, labels: dict) -> dict:
    missing = missing_pairs(s.rows, labels.values())
    mine = [labels[k] for k in s.by_key if k in labels]
    dist = Counter(r.label for r in mine)
    return {"done_q": sum(question_done(s, labels, q) for q in s.qids), "total_q": len(s.qids),
            "done_pairs": len(s.rows) - len(missing), "total_pairs": len(s.rows),
            "dist": {k: dist.get(k, 0) for k in (0, 1, 2)}}


def resume_qid(s: LabelSession, labels: dict) -> str | None:
    """Câu đầu tiên (theo thứ tự file) còn cặp chưa gán; None nếu đã xong hết."""
    missing = missing_pairs(s.rows, labels.values())
    return missing[0][0] if missing else None


def next_unfinished(s: LabelSession, labels: dict, after: str | None) -> str | None:
    """Câu chưa xong kế tiếp sau `after` (vòng lại từ đầu)."""
    start = s.qids.index(after) + 1 if after in s.qids else 0
    for q in s.qids[start:] + s.qids[:start]:
        if q != after and not question_done(s, labels, q):
            return q
    return None


# ------------------------------------------------------------------ ghi nhãn
def normalize_children(row: PoolRow, ids) -> list[str]:
    """Hạng phòng theo đúng thứ tự trong pool (id lạ giữ ở cuối để validate báo lỗi)."""
    chosen = list(dict.fromkeys(i for i in ids if i))
    known = [c.id for c in row.children if c.id in chosen]
    return known + [i for i in chosen if i not in known]


def save_label(s: LabelSession, qid: str, product_id: str, label: int, children_ok=(), note: str = "",
               now: datetime | None = None) -> list[str]:
    """Dựng LabelRow → `validate_label_against_pool` → `upsert_label`. Trả về danh sách lỗi (rỗng = đã lưu)."""
    row = s.by_key.get((qid, product_id))
    if row is None:
        return [f"{qid}/{product_id} không có trong pool_{s.labeler}"]
    try:
        label = int(label)
    except (TypeError, ValueError):
        return [f"nhãn phải là 0, 1 hoặc 2, gặp {label!r}"]
    if label not in (0, 1, 2):
        return [f"nhãn phải là 0, 1 hoặc 2, gặp {label!r}"]
    children = normalize_children(row, children_ok) if label == 2 else []
    try:
        lr = LabelRow(qid=qid, product_id=product_id, label=label, children_ok=children, note=(note or "").strip(),
                      labeler=s.labeler, labeled_at=(now or datetime.now()).astimezone(), pool_sha=s.pool_sha)
    except ValueError as e:
        return [str(e)]
    errors = validate_label_against_pool(lr, row)
    if errors:
        return errors
    try:
        upsert_label(s.labels_path, lr)
    except PermissionError:
        return [f"không ghi được {s.labels_path.name} — file đang mở ở chương trình khác (Excel?); đóng rồi thử lại"]
    except SchemaError as e:
        return [str(e)]
    return []


def clear_label(s: LabelSession, qid: str, product_id: str) -> list[str]:
    """Bỏ nhãn một cặp (về trạng thái chưa gán)."""
    labels = load_labels(s)
    if (qid, product_id) not in labels:
        return []
    del labels[(qid, product_id)]
    try:
        write_labels_csv(labels.values(), s.labels_path)
    except PermissionError:
        return [f"không ghi được {s.labels_path.name} — file đang mở ở chương trình khác (Excel?)"]
    return []


# ------------------------------------------------------------------ hiển thị
def header(s: LabelSession, qid: str) -> dict:
    r = s.by_qid[qid][0]
    return {"qid": qid, "query": r.query, "slice": r.slice, "filter_text": r.filter_text,
            "expected_no_result": r.expected_no_result, "children_visible": children_visible(r)}


def candidate_rows(s: LabelSession, qid: str, labels: dict) -> list[dict]:
    """Ứng viên của câu theo đúng thứ tự file, chỉ các cột được phép hiện (DISPLAY_COLUMNS; `children` chỉ ở
    parent_child) + nhãn / ghi chú / hạng phòng đã tick của người gán. Không có product_id, rank, nguồn, giá."""
    out = []
    for r in s.by_qid[qid]:
        lab = labels.get(r.key)
        d = {"nhãn": None if lab is None else str(lab.label), "ghi chú": lab.note if lab else ""}
        for c in CANDIDATE_FIELDS:
            if c == "children":
                if children_visible(r):
                    d["hạng phòng"] = "; ".join(ch.name for ch in r.children)
                    names = {ch.id: ch.name for ch in r.children}
                    d["hạng phòng đúng (đã tick)"] = "; ".join(names.get(i, i) for i in (lab.children_ok if lab else []))
                continue
            v = getattr(r, c)
            d[c] = ", ".join(v) if isinstance(v, list) else v
        out.append(d)
    return out
