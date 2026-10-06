"""VM không IP public phải có đường ra (NAT) và secret phải có quyền đọc; template chỉ tạo khi secret đã có giá trị.

Chạy: python3 infra/terraform/environments/staging-ha/tests/test_egress_and_secrets.py
"""
import pathlib
import re
import unittest

D = pathlib.Path(__file__).resolve().parents[1]
read = lambda name: (D / name).read_text()  # noqa: E731
MAIN, NETWORK, SECRETS, WEAVIATE = read("main.tf"), read("network.tf"), read("secrets.tf"), read("weaviate.tf")


def block(text: str, kind: str, name: str) -> str:
    match = re.search(rf'resource "{kind}" "{name}" \{{(.*?)\n\}}\n', text, re.S)
    assert match, f"thiếu resource {kind}.{name}"
    return match.group(1)


class Egress(unittest.TestCase):
    def test_app_template_has_no_public_ip(self):
        template = block(MAIN, "google_compute_instance_template", "app")
        self.assertNotIn("access_config", template)

    def test_cloud_nat_covers_all_subnets(self):
        nat = block(NETWORK, "google_compute_router_nat", "egress")
        self.assertIn("ALL_SUBNETWORKS_ALL_IP_RANGES", nat)

    def test_vms_wait_for_nat(self):
        self.assertIn("google_compute_router_nat.egress", block(MAIN, "google_compute_instance_template", "app"))
        self.assertIn("google_compute_router_nat.egress", block(WEAVIATE, "google_compute_instance", "weaviate"))


class Secrets(unittest.TestCase):
    def test_app_service_account_can_read_env_secret(self):
        iam = block(SECRETS, "google_secret_manager_secret_iam_member", "backend_env_reader")
        self.assertIn("roles/secretmanager.secretAccessor", iam)
        self.assertIn("var.app_service_account_email", iam)

    def test_secret_values_are_never_in_terraform(self):
        # Không có google_secret_manager_secret_version resource: giá trị nạp tay, không vào state.
        self.assertNotRegex(SECRETS, r'resource "google_secret_manager_secret_version"')

    def test_template_waits_for_secret_version_when_required(self):
        self.assertIn("data.google_secret_manager_secret_version.backend_env", block(MAIN, "google_compute_instance_template", "app"))
        self.assertIn("var.require_secret_versions", SECRETS)


if __name__ == "__main__":
    unittest.main()
