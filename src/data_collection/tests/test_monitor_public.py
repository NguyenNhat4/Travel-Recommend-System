import sys
import types
import unittest

# Host policy tests do not need the collector dependencies. Keep this test runnable
# in a minimal checkout where the full data-collection requirements are not installed;
# stub only a package that is really missing so other tests in the same run keep the real one.
try:
    import protego  # noqa: F401
except ImportError:
    protego = types.ModuleType("protego")
    protego.Protego = object
    sys.modules["protego"] = protego
try:
    import rapidfuzz  # noqa: F401
except ImportError:
    rapidfuzz = types.ModuleType("rapidfuzz")
    rapidfuzz.fuzz = types.SimpleNamespace()
    rapidfuzz.process = types.SimpleNamespace()
    sys.modules["rapidfuzz"] = rapidfuzz

import monitor


class MonitorHostPolicy(unittest.TestCase):
    def test_local_mode_accepts_only_local_hosts(self):
        self.assertTrue(monitor.host_allowed("127.0.0.1:8765"))
        self.assertTrue(monitor.host_allowed("localhost:8765"))
        self.assertFalse(monitor.host_allowed("203.0.113.10:8765"))

    def test_public_mode_accepts_external_host(self):
        self.assertTrue(monitor.host_allowed("203.0.113.10:8765", allow_public=True))


if __name__ == "__main__":
    unittest.main()
