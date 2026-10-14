"""Dashboard HA: sáu dashboard theo chủ đề, mọi ô hiển thị tên VM (không phải mã instance).

Chạy: python3 infra/terraform/environments/staging-ha/tests/test_dashboard.py
Không kiểm được dashboard thật trên GCP; chỉ kiểm cấu trúc Terraform và các filter.
"""
import pathlib
import re
import unittest

D = pathlib.Path(__file__).resolve().parents[1]
DASH = (D / "dashboard.tf").read_text()
ALERTS = (D / "alerts_dashboard.tf").read_text()
MON = (D / "monitoring.tf").read_text()
OUT = (D / "outputs.tf").read_text()

NAMES = ["ha", "ha_latency", "ha_vm_app", "ha_db_crawler", "ha_logs", "ha_alerts"]


def code_lines(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def dashboard_block(name: str) -> str:
    text = ALERTS if name == "ha_alerts" else DASH
    match = re.search(rf'resource "google_monitoring_dashboard" "{name}" \{{(.*?)\n\}}\n', text, re.S)
    assert match, f"thiếu dashboard {name}"
    return match.group(1)


class DashboardLayout(unittest.TestCase):
    def test_six_dashboards_exist_one_per_topic(self):
        for name in NAMES:
            self.assertIsNotNone(re.search(rf'resource "google_monitoring_dashboard" "{name}"', DASH + ALERTS), name)

    def test_dashboard_never_points_at_the_single_app_vm(self):
        self.assertNotIn("google_compute_instance.app", code_lines(DASH + ALERTS))

    def test_group_count_uses_the_mig_size_metric(self):
        self.assertIn("local.group_size_filter", DASH)
        self.assertIn("compute.googleapis.com/instance_group/size", MON)

    def test_dashboard_url_output_points_at_the_overview(self):
        self.assertIn('output "ha_dashboard_url"', OUT)
        self.assertIn("google_monitoring_dashboard.ha.id", OUT)

    def test_each_dashboard_opens_with_a_text_tile(self):
        for name in NAMES:
            self.assertIn("text = {", dashboard_block(name), name)

    def test_xychart_thresholds_have_no_color(self):
        # API từ chối color trong threshold của xyChart (chỉ scorecard được phép); lỗi này đã gặp khi apply.
        for line in code_lines(DASH + ALERTS).splitlines():
            if 'targetAxis = "Y1"' in line:
                self.assertNotIn("color", line, line)


class VmNamesNotIds(unittest.TestCase):
    def test_no_chart_groups_by_instance_id(self):
        # Mã instance đổi mỗi lần MIG thay VM; mọi nhóm theo tên VM (metadata.system_labels.name) hoặc instance_name.
        self.assertNotIn('"resource.labels.instance_id"', DASH)
        self.assertNotIn('"resource.labels.instance_id"', ALERTS)

    def test_no_title_or_legend_says_instance_code(self):
        self.assertNotIn("mã instance", code_lines(DASH).lower())

    def test_memory_disk_and_container_charts_group_by_vm_name(self):
        self.assertRegex(DASH, r'group_by_vm\s*=\s*\["metadata\.system_labels\.name"\]')
        for block in ("ha_vm_app", "ha_db_crawler"):
            body = dashboard_block(block)
            self.assertIn("local.group_by_vm", body, block)

    def test_cpu_charts_use_the_instance_name_metric_label(self):
        self.assertIn('groupByFields = ["metric.labels.instance_name"]', DASH)
        self.assertIn('groupByFields = ["metric.labels.instance_name"]', dashboard_block("ha_db_crawler"))

    def test_per_vm_alignment_is_five_minutes_to_load_less(self):
        self.assertRegex(DASH, r'align_per_vm\s*=\s*"300s"')
        self.assertRegex(DASH, r'align_lb\s*=\s*"60s"')


class DashboardContents(unittest.TestCase):
    def test_vm_resources_dashboard_splits_ram_disk_and_container_by_vm(self):
        body = dashboard_block("ha_vm_app")
        for needle in ("local.group_memory_filter", "local.group_disk_filter", "custom.googleapis.com/vota/container/cpu_percent",
                       "custom.googleapis.com/vota/container/memory_bytes", 'metric.labels.state!=\\"free\\"'):
            self.assertIn(needle, body, needle)

    def test_ram_by_state_is_the_last_tile_of_the_vm_dashboard(self):
        body = dashboard_block("ha_vm_app")
        by_state = body.index('title = "RAM theo trạng thái')
        self.assertGreater(by_state, body.index('title = "RAM đã dùng từng VM app'))

    def test_db_crawler_dashboard_uses_only_those_vms(self):
        body = dashboard_block("ha_db_crawler")
        for needle in ("local.db_cpu_filter", "local.crawler_cpu_filter", "local.db_memory_filter", "local.crawler_memory_filter",
                       "local.db_disk_filter", "local.crawler_disk_filter"):
            self.assertIn(needle, body, needle)
        self.assertIn("pg-w", body)   # ghi rõ witness không có RAM và đĩa

    def test_percentile_charts_live_only_on_the_latency_dashboard(self):
        for name in NAMES:
            body = dashboard_block(name)
            if name == "ha_latency":
                self.assertIn("ALIGN_PERCENTILE_95", body)
                self.assertIn("ALIGN_PERCENTILE_99", body)
            else:
                self.assertNotIn("ALIGN_PERCENTILE", body, name)

    def test_latency_per_vm_and_route_charts_use_the_api_metric(self):
        body = dashboard_block("ha_latency")
        self.assertEqual(body.count("google_logging_metric.ha_api_latency.name"), 3)  # p95 VM, p99 VM, p95 route
        self.assertIn('groupByFields = ["metric.labels.route"]', body)
        self.assertIn("250", body)   # ngưỡng NFR search

    def test_log_panels_only_on_the_logs_dashboard(self):
        logs = dashboard_block("ha_logs")
        self.assertEqual(logs.count("logsPanel = {"), 4)
        for name in NAMES:
            if name != "ha_logs":
                self.assertNotIn("logsPanel", dashboard_block(name), name)
        for name in ["log_filter_errors", "log_filter_slow", "log_filter_container", "log_filter_crawler"]:
            self.assertIn(f"local.{name}", logs, name)

    def test_api_latency_metric_excludes_probes_and_sse(self):
        metric = re.search(r'resource "google_logging_metric" "ha_api_latency" \{(.*?)\n\}\n', DASH, re.S).group(1)
        self.assertIn('EXTRACT(jsonPayload.duration_ms)', metric)
        self.assertIn('EXTRACT(jsonPayload.route)', metric)
        self.assertIn('DISTRIBUTION', metric)
        self.assertIn('NOT jsonPayload.route:\\"/stream\\"', metric)
        self.assertIn('NOT jsonPayload.route:\\"/health/\\"', metric)


class AlertsDashboard(unittest.TestCase):
    def test_alert_tiles_reference_the_policy_resources(self):
        # Mỗi ô là alertChart trỏ tới tên resource của policy; policy có count dùng try() để bỏ khi count = 0.
        body = dashboard_block("ha_alerts")
        self.assertIn("alertChart", ALERTS)
        self.assertIn("local.alert_panels_shown", ALERTS)
        self.assertIn("google_monitoring_alert_policy.mute_job_failed.name", ALERTS)
        self.assertIn("try(google_monitoring_alert_policy.db_memory_high[0].name", ALERTS)
        self.assertIn("alertChart", body + ALERTS)

    def test_alert_dashboard_states_the_mute_window_and_the_legacy_gap(self):
        self.assertIn("23:55–08:35", ALERTS)
        self.assertIn("vota-staging:", ALERTS)   # nói rõ cảnh báo staging cũ chưa có ở đây


if __name__ == "__main__":
    unittest.main()
