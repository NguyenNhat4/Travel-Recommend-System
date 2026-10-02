"""Cảnh báo khi lượt lỗi (CP7) và SLA (CP8) của docs/plan/2026-09-28-normalize-on-dinh-theo-buoc.md.

Tương đương `on_failure_callback` và SLA miss của Airflow, nhưng không dùng Airflow. Chưa có kênh gửi ra ngoài (người yêu cầu
2026-09-28: để sau; kênh nào cũng cần secret mới → đề xuất PRD). Cảnh báo được ghi ra file và monitor hiện:

- `<lượt>/alerts.jsonl`: cảnh báo của lượt đó;
- `<state>/alerts.jsonl`: mọi cảnh báo, mới nhất ở cuối (monitor đọc cho trang Tổng quan);
- `<state>/alerts_seen.json`: chữ ký cảnh báo đã báo → lúc báo, để chống báo dồn (`alert.cooldownHours`; SLA: mỗi quy tắc
  một lần mỗi ngày). Cảnh báo bị chặn vẫn được ghi file, kèm `suppressed: true`.

`on_run_finished` chạy sau khi lượt ghi kết thúc; `check_sla` chạy ở mỗi cron tick (kể cả tick rảnh, không cần DB). Cả hai là
best effort: lỗi ở đây không đổi trạng thái lượt.
"""
from __future__ import annotations

import json
import os
import re
import statistics
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

VN = timezone(timedelta(hours=7))
ALERTS = "alerts.jsonl"
SEEN = "alerts_seen.json"
KEEP = 2000  # số cảnh báo giữ trong <state>/alerts.jsonl
FINISHED_OK = ("ok", "partial")
POST_CRAWL = ("normalise", "validate", "db", "index")
SECRET_ENV = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|DATABASE_URL)$")
DSN_PASSWORD = re.compile(r"(://[^:/@\s]+:)[^@\s]+@")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def redact(text: str | None) -> str | None:
    """Bỏ mật khẩu trong DSN và giá trị của biến bí mật (khoá API, token, DSN) khỏi nội dung cảnh báo."""
    if not text:
        return text
    out = DSN_PASSWORD.sub(r"\1***@", str(text))
    for name, value in os.environ.items():
        if value and len(value) >= 6 and SECRET_ENV.search(name) and value in out:
            out = out.replace(value, "***")
    return out[:600]


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def read_alerts(path: Path) -> list[dict]:
    out = []
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    return out


def alert(level: str, kind: str, message: str, *, run: str | None = None, step: str | None = None,
          source: str | None = None, key: str | None = None) -> dict:
    """`key`: chữ ký chống báo dồn (mặc định loại + bước + nguồn)."""
    return {"at": now_utc().isoformat(timespec="seconds"), "level": level, "kind": kind, "run": run, "step": step,
            "source": source, "message": redact(message), "key": key or f"{kind}|{step or ''}|{source or ''}"}


def publish(alerts: list[dict], state_dir: Path, run_dir: Path | None, cooldown_hours: float) -> list[dict]:
    """Ghi cảnh báo; cùng chữ ký đã báo trong `cooldown_hours` thì đánh dấu `suppressed`. Trả cảnh báo không bị chặn."""
    if not alerts:
        return []
    state_dir = Path(state_dir)
    seen = _read_json(state_dir / SEEN)
    now = now_utc()
    shown = []
    for item in alerts:
        last = seen.get(item["key"])
        try:
            recent = last and now - datetime.fromisoformat(last) < timedelta(hours=cooldown_hours)
        except ValueError:
            recent = False
        item["suppressed"] = bool(recent)
        if not recent:
            seen[item["key"]] = item["at"]
            shown.append(item)
    lines = "".join(json.dumps(a, ensure_ascii=False) + "\n" for a in alerts)
    if run_dir is not None:
        with (Path(run_dir) / ALERTS).open("a", encoding="utf-8") as fh:
            fh.write(lines)
    feed = state_dir / ALERTS
    existing = read_alerts(feed)
    if len(existing) + len(alerts) > KEEP:
        keep = existing[-(KEEP - len(alerts)):]
        feed.write_text("".join(json.dumps(a, ensure_ascii=False) + "\n" for a in keep), encoding="utf-8")
    with feed.open("a", encoding="utf-8") as fh:
        fh.write(lines)
    _write_json(state_dir / SEEN, seen)
    for item in shown:
        print(f"alert.{item['level']} kind={item['kind']} step={item['step'] or '-'} source={item['source'] or '-'} "
              f"{item['message']}", flush=True)
    return shown


# ---------------------------------------------------------------------------------------------------- CP7


def run_alerts(data: dict, run_dir: Path, include_warnings: bool = True) -> list[dict]:
    """Cảnh báo của một lượt vừa kết thúc, theo run.json và file của lượt."""
    run = data.get("id")
    out: list[dict] = []
    steps = data.get("steps") or []
    status, kind = data.get("status"), data.get("errorKind")
    if status in ("failed", "dead") or (status == "partial" and kind):
        failed = next((s for s in reversed(steps) if s.get("status") == "error"), None)
        out.append(alert("error", "quality" if kind == "quality" else (kind or "unknown"),
                         ("Chặn chất lượng, không nạp DB: " if kind == "quality" else "Lượt lỗi: ")
                         + (data.get("error") or (failed or {}).get("error") or status),
                         run=run, step=(failed or {}).get("name")))
    if include_warnings:
        for s in steps:
            if s.get("status") == "blocked":
                out.append(alert("warning", "blocked", f"Nguồn bị chặn, lượt bỏ qua nguồn này: {s.get('error') or s.get('name')}",
                                 run=run, step=s.get("name"), source=s.get("group")))
            if s.get("status") == "timeout":  # P4: bước cào quá hạn giờ, đã dừng riêng bước đó
                out.append(alert("warning", "timeout", f"Nguồn quá hạn giờ, lượt chỉ giữ phần đã cào: {s.get('error') or s.get('name')}",
                                 run=run, step=s.get("name"), source=s.get("group")))
        for meta in sorted((Path(run_dir) / "normalised").glob("*.meta.json")):
            info = _read_json(meta)
            errors = info.get("errors") or 0
            if errors and info.get("status") != "failed":
                stem = meta.name[:-len(".meta.json")]
                out.append(alert("warning", "record", f"{errors}/{info.get('records')} bản ghi lỗi khi ánh xạ (dưới ngưỡng), "
                                                      f"xem errors.jsonl", run=run, step="normalise", source=stem))
        failed_batches = [b for b in read_alerts(Path(run_dir) / "db_batches.jsonl") if b.get("error")]
        if failed_batches:
            out.append(alert("warning", "infra", f"{len(failed_batches)} lô nạp DB theo phần lỗi; lỗi cuối: "
                                                 f"{failed_batches[-1]['error']}", run=run, step="stream.db"))
    return out


def on_run_finished(data: dict, run_dir: Path, state_dir: Path, values: dict) -> list[dict]:
    """Gọi sau khi lượt ghi kết thúc (fresh_catalog.run_job). Trả cảnh báo đã báo (không bị chặn)."""
    if not values.get("alert.enabled", True):
        return []
    items = run_alerts(data, run_dir, values.get("alert.includeWarnings", True))
    items += slow_step_alerts(data, Path(run_dir).parent, values)
    return publish(items, state_dir, run_dir, values.get("alert.cooldownHours", 6))


# ---------------------------------------------------------------------------------------------------- CP8


def _runs(run_root: Path, state_dir: Path) -> list[dict]:
    """Mọi lượt đã biết (run.json còn giữ + tóm tắt trong lịch sử), cũ trước."""
    found: dict[str, dict] = {}
    for line in read_alerts(Path(state_dir) / "runs.jsonl"):
        if line.get("id"):
            found[line["id"]] = line
    for path in Path(run_root).glob("*/run.json") if Path(run_root).is_dir() else []:
        data = _read_json(path)
        if data.get("id"):
            found[data["id"]] = data
    return sorted(found.values(), key=lambda r: r.get("startedAt") or "")


def _vn_date(stamp: str | None) -> date | None:
    try:
        return datetime.fromisoformat(stamp).astimezone(VN).date() if stamp else None
    except ValueError:
        return None


def last_db_load(runs: list[dict]) -> datetime | None:
    for run in reversed(runs):
        for s in reversed(run.get("steps") or []):
            if s.get("name") == "db" and s.get("status") == "ok":
                stamp = s.get("finishedAt") or run.get("finishedAt")
                try:
                    return datetime.fromisoformat(stamp) if stamp else None
                except ValueError:
                    return None
    return None


def slow_step_alerts(data: dict, run_root: Path, values: dict) -> list[dict]:
    """Bước sau cào của lượt chạy lâu hơn `sla.slowFactor` lần trung vị của chính bước đó ở các lượt đang giữ (≥ 3 lượt)."""
    factor = values.get("sla.slowFactor") or 0
    if not values.get("sla.enabled", True) or factor <= 0:
        return []
    history: dict[str, list[float]] = {}
    for path in Path(run_root).glob("*/run.json") if Path(run_root).is_dir() else []:
        other = _read_json(path)
        if other.get("id") == data.get("id"):
            continue
        for s in other.get("steps") or []:
            if s.get("name") in POST_CRAWL and s.get("status") == "ok" and s.get("seconds"):
                history.setdefault(s["name"], []).append(float(s["seconds"]))
    out = []
    for s in data.get("steps") or []:
        seconds, samples = s.get("seconds"), history.get(s.get("name")) or []
        if s.get("name") not in POST_CRAWL or not seconds or len(samples) < 3:
            continue
        median = statistics.median(samples)
        if median > 0 and seconds > factor * median:
            out.append(alert("warning", "sla", f"Bước {s['name']} chạy {seconds:g} s, gấp {seconds / median:.1f} lần trung vị "
                                               f"{median:g} s của {len(samples)} lượt trước", run=data.get("id"),
                             step=s["name"], key=f"sla-slow|{data.get('id')}|{s['name']}"))
    return out


def sla_status(state_dir: Path, run_root: Path, values: dict, now: datetime | None = None) -> dict:
    """Tình trạng SLA hôm nay (giờ Việt Nam), không ghi gì: dùng cho monitor và `check_sla`.

    - `finishBy`: tới `sla.finishBy` mà hôm nay có lịch nhưng chưa có lượt kết thúc ok/partial bắt đầu trong ngày;
    - `catalogAge`: lần nạp DB thành công gần nhất cũ hơn `sla.maxCatalogAgeHours`."""
    import fresh_settings  # tránh vòng import khi fresh_settings dùng module này
    now = (now or now_utc()).astimezone(VN)
    today = now.date()
    runs = _runs(run_root, state_dir)
    out: dict = {"enabled": bool(values.get("sla.enabled", True)), "date": today.isoformat(), "rules": []}
    if not out["enabled"]:
        return out
    hh, mm = (int(x) for x in str(values.get("sla.finishBy") or "19:00").split(":"))
    scheduled = bool(values.get("schedule.enabled")) and (
        fresh_settings.auto_mode(values, state_dir, today) == "full" or bool(values.get("schedule.dailyEnabled")))
    done = [r for r in runs if _vn_date(r.get("startedAt")) == today and r.get("status") in FINISHED_OK]
    if not scheduled:
        state, message = "none", "Hôm nay không có lịch chạy tự động"
    elif done:
        state, message = "ok", f"Đã có lượt xong hôm nay: {done[-1]['id']} ({done[-1]['status']})"
    elif now.time() < time(hh, mm):
        state, message = "pending", f"Chưa tới hạn {hh:02d}:{mm:02d}"
    else:
        state, message = "late", f"Quá {hh:02d}:{mm:02d} mà hôm nay chưa có lượt nào xong"
    out["rules"].append({"rule": "finishBy", "state": state, "message": message})
    limit = values.get("sla.maxCatalogAgeHours") or 0
    last = last_db_load(runs)
    if limit and last is not None:
        age = (now - last.astimezone(VN)).total_seconds() / 3600
        out["rules"].append({"rule": "catalogAge", "state": "late" if age > limit else "ok", "hours": round(age, 1),
                             "message": f"Lần nạp DB thành công gần nhất cách đây {age:.1f} giờ (ngưỡng {limit} giờ)"})
    else:
        out["rules"].append({"rule": "catalogAge", "state": "none", "message": "Chưa có lần nạp DB thành công nào trong lịch sử"})
    out["state"] = "late" if any(r["state"] == "late" for r in out["rules"]) else \
        "pending" if any(r["state"] == "pending" for r in out["rules"]) else "ok"
    return out


def check_sla(state_dir: Path, run_root: Path, values: dict, now: datetime | None = None) -> list[dict]:
    """Chạy ở mỗi cron tick: quy tắc SLA bị trễ → cảnh báo `sla`, mỗi quy tắc tối đa một lần mỗi ngày."""
    if not values.get("alert.enabled", True):
        return []
    status = sla_status(state_dir, run_root, values, now)
    items = [alert("error", "sla", rule["message"], step=rule["rule"], key=f"sla|{rule['rule']}|{status['date']}")
             for rule in status["rules"] if rule["state"] == "late"]
    return publish(items, state_dir, None, 24)
