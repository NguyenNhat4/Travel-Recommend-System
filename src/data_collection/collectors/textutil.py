"""Tiện ích văn bản: làm sạch, HTML → text, giá, nhận diện tiếng Việt."""

from __future__ import annotations

import html as html_lib
import json
import re
import unicodedata
from typing import Any, Iterable
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup

_WS = re.compile(r"[ \t ​  ]+")
_MANY_NL = re.compile(r"\n{3,}")


def clean_text(s: str | None) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFC", html_lib.unescape(s))
    s = s.replace("\r", "\n")
    lines = [_WS.sub(" ", line).strip() for line in s.split("\n")]
    out = "\n".join(lines)
    return _MANY_NL.sub("\n\n", out).strip()


def html_to_text(fragment: str | None) -> str:
    if not fragment:
        return ""
    if "<" not in fragment:
        return clean_text(fragment)
    soup = BeautifulSoup(fragment, "lxml")
    for bad in soup(["script", "style", "noscript"]):
        bad.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for block in soup.find_all(["p", "div", "li", "h1", "h2", "h3", "h4", "h5", "tr"]):
        block.insert_after("\n")
    return clean_text(soup.get_text())


def node_text(node) -> str:
    if node is None:
        return ""
    for br in node.find_all("br"):
        br.replace_with("\n")
    return clean_text(node.get_text("\n"))


def uniq(items: Iterable[Any]) -> list:
    seen: set = set()
    out = []
    for it in items:
        key = it.casefold() if isinstance(it, str) else json.dumps(it, sort_keys=True, ensure_ascii=False)
        if not it or key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def strip_accents(s: str) -> str:
    s = s.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def fold(s: str | None) -> str:
    """Bỏ dấu, chữ thường, gom khoảng trắng — dùng để so khớp."""
    if not s:
        return ""
    s = strip_accents(s).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return s.strip()


_VI_CHARS = set("ăâđêôơưàáạảãằắặẳẵầấậẩẫèéẹẻẽềếệểễìíịỉĩòóọỏõồốộổỗờớợởỡùúụủũừứựửữỳýỵỷỹ")


def vietnamese_ratio(text: str | None) -> float:
    if not text:
        return 0.0
    letters = [c for c in text.lower() if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if c in _VI_CHARS) / len(letters)


def detect_lang(text: str | None) -> str | None:
    if not text or len(text) < 20:
        return None
    return "vi" if vietnamese_ratio(text) >= 0.04 else "en"


_CURRENCY_PATTERNS = [
    (re.compile(r"(VND|VNĐ|vnđ|₫|\bđ\b|đồng)", re.I), "VND"),
    (re.compile(r"(US\$|USD)"), "USD"),
    (re.compile(r"(€|EUR)"), "EUR"),
    (re.compile(r"(£|GBP)"), "GBP"),
    (re.compile(r"(S\$|SGD)"), "SGD"),
    (re.compile(r"(THB|฿)"), "THB"),
    (re.compile(r"(KRW|₩)"), "KRW"),
    (re.compile(r"(JPY|¥)"), "JPY"),
    (re.compile(r"\$"), "USD"),
]
_NUMBER = re.compile(r"\d[\d.,\s]*\d|\d")


def parse_price(text: str | None, default_currency: str | None = None) -> tuple[float | int | None, str | None]:
    """'VND 5.148.000' → (5148000, 'VND'); 'US$83,08' → (83.08, 'USD'); '~ 3.220.000VNĐ/đêm' → (3220000, 'VND')."""
    if text is None:
        return None, None
    if isinstance(text, (int, float)):
        return text, default_currency
    t = clean_text(str(text))
    currency = next((code for pat, code in _CURRENCY_PATTERNS if pat.search(t)), default_currency)
    m = _NUMBER.search(t)
    if not m:
        return None, currency
    raw = re.sub(r"\s", "", m.group(0))
    if currency in ("VND", "KRW", "JPY") or currency is None and len(re.sub(r"\D", "", raw)) >= 5:
        digits = re.sub(r"\D", "", raw)
        return (int(digits) if digits else None), currency
    # tiền có phần thập phân: đoán dấu thập phân là dấu cuối cùng nếu theo sau là 1-2 chữ số
    last_sep = max(raw.rfind("."), raw.rfind(","))
    if last_sep != -1 and 1 <= len(raw) - last_sep - 1 <= 2:
        whole = re.sub(r"\D", "", raw[:last_sep])
        frac = raw[last_sep + 1 :]
        try:
            return float(f"{whole or 0}.{frac}"), currency
        except ValueError:
            return None, currency
    digits = re.sub(r"\D", "", raw)
    return (int(digits) if digits else None), currency


def first_int(text: str | None) -> int | None:
    if not text:
        return None
    m = re.search(r"\d+", text)
    return int(m.group(0)) if m else None


def first_float(text: str | None) -> float | None:
    if not text:
        return None
    m = re.search(r"\d+(?:[.,]\d+)?", text)
    return float(m.group(0).replace(",", ".")) if m else None


def json_ld_blocks(soup: BeautifulSoup) -> list[dict]:
    out: list[dict] = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string or tag.get_text()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        stack = data if isinstance(data, list) else [data]
        for item in stack:
            if not isinstance(item, dict):
                continue
            graph = item.get("@graph")
            if isinstance(graph, list):
                out.extend(x for x in graph if isinstance(x, dict))
            else:
                out.append(item)
    return out


def meta_content(soup: BeautifulSoup, *names: str) -> str:
    for n in names:
        tag = soup.find("meta", attrs={"property": n}) or soup.find("meta", attrs={"name": n})
        if tag and tag.get("content"):
            return clean_text(tag["content"])
    return ""


def iso_date(value: str | None) -> str | None:
    """'2026-12-31T16:59:00.153' → '2026-12-31'; ngày rỗng kiểu 0001-01-01 → None."""
    if not value or not isinstance(value, str):
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", value)
    if not m or m.group(1) in ("0001", "1900"):
        return None
    return m.group(0)


_ISO_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")
_DAY_MONTH = re.compile(r"(\d{1,2})/(\d{1,2})")


def day_month_iso(text: str | None, hint: str | None) -> str | None:
    """Ngày trang trip.com ghi '14/10' (không có năm) → '2026-10-14', năm lấy từ `hint` là ngày đầy đủ cùng ngày/tháng.
    Đã là ISO thì giữ. Không có `hint` hoặc ngày/tháng lệch `hint` → None: không đoán năm."""
    if not isinstance(text, str):
        return None
    if _ISO_DAY.fullmatch(text):
        return text
    m, full = _DAY_MONTH.search(text), iso_date(hint)
    if not m or not full or (int(m.group(1)), int(m.group(2))) != (int(full[8:10]), int(full[5:7])):
        return None
    return full


def trip_combo_dates(attrs: dict) -> dict:
    """`departDate`/`returnDate` của combo bay+ở trip.com về ISO (hợp đồng `ProductAttributes.returnDate`: format date).
    Năm lấy từ `dDate`/`rDate` của `url` trang tìm kiếm combo (collectors/trip_combos.py `search_url`). Không quy được thì
    bỏ khoá, không giữ chuỗi sai hợp đồng. Combo khác giữ nguyên. Trả bản sao khi có đổi."""
    if attrs.get("comboKind") != "trip_real_flight_hotel" or not ({"departDate", "returnDate"} & attrs.keys()):
        return attrs
    query = parse_qs(urlsplit(attrs.get("url") or "").query)
    out = dict(attrs)
    for key, param in (("departDate", "dDate"), ("returnDate", "rDate")):
        if key in out:
            value = day_month_iso(out[key], (query.get(param) or [None])[0])
            if value is None:
                del out[key]
            else:
                out[key] = value
    return out if out != attrs else attrs
