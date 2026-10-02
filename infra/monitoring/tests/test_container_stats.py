import importlib.util
import json
import unittest
from pathlib import Path


COLLECTOR_PATH = Path(__file__).parents[1] / "vota-container-stats-collector.py"
SPEC = importlib.util.spec_from_file_location("vota_container_stats_collector", COLLECTOR_PATH)
COLLECTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COLLECTOR)

LABELS = {"project_id": "p", "instance_id": "123", "zone": "asia-southeast1-a"}


class ParseTest(unittest.TestCase):
    def test_parse_size_handles_binary_and_decimal_units(self):
        self.assertEqual(COLLECTOR.parse_size("12.5MiB"), 13107200)
        self.assertEqual(COLLECTOR.parse_size("1GiB"), 1024**3)
        self.assertEqual(COLLECTOR.parse_size("2kB"), 2000)
        self.assertEqual(COLLECTOR.parse_size("0B"), 0)

    def test_parse_size_unknown_text_is_zero(self):
        self.assertEqual(COLLECTOR.parse_size("--"), 0)
        self.assertEqual(COLLECTOR.parse_size("12 parsecs"), 0)

    def test_parse_percent(self):
        self.assertEqual(COLLECTOR.parse_percent("12.34%"), 12.34)
        self.assertEqual(COLLECTOR.parse_percent("--"), 0.0)

    def test_parse_stats_line(self):
        line = json.dumps(
            {"Name": "vota-backend", "CPUPerc": "35.20%", "MemUsage": "512MiB / 7.76GiB", "MemPerc": "6.44%"}
        )
        sample = COLLECTOR.parse_stats_line(line)
        self.assertEqual(sample["container_name"], "vota-backend")
        self.assertEqual(sample["cpu_percent"], 35.2)
        self.assertEqual(sample["memory_bytes"], 512 * 1024**2)
        self.assertGreater(sample["memory_limit_bytes"], 7 * 1024**3)
        self.assertEqual(sample["memory_percent"], 6.44)


class PayloadTest(unittest.TestCase):
    def test_three_gauge_series_per_container(self):
        samples = [
            {"container_name": "vota-redis", "cpu_percent": 1.0, "memory_bytes": 100, "memory_percent": 2.0},
            {"container_name": "", "cpu_percent": 9, "memory_bytes": 9, "memory_percent": 9},
        ]
        payload = COLLECTOR.build_time_series(samples, LABELS, "2026-10-02T00:00:00.000000Z")
        series = payload["timeSeries"]
        self.assertEqual(len(series), 3)
        self.assertEqual(
            {item["metric"]["type"] for item in series},
            {
                "custom.googleapis.com/vota/container/cpu_percent",
                "custom.googleapis.com/vota/container/memory_bytes",
                "custom.googleapis.com/vota/container/memory_percent",
            },
        )
        first = series[0]
        self.assertEqual(first["metric"]["labels"], {"container_name": "vota-redis"})
        self.assertEqual(first["resource"], {"type": "gce_instance", "labels": LABELS})
        self.assertEqual(first["metricKind"], "GAUGE")
        self.assertEqual(first["points"][0]["value"], {"doubleValue": 1.0})

    def test_empty_samples_give_empty_payload(self):
        self.assertEqual(COLLECTOR.build_time_series([], LABELS, "t"), {"timeSeries": []})


if __name__ == "__main__":
    unittest.main()
