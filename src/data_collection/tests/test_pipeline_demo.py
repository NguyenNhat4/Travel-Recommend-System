"""Hồi quy cho pipeline_demo.py, apify_source.py và các route /pipeline của monitor.py.

Không gọi mạng thật, không cần Postgres: Apify được thay bằng server giả chạy trên 127.0.0.1; phần chạy trọn luồng (--no-db) dùng
một lát dữ liệu thô thật nếu có trong data/interim (không có thì bỏ qua)."""
import contextlib
import io
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

import apify_source as ap
import monitor
import pipeline_demo as pd

REAL_INTERIM = Path(__file__).resolve().parents[1] / "data" / "interim"


def write_jsonl(path: Path, records: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")


class Guardrails(unittest.TestCase):
    def test_db_target_accepts_local_demo_database(self):
        pd.check_db_target("127.0.0.1", 5432, "vota_demo")
        pd.check_db_target("127.0.0.1", 55432, "vota_demo")
        pd.check_db_target("localhost", 55439, "vota_demo_2")

    def test_db_target_refuses_remote_host_and_non_demo_names(self):
        for host, port, name in (("db.example.com", 55432, "vota_demo"), ("127.0.0.1", 55432, "vota"),
                                 ("127.0.0.1", 55432, "insider"), ("127.0.0.1", 55432, "vota_demo; DROP DATABASE vota"),
                                 ("127.0.0.1", 55432, "VOTA_DEMO")):
            with self.subTest(host=host, port=port, name=name), self.assertRaises(pd.GuardrailError):
                pd.check_db_target(host, port, name)

    def test_run_dir_must_be_direct_child_of_runs_with_valid_name(self):
        with tempfile.TemporaryDirectory() as t:
            demo = Path(t) / "demo"
            pd.check_run_dir(demo / "runs" / "20260921-101500", demo)
            pd.check_run_dir(demo / "runs" / "20260921-101500-t1", demo)
            for bad in (demo / "runs" / "..", demo / "products", demo / "runs" / "x" / "20260921-101500", demo / "runs" / "abc",
                        Path(t) / "20260921-101500"):
                with self.subTest(bad=str(bad)), self.assertRaises(pd.GuardrailError):
                    pd.check_run_dir(bad, demo)

    def test_run_refuses_non_demo_database_before_creating_anything(self):
        with tempfile.TemporaryDirectory() as t, mock.patch.dict(os.environ, {"VOTA_DATA_DIR": t}):
            self.assertEqual(pd.main(["run", "--db-name", "vota", "--run-id", "20260921-101500"]), 2)
            self.assertFalse((Path(t) / "demo" / "runs").exists())

    def test_prune_keeps_newest_and_only_touches_valid_run_dirs(self):
        with tempfile.TemporaryDirectory() as t:
            demo = Path(t)
            names = [f"20260921-10150{i}" for i in range(8)]
            for n in names + ["keep-me-not-a-run"]:
                (demo / "runs" / n).mkdir(parents=True)
            pd.prune_runs(demo, keep=3)
            left = sorted(p.name for p in (demo / "runs").iterdir())
            self.assertEqual(left, ["20260921-101505", "20260921-101506", "20260921-101507", "keep-me-not-a-run"])

    def test_lock_refuses_second_live_run(self):
        with tempfile.TemporaryDirectory() as t:
            demo = Path(t)
            (demo).mkdir(exist_ok=True)
            (demo / "run.lock").write_text(str(os.getppid()))  # tiến trình cha còn sống, khác pid hiện tại
            with self.assertRaises(pd.GuardrailError):
                pd.acquire_lock(demo)
            (demo / "run.lock").write_text("999999999")  # pid không tồn tại: khoá cũ, được ghi đè
            self.assertEqual(pd.acquire_lock(demo).read_text(), str(os.getpid()))


class Selection(unittest.TestCase):
    def fixture(self, root: Path) -> None:
        i = root / "interim"
        write_jsonl(i / "booking_hotels.jsonl", [{"name": f"B{n}", "city": "Nha Trang"} for n in range(6)] + [{"name": "Bhn", "city": "Hà Nội"}])
        write_jsonl(i / "agoda_hotels.jsonl", [{"name": f"A{n}", "plan": {"destination": "Nha Trang"}} for n in range(4)]
                    + [{"name": "Ahn", "plan": {"destination": "Hà Nội"}}])
        write_jsonl(i / "trip_attractions.jsonl", [{"name": "T1", "plan": {"destination": "Nha Trang"}}, {"name": "T2", "plan": {"destination": "Hà Nội"}}])
        write_jsonl(i / "trip_flights.jsonl", [{"fromCity": "Hà Nội", "toCity": "Nha Trang"}, {"fromCity": "Hà Nội", "toCity": "Đà Nẵng"}])
        write_jsonl(i / "vinpearl.jsonl", [{"recordType": "vinpearl_hotel", "name": "V1"}, {"recordType": "vinpearl_tour", "name": "V2"}])

    def test_no_filter_keeps_everything(self):
        with tempfile.TemporaryDirectory() as t:
            self.fixture(Path(t))
            sel = pd.select_feeds(Path(t), [], None)
            self.assertEqual({k: len(v) for k, v in sel.items()},
                             {"vinpearl_hotels": 1, "vinpearl_tours": 1, "booking_hotels": 7, "agoda_hotels": 5, "trip_attractions": 2, "trip_flights": 2,
                              "api_agoda": 0, "api_booking": 0})

    def test_destination_filter_keeps_vinpearl_always_and_matches_flight_endpoints(self):
        with tempfile.TemporaryDirectory() as t:
            self.fixture(Path(t))
            sel = pd.select_feeds(Path(t), ["nha trang"], None)  # không phân biệt hoa thường
            self.assertEqual({k: len(v) for k, v in sel.items()},
                             {"vinpearl_hotels": 1, "vinpearl_tours": 1, "booking_hotels": 6, "agoda_hotels": 4, "trip_attractions": 1, "trip_flights": 1,
                              "api_agoda": 0, "api_booking": 0})

    def test_half_written_last_line_is_skipped(self):
        with tempfile.TemporaryDirectory() as t:
            self.fixture(Path(t))
            p = Path(t) / "interim" / "booking_hotels.jsonl"
            p.write_text(p.read_text(encoding="utf-8") + '{"name": "dang-ghi-do', encoding="utf-8")
            self.assertEqual(len(pd.select_feeds(Path(t), [], None)["booking_hotels"]), 7)

    def test_cap_hotels_spreads_across_destinations_and_interleaves_sources(self):
        def recs(dest, n):
            return [(json.dumps({"city": dest, "n": i}), {"city": dest}) for i in range(n)]
        parsed = {"booking_hotels": recs("X", 10) + recs("Y", 2), "agoda_hotels": recs("X", 10) + recs("Z", 1)}
        pd.cap_hotels(parsed, 6)
        chosen = [r["city"] for s in parsed for _, r in parsed[s]]
        self.assertEqual(len(chosen), 6)
        self.assertEqual({d: chosen.count(d) for d in "XYZ"}, {"X": 3, "Y": 2, "Z": 1})
        self.assertTrue(any(r["city"] == "X" for _, r in parsed["booking_hotels"]) and any(r["city"] == "X" for _, r in parsed["agoda_hotels"]))

    def test_cap_hotels_is_deterministic_and_handles_small_input(self):
        def build():
            return {"booking_hotels": [(str(i), {"city": "A" if i % 2 else "B"}) for i in range(9)], "agoda_hotels": []}
        a, b = build(), build()
        pd.cap_hotels(a, 4)
        pd.cap_hotels(b, 4)
        self.assertEqual(a, b)
        c = build()
        pd.cap_hotels(c, 100)  # cap lớn hơn dữ liệu: giữ hết
        self.assertEqual(len(c["booking_hotels"]), 9)


class State(unittest.TestCase):
    def test_state_file_is_valid_json_after_every_change_and_log_is_trimmed(self):
        with tempfile.TemporaryDirectory() as t:
            st = pd.RunState(Path(t) / "20260921-101500", {"x": 1})
            st.start("ingest")
            with contextlib.redirect_stdout(io.StringIO()):  # RunState.log cũng in ra màn hình
                for i in range(pd.LOG_KEEP + 30):
                    st.log(f"dòng {i}")
            st.done("ingest", received=5)
            data = json.loads(st.path.read_text(encoding="utf-8"))
            self.assertEqual(len(data["log"]), pd.LOG_KEEP)
            self.assertEqual(data["log"][-1].split(" ", 1)[1], f"dòng {pd.LOG_KEEP + 29}")
            ingest = next(s for s in data["stages"] if s["id"] == "ingest")
            self.assertEqual((ingest["status"], ingest["metrics"]["received"]), ("done", 5))
            self.assertFalse(list(Path(t).rglob("*.tmp")), "file tạm phải được đổi tên, không để lại")

    def test_failed_stage_shows_error_and_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as t:
            st = pd.RunState(Path(t) / "20260921-101500", {})

            def boom(state):
                raise ValueError("hỏng")
            self.assertFalse(pd.run_stage(st, "normalise", boom))
            s = st.stage("normalise")
            self.assertEqual((s["status"], s["metrics"]["error"]), ("failed", "ValueError: hỏng"))

    def test_compare_frozen_tolerates_unreadable_reference_and_reports_identity(self):
        with tempfile.TemporaryDirectory() as t:
            a, b = Path(t) / "a.jsonl", Path(t) / "b.jsonl"
            a.write_text('{"productId": "1", "n": 1}\n{"productId": "2", "n": 2}\n', encoding="utf-8")
            b.write_text('{"productId": "1", "n": 1}\n{"productId": "3", "n": 3}\n', encoding="utf-8")
            c = pd.compare_frozen(a, b)
            self.assertEqual((c["common"], c["identicalRows"], c["onlyInRun"], c["onlyInFrozen"], c["sameSha256"]), (1, 1, 1, 1, False))
            self.assertTrue(pd.compare_frozen(a, a)["sameSha256"])
            b.write_text("không phải json\n", encoding="utf-8")
            self.assertIsNone(pd.compare_frozen(a, b))
            self.assertIsNone(pd.compare_frozen(a, Path(t) / "khong-co.jsonl"))

    def test_helpers(self):
        self.assertEqual(pd.trim("x" * 500, max_str=10), "x" * 9 + "…")
        self.assertEqual(pd.trim([1, 2, 3, 4, 5, 6], max_list=2), [1, 2, "… +4 mục"])
        rows = [{"taxonomy": "hotel", "description": "d", "unitPrice": 1, "imageUrl": None, "attributes": {"level": "room", "latitude": 1, "longitude": 2}},
                {"taxonomy": "hotel", "description": "", "unitPrice": None, "imageUrl": "u", "attributes": {"level": "room"}}]
        cov = pd.coverage_of(rows)["hotel/room"]
        self.assertEqual((cov["rows"], cov["fields"]["description"], cov["fields"]["unitPrice"], cov["fields"]["toạ độ"]), (2, 50, 50, 50))
        self.assertEqual(pd.composition_of(rows), {"hotel/room": 2})


class FakeApify(BaseHTTPRequestHandler):
    calls: list = []
    mode = "ok"
    token = "tok-SECRET-123"

    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth(self, body=b""):
        FakeApify.calls.append((self.command, self.path, dict(self.headers), body))
        if self.headers.get("Authorization") != f"Bearer {FakeApify.token}":
            self._send(401, {"error": {"type": "user-or-token-not-found", "message": "token không đúng"}})
            return False
        return True

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if not self._auth(body):
            return
        if self.path.startswith("/acts/"):
            return self._send(201, {"data": {"id": "RUN1", "status": "RUNNING", "defaultDatasetId": "DS1"}})
        if self.path.startswith("/actor-runs/RUN1/abort"):
            return self._send(200, {"data": {"status": "ABORTED"}})
        self._send(404, {})

    def do_GET(self):
        if not self._auth():
            return
        if self.path.startswith("/actor-runs/RUN1"):
            status = "RUNNING" if FakeApify.mode == "hang" else ("FAILED" if FakeApify.mode == "fail" else "SUCCEEDED")
            return self._send(200, {"data": {"id": "RUN1", "status": status, "defaultDatasetId": "DS1", "usageTotalUsd": 0.0123,
                                             "statusMessage": "hết credit" if status == "FAILED" else ""}})
        if self.path.startswith("/datasets/DS1/items"):
            return self._send(200, [{"name": "A", "price": 10, "lat": None}, {"name": "B", "price": None, "lat": 1.5}])
        self._send(404, {})


class ApifyClient(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeApify)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        FakeApify.calls, FakeApify.mode = [], "ok"
        self.client = ap.Apify(FakeApify.token, base=self.base, timeout=5)

    def test_run_sends_bearer_token_budget_cap_and_returns_items_and_cost(self):
        res = self.client.run_and_collect("user/actor-name", {"destinations": ["Nha Trang"]}, max_items=5, max_usd=0.5, wait_timeout_s=30)
        self.assertEqual(len(res["items"]), 2)
        self.assertEqual(res["costUsd"], 0.0123)
        method, path, headers, body = FakeApify.calls[0]
        self.assertEqual((method, path.split("?")[0]), ("POST", "/acts/user~actor-name/runs"))
        self.assertIn("maxTotalChargeUsd=0.5", path)
        self.assertIn("maxItems=5", path)
        self.assertEqual(json.loads(body), {"destinations": ["Nha Trang"]})
        self.assertTrue(all(c[2].get("Authorization") == f"Bearer {FakeApify.token}" for c in FakeApify.calls))
        self.assertFalse(any(FakeApify.token in c[1] for c in FakeApify.calls), "token không được nằm trên URL")

    def test_wrong_token_error_never_contains_the_token(self):
        bad = ap.Apify("tok-WRONG-999", base=self.base, timeout=5)
        with self.assertRaises(ap.ApifyError) as cm:
            bad.run_and_collect("user/actor", {}, max_items=1, max_usd=0.1)
        self.assertIn("401", str(cm.exception))
        self.assertNotIn("tok-WRONG-999", str(cm.exception))

    def test_unreachable_server_error_never_contains_the_token(self):
        dead = ap.Apify("tok-DEAD-1", base="http://127.0.0.1:9", timeout=2)
        with self.assertRaises(ap.ApifyError) as cm:
            dead.start_run("user/actor", {})
        self.assertNotIn("tok-DEAD-1", str(cm.exception))

    def test_failed_run_reports_status_message(self):
        FakeApify.mode = "fail"
        with self.assertRaisesRegex(ap.ApifyError, "FAILED.*hết credit"):
            self.client.run_and_collect("user/actor", {}, max_items=1, max_usd=0.1, wait_timeout_s=30)

    def test_run_that_never_finishes_is_aborted(self):
        FakeApify.mode = "hang"
        with self.assertRaisesRegex(ap.ApifyError, "đã huỷ"):
            self.client.run_and_collect("user/actor", {}, max_items=1, max_usd=0.1, wait_timeout_s=1)
        self.assertTrue(any(c[0] == "POST" and c[1].startswith("/actor-runs/RUN1/abort") for c in FakeApify.calls))

    def test_probe_saves_raw_json_and_reports_fields(self):
        with tempfile.TemporaryDirectory() as t:
            res = ap.probe("user/actor", {"q": 1}, limit=2, max_usd=0.1, out_dir=Path(t), client=self.client)
            saved = json.loads(res["path"].read_text(encoding="utf-8"))
            self.assertEqual((saved["actor"], len(saved["items"]), saved["costUsd"]), ("user/actor", 2, 0.0123))
            fields = {f["key"]: f for f in res["fields"]}
            self.assertEqual((fields["name"]["filledPct"], fields["price"]["filledPct"], fields["lat"]["filledPct"]), (100, 50, 50))

    def test_probe_refuses_large_limit_or_budget(self):
        for kwargs in ({"limit": 0, "max_usd": 0.1}, {"limit": 101, "max_usd": 0.1}, {"limit": 5, "max_usd": 0}, {"limit": 5, "max_usd": 50}):
            with self.subTest(**kwargs), self.assertRaises(ap.ApifyError):
                ap.probe("user/actor", {}, out_dir=Path("."), client=self.client, **kwargs)

    def test_actor_path(self):
        self.assertEqual(ap.actor_path("makework36/fast-booking-scraper"), "makework36~fast-booking-scraper")
        for bad in ("", "a b", "a/b/c"):
            with self.subTest(bad=bad), self.assertRaises(ap.ApifyError):
                ap.actor_path(bad)


class EnvFile(unittest.TestCase):
    def test_load_env_sets_missing_only_and_strips_quotes_and_comments(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / ".env"
            p.write_text("# ghi chú\nAPIFY_TOKEN='abc'\nKEEP=from-file\nBAD LINE\n\nEMPTY=\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"KEEP": "from-env"}, clear=False):
                os.environ.pop("APIFY_TOKEN", None)
                ap.load_env(p)
                self.assertEqual((os.environ["APIFY_TOKEN"], os.environ["KEEP"]), ("abc", "from-env"))
                os.environ.pop("APIFY_TOKEN", None)
                os.environ.pop("EMPTY", None)

    def test_missing_token_gives_actionable_message(self):
        with mock.patch.dict(os.environ, {}, clear=False), mock.patch.object(ap, "load_env"):
            os.environ.pop("APIFY_TOKEN", None)
            with self.assertRaisesRegex(ap.ApifyError, r"\.env.*API & Integrations"):
                ap.get_token()


class MonitorRoutes(unittest.TestCase):
    def test_state_empty_then_returns_written_state_and_marks_dead_process(self):
        with tempfile.TemporaryDirectory() as t:
            m = monitor.Monitor(Path(t))
            self.assertEqual(m.pipeline_state("latest"), {"empty": True})
            run = Path(t) / "demo" / "runs" / "20260921-101500"
            run.mkdir(parents=True)
            (run / "state.json").write_text(json.dumps({"runId": run.name, "status": "running", "pid": 999999999}), encoding="utf-8")
            (Path(t) / "demo" / "latest.txt").write_text(run.name, encoding="utf-8")
            st = m.pipeline_state("latest")
            self.assertEqual((st["status"], st.get("stale")), ("stopped", True))
            self.assertEqual(m.pipeline_runs()[0]["id"], run.name)

    def test_state_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as t:
            for bad in ("../../etc", "20260921-101500/../x", "abc"):
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    monitor.Monitor(Path(t)).pipeline_state(bad)

    def test_start_pipeline_validates_input_and_refuses_second_run(self):
        with tempfile.TemporaryDirectory() as t:
            m = monitor.Monitor(Path(t))
            for bad in ({"destinations": "a; rm -rf /"}, {"destinations": "x" * 300}, {"delayMs": "abc"}):
                with self.subTest(bad=bad), self.assertRaises(ValueError), mock.patch("subprocess.Popen") as popen:
                    m.start_pipeline(bad)
                    popen.assert_not_called()
            run = Path(t) / "demo" / "runs" / "20260921-101500"
            run.mkdir(parents=True)
            (run / "state.json").write_text(json.dumps({"status": "running", "pid": os.getpid()}), encoding="utf-8")
            (Path(t) / "demo" / "latest.txt").write_text(run.name, encoding="utf-8")
            with mock.patch("subprocess.Popen") as popen:
                self.assertEqual(m.start_pipeline({})[0], 409)
                popen.assert_not_called()

    def test_start_pipeline_only_api(self):
        with tempfile.TemporaryDirectory() as t, mock.patch("subprocess.Popen") as popen:
            monitor.Monitor(Path(t)).start_pipeline({"onlyApi": True})
            self.assertIn("--only-api", popen.call_args.args[0])

    def test_start_pipeline_builds_a_safe_command(self):
        with tempfile.TemporaryDirectory() as t:
            m = monitor.Monitor(Path(t))
            with mock.patch("subprocess.Popen") as popen:
                code, body = m.start_pipeline({"destinations": "Nha Trang,Phú Quốc", "maxHotels": "300", "delayMs": 999999, "liveVinpearl": True,
                                               "liveTours": True, "noDb": True})
            self.assertEqual(code, 200)
            argv = popen.call_args.args[0]
            self.assertEqual(argv[argv.index("--replay-delay-ms") + 1], "2000")  # bị chặn ở mức tối đa
            self.assertEqual(argv[argv.index("--destinations") + 1], "Nha Trang,Phú Quốc")
            self.assertEqual(argv[argv.index("--max-hotels") + 1], "300")
            self.assertIn("--live-vinpearl", argv)
            self.assertNotIn("--live-tours", argv, "giao diện không được mở trình duyệt (Chromium) dù có ai gửi liveTours")
            self.assertIn("--no-db", argv)
            self.assertNotIn("--db-port", argv, "giao diện không được đổi đích Postgres")
            self.assertEqual(popen.call_args.kwargs["env"]["VOTA_DATA_DIR"], str(Path(t)))


@unittest.skipUnless(all((REAL_INTERIM / f).exists() for f in ("booking_hotels.jsonl", "agoda_hotels.jsonl", "vinpearl.jsonl")),
                     "cần dữ liệu thô đã cào trong data/interim")
class EndToEnd(unittest.TestCase):
    def test_full_run_without_db_on_a_real_slice(self):
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / "data"
            for f in REAL_INTERIM.glob("*.jsonl"):
                lines = [ln for ln in f.read_text(encoding="utf-8").split("\n") if ln.strip()]
                (src / "interim").mkdir(parents=True, exist_ok=True)
                (src / "interim" / f.name).write_text("\n".join(lines[:150]) + "\n", encoding="utf-8")
            frozen = src / "products.jsonl"
            frozen.write_text('{"productId": "p1"}\n', encoding="utf-8")
            before = pd.sha256_of(frozen)
            with mock.patch.dict(os.environ, {"VOTA_DATA_DIR": str(src)}), contextlib.redirect_stdout(io.StringIO()):
                code = pd.main(["run", "--no-db", "--replay-delay-ms", "0", "--run-id", "20260921-101500-e2e", "--as-of", "2026-09-21"])
            state = json.loads((src / "demo" / "runs" / "20260921-101500-e2e" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual((code, state["status"]), (0, "succeeded"), state["log"][-5:])
            self.assertEqual({s["id"]: s["status"] for s in state["stages"]},
                             {"trigger": "done", "ingest": "done", "normalise": "done", "loader": "done", "database": "skipped", "report": "done"})
            self.assertGreater(state["stages"][2]["metrics"]["rowsFinal"], 0)
            self.assertEqual(state["funnel"][-1]["rows"], state["stages"][2]["metrics"]["rowsFinal"])
            self.assertEqual(pd.sha256_of(frozen), before, "catalog đóng băng không được đổi")
            self.assertTrue(all(g["ok"] for g in state["guardrails"]))
            self.assertFalse((src / "products.csv").exists(), "chỉ ghi trong data/demo")


if __name__ == "__main__":
    unittest.main()
