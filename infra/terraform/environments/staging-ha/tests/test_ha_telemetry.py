"""Telemetry của VM HA (log, watcher, collector, nhãn nhóm) phải khớp giữa Terraform, startup script và file trên đĩa.

Chạy: python3 infra/terraform/environments/staging-ha/tests/test_ha_telemetry.py
Không kiểm được trên VM thật; chỉ kiểm tên file, khoá metadata, cú pháp template và ràng buộc autoscaler.
"""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAIN = (ROOT / "main.tf").read_text()
STARTUP = (ROOT / "startup.sh.tftpl").read_text()
MON_DIR = ROOT.parents[2] / "monitoring"   # infra/monitoring


def startup_block() -> str:
    start = STARTUP.index("fetch_monitoring_file() {")
    end = STARTUP.index("install_monitoring || echo")
    return STARTUP[start:end]


class HaTelemetry(unittest.TestCase):
    def test_template_carries_group_label(self):
        self.assertIn('group = "${var.name_prefix}-app"', MAIN)
        self.assertRegex(MAIN, r'role\s+= "app"')

    def test_metadata_keys_match_what_startup_fetches(self):
        keys_tf = set(re.findall(r'(vota-mon-[a-z-]+)\s+= file\(', MAIN))
        keys_startup = set(re.findall(r'fetch_monitoring_file (vota-mon-[a-z-]+) ', startup_block()))
        self.assertEqual(keys_tf, keys_startup)
        self.assertEqual(len(keys_tf), 9)

    def test_every_file_referenced_by_terraform_exists(self):
        names = re.findall(r'file\("\$\{local\.monitoring_dir\}/([^"]+)"\)', MAIN)
        self.assertEqual(len(names), 9)
        for name in names:
            self.assertTrue((MON_DIR / name).is_file(), name)

    def test_install_script_installs_the_files_startup_writes(self):
        install = (MON_DIR / "install-vota-docker-event-watcher.sh").read_text()
        for name in [
            "vota-docker-event-watcher.py", "vota-docker-event-watcher.service",
            "vota-container-disk-collector.py", "vota-container-disk-collector.service",
            "vota-container-stats-collector.py", "vota-container-stats-collector.service",
            "vota-monitoring-logrotate.conf",
        ]:
            self.assertIn(name, install, name)

    def test_startup_block_has_no_template_sequences(self):
        block = startup_block()
        self.assertNotIn("${", block)   # templatefile sẽ thay chuỗi này
        self.assertNotIn("%{", block)

    def test_monitoring_failure_cannot_stop_app_boot(self):
        # Hàm được gọi trong "||" nên set -e tắt bên trong; mỗi bước phải tự "return 1" để dừng sớm, còn lỗi không kéo sập boot.
        self.assertIn("install_monitoring || echo", STARTUP)
        calls = re.findall(r"^\s+fetch_monitoring_file vota-mon-.*$", startup_block(), re.M)
        self.assertEqual(len(calls), 9)
        for call in calls:
            self.assertIn("|| return 1", call)

    def test_process_metrics_are_excluded_but_host_metrics_stay(self):
        # Metric theo tiến trình chiếm ~83% lượng metric agent bị tính phí (2026-10-12). Pipeline phải tham chiếu processor.
        for name in ("ops-agent-staging.yaml", "ops-agent-crawler.yaml"):
            text = (MON_DIR / name).read_text()
            self.assertIn("type: exclude_metrics", text, name)
            self.assertIn("- agent.googleapis.com/processes/*", text, name)
            self.assertIn("hostmetrics", text, name)
            default = text.split("default_pipeline:", 2)[-1]
            self.assertIn("processors:\n          - metrics_filter", default, name)

    def test_ops_agent_keeps_hostmetrics_for_the_autoscaler_memory_metric(self):
        agent = (MON_DIR / "ops-agent-staging.yaml").read_text()
        self.assertIn("hostmetrics", agent)

    def test_helper_container_exit_is_not_counted_as_a_service_stop(self):
        watcher = (MON_DIR / "vota-docker-event-watcher.py").read_text()
        self.assertIn('return "helper"', watcher)
        main = (MON_DIR / "main.tf").read_text()
        stop = re.search(r'resource "google_logging_metric" "staging_container_stop" \{(.*?)\n\}\n', main, re.S).group(1)
        self.assertIn('container_class=\\"service\\"', stop)   # chỉ container service dừng mới báo động

    def test_failed_ops_agent_restart_restores_previous_config(self):
        block = startup_block()
        self.assertIn('cp -a "$conf.default" "$conf"', block)
        self.assertIn('rm -f "$conf"', block)

    def test_crawler_agent_config_does_not_count_container_stdout_twice(self):
        crawler = "\n".join(line for line in (MON_DIR / "ops-agent-crawler.yaml").read_text().splitlines()
                            if not line.lstrip().startswith("#"))   # comment nhắc docker_json không tính
        self.assertNotIn("docker_json", crawler)                 # stdout đã có trong file lượt cào
        self.assertIn("fresh-catalog-2*.log", crawler)           # không đọc monitor-cd.log
        self.assertIn("parse_json", crawler)                     # jsonPayload.service cho ba cảnh báo crawler

    def test_crawler_deploy_installs_its_agent_config(self):
        deploy = (ROOT.parents[2].parent / "scripts" / "deploy-staging-ha-crawler.sh").read_text()
        self.assertIn('ops-agent-crawler.yaml', deploy)
        self.assertIn("google-cloud-ops-agent", deploy)


if __name__ == "__main__":
    unittest.main()
