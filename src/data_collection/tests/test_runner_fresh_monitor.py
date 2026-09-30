"""`run_daily_docker.sh fresh-monitor`: chạy nền, tự bật lại; RAM không giới hạn mặc định (lượt bấm trên monitor chạy trong
container này — giới hạn 1 GB đã giết lượt full 30/09 bằng SIGKILL), đặt được bằng MONITOR_MEMORY."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

RUNNER = Path(__file__).resolve().parents[1] / "run_daily_docker.sh"
FAKE_DOCKER = """#!/usr/bin/env bash
echo "$*" >> "$DOCKER_LOG"
[ "$1" = run ] && echo fakecontainerid
exit 0
"""


class FreshMonitorRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "bin").mkdir()
        docker = root / "bin" / "docker"
        docker.write_text(FAKE_DOCKER)
        docker.chmod(0o755)
        (root / "data").mkdir()
        (root / "logs").mkdir()
        (root / "env").write_text("DB_TARGET=cloud\n")
        self.log = root / "docker.log"
        self.env = {"PATH": f"{root / 'bin'}:/usr/bin:/bin", "HOME": str(root), "DOCKER_LOG": str(self.log),
                    "FRESH_IMAGE": "registry/fresh@sha256:abc", "FRESH_DATA_DIR": str(root / "data"),
                    "CATALOG_ENV_FILE": str(root / "env"), "CATALOG_LOG_DIR": str(root / "logs"),
                    "MONITOR_HOST": "0.0.0.0", "MONITOR_PUBLIC": "1", "PULL": "0"}

    def tearDown(self):
        self.tmp.cleanup()

    def run_monitor(self, **extra):
        return subprocess.run(["bash", str(RUNNER), "fresh-monitor"], env={**self.env, **extra},
                              capture_output=True, text=True, timeout=30)

    def calls(self):
        return self.log.read_text().splitlines()

    def test_default_runs_detached_with_restart_policy_and_no_memory_limit(self):
        result = self.run_monitor()
        self.assertEqual(result.returncode, 0, result.stderr)
        rm, run = self.calls()
        self.assertEqual(rm, "rm -f vota-fresh-catalog-monitor")  # thay container cũ cùng tên
        self.assertTrue(run.startswith("run -d --restart unless-stopped --log-opt max-size=10m --log-opt max-file=3 "))
        self.assertNotIn("--memory", run)  # lượt Cào lớn chạy trong container monitor: không bóp RAM
        for part in ("--name vota-fresh-catalog-monitor", "--network host",
                     "registry/fresh@sha256:abc /app/src/data_collection/monitor.py", "--host 0.0.0.0"):
            self.assertIn(part, run)
        self.assertNotIn("--rm", run)  # Docker không cho --restart đi cùng --rm
        self.assertIn("chạy nền", result.stdout)

    def test_foreground_mode_and_custom_memory(self):
        result = self.run_monitor(MONITOR_RESTART="no", MONITOR_MEMORY="768m")
        self.assertEqual(result.returncode, 0, result.stderr)
        [run] = self.calls()
        self.assertTrue(run.startswith("run --rm --init --name vota-fresh-catalog-monitor"))
        self.assertIn("--memory 768m", run)
        self.assertNotIn("--restart", run)

    def test_invalid_restart_policy_is_rejected(self):
        result = self.run_monitor(MONITOR_RESTART="sometimes")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()
