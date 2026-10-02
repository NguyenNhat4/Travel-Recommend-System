"""Part 8a — adapter pgvectorscale (kế thừa pgvector: cùng DDL, cùng dịch filter). Index `diskann` (StreamingDiskANN).

VERIFY đã tra trên timescale/timescaledb-ha:pg16.15-ts2.30.1 (vectorscale 0.9.1, vector 0.8.6), thử thật:
- diskann KHÔNG hỗ trợ halfvec ở 0.9.1 (chỉ vector_cosine_ops/l2/ip trên `vector`) → theo spec 8a: cột `vector({dim})` fp32.
  Adapter vẫn probe bằng tạo thử index trên bảng TẠM mỗi lần create() — bản sau có halfvec thì tự dùng.
- Query vector phải là `::vector` (cast `::halfvec` làm planner bỏ index → Seq Scan).
- GUC truy vấn: diskann.query_search_list_size (1..10000, mặc định 100), diskann.query_rescore (0..1000, mặc định 50).
  Thư viện nạp lười: SET trước khi nạp chỉ tạo placeholder, giá trị ngoài miền bị bỏ qua lặng lẽ → validate miền ở Python.
- Build song song cần ≥ 65.536 vector (catalog build tuần tự).
diskann_labels (label filter ANY-of): bỏ ở fast-track (spec-fasttrack §4 Part 8a).
"""
from __future__ import annotations

from .base import ALL_FILTER_OPS, Capabilities
from .pgvector import PgVectorStore

SLS_RANGE = (1, 10000)
RESCORE_RANGE = (0, 1000)
DISKANN_OPTIONS = ("storage_layout", "num_neighbors", "search_list_size", "max_alpha", "num_dimensions", "num_bits_per_dimension")


class PgVectorScaleStore(PgVectorStore):
    name = "pgvectorscale"
    extension_sql = "CREATE EXTENSION IF NOT EXISTS vectorscale CASCADE"
    index_name = "items_diskann"
    managed_gucs = ("diskann.query_search_list_size", "diskann.query_rescore")

    def __init__(self, cfg, dim, opts=None):
        super().__init__(cfg, dim, opts)
        self.vec_type = "vector"            # xác định lại bằng probe ở create()
        self.opclass = "vector_cosine_ops"
        self.halfvec_probe: str | None = None

    def connect(self) -> None:
        import psycopg
        from pgvector.psycopg import register_vector
        self.conn = psycopg.connect(self.dsn, autocommit=True, prepare_threshold=None)
        self._session_gucs = {}
        self.conn.execute(self.extension_sql)
        register_vector(self.conn)
        self.conn.execute("SELECT NULL::vector")
        if self.opts.timeout_ms:
            self.conn.execute(f"SET statement_timeout = {int(self.opts.timeout_ms)}")
        # bảng đã có (worker perf/quality kết nối lại) → khớp kiểu cột thật
        row = self.conn.execute("SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
                                "WHERE attrelid = to_regclass('items') AND attname = 'embedding'").fetchone()
        if row and row[0]:
            self.vec_type = "halfvec" if row[0].startswith("halfvec") else "vector"
            self.opclass = "halfvec_cosine_ops" if self.vec_type == "halfvec" else "vector_cosine_ops"

    def probe_halfvec(self) -> bool:
        """spec 8a VERIFY: tạo thử index diskann trên cột halfvec của bảng TẠM."""
        try:
            with self.conn.transaction():
                self.conn.execute("CREATE TEMP TABLE vbench_probe (e halfvec(3)) ON COMMIT DROP")
                self.conn.execute("INSERT INTO vbench_probe SELECT ('[' || random() || ',' || random() || ',' || random() || ']')::halfvec "
                                  "FROM generate_series(1, 10)")
                self.conn.execute("CREATE INDEX ON vbench_probe USING diskann (e halfvec_cosine_ops)")
            self.halfvec_probe = "supported"
            return True
        except Exception as e:  # noqa: BLE001
            self.halfvec_probe = f"unsupported: {str(e).splitlines()[0]}"
            return False

    def create(self, index) -> None:
        if self.probe_halfvec():
            self.vec_type, self.opclass = "halfvec", "halfvec_cosine_ops"
        else:
            self.vec_type, self.opclass = "vector", "vector_cosine_ops"
        super().create(index)

    def index_sql(self, params: dict) -> str:
        opts = []
        for k, v in params.items():
            if k not in DISKANN_OPTIONS:
                raise ValueError(f"tham số diskann lạ: {k} (hợp lệ: {DISKANN_OPTIONS})")
            opts.append(f"{k} = {v!r}" if isinstance(v, str) else f"{k} = {v}")
        return f"CREATE INDEX {self.index_name} ON items USING diskann (embedding {self.opclass})" + (
            f" WITH ({', '.join(opts)})" if opts else "")

    def finalize(self) -> float:
        """Build diskann với cùng ngân sách song song như pgvector (fasttrack §4: max_parallel_maintenance_workers).

        Đo 22/09 (100k × 1024, vectorscale 0.9.1): mặc định diskann.force_parallel_workers = -1 build TUẦN TỰ (0 worker,
        209 s) dù ≥ min_vectors_for_parallel_build; đặt = max_parallel_maintenance_workers → 4 worker, 84 s. Tham số index
        vẫn mặc định; chỉ ảnh hưởng thời gian build (B3, ghi nhận).
        """
        n = int(self.conn.execute("SHOW max_parallel_maintenance_workers").fetchone()[0])
        self.build_parallel_workers = n
        self.conn.execute(f"SET diskann.force_parallel_workers = {n}")
        try:
            return super().finalize()
        finally:
            self.conn.execute("RESET diskann.force_parallel_workers")

    def index_meta(self) -> dict:
        return {**super().index_meta(), "diskann_force_parallel_workers": getattr(self, "build_parallel_workers", None),
                "vec_type": self.vec_type, "halfvec_probe": self.halfvec_probe}

    def _guc_items(self, qp: dict) -> list[tuple[str, str]]:
        out = []
        if "query_search_list_size" in qp:
            v = int(qp["query_search_list_size"])
            if not SLS_RANGE[0] <= v <= SLS_RANGE[1]:
                raise ValueError(f"diskann.query_search_list_size ngoài miền {SLS_RANGE}: {v}")
            out.append(("diskann.query_search_list_size", str(v)))
        if "query_rescore" in qp:
            v = int(qp["query_rescore"])
            if not RESCORE_RANGE[0] <= v <= RESCORE_RANGE[1]:
                raise ValueError(f"diskann.query_rescore ngoài miền {RESCORE_RANGE}: {v}")
            out.append(("diskann.query_rescore", str(v)))
        return out

    def capabilities(self) -> Capabilities:
        return Capabilities(exact_search=True, filter_ops=ALL_FILTER_OPS, geo="native", count_exact=True, facet="exact",
                            lexical="ts_rank", vector_dtypes=frozenset({"f32", "binary"}), async_client=True, backup="native",
                            acorn=False,
                            notes=(f"cột vector: {self.vec_type} (probe halfvec diskann: {self.halfvec_probe or 'chưa chạy'})",
                                   "diskann memory_optimized (SBQ 1 bit/chiều ở 1024-d) + rescore",
                                   "GUC truy vấn (diskann.*) đặt mức session, chỉ gửi khi cấu hình đổi",
                                   "compose: NO_TS_TUNE=true để planner/parallel GUC giống container pgvector",
                                   "lexical/facet/backup/diskann_labels chưa cài ở fast-track"))
