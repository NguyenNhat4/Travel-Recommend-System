"""Dashboard nhóm HA phải nhìn đúng nhóm, không nhìn một VM cố định.

Chạy: python3 infra/terraform/environments/staging-ha/tests/test_dashboard.py
Không kiểm được dashboard thật trên GCP; chỉ kiểm cấu trúc Terraform và các filter.
"""
import pathlib
import re
import unittest

D = pathlib.Path(__file__).resolve().parents[1]
DASH = (D / "dashboard.tf").read_text()
MON = (D / "monitoring.tf").read_text()
OUT = (D / "outputs.tf").read_text()


def code_lines(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


class Dashboard(unittest.TestCase):
    def test_dashboard_resource_exists(self):
        self.assertIn('resource "google_monitoring_dashboard" "ha"', DASH)

    def test_dashboard_never_points_at_the_single_app_vm(self):
        self.assertNotIn("google_compute_instance.app", code_lines(DASH))   # chỉ nhìn một VM cũ là lỗi gốc

    def test_group_count_uses_the_mig_size_metric(self):
        self.assertIn("local.group_size_filter", DASH)
        self.assertIn("compute.googleapis.com/instance_group/size", MON)

    def test_cpu_is_split_per_vm_by_instance_name(self):
        self.assertIn("local.group_vm_filter", DASH)
        self.assertIn('groupByFields = ["metric.labels.instance_name"]', DASH)

    def test_cpu_group_filter_is_limited_to_the_mig_name_prefix(self):
        self.assertIn('starts_with(\\"${local.vm_name_prefix}\\")', MON)

    def test_p95_chart_shows_nfr_and_alert_thresholds(self):
        self.assertIn("ALIGN_PERCENTILE_95", DASH)
        self.assertIn("250", DASH)
        self.assertIn("var.alert_p95_latency_ms", DASH)

    def test_memory_chart_has_no_fake_vm_name_label(self):
        # metric memory của Ops Agent không mang instance_name; chỉ group theo instance_id.
        self.assertIn('groupByFields = ["resource.labels.instance_id"]', DASH)
        self.assertNotIn("metric.labels.instance_name", DASH.split("RAM đã dùng")[1])

    def test_p99_is_shown_for_lb_and_per_vm_and_route(self):
        self.assertIn("ALIGN_PERCENTILE_99", DASH)
        self.assertEqual(DASH.count('"ALIGN_PERCENTILE_99"'), 2)   # p99 của LB và p99 theo VM; route chỉ có p95
        self.assertIn('groupByFields = ["resource.labels.instance_id"]', DASH)   # p95/p99 theo VM
        self.assertIn('groupByFields = ["metric.labels.route"]', DASH)            # p95 theo route

    def test_api_latency_metric_excludes_probes_and_sse(self):
        metric = re.search(r'resource "google_logging_metric" "ha_api_latency" \{(.*?)\n\}\n', DASH, re.S).group(1)
        self.assertIn('EXTRACT(jsonPayload.duration_ms)', metric)
        self.assertIn('EXTRACT(jsonPayload.route)', metric)                        # nhãn route để chart theo route
        self.assertIn('DISTRIBUTION', metric)                                      # cần phân phối để có p95/p99
        self.assertIn('NOT jsonPayload.route:\\"/stream\\"', metric)               # SSE kéo dài theo LLM
        self.assertIn('NOT jsonPayload.route:\\"/health/\\"', metric)              # probe
        self.assertIn("google_logging_metric.ha_api_latency.name", DASH)           # chart dùng đúng metric này

    def test_log_panels_are_present_and_use_shared_filters(self):
        self.assertGreaterEqual(DASH.count("logsPanel = {"), 4)
        for name in ["log_filter_errors", "log_filter_slow", "log_filter_container", "log_filter_crawler"]:
            self.assertIn(f"local.{name}", DASH, name)
        self.assertIn("console.cloud.google.com/logs/query", DASH)                  # link mở Logs Explorer

    def test_xychart_thresholds_have_no_color(self):
        # API từ chối color trong threshold của xyChart (chỉ scorecard được phép); lỗi này đã gặp khi apply.
        for line in code_lines(DASH).splitlines():
            if 'targetAxis = "Y1"' in line:
                self.assertNotIn("color", line, line)

    def test_dashboard_url_is_an_output(self):
        self.assertIn('output "ha_dashboard_url"', OUT)
        self.assertIn("google_monitoring_dashboard.ha.id", OUT)


if __name__ == "__main__":
    unittest.main()
