"""Parser combo: từ tên + mô tả của combo ra thành phần (combo_items) và giá trị attributes.priceBasis / nights / minPax.

Theo spec "Parser combo" trong tài liệu "V-OTA Database Schema" (20/09/2026), việc #3 và #10. **Không sửa products.jsonl**
(catalog đã đóng băng, form 13 trường + tập khoá attributes giữ nguyên): kết quả ghi ra file riêng để loader của nhóm nạp vào
`catalog.combo_items` và gán thêm attributes cho combo.

    python parse_combos.py [--data-dir data]

Đầu ra (trong --data-dir):
  combo_items.jsonl / combo_items.csv   một dòng một thành phần: combo_product_id, position, label, item_kind, item_product_id,
                                        quantity, unit, is_optional, source, confidence, evidence
  combo_items_review.csv                hàng đợi soát tay: thành phần cần map sang sản phẩm (hotel/attraction/golf/flight) mà
                                        item_product_id NULL hoặc confidence < 0.8
  combo_attributes.json                 productId -> {"attributes": {"priceBasis", "nights"?, "minPax"?}, "evidence": {...}}
  combo_items_report.md                 thống kê
Soát tay: ghi dòng đúng cột như combo_items.jsonl vào `combo_items_manual.jsonl` (source = "manual"); dòng cùng
(combo_product_id, position) thay cho dòng parse và không bị ghi đè khi chạy lại.

Chạy lại được bất kỳ lúc nào; kết quả xác định (không ngẫu nhiên).
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from data_collection.collectors.textutil import fold

SOURCE = "description_parse"
MIN_REVIEW_CONFIDENCE = 0.8
MAPPABLE_KINDS = ("hotel", "attraction", "golf", "flight")

# ------------------------------------------------------------------ nhận loại (từ khoá đã bỏ dấu, chữ thường)
# Thứ tự = độ ưu tiên: cụm cụ thể trước cụm chung. Bảng theo spec, bổ sung từ khoá thấy trong 93 combo thật
# (khu trò chơi, vườn thú, buggy, cano, xông hơi, fastpass ...).
KIND_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("flight", ("ve may bay", "chuyen bay", "hang khong")),
    ("golf", ("golf", "green fee")),
    ("hotel", ("dem", "phong", "nghi duong", "resort", "villa", "suite", "deluxe", "bungalow", "luu tru")),
    ("transfer", ("xe dua don", "dua don", "tau cao toc", "shuttle", "xe dien", "buggy", "cano", "xe buyt")),
    ("meal", ("buffet", "an sang", "an trua", "an toi", "bua", "set menu", "tiec", "bbq", "minibar", "am thuc", "suat an",
              "nha hang", "xuc xich", "pizza", "ga chien", "nuoc ngot", "tra chieu", "banh", "kem", "set ")),
    ("other", ("vip tour", "vip zoo", "premium", "fastpass", "uu tien", "goi dich vu", "qua luu niem", "qua safari", "tui tote",
               "tui vai", "mu luoi", "dau goi", "dau xa", "voucher qua", "spa", "massage", "ho boi", "gym", "late check out",
               "som nhan phong", "trang tri")),
    ("attraction", ("ve ", "vinwonders", "vinpearl safari", "safari", "grand world", "vinpearl land", "tata show", "thuy cung",
                    "aquarium", "cong vien", "cap treo", "show", "khu tro choi", "tro choi", "games", "game", "vuon thu", "vinke",
                    "bao tang", "gondola", "thuyen", "cheo thuyen", "gokart", "vong quay", "tour", "khu ")),
    ("other", ("xong hoi", "jjimjilbang", "tam bun", "tam bien", "te bao chet", "tay da chet", "tri lieu", "thien chuong",
               "voucher", "qua ", "goi ")),
]
DEFAULT_UNIT = {"hotel": "đêm", "attraction": "vé", "golf": "lượt", "flight": "khách", "meal": "suất", "transfer": "lượt", "other": "suất"}
DDL_UNITS = {"đêm", "vé", "khách", "suất", "lượt"}
UNIT_WORDS = {"khu": "khu", "tro": "trò", "game": "trò", "games": "trò", "luot": "lượt", "buoi": "buổi", "suat": "suất",
              "ve": "vé", "tieng": "giờ", "chieu": "chiều", "tuyen": "tuyến", "ngay": "ngày", "dem": "đêm", "nguoi": "người"}
QTY_RE = re.compile(r"\b0*(\d{1,3})\s*(khu|tro|games?|luot|buoi|suat|ve|tieng|chieu|tuyen|ngay|dem)\b")

# Mảnh chỉ là nhãn khuyến mãi / bao bì, không phải thành phần
WRAPPER_RE = re.compile(r"^(?:tieu chuan|\d+ khu|\d+ ngay|\d+ tieng|happy hour|sunset|all in one|jumbo \d+|phieu luu|hang \w+|tron ven(?: \d+ khu)?|pha dao \d+ khu(?: cua hoi)?|ve(?: vao cua)? \d+ khu)?$")
GENERIC_TICKET = {"ve", "ve vao cua", "ve vao cong", "ve tham quan", "ve vao cua truc tiep"}
GIFT_RE = re.compile(r"^\s*(?:tang|tặng)\b\s*", re.I)
SKIP_LINE_RE = re.compile(r"^(?:phu thu|luu y|ve chi|khong|vui long|ap dung|thanh toan|tre em|khach hang)\b")
# Điều khoản / chính sách lẫn trong khối "Bao gồm" của nguồn: không phải thành phần combo
POLICY_RE = re.compile(r"\b(?:hoan|huy|doi tra|quy doi|quy dinh|mien phi|cao (?:tu|duoi|tren)|tre em|nguoi cao tuoi|phu thu|luu y|ap dung|"
                       r"dieu khoan|khong duoc|vui long|chinh sach|hieu luc|su dung trong|thanh toan|xuat trinh|cccd)\b")
DESC_ATTRACTION_RE = re.compile(r"vinwonders|safari|grand world|vinke|aquarium|tata show|thuy cung|gondola|cap treo|vinpearl")
BAD_TICKET_RE = re.compile(r"\b(?:combo|buffet|passport|fastpass|zipline|buggy|tre em|nguoi cao tuoi|nguoi dia phuong|uu dai|sinh vien|"
                           r"hoc sinh|vip|tour|trai nghiem|workshop|khong gioi han|sau \d+h?|tang|voucher|flash sale|ghe|xe dien|bua|set menu|tiec)\b")
GENERIC_WORDS_RE = re.compile(r"\b(?:ve|vao|cua|truc tiep|combo|tieu chuan|tang|dich vu|goi)\b")

# ------------------------------------------------------------------ pg_trgm
def trigrams(text: str) -> set[str]:
    out: set[str] = set()
    for word in fold(text).split():
        padded = f"  {word} "
        out.update(padded[i:i + 3] for i in range(len(padded) - 2))
    return out


def similarity(a: str, b: str) -> float:
    """Giống pg_trgm.similarity(): |A∩B| / |A∪B| trên tập trigram của từng từ (đã bỏ dấu, thêm 2 khoảng trắng đầu và 1 cuối)."""
    ta, tb = trigrams(a), trigrams(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


# ------------------------------------------------------------------ tách và phân loại
def classify(piece: str) -> tuple[str, bool]:
    """Trả (item_kind, mơ_hồ). 'cap treo' vừa là vé vào cửa vừa là phương tiện di chuyển (spec): mơ hồ → confidence 0.6."""
    f = fold(piece)
    ambiguous = "cap treo" in f
    if ambiguous and re.search(r"\b(?:dua don|di chuyen|tau cao toc|cano)\b", f):
        return "transfer", True
    for kind, words in KIND_RULES:
        if any(re.search(rf"\b{re.escape(w.strip())}\b", f) for w in words):
            return kind, ambiguous
    return "other", ambiguous


def strip_tags(name: str) -> str:
    return re.sub(r"\[[^\]]*\]", " ", name)


def split_pieces(text: str) -> list[str]:
    """Cắt theo dấu +, &, |, :, ' - ', ',', ';' và các từ nối 'và', 'kèm', 'bao gồm' (mỗi đoạn là một ứng viên)."""
    text = re.sub(r"\s+(?:kèm(?: theo)?|bao gồm)\s+", " + ", text, flags=re.I)
    parts = re.split(r"\s*(?:\+|&|\||(?<!\d):(?!\d)|;|,|\s[-–]\s|\svà\s)\s*", text)
    return [p.strip(" -–.•►*") for p in parts if p and p.strip(" -–.•►*")]


def core_label(piece: str) -> str:
    """Bỏ chữ 'combo', 'tặng' để so khớp; giữ nguyên chữ có dấu cho label hiển thị ở nơi khác."""
    f = fold(piece)
    f = re.sub(r"\b(combo|tang|goi|tieu chuan)\b", " ", f)
    return re.sub(r"\s+", " ", f).strip()


def parse_quantity(piece: str, kind: str) -> tuple[float, str]:
    m = QTY_RE.search(fold(piece))
    if m:
        return float(m.group(1)), UNIT_WORDS.get(m.group(2), m.group(2))
    return 1.0, DEFAULT_UNIT[kind]


def name_pieces(name: str) -> list[str]:
    return split_pieces(strip_tags(name))


def description_pieces(description: str, policies: dict | None) -> list[str]:
    """Dòng gạch đầu dòng của khối 'Bao gồm' (mô tả hoặc policies), bỏ phụ thu / lưu ý; cắt ở ';' và ' + '."""
    blocks: list[str] = []
    m = re.search(r"(?:^|\n)\s*(?:combo |gói )?bao gồm[^\n]*\n((?:[ \t]*[-•►+*✓].*(?:\n|$)){1,12})", description or "", re.I)
    if m:
        blocks.append(m.group(1))
    for key, val in (policies or {}).items():
        if fold(key).startswith("bao gom") and isinstance(val, str):
            blocks.append(val)
    out: list[str] = []
    for block in blocks:
        for line in block.split("\n"):
            line = line.strip(" \t-•►+*✓")
            if not line or SKIP_LINE_RE.match(fold(line)) or POLICY_RE.search(fold(line)) or len(line) > 90:
                continue
            line = re.sub(r"\s*(?:sử dụng trong ngày|dành cho|cho)\s*0?\d+\s*(?:người|khách)\b.*$", "", line, flags=re.I).strip()
            out.extend(p for p in re.split(r"\s*(?:;|\+)\s*", line) if p.strip())
    return out


# ------------------------------------------------------------------ nights / minPax / priceBasis
NIGHTS_RES = (re.compile(r"\b(\d+)\s*[Nn]\s*(\d+)\s*[ĐđDd]\b"), re.compile(r"\b(\d+)\s*ngày\s*(\d+)\s*đêm\b", re.I))
MINPAX_RES = (re.compile(r"tối thiểu\s*0?(\d+)\s*(?:người|khách)", re.I), re.compile(r"\bcho\s*0?([2-9])\s*(?:người|khách)\b", re.I))
# Bằng chứng mạnh (đúng các ví dụ của spec) → per_person; "vé ... cho 01 người" là bằng chứng yếu hơn nên xét sau giá người lớn / trẻ em
PER_PERSON_TEXT = (re.compile(r"/\s*(?:khách|người)\b", re.I), re.compile(r"giá\s*(?:vé\s*)?cho\s*0?1\s*(?:người|khách)", re.I),
                   re.compile(r"mỗi\s*(?:khách|người)\b", re.I))
GIFT_CONTEXT = re.compile(r"ảnh|quà|tặng|voucher|khăn|nước|kem\b|mũ|túi", re.I)  # "Tặng 01 ảnh lưu niệm/ khách": quà tặng, không phải cơ sở tính giá
PER_PERSON_TICKET = re.compile(r"\bvé\b[^.\n]{0,80}?\bcho\s*0?1\s*(?:người|khách)\b", re.I)


def combo_attributes(product: dict) -> tuple[dict, dict]:
    """(attributes, evidence). priceBasis mặc định per_package; per_person khi mô tả / attributes nói giá theo khách."""
    a = product["attributes"]
    pol = a.get("policies") or {}
    text = "\n".join([product["name"], product.get("description") or ""] + [v for v in pol.values() if isinstance(v, str)])
    attrs: dict = {"priceBasis": "per_package"}
    evidence: dict = {}
    hit = next((m for rx in PER_PERSON_TEXT for m in rx.finditer(text) if not GIFT_CONTEXT.search(text[max(0, m.start() - 40):m.end()])), None)
    if hit:
        attrs["priceBasis"], evidence["priceBasis"] = "per_person", f"mô tả: \"{text[max(0, hit.start() - 20):hit.end() + 10]}\"".replace("\n", " ")
    else:
        if (a.get("childPrice") or 0) > 0 and a.get("adultOriginalPrice"):
            attrs["priceBasis"], evidence["priceBasis"] = "per_person", "attributes: có giá người lớn và giá trẻ em (adultOriginalPrice, childPrice)"
        else:
            m = PER_PERSON_TICKET.search(text)
            if m:
                attrs["priceBasis"], evidence["priceBasis"] = "per_person", f"mô tả: \"{m.group(0)[:80]}\"".replace("\n", " ")
    for rx in NIGHTS_RES:
        m = rx.search(text)
        if m:
            attrs["nights"], evidence["nights"] = int(m.group(2)), m.group(0)
            break
    for rx in MINPAX_RES:
        m = rx.search(text)
        if m and int(m.group(1)) >= 2:
            attrs["minPax"], evidence["minPax"] = int(m.group(1)), m.group(0)
            break
    return attrs, evidence


# ------------------------------------------------------------------ map sang sản phẩm
class Catalog:
    def __init__(self, rows: list[dict]):
        self.by_dest_tickets: dict[str, list[dict]] = defaultdict(list)
        self.by_dest_hotels: dict[str, list[dict]] = defaultdict(list)
        self.rooms_of: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            a = r["attributes"]
            if r["taxonomy"] in ("attraction", "golf"):
                self.by_dest_tickets[r["destination"]].append(r)
            elif r["taxonomy"] == "hotel" and a.get("level") == "property":
                self.by_dest_hotels[r["destination"]].append(r)
            elif r["taxonomy"] == "hotel" and a.get("level") == "room":
                self.rooms_of[a.get("parentProductId")].append(r)

    @staticmethod
    def _ticket_core(r: dict) -> str:
        f = fold(strip_tags(r["name"]))
        return re.sub(r"\b(ve|vao|cua|truc tiep|combo|tieu chuan|nguoi lon)\b", " ", f).strip()

    @staticmethod
    def _standard_rank(r: dict) -> tuple:
        """Vé "chuẩn" của một địa điểm: ít từ khoá phụ (combo, buffet, fastpass, ưu đãi ...) nhất; tên trùng đúng tên địa điểm đứng đầu."""
        f = fold(strip_tags(r["name"]))
        bad = len(BAD_TICKET_RE.findall(f)) + (1 if "+" in r["name"] else 0)
        return (bad, f != fold(r["attributes"].get("venue") or ""), "tieu chuan" not in f, "ve vao cua" not in f,
                r["unitPrice"] if r["unitPrice"] is not None else 10 ** 12, r["sourceRef"])

    def _best_in(self, core: str, pool: list[dict]) -> dict:
        def key(r: dict) -> tuple:
            sim = similarity(core, self._ticket_core(r))
            return (-round(sim, 2) if sim >= 0.25 else 0.0, self._standard_rank(r))
        return min(pool, key=key)

    def map_attraction(self, label: str, combo: dict, kind: str, ambiguous: bool) -> tuple[str | None, float | None, str]:
        """0.95 khớp đúng tên (cùng điểm đến); 0.6 chỉ khớp địa điểm (venue); NULL nếu không có gì khớp. 'cáp treo' mơ hồ → tối đa 0.6."""
        want = "golf" if kind == "golf" else "attraction"
        pool = [r for r in self.by_dest_tickets.get(combo["destination"], []) if r["taxonomy"] == want]
        core = re.sub(r"\b(?:ve|vao|cua|truc tiep|combo|tieu chuan|tang)\b", " ", fold(label))
        core = re.sub(r"\s+", " ", core).strip()
        combo_venue = combo["attributes"].get("venue") or ""
        generic = not core or fold(label) in GENERIC_TICKET
        if not generic and pool:
            best = min(pool, key=lambda r: (-similarity(core, self._ticket_core(r)), self._standard_rank(r)))
            name_sim = similarity(core, self._ticket_core(best))
            if name_sim >= 0.6:
                return best["productId"], 0.6 if ambiguous else 0.95, f"khớp tên {name_sim:.2f}: {best['name'][:70]}"
        # chỉ khớp địa điểm: vé chung chung → venue của combo; tên cụ thể → venue giống tên nhất (>= 0.4)
        venue = combo_venue if generic else ""
        if not generic:
            venues = {(r["attributes"].get("venue") or "") for r in pool} - {""}
            scored = sorted(((similarity(core, v), v) for v in venues), reverse=True)
            if scored and scored[0][0] >= 0.4:
                venue = scored[0][1]
        same = [r for r in pool if venue and (r["attributes"].get("venue") or "") == venue]
        if same:
            pick = self._best_in(core, same)
            return pick["productId"], 0.6, f"chỉ khớp địa điểm \"{venue}\": {pick['name'][:70]}"
        # phân khu / hoạt động nằm trong địa điểm của chính combo (vd. "Công viên nước", "Cáp treo", "Tata Show" trong combo của VinWonders X)
        inside = [r for r in pool if combo_venue and (r["attributes"].get("venue") or "") == combo_venue]
        if kind == "attraction" and inside:
            pick = self._best_in(core, inside)
            return pick["productId"], 0.6, f"phân khu/hoạt động trong địa điểm của combo \"{combo_venue}\": {pick['name'][:70]}"
        return None, None, "không có sản phẩm khớp trong cùng điểm đến"

    def map_hotel(self, label: str, combo: dict) -> tuple[str | None, float | None, str]:
        best, best_sim = None, 0.0
        for h in self.by_dest_hotels.get(combo["destination"], []):
            s = similarity(label, h["name"])
            if s > best_sim:
                best, best_sim = h, s
        if best is None or best_sim < 0.4:
            return None, None, "không có khách sạn khớp trong cùng điểm đến"
        rooms = self.rooms_of.get(best["productId"], [])
        if not rooms:
            return best["productId"], 0.85, f"khớp tên khách sạn {best_sim:.2f}, khách sạn không có hạng phòng: {best['name'][:60]}"
        scored = sorted(((similarity(label, r["attributes"].get("roomName") or ""), r) for r in rooms), key=lambda t: (-t[0], t[1]["unitPrice"] or 10 ** 12))
        s, room = scored[0]
        if s >= 0.5:
            return room["productId"], 0.95, f"khớp khách sạn và hạng phòng {s:.2f}: {room['name'][:70]}"
        return room["productId"], 0.85, f"khớp tên khách sạn {best_sim:.2f}, hạng phòng suy ra (rẻ nhất): {room['name'][:70]}"


# ------------------------------------------------------------------ parse một combo
def parse_combo(combo: dict, cat: Catalog) -> list[dict]:
    a = combo["attributes"]
    venue_fold = fold(a.get("venue") or "")
    ctx_tokens = set(venue_fold.split()) | set(fold(combo["destination"]).split()) | set(fold(a.get("province") or "").split())
    candidates: list[tuple[str, str]] = [(p, f"tên: {p}") for p in name_pieces(combo["name"])]
    for line in description_pieces(combo.get("description") or "", a.get("policies")):
        candidates.append((line, f"mô tả: {line}"))
    items: list[dict] = []
    seen: list[tuple[str, set[str]]] = []
    for piece, evidence in candidates:
        gift = bool(GIFT_RE.match(piece))
        core = core_label(piece)
        if not core or WRAPPER_RE.match(core):
            continue
        kind, ambiguous = classify(piece)
        # tên địa danh đơn thuần (vd. "Cửa Hội") là ngữ cảnh chứ không phải thành phần
        if kind in ("other", "attraction") and set(core.split()) <= ctx_tokens and not re.search(
                r"vinwonders|safari|grand world|vinke|aquarium|vinpearl", core):
            continue
        # số lượng gộp trong mảnh quá ngắn (vd. "03 khu") không phải thành phần
        if re.fullmatch(r"\d+ (?:khu|tro|game|games|luot|ngay|tieng)", core):
            continue
        from_description = evidence.startswith("mô tả")
        if from_description and kind == "attraction" and not DESC_ATTRACTION_RE.search(fold(piece)):
            continue  # dòng mô tả chỉ bổ sung thành phần mà tên chưa nêu; vé chung chung đã có từ tên
        label = re.sub(r"\s+", " ", re.sub(r"(?i)^combo\s+", "", piece)).strip()
        if fold(label) in GENERIC_TICKET:
            label = f"Vé vào cửa {a.get('venue') or combo['destination']}"
        tokens = set(GENERIC_WORDS_RE.sub(" ", fold(label)).split())
        if any(k == kind and (tokens <= t or t <= tokens) for k, t in seen):  # đã có (từ tên hoặc dòng mô tả trước)
            continue
        qty, unit = parse_quantity(piece, kind)
        if unit not in DDL_UNITS:
            unit = DEFAULT_UNIT[kind]
        pid = conf = None
        note = "không map: loại không có trong catalog"
        if kind in ("attraction", "golf"):
            pid, conf, note = cat.map_attraction(label, combo, kind, ambiguous)
        elif kind == "hotel":
            pid, conf, note = cat.map_hotel(label, combo)
        if ambiguous and pid is None:
            note += " (mơ hồ: 'cáp treo' vừa là vé vào cửa vừa là phương tiện di chuyển)"
        seen.append((kind, tokens))
        items.append({"combo_product_id": combo["productId"], "position": len(items) + 1, "label": label, "item_kind": kind,
                      "item_product_id": pid, "quantity": qty, "unit": unit, "is_optional": False, "source": SOURCE,
                      "confidence": conf, "evidence": f"{evidence} | {note}"[:400]})
        if len(items) >= 12:
            break
    if not items:  # spec tuần 1: mọi combo có ít nhất một dòng
        label = re.sub(r"\s+", " ", strip_tags(combo["name"])).strip(" -–")
        items.append({"combo_product_id": combo["productId"], "position": 1, "label": label, "item_kind": "other", "item_product_id": None,
                      "quantity": 1.0, "unit": DEFAULT_UNIT["other"], "is_optional": False, "source": SOURCE, "confidence": None,
                      "evidence": f"tên: {combo['name']} | không tách được thành phần, giữ nguyên tên combo"})
    return items


FIELDS = ["combo_product_id", "position", "label", "item_kind", "item_product_id", "quantity", "unit", "is_optional", "source",
          "confidence", "evidence"]


def load_manual(path: Path) -> dict[tuple[str, int], dict]:
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8").split("\n"):
        if line.strip():
            r = json.loads(line)
            out[(r["combo_product_id"], int(r["position"]))] = {**r, "source": "manual"}
    return out


def needs_review(item: dict) -> bool:
    return item["item_kind"] in MAPPABLE_KINDS and (item["item_product_id"] is None or (item["confidence"] or 0) < MIN_REVIEW_CONFIDENCE) \
        and item["source"] != "manual"


def normalize_unit(item: dict) -> dict:
    """Chuẩn hóa cả dòng parse lẫn dòng manual về enum unit của DDL mà không làm mất quyết định map tay."""
    if item.get("unit") in DDL_UNITS:
        return item
    old = item.get("unit")
    evidence = (item.get("evidence") or "").rstrip()
    note = f"unit chuẩn hóa từ {old!r} theo item_kind={item['item_kind']}"
    return {**item, "unit": DEFAULT_UNIT[item["item_kind"]], "evidence": f"{evidence} | {note}".strip(" |")[:400]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    a = ap.parse_args(argv)
    d = a.data_dir
    with open(d / "products.jsonl", encoding="utf-8") as f:
        rows = [json.loads(l) for l in f]
    combos = [r for r in rows if r["taxonomy"] == "combo"]
    cat = Catalog(rows)
    manual = load_manual(d / "combo_items_manual.jsonl")

    items: list[dict] = []
    attrs_out: dict[str, dict] = {}
    for combo in combos:
        parsed = parse_combo(combo, cat)
        merged = [manual.pop((combo["productId"], it["position"]), it) for it in parsed]
        merged += [m for k, m in sorted(manual.items()) if k[0] == combo["productId"]]
        merged = [normalize_unit(it) for it in merged]
        items.extend(merged)
        attributes, evidence = combo_attributes(combo)
        attrs_out[combo["productId"]] = {"attributes": attributes, "evidence": evidence}

    with open(d / "combo_items.jsonl", "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps({k: it.get(k) for k in FIELDS}, ensure_ascii=False) + "\n")
    with open(d / "combo_items.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(FIELDS)
        w.writerows([[("" if it.get(k) is None else it.get(k)) for k in FIELDS] for it in items])
    by_id = {r["productId"]: r for r in rows}
    review = [it for it in items if needs_review(it)]
    with open(d / "combo_items_review.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["combo_name", "destination", "position", "label", "item_kind", "item_product_id", "matched_name", "confidence", "evidence"])
        for it in review:
            combo = by_id[it["combo_product_id"]]
            hit = by_id.get(it["item_product_id"] or "")
            w.writerow([combo["name"], combo["destination"], it["position"], it["label"], it["item_kind"], it["item_product_id"] or "",
                        hit["name"] if hit else "", "" if it["confidence"] is None else it["confidence"], it["evidence"]])
    (d / "combo_attributes.json").write_text(json.dumps(attrs_out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    kinds = Counter(it["item_kind"] for it in items)
    mappable = [it for it in items if it["item_kind"] in MAPPABLE_KINDS]
    mapped = [it for it in mappable if it["item_product_id"]]
    high = [it for it in mapped if (it["confidence"] or 0) >= MIN_REVIEW_CONFIDENCE]
    per_combo = Counter(it["combo_product_id"] for it in items)
    basis = Counter(v["attributes"]["priceBasis"] for v in attrs_out.values())
    report = [
        "# Kết quả parse combo", "",
        f"- Combo: **{len(combos)}** · thành phần: **{len(items)}** (trung bình {len(items) / max(1, len(combos)):.1f} / combo; "
        f"combo ít nhất một dòng: {sum(1 for c in combos if per_combo[c['productId']] >= 1)}/{len(combos)})",
        "- Theo loại: " + " · ".join(f"{k} {v}" for k, v in kinds.most_common()),
        f"- Thành phần cần map sang sản phẩm ({'/'.join(MAPPABLE_KINDS)}): {len(mappable)}; đã map {len(mapped)} "
        f"({100 * len(mapped) / max(1, len(mappable)):.0f}%), trong đó confidence ≥ {MIN_REVIEW_CONFIDENCE}: {len(high)} "
        f"({100 * len(high) / max(1, len(mappable)):.0f}%)",
        f"- Đã soát tay (`combo_items_manual.jsonl`): {sum(1 for it in items if it['source'] == 'manual')} dòng; hàng đợi soát tay còn lại (`combo_items_review.csv`): {len(review)} dòng",
        f"- priceBasis: " + " · ".join(f"{k} {v}" for k, v in basis.most_common())
        + f"; nights parse được: {sum(1 for v in attrs_out.values() if 'nights' in v['attributes'])}; "
        f"minPax parse được: {sum(1 for v in attrs_out.values() if 'minPax' in v['attributes'])}", "",
        "Lưu ý: cả 93 combo hiện có là combo vé / dịch vụ tại khu vui chơi (VinWonders, Safari, Aquafield ...), không có combo khách sạn, "
        "nên không có thành phần `hotel` và `nights`. Loại meal / transfer / other không có sản phẩm tương ứng trong catalog nên "
        "`item_product_id` = NULL theo đúng spec (không tính vào hàng đợi soát tay).",
    ]
    (d / "combo_items_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
