"""Khách nào mất hit khi đổi công thức, và món họ thực sự mua có phải món bán chạy không? (gate G2)

Câu hỏi của G2: mức giảm nexttrip là **chi phí thật** (gợi ý sai gu khách) hay là **hệ quả của dữ liệu giả lập** (event CDP
chọn điểm đến theo độ phổ biến, nên target của split thường là món bán chạy — hạ trọng số pop thì tất nhiên mất hit)?

Phép kiểm: lấy các khách **lật từ hit sang miss** khi đổi từ production sang cấu hình ứng viên, rồi so độ phổ biến của
target của họ với target của toàn bộ khách. Nếu target bị mất lệch hẳn về phía món bán chạy thì mức giảm phần lớn là
artefact của bộ sinh event; nếu không, đó là mất thật.

Kèm hai phân tích phục vụ quyết định:
- Phân bố `strategy` của khách lật: công thức chỉ áp khi KHÔNG có chuyến mở, nên khách lật phải nằm ngoài nhánh chuyến mở.
  Có khách chuyến mở bị lật là dấu hiệu sai ở chỗ khác.
- Chia theo số event trong train: nếu mất tập trung ở khách ít lịch sử thì có đường giảm thiệt hại — chỉ áp công thức mới
  khi tín hiệu dài hạn đủ mạnh.

Chạy:
    python -m src.evaluation.recsys_bench.theme_study.loss_analysis --vec npy:<prefix> --as-of <ISO> \
      --per-user p2_a.jsonl p4_c.jsonl --baseline P0_prod+F0_prod \
      --config P2_confidence+F14c_betweenQuantilePop35 --split nexttrip --out loss.json
"""
from __future__ import annotations

import argparse
import collections
import io
import json

import numpy as np

from src.evaluation.recsys_bench import splits as SP
from src.evaluation.recsys_bench.theme_study import theme_exp as TE
from src.evaluation.recsys_bench.theme_study.paired_ci import load

#: Nhánh "đang có chuyến mở" của engine (spec §4.4). Công thức giữa hai chuyến không chạm các khách này.
OPEN_TRIP_STRATEGIES = ("cross_vertical", "recent_activity", "cold_start_content")
EVENT_BUCKETS = ((0, 3), (3, 6), (6, 12), (12, 10 ** 9))


def pop_percentile(w: TE.World) -> dict:
    """productId → phân vị độ phổ biến (0–1) trong các unit gợi ý được; món không ai mua nằm cùng bậc thấp nhất."""
    rec = np.flatnonzero(w.rec)
    vals = w.pop[rec]
    order = np.argsort(vals, kind="stable")
    pct = np.empty(len(rec), dtype=np.float64)
    # Phân vị theo hạng trung bình của các giá trị bằng nhau: 60 % sản phẩm có pop = 0 nên không được xếp hạng tuỳ tiện.
    ranks = np.empty(len(rec), dtype=np.float64)
    i = 0
    s = vals[order]
    while i < len(s):
        j = i
        while j < len(s) and s[j] == s[i]:
            j += 1
        ranks[order[i:j]] = (i + j - 1) / 2
        i = j
    pct = ranks / max(len(rec) - 1, 1)
    return {w.pid[int(u)]: float(p) for u, p in zip(rec, pct)}


def describe(name: str, uids: list[str], feat: dict, pop_pct: dict) -> dict:
    """Tóm tắt một nhóm khách: độ phổ biến của target, số event, phân bố strategy."""
    if not uids:
        return {"group": name, "n": 0}
    pops = [pop_pct[feat[u]["target"]] for u in uids if feat[u]["target"] in pop_pct]
    nev = [feat[u]["nEvents"] for u in uids]
    return {
        "group": name, "n": len(uids),
        "targetPopPct_mean": round(float(np.mean(pops)), 4) if pops else None,
        "targetPopPct_median": round(float(np.median(pops)), 4) if pops else None,
        "targetPopPct_shareTop10": round(float(np.mean([p >= 0.9 for p in pops])), 4) if pops else None,
        "nEvents_median": float(np.median(nev)),
        "strategies": dict(collections.Counter(feat[u]["strategy"] for u in uids).most_common()),
        "shareOpenTrip": round(float(np.mean([feat[u]["strategy"] in OPEN_TRIP_STRATEGIES for u in uids])), 4),
    }


#: Phân vị độ phổ biến của target, để trả lời "lợi thế của production có nằm hết ở món bán chạy không".
POP_BUCKETS = ((0.0, 0.5), (0.5, 0.75), (0.75, 0.9), (0.9, 1.01))
#: Độ nhất quán hướng của lịch sử (`coherence`, xem `trip_coherence`). Khách lịch sử tản mát thì `u_long` là trung bình
#: của nhiều hướng khác nhau, bám theo nó không có nghĩa gì — giả thuyết: mất hit tập trung ở nhóm này.
COH_BUCKETS = ((0.0, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01))


def trip_coherence(profile, mean_vec=None) -> float:
    """Độ dài vector tổng hợp (mean resultant length) của các hướng chuyến, trong [0, 1].

    `u_long` = chuẩn hoá của `Σ w_t · v_t` với `v_t` là hướng từng chuyến (đã chuẩn hoá về 1). Tỷ số
    `‖Σ w_t v_t‖ / Σ w_t` bằng 1 khi mọi chuyến cùng hướng và tiến về 0 khi các chuyến trỏ tứ phía. Đây là thước đo
    "lịch sử khách có nhất quán không" độc lập với số event — khác hẳn `nEvents`.

    **Phải truyền `mean_vec`.** Trong không gian thô của e5-small mọi vector gần như song song (cos trung vị 0,81, báo cáo
    gốc §C), nên tỷ số này ra ≥ 0,8 cho *mọi* khách và không phân biệt được gì — đã đo 08/10: cả 1.835 khách nexttrip nằm
    trong một bậc. Trừ vector trung bình catalog trước rồi chuẩn hoá lại thì mới còn tín hiệu."""
    trips = list(profile.trips.values())
    if not trips:
        return 0.0
    from src.backend.app.domain.recommendation.profile import H_LONG_DAYS
    ws = np.array([2 ** (-t.age_days / H_LONG_DAYS) for t in trips], dtype=np.float64)
    V = np.stack([np.asarray(t.vec, dtype=np.float64) for t in trips])
    if mean_vec is not None:
        V = V - np.asarray(mean_vec, dtype=np.float64)
        V = V / np.maximum(np.linalg.norm(V, axis=1, keepdims=True), 1e-9)
    tot = float(ws.sum())
    return float(np.linalg.norm(ws @ V) / tot) if tot else 0.0


def by_coherence_bucket(base_hit: dict, cand_hit: dict, feat: dict) -> list[dict]:
    out = []
    for lo, hi in COH_BUCKETS:
        uids = [u for u in base_hit if u in cand_hit and lo <= feat[u]["coherence"] < hi]
        if not uids:
            continue
        b = float(np.mean([base_hit[u] for u in uids]))
        c = float(np.mean([cand_hit[u] for u in uids]))
        out.append({"coherence": f"[{lo}, {min(hi, 1.0)})", "n": len(uids),
                    "baseline": round(b, 4), "candidate": round(c, 4), "diff": round(c - b, 4),
                    "nEvents_median": float(np.median([feat[u]["nEvents"] for u in uids])),
                    "shareOpenTrip": round(float(np.mean([feat[u]["strategy"] in OPEN_TRIP_STRATEGIES for u in uids])), 4),
                    "shareOfTotalLoss": None})
    total = sum(r["diff"] * r["n"] for r in out)
    for r in out:
        r["shareOfTotalLoss"] = round(r["diff"] * r["n"] / total, 4) if total else None
    return out


def by_pop_bucket(base_hit: dict, cand_hit: dict, feat: dict, pop_pct: dict) -> list[dict]:
    """hit của hai cấu hình, chia theo độ phổ biến của **target**.

    Đây là phép kiểm quyết định cho G2: nếu lợi thế của production chỉ tồn tại ở nhóm target bán chạy, thì mức giảm đo
    được chủ yếu là hệ quả của việc bộ sinh event chọn điểm đến theo độ phổ biến, không phải mất khả năng đoán gu khách."""
    out = []
    for lo, hi in POP_BUCKETS:
        uids = [u for u in base_hit if u in cand_hit and lo <= pop_pct.get(feat[u]["target"], -1) < hi]
        if not uids:
            continue
        b = float(np.mean([base_hit[u] for u in uids]))
        c = float(np.mean([cand_hit[u] for u in uids]))
        out.append({"targetPopPct": f"[{lo}, {min(hi, 1.0)})", "n": len(uids),
                    "baseline": round(b, 4), "candidate": round(c, 4), "diff": round(c - b, 4),
                    "shareOfTotalLoss": None})
    total_loss = sum(r["diff"] * r["n"] for r in out)
    for r in out:
        r["shareOfTotalLoss"] = round(r["diff"] * r["n"] / total_loss, 4) if total_loss else None
    return out


def by_bucket(base_hit: dict, cand_hit: dict, feat: dict) -> list[dict]:
    out = []
    for lo, hi in EVENT_BUCKETS:
        uids = [u for u in base_hit if lo <= feat[u]["nEvents"] < hi]
        if not uids:
            continue
        b = float(np.mean([base_hit[u] for u in uids]))
        c = float(np.mean([cand_hit[u] for u in uids]))
        out.append({"nEvents": f"[{lo}, {hi if hi < 10 ** 9 else '∞'})", "n": len(uids),
                    "baseline_hit@20": round(b, 4), "candidate_hit@20": round(c, 4), "diff": round(c - b, 4),
                    "shareOpenTrip": round(float(np.mean([feat[u]["strategy"] in OPEN_TRIP_STRATEGIES for u in uids])), 4)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vec", required=True)
    ap.add_argument("--as-of", required=True)
    ap.add_argument("--per-user", nargs="+", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--split", default="nexttrip", choices=["llbo", "temporal", "nexttrip"])
    ap.add_argument("--profile", default="P2_confidence", help="profile dùng để tính `coherence` (của cấu hình ứng viên)")
    ap.add_argument("--metric", default="hit@20")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    from datetime import datetime
    TE.AS_OF = datetime.fromisoformat(a.as_of)

    rows = [r for r in load(a.per_user) if r.get("stratum") == a.split]
    base_hit = {r["uid"]: float(r[a.metric]) for r in rows if r["config"] == a.baseline}
    cand_hit = {r["uid"]: float(r[a.metric]) for r in rows if r["config"] == a.config}
    targets = {r["uid"]: r.get("target") for r in rows if r["config"] == a.baseline}
    shared = sorted(set(base_hit) & set(cand_hit))
    if not shared:
        raise SystemExit(f"không có khách nào xuất hiện ở cả {a.baseline!r} và {a.config!r} trong stratum {a.split!r}")

    idx, vec = TE.load_index(a.vec)
    events = TE.load_events()
    purchases = [e for e in events if e["eventName"] == "purchase"]
    w = TE.World(idx, vec, [e for e in purchases if TE.parse_ts(e["timestamp"]) < TE.AS_OF])
    pop_pct = pop_percentile(w)
    mean_vec = np.asarray(vec.E, dtype=np.float32).mean(0)      # cùng vector trung bình mà F13a dùng
    split = {"llbo": SP.leave_last_booking_out, "temporal": SP.temporal_split,
             "nexttrip": SP.next_trip_split}[a.split](events, idx)
    eng = TE.OfflineEngine(idx, vec, purchases, mode="prod")

    # `strategy` lấy từ chính engine; `coherence` tính trên profile P2 (profile của cấu hình ứng viên) bằng cách bắt lại
    # profile khi engine dựng nó — một lượt gọi / khách.
    import src.backend.app.application.recommendation.use_cases as UC
    from src.backend.app.domain.recommendation import build_profile as prod_build
    from src.evaluation.recsys_bench.theme_study.profile_variants import PROFILES, make_build_profile

    bp = make_build_profile(**PROFILES[a.profile])
    captured: list = []

    def capture(events_, E, tax, dest, today=None):
        p = bp(events_, E, tax, dest, today)
        captured.append(p)
        return p

    feat = {}
    UC.build_profile = capture
    try:
        for u in shared:
            captured.clear()
            r = eng.recommend(u, split.as_of_by_user[u], 4, split.train_by_user[u])
            coh = trip_coherence(captured[-1], mean_vec) if captured else 0.0
            feat[u] = {"strategy": r["strategy"], "nEvents": len(split.train_by_user[u]), "target": targets[u],
                       "coherence": round(coh, 4), "nTrips": len(captured[-1].trips) if captured else 0}
    finally:
        UC.build_profile = prod_build

    lost = [u for u in shared if base_hit[u] > cand_hit[u]]
    gained = [u for u in shared if base_hit[u] < cand_hit[u]]
    kept_hit = [u for u in shared if base_hit[u] == cand_hit[u] == 1.0]
    res = {
        "split": a.split, "metric": a.metric, "baseline": a.baseline, "config": a.config, "n": len(shared),
        "baseline_mean": round(float(np.mean([base_hit[u] for u in shared])), 4),
        "candidate_mean": round(float(np.mean([cand_hit[u] for u in shared])), 4),
        "groups": [describe("all", shared, feat, pop_pct), describe("baselineHit",
                   [u for u in shared if base_hit[u] == 1.0], feat, pop_pct),
                   describe("lost (hit→miss)", lost, feat, pop_pct),
                   describe("gained (miss→hit)", gained, feat, pop_pct),
                   describe("keptHit", kept_hit, feat, pop_pct)],
        "byEventBucket": by_bucket(base_hit, cand_hit, feat),
        "byTargetPopBucket": by_pop_bucket(base_hit, cand_hit, feat, pop_pct),
        "byCoherenceBucket": by_coherence_bucket(base_hit, cand_hit, feat),
    }
    json.dump(res, io.open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1), flush=True)


if __name__ == "__main__":
    main()
