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


POLICIES = ["group_below_min", "group_at_max", "group_memory_high", "group_disk_high", "lb_5xx_ratio", "lb_latency", "lb_uptime", "redis_memory"]


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

    def test_memory_and_disk_filters_select_the_app_group_not_a_vm_name(self):
        # Metric Ops Agent không có nhãn instance_name: lọc theo nhãn instance của template (group = <prefix>-app).
        for loc in ("group_memory_filter", "group_disk_filter"):
            self.assertIn(f'metadata.user_labels.\\"group\\"=\\"${{local.vm_name_prefix}}\\"', MON, loc)
        self.assertNotIn("instance_name", re.search(r"group_memory_filter = (.*)", MON).group(1))
        self.assertIn("metric.labels.state", re.search(r"group_memory_filter = (.*)", MON).group(1))
        self.assertIn("metric.labels.state", re.search(r"group_disk_filter   = (.*)", MON).group(1))

    def test_memory_and_disk_alert_on_any_vm_and_on_silent_agent(self):
        for name, filt, threshold in (
            ("group_memory_high", "local.group_memory_filter", "var.alert_memory_percent"),
            ("group_disk_high", "local.group_disk_filter", "var.alert_disk_percent"),
        ):
            body = policy(name)
            self.assertIn(filt, body, name)
            self.assertIn(threshold, body, name)
            self.assertIn('comparison      = "COMPARISON_GT"', body, name)
            self.assertIn('cross_series_reducer = "REDUCE_MAX"', body, name)   # một VM vượt ngưỡng là đủ báo
            self.assertIn("condition_absent", body, name)                     # Ops Agent dừng trên cả nhóm
            self.assertIn("local.alert_channels", body, name)

    def test_memory_threshold_stays_above_the_autoscaler_target(self):
        # Autoscaler co giãn theo memory_target_percent; alert chỉ được báo khi vượt xa mức đó.
        variables = (D / "variables.tf").read_text()
        default = lambda name: float(re.search(rf'variable "{name}" \{{.*?default\s*=\s*([\d.]+)', variables, re.S).group(1))
        self.assertGreater(default("alert_memory_percent"), default("memory_target_percent"))
        self.assertLess(default("alert_memory_percent"), 100)
        self.assertLess(default("alert_disk_percent"), 100)

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


class DbAndCrawlerResourceAlerts(unittest.TestCase):
    """RAM, đĩa, CPU của cụm DB (pg-a, pg-b, pg-w) và VM job cào. Số liệu đỉnh 7 ngày: xem history/2026-10-14-canh-bao-tai-nguyen-db-va-crawler.md."""

    PAT = (D / "patroni_monitoring.tf").read_text()
    CRA = (D / "crawler_monitoring.tf").read_text()
    VARS = (D / "variables.tf").read_text()

    def default(self, name: str) -> float:
        return float(re.search(rf'variable "{name}" \{{.*?default\s*=\s*([\d.]+)', self.VARS, re.S).group(1))

    def local_value(self, text: str, name: str) -> str:
        return re.search(rf"{name}\s*=\s*(.*)", text).group(1)

    def test_db_policies_notify_through_the_shared_channels_and_need_the_patroni_cluster(self):
        for name in ("db_memory_high", "db_disk_high", "db_cpu_high"):
            body = block(self.PAT, "google_monitoring_alert_policy", name)
            self.assertIn("notification_channels = local.alert_channels", body, name)   # chịu lịch mute ban đêm như các alert HA
            self.assertIn("count                 = var.create_patroni ? 1 : 0", body, name)

    def test_crawler_policies_notify_and_exist_only_with_the_crawler_vm(self):
        for name in ("crawler_memory_high", "crawler_disk_high", "crawler_cpu_sustained"):
            body = block(self.CRA, "google_monitoring_alert_policy", name)
            self.assertIn("notification_channels = local.alert_channels", body, name)
            self.assertIn("count                 = local.crawler_enabled ? 1 : 0", body, name)

    def test_db_memory_and_disk_select_only_the_two_db_nodes_with_the_agent(self):
        # pg-w (witness) không có Ops Agent; lọc theo nhãn role=patroni để không có node "không có dữ liệu" giả.
        for name in ("db_memory_filter", "db_disk_filter"):
            value = self.local_value(self.PAT, name)
            self.assertIn('metadata.user_labels.\\"role\\"=\\"patroni\\"', value, name)
            self.assertIn('metadata.user_labels.\\"component\\"=\\"database\\"', value, name)
            self.assertNotIn("etcd-witness", value, name)

    def test_db_cpu_covers_all_three_nodes_by_name_prefix(self):
        value = self.local_value(self.PAT, "db_cpu_filter")
        self.assertIn('starts_with(\\"${var.name_prefix}-pg-\\")', value)   # gồm pg-w: CPU đo từ hypervisor

    def test_db_policies_name_the_node_in_the_incident(self):
        memory = block(self.PAT, "google_monitoring_alert_policy", "db_memory_high")
        cpu = block(self.PAT, "google_monitoring_alert_policy", "db_cpu_high")
        disk = block(self.PAT, "google_monitoring_alert_policy", "db_disk_high")
        # Nhóm theo tên VM (metadata.system_labels.name) để incident nêu đúng VM; CPU dùng nhãn instance_name của Compute Engine.
        self.assertIn('group_by_fields      = ["metadata.system_labels.name"]', memory)
        self.assertIn('group_by_fields      = ["metric.label.instance_name"]', cpu)
        self.assertIn('group_by_fields      = ["metadata.system_labels.name", "metric.label.device"]', disk)

    def test_app_memory_and_disk_alerts_name_the_vm_in_the_incident(self):
        memory = block(MON, "google_monitoring_alert_policy", "group_memory_high")
        disk = block(MON, "google_monitoring_alert_policy", "group_disk_high")
        self.assertIn('group_by_fields      = ["metadata.system_labels.name"]', memory)
        self.assertIn('group_by_fields      = ["metadata.system_labels.name", "metric.label.device"]', disk)

    def test_crawler_alerts_name_the_vm_in_the_incident(self):
        crawler = (D / "crawler_monitoring.tf").read_text()
        self.assertIn('group_by_fields      = ["metadata.system_labels.name"]', block(crawler, "google_monitoring_alert_policy", "crawler_memory_high"))
        self.assertIn('group_by_fields      = ["metadata.system_labels.name", "metric.label.device"]', block(crawler, "google_monitoring_alert_policy", "crawler_disk_high"))
        self.assertIn('group_by_fields      = ["metric.label.instance_name"]', block(crawler, "google_monitoring_alert_policy", "crawler_cpu_sustained"))

    def test_db_memory_and_disk_alarm_when_the_agent_goes_silent(self):
        for name in ("db_memory_high", "db_disk_high"):
            self.assertIn("condition_absent", block(self.PAT, "google_monitoring_alert_policy", name), name)

    def test_crawler_filters_follow_the_vm_instance_id_not_a_name_guess(self):
        # Tham chiếu instance_id của chính VM: không cần thêm nhãn vào VM đang chạy. try() để không lỗi khi tắt VM.
        for name in ("crawler_memory_filter", "crawler_disk_filter"):
            value = self.local_value(self.CRA, name)
            self.assertIn("resource.labels.instance_id", value, name)
            self.assertIn('try(google_compute_instance.crawler[0].instance_id, "")', self.CRA, name)
        self.assertIn('metric.labels.instance_name=\\"${local.crawler_name}\\"', self.local_value(self.CRA, "crawler_cpu_filter"))

    def test_crawler_cpu_waits_longer_than_one_daily_crawl(self):
        # Lượt cào bình thường chạm gần 100% CPU khoảng 1 giờ (quanh 09:00 giờ Việt Nam). Alert chỉ được kêu sau lâu hơn thế.
        body = block(self.CRA, "google_monitoring_alert_policy", "crawler_cpu_sustained")
        self.assertIn('duration        = "${var.alert_crawler_cpu_minutes * 60}s"', body)
        self.assertGreaterEqual(self.default("alert_crawler_cpu_minutes"), 120)

    def test_default_thresholds_sit_above_the_observed_seven_day_peaks(self):
        # Đỉnh đo 2026-10-14 (theo giờ): DB RAM 66,6; DB đĩa 19,5; DB CPU 12,6; máy cào RAM 57,8; máy cào đĩa 77,7.
        self.assertGreater(self.default("alert_db_memory_percent"), 66.6)
        self.assertGreater(self.default("alert_db_disk_percent"), 19.5)
        self.assertGreater(self.default("alert_db_cpu_percent"), 12.6)
        self.assertGreater(self.default("alert_crawler_memory_percent"), 57.8)
        self.assertGreater(self.default("alert_crawler_disk_percent"), 77.7)
        for name in ("alert_db_memory_percent", "alert_db_disk_percent", "alert_db_cpu_percent", "alert_crawler_memory_percent", "alert_crawler_disk_percent", "alert_crawler_cpu_percent"):
            self.assertLess(self.default(name), 100, name)


if __name__ == "__main__":
    unittest.main()
