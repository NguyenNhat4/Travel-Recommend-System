"""Bước con của một bước lớn trong lượt cào (bảo trì DB, kiểm tra, nạp DB, index) cho sơ đồ trên monitor.

Mỗi bước con: tên, trạng thái, số giây, vào → ra (số dòng), và `ok`/`total` khi bước có tỉ lệ thành công (vd. dòng ghép được
với DB / dòng đưa vào). Danh sách nằm ở `detail.substeps` của bước trong run.json; monitor vẽ thành chuỗi ô khi bung ô lớn.
Bước chuẩn hoá/gộp có bước con riêng của normalise.StepClock (normalise_stages/steps.json), không dùng file này.
"""
from __future__ import annotations

import contextlib
import time


def substep_line(step: str, entry: dict) -> str:
    """Một dòng log cho bước con đã xong, để tab Log của monitor lọc theo `name=<bước>` (ô lớn) hoặc
    `name=<bước>:<bước con>` (ô con). Nhận cả khoá của stage_log (in/out) lẫn normalise.StepClock (rowsIn/rowsOut)."""
    fields = {"status": entry.get("status"), "in": entry.get("in", entry.get("rowsIn")),
              "out": entry.get("out", entry.get("rowsOut")), "changed": entry.get("changed"),
              "ok": f"{entry['ok']}/{entry['total']}" if entry.get("total") else None, "seconds": entry.get("seconds")}
    text = " ".join(f"{key}={value}" for key, value in fields.items() if value is not None)
    extra = entry.get("error") or entry.get("note")
    return f"catalog.substep name={step}:{entry.get('name')} {text}" + (f" — {extra}" if extra else "")


class Stages:
    """`sink`: danh sách nhận bước con (thường là `detail['substeps']`); `on_change`: gọi sau mỗi lần đổi để run.json có
    bước con đang chạy (fresh_catalog.save_run); `step` + `emit`: ghi một dòng log khi mỗi bước con xong (substep_line).
    Không có sink thì chỉ chạy, không ghi gì."""

    def __init__(self, sink: list | None = None, on_change=None, step: str | None = None, emit=None):
        self.sink = sink
        self.on_change = on_change
        self.step = step
        self.emit = emit

    def _log(self, entry: dict) -> None:
        if self.emit is not None and self.step:
            self.emit(substep_line(self.step, entry))

    def _changed(self) -> None:
        if self.on_change is not None:
            self.on_change()

    @contextlib.contextmanager
    def stage(self, name: str, *, inp: int | None = None):
        entry = {"name": name, "status": "running", "seconds": None, "in": inp, "out": None}
        if self.sink is not None:
            self.sink.append(entry)
            self._changed()
        started = time.monotonic()
        try:
            yield entry
        except BaseException as exc:
            entry.update(status="error", error=f"{type(exc).__name__}: {exc}"[:300])
            raise
        else:
            if entry["status"] == "running":
                entry["status"] = "ok"
        finally:
            entry["seconds"] = round(time.monotonic() - started, 3)
            self._changed()
            self._log(entry)

    def add(self, name: str, *, status: str = "ok", **fields) -> dict:
        """Bước con đã xong mà không đo giờ riêng (vd. suy từ báo cáo của bước)."""
        entry = {"name": name, "status": status, "seconds": None, "in": None, "out": None, **fields}
        if self.sink is not None:
            self.sink.append(entry)
            self._changed()
        self._log(entry)
        return entry
