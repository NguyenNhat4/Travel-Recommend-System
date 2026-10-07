#!/usr/bin/env python3
"""Probe cụm Patroni, chạy mỗi phút trên từng node DB (cron). Ghi một dòng JSON vào OUT ("-" = stdout);
Ops Agent đẩy lên Cloud Logging, log-based metric trong infra/terraform/environments/staging-ha/patroni_monitoring.tf
biến status != ok thành cảnh báo.

status:
  ok          có leader và ít nhất một replica đang streaming
  no_replica  có leader nhưng KHÔNG còn replica: sau failover hệ thống là một DB đơn lẻ; mất nốt là mất dữ liệu
  no_leader   không có leader (đang bầu cử hoặc mất đa số etcd)
  broken      không hỏi được Patroni REST trên node này
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

LEADER_ROLES = {"leader", "master", "standby_leader"}
REPLICA_ROLES = {"replica", "sync_standby", "quorum_standby"}


def classify(cluster: dict) -> dict:
    members = cluster.get("members") or []
    leaders = [m for m in members if m.get("role") in LEADER_ROLES]
    replicas = [m for m in members if m.get("role") in REPLICA_ROLES and m.get("state") == "streaming"]
    if not leaders:
        status = "no_leader"
    elif not replicas:
        status = "no_replica"
    else:
        status = "ok"
    lags = [m.get("lag") for m in replicas if isinstance(m.get("lag"), int)]
    return {
        "status": status,
        "leader": leaders[0].get("name") if leaders else None,
        "members": len(members),
        "streaming_replicas": len(replicas),
        "sync_standby": any(m.get("role") == "sync_standby" for m in members),
        "max_lag_bytes": max(lags) if lags else 0,
    }


def fetch(url: str, timeout: float = 3.0) -> dict:
    with urllib.request.urlopen(url.rstrip("/") + "/cluster", timeout=timeout) as response:
        return json.load(response)


def main() -> int:
    url = os.environ.get("PATRONI_URL", "http://127.0.0.1:8008")
    out = os.environ.get("OUT", "/var/log/vota/patroni-cluster.jsonl")
    node = os.environ.get("PATRONI_NAME", os.uname().nodename)
    try:
        body = classify(fetch(url))
    except Exception:  # noqa: BLE001 — mọi lỗi đều là "không hỏi được Patroni"
        body = {"status": "broken", "leader": None, "members": 0, "streaming_replicas": 0,
                "sync_standby": False, "max_lag_bytes": 0}
    line = json.dumps({"event": "patroni_cluster", "probe": "patroni-cluster", "node": node,
                       "ts": int(time.time()), **body}, separators=(",", ":"))
    if out == "-":
        print(line)
    else:
        with open(out, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
