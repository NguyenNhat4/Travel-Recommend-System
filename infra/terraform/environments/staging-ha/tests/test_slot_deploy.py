"""Hợp đồng của cơ chế cập nhật không gián đoạn trên một VM (slot blue/green + proxy cục bộ).

Chạy: python3 -m pytest infra/terraform/environments/staging-ha/tests/test_slot_deploy.py
Chỉ kiểm cấu trúc script và cách nối với Terraform/CD; hành vi thật cần chạy trên VM (xem slot-deploy.sh).
"""
import pathlib
import re
import subprocess
import unittest

D = pathlib.Path(__file__).resolve().parents[1]
ROOT = D.parents[3]
SCRIPT = (D / "slot-deploy.sh").read_text()
STARTUP = (D / "startup.sh.tftpl").read_text()
MAIN = (D / "main.tf").read_text()
ROLL = (ROOT / "scripts" / "roll-staging-ha-app-slots.sh").read_text()
PIN = (ROOT / "scripts" / "pin-staging-ha-mig-opportunistic.sh").read_text()
WORKFLOWS = {k: (ROOT / ".github" / "workflows" / f"staging-ha-{k}-cd.yml").read_text() for k in ("backend", "frontend")}


class Syntax(unittest.TestCase):
    def test_scripts_parse(self):
        for path in (D / "slot-deploy.sh", ROOT / "scripts" / "roll-staging-ha-app-slots.sh", ROOT / "scripts" / "pin-staging-ha-mig-opportunistic.sh"):
            result = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, f"{path.name}: {result.stderr}")


class SlotLayout(unittest.TestCase):
    def test_slots_use_distinct_ports_and_never_the_legacy_ones(self):
        ports = re.findall(r"(?:BACKEND_PORT|FRONTEND_PORT)=(\d+)", SCRIPT)
        self.assertEqual(sorted(ports), ["3001", "3002", "8001", "8002"])
        self.assertEqual(len(set(ports)), 4)
        self.assertNotIn("3000", ports)
        self.assertNotIn("8000", ports)

    def test_frontend_is_pointed_at_its_own_backend(self):
        self.assertIn("BACKEND_BASE_URL: http://127.0.0.1:${BACKEND_PORT}", SCRIPT)
        self.assertIn("PORT: ${FRONTEND_PORT}", SCRIPT)
        self.assertIn('"--port", "${BACKEND_PORT}"', SCRIPT)

    def test_container_names_are_per_slot(self):
        self.assertIn("container_name: vota-backend-${SLOT}", SCRIPT)
        self.assertIn("container_name: vota-frontend-${SLOT}", SCRIPT)

    def test_stop_grace_chain_is_kept_per_slot(self):
        self.assertEqual(SCRIPT.count("stop_grace_period: ${BACKEND_STOP_GRACE:-110}s"), 2)
        self.assertIn("UVICORN_TIMEOUT_GRACEFUL_SHUTDOWN: ${UVICORN_GRACEFUL_SECONDS:-100}", SCRIPT)


class Proxy(unittest.TestCase):
    def test_proxy_owns_the_port_the_load_balancer_uses(self):
        self.assertIn("listen 3000 default_server;", SCRIPT)
        self.assertIn("iptables -A INPUT -p tcp --dport 3000", STARTUP)

    def test_proxy_keeps_sse_streams_and_old_workers_alive_on_reload(self):
        self.assertIn("proxy_buffering off;", SCRIPT)
        self.assertRegex(SCRIPT, r"proxy_read_timeout\s+\d+s;")
        # worker_shutdown_timeout phải phủ LB draining (100 s) để SSE đang chạy không bị cắt khi reload.
        seconds = int(re.search(r"worker_shutdown_timeout\s+(\d+)s;", SCRIPT).group(1))
        self.assertGreaterEqual(seconds, 100)

    def test_reload_names_the_config_so_nginx_finds_its_pid_file(self):
        # Lỗi thật 2026-10-12: `nginx -s reload` không kèm -c tìm /run/nginx.pid (config đặt pid /tmp/nginx.pid) và lỗi.
        self.assertIn("pid /tmp/nginx.pid;", SCRIPT)
        for line in re.findall(r".*nginx .*-s reload.*", SCRIPT):
            if line.lstrip().startswith("#"):
                continue
            self.assertRegex(line, r"nginx -c \"\$PROXY_DIR/nginx\.conf\" -s reload", line)

    def test_failed_reload_puts_the_old_upstream_back(self):
        deploy = SCRIPT[SCRIPT.index("mode_deploy() {"):]
        branch = deploy[deploy.index("elif running vota-proxy; then"):deploy.index("log \"kiểm tra qua proxy")]
        self.assertIn("if ! reload_proxy; then", branch)
        self.assertLess(branch.index("if ! reload_proxy; then"), branch.index('slot_ports "$active"'))

    def test_switch_validates_config_before_reload(self):
        self.assertRegex(SCRIPT, r"nginx -t -c .*\n?.*nginx -s reload|nginx -t -c")
        self.assertIn("nginx -s reload", SCRIPT)


class SafetyProperties(unittest.TestCase):
    def test_old_slot_is_only_removed_after_the_new_one_is_ready_and_traffic_switched(self):
        deploy = SCRIPT[SCRIPT.index("mode_deploy() {"):]
        self.assertLess(deploy.index("wait_ready"), deploy.index("reload_proxy"))
        self.assertLess(deploy.index("reload_proxy"), deploy.index("drain_and_remove_old"))

    def test_new_slot_failure_leaves_the_old_one_untouched(self):
        deploy = SCRIPT[SCRIPT.index("mode_deploy() {"):]
        failure = deploy[deploy.index("if ! wait_ready"):deploy.index("if [ \"$active\" = legacy ]")]
        self.assertIn('stop_slot "$new"', failure)
        self.assertNotIn('stop_slot "$active"', failure)

    def test_legacy_container_is_not_auto_restarted_after_it_is_told_to_stop(self):
        self.assertLess(SCRIPT.index("docker update --restart=no vota-frontend vota-backend"), SCRIPT.index("docker kill --signal TERM vota-frontend"))

    def test_pgbouncer_is_not_recreated_while_running(self):
        ensure = SCRIPT[SCRIPT.index("ensure_infra() {"):SCRIPT.index("# Slot và proxy")]
        self.assertIn("if running vota-pgbouncer; then return 0; fi", ensure)

    def test_refuses_two_copies_when_ram_is_short(self):
        self.assertIn("MIN_AVAILABLE_MB", SCRIPT)
        self.assertIn("/proc/meminfo", SCRIPT)

    def test_images_must_be_digests(self):
        self.assertIn("@sha256:[a-f0-9]{64}", SCRIPT)


class WiringWithTerraformAndCd(unittest.TestCase):
    def test_startup_installs_and_runs_the_script_with_template_images(self):
        self.assertIn("/usr/local/sbin/vota-slot-deploy.sh", STARTUP)
        self.assertIn("${slot_deploy}", STARTUP)
        self.assertIn("vota-slot-deploy.sh boot", STARTUP)
        self.assertIn('slot_deploy = file("${path.module}/slot-deploy.sh")', MAIN)
        self.assertIn("slot_deploy        = local.slot_deploy", MAIN)

    def test_boot_env_has_everything_the_script_needs(self):
        for key in ("BACKEND_ENV_SECRET", "UVICORN_WORKERS", "UVICORN_GRACEFUL_SECONDS", "BACKEND_STOP_GRACE"):
            self.assertIn(f"{key}=", STARTUP)

    def test_cd_pins_policy_then_applies_then_rolls_vms(self):
        for kind, text in WORKFLOWS.items():
            pin = text.index("pin-staging-ha-mig-opportunistic.sh")
            apply = text.index("scripts/deploy-staging-ha-app.sh", pin)
            roll = text.index("roll-staging-ha-app-slots.sh", apply)
            self.assertLess(pin, apply, kind)
            self.assertLess(apply, roll, kind)

    def test_cd_rollback_also_rolls_vms(self):
        for kind, text in WORKFLOWS.items():
            rollback = text[text.index("Roll back"):]
            self.assertIn("roll-staging-ha-app-slots.sh", rollback, kind)

    def test_cd_no_longer_requires_vms_to_be_on_the_new_template(self):
        for kind, text in WORKFLOWS.items():
            self.assertNotIn("target_template", text, kind)

    def test_changes_to_the_new_scripts_trigger_cd(self):
        for kind, text in WORKFLOWS.items():
            self.assertIn("'scripts/roll-staging-ha-app-slots.sh'", text, kind)
            self.assertIn("'scripts/pin-staging-ha-mig-opportunistic.sh'", text, kind)

    def test_roll_checks_each_vm_runs_the_target_images(self):
        self.assertIn("SLOT_RESULT", ROLL)
        self.assertIn('backend=$BACKEND_REF', ROLL)

    def test_roll_does_not_pin_ssh_host_keys(self):
        # Lỗi thật 2026-10-12: MIG tạo lại fn9m (autohealing) -> khoá host mới -> "Host key verification failed" trên runner.
        self.assertIn("--strict-host-key-checking=no", ROLL)

    def test_pin_script_matches_main_tf_policy(self):
        self.assertIn('"type":"OPPORTUNISTIC"', PIN)
        self.assertIn('"maxSurge":{"fixed":0}', PIN)
        self.assertIn('"maxUnavailable":{"fixed":3}', PIN)


class SerialisedDeploys(unittest.TestCase):
    """Deploy không chạy chồng: khoá concurrency ở workflow (lớp 1) và flock trên VM (lớp 2)."""

    def test_cd_deploy_jobs_share_one_concurrency_group(self):
        for kind, text in WORKFLOWS.items():
            deploy = text[text.index("  deploy:\n"):]
            self.assertRegex(deploy, r"concurrency:\n\s+group: staging-ha-app\n\s+cancel-in-progress: false", kind)
            # khoá nằm ở job deploy, không ở workflow (job build không phải chờ)
            self.assertNotRegex(text[:text.index("  deploy:\n")], r"(?m)^concurrency:", kind)

    def test_slot_script_serialises_runs_on_one_vm(self):
        self.assertIn("flock -w 1800 9", SCRIPT)
        for fn in ("mode_boot() {", "mode_deploy() {"):
            self.assertIn("acquire_lock", SCRIPT[SCRIPT.index(fn):SCRIPT.index(fn) + 60], fn)

    def test_background_drain_does_not_hold_the_lock(self):
        self.assertIn('9>- >'.replace("-", "&-"), SCRIPT[SCRIPT.index("drain_and_remove_old() {"):])


class RollVisitsEveryVm(unittest.TestCase):
    """Chạy roll-staging-ha-app-slots.sh thật với gcloud giả, nhưng ssh giả đọc stdin như ssh thật.

    Lỗi thật 2026-10-12: vòng `while read ... <<< "$vms"` bị `gcloud compute ssh` nuốt stdin nên chỉ VM đầu tiên được cập nhật.
    """

    def _run(self, tmp):
        import json
        import os
        import stat
        digest = "sha256:" + "a" * 64
        backend = f"asia-southeast1-docker.pkg.dev/p/r/vota-backend@{digest}"
        frontend = f"asia-southeast1-docker.pkg.dev/p/r/vota-frontend@{digest}"
        vms = [
            {"instance": f"https://www.googleapis.com/compute/v1/projects/p/zones/z-{n}/instances/vm-{n}", "instanceStatus": "RUNNING"}
            for n in ("a", "b", "c")
        ]
        (tmp / "vms.json").write_text(json.dumps(vms))
        stub = tmp / "bin" / "gcloud"
        stub.parent.mkdir()
        stub.write_text(
            """#!/usr/bin/env bash
case "$*" in
  *list-instances*) cat "$STUB_DIR/vms.json" ;;
  *"compute ssh"*)
    cat > /dev/null    # ssh thật đọc stdin
    name="$3"; echo "$name" >> "$STUB_DIR/visited"
    echo "SLOT_RESULT host=$name active=blue backend=$BACKEND_REF frontend=$FRONTEND_REF" ;;
esac
"""
        )
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        env = dict(os.environ, PATH=f"{stub.parent}:{os.environ['PATH']}", STUB_DIR=str(tmp),
                   BACKEND_REF=backend, FRONTEND_REF=frontend, GCP_PROJECT_ID="p")
        result = subprocess.run(["bash", str(ROOT / "scripts" / "roll-staging-ha-app-slots.sh")], env=env, capture_output=True, text=True)
        visited = (tmp / "visited").read_text().split() if (tmp / "visited").exists() else []
        return result, visited

    def test_every_running_vm_is_updated_even_when_ssh_reads_stdin(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            result, visited = self._run(pathlib.Path(d))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(visited, ["vm-a", "vm-b", "vm-c"], result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
