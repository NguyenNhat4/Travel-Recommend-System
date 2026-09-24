"""Dữ liệu cho trang /daily của monitor.py: lượt chạy và bước đang chạy, data version, so sánh, phễu dữ liệu qua từng bước,
truy vết một sản phẩm từ raw → interim → chuẩn hoá → catalog → dòng nạp DB, và các thao tác (chạy, accept, switch, đóng băng).

Chỉ đọc file dưới data/; thao tác ghi đều chạy `daily.py` trong tiến trình con (daily.py tự khoá, không chạy chồng).
Không bao giờ trả giá trị biến môi trường — chỉ trả tên biến và đã đặt hay chưa.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

import daily
from collectors.common import RawCache, Paths
from collectors.textutil import fold

HERE = Path(__file__).resolve().parent
RUN_ID = re.compile(r"^(?:switch-)?\d{8}-\d{6}(?:-\d+)?$")
LOG_NAME = re.compile(r"^[a-z0-9_:-]+\.log$")
MAX_RAW_BYTES = 400_000
SOURCE_FILES = {  # tiền tố sourceRef → file interim/thư mục raw có thể chứa bản ghi gốc
    "vinpearl": ("vinpearl", "vinpearl_bundles"),
    "booking": ("booking_hotels", "booking_attractions", "booking_flights"),
    "agoda": ("agoda_hotels", "agoda_api"),
    "trip": ("trip_attractions", "trip_flights", "trip_hotels", "trip_combos", "trip_experiences"),
}


def trim(obj, max_str: int = 400, max_list: int = 12, max_keys: int = 80):
    if isinstance(obj, str):
        return obj if len(obj) <= max_str else obj[:max_str - 1] + "…"
    if isinstance(obj, list):
        out = [trim(x, max_str, max_list, max_keys) for x in obj[:max_list]]
        return out + ([f"… +{len(obj) - max_list} mục"] if len(obj) > max_list else [])
    if isinstance(obj, dict):
        out = {k: trim(v, max_str, max_list, max_keys) for k, v in list(obj.items())[:max_keys]}
        if len(obj) > max_keys:
            out["…"] = f"+{len(obj) - max_keys} khoá"
        return out
    return obj


def brief(r: dict) -> dict:
    return {"productId": r.get("productId"), "name": r.get("name"), "taxonomy": r.get("taxonomy"), "destination": r.get("destination"),
            "unitPrice": r.get("unitPrice"), "available": r.get("available"), "sourceRef": r.get("sourceRef"),
            "level": (r.get("attributes") or {}).get("level")}


class DailyApi:
    def __init__(self, data: Path):
        self.data = data
        self._rows_cache: OrderedDict[tuple, list[dict]] = OrderedDict()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ đọc có cache
    def _rows(self, path: Path) -> list[dict]:
        """Đọc catalog (jsonl / jsonl.gz) có cache theo (đường dẫn, mtime, size); giữ tối đa 4 file."""
        try:
            st = path.stat()
        except OSError:
            return []
        key = (str(path), st.st_mtime_ns, st.st_size)
        with self._lock:
            if key in self._rows_cache:
                self._rows_cache.move_to_end(key)
                return self._rows_cache[key]
        rows = daily.read_rows(path)
        with self._lock:
            self._rows_cache[key] = rows
            while len(self._rows_cache) > 4:
                self._rows_cache.popitem(last=False)
        return rows

    def _run_dir(self, run_id: str) -> Path:
        if run_id == "latest":
            try:
                run_id = (self.data / "daily" / "latest.txt").read_text(encoding="utf-8").strip()
            except OSError:
                raise ValueError("chưa có lượt nào")
        if not RUN_ID.match(run_id):
            raise ValueError("mã lượt không hợp lệ")
        path = self.data / "daily" / run_id
        if not path.is_dir():
            raise ValueError(f"không có lượt {run_id}")
        return path

    @staticmethod
    def _state(run_dir: Path) -> dict:
        try:
            return json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"runId": run_dir.name}

    # ------------------------------------------------------------------ tổng quan
    def busy(self) -> str | None:
        lock = daily.DailyLock(self.data / "state" / "daily.lock")
        if lock.acquire():
            lock.release()
            return None
        try:
            return (self.data / "state" / "daily.lock").read_text(encoding="utf-8").strip() or "đang chạy"
        except OSError:
            return "đang chạy"

    def targets(self) -> dict:
        daily.load_env()
        out = {}
        for name, spec in daily.TARGETS.items():
            out[name] = {var: bool(os.environ.get(env)) for var, env in (("seed", spec["seed"]), ("weaviate", spec["weaviate"]))}
            out[name]["vars"] = {env: bool(os.environ.get(env)) for env in spec.values()}
        out["cohere"] = bool(os.environ.get("COHERE_API_KEY"))
        out["defaultLoad"] = os.environ.get("DAILY_LOAD", "")
        out["destinations"] = os.environ.get("DAILY_DESTINATIONS") or "@v1"
        return out

    def runs(self, limit: int = 25) -> list[dict]:
        root = self.data / "daily"
        dirs = sorted((p for p in root.glob("*") if p.is_dir() and RUN_ID.match(p.name)), key=lambda p: p.name.replace("switch-", ""),
                      reverse=True) if root.exists() else []
        out = []
        for d in dirs[:limit]:
            st = self._state(d)
            pub = st.get("publish") or {}
            out.append({"runId": d.name, "kind": st.get("kind", "run"), "startedAt": st.get("startedAt"), "finishedAt": st.get("finishedAt"),
                        "exitCode": st.get("exitCode"), "currentStage": st.get("currentStage"), "publish": pub.get("status"),
                        "version": pub.get("version") or st.get("version"),
                        "workers": {k: v.get("status") for k, v in (st.get("workers") or {}).items()},
                        "load": {k: v.get("status") for k, v in (st.get("load") or {}).items()}})
        return out

    def overview(self) -> dict:
        active = daily.active_version(self.data)
        manifest = None
        if active:
            try:
                manifest = daily.read_manifest(self.data, active)
                manifest = {k: manifest.get(k) for k in ("version", "label", "createdAt", "rows", "available", "byTaxonomy", "stats")}
            except ValueError:
                manifest = None
        catalog = self.data / "products.jsonl"
        return {"busy": self.busy(), "activeVersion": manifest, "loaded": daily.loaded_versions(self.data), "targets": self.targets(),
                "catalogRows": sum(1 for _ in open(catalog, encoding="utf-8")) if catalog.exists() else 0,
                "runs": self.runs(), "now": datetime.now().astimezone().isoformat(timespec="seconds")}

    def run(self, run_id: str) -> dict:
        d = self._run_dir(run_id)
        st = self._state(d)
        report = d / "report.txt"
        return {"state": st, "report": report.read_text(encoding="utf-8") if report.exists() else None,
                "logs": sorted(p.name for p in d.glob("*.log")), "funnel": self.funnel(d, st)}

    def log(self, run_id: str, name: str, lines: int = 200) -> dict:
        d = self._run_dir(run_id)
        if not LOG_NAME.match(name) or not (d / name).is_file():
            raise ValueError("không có log này")
        text = (d / name).read_text(encoding="utf-8", errors="replace").splitlines()
        return {"name": name, "lines": text[-lines:], "total": len(text)}

    @staticmethod
    def funnel(run_dir: Path, st: dict) -> dict | None:
        """Số dòng qua từng bước xử lý của một lượt: đọc interim → dựng dòng → loại → chuẩn hoá → cuối → giữ dòng → gate → promote."""
        path = run_dir / "stage" / "normalise_report.json"
        if not path.exists():
            return None
        rep = json.loads(path.read_text(encoding="utf-8"))
        pub = st.get("publish") or {}
        stats = pub.get("stats") or {}
        steps = [
            ("Bản ghi interim đọc được", sum((rep.get("recordsRead") or {}).values()), "mỗi nguồn giữ bản crawledAt mới nhất theo key"),
            ("Khách sạn trước khi gộp", rep.get("hotelRecords"), "Vinpearl + booking + Agoda + trip"),
            ("Khách sạn sau khi gộp trùng", rep.get("hotelClusters"), "tên giống ≥ 88 điểm + khoảng cách"),
            ("Dòng dựng được", rep.get("rowsBuilt"), "khách sạn, phòng, vé, tuyến/chuyến bay, combo"),
            ("Sau danh sách loại", rep.get("rowsAfterExclusions"), "soát tay + không phải điểm du lịch"),
            ("Sau khi bỏ dòng không bán được", rep.get("rowsAfterUnsellable"), "không giá mà nguồn không cung cấp"),
            ("Sau kiểm tra", rep.get("rowsAfterValidation"), "trùng productId, thiếu tên/loại"),
            ("Sau gộp giá thành viên", rep.get("rowsAfterMemberMerge"), "biến thể VIN33 về sản phẩm gốc"),
            ("Chuẩn hoá xong", rep.get("rowsFinal"), "đã xoá dòng lỗi vị trí / giá phi lý / mồ côi"),
            ("Catalog sau giữ dòng", stats.get("total"), f"mới {stats.get('new', 0)} · giữ lại {stats.get('carried', 0)} · ngừng bán {stats.get('retired', 0)}"),
        ]
        return {"recordsRead": rep.get("recordsRead"), "steps": [{"label": a, "rows": b, "note": c} for a, b, c in steps if b is not None],
                "dropped": rep.get("dropped"), "gate": {"status": pub.get("status"), "problems": pub.get("problems") or []},
                "profile": pub.get("profile"), "previousProfile": pub.get("previousProfile")}

    # ------------------------------------------------------------------ version
    def versions(self) -> dict:
        items = []
        for m in daily.list_versions(self.data):
            items.append({k: m.get(k) for k in ("version", "label", "createdAt", "runId", "previousVersion", "stats", "rows", "available",
                                                 "byTaxonomy", "snapshot", "frozenAt")})
        return {"active": daily.active_version(self.data), "loaded": daily.loaded_versions(self.data), "items": items}

    def version(self, version: str) -> dict:
        return daily.read_manifest(self.data, version)

    def diff(self, old: str, new: str | None) -> dict:
        a = self._rows(daily.versions_dir(self.data) / daily.read_manifest(self.data, old)["version"] / "products.jsonl.gz")
        if new:
            b = self._rows(daily.versions_dir(self.data) / daily.read_manifest(self.data, new)["version"] / "products.jsonl.gz")
        else:
            b = self._rows(self.data / "products.jsonl")
        return {"old": old, "new": new or "đang dùng", "kinds": daily.diff_versions(a, b)}

    # ------------------------------------------------------------------ dữ liệu qua từng bước
    def search(self, q: str, limit: int = 30) -> list[dict]:
        q = (q or "").strip()
        if len(q) < 2:
            return []
        rows = self._rows(self.data / "products.jsonl")
        f = fold(q)
        hits = [r for r in rows if r.get("productId") == q or q in (r.get("sourceRef") or "") or f in fold(r.get("name") or "")]
        return [brief(r) for r in hits[:limit]]

    def _interim_matches(self, row: dict, limit: int = 3) -> list[dict]:
        ref = (row.get("sourceRef") or "").split(":")
        if len(ref) < 3:
            return []
        bundle = ref[:2] == ["vinpearl", "bundle"]
        token = ref[3] if bundle and len(ref) > 3 else ref[2]
        stems = ("vinpearl_bundles",) if bundle else tuple(x for x in SOURCE_FILES.get(ref[0], ()) if x != "vinpearl_bundles")
        out = []
        for stem in stems:
            path = self.data / "interim" / f"{stem}.jsonl"
            if not path.exists():
                continue
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if token in line:
                        rec = json.loads(line)
                        out.append({"file": f"interim/{stem}.jsonl", "key": rec.get("key"), "crawledAt": rec.get("crawledAt"),
                                    "record": trim(rec)})
                        if len(out) >= limit:
                            return out
        return out

    def _raw_files(self, row: dict, limit: int = 30) -> list[dict]:
        """File raw của sản phẩm: đúng file theo attributes.url (tên file raw = URL đã làm sạch + hash), rồi file có mã sản phẩm trong tên."""
        ref = (row.get("sourceRef") or "").split(":")
        attrs = row.get("attributes") or {}
        paths = Paths(self.data)
        found: dict[str, dict] = {}
        for stem in SOURCE_FILES.get(ref[0] if ref else "", ()):
            cache = RawCache(paths, stem)
            for url in filter(None, {attrs.get("url"), attrs.get("bookingUrl")}):
                for ext in ("html", "json"):
                    p = cache.path(url, ext)
                    if p.exists():
                        found[str(p)] = {"path": str(p.relative_to(self.data)), "bytes": p.stat().st_size, "match": "URL"}
            token = (ref[2] if len(ref) > 2 else "").lower()
            if len(token) >= 5 and cache.dir.exists():
                for sub in cache.dir.iterdir():
                    if not sub.is_dir():
                        continue
                    for entry in os.scandir(sub):
                        if token in entry.name.lower() and entry.path not in found:
                            found[entry.path] = {"path": str(Path(entry.path).relative_to(self.data)), "bytes": entry.stat().st_size,
                                                 "match": "mã trong tên file"}
                            if len(found) >= limit:
                                return list(found.values())
        return list(found.values())

    def trace(self, product_id: str) -> dict:
        rows = self._rows(self.data / "products.jsonl")
        row = next((r for r in rows if r.get("productId") == product_id), None)
        if row is None:
            raise ValueError("không có sản phẩm này trong catalog đang dùng")
        steps = {"catalog": row}
        latest = None
        try:
            latest = self._run_dir("latest")
        except ValueError:
            pass
        if latest:
            normalised = self._rows(latest / "stage" / "products.jsonl")
            steps["normalised"] = next((r for r in normalised if r.get("productId") == product_id), None)
            steps["normalisedRun"] = latest.name
        loader = self._rows(self.data / "loader" / "cdp_products.jsonl")
        steps["db"] = next((r for r in loader if r.get("product_id") == product_id), None)
        if row.get("taxonomy") == "combo":
            combos = self._rows(self.data / "loader" / "catalog_combo_items.jsonl")
            steps["comboItems"] = [c for c in combos if c.get("combo_product_id") == product_id]
        history = []
        for m in daily.list_versions(self.data)[:6]:
            vrows = self._rows(daily.versions_dir(self.data) / m["version"] / "products.jsonl.gz")
            hit = next((r for r in vrows if r.get("productId") == product_id), None)
            history.append({"version": m["version"], "label": m.get("label"), "present": hit is not None,
                            "unitPrice": hit.get("unitPrice") if hit else None, "available": hit.get("available") if hit else None})
        return {"product": brief(row), "interim": self._interim_matches(row), "raw": self._raw_files(row), "steps": trim(steps, 600, 40),
                "history": history}

    def raw(self, rel: str) -> dict:
        path = (self.data / rel).resolve()
        if not path.is_relative_to((self.data / "raw").resolve()) or not path.is_file():
            raise ValueError("chỉ xem được file trong data/raw")
        import gzip

        with (gzip.open(path, "rb") if path.suffix == ".gz" else open(path, "rb")) as f:
            body = f.read(MAX_RAW_BYTES + 1)
        text = body[:MAX_RAW_BYTES].decode("utf-8", errors="replace")
        if path.name.endswith(".json.gz"):
            try:
                text = json.dumps(json.loads(body.decode("utf-8")), ensure_ascii=False, indent=1)[:MAX_RAW_BYTES]
            except ValueError:
                pass
        return {"path": rel, "truncated": len(body) > MAX_RAW_BYTES, "text": text}

    # ------------------------------------------------------------------ thao tác (chạy daily.py nền)
    def _spawn(self, args: list[str]) -> dict:
        if self.busy():
            raise ValueError("đang có lượt khác chạy – đợi lượt đó xong")
        launch = self.data / "daily" / f"launcher-{datetime.now():%Y%m%d-%H%M%S}.log"
        launch.parent.mkdir(parents=True, exist_ok=True)
        with open(launch, "w", encoding="utf-8") as log:
            subprocess.Popen([sys.executable, str(HERE / "daily.py"), "--data-dir", str(self.data)] + args, cwd=HERE,
                             stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        return {"started": " ".join(args[:2]), "launcherLog": launch.name}

    @staticmethod
    def _load_arg(body: dict) -> list[str]:
        load = [t for t in body.get("load") or [] if t in daily.TARGETS]
        return ["--load", ",".join(load)] + (["--no-index"] if body.get("noIndex") else [])

    def act(self, action: str, body: dict) -> dict:
        if action == "run":
            workers = [w for w in body.get("workers") or [] if w in daily.workers()]
            args = ["run"] + (["--workers", ",".join(workers)] if workers else []) + (["--no-crawl"] if body.get("noCrawl") else [])
            return self._spawn(args + self._load_arg(body))
        if action == "accept":
            run_id = str(body.get("run") or "")
            if not RUN_ID.match(run_id):
                raise ValueError("mã lượt không hợp lệ")
            return self._spawn(["accept", run_id] + self._load_arg(body))
        if action == "switch":
            version = str(body.get("version") or "")
            daily.read_manifest(self.data, version)
            return self._spawn(["switch", version] + self._load_arg(body))
        if action == "freeze":
            version, label = str(body.get("version") or ""), str(body.get("label") or "")
            target = daily.freeze_version(self.data, version, label)
            return {"frozen": version, "label": label, "snapshot": str(target)}
        raise ValueError("thao tác không hợp lệ")
