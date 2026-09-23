import json
import contextlib
import io
import os
import shlex
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import batch
import catalog
from collectors.common import HostRateLimiter, Paths, RunLock


class BatchTests(unittest.TestCase):
    def test_city_default_plans_all_sources_without_taxonomy(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(batch.main(["run", "--cities", "Hà Nội", "--origins", "SGN", "--dates", "2027-01-15",
                                         "--root", tmp, "--dry-run"]), 0)
        commands = [shlex.split(line) for line in output.getvalue().splitlines() if "crawl.py --data-dir" in line]
        self.assertEqual(len(commands), 6)  # 5 nguồn + job khách sạn thương hiệu Vinpearl dùng chung trên Booking
        self.assertEqual({cmd[4] for cmd in commands}, set(batch.CITY_SOURCES))
        self.assertNotIn("booking-flights", {cmd[4] for cmd in commands})  # opt-in: Booking trả rỗng cho phiên tự động
        brand = [cmd for cmd in commands if cmd[4] == "booking-hotels" and "--brand-only" in cmd]
        self.assertEqual(len(brand), 1)
        vp = next(cmd for cmd in commands if cmd[4] == "vinpearl")
        self.assertNotIn("--skip-hotels", vp)
        for cmd in commands:
            if cmd[4] in ("trip-flights", "trip-attractions"):
                self.assertNotIn("--depart-dates", cmd)
        self.assertEqual(batch.select_sources(taxonomy="hotel"), ("booking-hotels", "agoda-hotels"))
        self.assertEqual(batch.select_sources(taxonomy="flight"), ("trip-flights",))
        self.assertEqual(batch.select_sources("booking-flights"), ("booking-flights",))  # vẫn chọn được khi chủ động
        with self.assertRaises(ValueError):
            batch.select_sources("trip-flights", "hotel")

    def test_city_export_keeps_taxonomies_together_and_ids(self):
        hotel = dict.fromkeys(catalog.FIELDS)
        hotel.update(productId="hotel", name="Hotel", destination="Hà Nội", taxonomy="hotel", attributes={}, available=False)
        attraction = dict(hotel, productId="attraction", taxonomy="attraction")
        second = dict(hotel, productId="other-city", destination="Đà Nẵng")
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder / "products.json"
            source.write_text(json.dumps([hotel, attraction, second]))
            index = catalog.city_catalogs(source, folder / "cities")
            self.assertEqual(len(index), 2)
            hanoi = json.loads((folder / "cities/ha-noi.json").read_text())
            self.assertEqual({r["productId"] for r in hanoi}, {"hotel", "attraction"})
            self.assertTrue(all(set(r) == catalog.FIELDS for r in hanoi))

    def test_trip_missing_service_retained_with_original_observed_at(self):
        from normalise import trip_route_history
        rows = [{"key": "a", "crawledAt": "2026-09-18T01:00:00Z", "flights": [
            {"flightNumber": "VN1", "price": 100}, {"flightNumber": "VN2", "price": 200}]},
            {"key": "a", "crawledAt": "2026-09-19T01:00:00Z", "flights": [{"flightNumber": "VN1", "price": 300}]}]
        flights = {f["flightNumber"]: f for f in trip_route_history(rows)[0]["flights"]}
        self.assertEqual(flights["VN1"]["price"], 300)
        self.assertFalse(flights["VN1"]["notInLatestSnapshot"])
        self.assertTrue(flights["VN2"]["notInLatestSnapshot"])
        self.assertEqual(flights["VN2"]["observedAt"], rows[0]["crawledAt"])

    def test_availability_dates_come_from_quotes_not_crawl_time(self):
        from normalise import price_evidence
        record = {"crawledAt": "2026-09-19T01:00:00Z", "priceQuery": {"dates": ["2026-10-01", "2026-10-15"]}}
        evidence, available_from, available_to = price_evidence(record, {"2026-10-01": 1000000, "2026-10-15": 1200000})
        self.assertEqual(evidence["availabilityDatesObserved"], ["2026-10-01", "2026-10-15"])
        self.assertEqual(evidence["priceObservedAt"], record["crawledAt"])
        self.assertNotIn("availableFrom", evidence)
        self.assertNotIn("availableTo", evidence)
        # chỉ 2 ngày mẫu rời rạc (không phải --calendar-days dày đặc) → không được bịa khoảng available
        self.assertIsNone(available_from)
        self.assertIsNone(available_to)

    def test_dense_calendar_sweep_gives_a_real_available_window(self):
        from normalise import price_evidence
        dates = [f"2026-10-{d:02d}" for d in range(1, 31)]  # 30 ngày liên tiếp, kiểu --calendar-days 30
        record = {"crawledAt": "2026-09-19T01:00:00Z", "priceQuery": {"dates": dates}}
        evidence, available_from, available_to = price_evidence(record, {"2026-10-01": 1000000})
        self.assertEqual((available_from, available_to), ("2026-10-01", "2026-10-30"))

    def test_single_night_query_gives_checkin_checkout_as_window(self):
        from normalise import price_evidence
        record = {"crawledAt": "2026-09-19T01:00:00Z", "priceQuery": {"checkin": "2026-10-15", "checkout": "2026-10-16"}}
        evidence, available_from, available_to = price_evidence(record)
        self.assertEqual((available_from, available_to), ("2026-10-15", "2026-10-16"))

    def test_one_city_flights_have_inbound_routes(self):
        jobs, skipped = batch.plan_jobs("booking-flights", "Hà Nội", dates="2027-01-15", origins="SGN,DAD")
        self.assertEqual(len(jobs), 1)  # một job cho mọi tuyến tới HAN, không phải mỗi tuyến một tiến trình
        self.assertEqual(set(jobs[0]["route"].split(",")), {"SGN-HAN", "DAD-HAN"})
        self.assertFalse(skipped)

    def test_flight_jobs_group_by_target_airport_over_all_origins(self):
        for source in ("trip-flights", "booking-flights"):
            jobs, _ = batch.plan_jobs(source, "Hà Nội,Đà Nẵng")
            self.assertEqual({j["city"] for j in jobs}, {"Hà Nội", "Đà Nẵng"})
            self.assertEqual(len(jobs), 2)
            for job in jobs:
                routes = job["route"].split(",")
                self.assertGreater(len(routes), 5)
                self.assertEqual(len({r.split("-")[1] for r in routes}), 1)  # cùng một sân bay đến
                self.assertEqual(job["args"][:2], ["--routes", job["route"]])

    def test_default_hotels_one_query_date_per_city(self):
        jobs, _ = batch.plan_jobs("booking-hotels", "Hà Nội,Đà Nẵng")
        cities = [j for j in jobs if j["city"] != "all"]
        brand = [j for j in jobs if j["city"] == "all"]
        self.assertEqual(len(cities), 2)
        self.assertTrue(all("--checkin" in j["args"] and "--no-brand-sitemap" in j["args"] for j in cities))
        self.assertEqual(len(brand), 1)  # sitemap thương hiệu Vinpearl: một job toàn quốc
        self.assertIn("--brand-only", brand[0]["args"])
        self.assertTrue(brand[0]["once"])

    def test_no_empty_jobs_for_destinations_without_verified_source_ids(self):
        jobs, skipped = batch.plan_jobs("agoda-hotels", "Hà Nội,Pleiku,Tuy Hòa")  # Pleiku, Tuy Hòa chưa có slug Agoda
        self.assertEqual([j["city"] for j in jobs], ["Hà Nội"])
        self.assertEqual(len(skipped), 2)
        jobs, skipped = batch.plan_jobs("trip-attractions", "Hà Nội,Hội An,Ninh Bình")  # Hội An, Ninh Bình chưa có ID Trip
        self.assertEqual([j["city"] for j in jobs], ["Hà Nội"])
        self.assertTrue(all("chưa có" in m for m in skipped))
        jobs, _ = batch.plan_jobs("booking-hotels", "Hội An,Ninh Bình")  # Booking chỉ cần tên tìm kiếm
        self.assertEqual({j["city"] for j in jobs}, {"all", "Hội An", "Ninh Bình"})

    def test_jsonl_with_unicode_line_separators_inside_strings_is_read_intact(self):
        # U+0085 / U+2028 hợp lệ trong chuỗi JSON nhưng str.splitlines() coi là xuống dòng (làm merge và catalog.py vỡ)
        tricky = {"key": "hotel:1", "crawledAt": "2026-09-19T00:00:00Z", "description": "dòng một\x85dòng hai\u2028dòng ba"}
        with tempfile.TemporaryDirectory() as tmp:
            job = Paths(Path(tmp) / "job").ensure()
            (job.interim / "booking_hotels.jsonl").write_text(json.dumps(tricky, ensure_ascii=False) + "\n", encoding="utf-8")
            dest = Path(tmp) / "main"
            self.assertEqual(batch.merge_interim([job.data], dest), 1)
            self.assertEqual(batch.merge_interim([job.data], dest), 0)  # nhập lại không nhân bản
            text = (dest / "interim/booking_hotels.jsonl").read_text(encoding="utf-8")
            self.assertEqual(json.loads(text.strip())["description"], tricky["description"])
            self.assertEqual(text.count("\n"), 1)  # không sinh dòng trống
            row = dict.fromkeys(catalog.FIELDS)
            row.update(productId="one", taxonomy="hotel", attributes={}, name="H", destination="X", available=False,
                       description=tricky["description"])
            source = Path(tmp) / "products.jsonl"
            source.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
            catalog.split_catalog(source, Path(tmp) / "tables")
            self.assertEqual(catalog.merge_catalog(Path(tmp) / "tables", Path(tmp) / "products.json"), 1)

    def test_shared_once_job_is_skipped_after_clean_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.assertFalse(batch.job_finished(folder))
            (folder / "last-run.json").write_text(json.dumps({"exitCode": 75}))
            self.assertFalse(batch.job_finished(folder))
            (folder / "last-run.json").write_text(json.dumps({"exitCode": 0}))
            self.assertTrue(batch.job_finished(folder))

    def test_shards_disjoint_complete_and_stable(self):
        jobs, _ = batch.plan_jobs("booking-flights", "Hà Nội,Đà Nẵng", months="2027-01,2027-02")
        shards = [{batch.job_id(j) for j in batch.shard_jobs(jobs, f"{i}/3")} for i in (1, 2, 3)]
        self.assertFalse(shards[0] & shards[1] or shards[0] & shards[2] or shards[1] & shards[2])
        self.assertEqual(set.union(*shards), {batch.job_id(j) for j in jobs})
        subset, _ = batch.plan_jobs("booking-flights", "Hà Nội", months="2027-01,2027-02")
        self.assertTrue({batch.job_id(j) for j in batch.shard_jobs(subset, "1/3")} <= shards[0])

    def test_no_airport_not_invented_and_month_year_explicit(self):
        jobs, skipped = batch.plan_jobs("booking-flights", "Hội An")
        self.assertFalse(jobs)
        self.assertTrue(skipped)
        self.assertEqual(batch.month_values("1,2", 2027), "2027-01,2027-02")
        with self.assertRaises(ValueError):
            batch.month_values("1,2")

    def test_shared_rate_reservations_across_instances(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"CRAWL_RATE_DB": tmp + "/rate.db"}):
            a, b = HostRateLimiter(4), HostRateLimiter(4)
            start = a.reserve_shared("example.test", 4)
            end = b.reserve_shared("example.test", 4)
            self.assertGreaterEqual(end - start, 4)
            b.penalise("example.test", 30)
            self.assertGreater(a.reserve_shared("example.test", 4) - end, 20)

    def test_import_is_idempotent_preserves_raw_and_refuses_busy_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            job = Paths(Path(tmp) / "job").ensure()
            dest = Path(tmp) / "main"
            file = job.interim / "trip_flights.jsonl"
            file.write_text(json.dumps({"key": "route", "crawledAt": "2026-09-19T00:00:00Z"}) + "\n")
            self.assertEqual(batch.merge_interim([job.data], dest), 1)
            self.assertEqual(batch.merge_interim([job.data], dest), 0)
            with RunLock(job, "trip_flights"), self.assertRaises(SystemExit):
                batch.merge_interim([job.data], dest)
            row = json.loads((dest / "interim/trip_flights.jsonl").read_text())
            self.assertEqual(row["rawArchive"], str(job.raw))

    def test_catalog_roundtrip_and_conflict_rejected(self):
        row = dict.fromkeys(catalog.FIELDS)
        row.update(productId="one", taxonomy="hotel", attributes={}, name="Hotel", destination="Hà Nội", available=False)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder / "source.jsonl"
            source.write_text(json.dumps(row) + "\n")
            catalog.split_catalog(source, folder / "tables")
            output = folder / "products.json"
            self.assertEqual(catalog.merge_catalog(folder / "tables", output), 1)
            self.assertEqual(json.loads(output.read_text()), [row])
            changed = dict(row, name="Changed")
            (folder / "tables/hotel.json").write_text(json.dumps([row, changed]))
            with self.assertRaises(ValueError):
                catalog.merge_catalog(folder / "tables", output)
            self.assertEqual(json.loads(output.read_text()), [row])


if __name__ == "__main__":
    unittest.main()
