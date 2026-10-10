"""Đo `compose_plan` (AC-AGT-04: tối ưu quãng đường, ngân sách, phương án khác) trên catalog Postgres. Chỉ đọc.

Mỗi ô (điểm đến × số ngày) lấy `--samples` mẫu ngẫu nhiên (seed cố định): mỗi mẫu `--places` điểm tham quan và
`--hotels` hạng phòng còn bán, có giá, có toạ độ; 2 người lớn; không vé máy bay. Mỗi mẫu chạy ba mức ngân sách:
- không có ngân sách;
- ngân sách chặt: tiền hoạt động + số đêm × giá phòng ở phân vị 25% của mẫu;
- ngân sách rộng: như trên với phân vị 75%.

Tiền hoạt động lấy từ lịch không ngân sách (cùng điểm), nên hai mức ngân sách chỉ khác ở phần khách sạn.

    DATABASE_URL=postgresql://vota_app_login:vota@localhost:5432/vota \\
        .venv/bin/python -m src.evaluation.agent.routing_bench --samples 30 --seed 42
"""
from __future__ import annotations

import argparse
import os
import random
import statistics
import time

import psycopg
from psycopg.rows import dict_row

from src.backend.app.domain.itinerary.planning import compose_plan

DESTINATIONS = ("Phú Quốc", "Nha Trang", "Hà Nội", "Hội An", "Huế", "Vũng Tàu")
DAYS = (3, 5)
PARTY = {"type": "COUPLE", "adults": 2, "children": 0}

QUERY = """
SELECT p.product_id::text AS id, p.name, m.variant, p.destination, p.unit_price, p.attributes,
       m.latitude, m.longitude, m.parent_product_id::text AS parent
FROM cdp.products p JOIN catalog.product_meta m USING (product_id)
WHERE p.available AND p.unit_price IS NOT NULL AND p.destination = %s
  AND (m.variant = 'hotel_room' OR p.taxonomy = 'attraction')
ORDER BY p.product_id
"""


def candidate(row: dict) -> dict:
    """Dòng catalog → ứng viên như Search trả về (toạ độ phòng lấy theo `product_meta`, có thể là toạ độ khách sạn cha)."""
    hotel = row["variant"] == "hotel_room"
    attributes = {**(row["attributes"] or {}), "latitude": row["latitude"], "longitude": row["longitude"]}
    if row["parent"]:
        attributes["parentProductId"] = row["parent"]
    return {"productId": row["id"], "name": row["name"], "taxonomy": "hotel" if hotel else "attraction",
            "destination": row["destination"], "unitPrice": int(row["unit_price"]), "currency": "VND",
            "priceUnit": "PER_NIGHT" if hotel else "PER_PERSON", "available": True, "description": "",
            "attributes": attributes, "availableFrom": None, "availableTo": None}


def intent(destination: str, days: int, budget: int | None) -> dict:
    return {"destination": destination, "startDate": None, "days": days, "party": PARTY, "budget": budget,
            "interests": [], "pace": None}


def stay_cost(proposal: dict, candidates: dict) -> int:
    return sum(candidates[s["stay_id"]]["unitPrice"] * s["nights"] for s in proposal.get("stays") or [])


def activity_cost(proposal: dict, candidates: dict) -> int:
    return sum(candidates[s["product_id"]]["unitPrice"] * 2 for s in proposal["slots"] if s["product_id"])


def quantile(values: list[int], q: float) -> int:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def run(rows: list[dict], destination: str, days: int, args, rng: random.Random) -> dict[str, list[dict]]:
    hotels = [r for r in rows if r["variant"] == "hotel_room" and r["latitude"] is not None]
    places = [r for r in rows if r["variant"] != "hotel_room"]
    nights = max(1, days - 1)
    out: dict[str, list[dict]] = {"none": [], "tight": [], "wide": []}
    for _ in range(args.samples):
        chosen = rng.sample(places, min(args.places, len(places))) + rng.sample(hotels, min(args.hotels, len(hotels)))
        candidates = {r["id"]: candidate(r) for r in chosen}
        sources = {pid: "search" for pid in candidates}
        base = compose_plan(candidates, sources, intent(destination, days, None))
        acts = activity_cost(base, candidates)
        prices = [candidates[r["id"]]["unitPrice"] for r in chosen if r["variant"] == "hotel_room"]
        budgets = {"none": None, "tight": acts + nights * quantile(prices, 0.25),
                   "wide": acts + nights * quantile(prices, 0.75)}
        for level, budget in budgets.items():
            started = time.perf_counter()
            proposal = compose_plan(candidates, sources, intent(destination, days, budget))
            elapsed = (time.perf_counter() - started) * 1000
            total = stay_cost(proposal, candidates) + activity_cost(proposal, candidates)
            options = proposal.get("options") or []
            closer = [o for o in options if o["km_delta"] < 0]
            cheaper = [o for o in options if o["km_delta"] > 0]
            out[level].append({"km": proposal.get("distance_km"), "hotel": stay_cost(proposal, candidates),
                               "fits": budget is None or total <= budget, "options": len(options),
                               "closer": closer[0] if closer else None, "cheaper": cheaper[-1] if cheaper else None,
                               "ms": elapsed, "two_stays": len(proposal.get("stays") or []) > 1})
    return out


def summary(results: list[dict]) -> str:
    known = [r for r in results if r["km"] is not None]
    if not known:
        return "| – | – | – | – | – | – | – |"
    km = statistics.mean(r["km"] for r in known)
    hotel = statistics.mean(r["hotel"] for r in known) / 1e6
    fits = 100 * sum(r["fits"] for r in results) / len(results)
    with_options = 100 * sum(r["options"] > 0 for r in known) / len(known)
    closer = [r["closer"] for r in known if r["closer"]]
    cheaper = [r["cheaper"] for r in known if r["cheaper"]]
    closer_text = (f"+{statistics.median(o['money_delta'] for o in closer) / 1e6:.1f} tr → "
                   f"−{statistics.median(-o['km_delta'] for o in closer):.1f} km ({len(closer)})") if closer else "–"
    cheaper_text = (f"−{statistics.median(-o['money_delta'] for o in cheaper) / 1e6:.1f} tr → "
                    f"+{statistics.median(o['km_delta'] for o in cheaper):.1f} km ({len(cheaper)})") if cheaper else "–"
    p95 = quantile([int(r["ms"]) for r in results], 0.95)
    return f"| {km:.1f} | {hotel:.1f} | {fits:.0f}% | {with_options:.0f}% | {closer_text} | {cheaper_text} | {p95} |"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--samples", type=int, default=30)
    parser.add_argument("--places", type=int, default=10)
    parser.add_argument("--hotels", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    labels = {"none": "không", "tight": "chặt (p25)", "wide": "rộng (p75)"}
    print("| Điểm đến | Ngày | Ngân sách | km TB | Khách sạn TB (tr) | Vừa ngân sách | Có phương án khác "
          "| Gần hơn: trung vị (số mẫu) | Rẻ hơn: trung vị (số mẫu) | p95 ms |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as connection:
        connection.execute("SET default_transaction_read_only = on")
        for destination in DESTINATIONS:
            rows = connection.execute(QUERY, (destination,)).fetchall()
            for days in DAYS:
                rng = random.Random(f"{args.seed}-{destination}-{days}")
                results = run(rows, destination, days, args, rng)
                for level, label in labels.items():
                    print(f"| {destination} | {days} | {label} {summary(results[level])}")


if __name__ == "__main__":
    main()
