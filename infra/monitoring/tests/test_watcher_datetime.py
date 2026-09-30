import importlib.util
import unittest
from pathlib import Path


WATCHER_PATH = Path(__file__).parents[1] / "vota-docker-event-watcher.py"
SPEC = importlib.util.spec_from_file_location("vota_docker_event_watcher", WATCHER_PATH)
WATCHER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WATCHER)


class WatcherDatetimeTest(unittest.TestCase):
    def test_event_datetime_is_utc_plus_seven(self):
        event = {
            "Action": "die",
            "timeNano": 1790784000 * 1_000_000_000,
            "Actor": {
                "ID": "container-id",
                "Attributes": {
                    "name": "vota-frontend",
                    "image": "frontend:image",
                },
            },
        }

        record = WATCHER.normalise_event(event)

        self.assertEqual(record["datetime"], "2026-09-30T23:00:00+07:00")

    def test_event_datetime_falls_back_to_local_now_for_missing_docker_time(self):
        record = WATCHER.normalise_event(
            {
                "Action": "stop",
                "Actor": {"Attributes": {"name": "vota-backend", "image": "backend:image"}},
            }
        )

        self.assertTrue(record["datetime"].endswith("+07:00"))


if __name__ == "__main__":
    unittest.main()
