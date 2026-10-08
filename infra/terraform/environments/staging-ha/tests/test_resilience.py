"""Hợp đồng chịu lỗi của nhóm HA: rolling update, autoscaler, tắt êm SSE, DB đa zone, job cào.

Chạy: python3 -m pytest infra/terraform/environments/staging-ha/tests/test_resilience.py
Chỉ kiểm cấu trúc/ràng buộc trong Terraform và compose; hành vi thật cần terraform apply + k6 (docs/plan/2026-10-07-ha-vung-crawler-rolling.md §6).
"""
import pathlib
import re
import unittest

D = pathlib.Path(__file__).resolve().parents[1]
MAIN = (D / "main.tf").read_text()
VARS = (D / "variables.tf").read_text()
COMPOSE = (D / "compose.ha.yml").read_text()
PATRONI = (D / "patroni.tf").read_text()
STARTUP = (D / "startup.sh.tftpl").read_text()
DOCKERFILE = (D.parents[3] / "Dockerfile.backend").read_text()


def block(text, kind, name):
    match = re.search(rf'resource "{kind}" "{name}" \{{(.*?)\n\}}\n', text, re.S)
    assert match, f"thiếu resource {kind}.{name}"
    return match.group(1)


def default(name):
    body = re.search(rf'variable "{name}" \{{(.*?)\n\}}\n', VARS, re.S).group(1)
    return float(re.search(r"default\s*=\s*([0-9.]+)", body).group(1))


class RollingUpdate(unittest.TestCase):
    """Use case (plan §5.1): đổi image khi có 3 VM; MIG chỉ có health check liveness nên coi VM mới là xong ngay khi tiến trình lên."""

    def test_mig_waits_min_ready_sec_at_least_boot_to_ready(self):
        mig = block(MAIN, "google_compute_region_instance_group_manager", "app")
        self.assertRegex(mig, r"min_ready_sec\s*=\s*var\.boot_to_ready_seconds")
        self.assertGreaterEqual(default("boot_to_ready_seconds"), 360)

    def test_mig_uses_the_provider_that_supports_min_ready_sec(self):
        mig = block(MAIN, "google_compute_region_instance_group_manager", "app")
        self.assertIn("provider                  = google-beta", mig)

    def test_surge_never_removes_capacity(self):
        mig = block(MAIN, "google_compute_region_instance_group_manager", "app")
        self.assertRegex(mig, r'replacement_method\s*=\s*"SUBSTITUTE"')
        self.assertIn("max_unavailable_fixed = 0", mig)

    def test_autohealing_initial_delay_covers_boot(self):
        mig = block(MAIN, "google_compute_region_instance_group_manager", "app")
        self.assertRegex(mig, r"initial_delay_sec\s*=\s*var\.boot_to_ready_seconds")


class Autoscaler(unittest.TestCase):
    def test_cooldown_is_not_shorter_than_boot_to_ready(self):
        scaler = block(MAIN, "google_compute_region_autoscaler", "app")
        self.assertRegex(scaler, r"cooldown_period\s*=\s*var\.boot_to_ready_seconds")

    def test_defaults_survive_losing_one_vm(self):
        n, cpu, mem = default("min_replicas"), default("cpu_target"), default("memory_target_percent")
        self.assertGreaterEqual(n, 3)
        self.assertLessEqual(cpu, (n - 1) / n)          # N=3: mất 1 VM, CPU còn lại <= 100%
        self.assertLessEqual(mem, 100 * (n - 1) / n)

    def test_validations_enforce_the_formula(self):
        self.assertIn("var.cpu_target <= (var.min_replicas - 1) / var.min_replicas", VARS)
        self.assertIn("var.memory_target_percent <= 100 * (var.min_replicas - 1) / var.min_replicas", VARS)


class GracefulShutdown(unittest.TestCase):
    """Use case (plan §5.4): trợ lý đang stream lịch trình 90 giây thì LB rút VM lúc scale-in."""

    def test_chain_sse_le_draining_le_stop_grace(self):
        sse, draining = default("sse_max_seconds"), default("lb_connection_draining_seconds")
        self.assertGreaterEqual(draining, sse)
        self.assertIn("var.lb_connection_draining_seconds + 10", MAIN)          # stop_grace = draining + 10
        self.assertRegex(block(MAIN, "google_compute_backend_service", "app"),
                         r"connection_draining_timeout_sec\s*=\s*var\.lb_connection_draining_seconds")

    def test_validation_blocks_draining_shorter_than_sse(self):
        self.assertIn("var.lb_connection_draining_seconds >= var.sse_max_seconds", VARS)

    def test_backend_and_frontend_stop_grace_come_from_the_chain(self):
        self.assertEqual(COMPOSE.count("stop_grace_period: ${BACKEND_STOP_GRACE:-110}s"), 2)  # backend + frontend proxy SSE
        self.assertIn("UVICORN_TIMEOUT_GRACEFUL_SHUTDOWN: ${UVICORN_GRACEFUL_SECONDS:-100}", COMPOSE)
        self.assertIn("BACKEND_STOP_GRACE='${stop_grace_seconds}'", STARTUP)

    def test_image_reads_graceful_timeout_from_env_not_a_hardcoded_30(self):
        self.assertIn("UVICORN_TIMEOUT_GRACEFUL_SHUTDOWN=30", DOCKERFILE)
        self.assertNotIn('"--timeout-graceful-shutdown", "30"', DOCKERFILE)


class SecretPermissions(unittest.TestCase):
    def test_jwt_files_are_root_owned_and_readable_by_backend_group(self):
        self.assertIn("chown root:10001 /etc/vota/secrets /etc/vota/secrets/*.pem", STARTUP)
        self.assertRegex(STARTUP, r"chmod 750 /etc/vota/secrets")
        self.assertRegex(STARTUP, r"chmod 640 /etc/vota/secrets/\*\.pem")


class PatroniTier(unittest.TestCase):
    def test_off_by_default(self):
        self.assertRegex(re.search(r'variable "create_patroni" \{(.*?)\n\}', VARS, re.S).group(1), r"default\s*=\s*false")

    def test_db_nodes_and_witness_are_in_three_distinct_zones(self):
        self.assertIn("!contains(var.patroni_zones, var.patroni_witness_zone)", VARS)
        self.assertIn("length(toset(var.patroni_zones)) == 2", VARS)

    def test_data_disk_survives_vm_replacement(self):
        disk = block(PATRONI, "google_compute_disk", "patroni_data")
        self.assertIn("prevent_destroy = true", disk)

    def test_ilb_only_sends_connections_to_the_leader(self):
        check = block(PATRONI, "google_compute_health_check", "patroni_primary")
        self.assertIn('"/primary"', check)
        self.assertIn("8008", check)

    def test_demoted_node_does_not_keep_old_connections(self):
        backend = block(PATRONI, "google_compute_region_backend_service", "patroni_primary")
        self.assertIn("NEVER_PERSIST", backend)

    def test_database_port_is_not_open_to_the_internet(self):
        for name in ("patroni_peers", "patroni_health", "patroni_clients"):
            fw = block(PATRONI, "google_compute_firewall", name)
            self.assertNotIn("0.0.0.0/0", fw, name)

    def test_nodes_have_no_public_ip(self):
        nic = re.search(r"network_interface \{(.*?)\n  \}", PATRONI, re.S).group(1)
        self.assertNotIn("access_config", nic)


if __name__ == "__main__":
    unittest.main()
