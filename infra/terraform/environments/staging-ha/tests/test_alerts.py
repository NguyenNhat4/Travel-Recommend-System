"""Cảnh báo của nhóm HA phải đủ, đúng ngưỡng và thật sự gửi tới ai đó.

Chạy: python3 infra/terraform/environments/staging-ha/tests/test_alerts.py
Không kiểm được tên metric trên GCP thật; chỉ kiểm cấu trúc và ràng buộc với biến.
"""
import pathlib
import re
import unittest

D = pathlib.Path(__file__).resolve().parents[1]
MON = (D / "monitoring.tf").read_text()


def policy(name: str) -> str:
    match = re.search(rf'resource "google_monitoring_alert_policy" "{name}" \{{(.*?)\n\}}\n', MON, re.S)
    assert match, f"thiếu alert policy {name}"
    return match.group(1)


POLICIES = ["group_below_min", "group_at_max", "lb_5xx_ratio", "lb_latency", "lb_uptime", "redis_memory"]


class Alerts(unittest.TestCase):
    def test_every_policy_notifies_someone(self):
        for name in POLICIES:
            self.assertIn("notification_channels = local.alert_channels", policy(name), name)

    def test_alert_channels_come_from_emails_and_existing_channels(self):
        self.assertIn("google_monitoring_notification_channel.email", MON)
        self.assertIn("var.notification_channel_ids", MON)

    def test_below_min_uses_the_autoscaler_floor_and_catches_total_loss(self):
        body = policy("group_below_min")
        self.assertIn("COMPARISON_LT", body)
        self.assertIn("var.min_replicas", body)
        self.assertIn("condition_absent", body)           # nhóm bị xoá sạch thì ngưỡng "<" không bao giờ kích hoạt

    def test_at_max_uses_the_autoscaler_ceiling(self):
        body = policy("group_at_max")
        self.assertIn("COMPARISON_GE", body)
        self.assertIn("var.max_replicas", body)

    def test_5xx_alert_is_a_ratio_not_a_count(self):
        body = policy("lb_5xx_ratio")
        self.assertIn("denominator_filter", body)
        self.assertIn("response_code_class=500", body)
        self.assertIn("var.alert_5xx_ratio", body)

    def test_latency_alert_uses_p95(self):
        body = policy("lb_latency")
        self.assertIn("ALIGN_PERCENTILE_95", body)
        self.assertIn("var.alert_p95_latency_ms", body)

    def test_uptime_check_probes_readiness_through_the_load_balancer(self):
        uptime = re.search(r'resource "google_monitoring_uptime_check_config" "lb_ready" \{(.*?)\n\}\n', MON, re.S).group(1)
        self.assertIn('"/health/ready"', uptime)
        self.assertIn("google_compute_global_address.lb.address", uptime)

    def test_redis_alert_exists_only_with_redis(self):
        self.assertIn("count                 = var.create_redis ? 1 : 0", policy("redis_memory"))

    def test_group_alerts_do_not_target_the_single_staging_vm(self):
        code = "\n".join(line for line in MON.splitlines() if not line.lstrip().startswith("#"))
        self.assertNotIn("google_compute_instance.app", code)   # alert cũ nhắm 1 VM; nhóm HA lọc theo tiền tố tên
        self.assertIn("starts_with", code)


if __name__ == "__main__":
    unittest.main()
