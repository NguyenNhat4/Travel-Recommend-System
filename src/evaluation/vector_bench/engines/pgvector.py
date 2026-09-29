"""Part 5 — adapter pgvector (baseline). Database `vbench` của compose project vbench, KHÔNG phải `vota`.

VERIFY đã tra trên pgvector/pgvector:0.8.6-pg16 + pgvector-python 0.5.0 + psycopg 3.3.6 (workflow vbench-verify-research):
- register_vector phải chạy SAU `CREATE EXTENSION vector`; GUC hnsw.* chỉ tồn tại khi vector.so đã nạp → `SELECT NULL::halfvec`.
- `SET LOCAL x = %s` không nhận bind param → dùng `set_config(name, value, true)` (= SET LOCAL, validate giá trị).
- COPY BINARY: halfvec phải là pgvector.HalfVector, uuid phải là uuid.UUID, smallint[] = 'int2[]'.
- Không có toán tử halfvec <=> vector → truyền HalfVector và cast `::halfvec`.
- HNSW trong EXPLAIN chỉ hiện dạng Node Type "Index Scan" + Index Name (CTE MATERIALIZED lồng → duyệt đệ quy).
Lexical (tsv/GIN), facet, backup: bỏ ở fast-track (spec-fasttrack §4 Part 5) — DDL không tạo cột tsv để B3 không gánh chi phí lexical.
"""
from __future__ import annotations

import importlib.metadata as md
import math
import time
import uuid
from typing import Any

import numpy as np

from ..filters import validate
from .base import ALL_FILTER_OPS, BaseStore, Capabilities, Hit, QueryTimeout, StoreOptions, UnsupportedFilter
from .selectivity import SelectivityEstimator, collect_pg_stats

KEYWORD_COLS = {"taxonomy", "destination", "variant"}
BOOL_COLS = {"available"}
NUM_COLS = {"unit_price", "star_rating"}
ITERATIVE = {"off", "strict_order", "relaxed_order"}
M_PER_DEG = 111_320.0     # spec P5.3: Δlat = r/111.320, Δlon = r/(111.320·cos lat)


class PgVectorStore(BaseStore):
    name = "pgvector"
    extension_sql = "CREATE EXTENSION IF NOT EXISTS vector"
    index_name = "items_hnsw"

    def __init__(self, cfg, dim: int, opts: StoreOptions | None = None):
        self.cfg = cfg
        self.dsn = cfg.get("dsn")
        self.dim = dim
        self.opts = opts or StoreOptions()
        self.conn = None
        self._est: SelectivityEstimator | None = None
        self._est_state: dict | None = None
        self.vec_type = "halfvec"
        self.opclass = "halfvec_cosine_ops"
        self._session_gucs: dict[str, str | None] = {}

    managed_gucs = ("hnsw.ef_search", "hnsw.iterative_scan", "hnsw.max_scan_tuples")

    # ------------------------------------------------------------ kết nối
    def connect(self) -> None:
        import psycopg
        from pgvector.psycopg import register_vector
        self.conn = psycopg.connect(self.dsn, autocommit=True, prepare_threshold=None)   # không auto-prepare: plan luôn theo tham số thật
        self._session_gucs = {}                # session mới = GUC mặc định của server
        self.conn.execute(self.extension_sql)
        register_vector(self.conn)
        self.conn.execute(f"SELECT NULL::{self.vec_type}")
        if self.opts.timeout_ms:
            self.conn.execute(f"SET statement_timeout = {int(self.opts.timeout_ms)}")

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None
        self._session_gucs = {}

    def server_version(self) -> str:
        v = self.conn.execute("SHOW server_version").fetchone()[0]
        ext = self.conn.execute("SELECT extname, extversion FROM pg_extension WHERE extname IN ('vector', 'vectorscale')").fetchall()
        return f"postgres {v}; " + ", ".join(f"{a} {b}" for a, b in sorted(ext))

    def client_version(self) -> str:
        return f"psycopg {md.version('psycopg')}; pgvector-python {md.version('pgvector')}"

    def capabilities(self) -> Capabilities:
        return Capabilities(exact_search=True, filter_ops=ALL_FILTER_OPS, geo="native", count_exact=True, facet="exact",
                            lexical="ts_rank", vector_dtypes=frozenset({"f32", "f16", "binary"}), async_client=True,
                            backup="native", acorn=False,
                            notes=("lexical/facet/backup chưa cài ở fast-track (Part 6b, G4, G7)",
                                   "GUC truy vấn (hnsw.*) đặt mức session, chỉ gửi khi cấu hình đổi — 1 round trip mỗi query "
                                   "(SET LOCAL trong transaction thêm ~3 ms/query trên Docker Desktop Windows)",
                                   "psycopg prepare_threshold=None: mọi query lập plan theo tham số thật"))

    # ------------------------------------------------------------ dịch filter (thuần)
    def translate(self, filt: dict | None) -> tuple[str, list[Any]]:
        if filt is None:
            return "TRUE", []
        validate(filt)
        params: list[Any] = []
        return self._tr(filt, params), params

    def _tr(self, node: dict, p: list[Any]) -> str:
        (op, arg), = node.items()
        if op == "and":
            return "(" + " AND ".join(self._tr(c, p) for c in arg) + ")"
        if op == "or":
            return "(" + " OR ".join(self._tr(c, p) for c in arg) + ")"
        if op == "not":
            return f"NOT ({self._tr(arg, p)})"
        if op == "eq":
            col, v = arg
            if col not in KEYWORD_COLS | BOOL_COLS:
                raise UnsupportedFilter("eq", col)
            p.append(v)
            return f"{col} = %s"
        if op == "in":
            col, vals = arg
            if col not in KEYWORD_COLS:
                raise UnsupportedFilter("in", col)
            p.append(list(vals))
            return f"{col} = ANY(%s)"
        if op == "range":
            col, cond = arg
            if col not in NUM_COLS:
                raise UnsupportedFilter("range", col)
            parts = []
            for k in ("gte", "gt", "lte", "lt"):
                if k in cond:
                    p.append(float(cond[k]))
                    parts.append(f"{col} {({'gte': '>=', 'gt': '>', 'lte': '<=', 'lt': '<'})[k]} %s")
            return "(" + " AND ".join(parts) + ")"
        if op == "all":
            p.append([int(x) for x in arg[1]])
            return "amenity_ids @> %s::smallint[]"
        if op == "any":
            p.append([int(x) for x in arg[1]])
            return "amenity_ids && %s::smallint[]"
        if op == "geo":
            lat, lon, r = float(arg["lat"]), float(arg["lon"]), float(arg["radius_m"])
            dlat = r / M_PER_DEG
            dlon = r / (M_PER_DEG * max(math.cos(math.radians(lat)), 1e-9))
            p.extend([lon - dlon, lat - dlat, lon + dlon, lat + dlat, lat, lon, r])
            return "(point(lon, lat) <@ box(point(%s, %s), point(%s, %s)) AND haversine_m(lat, lon, %s, %s) <= %s)"
        if op == "id_in":
            p.append([str(x) for x in arg])
            return "id = ANY(%s::uuid[])"
        raise UnsupportedFilter(op)

    # ------------------------------------------------------------ DDL + nạp
    def ddl(self) -> list[str]:
        return [
            self.extension_sql,
            """CREATE OR REPLACE FUNCTION haversine_m(lat1 float8, lon1 float8, lat2 float8, lon2 float8) RETURNS float8
  LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT AS $$
  SELECT 2 * 6371008.8 * asin(sqrt(
    power(sin(radians(lat2 - lat1) / 2), 2) +
    cos(radians(lat1)) * cos(radians(lat2)) * power(sin(radians(lon2 - lon1) / 2), 2))) $$""",
            "DROP TABLE IF EXISTS items",
            f"""CREATE TABLE items (
  id uuid PRIMARY KEY,
  embedding {self.vec_type}({self.dim}) NOT NULL,
  variant text NOT NULL, taxonomy text NOT NULL, destination text NOT NULL,
  available boolean NOT NULL,
  amenity_ids smallint[] NOT NULL DEFAULT '{{}}',
  unit_price float8, star_rating float8,
  lat float8 NOT NULL, lon float8 NOT NULL
)""",
            "CREATE INDEX items_dest_tax ON items (destination, taxonomy)",
            "CREATE INDEX items_amen     ON items USING gin (amenity_ids)",
            "CREATE INDEX items_price    ON items (unit_price)",
            "CREATE INDEX items_star     ON items (star_rating)",
            "CREATE INDEX items_geo      ON items USING gist (point(lon, lat))",
        ]

    def create(self, index) -> None:
        self._index = index
        for s in self.ddl():
            self.conn.execute(s)
        self._est = None
        self._est_state = None

    def _vec_obj(self, v: np.ndarray):
        from pgvector import HalfVector, Vector
        return HalfVector(v) if self.vec_type == "halfvec" else Vector(np.asarray(v, dtype=np.float32))

    def upsert(self, ids: list[str], vecs: np.ndarray, payloads: list[dict]) -> None:
        cols = "id, embedding, variant, taxonomy, destination, available, amenity_ids, unit_price, star_rating, lat, lon"
        types = ["uuid", self.vec_type, "text", "text", "text", "bool", "int2[]", "float8", "float8", "float8", "float8"]
        with self.conn.cursor() as cur, cur.copy(f"COPY items ({cols}) FROM STDIN WITH (FORMAT BINARY)") as cp:
            cp.set_types(types)
            for pid, v, pl in zip(ids, vecs, payloads):
                cp.write_row((uuid.UUID(pid), self._vec_obj(v), pl["variant"], pl["taxonomy"], pl["destination"],
                              bool(pl["available"]), [int(a) for a in pl["amenity_ids"]], _nullable(pl["unit_price"]),
                              _nullable(pl["star_rating"]), float(pl["lat"]), float(pl["lon"])))

    def index_sql(self, params: dict) -> str:
        with_ = ", ".join(f"{k} = {int(v)}" for k, v in params.items() if k in ("m", "ef_construction"))
        return f"CREATE INDEX {self.index_name} ON items USING hnsw (embedding {self.opclass})" + (f" WITH ({with_})" if with_ else "")

    def finalize(self) -> float:
        t0 = time.perf_counter()
        dl = self.opts.extra.get("deadline")            # chặn thời gian của `vb fast` (perf_counter tuyệt đối)
        to = 0 if dl is None else max(1000, int((dl - time.perf_counter()) * 1000))
        self.conn.execute(f"SET statement_timeout = {to}")
        # ANALYZE trước khi build: sau COPY reltuples = -1; diskann quyết build song song theo số tuple ước lượng
        # (đo 22/09: không ANALYZE → tuần tự 227 s; có → song song) — làm cho cả hai engine Postgres để giữ tương đương
        self.conn.execute("ANALYZE items")
        self.conn.execute(self.index_sql(dict(self._index.params)))
        self.conn.execute("ANALYZE items")
        if self.opts.timeout_ms:
            self.conn.execute(f"SET statement_timeout = {int(self.opts.timeout_ms)}")
        return time.perf_counter() - t0

    def index_meta(self) -> dict:
        r = self.conn.execute("SELECT pg_relation_size(%s), pg_total_relation_size('items')", (self.index_name,)).fetchone()
        return {"index_bytes": int(r[0]), "table_total_bytes": int(r[1])}

    # ------------------------------------------------------------ truy vấn
    def _guc_items(self, qp: dict) -> list[tuple[str, str]]:
        out = []
        if "ef_search" in qp:
            ef = int(qp["ef_search"])
            if not 1 <= ef <= 1000:
                raise ValueError(f"hnsw.ef_search ngoài miền 1..1000: {ef}")
            out.append(("hnsw.ef_search", str(ef)))
        if "iterative_scan" in qp:
            it = str(qp["iterative_scan"])
            if it not in ITERATIVE:
                raise ValueError(f"hnsw.iterative_scan không hợp lệ: {it}")
            out.append(("hnsw.iterative_scan", it))
        if "max_scan_tuples" in qp:
            out.append(("hnsw.max_scan_tuples", str(int(qp["max_scan_tuples"]))))
        return out

    def supports_query_config(self, qp: dict) -> tuple[bool, str]:
        mode = qp.get("mode", "ann")
        if mode not in ("exact", "ann", "auto"):
            return False, f"mode {mode} không có ở {self.name}"
        return True, ""

    def _exact_sql(self, where: str, with_total: bool) -> str:
        total = ", count(*) OVER () AS total" if with_total else ""
        return (f"WITH f AS MATERIALIZED (SELECT id, embedding FROM items WHERE {where}) "
                f"SELECT id, 1 - (embedding <=> %s::{self.vec_type}) AS score{total} FROM f "
                f"ORDER BY embedding <=> %s::{self.vec_type} LIMIT %s")

    def _ann_sql(self, where: str) -> str:
        return (f"WITH r AS MATERIALIZED (SELECT id, embedding <=> %s::{self.vec_type} AS d FROM items WHERE {where} "
                f"ORDER BY embedding <=> %s::{self.vec_type} LIMIT %s) SELECT id, 1 - d AS score FROM r ORDER BY d")

    def build_query(self, q: np.ndarray, filt: dict | None, k: int, qp: dict) -> tuple[str, list[Any], list[tuple[str, str]]]:
        """→ (sql, params, gucs). Thuần trừ mode auto (cần thống kê cache)."""
        where, wp = self.translate(filt)
        qv = self._vec_obj(q)
        mode = qp.get("mode", "ann")
        if mode == "auto":
            n_est = self.estimator().estimate(filt)
            mode = "exact" if n_est <= float(qp["auto_exact_max"]) else "ann"
            if mode == "exact":   # giữ GUC của cấu hình: đổi nhánh không tốn RESET/SET (hnsw.* vô hại với exact)
                return self._exact_sql(where, True), [*wp, qv, qv, k], self._guc_items(qp)
        if mode == "exact":
            return self._exact_sql(where, False), [*wp, qv, qv, k], []
        return self._ann_sql(where), [qv, *wp, qv, k], self._guc_items(qp)

    def search(self, q: np.ndarray, filt: dict | None, k: int, qp: dict) -> list[Hit]:
        sql, params, gucs = self.build_query(q, filt, k, qp)
        try:
            rows = self._execute(sql, params, gucs)
        except Exception as e:  # noqa: BLE001
            if type(e).__name__ == "QueryCanceled":
                raise QueryTimeout(str(e)) from e
            raise
        return [(str(r[0]), float(r[1])) for r in rows]

    def _apply_gucs(self, gucs: list[tuple[str, str]]) -> None:
        """Đặt GUC truy vấn ở mức SESSION, chỉ gửi khi giá trị đổi; GUC không nêu trong cấu hình → RESET về mặc định.

        Lệch câu chữ spec P5.3 (BEGIN; SET LOCAL …; query; COMMIT) — đo trên Docker Desktop/Windows (22/09):
        transaction + set_config thêm ~3 ms/query (3–4 round trip); pipeline mode của psycopg bị kẹt ~140 ms;
        gộp nhiều lệnh vào một Query message (literal vector ~10 KB) ~50 ms. Mỗi connection của bench chỉ phục vụ
        MỘT cấu hình nên SET mức session tương đương SET LOCAL mỗi request, và giống production đặt GUC qua
        server_settings của pool (giữ qua RESET ALL) — 0 round trip thêm. Giá trị đã validate (int / enum) trước khi ghép.
        """
        want = dict(gucs)
        for name in self.managed_gucs:
            val = want.get(name)
            if self._session_gucs.get(name, None) == val:
                continue
            if val is None:
                self.conn.execute(f"RESET {name}")
            else:
                self.conn.execute(f"SET {name} = {val}")
            self._session_gucs[name] = val

    def _execute(self, sql: str, params: list[Any], gucs: list[tuple[str, str]]) -> list[tuple]:
        self._apply_gucs(gucs)
        return self.conn.execute(sql, params).fetchall()

    def ping(self) -> None:
        self.conn.execute("SELECT 1").fetchone()

    def count(self, filt: dict | None) -> tuple[int, bool]:
        where, wp = self.translate(filt)
        return int(self.conn.execute(f"SELECT count(*) FROM items WHERE {where}", wp).fetchone()[0]), True

    def set_available(self, id: str, value: bool) -> None:
        self.conn.execute("UPDATE items SET available = %s WHERE id = %s", (bool(value), uuid.UUID(id)))

    def delete_ids(self, ids: list[str]) -> None:
        self.conn.execute("DELETE FROM items WHERE id = ANY(%s::uuid[])", ([str(i) for i in ids],))

    def delete_all(self) -> None:
        self.conn.execute("TRUNCATE items")

    # ------------------------------------------------------------ mode auto: thống kê cache
    def estimator(self) -> SelectivityEstimator:
        if self._est is None:
            if self._est_state is None:
                with self.conn.transaction():          # một lần, không bị statement_timeout của query (ở 1M unnest ~26M phần tử)
                    self.conn.execute("SET LOCAL statement_timeout = 0")
                    self._est_state = collect_pg_stats(self.conn)
            self._est = SelectivityEstimator(self._est_state)
        return self._est

    def needs_state(self, qps: list[dict]) -> bool:
        return any(qp.get("mode") == "auto" for qp in qps)

    def export_state(self) -> dict:
        self.estimator()
        return {"auto_stats": self._est_state}

    def import_state(self, state: dict) -> None:
        if state.get("auto_stats"):
            self._est_state = state["auto_stats"]
            self._est = SelectivityEstimator(self._est_state)

    def routed_mode(self, filt: dict | None, qp: dict) -> str:
        if qp.get("mode") != "auto":
            return qp.get("mode", "ann")
        return "exact" if self.estimator().estimate(filt) <= float(qp["auto_exact_max"]) else "ann"

    # ------------------------------------------------------------ EXPLAIN (plan_uses_index_rate)
    def plan_uses_index(self, q: np.ndarray, filt: dict | None, k: int, qp: dict) -> bool | None:
        sql, params, gucs = self.build_query(q, filt, k, qp)
        self._apply_gucs(gucs)
        plan = self.conn.execute("EXPLAIN (FORMAT JSON) " + sql, params).fetchone()[0][0]["Plan"]
        return _uses_index(plan, self.index_name)


def _uses_index(node: dict, name: str) -> bool:
    if node.get("Node Type") == "Index Scan" and node.get("Index Name") == name:
        return True
    return any(_uses_index(ch, name) for ch in node.get("Plans", []) or [])


def _nullable(v: Any) -> float | None:
    if v is None:
        return None
    f = float(v)
    return None if math.isnan(f) else f
