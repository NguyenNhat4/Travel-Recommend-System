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
APP_CD = (ROOT / ".github" / "workflows" / "staging-ha-app-cd.yml").read_text()
INFRA_CD = (ROOT / ".github" / "workflows" / "staging-ha-infra-cd.yml").read_text()
DESIRED = (ROOT / "scripts" / "set-staging-ha-desired-images.sh").read_text()


def body(text, start, end=None):
    i = text.index(start)
    return text[i:text.index(end, i)] if end else text[i:]


class Syntax(unittest.TestCase):
    def test_scripts_parse(self):
        scripts = ["roll-staging-ha-app-slots.sh", "pin-staging-ha-mig-opportunistic.sh", "set-staging-ha-desired-images.sh",
                   "verify-staging-ha-app.sh", "probe-staging-ha.sh", "ci/image-key.sh", "ci/buildx-builder.sh", "ci/py-deps.sh"]
        for path in [D / "slot-deploy.sh"] + [ROOT / "scripts" / name for name in scripts]:
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

    def test_backend_service_urls_follow_the_slot_port(self):
        # Secret giữ port 8000 của kiểu cũ; URL gọi ngược backend phải ghi đè trong khối backend (environment thắng env_file).
        backend = SCRIPT[SCRIPT.index("  backend:\n"):SCRIPT.index("  frontend:\n")]
        self.assertIn("ITINERARY_SERVICE_BASE_URL: http://127.0.0.1:${BACKEND_PORT}", backend)
        self.assertIn("ASSISTANT_API_BASE_URL: http://127.0.0.1:${BACKEND_PORT}/api/v1", backend)
        self.assertNotIn("127.0.0.1:8000", SCRIPT)

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
        switch = body(SCRIPT, "mode_switch() {", "mode_abort() {")
        branch = switch[switch.index("elif running vota-proxy; then"):switch.index("log \"kiểm tra qua proxy")]
        self.assertIn("if ! reload_proxy; then", branch)
        self.assertLess(branch.index("if ! reload_proxy; then"), branch.index('slot_ports "$active"'))

    def test_switch_validates_config_before_reload(self):
        self.assertRegex(SCRIPT, r"nginx -t -c .*\n?.*nginx -s reload|nginx -t -c")
        self.assertIn("nginx -s reload", SCRIPT)


class StaticAssetStore(unittest.TestCase):
    """Hai VM (hoặc hai lần tải trang) có thể khác phiên bản: chunk /_next/static của mọi bản gần đây phải còn phục vụ được."""

    def test_proxy_serves_next_static_from_the_shared_store_first(self):
        self.assertIn("location /_next/static/ {", SCRIPT)
        self.assertIn("root /etc/vota/proxy/static-store;", SCRIPT)
        self.assertIn("try_files $uri @frontend;", SCRIPT)
        self.assertIn('STATIC_STORE="${STATIC_STORE:-$PROXY_DIR/static-store}"', SCRIPT)   # proxy đã mount PROXY_DIR

    def test_assets_are_stashed_before_any_vm_switches(self):
        prepare = body(SCRIPT, "mode_prepare() {", "mode_switch() {")
        self.assertIn("stash_static", prepare)
        self.assertIn("stash_static", body(SCRIPT, "mode_boot() {", "check_ram() {"))
        stash = body(SCRIPT, "stash_static() {", "# ----")
        self.assertIn('docker cp "$cid:/app/.next/static"', stash)
        self.assertIn('-mtime +"$STATIC_KEEP_DAYS" -delete', stash)


class SafetyProperties(unittest.TestCase):
    def test_old_slot_is_only_removed_after_the_new_one_is_ready_and_traffic_switched(self):
        prepare = body(SCRIPT, "mode_prepare() {", "mode_switch() {")
        # pha 1: slot mới chỉ thành "chờ đổi" sau khi ready; không đụng proxy
        self.assertLess(prepare.index("wait_ready"), prepare.index('echo "$new" > "$PENDING"'))
        self.assertNotIn("reload_proxy", prepare)
        self.assertNotIn("drain_and_remove_old", prepare)
        switch = body(SCRIPT, "mode_switch() {", "mode_abort() {")
        # pha 2: chỉ đổi sang slot đã chuẩn bị và đúng image đích; rút bản cũ sau khi proxy đã ready với bản mới
        self.assertLess(switch.index('slot_images "$new")" = "$BACKEND_IMAGE $FRONTEND_IMAGE"'), switch.index("reload_proxy"))
        self.assertLess(switch.index("reload_proxy"), switch.index('wait_ready "http://127.0.0.1:3000/health/ready"'))
        self.assertLess(switch.index('wait_ready "http://127.0.0.1:3000/health/ready"'), switch.index("drain_and_remove_old"))

    def test_new_slot_failure_leaves_the_old_one_untouched(self):
        prepare = body(SCRIPT, "mode_prepare() {", "mode_switch() {")
        failure = prepare[prepare.index("if ! wait_ready"):prepare.index('echo "$new" > "$PENDING"')]
        self.assertIn('stop_slot "$new"', failure)
        self.assertNotIn('stop_slot "$active"', failure)

    def test_abort_only_drops_the_pending_slot(self):
        abort = body(SCRIPT, "mode_abort() {", "mode_deploy() {")
        self.assertIn('stop_slot "$new"', abort)
        self.assertNotIn('stop_slot "$active"', abort)
        self.assertIn('[ "$new" != "$active" ]', abort)

    def test_switch_succeeds_when_the_active_slot_already_runs_the_target(self):
        # Lần thử 2026-10-13: một deploy khác chạy giữa prepare và switch, slot chờ không còn -> switch báo lỗi oan.
        switch = body(SCRIPT, "mode_switch() {", "mode_abort() {")
        target_check = switch.index('[ "$(slot_images "$active")" = "$BACKEND_IMAGE $FRONTEND_IMAGE" ]')
        self.assertLess(target_check, switch.index('running "vota-frontend-$new" || die'))

    def test_deploy_is_prepare_then_switch(self):
        deploy = body(SCRIPT, "mode_deploy() {", "case \"$MODE\" in")
        self.assertLess(deploy.index("mode_prepare"), deploy.index("mode_switch"))

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
    def test_startup_prefers_desired_images_from_the_mig_and_falls_back_to_the_template(self):
        self.assertIn("instance/attributes/$1", STARTUP)
        self.assertIn("desired_image vota-backend-image '${backend_image}'", STARTUP)
        self.assertIn("desired_image vota-frontend-image '${frontend_image}'", STARTUP)
        self.assertIn("@sha256:[a-f0-9]{64}$ ]]", STARTUP)          # giá trị sai dạng thì dùng template
        self.assertIn('BACKEND_IMAGE="$boot_backend" FRONTEND_IMAGE="$boot_frontend"', STARTUP)

    def test_terraform_leaves_the_desired_images_on_the_mig_alone(self):
        self.assertIn("ignore_changes = [target_size, all_instances_config]", MAIN)
        self.assertIn("all-instances-config update", DESIRED)
        self.assertIn("vota-backend-image=$BACKEND_REF,vota-frontend-image=$FRONTEND_REF", DESIRED)

    def test_startup_installs_and_runs_the_script_with_template_images(self):
        self.assertIn("/usr/local/sbin/vota-slot-deploy.sh", STARTUP)
        self.assertIn("${slot_deploy}", STARTUP)
        self.assertIn("vota-slot-deploy.sh boot", STARTUP)
        self.assertIn('slot_deploy = file("${path.module}/slot-deploy.sh")', MAIN)
        self.assertIn("slot_deploy        = local.slot_deploy", MAIN)

    def test_boot_env_has_everything_the_script_needs(self):
        for key in ("BACKEND_ENV_SECRET", "UVICORN_WORKERS", "UVICORN_GRACEFUL_SECONDS", "BACKEND_STOP_GRACE"):
            self.assertIn(f"{key}=", STARTUP)

    def test_app_cd_pins_policy_then_records_desired_images_then_rolls(self):
        deploy = body(APP_CD, "  deploy:\n")
        pin = deploy.index("pin-staging-ha-mig-opportunistic.sh")
        desired = deploy.index("set-staging-ha-desired-images.sh", pin)
        roll = deploy.index("roll-staging-ha-app-slots.sh", desired)
        verify = deploy.index("verify-staging-ha-app.sh", roll)
        self.assertLess(verify, deploy.index("Record last good"))

    def test_app_cd_never_runs_terraform(self):
        self.assertNotIn("deploy-staging-ha-app.sh", APP_CD)
        self.assertNotIn("setup-terraform", APP_CD)
        self.assertIn("scripts/deploy-staging-ha-app.sh", INFRA_CD)

    def test_infra_cd_does_not_roll_vms(self):
        self.assertNotIn("roll-staging-ha-app-slots.sh", INFRA_CD)

    def test_cd_rollback_runs_on_failure_and_on_cancel_and_resets_desired_images(self):
        rollback = body(APP_CD, "Roll back to last good")
        self.assertIn("if: ${{ failure() || cancelled() }}", rollback)
        self.assertLess(rollback.index("set-staging-ha-desired-images.sh"), rollback.index("roll-staging-ha-app-slots.sh"))

    def test_app_cd_gates_on_ci_before_building(self):
        for component, workflow in (("backend", "backend-ci.yml"), ("frontend", "frontend-ci-cd.yml")):
            ci = body(APP_CD, f"  {component}-ci:\n", f"  {component}-image:\n")
            self.assertIn(f"uses: ./.github/workflows/{workflow}", ci)
            image = body(APP_CD, f"  {component}-image:\n", "\n\n")
            self.assertIn(f"needs: [plan, {component}-ci]", image)
        self.assertIn("if: ${{ !cancelled() && !failure()", body(APP_CD, "  deploy:\n"))

    def test_ci_workflows_are_reusable_and_do_not_also_run_on_push(self):
        for name in ("backend-ci.yml", "frontend-ci-cd.yml", "crawler-ci-cd.yml"):
            text = (ROOT / ".github" / "workflows" / name).read_text()
            on = body(text, "\non:\n", "\npermissions:")
            self.assertIn("  workflow_call:", on, name)
            self.assertNotRegex(on, r"(?m)^  push:", name)
            self.assertNotIn("- closed", on, name)

    def test_changes_to_the_new_scripts_trigger_cd(self):
        for script in ("roll-staging-ha-app-slots.sh", "pin-staging-ha-mig-opportunistic.sh", "set-staging-ha-desired-images.sh",
                       "verify-staging-ha-app.sh"):
            self.assertIn(f"'scripts/{script}'", APP_CD, script)
        self.assertIn("'infra/terraform/environments/staging-ha/slot-deploy.sh'", APP_CD)

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

    def test_app_cd_holds_one_workflow_level_lock(self):
        # Mức workflow: run chờ bị thay bằng run mới hơn, và run đó tính lại mọi thay đổi so với last-good (content key).
        self.assertRegex(APP_CD, r"(?m)^concurrency:\n  group: staging-ha-app\n  cancel-in-progress: false")
        self.assertIn("image-key.sh", body(APP_CD, "  plan:\n", "  backend-ci:\n"))
        self.assertIn("backend_key", body(APP_CD, "Record last good"))

    def test_infra_cd_uses_its_own_lock(self):
        self.assertIn("group: staging-ha-infra", INFRA_CD)
        self.assertNotIn("group: staging-ha-app", INFRA_CD)

    def test_slot_script_serialises_runs_on_one_vm(self):
        self.assertIn("flock -w 1800 9", SCRIPT)
        for fn in ("mode_boot() {", "mode_prepare() {", "mode_switch() {", "mode_abort() {"):
            self.assertIn("acquire_lock", SCRIPT[SCRIPT.index(fn):SCRIPT.index(fn) + 60], fn)

    def test_background_drain_does_not_hold_the_lock(self):
        self.assertIn('9>- >'.replace("-", "&-"), SCRIPT[SCRIPT.index("drain_and_remove_old() {"):])


class RollVisitsEveryVm(unittest.TestCase):
    """Chạy roll-staging-ha-app-slots.sh thật với gcloud giả; ssh giả đọc stdin (script slot) như ssh thật.

    Lỗi thật 2026-10-12: vòng `while read ... <<< "$vms"` bị `gcloud compute ssh` nuốt stdin nên chỉ VM đầu tiên được cập nhật.
    """

    def _run(self, tmp, **extra):
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
    name="$3"
    sum=$(sha256sum | cut -c1-64)   # ssh thật đọc stdin: script slot đến qua stdin
    case "$*" in *"$sum"*) ;; *) echo "checksum lệch" >&2; exit 1 ;; esac
    last="${@: -1}"; mode="${last##* }"   # --command là tham số cuối, mode là từ cuối của nó
    echo "$mode $name" >> "$STUB_DIR/visited"
    if [ "$mode" = prepare ] && [ "$name" = "${FAIL_PREPARE:-}" ]; then exit 1; fi
    if [ "$mode" = prepare ]; then echo "SLOT_PREPARED host=$name slot=green"; exit 0; fi
    echo "SLOT_RESULT host=$name active=blue backend=$BACKEND_REF frontend=$FRONTEND_REF" ;;
esac
"""
        )
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        env = dict(os.environ, PATH=f"{stub.parent}:{os.environ['PATH']}", STUB_DIR=str(tmp),
                   BACKEND_REF=backend, FRONTEND_REF=frontend, GCP_PROJECT_ID="p", **extra)
        result = subprocess.run(["bash", str(ROOT / "scripts" / "roll-staging-ha-app-slots.sh")], env=env, capture_output=True, text=True)
        visited = (tmp / "visited").read_text().splitlines() if (tmp / "visited").exists() else []
        return result, [tuple(line.split()) for line in visited]

    def _visits(self, visited, mode):
        return [name for m, name in visited if m == mode]

    def test_every_running_vm_is_prepared_switched_and_checked(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            result, visited = self._run(pathlib.Path(d))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for mode in ("prepare", "switch", "report"):
            self.assertEqual(sorted(self._visits(visited, mode)), ["vm-a", "vm-b", "vm-c"], (mode, visited))
        # mọi VM chuẩn bị xong trước khi VM nào đổi traffic; VM đầu là canary
        modes = [m for m, _ in visited]
        self.assertLess(max(i for i, m in enumerate(modes) if m == "prepare"), modes.index("switch"))
        self.assertEqual(self._visits(visited, "switch")[0], "vm-a")
        self.assertNotIn("abort", modes)

    def test_failed_prepare_aborts_everywhere_and_switches_nothing(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            result, visited = self._run(pathlib.Path(d), FAIL_PREPARE="vm-b")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self._visits(visited, "switch"), [])
        self.assertEqual(sorted(self._visits(visited, "abort")), ["vm-a", "vm-b", "vm-c"])


class AlwaysOn(unittest.TestCase):
    """Staging-ha chạy 24/7 (2026-10-12): VM không được gắn lịch tắt/bật."""

    def test_no_vm_is_attached_to_a_schedule_policy(self):
        for name in ("bastion.tf", "crawler.tf", "patroni.tf", "weaviate.tf"):
            self.assertNotRegex((D / name).read_text(), r"(?m)^\s*resource_policies\s*=", name)


class DockerCredentialsPerJob(unittest.TestCase):
    """Các runner chung một HOME; `docker logout` của job khác xoá đăng nhập (403 khi đẩy image, 2026-10-12)."""

    def test_image_builds_use_their_own_docker_config(self):
        for wf in ("staging-ha-image-build.yml",):
            text = (ROOT / ".github" / "workflows" / wf).read_text()
            self.assertLess(text.index("DOCKER_CONFIG="), text.index("docker/login-action"), wf)


class ImageContentKey(unittest.TestCase):
    """Content key phải phủ mọi thứ Dockerfile COPY từ context, nếu không đổi file sẽ không build lại image."""

    def _copy_sources(self, dockerfile):
        sources = []
        for line in (ROOT / dockerfile).read_text().splitlines():
            line = line.strip()
            if line.startswith("COPY ") and "--from=" not in line:
                sources += line.split()[1:-1]
        return sources

    def test_every_copied_path_is_part_of_the_key(self):
        key_script = (ROOT / "scripts" / "ci" / "image-key.sh").read_text()
        for component, dockerfile in (("backend", "Dockerfile.backend"), ("frontend", "src/frontend/Dockerfile.web"),
                                      ("crawler", "Dockerfile.fresh-catalog")):
            paths = re.search(rf"{component}\)\s+paths=\(([^)]*)\)", key_script).group(1).split()
            self.assertIn(dockerfile.split("/")[-1] if component != "frontend" else "src/frontend", " ".join(paths), component)
            for src in self._copy_sources(dockerfile):
                self.assertTrue(any(src == p or src.startswith(p.rstrip("/") + "/") for p in paths), f"{component}: {src} không nằm trong key")


if __name__ == "__main__":
    unittest.main()
