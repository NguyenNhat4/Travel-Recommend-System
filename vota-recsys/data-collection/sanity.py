"""The mandatory popularity sanity check (spec section 10, handbook section 6).

    "Kiểm tra tỉnh táo: nếu baseline theo độ phổ biến cho điểm gần bằng không,
     dữ liệu của bạn quá ngẫu nhiên. Nếu không gì đánh bại được nó, dữ liệu quá
     tập trung."

This is the diagnostic that tells you whether the seeded histories are worth
training on, and it is deliberately implemented as a runnable check rather than
a comment, because the failure it catches is invisible otherwise: random data
makes a broken recommender look fine, and every model scores the same.

Three baselines over a leave-last-out split, which are also the three the
handbook (section 12) requires as mandatory comparisons all the way through the
project:

* **random** — the floor. Anything at or below this means no signal.
* **most-popular** — global purchase counts.
* **most-popular-in-destination** — the one that should win, and the reason
  popularity is sampled per destination rather than globally.

Where this lives: the handbook puts evaluation metrics in ``eval/``, and that is
right for the Week 2+ model comparison. This copy stays inside
``data-collection`` because it is checking the *generator*, not a model — it has
to run at the end of ``seed-histories`` to tell you immediately whether to
re-seed, and coupling that to a directory Week 2 has not created yet would mean
the check does not run at all in Week 1.
"""

from __future__ import annotations

import logging
import random
from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import text

import db
import exitcodes
from config import Config

log = logging.getLogger("sanity")


def _load_purchases(cfg: Config) -> list[dict[str, Any]]:
    with db.session_scope(cfg) as s:
        rows = s.execute(
            text(
                """
                SELECT e.cdp_user_id, e.product_id, e.timestamp, p.destination
                  FROM events e
                  JOIN products p USING (product_id)
                 WHERE e.event_name = 'purchase'
                 ORDER BY e.cdp_user_id, e.timestamp
                """
            )
        ).mappings().all()
    return [dict(r) for r in rows]


def recall_at_k(recommended: list[str], held_out: str, k: int) -> float:
    return 1.0 if held_out in recommended[:k] else 0.0


def evaluate(cfg: Config, *, k: int, seed: int = 0) -> dict[str, Any]:
    """Leave-last-out split, then Recall@k for the three baselines.

    Leave-*last*-out rather than random hold-out because these are bookings in
    time order: predicting a past purchase from a future one leaks, and would
    flatter every baseline equally, which defeats the comparison.
    """
    purchases = _load_purchases(cfg)
    if not purchases:
        return {"error": "no purchase events joined to products"}

    by_user: dict[str, list[dict]] = defaultdict(list)
    for p in purchases:
        by_user[p["cdp_user_id"]].append(p)

    min_events = int(cfg.section("sanity").get("min_events_for_split", 2))
    train: list[dict] = []
    tests: list[tuple[str, str, str | None]] = []
    for user, events in by_user.items():
        if len(events) < min_events:
            train.extend(events)
            continue
        *head, last = events
        train.extend(head)
        tests.append((user, str(last["product_id"]), last.get("destination")))

    if not tests:
        return {
            "error": (
                f"no user has >= {min_events} purchases, so there is nothing to hold out. "
                "The catalogue may be too small for the configured trip shapes."
            )
        }

    global_counts = Counter(str(p["product_id"]) for p in train)
    dest_counts: dict[str, Counter] = defaultdict(Counter)
    for p in train:
        dest_counts[p.get("destination") or "?"][str(p["product_id"])] += 1

    all_products = sorted({str(p["product_id"]) for p in purchases})
    rng = random.Random(seed)

    popular_top = [pid for pid, _ in global_counts.most_common(k)]
    scores = {"random": 0.0, "popular": 0.0, "popular_in_destination": 0.0}

    for _user, held_out, destination in tests:
        scores["random"] += recall_at_k(rng.sample(all_products, min(k, len(all_products))), held_out, k)
        scores["popular"] += recall_at_k(popular_top, held_out, k)
        in_dest = [pid for pid, _ in dest_counts.get(destination or "?", Counter()).most_common(k)]
        if len(in_dest) < k:
            # Top up from the global list, as a real most-popular-in-destination
            # baseline would: a thin destination should not be punished for
            # having fewer than k candidates.
            in_dest += [p for p in popular_top if p not in in_dest][: k - len(in_dest)]
        scores["popular_in_destination"] += recall_at_k(in_dest, held_out, k)

    n = len(tests)
    return {
        "k": k,
        "users_evaluated": n,
        "train_purchases": len(train),
        "catalogue_size": len(all_products),
        "distinct_products_purchased": len(global_counts),
        "recall": {name: round(total / n, 4) for name, total in scores.items()},
        "top20_purchase_share": _top_share(global_counts),
    }


def _top_share(counts: Counter, fraction: float = 0.2) -> float:
    """Share of purchases held by the top 20% of purchased products.

    The observed version of the power law the generator aims for: spec section
    10 wants ~20% of products taking ~80% of bookings, and this measures what
    actually came out rather than what was configured.
    """
    if not counts:
        return 0.0
    ordered = [c for _, c in counts.most_common()]
    k = max(1, int(len(ordered) * fraction))
    return round(sum(ordered[:k]) / sum(ordered), 4)


def run_sanity(cfg: Config, *, k: int | None = None) -> int:
    db.check_connection(cfg)
    cfg_sanity = cfg.section("sanity")
    k = int(k or cfg_sanity.get("k", 20))
    band = cfg_sanity.get("popular_recall_band") or {}
    low, high = float(band.get("low", 0.02)), float(band.get("high", 0.60))

    result = evaluate(cfg, k=k)
    if "error" in result:
        log.error("sanity check cannot run: %s", result["error"])
        return exitcodes.GATE_FAILED

    r = result["recall"]
    print("=" * 78)
    print(f"Popularity sanity check (spec section 10) — Recall@{k}")
    print("=" * 78)
    print(f"  users evaluated:              {result['users_evaluated']}")
    print(f"  training purchases:           {result['train_purchases']}")
    print(f"  catalogue size:               {result['catalogue_size']}")
    print(f"  distinct products purchased:  {result['distinct_products_purchased']}")
    print(f"  top-20% purchase share:       {result['top20_purchase_share']:.0%}  "
          f"(spec section 10 wants ~80%)")
    print()
    print(f"  random                        {r['random']:.4f}")
    print(f"  most-popular                  {r['popular']:.4f}")
    print(f"  most-popular-in-destination   {r['popular_in_destination']:.4f}")
    print()

    problems: list[str] = []

    # Before judging the baselines, check that Recall@k can mean anything at
    # this catalogue size. With 26 products and k=20, a *random* recommender
    # scores 0.79 simply because the list covers three quarters of the
    # catalogue — and the band test then reports "data too concentrated", which
    # sends someone off tuning zipf_alpha when the real answer is "get more
    # products". Diagnose that first.
    catalogue = int(result["catalogue_size"])
    if catalogue < k * 3:
        log.error(
            "Recall@%d is not informative with only %d products in the catalogue: a random "
            "baseline already scores %.2f because the recommendation list covers %.0f%% of "
            "everything. This is a CATALOGUE SIZE problem, not a seeding problem — spec "
            "section 0 item 1 wants 2,000-5,000 products. Either grow the catalogue or "
            "re-run with a smaller k (e.g. --k %d) to get a reading in the meantime.",
            k, catalogue, r["random"], 100.0 * min(k, catalogue) / catalogue,
            max(1, catalogue // 10),
        )
        print("VERDICT: INCONCLUSIVE — catalogue too small to evaluate Recall@%d." % k)
        return exitcodes.GATE_FAILED

    if r["popular"] < low:
        problems.append(
            f"most-popular Recall@{k} is {r['popular']:.4f}, below {low}. Spec section 10: "
            "'popularity baseline gần 0 nghĩa là dữ liệu quá ngẫu nhiên'. The generated "
            "data has no popularity structure to learn — check seed.zipf_alpha and that "
            "products are sampled per destination."
        )
    if r["popular"] > high:
        problems.append(
            f"most-popular Recall@{k} is {r['popular']:.4f}, above {high}. Spec section 10: "
            "if nothing can beat the popularity baseline the data is too concentrated. "
            "Lower seed.zipf_alpha or widen the catalogue."
        )
    if cfg_sanity.get("require_popular_beats_random", True) and r["popular"] <= r["random"]:
        problems.append(
            f"most-popular ({r['popular']:.4f}) does not beat random ({r['random']:.4f}). "
            "That is the clearest possible sign the histories are noise."
        )
    if r["popular_in_destination"] < r["popular"]:
        # A warning, not a failure: with a small catalogue the two baselines
        # genuinely converge, and that is a fact about the data rather than a bug.
        log.warning(
            "most-popular-in-destination (%.4f) does not beat most-popular (%.4f). With a "
            "small or single-destination catalogue these converge; with a full one it means "
            "popularity is not destination-specific.",
            r["popular_in_destination"], r["popular"],
        )

    if problems:
        for p in problems:
            log.error("SANITY FAILED: %s", p)
        print("VERDICT: FAIL — re-seed before building anything on this data.")
        return exitcodes.GATE_FAILED

    print("VERDICT: PASS — the popularity baseline is beatable but not trivial.")
    return exitcodes.OK
