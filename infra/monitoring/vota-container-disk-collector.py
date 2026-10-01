#!/usr/bin/env python3
"""Periodically record how much disk each Docker container uses.

One JSON line per container per cycle goes to the log file the Ops Agent tails:
  writable_bytes  container writable layer (docker inspect --size, SizeRw)
  log_bytes       json-file log plus its rotated files
  volume_bytes    named volumes mounted into the container (bind mounts are excluded)
  total_bytes     sum of the three

Image layers are shared between containers and are not counted. A named volume mounted by
several containers is counted in each of them, so per-container totals are not additive.
"""

import glob
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


OUTPUT_LOG = Path(os.environ.get("VOTA_CONTAINER_DISK_LOG", "/var/log/vota/container-disk.jsonl"))
INTERVAL_SECONDS = int(os.environ.get("VOTA_CONTAINER_DISK_INTERVAL_SECONDS", "300"))
COMMAND_TIMEOUT_SECONDS = int(os.environ.get("VOTA_CONTAINER_DISK_COMMAND_TIMEOUT_SECONDS", "180"))
VIETNAM_TZ = timezone(timedelta(hours=7))


def local_datetime():
    return datetime.now(VIETNAM_TZ).isoformat()


def log_bytes(log_path):
    """Size of the json-file log and its rotations (<path>, <path>.1, ...)."""
    if not log_path:
        return 0
    total = 0
    for path in glob.glob(glob.escape(log_path) + "*"):
        try:
            total += os.stat(path).st_size
        except OSError:
            continue
    return total


def directory_bytes(path):
    """Disk space allocated to a directory tree (st_blocks), without following symlinks."""
    total = 0
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        info = entry.stat(follow_symlinks=False)
                        total += info.st_blocks * 512
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                    except OSError:
                        continue
        except OSError:
            continue
    return total


def build_record(inspect, volume_size=directory_bytes, cache=None):
    """Turn one `docker inspect --size` object into a container_disk record."""
    cache = {} if cache is None else cache
    writable = inspect.get("SizeRw") or 0
    volume_total = 0
    for mount in inspect.get("Mounts") or []:
        if mount.get("Type") != "volume":
            continue
        source = mount.get("Source")
        if not source:
            continue
        if source not in cache:
            cache[source] = volume_size(source)
        volume_total += cache[source]
    logs = log_bytes(inspect.get("LogPath") or "")
    return {
        "event": "container_disk",
        "container_name": (inspect.get("Name") or "").lstrip("/"),
        "container_id": inspect.get("Id", ""),
        "image": (inspect.get("Config") or {}).get("Image", ""),
        "status": (inspect.get("State") or {}).get("Status", ""),
        "writable_bytes": writable,
        "log_bytes": logs,
        "volume_bytes": volume_total,
        "total_bytes": writable + logs + volume_total,
        "datetime": local_datetime(),
    }


def docker_json(args):
    result = subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        timeout=COMMAND_TIMEOUT_SECONDS,
        check=True,
    )
    return result.stdout


def collect():
    ids = docker_json(["container", "ls", "--all", "--quiet", "--no-trunc"]).split()
    if not ids:
        return []
    inspected = json.loads(docker_json(["container", "inspect", "--size", *ids]))
    cache = {}
    return [build_record(item, cache=cache) for item in inspected]


def write_records(handle, records):
    for record in records:
        handle.write(json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n")
    handle.flush()


def run():
    OUTPUT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_LOG.open("a", encoding="utf-8") as output:
        while True:
            started = time.monotonic()
            try:
                write_records(output, collect())
            except (OSError, subprocess.SubprocessError, ValueError) as error:
                write_records(
                    output,
                    [{"event": "container_disk_error", "error": str(error)[:300], "datetime": local_datetime()}],
                )
                print(f"container disk collection failed: {error}", file=sys.stderr)
            time.sleep(max(1.0, INTERVAL_SECONDS - (time.monotonic() - started)))


if __name__ == "__main__":
    run()
