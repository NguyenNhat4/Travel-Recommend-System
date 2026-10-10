"""`run_daily_docker.sh prune-images`: sau deploy job cào, giữ image vừa deploy + một bản trước, xoá image cũ hơn của cùng
repository (đĩa VM đầy dần vì mỗi lần deploy để lại image vài GB, 06/10)."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

RUNNER = Path(__file__).resolve().parents[1] / "run_daily_docker.sh"
# 4 image của repo: sha:new (vừa deploy), sha:prev, sha:old1, sha:old2 (cũ nhất).
FAKE_DOCKER = r"""#!/usr/bin/env bash
echo "$*" >> "$DOCKER_LOG"
case "$1 $2" in
  "image inspect") echo "sha256:new" ;;
  "image ls")
    if [[ "$*" == *--format* ]]; then
      printf '%s\n' "2026-10-06 15:00:00 +0700 +07|sha256:new" "2026-10-03 10:00:00 +0700 +07|sha256:prev" \
                    "2026-09-30 10:00:00 +0700 +07|sha256:old1" "2026-09-25 10:00:00 +0700 +07|sha256:old2"
    else
      printf '%s\n' sha256:new sha256:prev sha256:old1 sha256:old2
    fi ;;
esac
exit 0
"""


class PruneImagesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "bin").mkdir()
        docker = root / "bin" / "docker"
        docker.write_text(FAKE_DOCKER)
        docker.chmod(0o755)
        self.log = root / "docker.log"
        self.env = {"PATH": f"{root / 'bin'}:/usr/bin:/bin", "HOME": str(root), "DOCKER_LOG": str(self.log)}

    def tearDown(self):
        self.tmp.cleanup()

    def run_prune(self, *args):
        return subprocess.run(["bash", str(RUNNER), "prune-images", *args], env=self.env,
                              capture_output=True, text=True, timeout=30)

    def test_keeps_current_and_previous_removes_older_images_of_the_same_repo(self):
        result = self.run_prune("asia-docker.pkg.dev/p/r/fresh@sha256:abc")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.log.read_text().splitlines()
        removed = [c.split()[1] for c in calls if c.startswith("rmi ")]
        self.assertEqual(sorted(removed), ["sha256:old1", "sha256:old2"])
        self.assertIn("image ls asia-docker.pkg.dev/p/r/fresh --no-trunc --quiet", calls)  # chỉ repo của job cào
        self.assertIn("image prune -f", calls)

    def test_requires_the_deployed_image(self):
        result = self.run_prune()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists() and "rmi" in self.log.read_text())


if __name__ == "__main__":
    unittest.main()
