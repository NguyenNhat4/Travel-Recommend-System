"""CdpClientPort đọc event từ JSONL (mock). Bản Postgres (cdp.events qua role cdp_reader) thay file này, cùng interface."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone


class LocalCdpClient:
    def __init__(self, events_path: str | None):
        self._by_user: dict[str, list[dict]] = defaultdict(list)
        self._all: list[dict] = []
        if events_path:
            with open(events_path, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        e = json.loads(line)
                        self._all.append(e)
                        self._by_user[e["cdpUserId"]].append(e)

    def events_for_user(self, cdp_user_id: str) -> list[dict]:
        return list(self._by_user.get(cdp_user_id, []))

    def purchase_events(self, since_days: int = 730) -> list[dict]:
        cut = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()
        return [e for e in self._all if e.get("eventName") == "purchase" and str(e["timestamp"]) >= cut]

    # ghi purchase khi checkout (feedback loop) — bản mock chỉ giữ trong bộ nhớ
    def record_events(self, events: list[dict]) -> None:
        for e in events:
            self._all.append(e)
            self._by_user[e["cdpUserId"]].append(e)
