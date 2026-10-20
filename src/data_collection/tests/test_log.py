"""Log JSON của crawler (docs/spec/logging-schema.md): schema, giờ +07:00, che dữ liệu nhạy cảm, sự kiện theo bước,
và stdout của lệnh `due` không bị lẫn log."""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fresh_catalog
import log
from fresh_run_log import RunRecorder

SECRETS = ["hunter2", "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc123def", "postgresql://app:s3cretpw@db.internal:5432/vota",
           "sk_live_abcdefgh12345678", "a.nguyen@example.com", "0912345678", "4111111111111111",
           "Bearer abc.def.ghi-123", "co-api-key-9f8e7d6c"]


def capture():
    """Chạy khối và trả các dòng JSON ghi ra stdout."""
    class Ctx:
        def __enter__(self):
            self.buf = io.StringIO()
            self.cm = contextlib.redirect_stdout(self.buf)
            self.cm.__enter__()
            return self

        def __exit__(self, *exc):
            self.cm.__exit__(*exc)

        @property
        def lines(self):
            return [json.loads(line) for line in self.buf.getvalue().splitlines() if line.strip()]
    return Ctx()


class LoggerSchemaTests(unittest.TestCase):
    def setUp(self):
        log.configure(reset=True)
        self.addCleanup(log.configure, reset=True)

    def test_one_json_line_with_common_fields_and_hanoi_time(self):
        log.configure(run_id="full-20261006T030000Z-1", flow="full")
        with capture() as out, log.scope(step="vinpearl", source="vinpearl"):
            log.info("catalog.index.start", "catalog.index.start", records=3)
        (record,) = out.lines
        self.assertEqual((record["service"], record["severity"], record["event"]), ("crawler", "INFO", "catalog.index.start"))
        self.assertEqual((record["run_id"], record["flow"], record["step"], record["source"]),
                         ("full-20261006T030000Z-1", "full", "vinpearl", "vinpearl"))
        self.assertRegex(record["ts"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}\+07:00$")
        self.assertRegex(record["ts_utc"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
        self.assertEqual(record["message"], "catalog.index.start")
        self.assertEqual(record["records"], 3)

    def test_log_level_env_filters_lower_severities(self):
        with patch.dict(os.environ, {"LOG_LEVEL": "WARNING"}), capture() as out:
            log.info("a.b", "bỏ")
            log.debug("a.c", "bỏ")
            log.warning("a.d", "giữ")
        self.assertEqual([r["event"] for r in out.lines], ["a.d"])

    def test_say_infers_event_severity_and_source_from_the_line(self):
        with capture() as out:
            log.say("[trip] catalog.source.timeout name=trip-flights: quá hạn giờ")
            log.say("alert.failed RuntimeError: boom")
            log.say("[booking] WARNING chậm")
            log.say("Run full: /data/x")
        timeout, failed, warn, free = out.lines
        self.assertEqual((timeout["event"], timeout["source"], timeout["severity"]), ("catalog.source.timeout", "trip", "WARNING"))
        self.assertEqual((failed["event"], failed["severity"]), ("alert.failed", "ERROR"))
        self.assertEqual((warn["event"], warn["severity"], warn["source"]), ("crawler.output", "WARNING", "booking"))
        self.assertEqual(free["event"], "crawler.output")

    def test_error_carries_type_message_and_stack_redacted(self):
        try:
            raise RuntimeError("không nối được postgresql://app:s3cretpw@db:5432/vota")
        except RuntimeError as exc:
            with capture() as out:
                log.error("run.failed", "lỗi", error=exc)
        err = out.lines[0]["error"]
        self.assertEqual(err["type"], "RuntimeError")
        self.assertNotIn("s3cretpw", json.dumps(err))
        self.assertIn("stack", err)

    def test_plain_mode_for_child_processes_prints_only_the_text_line(self):
        with patch.dict(os.environ, {"CRAWL_LOG_PLAIN": "1"}), capture() as out:
            log.say("live.control key=trip paused=True")
        self.assertEqual(out.buf.getvalue(), "live.control key=trip paused=True\n")


class RedactTests(unittest.TestCase):
    def test_sensitive_keys_and_value_patterns_are_masked(self):
        data = {"password": "hunter2", "Authorization": "Bearer abc.def.ghi-123", "cohere_api_key": "co-api-key-9f8e7d6c",
                "dsn": "postgresql://app:s3cretpw@db:5432/vota", "ok": 5,
                "nested": {"note": "gọi a.nguyen@example.com hoặc 0912345678, thẻ 4111111111111111",
                           "jwt": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc123def", "stripe": "sk_live_abcdefgh12345678"}}
        dumped = json.dumps(log.redact(data))
        for secret in SECRETS:
            self.assertNotIn(secret, dumped)
        self.assertEqual(log.redact(data)["ok"], 5)

    def test_source_url_keeps_host_and_path_but_drops_query_and_userinfo(self):
        text = log.redact_text("GET https://user:pw@www.trip.com/hotels/detail?token=abc123&key=zzz#frag trả 200")
        self.assertIn("https://www.trip.com/hotels/detail", text)
        for leaked in ("abc123", "zzz", "pw@", "frag"):
            self.assertNotIn(leaked, text)

    def test_key_value_text_is_masked(self):
        text = log.redact_text("khởi tạo COHERE_API_KEY=co-api-key-9f8e7d6c password: hunter2 xong")
        self.assertNotIn("co-api-key-9f8e7d6c", text)
        self.assertNotIn("hunter2", text)

    def test_emit_never_prints_injected_secrets(self):
        with capture() as out:
            # giá trị trần (không có khoá đi kèm) chỉ che được khi khớp mẫu; mật khẩu/key phải đi theo khoá
            log.info("catalog.index.complete", "catalog.index.complete " + " ".join(SECRETS[1:8])
                     + f" password={SECRETS[0]} api_key={SECRETS[8]}",
                     report={"dsn": SECRETS[2], "mail": SECRETS[4]}, token=SECRETS[1], password=SECRETS[0],
                     cohere={"api_key": SECRETS[8]})
        for secret in SECRETS:
            self.assertNotIn(secret, out.buf.getvalue())


class RunRecorderLogTests(unittest.TestCase):
    def run_recorder(self, root: Path, fail=False):
        (root / "state").mkdir(exist_ok=True)
        rec = RunRecorder(root / "run", root / "state", run_id="full-20261006T030000Z-7", mode="full",
                          trigger="manual", settings={}).start()
        err = None
        try:
            with rec.step("vinpearl", group="crawl") as detail:
                detail["records"] = 12
            if fail:
                with rec.step("trip-hotels.prices"):
                    raise RuntimeError("hỏng")
        except RuntimeError as exc:
            err = exc
        log.say("[vinpearl] Fetched 3 rows", source="vinpearl")
        rec.finish("failed" if fail else "ok", 3 if fail else 0)
        return err

    def test_step_start_end_json_on_stdout_and_plain_text_in_job_log(self):
        with tempfile.TemporaryDirectory() as tmp, capture() as out:
            root = Path(tmp)
            self.run_recorder(root, fail=True)
            job_log = (root / "run" / "job.log").read_text(encoding="utf-8")
        records = out.lines
        start = next(r for r in records if r["event"] == "step.start" and r["step"] == "vinpearl")
        end = next(r for r in records if r["event"] == "step.end" and r["step"] == "vinpearl")
        self.assertEqual((start["run_id"], start["flow"], start["source"]), ("full-20261006T030000Z-7", "full", "vinpearl"))
        self.assertEqual((end["status"], end["severity"], end["records"]), ("ok", "INFO", 12))
        self.assertIsInstance(end["duration_ms"], int)
        failed = next(r for r in records if r["event"] == "step.end" and r["step"] == "trip-hotels.prices")
        self.assertEqual((failed["status"], failed["severity"], failed["source"]), ("error", "ERROR", "tripHotels"))
        # job.log: đúng chữ cũ cho monitor, không có JSON
        self.assertRegex(job_log, r"(?m)^\d{2}:\d{2}:\d{2} catalog\.step\.start name=vinpearl group=crawl$")
        self.assertRegex(job_log, r"(?m)^\d{2}:\d{2}:\d{2} catalog\.step\.done name=vinpearl status=ok seconds=")
        self.assertRegex(job_log, r"(?m)^\d{2}:\d{2}:\d{2} \[vinpearl\] Fetched 3 rows$")
        self.assertNotIn('"service"', job_log)
        # stdout container: JSON, không lặp dòng text
        self.assertNotIn("catalog.step.start name=vinpearl\n", out.buf.getvalue())

    def test_context_is_cleared_after_the_run(self):
        with tempfile.TemporaryDirectory() as tmp, capture():
            self.run_recorder(Path(tmp))
        self.assertIsNone(log.current()["run_id"])


class CommandStdoutTests(unittest.TestCase):
    def test_due_stdout_is_only_the_mode_name_and_log_goes_to_stderr(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"CATALOG_STATE_DIR": str(Path(tmp) / "state"), "CATALOG_RUN_ROOT": str(Path(tmp) / "runs")}
            out, err = io.StringIO(), io.StringIO()
            with patch.dict(os.environ, env), \
                    patch.object(fresh_catalog.fresh_settings, "scheduled_mode", return_value=("daily", "đến giờ")), \
                    contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                self.assertEqual(fresh_catalog.run_job("due"), 0)
        self.assertEqual(out.getvalue().strip(), "daily")
        # catalog.freshness (heartbeat của lượt due, phát ở mỗi tick) được ghi sau catalog.due nên không còn là dòng cuối
        records = [json.loads(line) for line in err.getvalue().strip().splitlines()]
        record = next(r for r in records if r["event"] == "catalog.due")
        self.assertEqual(record["mode"], "daily")
        self.assertIn("catalog.due daily", record["message"])

    def test_run_end_event_keeps_the_legacy_exit_string(self):
        class Rec:
            data = {"counts": {"db": {"rows": 5}}, "sourceStatuses": {"vinpearl": 0}}
            _t0 = 0.0
        with capture() as out:
            fresh_catalog.emit_run_end(Rec, "partial", 3)
        (record,) = out.lines
        self.assertEqual((record["event"], record["severity"], record["exit_code"], record["status"]),
                         ("run.end", "WARNING", 3, "partial"))
        self.assertIn("fresh-catalog.exit=3", record["message"])
        self.assertEqual(record["records"], {"db": {"rows": 5}})
        self.assertIn("duration_ms", record)


if __name__ == "__main__":
    unittest.main()
