import importlib.util
from pathlib import Path


WATCHER_PATH = Path(__file__).parents[1] / "vota-docker-event-watcher.py"
SPEC = importlib.util.spec_from_file_location("vota_docker_event_watcher", WATCHER_PATH)
WATCHER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WATCHER)


def test_event_datetime_is_utc_plus_seven():
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

    assert record["datetime"] == "2026-09-30T23:00:00+07:00"


def test_event_datetime_falls_back_to_local_now_for_missing_docker_time():
    record = WATCHER.normalise_event(
        {
            "Action": "stop",
            "Actor": {"Attributes": {"name": "vota-backend", "image": "backend:image"}},
        }
    )

    assert record["datetime"].endswith("+07:00")
