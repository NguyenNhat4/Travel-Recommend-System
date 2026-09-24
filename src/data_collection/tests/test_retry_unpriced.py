import json
import tempfile
import unittest
from pathlib import Path

import retry_unpriced as ru


def make_job(root: Path, job: str, spec: dict, records: list[dict]) -> None:
    folder = root / job
    (folder / "interim").mkdir(parents=True)
    (folder / "job.json").write_text(json.dumps(spec), encoding="utf-8")
    source = spec["source"].replace("-", "_")
    (folder / "interim" / f"{source}.jsonl").write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


def booking(key, price, crawled="2026-09-19T01:00:00Z"):
    return {"recordType": "booking_hotel", "key": key, "url": f"https://www.booking.com/hotel/vn/{key}.vi.html",
            "minPrice": price, "crawledAt": crawled, "priceQuery": {"checkin": "2026-10-15"}}


SPEC = {"source": "booking-hotels", "city": "Hà Nội", "period": "2026-10-15",
        "args": ["--destinations", "Hà Nội", "--per-destination", "100", "--no-brand-sitemap",
                 "--checkin", "2026-10-15", "--nights", "1", "--adults", "2"]}


class RetryUnpricedTests(unittest.TestCase):
    def test_only_unpriced_latest_records_are_retried_with_shifted_dates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_job(root, "a" * 20, SPEC, [booking("has-price", 500000), booking("no-price", None),
                                            booking("later-priced", None, "2026-09-19T01:00:00Z"),
                                            booking("later-priced", 900000, "2026-09-19T02:00:00Z")])
            groups = ru.find_unpriced(root)
            self.assertEqual(len(groups), 1)
            (group,) = groups.values()
            self.assertEqual(group["urls"], ["https://www.booking.com/hotel/vn/no-price.vi.html"])  # bản mới hơn có giá thì thôi
            spec = ru.retry_spec(group, "booking-hotels", 14)
            self.assertEqual(spec["args"][spec["args"].index("--checkin") + 1], "2026-10-29")
            self.assertEqual(spec["args"].count("--checkin"), 1)  # không nhân đôi tham số ngày cũ
            self.assertIn("--no-brand-sitemap", spec["args"])
            self.assertEqual(spec["args"][spec["args"].index("--per-destination") + 1], "100")  # cùng cách tìm URL như job gốc
            match = spec["args"][spec["args"].index("--match") + 1]
            self.assertIn(r"no\-price", match.replace("\\-", r"\-"))
            self.assertEqual(spec["retryOf"], "2026-10-15")
            self.assertEqual(ru.retry_spec(group, "booking-hotels", 45)["args"][spec["args"].index("--checkin") + 1], "2026-11-29")

    def test_second_pass_only_covers_what_the_first_pass_left_unpriced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_job(root, "a" * 20, SPEC, [booking("x", None), booking("y", None)])
            first = ru.plan_pass(root, 14)
            self.assertEqual(len(first), 1)
            retry = dict(first[0])
            make_job(root, "b" * 20, retry, [booking("x", 700000, "2026-09-20T00:00:00Z"),
                                              booking("y", None, "2026-09-20T00:00:00Z")])
            (second,) = ru.plan_pass(root, 45)
            urls = second["args"][second["args"].index("--match") + 1]
            self.assertIn("y", urls)
            self.assertNotIn("/x.", urls)

    def test_nothing_to_retry_when_everything_has_a_price(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_job(root, "a" * 20, SPEC, [booking("x", 1), booking("y", 2)])
            self.assertEqual(ru.plan_pass(root, 14), [])

    def test_dry_run_prints_plan_and_touches_nothing(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_job(root, "a" * 20, SPEC, [booking("x", None)])
            before = sorted(p.name for p in root.rglob("*"))
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(ru.main(["--root", str(root)]), 0)
            self.assertIn("1 khách sạn chưa có giá", out.getvalue())
            self.assertEqual(before, sorted(p.name for p in root.rglob("*")))


if __name__ == "__main__":
    unittest.main()
