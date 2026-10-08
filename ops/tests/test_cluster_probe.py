"""cluster_probe.py: phân loại trạng thái cụm Patroni từ /cluster. Chạy: python3 -m pytest ops/tests/test_cluster_probe.py

Use case (docs/plan/2026-10-07-ha-vung-crawler-rolling.md §2, use case 3): lúc 03:12 zone a mất, Patroni nâng replica ở
zone b. Từ đó cụm chỉ còn MỘT DB; nếu không ai biết, 5 giờ sau zone b gặp sự cố đĩa là mất cả đơn đã thanh toán.
Probe phải báo no_replica ngay khi chỉ còn leader để cảnh báo kêu và người vận hành dựng node thay thế.
"""
import importlib.util
import json
import pathlib
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

SPEC = importlib.util.spec_from_file_location("cluster_probe", pathlib.Path(__file__).parents[1] / "patroni" / "cluster_probe.py")
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def member(name, role, state="running", lag=None):
    m = {"name": name, "role": role, "state": state}
    if lag is not None:
        m["lag"] = lag
    return m


def test_ok_with_leader_and_streaming_sync_standby():
    result = probe.classify({"members": [member("a", "leader"), member("b", "sync_standby", "streaming", 0)]})
    assert result["status"] == "ok" and result["sync_standby"] is True and result["leader"] == "a"


def test_no_replica_after_failover_leaves_a_single_node():
    result = probe.classify({"members": [member("b", "leader")]})
    assert (result["status"], result["streaming_replicas"]) == ("no_replica", 0)


def test_replica_that_is_not_streaming_does_not_count():
    result = probe.classify({"members": [member("a", "leader"), member("b", "replica", "running")]})
    assert result["status"] == "no_replica"


def test_no_leader_during_election_or_quorum_loss():
    assert probe.classify({"members": [member("a", "replica", "streaming"), member("b", "replica", "streaming")]})["status"] == "no_leader"
    assert probe.classify({"members": []})["status"] == "no_leader"


def test_max_lag_reported():
    result = probe.classify({"members": [member("a", "leader"), member("b", "replica", "streaming", 2048)]})
    assert result["max_lag_bytes"] == 2048


def _serve(payload, status=200):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(status)
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())

        def log_message(self, *_):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def test_main_writes_one_json_line(tmp_path, monkeypatch):
    server = _serve({"members": [member("a", "leader"), member("b", "sync_standby", "streaming", 0)]})
    out = tmp_path / "p.jsonl"
    monkeypatch.setenv("PATRONI_URL", f"http://127.0.0.1:{server.server_port}")
    monkeypatch.setenv("OUT", str(out))
    monkeypatch.setenv("PATRONI_NAME", "node-a")
    assert probe.main() == 0
    server.shutdown()
    row = json.loads(out.read_text().strip())
    assert row["event"] == "patroni_cluster" and row["status"] == "ok" and row["node"] == "node-a"


def test_unreachable_patroni_is_broken(tmp_path, monkeypatch):
    out = tmp_path / "p.jsonl"
    monkeypatch.setenv("PATRONI_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("OUT", str(out))
    probe.main()
    assert json.loads(out.read_text().strip())["status"] == "broken"
