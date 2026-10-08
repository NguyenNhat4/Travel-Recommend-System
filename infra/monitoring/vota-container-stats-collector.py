#!/usr/bin/env python3
"""Periodically publish per-container CPU and memory as Cloud Monitoring custom metrics.

`docker stats --no-stream` is sampled every interval and written as GAUGE points on the
gce_instance resource of this VM, one series per container_name:
  custom.googleapis.com/vota/container/cpu_percent     100 = one fully used vCPU
  custom.googleapis.com/vota/container/memory_bytes    working-set memory in bytes
  custom.googleapis.com/vota/container/memory_percent  memory_bytes / memory limit (VM RAM if unlimited)

Only the Python standard library is used; the access token comes from the metadata server,
so the VM service account needs the same Monitoring write access the Ops Agent already has.
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone


INTERVAL_SECONDS = int(os.environ.get("VOTA_CONTAINER_STATS_INTERVAL_SECONDS", "60"))
COMMAND_TIMEOUT_SECONDS = int(os.environ.get("VOTA_CONTAINER_STATS_COMMAND_TIMEOUT_SECONDS", "60"))
METADATA_URL = "http://metadata.google.internal/computeMetadata/v1/"
MONITORING_URL = "https://monitoring.googleapis.com/v3/projects/{project}/timeSeries"
METRIC_PREFIX = "custom.googleapis.com/vota/container/"
METRICS = ("cpu_percent", "memory_bytes", "memory_percent")

SIZE_UNITS = {
    "b": 1,
    "kb": 1000,
    "mb": 1000**2,
    "gb": 1000**3,
    "tb": 1000**4,
    "kib": 1024,
    "mib": 1024**2,
    "gib": 1024**3,
    "tib": 1024**4,
}
SIZE_PATTERN = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*([A-Za-z]+)\s*$")


def parse_percent(text):
    """'12.34%' -> 12.34; anything unreadable (docker prints '--') -> 0.0."""
    try:
        return float(str(text).strip().rstrip("%"))
    except ValueError:
        return 0.0


def parse_size(text):
    """'12.5MiB' -> bytes; unknown unit or text -> 0."""
    match = SIZE_PATTERN.match(str(text))
    if not match:
        return 0
    unit = SIZE_UNITS.get(match.group(2).lower())
    return int(float(match.group(1)) * unit) if unit else 0


def parse_stats_line(line):
    """One `docker stats --format '{{json .}}'` line -> sample dict."""
    raw = json.loads(line)
    used, _, limit = str(raw.get("MemUsage", "")).partition("/")
    return {
        "container_name": raw.get("Name", ""),
        "cpu_percent": parse_percent(raw.get("CPUPerc")),
        "memory_bytes": parse_size(used),
        "memory_limit_bytes": parse_size(limit),
        "memory_percent": parse_percent(raw.get("MemPerc")),
    }


def build_time_series(samples, resource_labels, end_time):
    """Samples -> Cloud Monitoring timeSeries.create payload."""
    series = []
    for sample in samples:
        if not sample["container_name"]:
            continue
        for metric in METRICS:
            series.append(
                {
                    "metric": {
                        "type": METRIC_PREFIX + metric,
                        "labels": {"container_name": sample["container_name"]},
                    },
                    "resource": {"type": "gce_instance", "labels": dict(resource_labels)},
                    "metricKind": "GAUGE",
                    "valueType": "DOUBLE",
                    "points": [
                        {
                            "interval": {"endTime": end_time},
                            "value": {"doubleValue": float(sample[metric])},
                        }
                    ],
                }
            )
    return {"timeSeries": series}


def metadata(path):
    request = urllib.request.Request(METADATA_URL + path, headers={"Metadata-Flavor": "Google"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.read().decode()


def resource_labels():
    return {
        "project_id": metadata("project/project-id"),
        "instance_id": metadata("instance/id"),
        "zone": metadata("instance/zone").rsplit("/", 1)[-1],
    }


class TokenCache:
    def __init__(self):
        self.token = ""
        self.expires_at = 0.0

    def get(self):
        if time.time() >= self.expires_at - 60:
            payload = json.loads(metadata("instance/service-accounts/default/token"))
            self.token = payload["access_token"]
            self.expires_at = time.time() + int(payload.get("expires_in", 300))
        return self.token


def collect():
    result = subprocess.run(
        ["docker", "stats", "--no-stream", "--format", "{{json .}}"],
        capture_output=True,
        text=True,
        timeout=COMMAND_TIMEOUT_SECONDS,
        check=True,
    )
    return [parse_stats_line(line) for line in result.stdout.splitlines() if line.strip()]


def publish(payload, labels, tokens):
    if not payload["timeSeries"]:
        return
    request = urllib.request.Request(
        MONITORING_URL.format(project=labels["project_id"]),
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {tokens.get()}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30):
        pass


def run():
    labels = resource_labels()
    tokens = TokenCache()
    while True:
        started = time.monotonic()
        try:
            end_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            publish(build_time_series(collect(), labels, end_time), labels, tokens)
        except urllib.error.HTTPError as error:
            print(f"container stats publish failed: HTTP {error.code} {error.read()[:300]!r}", file=sys.stderr)
        except (OSError, subprocess.SubprocessError, ValueError, KeyError) as error:
            print(f"container stats collection failed: {error}", file=sys.stderr)
        time.sleep(max(1.0, INTERVAL_SECONDS - (time.monotonic() - started)))


if __name__ == "__main__":
    run()
