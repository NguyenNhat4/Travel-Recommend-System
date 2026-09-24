"""Client Apify tối giản (chỉ thư viện chuẩn) và lệnh xem thử JSON mà một actor trả về.

Dùng cho luồng demo: gửi một yêu cầu → Apify chạy trên cloud → nhận về JSON đã tách sẵn trường (không phải đọc HTML).
Chưa có bộ chuyển JSON của actor về bản ghi trung gian của `normalise.py`: chỉ viết sau khi `probe-apify` cho thấy JSON thật
(trang mô tả của actor không đủ tin để đoán tên trường).

  python pipeline_demo.py probe-apify --actor makework36/fast-booking-scraper --input @input.json --limit 5 --max-usd 0.10

Token: biến môi trường `APIFY_TOKEN` hoặc file `.env` cạnh file này (đã nằm trong .gitignore, xem `.env.example`). Token chỉ đi qua
header `Authorization`, không bao giờ được in ra hay ghi vào log/state. Không có cơ chế xoay nhiều token: mỗi người một tài khoản
(điều khoản Apify 4.3 cấm tạo/dùng nhiều Personal Account để lách giới hạn).
Chi phí: mọi lượt chạy đều gửi `maxTotalChargeUsd` (trần chi tiêu) và `maxItems`; vượt trần thì Apify tự dừng tính tiền.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.apify.com/v2"
ROOT = Path(__file__).resolve().parent
TERMINAL = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}
MAX_PROBE_ITEMS = 100


class ApifyError(RuntimeError):
    pass


def load_env(path: Path | None = None) -> None:
    """Nạp các dòng KEY=VALUE từ `.env` vào os.environ (không ghi đè biến đã có)."""
    path = path or ROOT / ".env"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def get_token() -> str:
    load_env()
    token = os.environ.get("APIFY_TOKEN", "").strip()
    if not token:
        raise ApifyError("Chưa có APIFY_TOKEN. Sao chép .env.example thành .env, điền token (Apify Console → API & Integrations) rồi chạy lại. "
                         "Đừng dán token vào chat hay commit lên git.")
    return token


def actor_path(actor: str) -> str:
    """'user/name' → 'user~name' (dạng dùng trong URL API)."""
    actor = actor.strip()
    if not actor or actor.count("/") > 1 or " " in actor:
        raise ApifyError(f"Tên actor không hợp lệ: {actor!r} (dạng 'user/actor-name')")
    return actor.replace("/", "~")


class Apify:
    def __init__(self, token: str, base: str = API, timeout: float = 90.0):
        self.token, self.base, self.timeout = token, base.rstrip("/"), timeout

    def _request(self, method: str, path: str, params: dict | None = None, body=None):
        url = f"{self.base}{path}"
        if params:
            url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": f"Bearer {self.token}", "Content-Type": "application/json", "Accept": "application/json",
            "User-Agent": "vota-pipeline-demo/1"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                return json.loads(raw.decode("utf-8")) if raw else None, resp.headers
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                err = json.loads(e.read().decode("utf-8")).get("error") or {}
                detail = f"{err.get('type', '')}: {err.get('message', '')}".strip(": ")
            except (ValueError, OSError):
                pass
            raise ApifyError(f"Apify trả HTTP {e.code} cho {method} {path}. {detail}".replace(self.token, "***")) from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ApifyError(f"Không gọi được Apify ({method} {path}): {e}".replace(self.token, "***")) from None

    def start_run(self, actor: str, input_: dict, *, max_items: int | None = None, max_usd: float | None = None,
                  timeout_s: int | None = None, memory_mb: int | None = None) -> dict:
        body, _ = self._request("POST", f"/acts/{actor_path(actor)}/runs", {
            "maxItems": max_items, "maxTotalChargeUsd": max_usd, "timeout": timeout_s, "memory": memory_mb}, input_)
        return (body or {}).get("data") or {}

    def get_run(self, run_id: str, wait: int = 0) -> dict:
        body, _ = self._request("GET", f"/actor-runs/{urllib.parse.quote(run_id)}", {"waitForFinish": min(max(wait, 0), 60) or None})
        return (body or {}).get("data") or {}

    def abort(self, run_id: str) -> dict:
        body, _ = self._request("POST", f"/actor-runs/{urllib.parse.quote(run_id)}/abort")
        return (body or {}).get("data") or {}

    def items(self, dataset_id: str, limit: int | None = None, offset: int = 0) -> list[dict]:
        body, _ = self._request("GET", f"/datasets/{urllib.parse.quote(dataset_id)}/items",
                                {"format": "json", "clean": "true", "limit": limit, "offset": offset or None})
        return body if isinstance(body, list) else []

    def run_and_collect(self, actor: str, input_: dict, *, max_items: int, max_usd: float, wait_timeout_s: int = 600,
                        on_status=None) -> dict:
        """Chạy actor, đợi xong, lấy tối đa max_items dòng. Quá hạn thì huỷ run. Trả {run, items, costUsd}."""
        run = self.start_run(actor, input_, max_items=max_items, max_usd=max_usd, timeout_s=wait_timeout_s)
        run_id = run.get("id")
        if not run_id:
            raise ApifyError("Apify không trả run id")
        deadline = time.monotonic() + wait_timeout_s
        while run.get("status") not in TERMINAL:
            if time.monotonic() > deadline:
                self.abort(run_id)
                raise ApifyError(f"Run {run_id} quá {wait_timeout_s}s, đã huỷ")
            run = self.get_run(run_id, wait=20)
            if on_status:
                on_status(run)
        if run.get("status") != "SUCCEEDED":
            raise ApifyError(f"Run {run_id} kết thúc ở trạng thái {run.get('status')}: {run.get('statusMessage') or ''}".strip())
        items = self.items(run["defaultDatasetId"], limit=max_items)
        return {"run": run, "items": items, "costUsd": run.get("usageTotalUsd")}


def field_report(items: list[dict]) -> list[dict]:
    """Mỗi khoá cấp 1 của JSON: kiểu, tỷ lệ dòng có giá trị, một ví dụ ngắn. Để nhìn nhanh actor có trả đủ trường catalog cần không."""
    keys: dict[str, dict] = {}
    for it in items:
        for k, v in it.items():
            e = keys.setdefault(k, {"key": k, "filled": 0, "types": set(), "example": None})
            e["types"].add(type(v).__name__)
            if v not in (None, "", [], {}):
                e["filled"] += 1
                if e["example"] is None:
                    e["example"] = v
    n = max(len(items), 1)
    out = []
    for e in keys.values():
        ex = json.dumps(e["example"], ensure_ascii=False) if e["example"] is not None else ""
        out.append({"key": e["key"], "types": "/".join(sorted(e["types"])), "filledPct": round(100 * e["filled"] / n),
                    "example": ex if len(ex) <= 70 else ex[:67] + "..."})
    return sorted(out, key=lambda r: (-r["filledPct"], r["key"]))


def probe(actor: str, input_: dict, *, limit: int, max_usd: float, out_dir: Path, client: Apify | None = None,
          on_status=None) -> dict:
    """Chạy thử vài dòng và lưu JSON thô vào out_dir để xem trước khi viết adapter. Tốn vài cent."""
    if not 1 <= limit <= MAX_PROBE_ITEMS:
        raise ApifyError(f"--limit phải trong 1..{MAX_PROBE_ITEMS} (probe chỉ để xem thử)")
    if not 0 < max_usd <= 5:
        raise ApifyError("--max-usd phải trong (0, 5]")
    client = client or Apify(get_token())
    res = client.run_and_collect(actor, input_, max_items=limit, max_usd=max_usd, wait_timeout_s=300, on_status=on_status)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = out_dir / f"{stamp}-{actor.replace('/', '__')}.json"
    path.write_text(json.dumps({"actor": actor, "input": input_, "costUsd": res["costUsd"], "items": res["items"]},
                               ensure_ascii=False, indent=1), encoding="utf-8")
    return {"path": path, "count": len(res["items"]), "costUsd": res["costUsd"], "fields": field_report(res["items"])}
