"""Bước 2 — `description` → `catalog.combo_items` (MOCK_DATA_SPEC §3, DATABASE_SCHEMA §9).

Thành phần combo chỉ tồn tại trong `name`/`description` (chốt 18/09). Job này tách hạng mục, nhận
loại, đoán số lượng/đơn vị, rồi map sang sản phẩm thật bằng trigram similarity của `pg_trgm`.

Ba ràng buộc DDL chi phối toàn bộ module (xem `db/init/01_vota.sql`):

* FK `(item_product_id, item_kind) → cdp.products (product_id, taxonomy)`. `item_kind` vừa là
  loại hiển thị vừa là taxonomy của sản phẩm được trỏ tới, nên `meal`/`transfer`/`other`
  **buộc phải** có `item_product_id = NULL` — không có sản phẩm nào mang taxonomy đó.
* `combo_taxonomy` là GENERATED — không bao giờ liệt kê trong INSERT.
* `unit` chỉ nhận 5 giá trị: đêm · vé · khách · suất · lượt.

Chạy lại được: xoá `source = 'description_parse'`, giữ `manual` (người đã sửa tay).
"""

from __future__ import annotations

import re

from . import config
from .common import insert_batch, normalise_space, strip_accents

COLUMNS = [
    "combo_product_id", "position", "label", "item_kind", "item_product_id",
    "quantity", "unit", "is_optional", "source", "confidence", "evidence",
]

#: "2 đêm", "3 vé", "1 lượt" — số lượng đứng trước đơn vị.
QUANTITY_RE = re.compile(r"(\d+)\s*(đêm|vé|khách|người|suất|lượt|ngày)", re.IGNORECASE)
UNIT_ALIASES = {"người": "khách", "ngày": "đêm"}
VALID_UNITS = {"đêm", "vé", "khách", "suất", "lượt"}


def split_items(name: str, description: str) -> list[str]:
    """Tách `name + ". " + description` thành các đoạn hạng mục (§9.1).

    Bỏ phần mở đầu kiểu "Combo 3N2Đ ... bao gồm:" vì nó là tiêu đề, không phải hạng mục.
    """
    text = f"{name}. {description}"
    # Cắt phần dẫn nhập: mọi thứ trước "bao gồm:" / "gồm:" là tên combo.
    lead = re.split(r"\bbao gồm\s*:|\bgồm\s*:", text, maxsplit=1)
    if len(lead) > 1:
        text = lead[1]

    pattern = "|".join(re.escape(token) for token in config.COMBO_SPLIT_TOKENS)
    parts = re.split(pattern, text)

    items: list[str] = []
    for part in parts:
        cleaned = normalise_space(part).strip(" .;:-")
        if len(cleaned) < 3:
            continue
        # Câu điều kiện ở cuối mô tả không phải hạng mục.
        low = strip_accents(cleaned).lower()
        if low.startswith("ap dung") or low.startswith("gia cho"):
            continue
        items.append(cleaned)
    return items


def classify(label: str) -> tuple[str, str, str | None]:
    """Đoán (item_kind, unit, ghi chú evidence) từ một đoạn nhãn (§9.2).

    Không khớp từ khoá nào → `other`, vẫn giữ nguyên `label` để người soát tay đọc được.
    """
    low = strip_accents(label).lower()

    # "Cáp treo" mơ hồ: vé/khu vui chơi → attraction; đưa đón/di chuyển → transfer (§9 ghi chú).
    if config.CABLE_CAR_TERM in low:
        as_attraction = any(hint in low for hint in config.CABLE_CAR_ATTRACTION_HINTS)
        as_transfer = any(hint in low for hint in config.CABLE_CAR_TRANSFER_HINTS)
        if as_attraction and not as_transfer:
            return "attraction", "vé", None
        if as_transfer and not as_attraction:
            return "transfer", "lượt", None
        return "attraction", "vé", "cáp treo mơ hồ: có thể là attraction hoặc transfer"

    for kind, keywords, unit in config.COMBO_ITEM_KEYWORDS:
        if any(keyword in low for keyword in keywords):
            return kind, unit, None
    return "other", "suất", None


def extract_quantity(label: str, default_unit: str) -> tuple[float, str]:
    match = QUANTITY_RE.search(label)
    if not match:
        return 1.0, default_unit
    quantity = float(match.group(1))
    unit = match.group(2).lower()
    unit = UNIT_ALIASES.get(unit, unit)
    if unit not in VALID_UNITS:
        unit = default_unit
    return quantity, unit


def build_items(combo: dict) -> list[dict]:
    """Thuần: từ một combo ra list hạng mục chưa map sản phẩm.

    `combo` cần các khoá: product_id, name, description.
    Mọi combo phải có ít nhất một dòng (verify.sql "every combo has items"); không parse được
    hạng mục nào thì trả về một dòng `other` mang tên combo.
    """
    items: list[dict] = []
    for label in split_items(combo["name"], combo.get("description") or ""):
        kind, default_unit, note = classify(label)
        quantity, unit = extract_quantity(label, default_unit)
        items.append(
            {
                "label": label[:200],
                "item_kind": kind,
                "quantity": quantity,
                "unit": unit,
                "evidence": note or label[:200],
                "ambiguous": note is not None,
            }
        )

    if not items:
        items.append(
            {
                "label": combo["name"][:200],
                "item_kind": "other",
                "quantity": 1.0,
                "unit": "suất",
                "evidence": "không tách được hạng mục nào từ description",
                "ambiguous": False,
            }
        )
    return items


def _match_product(cur, *, label: str, kind: str, destination: str) -> tuple[str | None, float]:
    """Map một nhãn sang `product_id` bằng trigram similarity trong cùng destination (§3).

    Trả về (product_id hoặc None, confidence). Ưu tiên brand Vinpearl khi điểm xấp xỉ bằng nhau.
    Hotel: ưu tiên `hotel_room` con có roomName khớp; không có thì về property với confidence 0.6.
    """
    if kind in config.COMBO_KINDS_WITHOUT_PRODUCT:
        # FK (item_product_id, item_kind) → products(product_id, taxonomy) không cho phép map.
        return None, config.COMBO_CONFIDENCE_VENUE_ONLY

    taxonomy = kind  # hotel/flight/attraction/golf trùng tên với taxonomy
    if kind == "hotel":
        # Thử hạng phòng trước: khớp trên chính tên phòng, không phải tên khách sạn.
        cur.execute(
            """
            SELECT p.product_id,
                   similarity(unaccent(%s), unaccent(p.name)) AS score_name,
                   similarity(unaccent(%s), unaccent(coalesce(p.attributes->>'roomName',''))) AS score_room,
                   (p.attributes->>'brand' = 'Vinpearl') AS is_vinpearl
            FROM   cdp.products p
            WHERE  p.taxonomy = 'hotel'
              AND  p.attributes->>'level' = 'room'
              AND  p.destination = %s
            ORDER  BY GREATEST(
                        similarity(unaccent(%s), unaccent(p.name)),
                        similarity(unaccent(%s), unaccent(coalesce(p.attributes->>'roomName','')))
                      ) DESC,
                      is_vinpearl DESC
            LIMIT  1
            """,
            (label, label, destination, label, label),
        )
        row = cur.fetchone()
        if row and max(row[1] or 0, row[2] or 0) > config.COMBO_TRGM_THRESHOLD:
            best = max(row[1] or 0, row[2] or 0)
            confidence = (
                config.COMBO_CONFIDENCE_EXACT if best >= 0.8 else config.COMBO_CONFIDENCE_DERIVED_ROOM
            )
            return str(row[0]), confidence

        # Không có phòng khớp → về property, confidence 0.6 (§3).
        cur.execute(
            """
            SELECT p.product_id, similarity(unaccent(%s), unaccent(p.name)) AS score
            FROM   cdp.products p
            WHERE  p.taxonomy = 'hotel'
              AND  p.attributes->>'level' = 'property'
              AND  p.destination = %s
            ORDER  BY score DESC, (p.attributes->>'brand' = 'Vinpearl') DESC
            LIMIT  1
            """,
            (label, destination),
        )
        row = cur.fetchone()
        if row and (row[1] or 0) > config.COMBO_TRGM_THRESHOLD:
            return str(row[0]), config.COMBO_CONFIDENCE_VENUE_ONLY
        return None, config.COMBO_CONFIDENCE_VENUE_ONLY

    cur.execute(
        """
        SELECT p.product_id,
               similarity(unaccent(%s), unaccent(p.name)) AS score,
               similarity(unaccent(%s), unaccent(coalesce(p.attributes->>'venue',''))) AS venue_score
        FROM   cdp.products p
        WHERE  p.taxonomy = %s
          AND  p.destination = %s
        ORDER  BY GREATEST(
                    similarity(unaccent(%s), unaccent(p.name)),
                    similarity(unaccent(%s), unaccent(coalesce(p.attributes->>'venue','')))
                  ) DESC,
                  (p.attributes->>'brand' = 'Vinpearl') DESC
        LIMIT  1
        """,
        (label, label, taxonomy, destination, label, label),
    )
    row = cur.fetchone()
    if not row:
        return None, config.COMBO_CONFIDENCE_VENUE_ONLY
    name_score = row[1] or 0
    venue_score = row[2] or 0
    best = max(name_score, venue_score)
    if best <= config.COMBO_TRGM_THRESHOLD:
        return None, config.COMBO_CONFIDENCE_VENUE_ONLY
    if name_score >= 0.8:
        return str(row[0]), config.COMBO_CONFIDENCE_EXACT
    if name_score > venue_score:
        return str(row[0]), config.COMBO_CONFIDENCE_DERIVED_ROOM
    return str(row[0]), config.COMBO_CONFIDENCE_VENUE_ONLY


def run(conn) -> dict:
    with conn.cursor() as cur:
        # §3: tạo extension trong script, KHÔNG sửa DDL. unaccent cần cho so khớp tiếng Việt
        # (spec chỉ nhắc pg_trgm nhưng câu similarity dùng unaccent()).
        cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        cur.execute("CREATE EXTENSION IF NOT EXISTS unaccent")

        cur.execute(
            "SELECT product_id, name, description, destination "
            "FROM cdp.products WHERE taxonomy = 'combo' ORDER BY source_ref"
        )
        combos = [
            {"product_id": r[0], "name": r[1], "description": r[2], "destination": r[3]}
            for r in cur.fetchall()
        ]

        # Chạy lại được: bỏ dòng tự parse, giữ dòng người sửa tay.
        cur.execute("DELETE FROM catalog.combo_items WHERE source = 'description_parse'")

        rows: list[tuple] = []
        mapped_by_kind: dict[str, list[int]] = {}
        for combo in combos:
            # position phải không đụng dòng manual còn lại của chính combo đó (PK là (combo, position)).
            cur.execute(
                "SELECT coalesce(max(position), 0) FROM catalog.combo_items WHERE combo_product_id = %s",
                (combo["product_id"],),
            )
            position = cur.fetchone()[0]

            for item in build_items(combo):
                position += 1
                product_id, confidence = _match_product(
                    cur,
                    label=item["label"],
                    kind=item["item_kind"],
                    destination=combo["destination"],
                )
                if item["ambiguous"]:
                    confidence = min(confidence, config.CABLE_CAR_AMBIGUOUS_CONFIDENCE)
                if product_id is not None and confidence < config.COMBO_CONFIDENCE_MIN:
                    product_id = None
                if product_id is not None and str(product_id) == str(combo["product_id"]):
                    product_id = None  # CHECK combo_items_not_self

                bucket = mapped_by_kind.setdefault(item["item_kind"], [0, 0])
                bucket[1] += 1
                if product_id is not None:
                    bucket[0] += 1

                rows.append(
                    (
                        combo["product_id"],
                        position,
                        item["label"],
                        item["item_kind"],
                        product_id,
                        item["quantity"],
                        item["unit"],
                        False,
                        "description_parse",
                        round(confidence, 2),
                        item["evidence"],
                    )
                )

        insert_batch(cur, "catalog.combo_items", COLUMNS, rows)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM catalog.combo_items")
        total = cur.fetchone()[0]
        cur.execute(
            "SELECT count(*) FROM catalog.combo_items "
            "WHERE item_product_id IS NULL OR confidence < %s",
            (config.COMBO_REVIEW_THRESHOLD,),
        )
        review_queue = cur.fetchone()[0]
        cur.execute(
            """
            SELECT count(*) FROM cdp.products p
            WHERE p.taxonomy = 'combo'
              AND NOT EXISTS (SELECT 1 FROM catalog.combo_items c
                              WHERE c.combo_product_id = p.product_id)
            """
        )
        empty_combos = cur.fetchone()[0]

    mapping_rate = {
        kind: {"mapped": counts[0], "total": counts[1],
               "rate": round(counts[0] / counts[1], 3) if counts[1] else 0.0}
        for kind, counts in sorted(mapped_by_kind.items())
    }
    total_mapped = sum(c[0] for c in mapped_by_kind.values())
    # Tỷ lệ "map được" chỉ có nghĩa trên các kind MAP ĐƯỢC. meal/transfer/other luôn NULL vì FK
    # (item_product_id, item_kind) → products(product_id, taxonomy) không có taxonomy tương ứng;
    # gộp chúng vào mẫu số sẽ làm chỉ số trông tệ đi mà không phản ánh chất lượng parser.
    mappable = [
        counts for kind, counts in mapped_by_kind.items()
        if kind not in config.COMBO_KINDS_WITHOUT_PRODUCT
    ]
    mappable_total = sum(c[1] for c in mappable)
    mappable_mapped = sum(c[0] for c in mappable)
    return {
        "combos": len(combos),
        "items": total,
        "empty_combos": empty_combos,
        "review_queue": review_queue,
        "mapped_overall": round(total_mapped / total, 3) if total else 0.0,
        "mapped_mappable": round(mappable_mapped / mappable_total, 3) if mappable_total else 0.0,
        "by_kind": mapping_rate,
    }
