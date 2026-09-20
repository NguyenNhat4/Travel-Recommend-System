"""CLI của bước seed.

    cd src
    python -m data_collection.seed --as-of 2026-09-20 --seed 42 --reset

Mọi thứ có ngày sinh **tương đối theo `--as-of`**: cửa sổ đặt chỗ, `attributes.availability`,
event lịch sử, chuyến sắp tới của persona. Chạy lại trước demo để cuộn cửa sổ, nếu không
toàn bộ catalog hết hạn (DATABASE_SCHEMA §1 mục 13).

`db/verify.sql` dùng `current_date` và `now()`, nên để mọi dòng có nghĩa thì `--as-of` nên là hôm nay.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import time
from pathlib import Path

from . import config, gen_products, load_products, parse_combos, report, seed_app, seed_histories, seed_insider
from .common import connect, parse_as_of, window_end

#: Thư mục `src/data_collection` — nơi chứa products.jsonl và README.
PACKAGE_ROOT = Path(__file__).resolve().parent.parent
#: Gốc repo — nơi chứa db/verify*.sql.
REPO_ROOT = PACKAGE_ROOT.parent.parent

#: Bảng do seed sở hữu. --reset chỉ xoá đúng những bảng này; carts/conversations/logs
#: sinh khi chạy app nên không đụng tới (MOCK_DATA_SPEC §1).
VOTA_TABLES = [
    "app.booking_items", "app.bookings", "app.users",
    "catalog.combo_items", "cdp.events", "cdp.profiles", "cdp.products",
]
INSIDER_TABLES = ["channel_events", "insider_events", "identifiers", "insider_profiles", "partners"]


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m data_collection.seed",
        description="Nạp catalog và sinh mock data tuần 1 cho database vota + insider.",
    )
    parser.add_argument("--as-of", default=dt.date.today().isoformat(),
                        help="Ngày nạp (YYYY-MM-DD). Mặc định hôm nay.")
    parser.add_argument("--seed", type=int, default=42, help="Seed RNG. Cùng seed → cùng dữ liệu.")
    parser.add_argument("--users", type=int, default=config.N_USERS, help="Số khách trong cdp.profiles.")
    parser.add_argument("--products", type=Path, default=None,
                        help="Đường dẫn products.jsonl. Mặc định: products.jsonl, "
                             "không có thì dùng products.synthetic.jsonl (sinh tự động).")
    parser.add_argument("--reset", action="store_true",
                        help="Xoá dữ liệu seed cũ rồi nạp lại từ đầu.")
    parser.add_argument("--allow-remote-reset", action="store_true",
                        help="Cho phép --reset trên host không phải localhost (staging chung).")
    return parser.parse_args(argv)


def _resolve_products(path: Path | None, *, seed: int, as_of: dt.date) -> tuple[Path, bool]:
    """Chọn file catalog. Chưa có crawl thì sinh bản tổng hợp (§1b) — không chặn mock."""
    if path is not None:
        if not path.exists():
            raise SystemExit(f"Không tìm thấy {path}")
        return path, False

    real = PACKAGE_ROOT / "products.jsonl"
    if real.exists():
        return real, False

    synthetic = PACKAGE_ROOT / "products.synthetic.jsonl"
    print(f"! Chưa có {real.name} từ crawler — sinh catalog tổng hợp {synthetic.name} (MOCK_DATA_SPEC §1b).")
    print("  Hai dòng db/verify.sql sẽ FAIL theo thiết kế; xem báo cáo cuối lần chạy.")
    info = gen_products.run(seed=seed, as_of=as_of, out_path=synthetic)
    print(f"  {info['total']} sản phẩm: " + ", ".join(f"{k}={v}" for k, v in sorted(info["variants"].items())))
    return synthetic, True


def _guard_remote_reset(dsn: str, allowed: bool) -> None:
    """Chặn --reset nhầm vào Postgres staging chung.

    AGENTS.md §6.3: chỉ job seed (CI hoặc một người) được reset staging, mỗi lần phải báo trong nhóm.
    """
    if allowed:
        return
    host = dsn.split("@")[-1].split("/")[0].split(":")[0] if "@" in dsn else "localhost"
    if host not in ("localhost", "127.0.0.1", "::1", "postgres"):
        raise SystemExit(
            f"--reset nhắm tới host '{host}', không phải local.\n"
            "Nếu đúng ý (staging chung), chạy lại với --allow-remote-reset và báo trong nhóm."
        )


def _reset(vota_conn, insider_conn) -> None:
    with vota_conn.cursor() as cur:
        cur.execute(f"TRUNCATE {', '.join(VOTA_TABLES)} RESTART IDENTITY CASCADE")
    vota_conn.commit()
    with insider_conn.cursor() as cur:
        cur.execute(f"TRUNCATE {', '.join(INSIDER_TABLES)} RESTART IDENTITY CASCADE")
    insider_conn.commit()


def _assert_empty(vota_conn, insider_conn) -> None:
    """Không có --reset thì các bước sinh dữ liệu phải chạy trên bảng rỗng.

    products/combo_items thì upsert được, nhưng profiles/events/users/insider thì không:
    chạy lại sẽ nhân đôi dữ liệu và làm verify sai. Báo rõ thay vì hỏng âm thầm.
    """
    checks = [(vota_conn, "cdp.profiles"), (vota_conn, "cdp.events"), (vota_conn, "app.users"),
              (insider_conn, "insider_profiles")]
    for conn, table in checks:
        with conn.cursor() as cur:
            cur.execute(f"SELECT count(*) FROM {table}")
            count = cur.fetchone()[0]
        if count:
            raise SystemExit(
                f"{table} đã có {count} dòng. Chạy lại với --reset để xoá và nạp lại, "
                "hoặc dùng database trống."
            )


def main(argv=None) -> int:
    args = _parse_args(argv)
    as_of = parse_as_of(args.as_of)
    started = time.monotonic()

    products_path, synthetic = _resolve_products(args.products, seed=args.seed, as_of=as_of)

    vota_conn = connect(config.SEED_DATABASE_URL)
    insider_conn = connect(config.INSIDER_DATABASE_URL)
    try:
        if args.reset:
            _guard_remote_reset(config.SEED_DATABASE_URL, args.allow_remote_reset)
            _guard_remote_reset(config.INSIDER_DATABASE_URL, args.allow_remote_reset)
            _reset(vota_conn, insider_conn)
        else:
            _assert_empty(vota_conn, insider_conn)

        print("1/6 load_products")
        products_info = load_products.run(
            vota_conn, products_path=products_path, as_of=as_of, seed=args.seed
        )

        print("2/6 parse_combos")
        combos_info = parse_combos.run(vota_conn)

        # Persona dựng trước: seed_histories phải chừa VP0000001..4 và dùng đúng lịch sử này.
        pool = seed_histories.load_pool(vota_conn)
        persona_events, upcoming = seed_app.build_persona_events(args.seed, as_of, pool)

        print("3/6 seed_histories")
        histories_info = seed_histories.run(
            vota_conn, seed=args.seed, as_of=as_of, n_users=args.users,
            reserved=persona_events, pool=pool,
        )

        print("4/6 seed_app")
        app_info = seed_app.run(vota_conn, seed=args.seed, as_of=as_of, upcoming=upcoming)

        print("5/6 seed_insider")
        insider_info = seed_insider.run(vota_conn, insider_conn, seed=args.seed, as_of=as_of)

        print("6/6 report")
        verify = report.classify(
            report.run_verify(vota_conn, REPO_ROOT / "db" / "verify.sql"), synthetic=synthetic
        )
        verify_insider = report.classify(
            report.run_verify(insider_conn, REPO_ROOT / "db" / "verify_insider.sql"), synthetic=False
        )
        baseline = report.baseline_recall(vota_conn)

        summary = {
            "as_of": as_of.isoformat(),
            "seed": args.seed,
            "window": [as_of.isoformat(), window_end(as_of).isoformat()],
            "products_path": products_path.name,
            "synthetic": synthetic,
            "elapsed_seconds": round(time.monotonic() - started, 1),
            "products": products_info,
            "combos": combos_info,
            "histories": histories_info,
            "app": app_info,
            "insider": insider_info,
            "verify": verify,
            "verify_insider": verify_insider,
            "baseline": baseline,
        }
        report.write_block(PACKAGE_ROOT / "README.md", report.render(summary))
        report.print_summary(summary)

        # Exit code khác 0 khi có FAIL ngoài dự kiến, để CI bắt được.
        return 1 if (verify["failed"] or verify_insider["failed"]) else 0
    finally:
        vota_conn.close()
        insider_conn.close()


if __name__ == "__main__":
    sys.exit(main())
