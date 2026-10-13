"""Xem toàn bộ database `vota` trên monitor (tab "DB"): bảng, dòng và liên kết giữa các bảng.

Công cụ vận hành cho admin (`docs/prd/deployment-plan.md` §5, ngoại lệ NFR-SEC-02). Chỉ đọc: mỗi yêu cầu một kết nối
`default_transaction_read_only`, `statement_timeout` 5 giây, không có SQL tự do; tên schema / bảng / cột chỉ nhận khi có
trong metadata của PostgreSQL. Cột bí mật (tên chứa password / token / secret / hash) luôn hiện "(ẩn)" và không lọc, tìm hay
sắp xếp được (NFR-SEC-01).

Liên kết: khoá ngoại khai báo trong PostgreSQL (hai chiều, kể cả khoá nhiều cột) cộng quan hệ theo quy ước không có khoá
ngoại: `attributes.parentProductId` (vé / phòng → tuyến / khách sạn), `demo:business:<sourceRef>` (vé mô phỏng → vé gốc)
và cột `product_id` của view (vd. `catalog.product_meta`) → `cdp.products`.

Tìm (chốt 2026-10-13, `docs/prd/update-archive/2026-10-13-tim-nhanh-tab-db-monitor.md`): không phân biệt hoa thường và dấu
tiếng Việt. `search()` tìm chung mọi bảng: UUID / mã khớp đúng, chuỗi khác khớp "có chứa" trên các cột chữ ngắn; mỗi bảng
một câu lệnh, chịu riêng `statement_timeout`.
"""
from __future__ import annotations

import base64
import datetime as dt
import decimal
import re
import threading
import time
import unicodedata
import uuid

SCHEMAS = ("cdp", "catalog", "app")
SECRET = re.compile(r"password|token|secret|hash", re.I)
MASK = "(ẩn)"
MAX_LIMIT = 200
META_TTL = 60.0
SIM_PREFIX = "demo:business:"
SEARCH_LIMIT = 10
# Cột chữ dài / không dùng để tìm nhanh (quét chậm, khớp nhiễu): mô tả, nội dung chat, bằng chứng, URL ảnh.
LONG_TEXT = re.compile(r"description|content|evidence|url|image|user_agent|checksum", re.I)
TEXT_TYPES = ("text", "character varying", "character")
HEAVY_TYPES = ("jsonb", "json")  # ô lọc của bảng bỏ qua trừ khi chọn "tìm cả mô tả và JSON"
INT_TYPES = ("integer", "bigint", "smallint")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
# Cột hiện kèm mỗi kết quả tìm chung (ngoài khoá và cột khớp), theo thứ tự ưu tiên.
LABEL_COLUMNS = ("name", "display_name", "product_name", "email", "contact_name", "reference_code", "destination",
                 "taxonomy", "event_name", "query", "status", "label", "source_ref", "cdp_user_id")
# Bảng hay cần tìm nhất đứng trước trong kết quả.
SEARCH_ORDER = ("cdp.products", "app.bookings", "app.users", "app.booking_items", "app.payments", "cdp.profiles",
                "cdp.events", "catalog.combo_items")

MAX_QUERY = 100
COUNT_CAP = 10_000  # ô lọc của bảng chỉ đếm tới đây: từ phổ biến không phải quét hết bảng để đếm

# Không phân biệt hoa thường và dấu tiếng Việt mà không bỏ dấu dữ liệu trong DB: `translate()` / `lower()` trên từng dòng chậm
# gấp 15–30 lần (đo 13/10/2026 trên 12.515 sản phẩm: 639 ms so với 23 ms) và PostgreSQL không có extension `unaccent` (kết
# nối chỉ đọc không tạo được). Thay vào đó chuỗi tìm (đã bỏ dấu) thành biểu thức chính quy: mỗi chữ cái là một lớp ký tự gồm
# mọi dạng hoa / thường / có dấu của nó ("da" → "[DdĐđ][AaÀÁ…]").
_VN = "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ"
_BASE = "".join("d" if c == "đ" else unicodedata.normalize("NFD", c)[0] for c in _VN)
_FOLD_TABLE = {**{ord(a): b for a, b in zip(_VN + _VN.upper(), _BASE + _BASE)},
               **{ord(c): None for c in "̛̣̀́̂̃̆̉"}}
_VARIANTS: dict[str, set[str]] = {}
for _accented, _base in zip(_VN, _BASE):
    _VARIANTS.setdefault(_base, set()).update({_accented, _accented.upper()})
_REGEX_SPECIAL = set("\\^$.|?*+()[]{}")


def fold(text: str) -> str:
    """Chữ thường, bỏ dấu tiếng Việt (cả chuỗi dạng NFD)."""
    return unicodedata.normalize("NFC", text).translate(_FOLD_TABLE).lower()


def accent_regex(text: str) -> str:
    """Biểu thức chính quy (PostgreSQL ARE) khớp `text` bất kể hoa thường và dấu tiếng Việt; khoảng trắng khớp một hay nhiều."""
    out = []
    for ch in fold(text.strip()):
        if ch.isalpha():
            out.append("[" + "".join(sorted({ch, ch.upper(), *_VARIANTS.get(ch, ())})) + "]")
        elif ch.isspace():
            if not out or out[-1] != r"\s+":
                out.append(r"\s+")
        else:
            out.append("\\" + ch if ch in _REGEX_SPECIAL else ch)
    return "".join(out)


def is_secret(column: str) -> bool:
    return bool(SECRET.search(column))


def jsonable(value):
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return base64.b64encode(bytes(value)).decode()
    if isinstance(value, dt.timedelta):
        return value.total_seconds()
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return value


def masked(row: dict) -> dict:
    return {k: (MASK if is_secret(k) and v is not None else jsonable(v)) for k, v in row.items()}


class DbBrowser:
    def __init__(self, url: str, connect=None):
        self.url = url
        self._connect = connect  # tests inject a psycopg-compatible factory
        self._meta = None
        self._meta_at = 0.0
        self._lock = threading.Lock()

    # -- connection
    def connection(self):
        import psycopg
        from psycopg.rows import dict_row
        if self._connect is not None:
            return self._connect()
        conn = psycopg.connect(self.url, connect_timeout=5, row_factory=dict_row,
                               options="-c default_transaction_read_only=on -c statement_timeout=5000")
        conn.read_only = True
        return conn

    def _query(self, sql, params=()):
        with self.connection() as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            return conn.execute(sql, params).fetchall()

    # -- metadata
    def metadata(self, refresh: bool = False) -> dict:
        with self._lock:
            if not refresh and self._meta is not None and time.monotonic() - self._meta_at < META_TTL:
                return self._meta
            with self.connection() as conn:
                conn.execute("SET TRANSACTION READ ONLY")
                tables = conn.execute(
                    """SELECT c.table_schema AS s, c.table_name AS t, c.column_name AS col, c.data_type AS type,
                              tb.table_type AS kind
                         FROM information_schema.columns c
                         JOIN information_schema.tables tb USING (table_schema, table_name)
                        WHERE c.table_schema = ANY(%s)
                        ORDER BY c.table_schema, c.table_name, c.ordinal_position""", (list(SCHEMAS),)).fetchall()
                keys = conn.execute(
                    """SELECT n.nspname AS s, cl.relname AS t, con.contype AS kind, con.conname AS name,
                              ARRAY(SELECT a.attname FROM unnest(con.conkey) WITH ORDINALITY k(n, i)
                                    JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.n ORDER BY k.i) AS cols,
                              fn.nspname AS fs, fcl.relname AS ft,
                              ARRAY(SELECT a.attname FROM unnest(con.confkey) WITH ORDINALITY k(n, i)
                                    JOIN pg_attribute a ON a.attrelid = con.confrelid AND a.attnum = k.n ORDER BY k.i) AS fcols
                         FROM pg_constraint con
                         JOIN pg_class cl ON cl.oid = con.conrelid
                         JOIN pg_namespace n ON n.oid = cl.relnamespace
                         LEFT JOIN pg_class fcl ON fcl.oid = con.confrelid
                         LEFT JOIN pg_namespace fn ON fn.oid = fcl.relnamespace
                        WHERE con.contype IN ('p', 'f') AND n.nspname = ANY(%s)""", (list(SCHEMAS),)).fetchall()
            meta: dict[str, dict] = {}
            for r in tables:
                entry = meta.setdefault(f"{r['s']}.{r['t']}", {"schema": r["s"], "table": r["t"],
                                                               "view": r["kind"] != "BASE TABLE",
                                                               "columns": [], "types": {}, "pk": [], "fks": []})
                entry["columns"].append(r["col"])
                entry["types"][r["col"]] = r["type"]
            for k in keys:
                entry = meta.get(f"{k['s']}.{k['t']}")
                if entry is None:
                    continue
                if k["kind"] == "p":
                    entry["pk"] = list(k["cols"])
                elif f"{k['fs']}.{k['ft']}" in meta:
                    entry["fks"].append({"name": k["name"], "columns": list(k["cols"]),
                                         "target": f"{k['fs']}.{k['ft']}", "targetColumns": list(k["fcols"])})
            self._meta, self._meta_at = meta, time.monotonic()
            return meta

    def _table(self, name: str) -> dict:
        meta = self.metadata()
        if name not in meta:
            raise ValueError("Bảng không có trong database vota")
        return meta[name]

    @staticmethod
    def _ident(entry: dict):
        from psycopg import sql
        return sql.Identifier(entry["schema"], entry["table"])

    def _where(self, entry: dict, filters: dict, q: str, deep: bool = False):
        """Điều kiện lọc. `q`: dòng có đủ mọi từ. Mặc định tìm mọi cột trừ JSON và cột chữ dài (mô tả, nội dung, URL…): đổi
        JSON thành chuỗi rồi so khớp làm ô lọc `cdp.products` production chậm gấp ~10 lần (đo 13/10/2026 trên 30.935 sản
        phẩm: 1,7–2,5 s so với ~0,2 s mỗi câu lệnh). `deep` = tìm cả các cột đó."""
        from psycopg import sql
        parts, params = [], []
        for column, value in (filters or {}).items():
            if column not in entry["columns"]:
                raise ValueError(f"Cột không có trong bảng: {column}")
            if is_secret(column):
                raise ValueError("Không lọc được theo cột bí mật")
            if value is None:
                parts.append(sql.SQL("{} IS NULL").format(sql.Identifier(column)))
            else:
                parts.append(sql.SQL("{}::text = %s").format(sql.Identifier(column)))
                params.append(str(value))
        if q and fold(q).strip():
            readable = [c for c in entry["columns"] if not is_secret(c)]
            visible = [c for c in readable if deep or (entry["types"][c] not in HEAVY_TYPES and not LONG_TEXT.search(c))]
            visible = visible or readable  # bảng chỉ có cột nặng: tìm mọi cột
            text = sql.SQL("concat_ws(' ', {})").format(
                sql.SQL(", ").join(sql.SQL("{}::text").format(sql.Identifier(c)) for c in visible))
            for word in fold(q[:MAX_QUERY]).split():  # dòng có đủ mọi từ, ở cột nào cũng được; không phân biệt hoa thường, dấu
                parts.append(sql.SQL("{} ~ %s").format(text))
                params.append(accent_regex(word))
        clause = sql.SQL(" WHERE ") + sql.SQL(" AND ").join(parts) if parts else sql.SQL("")
        return clause, params

    # -- API
    def tables(self) -> dict:
        from psycopg import sql
        meta = self.metadata()
        counts = {}
        with self.connection() as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            for name, entry in meta.items():
                try:
                    counts[name] = conn.execute(sql.SQL("SELECT count(*) AS n FROM {}").format(
                        self._ident(entry))).fetchone()["n"]
                except Exception:  # permission / timeout on one table: keep the rest of the list
                    conn.rollback()
                    conn.execute("SET TRANSACTION READ ONLY")
                    counts[name] = None
        return {"tables": [{"name": name, "schema": e["schema"], "table": e["table"], "view": e["view"],
                            "rows": counts.get(name), "columns": len(e["columns"]), "pk": e["pk"],
                            "links": len(e["fks"]) + len(self._incoming(name))} for name, e in meta.items()]}

    def graph(self) -> dict:
        """Sơ đồ quan hệ: mọi bảng / view kèm đủ cột (kiểu, khoá chính, khoá ngoại), số dòng, và các cạnh.

        Cạnh `fk` lấy từ khoá ngoại trong PostgreSQL; cạnh `convention` là quan hệ quy ước không có khoá ngoại (cùng quy
        ước với `row()`): sản phẩm cha–con, vé mô phỏng–vé gốc, cột `product_id` của view → `cdp.products`.
        """
        meta = self.metadata()
        counts = {t["name"]: t["rows"] for t in self.tables()["tables"]}
        tables, edges = [], []
        for name, e in meta.items():
            fk_of = {c: fk["target"] for fk in e["fks"] for c in fk["columns"]}
            tables.append({"name": name, "schema": e["schema"], "table": e["table"], "view": e["view"],
                           "rows": counts.get(name),
                           "columns": [{"name": c, "type": e["types"][c], "pk": c in e["pk"], "fk": fk_of.get(c),
                                        "secret": is_secret(c)} for c in e["columns"]]})
            for fk in e["fks"]:
                edges.append({"from": name, "to": fk["target"], "columns": fk["columns"],
                              "targetColumns": fk["targetColumns"], "kind": "fk"})
            if e["view"] and "product_id" in e["columns"] and "cdp.products" in meta:
                edges.append({"from": name, "to": "cdp.products", "columns": ["product_id"],
                              "targetColumns": ["product_id"], "kind": "convention"})
        if "cdp.products" in meta:
            edges.append({"from": "cdp.products", "to": "cdp.products", "columns": ["attributes.parentProductId"],
                          "targetColumns": ["product_id"], "kind": "convention", "label": "sản phẩm con → cha"})
            edges.append({"from": "cdp.products", "to": "cdp.products", "columns": ["source_ref (demo:business:…)"],
                          "targetColumns": ["source_ref"], "kind": "convention", "label": "vé mô phỏng → vé gốc"})
        return {"tables": tables, "edges": edges}

    def rows(self, name: str, filters: dict | None = None, q: str = "", sort: str = "", desc: bool = False,
             offset: int = 0, limit: int = 50, deep: bool = False) -> dict:
        from psycopg import sql
        entry = self._table(name)
        limit, offset = max(1, min(int(limit), MAX_LIMIT)), max(0, int(offset))
        where, params = self._where(entry, filters or {}, q, deep)
        order = sort or (entry["pk"][0] if entry["pk"] else entry["columns"][0])
        if order not in entry["columns"] or is_secret(order):
            raise ValueError("Không sắp xếp được theo cột này")
        body = sql.SQL("FROM {}{}").format(self._ident(entry), where)
        capped = bool(q and q.strip())  # có chuỗi tìm: chỉ đếm tới COUNT_CAP
        with self.connection() as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            if capped:
                total = conn.execute(sql.SQL("SELECT count(*) AS n FROM (SELECT 1 ") + body + sql.SQL(" LIMIT %s) hit"),
                                     params + [COUNT_CAP + 1]).fetchone()["n"]
            else:
                total = conn.execute(sql.SQL("SELECT count(*) AS n ") + body, params).fetchone()["n"]
            data = conn.execute(sql.SQL("SELECT * ") + body + sql.SQL(" ORDER BY {} {} NULLS LAST LIMIT %s OFFSET %s").format(
                sql.Identifier(order), sql.SQL("DESC" if desc else "ASC")), params + [limit, offset]).fetchall()
        more = capped and total > COUNT_CAP
        return {"table": name, "columns": entry["columns"], "types": entry["types"], "pk": entry["pk"],
                "secret": [c for c in entry["columns"] if is_secret(c)], "fks": entry["fks"],
                "total": COUNT_CAP if more else total, "totalCapped": more, "offset": offset, "limit": limit,
                "rows": [masked(r) for r in data]}

    def search(self, q: str, limit: int = SEARCH_LIMIT) -> dict:
        """Tìm nhanh trên mọi bảng (không gồm view, vốn lặp lại dữ liệu của bảng): UUID khớp đúng mọi cột UUID và cột chữ
        chứa mã; số nguyên khớp đúng cột khoá số; chuỗi khác khớp "có chứa" (không phân biệt hoa thường, dấu) trên các cột
        chữ ngắn. Mỗi bảng tối đa `limit` dòng, xếp: khớp trọn → khớp đầu chuỗi → khớp giữa. Bảng lỗi / quá giờ có `error`,
        bảng khác vẫn trả."""
        started = time.monotonic()
        text = (q or "").strip()[:MAX_QUERY]
        folded = fold(text).strip()
        out = {"q": text, "groups": [], "tables": 0}
        if len(folded) < 2:
            return {**out, "ms": 0}
        limit = max(1, min(int(limit), 50))
        meta = self.metadata()
        order = {name: i for i, name in enumerate(SEARCH_ORDER)}
        names = sorted((n for n, e in meta.items() if not e["view"]), key=lambda n: (order.get(n, len(order)), n))
        with self.connection() as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            for name in names:
                entry = meta[name]
                plan = self._search_plan(entry, text, folded)
                if plan is None:
                    continue
                query, params, matchable = plan
                out["tables"] += 1
                try:
                    rows = conn.execute(query, params + [limit + 1]).fetchall()
                except Exception as exc:  # quá giờ / lỗi ở một bảng: các bảng khác vẫn trả
                    conn.rollback()
                    conn.execute("SET TRANSACTION READ ONLY")
                    out["groups"].append({"table": name, "pk": entry["pk"], "columns": [], "rows": [], "more": False,
                                          "error": "quá giờ" if type(exc).__name__ == "QueryCanceled" else type(exc).__name__})
                    continue
                if rows:
                    out["groups"].append(self._search_group(name, entry, rows[:limit], len(rows) > limit, text, folded,
                                                            matchable))
        return {**out, "ms": round((time.monotonic() - started) * 1000)}

    def _search_plan(self, entry: dict, text: str, folded: str):
        """(câu lệnh, tham số, cột có thể khớp) của một bảng, hoặc None khi bảng không có cột nào để tìm."""
        from psycopg import sql
        types = entry["types"]
        cols = [c for c in entry["columns"] if not is_secret(c)]
        short_text = [c for c in cols if types[c] in TEXT_TYPES and not LONG_TEXT.search(c)]
        conds, params, exact, exact_params, prefix, prefix_params, matchable = [], [], [], [], [], [], []
        phrase, phrase_params = [], []
        if UUID_RE.match(text):
            for c in cols:
                if types[c] == "uuid":
                    conds.append(sql.SQL("{} = %s::uuid").format(sql.Identifier(c)))
                    params.append(text)
                    matchable.append(c)
            for c in short_text:  # mã dạng chữ chứa UUID: cdp_user_id, event_group_id, session_id…
                conds.append(sql.SQL("lower({}) = %s").format(sql.Identifier(c)))
                params.append(text.lower())
                matchable.append(c)
        else:
            if text.isdigit() and len(text) <= 18:
                for c in cols:
                    if types[c] in INT_TYPES and (c in entry["pk"] or c.endswith("_id")):
                        condition = sql.SQL("{} = %s").format(sql.Identifier(c))
                        conds.append(condition)
                        params.append(int(text))
                        exact.append(condition)
                        exact_params.append(int(text))
                        matchable.append(c)
            pattern = accent_regex(text)
            words = folded.split()
            if short_text:  # đủ mọi từ, mỗi từ ở cột chữ ngắn nào cũng được ("vinpearl phu quoc": tên + điểm đến)
                every_word = sql.SQL(" AND ").join(
                    sql.SQL("({})").format(sql.SQL(" OR ").join(sql.SQL("{} ~ %s").format(sql.Identifier(c))
                                                                 for c in short_text)) for _ in words)
                conds.append(sql.SQL("({})").format(every_word))
                params += [accent_regex(w) for w in words for _ in short_text]
            for c in short_text:
                column = sql.Identifier(c)
                exact.append(sql.SQL("{} ~ %s").format(column))
                exact_params.append(f"^\\s*{pattern}\\s*$")
                prefix.append(sql.SQL("{} ~ %s").format(column))
                prefix_params.append(f"^\\s*{pattern}")
                phrase.append(sql.SQL("{} ~ %s").format(column))
                phrase_params.append(pattern)
                matchable.append(c)
        if not conds:
            return None
        key = sql.Identifier(entry["pk"][0] if entry["pk"] else entry["columns"][0])
        order = key
        if exact:  # khớp trọn → đầu chuỗi → cả cụm trong một cột → các từ rải ở nhiều cột
            any_of = lambda parts: sql.SQL(" OR ").join(parts) if parts else sql.SQL("false")  # noqa: E731
            order = sql.SQL("CASE WHEN {} THEN 0 WHEN {} THEN 1 WHEN {} THEN 2 ELSE 3 END, {}").format(
                any_of(exact), any_of(prefix), any_of(phrase), key)
        query = sql.SQL("SELECT * FROM {} WHERE {} ORDER BY {} LIMIT %s").format(
            self._ident(entry), sql.SQL(" OR ").join(conds), order)
        return query, params + exact_params + prefix_params + phrase_params, matchable

    @staticmethod
    def _search_group(name: str, entry: dict, rows: list, more: bool, text: str, folded: str, matchable: list) -> dict:
        labels = [c for c in LABEL_COLUMNS if c in entry["columns"]]
        words = folded.split()
        found, wanted = [], []
        for row in rows:
            record = masked(row)
            matched = [c for c in matchable if record.get(c) is not None and (
                str(record[c]).lower() == text.lower() or any(w in fold(str(record[c])) for w in words))]
            found.append((record, matched))
            wanted += matched
        columns = list(dict.fromkeys([*entry["pk"], *wanted, *labels]))[:7]
        return {"table": name, "pk": entry["pk"], "columns": columns, "more": more,
                "rows": [{"key": {c: record.get(c) for c in entry["pk"]} if entry["pk"] else None,
                          "values": {c: record.get(c) for c in columns}, "matched": matched} for record, matched in found]}

    def _incoming(self, name: str) -> list[dict]:
        meta = self.metadata()
        return [{"table": other, **fk} for other, e in meta.items() for fk in e["fks"] if fk["target"] == name]

    def row(self, name: str, key: dict) -> dict:
        from psycopg import sql
        entry = self._table(name)
        if not key:
            raise ValueError("Thiếu khoá của dòng")
        found = self.rows(name, key, limit=2)
        if found["total"] != 1:
            raise ValueError("Khoá không xác định đúng một dòng")
        record = found["rows"][0]
        outgoing = []
        for fk in entry["fks"]:
            values = [record.get(c) for c in fk["columns"]]
            if all(v is not None for v in values):
                outgoing.append({"via": fk["columns"], "table": fk["target"],
                                 "key": dict(zip(fk["targetColumns"], values)), "kind": "fk"})
        incoming = []
        with self.connection() as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            for ref in self._incoming(name):
                values = [record.get(c) for c in ref["targetColumns"]]
                if any(v is None for v in values):
                    continue
                source = self._table(ref["table"])
                filters = dict(zip(ref["columns"], values))
                where, params = self._where(source, filters, "")
                count = conn.execute(sql.SQL("SELECT count(*) AS n FROM {}{}").format(self._ident(source), where),
                                     params).fetchone()["n"]
                incoming.append({"table": ref["table"], "via": ref["columns"], "filters": jsonable(filters),
                                 "count": count, "kind": "fk"})
            self._conventions(conn, name, entry, record, outgoing, incoming)
        return {"table": name, "row": record, "pk": entry["pk"], "outgoing": outgoing, "incoming": incoming,
                "secret": [c for c in entry["columns"] if is_secret(c)]}

    def _conventions(self, conn, name, entry, record, outgoing, incoming) -> None:
        """Quan hệ theo quy ước catalog, không có khoá ngoại trong DDL."""
        products = "cdp.products"
        if name == products:
            attrs = record.get("attributes") or {}
            parent = attrs.get("parentProductId") if isinstance(attrs, dict) else None
            if parent:
                outgoing.append({"via": ["attributes.parentProductId"], "table": products,
                                 "key": {"product_id": parent}, "kind": "convention"})
            ref = record.get("source_ref") or ""
            if ref.startswith(SIM_PREFIX):
                row = conn.execute("SELECT product_id FROM cdp.products WHERE source_ref = %s",
                                   (ref[len(SIM_PREFIX):],)).fetchone()
                if row:
                    outgoing.append({"via": ["source_ref (vé gốc)"], "table": products,
                                     "key": {"product_id": str(row["product_id"])}, "kind": "convention"})
            children = conn.execute("SELECT count(*) AS n FROM cdp.products WHERE attributes->>'parentProductId' = %s",
                                    (record["product_id"],)).fetchone()["n"]
            if children:
                incoming.append({"table": products, "via": ["attributes.parentProductId"], "kind": "convention",
                                 "filters": {"attributes.parentProductId": record["product_id"]}, "count": children})
            copy = conn.execute("SELECT product_id FROM cdp.products WHERE source_ref = %s",
                                (SIM_PREFIX + ref,)).fetchone()
            if copy:
                incoming.append({"table": products, "via": ["source_ref (vé mô phỏng)"], "kind": "convention",
                                 "filters": {"product_id": str(copy["product_id"])}, "count": 1})
            return
        if entry["view"] and "product_id" in entry["columns"] and record.get("product_id"):
            outgoing.append({"via": ["product_id"], "table": products, "key": {"product_id": record["product_id"]},
                             "kind": "convention"})

    def children(self, parent_id: str, offset: int = 0, limit: int = 50) -> dict:
        """Dòng con của một sản phẩm theo attributes.parentProductId (quan hệ quy ước)."""
        limit, offset = max(1, min(int(limit), MAX_LIMIT)), max(0, int(offset))
        with self.connection() as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            total = conn.execute("SELECT count(*) AS n FROM cdp.products WHERE attributes->>'parentProductId' = %s",
                                 (parent_id,)).fetchone()["n"]
            data = conn.execute("SELECT * FROM cdp.products WHERE attributes->>'parentProductId' = %s "
                                "ORDER BY product_id LIMIT %s OFFSET %s", (parent_id, limit, offset)).fetchall()
        entry = self._table("cdp.products")
        return {"table": "cdp.products", "columns": entry["columns"], "types": entry["types"], "pk": entry["pk"],
                "secret": [], "fks": entry["fks"], "total": total, "offset": offset, "limit": limit,
                "rows": [masked(r) for r in data]}
