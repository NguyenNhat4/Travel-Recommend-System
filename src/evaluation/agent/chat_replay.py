"""Chạy lại các hội thoại thử với backend đang chạy, ghi toàn văn ra markdown để đọc và đánh giá bằng mắt.

Không chấm tự động: dùng khi cần xem trợ lý trả lời thế nào với người dùng nhắn lộn xộn (không dấu, viết tắt, sai
chính tả, đổi ý). Dataset: `src/evaluation/datasets/chat_messy_v1.json` (`[{"id", "persona", "turns": [...]}]`).

    .venv/bin/python -m src.evaluation.agent.chat_replay --api-base-url http://127.0.0.1:8000 \
        --out /tmp/chat-replay.md [--only M03,M05] [--log backend.log]

`--log`: file log JSON của backend; có thì in thêm các node đã đi của từng lượt (theo `x-request-id`).
Giới hạn gửi tin là 10 tin/phút mỗi IP (`domain/auth/rate_limits.py`), nên mỗi lượt cách nhau ít nhất 6,5 giây.
"""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_DATASET = Path(__file__).resolve().parents[1] / "datasets" / "chat_messy_v1.json"
MIN_TURN_SECONDS = 6.5


def nodes_of(log: Path | None, request_id: str | None) -> list[str]:
    if log is None or not request_id or not log.exists():
        return []
    path = []
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        if f'"request_id":"{request_id}"' in line and '"event":"assistant.node"' in line:
            match = re.search(r'"node":"([a-z_]+)"', line)
            if match:
                path.append(match.group(1))
    return path


def send(base_url: str, text: str, conversation: str | None) -> tuple[dict, str | None, int, float]:
    body = {"message": text, **({"conversationId": conversation} if conversation else {})}
    request = urllib.request.Request(f"{base_url.rstrip('/')}/api/v1/assistant/itineraries",
                                     data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            return json.load(response), response.headers.get("x-request-id"), response.status, time.time() - started
    except urllib.error.HTTPError as error:
        return json.load(error), error.headers.get("x-request-id"), error.code, time.time() - started


def render(payload: dict, http_status: int, seconds: float, nodes: list[str]) -> list[str]:
    lines = [f"*{payload.get('status') or http_status} · {seconds:.1f}s · {' → '.join(nodes)}*", ""]
    text = payload.get("question") or payload.get("message") or (payload.get("error") or {}).get("message") or ""
    text = re.sub(r"\(product:[^)]+\)", "", text)
    lines += ["> " + line if line.strip() else ">" for line in text.strip().split("\n")]
    results = payload.get("searchResults") or {}
    if isinstance(results, dict) and results:
        lines += ["", "Thẻ: " + "; ".join(f"[{kind}] {item.get('name')}" for kind, items in results.items()
                                         for item in items)]
    itinerary = payload.get("itinerary")
    if itinerary:
        days = [f"N{day['day']}: " + " | ".join((slot.get("time") or "")[:3] + " " + (
            (slot.get("product") or {}).get("name") or slot.get("note") or "") for slot in day.get("slots", []))
                for day in itinerary.get("days", [])]
        lines += ["", "Lịch: " + " ‖ ".join(days),
                  f"Vé: {[f['product']['name'] for f in itinerary.get('flights') or []]} · KS: "
                  f"{[s['product']['name'] for s in itinerary.get('stays') or []]} · tổng "
                  f"{itinerary.get('estimatedTotal')} · bookable {itinerary.get('bookableCount')}"]
    warnings = sorted({w.get("code") for w in payload.get("warnings") or []} - {"PRODUCT_DROPPED_DUPLICATE"})
    if warnings:
        lines.append(f"Cảnh báo: {', '.join(warnings)}")
    if payload.get("clarificationForm"):
        lines.append("Form: (form điền sẵn)")
    if payload.get("suggestions"):
        lines.append("Nút: " + " · ".join(f"「{chip}」" for chip in payload["suggestions"]))
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--only", default="", help="Danh sách id, phân tách bằng dấu phẩy.")
    parser.add_argument("--log", type=Path, default=None)
    args = parser.parse_args()
    only = {item.strip() for item in args.only.split(",") if item.strip()}
    out: list[str] = []
    for conv in json.loads(args.dataset.read_text(encoding="utf-8")):
        if only and conv["id"] not in only:
            continue
        out += [f"## {conv['id']} — {conv['persona']}", ""]
        conversation = None
        for text in conv["turns"]:
            payload, request_id, status, seconds = send(args.api_base_url, text, conversation)
            conversation = payload.get("conversationId") or conversation
            out += [f"**Người dùng:** {text}", ""] + render(payload, status, seconds,
                                                             nodes_of(args.log, request_id)) + [""]
            print(conv["id"], repr(text)[:40], payload.get("status") or status, f"{seconds:.1f}s", flush=True)
            args.out.write_text("\n".join(out), encoding="utf-8")
            time.sleep(max(0.3, MIN_TURN_SECONDS - seconds))
        out.append("")
    args.out.write_text("\n".join(out), encoding="utf-8")


if __name__ == "__main__":
    main()
