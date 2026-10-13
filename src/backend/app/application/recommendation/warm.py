"""Làm ấm cache gợi ý trang chủ ngay sau khi đăng nhập (PRD architecture §4, chốt 2026-10-12).

Đăng nhập xong, trình duyệt mở trang chủ và hỏi `/recommendations?k=4` (không destination). Tính trước đúng request đó
trên pool riêng thì request của trang chủ trúng cache, hoặc chờ lần tính đang chạy (`wait_hit`) thay vì tính lần hai.
Persona demo gửi kèm destination nên không được làm ấm (người dùng chấp nhận, 2026-10-12).

Không dùng `BackgroundTasks` của FastAPI: middleware log HTTP đo trọn lời gọi app, thời gian làm ấm sẽ bị tính vào
request đăng nhập. Việc gửi vào pool không chép contextvars của request, nên số đo của engine không lẫn vào log đăng nhập.
"""
from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import Executor
from typing import Any, Callable

from src.backend.app.core.logging_config import log_event

logger = logging.getLogger("uvicorn.error")

#: Khối gợi ý trang chủ (`HomeView.tsx`) hỏi k=4, không destination; khoá cache phải trùng đúng request đó.
HOME_K = 4


class WarmRecommendations:
    """`warm(cdp_user_id)` đặt một lần tính gợi ý vào pool riêng rồi trả ngay; không bao giờ ném lỗi.

    `engine` trả engine đang phục vụ lúc gọi (RecsysRefresher thay engine mỗi lần nạp lại). Bỏ qua khi engine chưa nạp
    hoặc cache tắt; bỏ trùng theo người dùng; tối đa `max_pending` việc đang chờ hoặc đang chạy.
    """

    def __init__(self, engine: Callable[[], Any], executor: Executor, *, k: int = HOME_K, max_pending: int = 32,
                 clock: Callable[[], float] = time.perf_counter):
        self._engine = engine
        self._executor = executor
        self._k = k
        self._max_pending = max_pending
        self._clock = clock
        self._pending: set[str] = set()
        self._lock = threading.Lock()

    def __call__(self, cdp_user_id: str | None) -> None:
        if not cdp_user_id:
            return
        try:
            engine = self._engine()
            if engine is None:
                self._log("no_engine")
                return
            if not getattr(engine, "cache_enabled", False):
                return   # cache tắt: lúc nạp đã log `recsys.cache.disabled`, tính trước cũng không lưu được
            with self._lock:
                if cdp_user_id in self._pending:
                    self._log("duplicate")
                    return
                if len(self._pending) >= self._max_pending:
                    self._log("busy")
                    return
                self._pending.add(cdp_user_id)
            try:
                self._executor.submit(self._run, cdp_user_id)
            except Exception:   # ví dụ pool đã đóng khi app đang tắt
                self._done(cdp_user_id)
                raise
        except Exception as exc:   # đăng nhập không được hỏng vì làm ấm
            self._log("failed", "WARNING", error_kind=type(exc).__name__)

    def _run(self, cdp_user_id: str) -> None:
        started = self._clock()
        try:
            engine = self._engine()
            if engine is None or not getattr(engine, "cache_enabled", False):
                outcome = "no_engine" if engine is None else "cache_off"
            else:
                result = engine(cdp_user_id, k=self._k, destination=None)
                # miss = vừa tính và lưu; hit / wait_hit = đã có sẵn; error = Redis lỗi, đã tính nhưng không lưu.
                outcome = (result.get("diagnostics") or {}).get("cacheOutcome") or "uncached"
            self._log(outcome, duration_ms=self._elapsed_ms(started))
        except Exception as exc:
            self._log("failed", "WARNING", duration_ms=self._elapsed_ms(started), error_kind=type(exc).__name__)
        finally:
            self._done(cdp_user_id)

    def _done(self, cdp_user_id: str) -> None:
        with self._lock:
            self._pending.discard(cdp_user_id)

    def _elapsed_ms(self, started: float) -> int:
        return max(0, round((self._clock() - started) * 1000))

    @staticmethod
    def _log(outcome: str, level: str = "INFO", **fields: Any) -> None:
        log_event(logger, "recsys.cache.warm", level, outcome=outcome, **fields)
