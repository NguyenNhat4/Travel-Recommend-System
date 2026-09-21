"""Helper dùng chung giữa các bước seed: RNG tất định, slug, ngày, kết nối.

Không import psycopg ở cấp module — `connect()` import bên trong, để các hàm thuần
(`stable_order_key`, `slugify`, `zipf_weights`…) test được mà không cần cài driver.
"""

from __future__ import annotations

import datetime as dt
import re
import unicodedata
import uuid
import zlib
from typing import Iterable, Iterator, Sequence, TypeVar

import numpy as np

from . import config

T = TypeVar("T")

#: Namespace của uuid5 cho mọi id sinh ra. SCHEMA.md §2: productId = uuid5(NAMESPACE_URL, sourceRef),
#: nên id ổn định giữa các lần chạy lại và dùng làm khoá ngoại được.
NAMESPACE = uuid.NAMESPACE_URL

#: Múi giờ dữ liệu (+07:00). CDP lưu timestamptz; giờ cố định ở attributes ghi kèm offset này.
TZ_VN = dt.timezone(dt.timedelta(hours=7))


# ---------------------------------------------------------------- tất định

def make_rng(seed: int, stream: str) -> np.random.Generator:
    """RNG riêng cho từng bước, suy ra tất định từ (seed, tên bước).

    Mỗi bước một stream để thêm/bớt một bước không làm xê dịch số ngẫu nhiên của bước khác.
    """
    offset = zlib.crc32(stream.encode("utf-8"))
    return np.random.default_rng([seed, offset])


def stable_order_key(value: str) -> int:
    """Thứ tự cố định, không phụ thuộc PYTHONHASHSEED.

    `hash()` của Python bị ngẫu nhiên hoá giữa các tiến trình, nên không dùng được cho dữ liệu
    phải tái lập (§2.1 "dời vào cửa sổ: as_of + hash(product_id) % 30").
    """
    return zlib.crc32(value.encode("utf-8"))


def uuid5_for(*parts: str) -> uuid.UUID:
    """uuid5 từ các mảnh ghép bằng ':' — dùng cho productId, userId, bookingId, profileId."""
    return uuid.uuid5(NAMESPACE, ":".join(parts))


# ---------------------------------------------------------------- văn bản

def strip_accents(text: str) -> str:
    """Bỏ dấu tiếng Việt, giữ chữ thường. Dùng cho so khớp từ khoá và trigram.

    'đ'/'Đ' không phân rã được bằng NFD nên xử lý riêng.
    """
    text = text.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def slugify(text: str) -> str:
    """Slug ascii, dùng trong sourceRef và imageUrl."""
    ascii_text = strip_accents(text).lower()
    ascii_text = re.sub(r"[^a-z0-9]+", "-", ascii_text)
    return ascii_text.strip("-")


def normalise_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------- ngày tháng

def parse_as_of(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:  # pragma: no cover - chỉ chạy khi người dùng gõ sai
        raise SystemExit(f"--as-of phải là YYYY-MM-DD, nhận được {value!r}") from exc


def window_end(as_of: dt.date) -> dt.date:
    """Ngày cuối của cửa sổ đặt chỗ: as_of + WINDOW_DAYS - 1."""
    return as_of + dt.timedelta(days=config.WINDOW_DAYS - 1)


def at_time(day: dt.date, hour: int, minute: int = 0) -> dt.datetime:
    """timestamptz trong múi giờ VN."""
    return dt.datetime(day.year, day.month, day.day, hour, minute, tzinfo=TZ_VN)


def random_time_on(rng: np.random.Generator, day: dt.date) -> dt.datetime:
    """Giờ ngẫu nhiên trong ngày — event seed không nên dồn vào 00:00."""
    return at_time(day, int(rng.integers(7, 23)), int(rng.integers(0, 60)))


# ---------------------------------------------------------------- phân bố

def weighted_choice(rng: np.random.Generator, mapping: dict[T, float]) -> T:
    """Chọn một khoá theo trọng số. Thứ tự khoá cố định nên kết quả tái lập được."""
    keys = list(mapping)
    weights = np.array([mapping[k] for k in keys], dtype=float)
    return keys[int(rng.choice(len(keys), p=weights / weights.sum()))]


def zipf_weights(n: int, s: float = config.ZIPF_S) -> np.ndarray:
    """Trọng số power-law cho n hạng: w_i ∝ 1/(i+1)^s.

    Đây là thứ làm baseline most-popular "khó nhưng thắng được" — dữ liệu ngẫu nhiên đều
    khiến recommender hỏng trông vẫn ổn (handbook §6).
    """
    ranks = np.arange(1, n + 1, dtype=float)
    weights = 1.0 / np.power(ranks, s)
    return weights / weights.sum()


def round_price(value: float) -> int:
    """Làm tròn nghìn — giá VND hiển thị không có số lẻ."""
    step = config.PRICE_ROUNDING
    return int(round(value / step) * step)


def inclusive_int(rng: np.random.Generator, bounds: tuple[int, int]) -> int:
    """randint bao gồm cả hai đầu — spec viết khoảng theo kiểu (2, 5) là 2..5."""
    low, high = bounds
    return int(rng.integers(low, high + 1))


def chunked(rows: Sequence[T], size: int = config.BATCH_SIZE) -> Iterator[Sequence[T]]:
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


# ---------------------------------------------------------------- database

def connect(dsn: str, *, autocommit: bool = False):
    """Mở connection psycopg. Import cục bộ để module này còn dùng được khi chưa cài driver."""
    import psycopg

    return psycopg.connect(dsn, autocommit=autocommit)


def json_dump(value) -> str:
    """JSONB: ensure_ascii=False để tiếng Việt đọc được khi soát tay trong psql."""
    import json

    return json.dumps(value, ensure_ascii=False, default=str)


def insert_batch(cur, table: str, columns: Sequence[str], rows: Iterable[Sequence]) -> int:
    """Batch insert theo lô BATCH_SIZE.

    Cột luôn liệt kê tường minh: `combo_items.combo_taxonomy`, `booking_items.line_total`
    và `insider_events.ttl_days` là GENERATED, insert vào sẽ lỗi.
    """
    rows = list(rows)
    if not rows:
        return 0
    placeholder = "(" + ", ".join(["%s"] * len(columns)) + ")"
    statement = f"INSERT INTO {table} ({', '.join(columns)}) VALUES {placeholder}"
    for batch in chunked(rows):
        cur.executemany(statement, batch)
    return len(rows)
