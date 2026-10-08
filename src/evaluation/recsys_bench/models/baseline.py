"""`baseline_v1` + `regress --baseline` — khoá regression tự động cho recsys (Day 5 A5; spec `recsys-offline-eval.md` §1, §3.1).

Một baseline là ảnh chụp **đóng băng** của một run đã qua gate (mặc định run `<ngày>-<split>-gate-numpy`: pool engine, vectors numpy):
meta so được (configHash, split đóng băng, catalog, k, vectors…), mỗi arm có metric + `idsSha256` (sha256 của `{user: ids[:k]}`) +
rank và dấu vân tay `ids16` theo khách, nhãn phân khúc của `analyze` và các cặp "phải bằng nhau trong run" (G1/G2, `expect_equal_to`).

`check(baseline, summary, per_user)` so một run mới với baseline:

1. meta cứng lệch → `NotComparable` (mã 2): hai run không cùng điều kiện thì không có gì để kết luận;
2. arm `canary` (popular / random — không phụ thuộc engine) đổi ids → INCONCLUSIVE (mã 3): môi trường đổi (catalog, vector, pop);
3. arm `primary` (engine và các arm phải trùng engine) đổi ids ở bất kỳ khách nào → FAIL (mã 1); cặp G1/G2 trong run hết bằng → FAIL;
4. arm `scorer`: FAIL khi Δ (hit@10, hit@20, NDCG@10) tụt ≥ `maxDropPoints` điểm ∧ số khách tụt ròng ≥ `minUsersDrop` ∧
   p(tụt) < `pMax` (paired bootstrap như `compare`); chỉ Δ tụt mà không đủ hai điều kiện kia → WARN;
5. phân khúc (n ≥ `minSliceN`): hit@20 tụt ≥ `maxSliceDropPoints` điểm ∧ ≥ `minSliceUsersDrop` khách tụt ròng → FAIL (arm không phải canary).

Trạng thái tổng FAIL > INCONCLUSIVE > WARN > PASS → mã 1 / 3 / 0 / 0. Thuần Python + numpy: không typer, không DB.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ..analysis import LABELS, segments
from ..engine import config_hash
from ..metrics import paired_bootstrap
from ..paths import FROZEN_DIR
from .regress import compare_ids, ids_by_arm

SCHEMA_VERSION = 1
NAME = "baseline_v1"
ROLES = ("primary", "scorer", "canary")
PRIMARY_DEFAULT = ("engine", "engine_prod", "engine_nommr", "content_profile", "content_profile+mmr", "star_blend_a1", "star_blend_a1+mmr")
CANARY_DEFAULT = ("most_popular", "most_popular_in_destination")
#: cặp phải trùng ids trong cùng run (G1, G2, expect_equal_to của star_blend_a1) — chỉ ghi cặp có đủ hai arm
EQUALITY_PAIRS = (("content_profile+mmr", "engine"), ("content_profile", "engine_nommr"),
                  ("star_blend_a1", "content_profile"), ("star_blend_a1+mmr", "content_profile+mmr"))
THRESHOLDS_DEFAULT = {"maxDropPoints": 1.0, "minUsersDrop": 3, "pMax": 0.05, "maxSliceDropPoints": 3.0, "minSliceN": 20,
                      "minSliceUsersDrop": 2, "nBoot": 10_000, "seed": 42}
METRIC_KEYS = ("recall@5", "recall@10", "recall@20", "ndcg@5", "ndcg@10", "catalog_coverage", "availability_precision",
               "cross_category_rate", "cross_category_open_trip", "cross_category_open_trip_bought", "exposure_gini",
               "vertical_diversity@10", "returned_mean", "pool_truncated", "collab_coverage")
#: metric theo khách dùng cho luật FAIL (một target / khách ⟹ hit@k = recall@k)
USER_METRICS = ("hit@10", "hit@20", "ndcg@10")
#: meta phải bằng nhau để so được (đường dẫn trong dict meta)
HARD_META = ("modelVersion", "configHash", "engineRulesVersion", "k", "vectors", "vectorsMissing", "searchUnits", "recommendable",
             "split.kind", "split.frozenSha256", "split.eventsSha256", "split.usersTest", "algoMode", "funnel.pool")
SOFT_META = ("algosHash", "libs", "funnel.reranks")
STATUS_ORDER = ("PASS", "WARN", "INCONCLUSIVE", "FAIL")
EXIT_CODE = {"PASS": 0, "WARN": 0, "INCONCLUSIVE": 3, "FAIL": 1}


class NotComparable(ValueError):
    """Run và baseline không cùng điều kiện (meta cứng / arm / tập khách) — mã thoát 2."""


class BaselineError(ValueError):
    """Run không đủ điều kiện làm baseline (subset, chưa đóng băng split…) — mã thoát 1."""


# ---------------------------------------------------------------- dựng

def _ids(row: dict, k: int) -> list[str]:
    return [str(x) for x in (row.get("ids") or [])[:k]]


def ids_sha256(rows: dict[str, dict], k: int) -> str:
    """sha256 của JSON `{user: ids[:k]}` khoá sắp xếp — cùng mẫu `Split.frozen_sha256`."""
    payload = {u: _ids(r, k) for u, r in rows.items()}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def ids16(row: dict, k: int) -> str:
    return hashlib.sha256(json.dumps(_ids(row, k), ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def _get(d: dict, path: str):
    for part in path.split("."):
        if not isinstance(d, dict):
            return None
        d = d.get(part)
    return d


def default_role(arm: str) -> str:
    if arm in PRIMARY_DEFAULT:
        return "primary"
    if arm in CANARY_DEFAULT or arm.startswith("random-s") or arm == "random":
        return "canary"
    return "scorer"


def spec_hash(summary: dict, algo: str | None) -> str | None:
    """Băm cấu hình đã giải của một algo + `common` (ổn định giữa run `--only` và run đủ) — None cho arm không thuộc registry."""
    algos = _get(summary, "algosConfig.algos") or {}
    if not algo or algo not in algos:
        return None
    spec = {k: v for k, v in algos[algo].items() if k != "estimate"}
    return config_hash({"common": _get(summary, "algosConfig.common"), "spec": spec})


def meta_of(summary: dict) -> dict:
    split = summary.get("split") or {}
    return {"modelVersion": summary.get("modelVersion"), "configHash": summary.get("configHash"),
            "engineRulesVersion": _get(summary, "engineConfig.profile.ENGINE_RULES_VERSION"),
            "k": summary.get("k"), "vectors": summary.get("vectors"), "vectorsMissing": summary.get("vectorsMissing"),
            "searchUnits": summary.get("searchUnits"), "recommendable": summary.get("recommendable"),
            "asOf": summary.get("asOf"), "limitUsers": summary.get("limitUsers"), "usersEvaluated": summary.get("usersEvaluated"),
            "split": {"kind": split.get("kind"), "frozenSha256": split.get("frozenSha256"), "splitFile": split.get("splitFile"),
                      "usersTest": split.get("usersTest"), "eventsSha256": split.get("eventsSha256"), "T": split.get("T")},
            "algoMode": summary.get("algoMode"), "funnel": summary.get("funnel"), "algosHash": summary.get("algosHash"),
            "algosFile": summary.get("algosFile"), "libs": summary.get("libs"), "overrides": summary.get("overrides") or {}}


def default_path(summary: dict) -> Path:
    kind = _get(summary, "split.kind") or "unknown"
    as_of = str(summary.get("asOf") or "")[:10].replace("-", "")
    return FROZEN_DIR / f"{NAME}-{kind}-asof{as_of}.json"


def _row_metrics(raw_rows: list[dict]) -> dict[str, dict]:
    return {r["arm"]: r for r in raw_rows}


def _hit(rank, k: int) -> float:
    return 1.0 if rank is not None and rank <= k else 0.0


def _ndcg(rank, k: int) -> float:
    return float(1.0 / np.log2(rank + 1)) if rank is not None and rank <= k else 0.0


def user_metric(rank, metric: str) -> float:
    name, k = metric.split("@")
    return _hit(rank, int(k)) if name == "hit" else _ndcg(rank, int(k))


def equality_checks(by_arm: dict[str, dict[str, dict]], k: int) -> list[dict]:
    out = []
    for base, ref in EQUALITY_PAIRS:
        if base in by_arm and ref in by_arm:
            res = compare_ids(by_arm[base], by_arm[ref], k=k)
            out.append({"base": base, "ref": ref, "n": res["n"], "equal": res["equal"], "pass": res["pass"]})
    return out


def fingerprint(doc: dict) -> str:
    """Băm phần so được của baseline (meta + ids + metric + vai trò + nhãn phân khúc) — bỏ createdAt / note / gitDescribe để ghi lại
    cùng run là no-op; thêm nhãn (chạy `analyze` sau) là thay đổi thật, cần `--force`."""
    core = {"meta": doc["meta"], "labels": doc.get("labels"),
            "arms": {a: {"idsSha256": v["idsSha256"], "metrics": v["metrics"], "role": v["role"]} for a, v in doc["arms"].items()}}
    return hashlib.sha256(json.dumps(core, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


def build(summary: dict, per_user: list[dict], labels: dict[str, dict] | None, *, note: str, arms: list[str] | None = None,
          roles: dict[str, str] | None = None, with_ids: bool = False, git_describe: str | None = None,
          force: bool = False) -> dict:
    """Dựng dict baseline từ một run. `BaselineError` khi run là subset (`--limit-users`), chưa đóng băng split, hay gộp nhiều
    lượt chạy (trừ `force`)."""
    if summary.get("limitUsers") is not None:
        raise BaselineError(f"run có limitUsers={summary['limitUsers']} — baseline phải trên đủ khách của split")
    if not _get(summary, "split.frozenSha256"):
        raise BaselineError("run chưa đối chiếu bản đóng băng (--split-file) — baseline phải neo split đã commit")
    if len(summary.get("history") or []) > 1 and not force:
        raise BaselineError(f"run gộp {len(summary['history'])} lượt chạy (run --run-id nhiều lần) — chạy lại một lượt, hoặc --force")
    if not note.strip():
        raise BaselineError("--note bắt buộc (vì sao ghi baseline: mốc, run nguồn, history)")
    k = int(summary.get("k") or 20)
    by_arm = ids_by_arm(per_user)
    chosen = list(arms) if arms else sorted(by_arm)
    missing = [a for a in chosen if a not in by_arm]
    if missing:
        raise BaselineError(f"arm {missing} không có trong run (có: {sorted(by_arm)})")
    roles = dict(roles or {})
    bad = {a: r for a, r in roles.items() if r not in ROLES}
    if bad:
        raise BaselineError(f"--role {bad}: chỉ {ROLES}")
    raw = _row_metrics(summary.get("rawRows") or summary.get("rows") or [])
    out_arms = {}
    for arm in chosen:
        rows = by_arm[arm]
        row = raw.get(arm, {})
        role = roles.get(arm, default_role(arm))
        sample = next(iter(rows.values()))
        entry = {"role": role, "algo": row.get("algo"), "family": row.get("family"), "rerank": sample.get("rerank"),
                 "pool": sample.get("pool"), "specHash": spec_hash(summary, row.get("algo")),
                 "metrics": {m: row[m] for m in METRIC_KEYS if isinstance(row.get(m), (int, float))},
                 "nUsers": len(rows), "idsSha256": ids_sha256(rows, k),
                 "perUser": {u: {"rank": r.get("rank"), "ids16": ids16(r, k)} for u, r in sorted(rows.items())}}
        if with_ids and role == "primary":
            for u, r in rows.items():
                entry["perUser"][u]["ids"] = _ids(r, k)
        out_arms[arm] = entry
    doc = {"schemaVersion": SCHEMA_VERSION, "name": NAME,
           "createdAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "note": note.strip(),
           "gitDescribe": git_describe, "runId": summary.get("runId"), "meta": meta_of(summary),
           "thresholds": dict(THRESHOLDS_DEFAULT), "arms": out_arms,
           "idsEquality": equality_checks({a: by_arm[a] for a in chosen}, k)}
    if labels:
        users = sorted(set().union(*(by_arm[a].keys() for a in chosen)))
        doc["labels"] = {u: {lab: labels[u].get(lab) for lab in LABELS} for u in users if u in labels}
        doc["segments"] = segments({a: by_arm[a] for a in chosen}, doc["labels"], k=k)
    doc["fingerprint"] = fingerprint(doc)
    return doc


def write(doc: dict, path: Path, *, force: bool = False) -> str:
    """Ghi baseline; file đã có cùng fingerprint → không ghi lại ('unchanged'); khác → `BaselineError` trừ `force`."""
    path = Path(path)
    if path.exists():
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            old = {}
        if old.get("fingerprint") == doc["fingerprint"]:
            return "unchanged"
        if not force:
            raise BaselineError(f"{path} đã có (fingerprint {str(old.get('fingerprint'))[:12]} ≠ {doc['fingerprint'][:12]}, run "
                                f"{old.get('runId')}) — baseline là mốc đã commit; muốn thay thì --force + entry history + report")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps(doc) + "\n", encoding="utf-8")
    return "written"


#: object JSON không chứa object / mảng con (một khách, một nhãn, một ô phân khúc)
_LEAF = re.compile(r"\{\n\s+([^{}\[\]]*?)\n\s*\}")


def dumps(doc: dict) -> str:
    """JSON thụt 1, nhưng mỗi object lá trên một dòng: file gọn hơn và diff đọc được theo khách. Chuỗi JSON không chứa xuống dòng
    thô nên gộp dòng chỉ bỏ khoảng trắng giữa các token."""
    text = json.dumps(doc, ensure_ascii=False, indent=1, default=str)
    return _LEAF.sub(lambda m: "{" + " ".join(line.strip() for line in m.group(1).split("\n")) + "}", text)


def load(path: Path) -> dict:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schemaVersion") != SCHEMA_VERSION:
        raise NotComparable(f"{path}: schemaVersion {doc.get('schemaVersion')} ≠ {SCHEMA_VERSION}")
    return doc


# ---------------------------------------------------------------- so

def _worst(a: str, b: str) -> str:
    return a if STATUS_ORDER.index(a) >= STATUS_ORDER.index(b) else b


def _meta_diffs(base: dict, cur: dict, keys: tuple[str, ...]) -> list[dict]:
    return [{"key": key, "baseline": _get(base, key), "run": _get(cur, key)} for key in keys if _get(base, key) != _get(cur, key)]


def check(baseline: dict, summary: dict, per_user: list[dict], *, allow_subset: bool = False,
          thresholds: dict | None = None, git_describe: str | None = None) -> dict:
    th = {**THRESHOLDS_DEFAULT, **(baseline.get("thresholds") or {}), **{k: v for k, v in (thresholds or {}).items() if v is not None}}
    bmeta, cmeta = baseline["meta"], meta_of(summary)
    k = int(bmeta.get("k") or 20)
    warnings: list[str] = []
    hard = _meta_diffs(bmeta, cmeta, HARD_META)
    if hard:
        raise NotComparable("meta khác baseline: " + "; ".join(f"{d['key']} {d['baseline']!r} → {d['run']!r}" for d in hard))
    if cmeta.get("overrides"):
        raise NotComparable(f"run có --override {cmeta['overrides']} — baseline không có override")
    for d in _meta_diffs(bmeta, cmeta, SOFT_META):
        warnings.append(f"{d['key']} khác: {d['baseline']!r} → {d['run']!r}")
    if git_describe and baseline.get("gitDescribe") and git_describe != baseline["gitDescribe"]:
        warnings.append(f"commit khác: baseline {baseline['gitDescribe']} → run {git_describe}")
    by_arm = ids_by_arm(per_user)
    missing = [a for a in baseline["arms"] if a not in by_arm]
    if missing and not allow_subset:
        raise NotComparable(f"run thiếu arm của baseline {missing} — chạy đủ arm, hoặc --allow-subset")
    if missing:
        warnings.append(f"bỏ qua arm thiếu {missing} (--allow-subset)")
    if cmeta.get("limitUsers") is not None:
        if not allow_subset:
            raise NotComparable(f"run có limitUsers={cmeta['limitUsers']} — baseline trên đủ khách; dùng --allow-subset để so trên giao")
        warnings.append(f"run subset limitUsers={cmeta['limitUsers']}: so trên giao khách (--allow-subset)")
    raw = _row_metrics(summary.get("rawRows") or summary.get("rows") or [])
    status = "WARN" if warnings else "PASS"
    arms_out: dict[str, dict] = {}
    for arm, base in baseline["arms"].items():
        if arm not in by_arm:
            continue
        rows = by_arm[arm]
        sh = spec_hash(summary, (raw.get(arm) or {}).get("algo"))
        if base.get("specHash") != sh:
            raise NotComparable(f"arm {arm}: cấu hình algo khác baseline (specHash {base.get('specHash')} → {sh})")
        users = sorted(set(base["perUser"]) & set(rows))
        if not users:
            raise NotComparable(f"arm {arm}: không có khách chung với baseline")
        if not allow_subset and len(users) != len(base["perUser"]):
            raise NotComparable(f"arm {arm}: {len(users)}/{len(base['perUser'])} khách chung — dùng --allow-subset")
        changed = [u for u in users if ids16(rows[u], k) != base["perUser"][u]["ids16"]]
        full = len(users) == len(base["perUser"]) == len(rows)
        same_sha = ids_sha256(rows, k) == base["idsSha256"] if full else not changed
        res = {"role": base["role"], "n": len(users), "idsChanged": len(changed), "idsSha256Equal": bool(same_sha),
               "changedExamples": [{"user": u, "strategy": rows[u].get("strategy"), "poolTruncated": rows[u].get("poolTruncated"),
                                    "rankBaseline": base["perUser"][u]["rank"], "rankRun": rows[u].get("rank"),
                                    "ids": _ids(rows[u], k)[:6]} for u in changed[:10]],
               "metrics": {}, "verdict": "PASS", "reasons": []}
        cur_metrics = raw.get(arm) or {}
        res["aggregate"] = {m: {"baseline": base["metrics"].get(m), "run": cur_metrics.get(m)}
                            for m in base["metrics"] if cur_metrics.get(m) != base["metrics"].get(m)}
        for metric in USER_METRICS:
            a = {u: user_metric(base["perUser"][u]["rank"], metric) for u in users}
            b = {u: user_metric(rows[u].get("rank"), metric) for u in users}
            bs = paired_bootstrap(a, b, n_boot=int(th["nBoot"]), seed=int(th["seed"]))
            worse = sum(b[u] < a[u] for u in users)
            better = sum(b[u] > a[u] for u in users)
            p_drop = None if bs["p_one_sided"] is None else 1.0 - bs["p_one_sided"]
            res["metrics"][metric] = {"delta": bs["delta"], "ci95": bs["ci95"], "pDrop": p_drop, "worse": worse, "better": better}
            drop = bs["delta"] is not None and bs["delta"] <= -float(th["maxDropPoints"])
            if base["role"] == "scorer" and drop:
                if worse - better >= int(th["minUsersDrop"]) and p_drop is not None and p_drop < float(th["pMax"]):
                    res["verdict"] = "FAIL"
                    res["reasons"].append(f"{metric} tụt {bs['delta']:+.2f} điểm, {worse - better} khách ròng, p {p_drop:.3f}")
                else:
                    res["verdict"] = _worst(res["verdict"], "WARN")
                    res["reasons"].append(f"{metric} tụt {bs['delta']:+.2f} điểm (chưa đủ số khách / p)")
        if changed:
            if base["role"] == "primary":
                res["verdict"] = "FAIL"
                res["reasons"].append(f"ids[:{k}] đổi ở {len(changed)}/{len(users)} khách (arm primary phải khớp 100 %)")
            elif base["role"] == "canary":
                res["verdict"] = _worst(res["verdict"], "INCONCLUSIVE")
                res["reasons"].append(f"canary đổi ids ở {len(changed)} khách — môi trường (catalog / vector / popularity) khác baseline")
        arms_out[arm] = res
        status = _worst(status, res["verdict"])
    # cặp phải bằng nhau trong run
    eq_now = {(e["base"], e["ref"]): e for e in equality_checks(by_arm, k)}
    eq_out = []
    for e in baseline.get("idsEquality") or []:
        now = eq_now.get((e["base"], e["ref"]))
        item = {**e, "runEqual": None if now is None else now["equal"], "runN": None if now is None else now["n"],
                "runPass": None if now is None else now["pass"]}
        if e["pass"] and now is not None and not now["pass"]:
            item["verdict"] = "FAIL"
            status = "FAIL"
        eq_out.append(item)
    # phân khúc
    slices = []
    labels = baseline.get("labels") or {}
    if labels:
        for label in LABELS:
            groups: dict[str, list[str]] = {}
            for u, lab in labels.items():
                groups.setdefault(str(lab.get(label)), []).append(u)
            for value, members in sorted(groups.items()):
                for arm, base in baseline["arms"].items():
                    if arm not in by_arm or base["role"] == "canary":
                        continue
                    us = [u for u in members if u in by_arm[arm] and u in base["perUser"]]
                    if len(us) < int(th["minSliceN"]):
                        continue
                    a = [_hit(base["perUser"][u]["rank"], 20) for u in us]
                    b = [_hit(by_arm[arm][u].get("rank"), 20) for u in us]
                    delta = (float(np.mean(b)) - float(np.mean(a))) * 100.0
                    net = sum(x > y for x, y in zip(a, b)) - sum(y > x for x, y in zip(a, b))
                    if delta <= -float(th["maxSliceDropPoints"]) and net >= int(th["minSliceUsersDrop"]):
                        slices.append({"label": label, "value": value, "arm": arm, "n": len(us), "deltaHit20": delta, "netUsersDrop": net,
                                       "verdict": "FAIL"})
                        status = "FAIL"
    return {"status": status, "exit": EXIT_CODE[status], "baseline": {"runId": baseline.get("runId"), "createdAt": baseline.get("createdAt"),
                                                                        "gitDescribe": baseline.get("gitDescribe"), "note": baseline.get("note")},
            "runId": summary.get("runId"), "gitDescribe": git_describe, "k": k, "thresholds": th, "warnings": warnings,
            "arms": arms_out, "idsEquality": eq_out, "slices": slices}


def _fmt_delta(m: dict) -> str:
    if m.get("delta") is None:
        return "—"
    lo, hi = m["ci95"]
    return f"{m['delta']:+.2f} [{lo:+.2f}, {hi:+.2f}]"


def markdown(result: dict) -> str:
    b = result["baseline"]
    lines = [f"**regress --baseline: {result['status']}** (mã {result['exit']}) · run `{result['runId']}` vs baseline run `{b['runId']}` "
             f"({b['createdAt']}, {b['gitDescribe']}) · k = {result['k']}"]
    for w in result["warnings"]:
        lines.append(f"- cảnh báo: {w}")
    lines += ["", "| Arm | Vai trò | Khách | ids đổi | Δhit@10 [CI95] | Δhit@20 [CI95] | ΔNDCG@10 [CI95] | Kết luận |",
              "|---|---|---:|---:|---|---|---|---|"]
    for arm, r in result["arms"].items():
        m = r["metrics"]
        lines.append(f"| {arm} | {r['role']} | {r['n']} | {r['idsChanged']} | {_fmt_delta(m['hit@10'])} | {_fmt_delta(m['hit@20'])} | "
                     f"{_fmt_delta(m['ndcg@10'])} | {r['verdict']}{': ' + '; '.join(r['reasons']) if r['reasons'] else ''} |")
    if result["idsEquality"]:
        lines += ["", "| Cặp phải trùng trong run | Baseline | Run |", "|---|---|---|"]
        for e in result["idsEquality"]:
            run_cell = "—" if e["runEqual"] is None else f"{e['runEqual']}/{e['runN']}"
            flag = " **FAIL**" if e.get("verdict") == "FAIL" else ""
            lines.append(f"| `{e['base']}` = `{e['ref']}` | {e['equal']}/{e['n']} | {run_cell}{flag} |")
    if result["slices"]:
        lines += ["", "| Phân khúc tụt | Arm | n | Δhit@20 | khách tụt ròng |", "|---|---|---:|---:|---:|"]
        for s in result["slices"]:
            lines.append(f"| {s['label']} = {s['value']} | {s['arm']} | {s['n']} | {s['deltaHit20']:+.2f} | {s['netUsersDrop']} |")
    examples = [(arm, e) for arm, r in result["arms"].items() for e in r["changedExamples"]][:10]
    if examples:
        lines += ["", "| Arm | Khách đổi ids | strategy | pool cắt | rank baseline → run | ids[:6] |", "|---|---|---|---:|---|---|"]
        for arm, e in examples:
            lines.append(f"| {arm} | {e['user']} | {e['strategy']} | {e['poolTruncated']} | {e['rankBaseline']} → {e['rankRun']} | {e['ids']} |")
    return "\n".join(lines)
