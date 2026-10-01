"""Part 11 — gold append-only: version theo tag git, `retire`, `verify-append`, `gold/changelog.yaml`, `holes`.

Gold chỉ được **thêm** (spec Part 11): thêm câu, thêm nhãn cho cặp chưa có nhãn, hoặc chuyển câu `active → retired`. Mỗi
lần đổi ghi một mục vào `gold/changelog.yaml` (`version, at, action, …`) và ứng với một tag git `gold_vN`.

Phiên bản của `gold.jsonl` xác định bằng git: file hiện tại khớp blob của tag `gold_vN:<đường dẫn>` thì version là
`gold_vN`; không khớp tag nào → chưa có version (`sb run` từ chối, spec §1.5). `retire` trước khi tag `gold_v1` được phép
khi pool bỏ sót sản phẩm đúng (`pool_miss`, chốt 30/09): câu bị loại khỏi metric ngay từ v1, nhãn đã gán giữ nguyên.

Holes: cặp (qid, product) lọt top-k của một arm mà chưa có nhãn → thư mục `gold/holes/<gold_version>__<tag>/` gồm
`pool_A.csv` [+ `pool_B.csv` khi `--split`], `pool_meta.json` (app gán nhãn mở như pool thường), `meta.csv` (arm / hạng /
số arm — nội bộ, người gán không xem), `auto_ooc.csv` (hole của câu out_of_catalog → tự gán 0), `holes.json`. Nhãn app
ghi vào `<thư mục>/labels/labels_X.csv`; `holes import` thêm vào gold với provenance `holes:<tag>@<version>`.
"""
from __future__ import annotations

import csv
import json
import random
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

from . import paths
from .gold import GoldError, PoolView, RuleViolation, _amenity_ids_in, pick_amenities, render_filter_text
from .gold_schema import (CSV_WRITE_ENCODING, GoldRecord, PoolFile, PoolMeta, PoolRow, atomic_write_text, file_sha256,
                          read_gold_jsonl, read_labels_csv, read_pool_csv, read_pool_meta, validate_label_against_pool,
                          write_gold_jsonl, write_pool_csv, write_pool_meta)
from .store import filters as F

TAG_RE = re.compile(r"^gold_v(\d+)$")
HOLES_JSON = "holes.json"
HOLES_META_CSV = "meta.csv"
AUTO_OOC_CSV = "auto_ooc.csv"


# ------------------------------------------------------------------ version theo tag git
def _git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=paths.repo_root(), capture_output=True, text=True, timeout=15)
    if r.returncode:
        raise GoldError(f"git {' '.join(args)}: {r.stderr.strip()[:200]}")
    return r.stdout.strip()


def version_number(tag: str) -> int:
    m = TAG_RE.match(tag)
    if not m:
        raise GoldError(f"tag không đúng dạng gold_vN: {tag!r}")
    return int(m.group(1))


def list_gold_tags() -> list[str]:
    """Tag `gold_v*` trong repo, tăng dần theo số (gold_v2 trước gold_v10)."""
    tags = [t for t in _git("tag", "-l", "gold_v*").split() if TAG_RE.match(t)]
    return sorted(tags, key=version_number)


def next_version(tags: list[str]) -> str:
    return f"gold_v{version_number(tags[-1]) + 1}" if tags else "gold_v1"


def repo_relpath(path: Path) -> str:
    return path.resolve().relative_to(paths.repo_root().resolve()).as_posix()


def gold_version_of(path: Path, tags: list[str] | None = None) -> str | None:
    """Tag `gold_vN` (mới nhất) mà blob `<tag>:<path>` trùng file hiện tại; None nếu chưa khớp tag nào."""
    if not path.exists():
        raise GoldError(f"không thấy {path}")
    tags = list_gold_tags() if tags is None else tags
    if not tags:
        return None
    blob = _git("hash-object", "--", str(path))
    rel = repo_relpath(path)
    for tag in reversed(tags):
        r = subprocess.run(["git", "rev-parse", "--verify", "-q", f"{tag}:{rel}"], cwd=paths.repo_root(),
                           capture_output=True, text=True, timeout=15)
        if r.returncode == 0 and r.stdout.strip() == blob:
            return tag
    return None


def gold_at(ref: str, path: Path | None = None) -> list[GoldRecord]:
    """gold.jsonl tại một tham chiếu: đường dẫn file đang có, hoặc `git show <ref>:<gold.jsonl>` (tag / commit)."""
    p = Path(ref)
    if p.exists():
        return read_gold_jsonl(p)
    rel = repo_relpath(path or paths.GOLD_JSONL)
    r = subprocess.run(["git", "show", f"{ref}:{rel}"], cwd=paths.repo_root(), capture_output=True, timeout=15)
    if r.returncode:
        raise GoldError(f"không đọc được {ref}:{rel} — {r.stderr.decode('utf-8', 'replace').strip()[:200]}")
    out: list[GoldRecord] = []
    for n, line in enumerate(r.stdout.decode("utf-8").splitlines(), 1):
        if line.strip():
            try:
                out.append(GoldRecord.model_validate_json(line))
            except ValueError as e:
                raise GoldError(f"{ref}:{rel} dòng {n}: {e}") from None
    return out


# ------------------------------------------------------------------ changelog
def read_changelog(path: Path | None = None) -> list[dict]:
    p = path or paths.GOLD_CHANGELOG
    if not p.exists():
        return []
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    if not isinstance(data, list):
        raise GoldError(f"{p}: phải là một danh sách YAML")
    return data


def append_changelog(entry: dict, path: Path | None = None) -> list[dict]:
    p = path or paths.GOLD_CHANGELOG
    entries = read_changelog(p) + [entry]
    atomic_write_text(p, yaml.safe_dump(entries, allow_unicode=True, sort_keys=False, width=120))
    return entries


def changelog_entry(version: str, action: str, records: list[GoldRecord], **extra) -> dict:
    active = [r for r in records if r.status == "active"]
    return {"version": version, "at": datetime.now().astimezone().replace(microsecond=0).isoformat(), "action": action,
            "n_queries_active": len(active), "n_queries_retired": len(records) - len(active),
            "n_labels": sum(len(r.judgments) for r in records), **extra}


# ------------------------------------------------------------------ retire
def retire(records: list[GoldRecord], qid: str) -> list[GoldRecord]:
    """`status: active → retired` cho một câu; câu không có hoặc đã retired → RuleViolation. Nhãn giữ nguyên."""
    by = {r.qid: r for r in records}
    if qid not in by:
        raise RuleViolation("retire", [f"{qid}: không có trong gold"])
    if by[qid].status == "retired":
        raise RuleViolation("retire", [f"{qid}: đã retired"])
    return [r.model_copy(update={"status": "retired"}) if r.qid == qid else r for r in records]


def write_gold(records: list[GoldRecord], path: Path | None = None) -> None:
    write_gold_jsonl(records, path or paths.GOLD_JSONL)


# ------------------------------------------------------------------ verify-append
def verify_append(old: list[GoldRecord], new: list[GoldRecord]) -> list[str]:
    """Bản mới chỉ được thêm so với bản cũ: mọi qid cũ còn; câu cũ giữ nguyên text / slice / filter / expected_no_result;
    mọi nhãn cũ giữ nguyên giá trị và provenance; expected_children cũ còn nguyên; status chỉ đổi active → retired."""
    problems: list[str] = []
    by_new = {r.qid: r for r in new}
    dup = [q for q in {r.qid for r in new} if sum(1 for r in new if r.qid == q) > 1]
    problems += [f"{q}: qid trùng trong bản mới" for q in sorted(dup)]
    for o in old:
        n = by_new.get(o.qid)
        if n is None:
            problems.append(f"{o.qid}: có trong bản cũ nhưng mất ở bản mới")
            continue
        for f in ("text", "slice", "filter", "child_filter", "expected_no_result"):
            if getattr(o, f) != getattr(n, f):
                problems.append(f"{o.qid}: {f} bị đổi")
        for pid, lab in o.judgments.items():
            if pid not in n.judgments:
                problems.append(f"{o.qid}/{pid}: nhãn cũ bị xoá")
            elif n.judgments[pid] != lab:
                problems.append(f"{o.qid}/{pid}: nhãn đổi {lab} → {n.judgments[pid]}")
            elif n.provenance.get(pid) != o.provenance.get(pid):
                problems.append(f"{o.qid}/{pid}: provenance đổi {o.provenance.get(pid)!r} → {n.provenance.get(pid)!r}")
        for pid, kids in o.expected_children.items():
            if sorted(n.expected_children.get(pid, [])) != sorted(kids):
                problems.append(f"{o.qid}/{pid}: expected_children bị đổi")
        if o.status == "retired" and n.status != "retired":
            problems.append(f"{o.qid}: retired → active không được phép")
    return problems


# ================================================================== holes — cặp chưa nhãn lọt top-k
@dataclass
class Hole:
    qid: str
    product_id: str
    arms: list[str] = field(default_factory=list)
    best_rank: int = 0


def find_holes(records: list[GoldRecord], rows_by_arm: dict[str, list[dict]], k: int) -> tuple[list[Hole], list[Hole]]:
    """(hole cần người gán, hole của câu out_of_catalog → tự gán 0). Chỉ xét câu active; câu không có trong gold bị bỏ qua.
    Sắp: câu có nhiều arm kéo lên trước (gán cái ảnh hưởng nhiều nhất trước), rồi qid, rồi product_id."""
    judged = {r.qid: set(r.judgments) for r in records if r.status == "active"}
    ooc = {r.qid for r in records if r.status == "active" and r.expected_no_result}
    acc: dict[tuple[str, str], Hole] = {}
    for arm in sorted(rows_by_arm):
        for row in rows_by_arm[arm]:
            qid = row["qid"]
            if qid not in judged:
                continue
            for rank, pid in enumerate(list(row["top_ids"] or [])[:k], 1):
                if pid in judged[qid]:
                    continue
                h = acc.setdefault((qid, pid), Hole(qid, pid, [], rank))
                if arm not in h.arms:
                    h.arms.append(arm)
                h.best_rank = min(h.best_rank, rank)
    n_arms_q: dict[str, int] = {}
    for h in acc.values():
        n_arms_q[h.qid] = max(n_arms_q.get(h.qid, 0), len(h.arms))
    ordered = sorted(acc.values(), key=lambda h: (-n_arms_q[h.qid], h.qid, h.product_id))
    return [h for h in ordered if h.qid not in ooc], [h for h in ordered if h.qid in ooc]


def cap_holes(holes: list[Hole], records: list[GoldRecord], cap: int, *, seed: int) -> list[Hole]:
    """Giới hạn pool theo round-robin qua query, giữ coverage thay vì lấy các qid đầu.

    Trong mỗi query ưu tiên cặp được nhiều arm cùng kéo lên, rồi hạng tốt hơn. Thứ tự query được xáo
    xác định trong từng slice và round-robin giữa các slice, để cap không thiên về slice/qid đứng đầu file.
    """
    if cap < 1:
        raise ValueError("cap phải >= 1")
    if len(holes) <= cap:
        return list(holes)
    slice_by_qid = {r.qid: r.slice for r in records if r.status == "active"}
    by_qid: dict[str, list[Hole]] = {}
    for h in holes:
        by_qid.setdefault(h.qid, []).append(h)
    for qid in by_qid:
        by_qid[qid].sort(key=lambda h: (-len(h.arms), h.best_rank, h.product_id))
    by_slice: dict[str, list[str]] = {}
    for qid in by_qid:
        by_slice.setdefault(slice_by_qid.get(qid, ""), []).append(qid)
    rng = random.Random(seed)
    for qids in by_slice.values():
        qids.sort()
        rng.shuffle(qids)
    selected: list[Hole] = []
    level = 0
    while len(selected) < cap:
        added = False
        for slice_name in sorted(by_slice):
            for qid in by_slice[slice_name]:
                if level < len(by_qid[qid]):
                    selected.append(by_qid[qid][level])
                    added = True
                    if len(selected) == cap:
                        return selected
        if not added:
            break
        level += 1
    return selected


def hole_rows(holes: list[Hole], records: list[GoldRecord], view: PoolView) -> list[PoolRow]:
    """Dòng POOL_COLUMNS cho từng hole (app gán nhãn mở như pool thường). `from` / `rank_dense` = hạng tốt nhất, không ghi
    arm nào kéo lên (người gán không thiên vị; hai cột này app vẫn ẩn)."""
    by_q = {r.qid: r for r in records}
    labels = view.labels_by_key()
    out: list[PoolRow] = []
    for h in holes:
        rec = by_q[h.qid]
        it = view.items.get(h.product_id)
        if it is None:
            raise GoldError(f"{h.qid}/{h.product_id}: có trong kết quả arm nhưng không có trong items.parquet — catalog lệch")
        resolved = F.resolve(rec.filter, view.key_to_id) if rec.filter else None
        out.append(PoolRow(
            qid=h.qid, query=rec.text, slice=rec.slice, filter_text=render_filter_text(rec.filter, rec.child_filter, labels),
            filter_json=rec.filter, child_filter_json=rec.child_filter, expected_no_result=rec.expected_no_result,
            product_id=h.product_id, name=it["name"], taxonomy=it["variant"], destination=it["destination"] or "",
            star_rating=it["star_rating"],
            amenities=pick_amenities(it["amenity_ids"], view, must=_amenity_ids_in(resolved), query=rec.text),
            snippet=view.snippets.get(h.product_id, ""), children=view.children.get(h.product_id, []),
            source="dense", rank_dense=h.best_rank, rank_lex=None, is_overlap=False))
    return out


def write_holes(to_label: list[Hole], auto_ooc: list[Hole], records: list[GoldRecord], view: PoolView, out_dir: Path, *,
                seed: int, split: bool, snapshot: str, collection: str, k: int, run_id: str, arms: list[str],
                gold_version: str | None, tag: str) -> dict:
    """Ghi thư mục hole: pool_A.csv [+ pool_B.csv khi split — chia câu xen kẽ, không câu chung], pool_meta.json (app gán
    nhãn mở được), meta.csv (arm / hạng / số arm, nội bộ), auto_ooc.csv, holes.json. Ứng viên xáo trong từng câu."""
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = hole_rows(to_label, records, view)
    qids: list[str] = []
    for r in rows:
        if r.qid not in qids:
            qids.append(r.qid)
    by_q: dict[str, list[PoolRow]] = {q: [] for q in qids}
    for r in rows:
        by_q[r.qid].append(r)
    for q in qids:
        random.Random(f"{seed}|{q}").shuffle(by_q[q])
    assign = {q: ("B" if (split and i % 2 == 1) else "A") for i, q in enumerate(qids)}
    files: dict[str, PoolFile] = {}
    for x in (("A", "B") if split else ("A",)):
        mine = [r for q in qids if assign[q] == x for r in by_q[q]]
        p = out_dir / f"pool_{x}.csv"
        write_pool_csv(mine, p)
        files[x] = PoolFile(path=p.name, sha256=file_sha256(p), labeler=x, n_queries=len({r.qid for r in mine}),
                            n_pairs=len(mine))
    meta = PoolMeta(snapshot=snapshot, collection=collection, depth=k, seed=seed, drafts_sha256=None, overlap_qids=[],
                    files=files, created_at=datetime.now().astimezone().replace(microsecond=0))
    write_pool_meta(meta, out_dir / "pool_meta.json")
    with open(out_dir / HOLES_META_CSV, "w", encoding=CSV_WRITE_ENCODING, newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["qid", "product_id", "arms", "best_rank", "n_arms", "labeler"])
        for h in to_label:
            w.writerow([h.qid, h.product_id, ";".join(h.arms), h.best_rank, len(h.arms), assign[h.qid]])
    with open(out_dir / AUTO_OOC_CSV, "w", encoding=CSV_WRITE_ENCODING, newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["qid", "product_id", "arms", "best_rank"])
        for h in auto_ooc:
            w.writerow([h.qid, h.product_id, ";".join(h.arms), h.best_rank])
    summary = {"run_id": run_id, "arms": arms, "k": k, "gold_version": gold_version, "tag": tag, "snapshot": snapshot,
               "n_to_label": len(to_label), "n_auto_ooc": len(auto_ooc), "n_queries": len(qids),
               "files": {x: {"n_queries": f.n_queries, "n_pairs": f.n_pairs} for x, f in files.items()},
               "created_at": meta.created_at.isoformat()}
    atomic_write_text(out_dir / HOLES_JSON, json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    return summary


def read_holes_summary(holes_dir: Path) -> dict:
    p = holes_dir / HOLES_JSON
    if not p.exists():
        raise GoldError(f"không thấy {p} — thư mục hole phải do `sb gold holes` tạo")
    return json.loads(p.read_text(encoding="utf-8"))


def _read_auto_ooc(holes_dir: Path) -> list[tuple[str, str]]:
    p = holes_dir / AUTO_OOC_CSV
    if not p.exists():
        return []
    with open(p, encoding="utf-8-sig", newline="") as fh:
        return [(r["qid"], r["product_id"]) for r in csv.DictReader(fh)]


def import_holes(records: list[GoldRecord], holes_dir: Path, *, version: str, tag: str,
                 partial: bool = False) -> tuple[list[GoldRecord], dict]:
    """Nhãn người gán (labels/labels_X.csv của thư mục hole) + hole out_of_catalog tự gán 0 → thêm vào gold. Từ chối cặp
    đã có nhãn, nhãn sai luật với dòng pool, nhãn gắn pool khác sha; thiếu nhãn → từ chối trừ `partial`."""
    meta = read_pool_meta(holes_dir / "pool_meta.json")
    by_q = {r.qid: r for r in records}
    problems: list[str] = []
    adds: dict[tuple[str, str], tuple[int, list[str], str]] = {}         # (qid, pid) → (label, children_ok, provenance)
    for x, pf in meta.files.items():
        pool_p = holes_dir / pf.path
        if file_sha256(pool_p) != pf.sha256:
            raise GoldError(f"{pool_p.name}: sha khác pool_meta.json — file hole đã bị sửa")
        pool = {r.key: r for r in read_pool_csv(pool_p)}
        lp = holes_dir / "labels" / f"labels_{x}.csv"
        labels = {r.key: r for r in read_labels_csv(lp)} if lp.exists() else {}
        for key, lab in sorted(labels.items()):
            if key not in pool:
                problems.append(f"labels_{x}: {key[0]}/{key[1]} không có trong {pool_p.name}")
                continue
            if lab.labeler != x:
                problems.append(f"labels_{x}: {key[0]}/{key[1]} do người gán {lab.labeler}")
            if lab.pool_sha != pf.sha256:
                problems.append(f"labels_{x}: {key[0]}/{key[1]} gắn với pool khác (sha {lab.pool_sha[:12]}…)")
            problems += [f"labels_{x} {key[0]}/{key[1]}: {e}" for e in validate_label_against_pool(lab, pool[key])]
            adds[key] = (lab.label, list(lab.children_ok), f"holes:{tag}@{version}")
        missing = sorted(set(pool) - set(labels))
        if missing and not partial:
            problems += [f"{q}/{p}: chưa gán (labels_{x})" for q, p in missing[:30]]
            if len(missing) > 30:
                problems.append(f"… và {len(missing) - 30} cặp chưa gán nữa")
    n_auto = 0
    for q, p in _read_auto_ooc(holes_dir):
        if q in by_q and p not in by_q[q].judgments and (q, p) not in adds:
            adds[(q, p)] = (0, [], f"auto_ooc:{tag}@{version}")
            n_auto += 1
    for (q, p), (lab, _, _) in sorted(adds.items()):
        if q not in by_q:
            problems.append(f"{q}: không có trong gold")
        elif p in by_q[q].judgments:
            problems.append(f"{q}/{p}: đã có nhãn {by_q[q].judgments[p]} — gold chỉ thêm, không sửa")
    if problems:
        raise RuleViolation("holes import", problems)
    out: list[GoldRecord] = []
    touched: set[str] = set()
    for r in records:
        mine = {k: v for k, v in adds.items() if k[0] == r.qid}
        if not mine:
            out.append(r)
            continue
        touched.add(r.qid)
        judg, prov, kids = dict(r.judgments), dict(r.provenance), dict(r.expected_children)
        for (_, p), (lab, children, provenance) in sorted(mine.items()):
            judg[p], prov[p] = lab, provenance
            if lab == 2 and children:
                kids[p] = children
        out.append(r.model_copy(update={"judgments": judg, "provenance": prov, "expected_children": kids}))
    stats = {"human": len(adds) - n_auto, "auto_ooc": n_auto, "queries": len(touched)}
    return out, stats
