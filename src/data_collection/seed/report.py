"""Bước 6 — tóm tắt ra stdout và ghi khối `seed-report` trong `src/data_collection/README.md`.

Ba việc:

* chạy `db/verify.sql` / `db/verify_insider.sql` **bằng psycopg**, không cần psql cài sẵn
  (máy dev Windows thường không có). Bỏ dòng meta-command `\\pset` vì driver không hiểu chúng;
* đo baseline most-popular-in-destination để biết dữ liệu có "khó nhưng thắng được" không
  (DATABASE_SCHEMA §8 bước 7) — mock ngẫu nhiên đều sẽ lộ ra ở đây;
* chỉ thay phần giữa hai mốc trong README, **không ghi đè** sổ tay crawler 426 dòng.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from . import config


def _statements(sql_path: Path) -> list[str]:
    """Tách file verify thành từng câu lệnh, bỏ comment và meta-command của psql."""
    lines = [
        line
        for line in sql_path.read_text(encoding="utf-8").splitlines()
        if not line.strip().startswith("--") and not line.strip().startswith("\\")
    ]
    body = "\n".join(lines)
    return [s.strip() for s in body.split(";") if s.strip()]


def run_verify(conn, sql_path: Path) -> list[str]:
    """Trả về danh sách dòng kết quả, mỗi dòng dạng 'label: PASS' hoặc 'label: FAIL (n)'."""
    results: list[str] = []
    for statement in _statements(sql_path):
        with conn.cursor() as cur:
            cur.execute(statement)
            row = cur.fetchone()
        results.append(str(row[0]) if row else "(không có kết quả)")
    return results


def classify(results: list[str], *, synthetic: bool) -> dict:
    """Chia kết quả thành pass / fail thật / fail dự kiến.

    Hai ngưỡng của `db/verify.sql` là của crawl thật (2.216 sản phẩm, 316/559 property có phòng);
    catalog tổng hợp ~450 dòng không thể đạt. Đánh dấu riêng thay vì sửa db/*.sql (AGENTS.md §6.5).
    """
    passed, failed, expected = [], [], []
    for line in results:
        if "PASS" in line:
            passed.append(line)
        elif synthetic and any(line.startswith(prefix) for prefix in config.EXPECTED_SYNTHETIC_FAILURES):
            expected.append(line)
        else:
            failed.append(line)
    return {"passed": passed, "failed": failed, "expected_failures": expected}


def baseline_recall(conn, k: int = config.BASELINE_K) -> dict:
    """Recall@k của baseline 'most popular in destination', kiểu leave-last-purchase-out.

    Với mỗi khách có ≥ 2 chuyến mua: giấu chuyến cuối, gợi ý k sản phẩm được mua nhiều nhất trong
    destination của chuyến đó (tính trên dữ liệu còn lại), xem có trúng sản phẩm đã giấu không.
    Gần 0 nghĩa là dữ liệu quá ngẫu nhiên; > 0.6 nghĩa là baseline bất khả chiến bại.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH purchases AS (
                SELECT e.cdp_user_id, e.product_id, p.destination, e."timestamp",
                       row_number() OVER (PARTITION BY e.cdp_user_id ORDER BY e."timestamp" DESC) AS rn
                FROM   cdp.events e
                JOIN   cdp.products p ON p.product_id = e.product_id
                WHERE  e.event_name = 'purchase'
            ),
            held_out AS (SELECT * FROM purchases WHERE rn = 1),
            history  AS (SELECT * FROM purchases WHERE rn > 1),
            popular AS (
                SELECT destination, product_id,
                       row_number() OVER (PARTITION BY destination ORDER BY count(*) DESC, product_id) AS rank
                FROM   history GROUP BY destination, product_id
            )
            SELECT count(*) FILTER (WHERE hit) , count(*)
            FROM (
                SELECT EXISTS (
                         SELECT 1 FROM popular pop
                         WHERE pop.destination = h.destination
                           AND pop.rank <= %s
                           AND pop.product_id = h.product_id
                       ) AS hit
                FROM   held_out h
                WHERE  EXISTS (SELECT 1 FROM history hi WHERE hi.cdp_user_id = h.cdp_user_id)
            ) t
            """,
            (k,),
        )
        hits, total = cur.fetchone()

        # Số sản phẩm đặt được trung vị mỗi điểm đến — giải thích vì sao Recall cao hay thấp.
        cur.execute(
            """
            SELECT percentile_disc(0.5) WITHIN GROUP (ORDER BY n)
            FROM (
                SELECT p.destination, count(*) AS n
                FROM   cdp.products p JOIN catalog.product_meta m USING (product_id)
                WHERE  m.is_bookable AND p.available
                GROUP  BY p.destination
            ) t
            """
        )
        pool_median = cur.fetchone()[0]

    recall = round(hits / total, 3) if total else 0.0
    low, high = config.BASELINE_RECALL_RANGE
    return {
        "k": k,
        "users_evaluated": total,
        "recall": recall,
        "in_range": bool(low <= recall <= high) if total else False,
        "range": [low, high],
        "pool_median": pool_median,
    }


def _table(rows: list[tuple[str, object]]) -> str:
    body = "\n".join(f"| {name} | {value} |" for name, value in rows)
    return f"| Mục | Giá trị |\n|---|---|\n{body}"


def render(summary: dict) -> str:
    """Nội dung khối seed-report (markdown)."""
    products = summary["products"]
    combos = summary["combos"]
    histories = summary["histories"]
    app = summary["app"]
    insider = summary["insider"]
    verify = summary["verify"]
    verify_insider = summary["verify_insider"]
    baseline = summary["baseline"]

    lines: list[str] = []
    lines.append("## Mock data tuần 1 — kết quả lần chạy gần nhất")
    lines.append("")
    lines.append(
        "Phần này do `python -m data_collection.seed` sinh tự động (`seed/report.py`). "
        "Đừng sửa tay — chạy lại lệnh seed để cập nhật. Phần còn lại của README là sổ tay crawler, viết tay."
    )
    lines.append("")
    lines.append(
        _table(
            [
                ("as_of", f"`{summary['as_of']}`"),
                ("seed", f"`{summary['seed']}`"),
                ("Cửa sổ đặt chỗ", f"`{summary['window'][0]}` → `{summary['window'][1]}` ({config.WINDOW_DAYS} ngày)"),
                ("Nguồn catalog", f"`{summary['products_path']}`"),
                ("Loại catalog", "tổng hợp (`gen_products.py`)" if summary["synthetic"] else "crawl thật"),
                # Thời gian chạy chỉ in ra stdout, KHÔNG ghi vào khối này: nó đổi sau mỗi lần chạy
                # và sẽ làm file bẩn ở mọi lần seed, gây conflict vô ích khi nhiều người cùng chạy.
            ]
        )
    )
    lines.append("")

    lines.append("### Số dòng từng bảng")
    lines.append("")
    lines.append(
        _table(
            [
                ("`cdp.products`", products["total"]),
                ("— trong đó không bán được trong cửa sổ", products["unavailable"]),
                ("— có lịch 30 ngày (`attributes.availability`)", products["with_calendar"]),
                ("`catalog.combo_items`", combos["items"]),
                ("`cdp.profiles`", histories["profiles"]),
                ("`cdp.events`", histories["events"]),
                ("`app.users`", app["users"]),
                ("`app.bookings` / `booking_items`", f"{app['bookings']} / {app['booking_items']}"),
                ("`insider.insider_profiles`", insider["profiles"]),
                ("`insider.identifiers` (đang hiệu lực)", insider["current_identifiers"]),
                ("`insider.insider_events` (tổng / còn hạn)", f"{insider['events']} / {insider['live_events']}"),
                ("`insider.channel_events`", insider["channel_events"]),
                ("`catalog.product_vectors`", "0 — job `embed_products` của Search, tuần 2"),
            ]
        )
    )
    lines.append("")

    lines.append("### Combo: tỷ lệ map thành phần")
    lines.append("")
    lines.append(f"- Combo: **{combos['combos']}**, hạng mục: **{combos['items']}**, combo rỗng: **{combos['empty_combos']}**")
    lines.append(
        f"- Map được trên các loại map được: **{combos['mapped_mappable']:.1%}** "
        f"(tính cả `meal`/`transfer`/`other`: {combos['mapped_overall']:.1%})"
    )
    lines.append(
        "- `meal`, `transfer`, `other` luôn `item_product_id = NULL`: FK "
        "`(item_product_id, item_kind) → products (product_id, taxonomy)` không có taxonomy tương ứng."
    )
    lines.append("")
    lines.append("| item_kind | map được | tổng | tỷ lệ |")
    lines.append("|---|---|---|---|")
    for kind, stats in combos["by_kind"].items():
        lines.append(f"| `{kind}` | {stats['mapped']} | {stats['total']} | {stats['rate']:.1%} |")
    lines.append("")
    lines.append(f"- **Hàng đợi soát tay** (`item_product_id IS NULL` hoặc `confidence < {config.COMBO_REVIEW_THRESHOLD}`): **{combos['review_queue']}** dòng.")
    lines.append("")
    lines.append("```sql")
    lines.append("SELECT combo_product_id, position, label, item_kind, confidence, evidence")
    lines.append("FROM   catalog.combo_items")
    lines.append(f"WHERE  item_product_id IS NULL OR confidence < {config.COMBO_REVIEW_THRESHOLD};")
    lines.append("```")
    lines.append("")

    lines.append("### Phân bố khách")
    lines.append("")
    lines.append("| lifecycle_stage | số khách | tỷ lệ | mục tiêu |")
    lines.append("|---|---|---|---|")
    for stage, target in config.STAGE_DISTRIBUTION.items():
        count = histories["stages"].get(stage, 0)
        lines.append(f"| `{stage}` | {count} | {histories['stage_pct'].get(stage, 0)}% | {target:.0%} |")
    lines.append("")
    lines.append(f"- Event nhiều nhất trên một khách: **{histories['max_events_per_user']}** (trần {config.MAX_EVENTS_PER_USER}).")
    lines.append(
        f"- Cạnh lộn xộn cố ý: **{histories['broken_product_id']}** event `purchase` trỏ `product_id` không tồn tại, "
        f"**{histories['missing_group_id']}** event không có `event_group_id`."
    )
    lines.append(f"- Profile Insider `gdpr_optin = false`: **{insider['gdpr_opt_out']}**.")
    lines.append("")

    lines.append("### Tài khoản demo")
    lines.append("")
    lines.append(f"Mật khẩu chung: `{app['demo_password']}` (BCrypt cost {config.BCRYPT_COST}).")
    lines.append("")
    lines.append("| Persona | Email | cdp_user_id |")
    lines.append("|---|---|---|")
    for persona, uid in config.PERSONA_USER_IDS.items():
        lines.append(f"| `{persona}` | `{config.PERSONA_PROFILE[persona]['email']}` | `{uid}` |")
    lines.append(f"| 50 tài khoản test | `test01@vota.demo` … `test{config.N_TEST_USERS:02d}@vota.demo` | `VP0000005` trở đi |")
    lines.append("")
    lines.append(f"- Đơn của P1: `{app['reference_code']}`, nối sang `cdp.events` bằng `event_group_id`.")
    lines.append("")

    lines.append("### Baseline most-popular-in-destination")
    lines.append("")
    lines.append(
        f"- Recall@{baseline['k']} = **{baseline['recall']}** trên {baseline['users_evaluated']} khách "
        f"(giấu chuyến mua cuối). Mục tiêu: {baseline['range'][0]}–{baseline['range'][1]} — "
        + ("**đạt**." if baseline["in_range"] else "**chưa đạt**.")
    )
    lines.append(
        "- Gần 0 nghĩa là dữ liệu quá ngẫu nhiên (recommender hỏng trông vẫn ổn); "
        "quá cao nghĩa là baseline bất khả chiến bại, không đo được cải thiện."
    )
    if not baseline["in_range"] and baseline["recall"] > baseline["range"][1] and summary["synthetic"]:
        lines.append("")
        lines.append(
            f"> **Vượt ngưỡng trên là hệ quả của catalog tổng hợp, không phải lỗi phân bố.** "
            f"Mỗi điểm đến chỉ có khoảng {baseline.get('pool_median', '~50')} sản phẩm đặt được, nên top-{baseline['k']} "
            f"đã phủ phần lớn giỏ hàng: baseline trúng quá dễ. Catalog crawl thật (2.216 sản phẩm, 15 điểm đến) "
            "có giỏ mỗi điểm đến lớn hơn nhiều lần và con số này sẽ giảm. "
            "**Không hạ `ZIPF_S` để ép chỉ số xuống** — làm thế là bóp méo dữ liệu cho vừa thước đo. "
            "Đo lại sau khi có `products.jsonl` thật; cùng gốc nguyên nhân với hai dòng FAIL dự kiến bên dưới."
        )
    lines.append("")

    lines.append("### `db/verify.sql`")
    lines.append("")
    lines.append(
        f"Chạy bằng `SEED_DATABASE_URL` (superuser) — role `vota_app` của `DATABASE_URL` không đọc được "
        "`cdp.events`/`cdp.profiles` nên sẽ lỗi quyền chứ không ra FAIL."
    )
    lines.append("")
    lines.append("```")
    for line in verify["passed"] + verify["expected_failures"] + verify["failed"]:
        suffix = ""
        if line in verify["expected_failures"]:
            suffix = "   ← FAIL dự kiến: ngưỡng của crawl thật, catalog tổng hợp không đạt"
        lines.append(line + suffix)
    lines.append("```")
    lines.append("")
    lines.append("```")
    for line in verify_insider["passed"] + verify_insider["expected_failures"] + verify_insider["failed"]:
        lines.append(line)
    lines.append("```")
    lines.append("")
    if summary["synthetic"]:
        lines.append(
            "> Hai dòng FAIL dự kiến (`products = 2216`, `is_recommendable properties >= 300`) là ngưỡng "
            "của catalog crawl thật (2.216 sản phẩm; 316/559 property có hạng phòng đặt được). Catalog tổng hợp "
            "cố ý nhỏ hơn ~5 lần (MOCK_DATA_SPEC §1b) để chạy nhanh và đọc tay được. "
            "Có `products.jsonl` thật thì chạy lại `--reset`, cả hai tự PASS — không sửa `db/*.sql`."
        )
        lines.append("")

    lines.append("### Nguồn của từng trường")
    lines.append("")
    lines.append("| Trường | Nguồn |")
    lines.append("|---|---|")
    lines.append("| `cdp.products` 13 trường | `products.jsonl` (hoặc `products.synthetic.jsonl`), camelCase → snake_case |")
    lines.append("| `available_from/to` | cửa sổ 30 ngày từ `as_of`, cắt với khoảng nguồn; gốc giữ ở `attributes.sourceAvailableFrom/To` |")
    lines.append("| `attributes.availability` | `load_products.py` — chỉ `level=room` và `attraction`/`golf` |")
    lines.append("| `attributes.nights/minPax/priceBasis` | `load_products.py`, regex trên `name + description` |")
    lines.append("| `catalog.combo_items` | `parse_combos.py`, `source='description_parse'` + `confidence` + `evidence` |")
    lines.append("| `cdp.events` | `seed_histories.py` — chuyến theo power-law Zipf s=1.1, Vinpearl ×2 |")
    lines.append("| `cdp.profiles` | suy **từ** `cdp.events` (không sinh độc lập); tier/home_city/opt-in sinh riêng |")
    lines.append("| `app.users` | `seed_app.py`, BCrypt |")
    lines.append("| `insider.*` | `seed_insider.py`, bản sao tập con của `cdp` kèm TTL 90/730 ngày |")
    return "\n".join(lines)


def write_block(readme_path: Path, content: str) -> None:
    """Thay phần giữa hai mốc; giữ nguyên mọi thứ ngoài khối."""
    start, end = config.REPORT_MARKER_START, config.REPORT_MARKER_END
    block = f"{start}\n{content}\n{end}"
    text = readme_path.read_text(encoding="utf-8")

    if start in text and end in text:
        text = re.sub(
            re.escape(start) + r".*?" + re.escape(end), lambda _m: block, text, flags=re.DOTALL
        )
    else:
        text = text.rstrip() + "\n\n---\n\n" + block + "\n"
    readme_path.write_text(text, encoding="utf-8", newline="\n")


def print_summary(summary: dict) -> None:
    verify = summary["verify"]
    verify_insider = summary["verify_insider"]
    print()
    print("=" * 72)
    print(f"  Seed xong — as_of={summary['as_of']} seed={summary['seed']} ({summary['elapsed_seconds']}s)")
    print("=" * 72)
    print(f"  products {summary['products']['total']:>6}   combo_items {summary['combos']['items']:>5}")
    print(f"  profiles {summary['histories']['profiles']:>6}   events      {summary['histories']['events']:>5}")
    print(f"  users    {summary['app']['users']:>6}   bookings    {summary['app']['bookings']:>5}")
    print(
        f"  insider  {summary['insider']['profiles']:>6}   channel     {summary['insider']['channel_events']:>5}"
    )
    baseline = summary["baseline"]
    if baseline["in_range"]:
        note = "trong khoang muc tieu"
    elif summary["synthetic"] and baseline["recall"] > baseline["range"][1]:
        note = f"tren nguong - du kien voi catalog tong hop (~{baseline['pool_median']} san pham/diem den)"
    else:
        note = "NGOAI khoang muc tieu"
    print(f"  baseline Recall@{baseline['k']} = {baseline['recall']} ({note})")
    print("-" * 72)
    for line in verify["passed"]:
        print("  " + line)
    for line in verify["expected_failures"]:
        print("  " + line + "   <- FAIL du kien (catalog tong hop)")
    for line in verify["failed"]:
        print("  " + line + "   <- FAIL")
    print("-" * 72)
    for line in verify_insider["passed"] + verify_insider["expected_failures"] + verify_insider["failed"]:
        print("  " + line)
    print("=" * 72)
    total_failed = len(verify["failed"]) + len(verify_insider["failed"])
    if total_failed:
        print(f"  {total_failed} dòng FAIL ngoài dự kiến — xem ở trên.")
    else:
        print("  Mọi dòng PASS (trừ FAIL dự kiến của catalog tổng hợp).")
    print()
