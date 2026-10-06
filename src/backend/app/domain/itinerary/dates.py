"""Đọc ngày tường minh trong câu chat bằng luật tất định, không dùng model.

Dùng làm lưới an toàn cho bước trích intent: LLM đôi khi chép lại ngày cũ của chuyến đi thay vì ngày người
dùng vừa nói ("à nhầm ngày 15 tháng 10" ra 14/10). Chỉ nhận các dạng không mơ hồ; chuỗi như "1410" hay
"tuần sau" để LLM tự hiểu.
"""
from __future__ import annotations

import re
from datetime import date

#: Đơn vị đứng sau con số cho biết đó không phải ngày ("3-4 người", "2.5 triệu", "1/2 ngày").
_NOT_A_DATE_AFTER = (r"(?!\s*(?:ngày|ngay|đêm|dem|người|nguoi|người lớn|trẻ|tre|bé|be|tuổi|tuoi|triệu|trieu|tr\b|"
                     r"nghìn|nghin|ngàn|ngan|k\b|đ\b|vnd|sao|giờ|gio|h\b|phút|phut|%))")
_ISO = re.compile(r"(?<!\d)(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)")
_WORDS = re.compile(r"(?<!\d)(\d{1,2})\s*(?:tháng|thang|thg)\s*(\d{1,2})(?:\s*(?:năm|nam)\s*(\d{4}))?(?!\d)"
                    + _NOT_A_DATE_AFTER, re.IGNORECASE)
_NUMERIC = re.compile(r"(?<![\d/.\-])(\d{1,2})\s*([/.\-])\s*(\d{1,2})(?:\s*\2\s*(\d{4}|\d{2}))?(?![\d/.\-])"
                      + _NOT_A_DATE_AFTER, re.IGNORECASE)
#: Thời lượng dạng gói "3 ngày 2 đêm", "3n2d", "2N1Đ": cần cả phần đêm, để "2 ngày nữa" (ngày tương đối) không lọt vào.
_PACKAGE = re.compile(r"(?<!\d)(\d{1,2})\s*(?:ngày|ngay|n)\s*\d{1,2}\s*(?:đêm|dem|đ|d)(?!\w)", re.IGNORECASE)


def this_year(value: date, today: date) -> date:
    """Năm cũ hơn năm hiện tại coi là năm nay: LLM hay gán năm theo dữ liệu huấn luyện ("20/9" → 2023-09-20)."""
    if value.year >= today.year:
        return value
    try:
        return value.replace(year=today.year)
    except ValueError:  # 29/02 của năm không nhuận
        return value.replace(year=today.year, day=28)


def _build(day: str, month: str, year: str | None, today: date) -> date | None:
    full_year = today.year if year is None else int(year) + (2000 if len(year) == 2 else 0)
    try:
        return this_year(date(full_year, int(month), int(day)), today)
    except ValueError:
        return None


def stated_days(text: str) -> int | None:
    """Số ngày của thời lượng dạng gói "N ngày M đêm"/"NnMd" đầu tiên trong `text`: là N, kể cả khi M không phải N-1.

    Theo quy ước của AC-AGT-01 ("3 ngày 2 đêm" là lịch 3 ngày). Không có dạng gói thì `None`; "3 ngày" trơn để LLM hiểu.
    """
    match = _PACKAGE.search(text or "")
    return int(match.group(1)) if match else None


def explicit_dates(text: str, today: date) -> list[date]:
    """Các ngày khác nhau được viết rõ trong `text`, theo thứ tự xuất hiện.

    Nhận `2026-10-15`, `15/10`, `15-10`, `15.10`, `15/10/2026`, `ngày 15 tháng 10 [năm 2026]`, `15 thg 10`.
    Không có năm thì lấy năm của `today`, giống quy tắc của prompt trích intent.
    """
    found: list[tuple[int, date]] = []
    remaining = text or ""
    for pattern, order in ((_ISO, (3, 2, 1)), (_WORDS, (1, 2, 3)), (_NUMERIC, (1, 3, 4))):
        for match in pattern.finditer(remaining):
            day, month, year = (match.group(index) for index in order)
            value = _build(day, month, year, today)
            if value is not None:
                found.append((match.start(), value))
        # Xoá đoạn đã đọc để mẫu sau không đọc lại một phần của nó ("2026-10-15" không thành "10-15").
        remaining = pattern.sub(lambda match: " " * len(match.group(0)), remaining)
    unique: list[date] = []
    for _, value in sorted(found, key=lambda item: item[0]):
        if value not in unique:
            unique.append(value)
    return unique
