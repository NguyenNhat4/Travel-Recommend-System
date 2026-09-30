#!/usr/bin/env python3
"""Persist Docker lifecycle events before --rm containers disappear."""

import json
import os
import select
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


EVENT_LOG = Path(os.environ.get("VOTA_DOCKER_EVENT_LOG", "/var/log/vota/docker-events.jsonl"))
HEARTBEAT_SECONDS = int(os.environ.get("VOTA_DOCKER_EVENT_HEARTBEAT_SECONDS", "60"))


def now():
    return datetime.now(timezone.utc).isoformat()


def container_class(name, image):
    if name == "vota-fresh-catalog" or "vota-fresh-catalog@" in image:
        return "crawler"
    return "service"


def normalise_event(event):
    actor = event.get("Actor") or {}
    attrs = actor.get("Attributes") or {}
    name = attrs.get("name", "")
    image = attrs.get("image", "")
    action = event.get("Action") or event.get("status") or "unknown"
    exit_code = attrs.get("exitCode")
    try:
        exit_code = int(exit_code) if exit_code not in (None, "") else None
    except (TypeError, ValueError):
        exit_code = None
    oom_killed = str(attrs.get("oomKilled", "false")).lower() == "true"
    if action == "die" and oom_killed:
        event_kind = "oom"
    else:
        event_kind = action
    return {
        "event": event_kind,
        "container_name": name,
        "container_id": actor.get("ID", ""),
        "image": image,
        "container_class": container_class(name, image),
        "exit_code": exit_code,
        "oom_killed": oom_killed,
        "timestamp": event.get("timeNano") or event.get("time") or now(),
    }


def write_record(handle, record):
    handle.write(json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n")
    handle.flush()


def run():
    EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with EVENT_LOG.open("a", encoding="utf-8") as output:
        last_heartbeat = 0.0
        while True:
            process = subprocess.Popen(
                ["docker", "events", "--format", "{{json .}}", "--filter", "type=container"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            try:
                while process.poll() is None:
                    ready, _, _ = select.select([process.stdout], [], [], 1.0)
                    if ready:
                        line = process.stdout.readline()
                        if line:
                            try:
                                event = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            action = event.get("Action") or event.get("status")
                            if action in {"die", "stop", "kill", "oom", "restart"}:
                                write_record(output, normalise_event(event))
                    current = time.monotonic()
                    if current - last_heartbeat >= HEARTBEAT_SECONDS:
                        write_record(output, {"event": "heartbeat", "watcher": "docker-events", "timestamp": now()})
                        last_heartbeat = current
                write_record(output, {"event": "docker_events_disconnected", "watcher": "docker-events", "timestamp": now()})
            finally:
                if process.poll() is None:
                    process.terminate()
                process.wait()
            time.sleep(5)


if __name__ == "__main__":
    run()
