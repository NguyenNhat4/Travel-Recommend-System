import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


COLLECTOR_PATH = Path(__file__).parents[1] / "vota-container-disk-collector.py"
SPEC = importlib.util.spec_from_file_location("vota_container_disk_collector", COLLECTOR_PATH)
COLLECTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COLLECTOR)


def sized_file(directory, name, size):
    path = Path(directory) / name
    path.write_bytes(b"x" * size)
    return str(path)


class ContainerDiskRecordTest(unittest.TestCase):
    def test_log_bytes_sums_active_and_rotated_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = sized_file(tmp, "abc-json.log", 100)
            sized_file(tmp, "abc-json.log.1", 40)
            sized_file(tmp, "other-json.log", 999)
            self.assertEqual(COLLECTOR.log_bytes(log), 140)

    def test_log_bytes_missing_path_is_zero(self):
        self.assertEqual(COLLECTOR.log_bytes(""), 0)
        self.assertEqual(COLLECTOR.log_bytes("/nonexistent/x-json.log"), 0)

    def test_directory_bytes_walks_nested_files_and_skips_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            nested = Path(tmp) / "a" / "b"
            nested.mkdir(parents=True)
            (nested / "f").write_bytes(b"x" * 10_000)
            os.symlink(str(nested / "f"), str(Path(tmp) / "link"))
            allocated = COLLECTOR.directory_bytes(tmp)
            self.assertGreaterEqual(allocated, 10_000)
            self.assertLess(allocated, 40_000)

    def test_directory_bytes_unreadable_path_is_zero(self):
        self.assertEqual(COLLECTOR.directory_bytes("/nonexistent/dir"), 0)

    def test_record_totals_writable_log_and_named_volume_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = sized_file(tmp, "abc-json.log", 10)
            inspect = {
                "Id": "abc123",
                "Name": "/vota-weaviate",
                "LogPath": log,
                "SizeRw": 1000,
                "SizeRootFs": 5_000_000,
                "Config": {"Image": "weaviate:1"},
                "State": {"Status": "running"},
                "Mounts": [
                    {"Type": "volume", "Name": "weaviate_data", "Source": "/v/weaviate_data"},
                    {"Type": "bind", "Source": "/srv/vota/logs"},
                ],
            }
            record = COLLECTOR.build_record(inspect, volume_size=lambda source: 70_000)
            self.assertEqual(record["event"], "container_disk")
            self.assertEqual(record["container_name"], "vota-weaviate")
            self.assertEqual(record["writable_bytes"], 1000)
            self.assertEqual(record["log_bytes"], 10)
            self.assertEqual(record["volume_bytes"], 70_000)
            self.assertEqual(record["total_bytes"], 71_010)
            self.assertEqual(record["status"], "running")

    def test_record_tolerates_null_size_and_mounts(self):
        record = COLLECTOR.build_record(
            {"Name": "/vota-redis", "SizeRw": None, "Mounts": None, "State": {}, "Config": {}},
            volume_size=lambda source: 1,
        )
        self.assertEqual(record["writable_bytes"], 0)
        self.assertEqual(record["volume_bytes"], 0)
        self.assertEqual(record["total_bytes"], 0)

    def test_shared_volume_is_measured_once_per_cycle(self):
        calls = []

        def measure(source):
            calls.append(source)
            return 5

        cache = {}
        mounts = [{"Type": "volume", "Name": "v", "Source": "/v/v"}]
        for name in ("/a", "/b"):
            COLLECTOR.build_record(
                {"Name": name, "SizeRw": 0, "Mounts": mounts, "State": {}, "Config": {}},
                volume_size=measure,
                cache=cache,
            )
        self.assertEqual(calls, ["/v/v"])


if __name__ == "__main__":
    unittest.main()
