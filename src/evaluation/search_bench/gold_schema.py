"""Hợp đồng dữ liệu giữa CLI gold (máy 1) và app gán nhãn Streamlit (máy 2).

Luồng file:

    drafts.txt ──sb gold pool/split──▶ pool_A.csv, pool_B.csv, pool_meta.json
    pool_X.csv ──app Streamlit──────▶ labels/labels_X.csv
    labels_A.csv + labels_B.csv ──sb gold kappa / merge──▶ labels/merged.csv
    merged.csv ──sb gold import──────▶ gold.jsonl ──sb gold check──▶ xanh / đỏ

Quy tắc:
- Chỉ sửa file này trên main. Đổi schema nghĩa là đổi cả hai phía; nhánh nào cần đổi
  thì dừng lại, ghi đề xuất, không tự sửa trong nhánh.
- Mọi CSV ghi bằng UTF-8 có BOM để Excel mở đúng tiếng Việt; đọc được cả file có và
  không có BOM.
- Không file nào ghi giá: guide quy định không chấm giá.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "1"

# ---------------------------------------------------------------------------
# Hằng số dùng chung
# ---------------------------------------------------------------------------

LABELS: tuple[int, ...] = (0, 1, 2)
LABELERS: tuple[str, ...] = ("A", "B")
Label = Literal[0, 1, 2]
Labeler = Literal["A", "B"]

SLICES: tuple[str, ...] = (
    "dest_type",
    "audience_style",
    "amenity_single",
    "amenity_multi",
    "amenity_negation",
    "amenity_offtaxonomy",
    "parent_child",
    "named_entity",
    "no_diacritics",
    "abbrev_typo",
    "multi_constraint",
    "cross_vertical",
    "out_of_catalog",
    # gold_v4 (05/10, người dùng chốt D3 — đề xuất ở docs/spec/bench/gold-v4-bo-sung-va-quy-trinh-gan-nhan.md §14):
    # nối CUỐI để `split` giữ nguyên luồng RNG theo SLICES.index của 13 slice cũ.
    "taxonomy_collision",
    "flight_direction",
)
PARENT_CHILD_SLICE = "parent_child"
OUT_OF_CATALOG_SLICE = "out_of_catalog"

# Điều kiện trên các field này được kiểm ở cấp room / flight (child_filter),
# không ở cấp parent. `sb gold pool` tách filter của drafts theo danh sách này.
CHILD_FILTER_FIELDS: frozenset[str] = frozenset({"unit_price", "max_occupancy", "departure_date"})

CHILDREN_OK_SEP = ";"
CSV_WRITE_ENCODING = "utf-8-sig"
CSV_READ_ENCODING = "utf-8-sig"

# Thứ tự cột của pool_A.csv / pool_B.csv. Mỗi dòng là một cặp (qid, product_id).
POOL_COLUMNS: tuple[str, ...] = (
    "qid",
    "query",
    "slice",
    "filter_text",
    "filter_json",
    "child_filter_json",
    "expected_no_result",
    "product_id",
    "name",
    "taxonomy",
    "destination",
    "star_rating",
    "amenities",
    "snippet",
    "children",
    "from",
    "rank_dense",
    "rank_lex",
    "is_overlap",
)

# App KHÔNG được hiển thị các cột này cho người gán.
# product_id vẫn được dùng làm khoá, chỉ không hiện ra.
HIDDEN_COLUMNS: frozenset[str] = frozenset(
    {"product_id", "filter_json", "child_filter_json", "from", "rank_dense", "rank_lex", "is_overlap"}
)

# `children` chỉ hiện ở slice parent_child (xem children_visible()).
DISPLAY_COLUMNS: tuple[str, ...] = tuple(c for c in POOL_COLUMNS if c not in HIDDEN_COLUMNS)

LABEL_COLUMNS: tuple[str, ...] = (
    "qid",
    "product_id",
    "label",
    "children_ok",
    "note",
    "labeler",
    "labeled_at",
    "pool_sha",
)

MERGED_COLUMNS: tuple[str, ...] = (
    "qid",
    "product_id",
    "label",
    "label_A",
    "label_B",
    "children_ok",
    "needs_discussion",
    "source",
    "note",
)


class SchemaError(ValueError):
    """File không đúng hợp đồng (thiếu cột, sai kiểu, trùng khoá...)."""


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class Child(BaseModel):
    """Một hạng phòng (hoặc chuyến) con của parent, hiện ở slice parent_child."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str


class PoolRow(BaseModel):
    """Một ứng viên cần gán nhãn cho một câu."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    qid: str
    query: str
    slice: str
    filter_text: str = ""
    filter_json: Optional[dict[str, Any]] = None
    child_filter_json: Optional[dict[str, Any]] = None
    expected_no_result: bool = False
    product_id: str
    name: str
    taxonomy: str
    destination: str = ""
    star_rating: Optional[float] = None
    amenities: list[str] = Field(default_factory=list)
    snippet: str = ""
    children: list[Child] = Field(default_factory=list)
    source: Literal["dense", "lexical", "both"] = Field(alias="from")
    rank_dense: Optional[int] = None
    rank_lex: Optional[int] = None
    is_overlap: bool = False

    @field_validator("slice")
    @classmethod
    def _known_slice(cls, v: str) -> str:
        if v not in SLICES:
            raise ValueError(f"slice lạ: {v!r}; nếu tên slice trong drafts khác, sửa SLICES trên main")
        return v

    @model_validator(mode="after")
    def _ranks_match_source(self) -> "PoolRow":
        if self.source in ("dense", "both") and self.rank_dense is None:
            raise ValueError("from = dense/both nhưng thiếu rank_dense")
        if self.source in ("lexical", "both") and self.rank_lex is None:
            raise ValueError("from = lexical/both nhưng thiếu rank_lex")
        return self

    @property
    def key(self) -> tuple[str, str]:
        return (self.qid, self.product_id)

    def child_ids(self) -> set[str]:
        return {c.id for c in self.children}


class LabelRow(BaseModel):
    """Một nhãn do app ghi ra. Mỗi cặp (qid, product_id) đúng một dòng."""

    model_config = ConfigDict(extra="forbid")

    qid: str
    product_id: str
    label: Label
    children_ok: list[str] = Field(default_factory=list)
    note: str = ""
    labeler: Labeler
    labeled_at: datetime
    pool_sha: str

    @model_validator(mode="after")
    def _children_only_with_2(self) -> "LabelRow":
        if self.children_ok and self.label != 2:
            raise ValueError("children_ok chỉ dùng khi label = 2")
        return self

    @property
    def key(self) -> tuple[str, str]:
        return (self.qid, self.product_id)


class MergedRow(BaseModel):
    """Một dòng của merged.csv (đầu ra `sb gold merge`, đầu vào `sb gold import`)."""

    model_config = ConfigDict(extra="forbid")

    qid: str
    product_id: str
    label: Optional[Label] = None
    label_A: Optional[Label] = None
    label_B: Optional[Label] = None
    children_ok: list[str] = Field(default_factory=list)
    needs_discussion: bool = False
    source: Literal["A", "B", "both"]
    note: str = ""

    @model_validator(mode="after")
    def _consistent(self) -> "MergedRow":
        if self.needs_discussion and self.label is not None:
            raise ValueError("needs_discussion = true thì label phải để trống")
        if not self.needs_discussion and self.label is None:
            raise ValueError("label trống mà needs_discussion = false")
        if self.children_ok and self.label not in (2, None):
            raise ValueError("children_ok chỉ dùng khi label = 2")
        if self.source == "both" and (self.label_A is None or self.label_B is None):
            raise ValueError("source = both cần đủ label_A và label_B")
        return self

    @property
    def key(self) -> tuple[str, str]:
        return (self.qid, self.product_id)


class PoolFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    sha256: str
    labeler: Labeler
    n_queries: int
    n_pairs: int


class PoolMeta(BaseModel):
    """pool_meta.json: ghi snapshot và sha để import chặn nhãn lệch pool/snapshot."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    snapshot: str  # ngày snapshot catalog, ví dụ "2026-09-23"
    collection: str  # collection B0 dùng để dựng pool
    depth: int
    seed: int
    drafts_sha256: Optional[str] = None
    overlap_qids: list[str]
    files: dict[Labeler, PoolFile]
    created_at: datetime


class GoldRecord(BaseModel):
    """Một dòng của gold.jsonl (đầu ra `sb gold import`)."""

    model_config = ConfigDict(extra="forbid")

    qid: str
    text: str
    slice: str
    filter: Optional[dict[str, Any]] = None
    child_filter: Optional[dict[str, Any]] = None  # có thể chứa ngày tương đối "{D+30}"
    expected_no_result: bool = False
    judgments: dict[str, Label]
    provenance: dict[str, str]
    expected_children: dict[str, list[str]] = Field(default_factory=dict)
    status: Literal["active", "retired"] = "active"

    @model_validator(mode="after")
    def _keys_consistent(self) -> "GoldRecord":
        if set(self.provenance) != set(self.judgments):
            raise ValueError("provenance phải có đúng các product_id của judgments")
        for pid in self.expected_children:
            if self.judgments.get(pid) != 2:
                raise ValueError(f"expected_children có {pid} nhưng nhãn không phải 2")
        return self


# ---------------------------------------------------------------------------
# Tiện ích file
# ---------------------------------------------------------------------------


def file_sha256(path: str | os.PathLike[str]) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_write_text(path: str | os.PathLike[str], text: str, encoding: str = "utf-8") -> None:
    """Ghi ra file tạm cùng thư mục rồi đổi tên: app có chết giữa chừng cũng không hỏng file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _bool_cell(v: str) -> bool:
    s = (v or "").strip().lower()
    if s in ("true", "1", "yes"):
        return True
    if s in ("false", "0", "no", ""):
        return False
    raise SchemaError(f"giá trị bool không hợp lệ: {v!r}")


def _opt_int(v: str) -> Optional[int]:
    return int(v) if (v or "").strip() != "" else None


def _opt_float(v: str) -> Optional[float]:
    return float(v) if (v or "").strip() != "" else None


def _opt_json(v: str) -> Any:
    return json.loads(v) if (v or "").strip() != "" else None


def _json_cell(v: Any) -> str:
    if v is None:
        return ""
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def _bool_out(v: bool) -> str:
    return "true" if v else "false"


def _num_out(v: Optional[float | int]) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _read_csv_dicts(path: str | os.PathLike[str], expected: tuple[str, ...]) -> list[dict[str, str]]:
    with open(path, encoding=CSV_READ_ENCODING, newline="") as f:
        reader = csv.DictReader(f)
        header = tuple(reader.fieldnames or ())
        missing = [c for c in expected if c not in header]
        extra = [c for c in header if c not in expected]
        if missing or extra:
            raise SchemaError(f"{path}: thiếu cột {missing}, thừa cột {extra}")
        return list(reader)


def _write_csv_dicts(path: str | os.PathLike[str], columns: tuple[str, ...], rows: Iterable[dict[str, str]]) -> None:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(columns), lineterminator="\n")
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    atomic_write_text(path, buf.getvalue(), encoding=CSV_WRITE_ENCODING)


# ---------------------------------------------------------------------------
# Pool
# ---------------------------------------------------------------------------


def pool_row_to_cells(row: PoolRow) -> dict[str, str]:
    return {
        "qid": row.qid,
        "query": row.query,
        "slice": row.slice,
        "filter_text": row.filter_text,
        "filter_json": _json_cell(row.filter_json),
        "child_filter_json": _json_cell(row.child_filter_json),
        "expected_no_result": _bool_out(row.expected_no_result),
        "product_id": row.product_id,
        "name": row.name,
        "taxonomy": row.taxonomy,
        "destination": row.destination,
        "star_rating": _num_out(row.star_rating),
        "amenities": _json_cell(row.amenities),
        "snippet": row.snippet,
        "children": _json_cell([c.model_dump() for c in row.children]),
        "from": row.source,
        "rank_dense": _num_out(row.rank_dense),
        "rank_lex": _num_out(row.rank_lex),
        "is_overlap": _bool_out(row.is_overlap),
    }


def pool_row_from_cells(d: dict[str, str]) -> PoolRow:
    try:
        return PoolRow(
            qid=d["qid"],
            query=d["query"],
            slice=d["slice"],
            filter_text=d["filter_text"],
            filter_json=_opt_json(d["filter_json"]),
            child_filter_json=_opt_json(d["child_filter_json"]),
            expected_no_result=_bool_cell(d["expected_no_result"]),
            product_id=d["product_id"],
            name=d["name"],
            taxonomy=d["taxonomy"],
            destination=d["destination"],
            star_rating=_opt_float(d["star_rating"]),
            amenities=_opt_json(d["amenities"]) or [],
            snippet=d["snippet"],
            children=_opt_json(d["children"]) or [],
            **{"from": d["from"]},
            rank_dense=_opt_int(d["rank_dense"]),
            rank_lex=_opt_int(d["rank_lex"]),
            is_overlap=_bool_cell(d["is_overlap"]),
        )
    except (ValueError, KeyError) as e:  # pydantic.ValidationError là ValueError
        raise SchemaError(f"dòng pool lỗi (qid={d.get('qid')}, product_id={d.get('product_id')}): {e}") from e


def read_pool_csv(path: str | os.PathLike[str]) -> list[PoolRow]:
    rows = [pool_row_from_cells(d) for d in _read_csv_dicts(path, POOL_COLUMNS)]
    seen: set[tuple[str, str]] = set()
    per_qid: dict[str, tuple[str, str, bool]] = {}
    for r in rows:
        if r.key in seen:
            raise SchemaError(f"{path}: trùng cặp {r.key}")
        seen.add(r.key)
        q = (r.query, r.slice, r.expected_no_result)
        if per_qid.setdefault(r.qid, q) != q:
            raise SchemaError(f"{path}: câu {r.qid} có query/slice/expected_no_result khác nhau giữa các dòng")
    return rows


def write_pool_csv(rows: Iterable[PoolRow], path: str | os.PathLike[str]) -> None:
    """Giữ nguyên thứ tự truyền vào: `sb gold split` đã xáo trong từng qid."""
    _write_csv_dicts(path, POOL_COLUMNS, (pool_row_to_cells(r) for r in rows))


def children_visible(row: PoolRow) -> bool:
    return row.slice == PARENT_CHILD_SLICE


# ---------------------------------------------------------------------------
# Nhãn
# ---------------------------------------------------------------------------


def label_row_to_cells(row: LabelRow) -> dict[str, str]:
    return {
        "qid": row.qid,
        "product_id": row.product_id,
        "label": str(row.label),
        "children_ok": CHILDREN_OK_SEP.join(row.children_ok),
        "note": row.note,
        "labeler": row.labeler,
        "labeled_at": row.labeled_at.isoformat(),
        "pool_sha": row.pool_sha,
    }


def _split_children(v: str) -> list[str]:
    return [x.strip() for x in (v or "").split(CHILDREN_OK_SEP) if x.strip()]


def label_row_from_cells(d: dict[str, str]) -> LabelRow:
    try:
        return LabelRow(
            qid=d["qid"],
            product_id=d["product_id"],
            label=int(d["label"]),
            children_ok=_split_children(d["children_ok"]),
            note=d["note"],
            labeler=d["labeler"],
            labeled_at=datetime.fromisoformat(d["labeled_at"]),
            pool_sha=d["pool_sha"],
        )
    except (ValueError, KeyError) as e:
        raise SchemaError(f"dòng nhãn lỗi (qid={d.get('qid')}, product_id={d.get('product_id')}): {e}") from e


def read_labels_csv(path: str | os.PathLike[str]) -> list[LabelRow]:
    rows = [label_row_from_cells(d) for d in _read_csv_dicts(path, LABEL_COLUMNS)]
    seen: set[tuple[str, str]] = set()
    labelers = {r.labeler for r in rows}
    if len(labelers) > 1:
        raise SchemaError(f"{path}: một file chỉ được của một người gán, gặp {sorted(labelers)}")
    for r in rows:
        if r.key in seen:
            raise SchemaError(f"{path}: trùng cặp {r.key}")
        seen.add(r.key)
    return rows


def write_labels_csv(rows: Iterable[LabelRow], path: str | os.PathLike[str]) -> None:
    """Sắp theo (qid, product_id) để diff trên git dễ đọc."""
    ordered = sorted(rows, key=lambda r: r.key)
    _write_csv_dicts(path, LABEL_COLUMNS, (label_row_to_cells(r) for r in ordered))


def upsert_label(path: str | os.PathLike[str], row: LabelRow) -> None:
    """Thêm hoặc thay nhãn của một cặp rồi ghi lại toàn bộ file (an toàn khi app chết giữa chừng)."""
    existing = read_labels_csv(path) if Path(path).exists() else []
    if existing and existing[0].labeler != row.labeler:
        raise SchemaError(f"{path} là file của người gán {existing[0].labeler}, không ghi nhãn của {row.labeler}")
    by_key = {r.key: r for r in existing}
    by_key[row.key] = row
    write_labels_csv(by_key.values(), path)


def validate_label_against_pool(label: LabelRow, pool_row: PoolRow) -> list[str]:
    """Trả về danh sách lỗi (rỗng = hợp lệ). App gọi trước khi lưu; import gọi lại lần nữa."""
    errors: list[str] = []
    if label.key != pool_row.key:
        errors.append(f"nhãn {label.key} không khớp dòng pool {pool_row.key}")
        return errors
    if pool_row.slice == PARENT_CHILD_SLICE:
        if label.label == 2 and not label.children_ok:
            errors.append("slice parent_child: nhãn 2 phải tick ít nhất một hạng phòng đúng loại")
        unknown = set(label.children_ok) - pool_row.child_ids()
        if unknown:
            errors.append(f"children_ok có id không thuộc sản phẩm này: {sorted(unknown)}")
    elif label.children_ok:
        errors.append("children_ok chỉ dùng ở slice parent_child")
    return errors


def missing_pairs(pool_rows: Iterable[PoolRow], labels: Iterable[LabelRow]) -> list[tuple[str, str]]:
    labeled = {r.key for r in labels}
    return [r.key for r in pool_rows if r.key not in labeled]


# ---------------------------------------------------------------------------
# Merged
# ---------------------------------------------------------------------------


def _opt_label(v: str) -> Optional[int]:
    return int(v) if (v or "").strip() != "" else None


def merged_row_to_cells(row: MergedRow) -> dict[str, str]:
    return {
        "qid": row.qid,
        "product_id": row.product_id,
        "label": "" if row.label is None else str(row.label),
        "label_A": "" if row.label_A is None else str(row.label_A),
        "label_B": "" if row.label_B is None else str(row.label_B),
        "children_ok": CHILDREN_OK_SEP.join(row.children_ok),
        "needs_discussion": _bool_out(row.needs_discussion),
        "source": row.source,
        "note": row.note,
    }


def merged_row_from_cells(d: dict[str, str]) -> MergedRow:
    try:
        return MergedRow(
            qid=d["qid"],
            product_id=d["product_id"],
            label=_opt_label(d["label"]),
            label_A=_opt_label(d["label_A"]),
            label_B=_opt_label(d["label_B"]),
            children_ok=_split_children(d["children_ok"]),
            needs_discussion=_bool_cell(d["needs_discussion"]),
            source=d["source"],
            note=d["note"],
        )
    except (ValueError, KeyError) as e:
        raise SchemaError(f"dòng merged lỗi (qid={d.get('qid')}, product_id={d.get('product_id')}): {e}") from e


def read_merged_csv(path: str | os.PathLike[str]) -> list[MergedRow]:
    rows = [merged_row_from_cells(d) for d in _read_csv_dicts(path, MERGED_COLUMNS)]
    seen: set[tuple[str, str]] = set()
    for r in rows:
        if r.key in seen:
            raise SchemaError(f"{path}: trùng cặp {r.key}")
        seen.add(r.key)
    return rows


def write_merged_csv(rows: Iterable[MergedRow], path: str | os.PathLike[str]) -> None:
    ordered = sorted(rows, key=lambda r: r.key)
    _write_csv_dicts(path, MERGED_COLUMNS, (merged_row_to_cells(r) for r in ordered))


# ---------------------------------------------------------------------------
# Pool meta và gold.jsonl
# ---------------------------------------------------------------------------


def read_pool_meta(path: str | os.PathLike[str]) -> PoolMeta:
    with open(path, encoding="utf-8") as f:
        return PoolMeta.model_validate_json(f.read())


def write_pool_meta(meta: PoolMeta, path: str | os.PathLike[str]) -> None:
    atomic_write_text(path, meta.model_dump_json(indent=2) + "\n")


def read_gold_jsonl(path: str | os.PathLike[str]) -> list[GoldRecord]:
    out: list[GoldRecord] = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if line.strip():
                try:
                    out.append(GoldRecord.model_validate_json(line))
                except ValueError as e:
                    raise SchemaError(f"{path} dòng {n}: {e}") from e
    return out


def write_gold_jsonl(records: Iterable[GoldRecord], path: str | os.PathLike[str]) -> None:
    lines = [r.model_dump_json(exclude_none=False) for r in sorted(records, key=lambda r: r.qid)]
    atomic_write_text(path, "\n".join(lines) + "\n")
