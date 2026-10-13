"""`CdpHistoryReader` (đường **đọc** của recsys) trên `cdp.events` của PostgreSQL local.

Đừng nhầm với `local_cdp_client.py` cùng thư mục: file đó là đường **ghi** (async, `record_purchases`,
`cancel`, browse event, profile) theo port `CdpClient`. Hai port nằm chung `application/ports/cdp_client.py`,
cùng chạm `cdp.*` và cùng đi qua `CDP_DATABASE_URL` — không có code nào ngoài các adapter trong
`infrastructure/cdp/` được SQL thẳng vào schema `cdp` (AGENTS.md §6.1).

Connection phải là `CDP_DATABASE_URL` (role `cdp_reader`/`cdp_writer`). Dùng `DATABASE_URL`
sẽ lỗi `permission denied for table events`: role `vota_app` cố ý không đọc được
`cdp.events`/`cdp.profiles`, và đó là ranh giới CDP được mô phỏng bằng quyền.

Trả dict **camelCase** đúng tên trường CDP (`cdpUserId`, `eventName`, `usingDate`…) vì đó là hình dạng
`profile.py`/`popularity.py` đang đọc, và cũng là hình dạng `HttpCdpClient` sẽ trả khi lên CDP thật.

Không kết nối/đọc được (sập, timeout) → `CdpUnavailableError`, để `RecommendForUser` lui về `popular`
(hop-dong-tich-hop-cdp.md §6–§7). Lỗi quyền/SQL lúc chạy câu lệnh (`ProgrammingError`) là lỗi cấu hình nên vẫn
nổi lên. Lỗi xác thực lúc kết nối (sai mật khẩu, `pg_hba`) libpq báo như `OperationalError` thường, không tách được
khỏi sự cố, nên cũng thành `CdpUnavailableError`; lúc khởi động nó vẫn làm RecSys hỏng rõ ràng vì bảng phổ biến đọc
qua cùng đường kết nối.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from src.backend.app.application.ports.cdp_client import HISTORY_MAX_EVENTS, CdpUnavailableError

#: `timestamp` là từ khoá SQL nên phải để trong ngoặc kép ở mọi câu lệnh.
_COLUMNS = """
    cdp_user_id, event_name, "timestamp", product_id, taxonomy,
    event_group_id, quantity, unit_price, using_date
"""


def _to_cdp(row: tuple) -> dict:
    """Một dòng `cdp.events` → dict theo tên trường CDP."""
    cdp_user_id, event_name, timestamp, product_id, taxonomy, group_id, quantity, unit_price, using_date = row
    return {
        "cdpUserId": cdp_user_id,
        "eventName": event_name,
        "timestamp": timestamp.isoformat() if timestamp is not None else None,
        "productId": str(product_id) if product_id is not None else None,
        "taxonomy": taxonomy,
        "eventGroupId": group_id,
        "quantity": quantity,
        "unitPrice": float(unit_price) if unit_price is not None else None,
        "usingDate": using_date.isoformat() if using_date is not None else None,
    }


_PROFILE_COLUMNS = """
    cdp_user_id, lifecycle_stage, days_since_last_booking, lifetime_order_count, vinclub_tier,
    purchased_verticals, home_city, last_destination
"""


def _profile_to_cdp(row: tuple) -> dict:
    """Một dòng `cdp.profiles` → dict theo tên trường CDP (camelCase), chỉ các cột đánh giá offline cần."""
    user, stage, days, orders, tier, verticals, home, last = row
    return {
        "cdpUserId": user,
        "lifecycleStage": stage,
        "daysSinceLastBooking": days,
        "lifetimeOrderCount": orders,
        "vinclubTier": tier,
        "purchasedVerticals": list(verticals or []),
        "homeCity": home,
        "lastDestination": last,
    }


def _redact(text: str, dsn: str) -> str:
    """Xoá DSN và mật khẩu khỏi thông điệp lỗi. libpq thường không in lại chúng, nhưng không dựa vào điều đó."""
    import psycopg
    from psycopg.conninfo import conninfo_to_dict

    try:
        password = conninfo_to_dict(dsn).get("password")
    except psycopg.Error:  # DSN hỏng thì psycopg.connect đã ném ProgrammingError, không tới được đây
        password = None
    text = text.replace(dsn, "<CDP_DATABASE_URL>")
    return text.replace(password, "***") if password else text


class PostgresCdpReader:
    """Chỉ đọc. Mọi thao tác ghi đi qua `local_cdp_client.LocalCdpClient`."""

    def __init__(self, cdp_database_url: str, *, timeout_seconds: float = 2.0, history_limit: int = HISTORY_MAX_EVENTS):
        self._cdp_database_url = cdp_database_url
        self._timeout_seconds = timeout_seconds  # CDP_TIMEOUT_SECONDS (hop-dong-tich-hop-cdp.md §7)
        self._history_limit = history_limit      # tối đa 500 event mỗi lần tính (hop-dong-tich-hop-cdp.md §6)

    def _query(self, sql: str, params: tuple, *, statement_timeout: bool = False, mapper=_to_cdp) -> list[dict]:
        import psycopg

        try:
            # libpq chỉ nhận giây nguyên cho connect_timeout và coi mọi giá trị dưới 2 là 2.
            with psycopg.connect(self._cdp_database_url,
                                 connect_timeout=max(2, math.ceil(self._timeout_seconds))) as conn:
                with conn.cursor() as cur:
                    if statement_timeout:  # chỉ cho đường đọc theo request; đọc lô lúc khởi động không bị cắt
                        # SET LOCAL trong transaction, không qua tham số khởi động `options`: không đè `options`
                        # sẵn có trong DSN và đi qua được pooler chế độ transaction.
                        cur.execute("SELECT set_config('statement_timeout', %s, true)",
                                    (str(max(1, int(self._timeout_seconds * 1000))),))  # 0 = không giới hạn
                    cur.execute(sql, params)
                    return [mapper(row) for row in cur.fetchall()]
        except (psycopg.OperationalError, psycopg.InterfaceError, OSError) as exc:
            # Chỉ dòng đầu, cắt ngắn; DSN và mật khẩu bị xoá nếu driver có in lại (§8).
            detail = (_redact(str(exc), self._cdp_database_url).strip().splitlines() or [""])[0][:200]
            raise CdpUnavailableError(f"CDP history read failed: {type(exc).__name__}: {detail}") from exc

    def events_for_user(self, cdp_user_id: str) -> list[dict]:
        """Lịch sử của một khách, mới nhất trước — `profile.py` dựng hồ sơ từ đây. Tối đa `history_limit` event.

        Cùng thời điểm thì `event_id` tăng dần: khớp thứ tự harness bench dựng lại (`all_events` theo `event_id` tăng dần rồi
        `parity.events_desc` sort ổn định giảm dần theo thời điểm), kể cả ở mốc cắt 500."""
        return self._query(
            f'SELECT {_COLUMNS} FROM cdp.events WHERE cdp_user_id = %s ORDER BY "timestamp" DESC, event_id ASC LIMIT %s',
            (cdp_user_id, self._history_limit),
            statement_timeout=True,
        )

    def purchase_events(self, since_days: int = 730) -> list[dict]:
        """Toàn bộ `purchase` trong N ngày — đầu vào của bảng phổ biến (`popularity.py`)."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
        return self._query(
            f'SELECT {_COLUMNS} FROM cdp.events '
            f'WHERE event_name = %s AND "timestamp" >= %s ORDER BY "timestamp" DESC',
            ("purchase", cutoff),
        )

    def all_events(self, until: datetime | None = None) -> list[dict]:
        """Toàn bộ event, chỉ cho đánh giá offline (`src/evaluation/recsys_bench`); không gọi trong request.

        `until` cắt ở kho (`timestamp < until`) để harness không nhận event sau mốc đánh giá. Thứ tự tất định
        (khách, thời điểm, `event_id`) như bản của `origin/khoa/recsys-research@6b9b0af`. Đọc lô nên không
        đặt `statement_timeout`, giống `purchase_events`.
        """
        where, params = ('WHERE "timestamp" < %s ', (until,)) if until is not None else ("", ())
        return self._query(
            f'SELECT {_COLUMNS} FROM cdp.events {where}ORDER BY cdp_user_id, "timestamp", event_id',
            params,
        )

    def all_profiles(self) -> list[dict]:
        """Toàn bộ `cdp.profiles` (từ 2026-10-01), chỉ cho đánh giá offline (`recsys_bench sanity`): đối chiếu
        `lifecycle_stage` / `days_since_last_booking` seed đã ghi với bản tính lại từ event. Không gọi trong request;
        không `statement_timeout`; thứ tự tất định theo `cdp_user_id`. Trả camelCase như `all_events`."""
        return self._query(
            f"SELECT {_PROFILE_COLUMNS} FROM cdp.profiles ORDER BY cdp_user_id",
            (),
            mapper=_profile_to_cdp,
        )
