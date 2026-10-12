"""Cảnh báo của nhóm HA phải đủ, đúng ngưỡng và thật sự gửi tới ai đó.

Chạy: python3 infra/terraform/environments/staging-ha/tests/test_alerts.py
Không kiểm được tên metric trên GCP thật; chỉ kiểm cấu trúc và ràng buộc với biến.
"""
import pathlib
import re
import unittest

D = pathlib.Path(__file__).resolve().parents[1]
MON = (D / "monitoring.tf").read_text()
MUTE = (D / "alert_mute.tf").read_text()


def block(text: str, kind: str, name: str) -> str:
    match = re.search(rf'resource "{kind}" "{name}" \{{(.*?)\n\}}\n', text, re.S)
    assert match, f"thiếu {kind} {name}"
    return match.group(1)


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
        self.assertIn("local.group_size_filter", body)    # đếm VM theo metric của MIG, không theo tiền tố tên

    def test_at_max_needs_both_the_ceiling_and_high_cpu(self):
        body = policy("group_at_max")
        self.assertIn('combiner              = "AND"', body)   # chỉ đếm VM thì báo cả khi 2 VM nhàn rỗi
        self.assertNotIn("COMPARISON_GE", body)          # Cloud Monitoring chỉ nhận GT/LT
        self.assertEqual(len(re.findall(r'comparison\s+= "COMPARISON_GT"', body)), 2)   # bỏ qua chữ trong comment
        self.assertIn("var.max_replicas - 0.5", body)    # số VM nguyên: > max-0,5 tương đương >= max
        self.assertIn("local.group_size_filter", body)
        self.assertIn("var.cpu_target", body)            # tải vẫn cao: CPU trung bình nhóm trên cpu_target
        self.assertIn("local.group_vm_filter", body)

    def test_mute_job_failure_has_its_own_always_on_channel(self):
        policy_body = block(MUTE, "google_monitoring_alert_policy", "mute_job_failed")
        self.assertIn("google_monitoring_notification_channel.email_always", policy_body)
        self.assertNotIn("local.alert_channels", policy_body)   # kênh HA bị mute, nên không dùng kênh đó
        always = block(MUTE, "google_monitoring_notification_channel", "email_always")
        self.assertNotIn("ignore_changes", always)              # scheduler không được tắt kênh này

    def test_mute_jobs_retry_and_count_failures(self):
        for job in ("alert_mute_on", "alert_mute_off"):
            self.assertIn("retry_config", block(MUTE, "google_cloud_scheduler_job", job), job)
        metric = block(MUTE, "google_logging_metric", "ha_alert_mute_job_failed")
        self.assertIn("cloud_scheduler_job", metric)
        self.assertIn("severity>=ERROR", metric)

    def test_crawler_silence_alert_uses_the_every_tick_heartbeat(self):
        # catalog.due được phát ở mỗi tick cron, kể cả khi đang có lượt chạy; catalog.freshness thì không (xem crawler_monitoring.tf).
        crawler = (D / "crawler_monitoring.tf").read_text()
        heartbeat = block(crawler, "google_logging_metric", "crawler_freshness_heartbeat")
        self.assertIn('jsonPayload.event=\\"catalog.due\\"', heartbeat)
        self.assertNotIn("catalog.freshness", heartbeat)

    def test_late_catalog_alert_stays_gated_until_the_fixed_crawler_is_deployed(self):
        crawler = (D / "crawler_monitoring.tf").read_text()
        late_metric = block(crawler, "google_logging_metric", "crawler_catalog_late")
        late_policy = block(crawler, "google_monitoring_alert_policy", "crawler_catalog_late")
        self.assertIn("local.crawler_late_alerts ? 1 : 0", late_metric)
        self.assertIn("local.crawler_late_alerts ? 1 : 0", late_policy)
        variables = (D / "variables.tf").read_text()
        self.assertRegex(variables, r'variable "crawler_late_alert_enabled" \{[^}]*default\s*=\s*false')

    def test_crawler_alert_policies_restrict_the_resource_type(self):
        # Cloud Monitoring từ chối filter của alert policy không có resource.type (gặp khi apply 2026-10-12).
        crawler = (D / "crawler_monitoring.tf").read_text()
        for name in ("crawler_run_failed", "crawler_silent", "crawler_catalog_late"):
            body = block(crawler, "google_monitoring_alert_policy", name)
            self.assertIn('resource.type=\\"gce_instance\\"', body, name)

    def test_email_channel_stays_muted_by_schedule(self):
        self.assertIn("ignore_changes = [enabled]", block(MON, "google_monitoring_notification_channel", "email"))

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
