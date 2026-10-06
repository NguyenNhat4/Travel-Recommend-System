"""Hợp đồng health check của nhóm HA: autohealing dùng liveness, load balancer dùng readiness (không lẫn lộn).

Chạy: python3 infra/terraform/environments/staging-ha/tests/test_health_checks.py
"""
import pathlib
import re
import unittest

MAIN = (pathlib.Path(__file__).resolve().parents[1] / "main.tf").read_text()


def block(kind: str, name: str) -> str:
    match = re.search(rf'resource "{kind}" "{name}" \{{(.*?)\n\}}\n', MAIN, re.S)
    assert match, f"thiếu resource {kind}.{name}"
    return match.group(1)


class HealthCheckRoles(unittest.TestCase):
    def test_autohealing_uses_liveness(self):
        mig = block("google_compute_region_instance_group_manager", "app")
        self.assertIn("google_compute_health_check.live.id", mig)
        self.assertNotIn("google_compute_health_check.ready", mig)

    def test_load_balancer_uses_readiness(self):
        backend = block("google_compute_backend_service", "app")
        self.assertIn("google_compute_health_check.ready.id", backend)
        self.assertNotIn("google_compute_health_check.live", backend)

    def test_liveness_never_depends_on_recsys_or_database(self):
        live = block("google_compute_health_check", "live")
        self.assertIn('"/health/live"', live)
        self.assertNotIn("ready", live.replace("name", ""))  # đường dẫn không chứa /health/ready

    def test_readiness_path_is_the_recsys_aware_route(self):
        self.assertIn('"/health/ready"', block("google_compute_health_check", "ready"))

    def test_autohealing_tolerates_a_full_minute_of_silence(self):
        live = block("google_compute_health_check", "live")
        interval = int(re.search(r"check_interval_sec\s*=\s*(\d+)", live).group(1))
        threshold = int(re.search(r"unhealthy_threshold\s*=\s*(\d+)", live).group(1))
        self.assertGreaterEqual(interval * threshold, 60)


if __name__ == "__main__":
    unittest.main()
