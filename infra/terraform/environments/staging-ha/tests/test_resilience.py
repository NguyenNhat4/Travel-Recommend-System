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

    def test_mig_does_not_wait_past_liveness_and_gates_on_lb_health_instead(self):
        # Chốt 2026-10-09 (docs/prd/update-archive/2026-10-09-rut-ngan-cd-chap-nhan-downtime.md): không chờ min_ready_sec;
        # cổng sẵn sàng là bước Verify của workflow CD (test ở test_cd_waits_for_lb_healthy_before_last_good).
        mig = block(MAIN, "google_compute_region_instance_group_manager", "app")
        self.assertRegex(mig, r"min_ready_sec\s*=\s*0\b")
        self.assertGreaterEqual(default("boot_to_ready_seconds"), 240)

    def test_mig_uses_the_provider_that_supports_min_ready_sec(self):
        mig = block(MAIN, "google_compute_region_instance_group_manager", "app")
        self.assertIn("provider                  = google-beta", mig)

    def test_rollout_replaces_all_vms_at_once_without_surge(self):
        # Chấp nhận downtime khi thay VM (chốt 2026-10-09): không surge; unavailable = 3 vì regional MIG 3 zone chỉ nhận 0 hoặc >= 3.
        mig = block(MAIN, "google_compute_region_instance_group_manager", "app")
        self.assertRegex(mig, r'replacement_method\s*=\s*"SUBSTITUTE"')
        self.assertRegex(mig, r"max_surge_fixed\s*=\s*0\b")
        self.assertRegex(mig, r"max_unavailable_fixed\s*=\s*3\b")

    def test_cd_waits_for_lb_healthy_before_last_good(self):
        # Không có min_ready_sec thì MIG báo stable trước khi LB thấy VM HEALTHY; Verify phải chờ, nếu không sẽ rollback nhầm.
        for wf in ("staging-ha-backend-cd.yml", "staging-ha-frontend-cd.yml"):
            text = (D.parents[3] / ".github" / "workflows" / wf).read_text()
            self.assertIn('[ "$healthy" = "$target_size" ] && break', text, wf)

    def test_autohealing_initial_delay_covers_boot(self):
        mig = block(MAIN, "google_compute_region_instance_group_manager", "app")
        self.assertRegex(mig, r"initial_delay_sec\s*=\s*var\.boot_to_ready_seconds")


class Autoscaler(unittest.TestCase):
    def test_cooldown_is_not_shorter_than_boot_to_ready(self):
        scaler = block(MAIN, "google_compute_region_autoscaler", "app")
        self.assertRegex(scaler, r"cooldown_period\s*=\s*var\.boot_to_ready_seconds")

    def test_defaults_match_the_agreed_capacity_rule(self):
        # Quy tắc chốt 2026-10-08: nhóm app từ 1 đến 2 VM.
        self.assertEqual(default("min_replicas"), 1)
        self.assertEqual(default("max_replicas"), 2)
        self.assertGreater(default("cpu_target"), 0)
        self.assertLessEqual(default("cpu_target"), 1)

    def test_validations_no_longer_block_min_one(self):
        self.assertIn("var.min_replicas >= 1", VARS)
        self.assertNotIn("(var.min_replicas - 1) / var.min_replicas", VARS)


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

    def test_clone_source_is_rendered_only_for_node_a(self):
        # Node b phải join qua DCS/leader; chỉ node a được pg_basebackup từ primary cũ.
        self.assertRegex(PATRONI, r'clone_from_host\s*=\s*each\.key == "a" \? var\.patroni_clone_from_host : ""')
        template = (D / "patroni-node.sh.tftpl").read_text()
        self.assertIn('PG_VERSION_FILE=$(find /mnt/disks/pgdata/postgresql', template)
        self.assertIn('[ -z "$PG_VERSION_FILE" ]', template)
        self.assertIn('CLONE_ARG="-e PATRONI_CLONE_FROM_HOST=${clone_from_host}"',
                      template)

    def test_node_b_waits_for_bootstrap_leader_only_on_an_empty_data_disk(self):
        template = (D / "patroni-node.sh.tftpl").read_text()
        self.assertRegex(PATRONI, r'bootstrap_leader_ip\s*=\s*local\.patroni_ips\["a"\]')
        self.assertRegex(PATRONI, r'wait_for_bootstrap_leader\s*=\s*each\.key == "b"')
        self.assertIn("[ '${wait_for_bootstrap_leader}' = 'true' ]", template)
        self.assertIn('PG_VERSION_FILE=$(find /mnt/disks/pgdata/postgresql', template)
        self.assertIn('[ -z "$PG_VERSION_FILE" ]', template)
        self.assertIn('http://${bootstrap_leader_ip}:8008/primary', template)
        self.assertIn('seq 1 120', template)

    def test_patroni_bind_mount_is_owned_by_the_image_postgres_user(self):
        template = (D / "patroni-node.sh.tftpl").read_text()
        self.assertIn("POSTGRES_UID=$(docker run --rm --entrypoint /usr/bin/id", template)
        self.assertIn("POSTGRES_GID=$(docker run --rm --entrypoint /usr/bin/id", template)
        self.assertIn('chown -R "$POSTGRES_UID:$POSTGRES_GID" /mnt/disks/pgdata/postgresql', template)
        self.assertIn('chmod 700 /mnt/disks/pgdata/postgresql', template)


if __name__ == "__main__":
    unittest.main()
