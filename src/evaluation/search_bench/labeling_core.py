"""Lõi app gán nhãn relevance 0/1/2 (docs/spec/bench/prompts/may2-label-app.md) — Python thuần, không import streamlit.

Một phiên = một người gán X ∈ {A, B}: chỉ mở `pool_X.csv` (theo `pool_meta.json`) và `labels/labels_X.csv`, không bao
giờ đọc file nhãn của người kia (25 câu chung phải gán độc lập). File nhãn là nguồn sự thật duy nhất: mỗi lượt lưu (nút
Lưu / chuyển câu — `apply_changes`) ghi bằng `gold_schema.upsert_label` (ghi file tạm rồi đổi tên); nhãn đã lưu không mất
khi tắt app giữa chừng.
Định dạng file và luật kiểm tra lấy hết từ `gold_schema.py` — không tự viết parser CSV.
"""
from __future__ import annotations

import os
import threading
import time
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


_FILE_LOCKS: dict[str, threading.RLock] = {}
_FILE_LOCKS_GUARD = threading.Lock()


def _file_lock(path: Path) -> threading.RLock:
    """Một lock cho mỗi file nhãn trong tiến trình. App dùng chung qua link chạy mỗi phiên / tab trong một thread riêng;
    lưu nhãn là đọc – sửa – ghi cả file, hai lần lưu chen nhau sẽ làm mất một nhãn nếu không nối tiếp nhau."""
    # abspath + normcase, KHÔNG dùng resolve(): trên Windows resolve() đổi chuỗi trả về sau khi thư mục labels/ được tạo
    # (lần ghi đầu) → cùng một file ra hai khoá khác nhau và hai lần lưu vẫn chen nhau.
    key = os.path.normcase(os.path.abspath(path))
    with _FILE_LOCKS_GUARD:
        return _FILE_LOCKS.setdefault(key, threading.RLock())      # RLock: clear_label giữ khoá rồi gọi load_labels


_RETRY_DELAYS = (0.05, 0.1, 0.2, 0.4)
NOTE_MAX = 1000     # ghi chú dài hơn ~131k ký tự làm csv đọc lại lỗi (giới hạn trường của module csv) → chặn sớm, rộng rãi


def _with_retry(write):
    """Windows có thể từ chối thoáng qua việc đổi tên file tạm đè lên file nhãn vừa ghi (Defender / indexer đang mở nó)
    → thử lại vài lần (≤ 0,75 giây). File đang mở trong Excel thì vẫn lỗi sau lần cuối và báo cho người gán."""
    for delay in _RETRY_DELAYS:
        try:
            return write()
        except PermissionError:
            time.sleep(delay)
    return write()


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
    # đọc cũng qua khoá + thử lại: trên Windows mở file đúng lúc thread khác đổi tên đè lên nó → PermissionError
    with _file_lock(s.labels_path):
        if not s.labels_path.exists():
            return {}
        try:
            rows = _with_retry(lambda: read_labels_csv(s.labels_path))
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


def make_label_row(s: LabelSession, qid: str, product_id: str, label, children_ok=(), note: str = "",
                   now: datetime | None = None) -> tuple[LabelRow | None, list[str]]:
    """Dựng + kiểm một LabelRow (luật của `gold_schema`), chưa ghi. Trả (dòng, lỗi) — có lỗi thì dòng là None."""
    row = s.by_key.get((qid, product_id))
    if row is None:
        return None, [f"{qid}/{product_id} không có trong pool_{s.labeler}"]
    try:
        label = int(label)
    except (TypeError, ValueError):
        return None, [f"nhãn phải là 0, 1 hoặc 2, gặp {label!r}"]
    if label not in (0, 1, 2):
        return None, [f"nhãn phải là 0, 1 hoặc 2, gặp {label!r}"]
    children = normalize_children(row, children_ok) if label == 2 else []
    if len((note or "").strip()) > NOTE_MAX:
        return None, [f"ghi chú dài quá {NOTE_MAX} ký tự — rút gọn lại"]
    try:
        lr = LabelRow(qid=qid, product_id=product_id, label=label, children_ok=children, note=(note or "").strip(),
                      labeler=s.labeler, labeled_at=(now or datetime.now()).astimezone(), pool_sha=s.pool_sha)
    except ValueError as e:
        return None, [str(e)]
    errors = validate_label_against_pool(lr, row)
    return (None, errors) if errors else (lr, [])


def save_label(s: LabelSession, qid: str, product_id: str, label: int, children_ok=(), note: str = "",
               now: datetime | None = None) -> list[str]:
    """Dựng LabelRow → `validate_label_against_pool` → `upsert_label`. Trả về danh sách lỗi (rỗng = đã lưu)."""
    lr, errors = make_label_row(s, qid, product_id, label, children_ok, note, now)
    if errors:
        return errors
    try:
        with _file_lock(s.labels_path):
            _with_retry(lambda: upsert_label(s.labels_path, lr))
    except PermissionError:
        return [f"không ghi được {s.labels_path.name} — file đang mở ở chương trình khác (Excel?); đóng rồi thử lại"]
    except SchemaError as e:
        return [str(e)]
    return []


def clear_label(s: LabelSession, qid: str, product_id: str) -> list[str]:
    """Bỏ nhãn một cặp (về trạng thái chưa gán)."""
    with _file_lock(s.labels_path):
        labels = load_labels(s)
        if (qid, product_id) not in labels:
            return []
        del labels[(qid, product_id)]
        try:
            _with_retry(lambda: write_labels_csv(labels.values(), s.labels_path))
        except PermissionError:
            return [f"không ghi được {s.labels_path.name} — file đang mở ở chương trình khác (Excel?)"]
    return []


MSG_NEED_CHILDREN = "nhãn 2 — tick hạng phòng đúng loại ở ô bên dưới rồi bấm Lưu"


def apply_changes(s: LabelSession, qid: str, changes: dict[str, dict]) -> tuple[list[str], list[str]]:
    """Lưu một lượt các thay đổi của một câu (nút Lưu / lúc rời câu). `changes`: product_id → {"label": "0"/"1"/"2" hoặc
    None/"" (bỏ nhãn), "note": str, "children": [id…] (chỉ khi người gán vừa tick lại hạng phòng)}.

    Trả (lỗi, product_id đã lưu). Dòng lỗi không làm hỏng dòng khác: dòng hợp lệ vẫn được ghi.
    """
    labels = load_labels(s)
    errors: list[str] = []
    saved: list[str] = []
    for pid, ch in changes.items():
        row = s.by_key.get((qid, pid))
        if row is None:
            errors.append(f"{qid}/{pid} không có trong pool_{s.labeler}")
            continue
        cur = labels.get((qid, pid))
        lab = ch.get("label")
        lab = lab if lab is None or isinstance(lab, str) else str(lab)
        note = ch.get("note", cur.note if cur else "") or ""
        note = note if isinstance(note, str) else str(note)
        if lab in (None, ""):
            if cur:
                errs = clear_label(s, qid, pid)
                errors += [f"{row.name}: {e}" for e in errs]
                if not errs:
                    saved.append(pid)
            elif note.strip():
                errors.append(f"{row.name}: chọn nhãn trước rồi mới ghi chú")
            continue
        if "children" in ch:
            children = list(ch["children"] or [])
        else:
            children = list(cur.children_ok) if cur and cur.label == 2 else []
        errs = save_label(s, qid, pid, lab, children, note)
        if errs and lab == "2" and row.children and not children:
            errors.append(f"{row.name}: {MSG_NEED_CHILDREN}")
        elif errs:
            errors += [f"{row.name}: {e}" for e in errs]
        else:
            saved.append(pid)
    return errors, saved


# ------------------------------------------------------------------ nguồn nhãn (máy / người) và duyệt
# File phụ `labels/provenance_<X>.csv` cạnh file nhãn — KHÔNG đổi hợp đồng file nhãn (gold_schema đóng băng), nên
# kappa / merge / import không đổi. Cặp không có dòng ở đây = người gán X tự gán trong app.
PROV_COLUMNS = ("qid", "product_id", "source", "machine_label", "machine_children", "machine_note", "model", "created_at",
                "reviewed_by", "reviewed_at", "review")
SOURCE_MACHINE, SOURCE_HUMAN = "machine", "human"
REVIEW_ACCEPTED, REVIEW_EDITED = "accepted", "edited"


def provenance_path(s: LabelSession) -> Path:
    return s.labels_path.with_name(f"provenance_{s.labeler}.csv")


def load_provenance(s: LabelSession) -> dict[tuple[str, str], dict]:
    import csv
    import io
    p = provenance_path(s)
    with _file_lock(p):
        if not p.exists():
            return {}
        text = _with_retry(lambda: p.read_text(encoding="utf-8-sig"))
    rows = list(csv.DictReader(io.StringIO(text)))
    if rows and set(rows[0]) != set(PROV_COLUMNS):
        raise SessionError(f"{p.name}: sai cột ({sorted(rows[0])})")
    return {(r["qid"], r["product_id"]): r for r in rows}


def _write_provenance(s: LabelSession, prov: dict[tuple[str, str], dict]) -> None:
    import csv
    import io

    from .gold_schema import atomic_write_text
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=PROV_COLUMNS, lineterminator="\n")
    w.writeheader()
    order = {r.key: i for i, r in enumerate(s.rows)}
    for key in sorted(prov, key=lambda k: order.get(k, len(order))):
        w.writerow({c: prov[key].get(c, "") for c in PROV_COLUMNS})
    _with_retry(lambda: atomic_write_text(provenance_path(s), buf.getvalue(), encoding="utf-8-sig"))


def update_provenance(s: LabelSession, updates: dict[tuple[str, str], dict]) -> None:
    """Gộp các trường mới vào dòng provenance (tạo dòng nếu chưa có) — dưới khoá của file provenance."""
    if not updates:
        return
    p = provenance_path(s)
    with _file_lock(p):
        prov = load_provenance(s)
        for key, fields in updates.items():
            row = prov.setdefault(key, {"qid": key[0], "product_id": key[1], "source": SOURCE_HUMAN})
            row.update({k: v for k, v in fields.items() if k in PROV_COLUMNS})
        _write_provenance(s, prov)


def import_machine_labels(s: LabelSession, rows: list[dict], *, model: str,
                          now: datetime | None = None) -> dict[str, list]:
    """Ghi nhãn máy vào file nhãn của X, CHỈ cho cặp còn trống; cặp đã có nhãn người giữ nguyên; câu chung (is_overlap,
    dùng tính κ giữa hai người) bị từ chối. Mỗi cặp ghi được có dòng provenance source=machine (nhãn / hạng phòng / lý do
    gốc của máy) để app lọc và duyệt. Trả {"written", "skipped_labeled", "rejected"} (danh sách key / lỗi)."""
    when = (now or datetime.now()).astimezone().isoformat(timespec="seconds")
    out: dict[str, list] = {"written": [], "skipped_labeled": [], "rejected": []}
    prov_updates: dict[tuple[str, str], dict] = {}
    new_rows: dict[tuple[str, str], LabelRow] = {}
    lock = _file_lock(s.labels_path)
    lock.acquire()                                       # đọc – thêm – ghi một lần cho cả lô, dưới khoá của file nhãn
    try:
        labels = load_labels(s)
        _collect_machine(s, rows, labels, now, out, new_rows, prov_updates, when, model)
        if new_rows:
            _with_retry(lambda: write_labels_csv([*labels.values(), *new_rows.values()], s.labels_path))
    finally:
        lock.release()
    update_provenance(s, prov_updates)
    return out


def _collect_machine(s: LabelSession, rows: list[dict], labels: dict, now, out: dict, new_rows: dict,
                     prov_updates: dict, when: str, model: str) -> None:
    for m in rows:
        key = (m.get("qid", ""), m.get("product_id", ""))
        row = s.by_key.get(key)
        if m.get("labeler") not in (None, s.labeler):
            continue                                                     # dòng của người kia
        if row is None:
            out["rejected"].append(f"{key}: không có trong pool_{s.labeler}")
            continue
        if row.is_overlap:
            out["rejected"].append(f"{key}: câu chung — dành cho người gán (κ)")
            continue
        if key in labels:
            out["skipped_labeled"].append(key)
            continue
        if key in new_rows:
            out["rejected"].append(f"{key}: trùng trong lô")
            continue
        children = list(m.get("children_ok") or [])
        lr, errs = make_label_row(s, key[0], key[1], m.get("label"), children, "", now=now)
        if errs:
            out["rejected"].append(f"{key}: {'; '.join(errs)}")
            continue
        new_rows[key] = lr
        out["written"].append(key)
        prov_updates[key] = {"source": SOURCE_MACHINE, "machine_label": str(m.get("label")),
                             "machine_children": ";".join(normalize_children(row, children)) if children else "",
                             "machine_note": (m.get("note") or "").strip()[:NOTE_MAX], "model": model,
                             "created_at": when, "reviewed_by": "", "reviewed_at": "", "review": ""}


def record_review(s: LabelSession, keys_accepted: list, keys_edited: list, keys_unticked: list, reviewer: str,
                  now: datetime | None = None) -> None:
    """Duyệt: tick = chấp nhận nhãn hiện có; sửa nhãn của cặp máy gán = đã duyệt kiểu sửa; bỏ tick = về chưa duyệt."""
    when = (now or datetime.now()).astimezone().isoformat(timespec="seconds")
    updates = {k: {"reviewed_by": reviewer, "reviewed_at": when, "review": REVIEW_ACCEPTED} for k in keys_accepted}
    updates.update({k: {"reviewed_by": reviewer, "reviewed_at": when, "review": REVIEW_EDITED} for k in keys_edited})
    updates.update({k: {"reviewed_by": "", "reviewed_at": "", "review": ""} for k in keys_unticked})
    update_provenance(s, updates)


def unreviewed_machine(s: LabelSession, qid: str, labels: dict, prov: dict) -> list[tuple[str, str]]:
    """Cặp của câu `qid` đang có nhãn máy chưa duyệt (theo thứ tự pool)."""
    return [r.key for r in s.by_qid.get(qid, []) if r.key in labels
            and (prov.get(r.key) or {}).get("source") == SOURCE_MACHINE and not (prov.get(r.key) or {}).get("review")]


def accept_all_machine(s: LabelSession, qid: str, reviewer: str, now: datetime | None = None) -> list[tuple[str, str]]:
    """Nút “Duyệt tất cả nhãn máy” của một câu: chấp nhận mọi nhãn máy chưa duyệt của câu đó (nhãn đã duyệt / đã sửa và
    nhãn người không đụng tới). Trả danh sách cặp vừa duyệt."""
    if not reviewer.strip():
        raise ValueError("cần tên người duyệt")
    keys = unreviewed_machine(s, qid, load_labels(s), load_provenance(s))
    record_review(s, keys, [], [], reviewer.strip(), now=now)
    return keys


def plan_save(qid: str, pending: dict[str, dict], labels: dict, prov: dict) -> dict:
    """Tách một lượt thay đổi chưa lưu của câu `qid` (bảng + ô duyệt + hạng phòng) thành việc cần làm:
    `label_changes` (cho `apply_changes`), `tick_on` / `tick_off` (tick / bỏ tick ô duyệt), `machine` (product_id có
    nhãn máy — sửa nhãn các cặp này = đã duyệt kiểu sửa), `needs_reviewer` (có việc duyệt → cần tên người duyệt)."""
    def base(pid: str) -> tuple:
        cur = labels.get((qid, pid))
        return (str(cur.label) if cur else None), (cur.note if cur else "")

    label_changes = {}
    for pid, d in pending.items():
        change = {k: v for k, v in d.items() if k != "tick"}
        if "children" in change or (change.get("label"), change.get("note") or "") != (base(pid)[0], base(pid)[1] or ""):
            label_changes[pid] = change
    machine = {pid for pid in pending if (prov.get((qid, pid)) or {}).get("source") == SOURCE_MACHINE}
    tick_on = [pid for pid, d in pending.items() if d.get("tick") is True]
    tick_off = [pid for pid, d in pending.items() if d.get("tick") is False]
    return {"label_changes": label_changes, "tick_on": tick_on, "tick_off": tick_off, "machine": machine,
            "needs_reviewer": bool(tick_on or tick_off or (machine & set(label_changes)))}


def source_of(prov_row: dict | None) -> str:
    """Nhãn hiển thị của nguồn một cặp."""
    if not prov_row or prov_row.get("source") != SOURCE_MACHINE:
        return "người" + (f" · duyệt: {prov_row['reviewed_by']}" if prov_row and prov_row.get("review") else "")
    if prov_row.get("review") == REVIEW_EDITED:
        return f"máy → sửa: {prov_row.get('reviewed_by', '')}"
    if prov_row.get("review") == REVIEW_ACCEPTED:
        return f"máy · duyệt: {prov_row.get('reviewed_by', '')}"
    return "máy · chưa duyệt"


def review_stats(s: LabelSession, labels: dict, prov: dict) -> dict:
    """Đếm theo nguồn: nhãn máy (chưa duyệt / đã duyệt / đã sửa), nhãn người."""
    st = {"machine": 0, "machine_unreviewed": 0, "machine_accepted": 0, "machine_edited": 0, "human": 0}
    for key in labels:
        p = prov.get(key)
        if p and p.get("source") == SOURCE_MACHINE:
            st["machine"] += 1
            st[{"": "machine_unreviewed", REVIEW_ACCEPTED: "machine_accepted",
                REVIEW_EDITED: "machine_edited"}.get(p.get("review", ""), "machine_unreviewed")] += 1
        else:
            st["human"] += 1
    return st


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
