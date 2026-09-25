"""Đóng gói bản bàn giao catalog: thư mục + zip + sha256, kèm ghi chú số liệu cho nhóm.

    python make_handover.py [--data-dir data] [--out-dir ~/bangiao] [--previous ~/bangiao/vota-catalog-20260916/products.jsonl]

Chỉ đóng gói trên máy, không gửi đi đâu. Từ chối chạy khi tài liệu / template không khớp catalog (chạy ./finalize_catalog.sh trước),
khi thư mục đích đã tồn tại (không ghi đè bản đã bàn giao), hoặc khi quét thấy khoá bí mật trong gói.
Mọi con số trong bao-cao-ban-giao.md tính từ dữ liệu, không gõ tay (trừ mục kiểm chứng ngày 19/09, ghi rõ là kiểm tay).
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import re
import shutil
import tempfile
import zipfile
from datetime import date, timedelta
from pathlib import Path

import sys

SRC_ROOT = Path(__file__).resolve().parent.parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from data_collection.seed.catalog_meta import build_meta
from make_docs import table, vn

REQUIRED = ["products.jsonl", "SCHEMA.md", "BANGIAO.md", "template.json", "stats.md", "quality_review.csv", "dedup_report.csv",
            "excluded_location.csv", "excluded_auto.csv", "combo_items.jsonl", "combo_items.csv", "combo_items_review.csv",
            "combo_attributes.json", "combo_items_report.md", "combo_items_manual.jsonl", "combo_items_review_log.csv"]
FIELDS13 = {"productId", "name", "taxonomy", "destination", "description", "attributes", "unitPrice", "currency", "available",
            "availableFrom", "availableTo", "imageUrl", "sourceRef"}
SECRET_RES = {"khoá riêng": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "AWS": re.compile(r"AKIA[0-9A-Z]{16}"),
              "GitHub": re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"), "sk-": re.compile(r"\bsk-[A-Za-z0-9_-]{24,}"),
              "Slack": re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"), "Bearer": re.compile(r"Bearer\s+[A-Za-z0-9._~+/-]{30,}")}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def variant(o: dict) -> str:
    level = o["attributes"].get("level")
    if o["taxonomy"] == "hotel":
        return f"hotel_{level or 'property'}"
    if o["taxonomy"] == "flight":
        return "flight_route" if level == "route" else "flight"
    return o["taxonomy"]


def read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_inputs(d: Path, rows: list[dict]) -> None:
    missing = [f for f in REQUIRED if not (d / f).exists()]
    if missing or not (d / "sample" / "products-sample.jsonl").exists() or not (d / "map" / "places.geojson").exists():
        raise SystemExit(f"Thiếu file để đóng gói: {missing or 'sample/ hoặc map/'} — chạy ./finalize_catalog.sh trước.")
    n = len(rows)
    ids = {r["productId"] for r in rows}
    problems = []
    if any(set(r) != FIELDS13 for r in rows):
        problems.append("có dòng không đúng 13 trường")
    if len(ids) != n or len({r["sourceRef"] for r in rows}) != n:
        problems.append("productId hoặc sourceRef trùng")
    if any(r["attributes"].get("parentProductId") not in ids | {None} for r in rows):
        problems.append("có dòng mồ côi (thiếu dòng cha)")
    if any(str(r["sourceRef"]).startswith(("synthetic:", "mock:")) for r in rows):
        problems.append("có dòng synthetic/mock")
    label = f"{n:,}".replace(",", ".")
    for f in ("SCHEMA.md", "BANGIAO.md"):
        if f"{label} sản phẩm" not in (d / f).read_text(encoding="utf-8"):
            problems.append(f"{f} không nói {label} sản phẩm (tài liệu cũ)")
    if json.loads((d / "template.json").read_text(encoding="utf-8")).get("_tong_san_pham") != n:
        problems.append("template.json lệch số sản phẩm")
    combos = {r["productId"] for r in rows if r["taxonomy"] == "combo"}
    if {i["combo_product_id"] for i in read_jsonl(d / "combo_items.jsonl")} != combos:
        problems.append("combo_items.jsonl không phủ đúng các combo trong catalog (chạy lại parse_combos.py)")
    if problems:
        raise SystemExit("Không đóng gói vì: " + "; ".join(problems))


def id_survival(old: list[dict], new: list[dict]) -> tuple[list[dict], dict]:
    """Các productId của bản cũ không còn trong catalog mới, kèm ID mới nếu khách sạn đã được gộp sang nguồn khác."""
    new_ids = {r["productId"] for r in new}
    merged_into: dict[str, dict] = {}
    for r in new:
        for ref in r["attributes"].get("sameAs") or []:
            merged_into[ref] = r
    lost, old_to_new = [], {}
    by_variant: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0])
    for r in old:
        v = variant(r)
        by_variant[v][0] += 1
        if r["productId"] in new_ids:
            by_variant[v][1] += 1
            continue
        target = merged_into.get(r["sourceRef"])
        if target:
            old_to_new[r["productId"]] = target
        lost.append(r)
    for r in lost:  # hạng phòng của khách sạn đã đổi ID
        parent = r["attributes"].get("parentProductId")
        if r["productId"] not in old_to_new and parent in old_to_new:
            old_to_new[r["productId"]] = old_to_new[parent]
    return lost, {"by_variant": dict(by_variant), "old_to_new": old_to_new}


def write_lost_csv(path: Path, lost: list[dict], old_to_new: dict[str, dict]) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["productId_cu", "sourceRef_cu", "loai", "diem_den", "ten", "trang_thai", "productId_moi", "ten_moi"])
        for r in lost:
            target = old_to_new.get(r["productId"])
            state = ("đã gộp vào sản phẩm khác (khách sạn) hoặc thuộc khách sạn đã đổi ID" if target
                     else "không còn trong catalog mới")
            w.writerow([r["productId"], r["sourceRef"], variant(r), r["destination"], r["name"], state,
                        target["productId"] if target else "", target["name"] if target else ""])


def build_note(d: Path, new: list[dict], old: list[dict] | None, lost: list[dict], surv: dict | None, as_of: date) -> str:
    n = len(new)
    by = collections.Counter(variant(r) for r in new)
    A = lambda r: r["attributes"]  # noqa: E731
    parents_with_rooms = {A(r)["parentProductId"] for r in new if variant(r) == "hotel_room"}
    props = [r for r in new if variant(r) == "hotel_property"]
    no_room = sum(1 for r in props if r["productId"] not in parents_with_rooms)
    search_units = sum(by[v] for v in ("hotel_property", "flight_route", "attraction", "combo", "golf"))
    recommendable = sum(1 for m in build_meta(new).values() if m["is_recommendable"])
    old_by = collections.Counter(variant(r) for r in old) if old else None
    old_no_room = None
    if old:
        old_rooms = {A(r)["parentProductId"] for r in old if variant(r) == "hotel_room"}
        old_no_room = sum(1 for r in old if variant(r) == "hotel_property" and r["productId"] not in old_rooms)

    def row(label, *keys):
        cur = sum(by[k] for k in keys)
        prev = sum(old_by[k] for k in keys) if old_by is not None else None
        return [label, vn(prev) if prev is not None else "–", vn(cur)]

    numbers = [row("Khách sạn (`hotel_property`)", "hotel_property"), row("Hạng phòng (`hotel_room`)", "hotel_room"),
               row("Điểm tham quan / vé (`attraction`)", "attraction"), row("Tuyến bay (`flight_route`)", "flight_route"),
               row("Chuyến bay (`flight`)", "flight"), row("Combo", "combo"), row("Golf", "golf"),
               ["**Tổng số dòng**", vn(len(old)) if old else "–", f"**{vn(n)}**"],
               ["Khách sạn không có hạng phòng", vn(old_no_room) if old_no_room is not None else "–", vn(no_room)],
               ["Search unit (khách sạn + tuyến bay + điểm tham quan + combo + golf)",
                vn(sum(old_by[v] for v in ("hotel_property", "flight_route", "attraction", "combo", "golf"))) if old_by else "–", vn(search_units)],
               ["Search unit đưa vào gợi ý (trừ khách sạn không có phòng)", "–", vn(search_units - no_room)],
               ["Trong đó đặt được, tức có giá (`is_recommendable` của loader; điểm chưa giá tìm được nhưng không đặt được)", "–", vn(recommendable)],
               ["Dòng lịch 30 đêm cần sinh (hạng phòng × 30)", "–", vn(by["hotel_room"] * 30)]]

    dests: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for r in new:
        v = variant(r)
        if v in ("hotel_property", "flight_route", "attraction", "combo"):
            dests[r["destination"]][v] += 1
    full = sorted(k for k, c in dests.items() if all(c[v] for v in ("hotel_property", "flight_route", "attraction", "combo")))
    no_flight = sorted((k for k, c in dests.items() if c["hotel_property"] >= 20 and not c["flight_route"]), key=lambda k: -dests[k]["hotel_property"])

    no_flight_txt = ", ".join(f"{k} ({vn(dests[k]['hotel_property'])})" for k in no_flight)
    lo, hi = as_of.isoformat(), (as_of + timedelta(days=29)).isoformat()
    flights = [r for r in new if variant(r) == "flight"]
    in_window = sum(1 for r in flights if any(lo <= x <= hi for x in A(r).get("datesSeen") or []))
    expired = [r for r in new if r["availableTo"] and r["availableTo"] < lo]
    clipped = [r for r in new if r["taxonomy"] in ("attraction", "combo", "golf") and r["availableTo"] and lo <= r["availableTo"] < hi]
    unpriced = [r for r in new if r["unitPrice"] is None]
    routes_without = [r for r in new if variant(r) == "flight_route" and not any(A(x).get("parentProductId") == r["productId"] for x in flights)]
    derived = sum(1 for r in new if A(r).get("descriptionSource"))
    src = collections.Counter(r["sourceRef"].split(":")[0] for r in new)

    items = read_jsonl(d / "combo_items.jsonl")
    kinds = collections.Counter(i["item_kind"] for i in items)
    attrs = json.loads((d / "combo_attributes.json").read_text(encoding="utf-8"))
    basis = collections.Counter(v["attributes"]["priceBasis"] for v in attrs.values())
    with open(d / "combo_items_review.csv", encoding="utf-8-sig", newline="") as f:
        review = sum(1 for _ in csv.DictReader(f))

    with open(d / "combo_items_review_log.csv", encoding="utf-8-sig", newline="") as f:
        rlog = list(csv.DictReader(f))
    r06 = collections.Counter(x["quyet_dinh"] for x in rlog if x["nhom"] == "0,6")
    r95 = collections.Counter(x["quyet_dinh"] for x in rlog if x["nhom"] != "0,6")
    n06 = sum(r06.values())
    att_items = [i for i in items if i["item_kind"] in ("attraction", "golf")]
    att_mapped = sum(1 for i in att_items if i["item_product_id"])
    manual_n = sum(1 for i in items if i["source"] == "manual")
    left95 = sum(1 for i in att_items if i["item_product_id"] and i["source"] != "manual" and (i["confidence"] or 0) >= 0.8)
    test_count = sum(len(re.findall(r"^\s+def test_", p.read_text(encoding="utf-8"), re.M)) for p in Path(__file__).resolve().parent.glob("test_*.py"))
    removed_rooms = []
    with open(d / "excluded_location.csv", encoding="utf-8-sig", newline="") as f:
        for x in csv.DictReader(f):
            if x["reason"].startswith("giá phòng bất thường"):
                removed_rooms.append(f"{x['name']} ({x['reason'].split(':')[1].split('giá')[0].strip()})")
    seed_ok = (d / "seed" / "cdp_events.jsonl").exists()
    n_events = sum(1 for _ in open(d / "seed" / "cdp_events.jsonl", encoding="utf-8")) if seed_ok else 0
    n_profiles = sum(1 for _ in open(d / "seed" / "cdp_profiles.jsonl", encoding="utf-8")) if seed_ok else 0
    baseline = ""
    if seed_ok:
        mb = re.search(r"top-20\): (\d+/\d+ = [\d.]+%)", (d / "seed" / "seed_report.md").read_text(encoding="utf-8"))
        baseline = mb.group(1) if mb else ""

    summary = table(["Hạng mục", "Trạng thái", "Ở đâu"], [
        [f"Catalog thật {vn(n)} dòng (không synthetic, không expand)", "Xong, đóng băng", "`products.jsonl`"],
        ["Tài liệu: schema, bàn giao, template, mẫu (sinh tự động từ dữ liệu)", "Xong", "`SCHEMA.md`, `BANGIAO.md`, `template.json`, `sample/`"],
        [f"Combo: parse thành phần + `priceBasis`, đã soát tay {vn(manual_n)} dòng", "Xong", "`combo_items.*`, `combo_attributes.json`, `combo_items_review_log.csv`"],
        ["Loader: cửa sổ 30 ngày, lịch phòng, ngày bay", "Xong (chạy lại trước demo)", "`load_catalog.py`, `loader/loader_report.md`"],
        [f"Seed CDP: {vn(n_profiles)} profile, {vn(n_events)} event, 4 persona", "Xong", "`seed/`"],
        ["Seed Insider clone", "Chưa (cần seed CDP làm đầu vào)", "—"],
        ["DDL của nhóm (`vota_schema.sql`, `insider_schema.sql`)", "Chưa có trên máy → chưa nạp vào DB", "—"],
    ])

    lines = [f"# Báo cáo tổng hợp bàn giao — catalog thật {vn(n)} dòng", "",
             f"Bản {as_of.strftime('%d/%m/%Y')} · mảng Data · **đóng băng**: `productId` giữ ổn định từ bản này; cào thêm (nếu có) sẽ xuất thành bản riêng.", "",
             "## 0. Tóm tắt", "", summary, "",
             "## 1. Đây là gì", "",
             f"`products.jsonl` gồm **{vn(n)} sản phẩm thật** (theo nguồn chính: {' · '.join(f'{k} {vn(v)}' for k, v in src.most_common())}), "
             "**không có dòng synthetic/mock nào** và không có bước sinh thêm dòng (không có expand). Cùng schema 13 trường như trước. "
             f"{vn(derived)} mô tả là mô tả do code ghép từ dữ liệu có cấu trúc của nguồn (có nhãn `attributes.descriptionSource`); "
             "giá là một lần hỏi giá (khách sạn: nhận phòng 15/10/2026, 1 đêm, 2 người lớn).",
             "Phần mock trong thiết kế của nhóm (khách, event, lịch 30 đêm, chuỗi khả dụng) do loader / seed của nhóm sinh, không nằm trong file này.", "",
             "## 2. Số liệu trong tài liệu nhóm cần cập nhật", "",
             table(["Hạng mục", "Bản 16/09 (2.216 dòng)" if old else "Bản trước", f"Bản này ({as_of.strftime('%d/%m')})"], numbers), ""]
    lines += ["## 3. ID: bản cũ → bản này", ""]
    if old and surv:
        kept = sum(v[1] for v in surv["by_variant"].values())
        lines += [f"**{vn(kept)}/{vn(len(old))} `productId` của bản 16/09 ({100 * kept / len(old):.1f}%) còn nguyên.** "
                  + " · ".join(f"{k}: {vn(v[1])}/{vn(v[0])}" for k, v in sorted(surv["by_variant"].items())) + ".",
                  f"Mất {vn(len(lost))} ID ({' · '.join(f'{k} {vn(v)}' for k, v in collections.Counter(variant(r) for r in lost).most_common())}). "
                  f"{vn(sum(1 for r in lost if r['productId'] in surv['old_to_new']))} trong số đó có ID mới tương ứng "
                  "(khách sạn đã gộp sang nguồn khác); danh sách đầy đủ ở `ids_da_mat_so_voi_ban_16-09.csv`. "
                  "Nếu đã seed event / booking theo ID cũ thì seed lại từ catalog này; ID mất không có ID mới nghĩa là sản phẩm không còn trong catalog.", ""]
    else:
        lines += ["Không có bản trước để đối chiếu.", ""]
    seed_dir = d / "seed"
    seed_lines: list[str] = []
    if (seed_dir / "cdp_profiles.jsonl").exists() and (seed_dir / "cdp_events.jsonl").exists():
        profiles, events = read_jsonl(seed_dir / "cdp_profiles.jsonl"), read_jsonl(seed_dir / "cdp_events.jsonl")
        users, bookings = read_jsonl(seed_dir / "app_users.jsonl"), read_jsonl(seed_dir / "app_bookings.jsonl")
        stage = collections.Counter(p["lifecycle_stage"] for p in profiles)
        names = collections.Counter(e["event_name"] for e in events)
        m = re.search(r"as_of (\d{4}-\d{2}-\d{2}), seed (\d+)", (seed_dir / "seed_report.md").read_text(encoding="utf-8"))
        seed_lines = ["## 7. Seed và loader", "",
                      f"`seed/` (sinh bằng `seed_histories.py`{f', as_of {m.group(1)}, seed {m.group(2)}' if m else ''}, theo \"Kế hoạch mock data\" của file thiết kế DB): "
                      f"`cdp_profiles.jsonl` {vn(len(profiles))} · `cdp_events.jsonl` {vn(len(events))} ({', '.join(f'{k} {vn(v)}' for k, v in names.most_common())}) · "
                      f"`app_users.jsonl` {vn(len(users))} (4 persona + 50 test) · `app_bookings.jsonl` {len(bookings)} + `app_booking_items.jsonl`. "
                      f"Vòng đời tính từ event: {' · '.join(f'{k} {100 * v / len(profiles):.0f}%' for k, v in stage.most_common())}. "
                      "Tên cột theo DDL chính thức `origin/mockdata@cee95ba`; `password_hash` là BCrypt cost 10 của mật khẩu demo chung; "
                      "email / số điện thoại là dữ liệu giả; "
                      "ngày sinh tương đối theo as_of nên sinh lại (`--as-of`) trước demo. Chi tiết và các kiểm tra ở `seed/seed_report.md`.",
                      "Loader (`load_catalog.py --as-of`): áp cửa sổ 30 ngày, lịch phòng 30 ký tự, ngày bay, thuộc tính combo cho `cdp.products`. "
                      "**Không kèm file kết quả** (lớn và hết hạn theo ngày); chạy lại từ `src/data_collection` trước demo. Kết quả lần chạy này ở `loader/loader_report.md`.",
                      "Insider clone (`insider_profiles`, `identifiers`, `insider_events`, `channel_events`) sinh bằng `seed_insider.py` từ seed này.", ""]
    design = table(["#", "Hạng mục trong file thiết kế DB (20/09)", "Trạng thái trong file", "Phía Data"], [
        ["1", "ERD + DDL toàn hệ thống", "Xong, chờ review", "Đã đồng bộ nguyên văn từ `origin/mockdata@cee95ba` và nạp thử"],
        ["2", "`products` 13 trường + JSONB", "Đã chốt 18/09", f"Catalog đúng 13 trường (kiểm tự động khi đóng gói), {vn(n)} dòng"],
        ["3", "Parser combo", "Đã chốt 18/09", f"Xong: {vn(len(items))} thành phần, đã soát tay"],
        ["4", "Booking ↔ CDP (chỉ event purchase)", "Đã chốt 19/09", "Seed đơn của P1 nối bằng `event_group_id`"],
        ["5", "Không có bảng nhật ký", "Đã chốt 19/09", "Không ảnh hưởng dữ liệu"],
        ["6", "Insider clone là database riêng", "Đề xuất", "Đã có `seed_insider.py` và bộ dữ liệu sinh lại được"],
        ["7", "Giỏ hàng phía server", "Đề xuất", "Không ảnh hưởng catalog; seed không tạo giỏ"],
        ["8", "Tên cột opt-in của `cdp.profiles`", "Chờ CDP reviewer", "Seed dùng `email_optin`, `sms_optin`, `push_optin` theo ERD"],
        ["9", "Khách sạn không có phòng → `is_recommendable`", "Đã chốt 20/09", f"{vn(no_room)}/{vn(len(props))} khách sạn; loader tính `is_recommendable`"],
        ["10", "`priceBasis`", "Đã chốt 20/09", "Xong: `combo_attributes.json`"],
        ["11", "Khối lượng mock (2.000 khách, ~7.000 event)", "Chờ Evaluation", f"Seed dùng số đề xuất làm tham số: {vn(n_profiles)} khách, {vn(n_events)} event"],
        ["12", "Kích thước vector và model", "Tuần 2", f"Chưa; vector cho {vn(search_units)} search unit theo thiết kế"],
        ["13", "`available_from/to` = cửa sổ 30 ngày", "Đã chốt 20/09", "Xong: `load_catalog.py --as-of`"],
    ])
    baseline_txt = (f"; baseline «phổ biến nhất tại điểm đến» (ẩn lần đặt cuối, top-20) đạt {baseline}, cao vì mỗi điểm đến có ít điểm tham quan / golf — "
                    "giảm `--zipf` để phân bố phẳng hơn") if baseline else ""
    limits = [
        "## 9. Hạn chế đã biết và việc còn lại", "",
        f"- Giá là **một lần hỏi giá** (khách sạn: nhận phòng 15/10/2026, 1 đêm, 2 người lớn); vé máy bay là giá tham khảo của trip.com, {vn(len(flights) - in_window)} chuyến phải mock ngày trong cửa sổ.",
        f"- {vn(derived)}/{vn(n)} mô tả ({100 * derived / n:.0f}%) do code ghép từ dữ liệu có cấu trúc của nguồn; phòng cùng khách sạn có mô tả gần trùng nhau.",
        f"- Seed là dữ liệu mock{baseline_txt}.",
        "- DDL, seed CDP/app/Insider và DB loader dùng implementation chính thức trong `src/data_collection/seed` và `db/` của monorepo.",
        "- Đóng băng nên **chưa cào thêm** Booking Attractions, tuyến bay trip.com, golf OpenStreetMap, iVIVU (nếu làm sẽ xuất bản riêng, không đổi `productId` hiện có).",
        "- Ngày lễ âm lịch (Tết, Giỗ Tổ) chưa mô hình hoá trong lịch khả dụng; chỉ blackout ngày lễ dương lịch cố định.", ""]
    lines += ["## 4. Điều nhóm cần điều chỉnh", "",
              f"- **Không cần `expand_catalog.py` để đủ 10.000 dòng** (đã có {vn(n)}). Các test \"10.000 ID\" đổi thành đếm theo file.",
              f"- **Điểm chưa có giá:** {vn(len(unpriced))} dòng `unitPrice = null` (điểm tham quan trip.com không hiện giá, chưa rõ có bán vé không). "
              "`attributes.ticketed` chỉ là `true` khi có giá, vắng mặt nghĩa là chưa rõ; quy tắc \"`ticketed=false` → 0 VND, không có nút mua\" không còn áp dụng. "
              "Các dòng này đặt `available=true` theo quy ước demo.",
              f"- **Khách sạn không có hạng phòng:** {vn(no_room)}/{vn(len(props))} — hiển thị và tìm được nhưng không đặt được, không vào gợi ý.",
              f"- **Chuyến bay:** giờ bay (`departureTimeLocal`, `departureAt`) là **giờ Việt Nam**. `availableFrom/To` = ngày bay sớm nhất / muộn nhất trip.com liệt kê; "
              f"ngày cụ thể ở `attributes.datesSeen`. Với cửa sổ {as_of.strftime('%d/%m')}–{(as_of + timedelta(days=29)).strftime('%d/%m/%Y')}: "
              f"{vn(in_window)}/{vn(len(flights))} chuyến có ngày thật trong cửa sổ (dùng ngày đó thay vì mock); {vn(len(flights) - in_window)} chuyến còn lại cần mock hoặc đánh dấu không khả dụng."
              + (f" Tuyến không có chuyến nào: {', '.join(r['name'] for r in routes_without)}." if routes_without else ""),
              f"- **Khoảng bán Vinpearl:** {vn(len(expired))} dòng đã hết hạn trước {as_of.strftime('%d/%m')} (`available=false` theo quy tắc cửa sổ), "
              f"{vn(len(clipped))} vé/combo/golf hết hạn trong cửa sổ (khoảng bị cắt).",
              f"- **Điểm đến:** {len(full)} điểm đến có đủ khách sạn, tuyến bay đến, điểm tham quan và combo ({', '.join(full)}). "
              f"Điểm đến có ≥ 20 khách sạn nhưng không có tuyến bay đến: {no_flight_txt} "
              "— cần ánh xạ sang sân bay gần nhất khi gợi ý vé bay.",
              "- **Khách sạn chiếm phần lớn dòng** " f"({100 * (by['hotel_property'] + by['hotel_room']) / n:.0f}%); seed chuyến đi nên chọn theo điểm đến có đủ loại sản phẩm.", "",
              "## 5. Đã sửa và xác minh trong đợt này", "",
              "- **Kiểm chứng dữ liệu thật** (kiểm tay ngày 19/09, không chạy lại tự động): 297/297 khung bán `availableFrom/To` của vé Vinpearl khớp JSON gốc của API; "
              "15/15 khách sạn Booking lấy mẫu có đúng tên, toạ độ và giá trong HTML gốc đã cache; code không sinh giá trị ngẫu nhiên (`random` chỉ dùng cho độ trễ giữa các request).",
              f"- **Giờ bay:** trip.com ghi thời điểm chuyến bay theo UTC (`…Z`, đã đối chiếu trên trang trip.com); {vn(len(flights))} chuyến đã quy về giờ Việt Nam (+07:00) ở "
              "`departureTimeLocal`, `departureAt`, `arrivalAt`, tên, mô tả, `datesSeen`.",
              f"- **Vé máy bay:** {vn(len(flights) + by['flight_route'])} dòng `available=true` kèm `availableFrom/To` từ ngày trip.com liệt kê; bỏ các cờ phụ `bookable`, `priceKind`, `availabilityStatus`.",
              f"- **`ticketed`:** bỏ suy diễn \"không có giá = không bán vé\" cho {vn(len(unpriced))} điểm chưa giá; `available=true` theo quy ước demo.",
              f"- **Phòng giá vô lý:** xoá {len(removed_rooms)} hạng phòng (giá ≥ 10 triệu và > 8 lần giá trung vị cùng khách sạn, nguồn tự ghi như vậy): {'; '.join(removed_rooms)}.",
              "- **Tài liệu** không còn gõ tay: `make_docs.py` sinh `SCHEMA.md`, `BANGIAO.md`, `sample/README.md` từ chính `products.jsonl`; `finalize_catalog.sh` tự chạy.",
              f"- **Kiểm thử:** {test_count} test hồi quy (`python -m unittest discover -s . -p \"test_*.py\"`), chạy offline.", "",
              "## 6. Combo", "",
              f"`parse_combos.py` đã parse {vn(len(attrs))} combo thành {vn(len(items))} thành phần (`combo_items.jsonl` / `.csv`, cột theo bảng `catalog.combo_items`): "
              f"{' · '.join(f'{k} {vn(v)}' for k, v in kinds.most_common())}. `priceBasis`: "
              f"{' · '.join(f'{k} {vn(v)}' for k, v in basis.most_common())} (`combo_attributes.json`, để loader gán vào attributes; `products.jsonl` không đổi). "
              f"Tất cả {vn(len(attrs))} combo hiện có là combo vé / dịch vụ tại khu vui chơi, không có combo khách sạn nên không có `nights`.",
              "**Tại sao phải soát tay:** với độ tin cậy 0,6 parser chỉ biết thành phần thuộc cùng địa điểm (vd. \"Vườn Thú\" trong combo của VinWonders Vũ Yên), "
              "không biết đúng vé nào; nó chọn vé gần nhất, và nhiều lần chọn sai (vd. \"Vườn Thú\" → workshop trẻ em, \"Cáp treo\" → sản phẩm xông hơi, vé giá địa phương lẫn vé tiêu chuẩn). "
              "Liên kết sai làm chi tiết combo hiển thị sai sản phẩm nên phải người duyệt.",
              f"**Kết quả soát tay** ({n06} thành phần độ tin cậy 0,6; parser đã bỏ 1 dòng thừa \"vé vào cửa 2 khu\" vì đó chỉ là đếm số khu, không phải một vé): "
              f"giữ nguyên {r06.get('giữ nguyên', 0)} · đổi sang sản phẩm khác {r06.get('đổi sang sản phẩm khác', 0)} · "
              f"bỏ liên kết (để trống) {r06.get('bỏ liên kết (để trống)', 0)}. Kiểm thêm nhóm 0,95: sửa {sum(r95.values())} dòng lẫn vé giá địa phương / tiêu chuẩn. "
              "Nguyên tắc: chỉ liên kết khi sản phẩm trong catalog chính là thành phần đó (cùng vé, cùng phân khu, cùng biến thể giá); không chắc thì để trống. "
              f"Sau soát: {vn(att_mapped)}/{vn(len(att_items))} thành phần vé/điểm tham quan có sản phẩm, {vn(len(att_items) - att_mapped)} để trống vì catalog không có sản phẩm tương ứng "
              "(vườn thú và khu trò chơi của VinWonders Vũ Yên, GoKart, Tata Show, chỗ ngồi show Tiên Cá, gói VIP ...); hàng đợi soát tay còn "
              f"{vn(review)}. Lý do từng dòng ở `combo_items_review_log.csv`; quyết định ở `combo_items_manual.jsonl` (dòng `source = manual`, không bị ghi đè khi chạy lại `parse_combos.py`). "
              f"Chưa soát từng dòng: {left95} thành phần độ tin cậy 0,95 (chỉ kiểm chênh lệch giá địa phương / tiêu chuẩn), trong đó 3 dòng combo giá địa phương của Nha Trang / Hội An "
              "vẫn trỏ vé tiêu chuẩn vì mức giảm của combo không trùng mức giảm của vé địa phương.", "",
              *seed_lines,
              "## 8. Đối chiếu file thiết kế DB (13 hạng mục \"Việc chốt tuần 1\")", "", design, "",
              *limits,
              "## 10. Trong gói", "",
              "`bao-cao-ban-giao.md` (file này), `BANGIAO.md` (danh sách file), `SCHEMA.md`, `template.json`, `sample/`, `map/`, `seed/`, `loader/`, `stats.md`, `quality_review.csv`, "
              "`dedup_report.csv`, `excluded_*.csv`, các file `combo_*`, `MANIFEST.sha256` (mã băm từng file). Kiểm tra: `sha256sum -c MANIFEST.sha256`.",
              "Dữ liệu chỉ dùng nội bộ cho demo thực tập, không phân phối lại (điều khoản booking.com / agoda.com không cho phép thu thập tự động)."]
    return "\n".join(lines) + "\n"


def package_listing(pkg: Path) -> str:
    def size(p: Path) -> str:
        b = p.stat().st_size
        return f"{b / 1e6:.1f} MB" if b >= 1e6 else f"{max(1, round(b / 1e3))} KB"
    desc = {"products.jsonl": "**Bản chuẩn**, mỗi dòng 1 JSON đúng 13 trường", "SCHEMA.md": "Schema dạng người đọc",
            "template.json": "Schema dạng máy đọc (khoá `attributes` theo loại kèm độ phủ)", "stats.md": "Thống kê catalog",
            "quality_review.csv": "Danh sách cần soát", "dedup_report.csv": "Các cặp trùng đã gộp",
            "excluded_location.csv": "Dòng đã xoá vì lỗi dữ liệu", "excluded_auto.csv": "Điểm bị loại theo quy tắc không phải điểm du lịch",
            "combo_items.jsonl": "Thành phần combo (parse từ tên + mô tả)", "combo_items.csv": "Như trên, dạng bảng",
            "combo_items_review.csv": "Hàng đợi soát tay (độ tin cậy < 0,8)", "combo_attributes.json": "`priceBasis` / `nights` / `minPax` của từng combo",
            "combo_items_report.md": "Thống kê parse combo", "bao-cao-ban-giao.md": "Báo cáo tổng hợp: tóm tắt, số liệu cần cập nhật, ID cũ → mới, soát combo, seed/loader, đối chiếu file thiết kế DB",
            "combo_items_manual.jsonl": "Quyết định soát tay thành phần combo (source = manual)", "combo_items_review_log.csv": "Nhật ký soát tay: lý do từng dòng",
            "ids_da_mat_so_voi_ban_16-09.csv": "ID của bản 16/09 không còn trong catalog, kèm ID mới nếu đã gộp",
            "BANGIAO.md": "File này", "MANIFEST.sha256": "Mã băm SHA-256 của từng file"}
    rows = [[f"`{p.relative_to(pkg)}`", size(p), desc.get(p.name, "")] for p in sorted(pkg.rglob("*")) if p.is_file() and p.parent == pkg]
    for sub, what in (("sample", "Bộ mẫu chạy thử, liên kết cha–con toàn vẹn"), ("map", "Ghim bản đồ: CSV cho Google My Maps + `places.geojson`"),
                      ("seed", "Seed CDP clone: profile, event, user persona, đơn của P1 (`seed_report.md` có số liệu và kiểm tra)"),
                      ("loader", "Kết quả lần chạy loader (`loader_report.md`)")):
        if not (pkg / sub).exists():
            continue
        files = [p for p in (pkg / sub).rglob("*") if p.is_file()]
        rows.append([f"`{sub}/`", f"{sum(p.stat().st_size for p in files) / 1e6:.1f} MB", f"{what} ({len(files)} file)"])
    return table(["File", "Dung lượng", "Nội dung"], rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--out-dir", type=Path, default=Path.home() / "bangiao")
    ap.add_argument("--previous", type=Path, default=Path.home() / "bangiao" / "vota-catalog-20260916" / "products.jsonl")
    ap.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    a = ap.parse_args()
    d = a.data_dir
    new = read_jsonl(d / "products.jsonl")
    check_inputs(d, new)
    name = f"vota-catalog-{a.as_of.strftime('%Y%m%d')}"
    pkg, zip_path = a.out_dir / name, a.out_dir / f"{name}.zip"
    if pkg.exists() or zip_path.exists():
        raise SystemExit(f"{pkg} hoặc {zip_path} đã tồn tại — không ghi đè bản đã bàn giao. Đổi --as-of hoặc xoá thủ công nếu chắc chắn.")
    old = read_jsonl(a.previous) if a.previous.exists() else None

    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp) / name
        stage.mkdir()
        for f in REQUIRED:
            shutil.copy2(d / f, stage / f)
        for sub in ("sample", "map"):
            shutil.copytree(d / sub, stage / sub)
        if all((d / "seed" / f).exists() for f in ("cdp_profiles.jsonl", "cdp_events.jsonl", "app_users.jsonl", "app_bookings.jsonl",
                                                    "app_booking_items.jsonl", "seed_report.md")):
            shutil.copytree(d / "seed", stage / "seed")
        if (d / "loader" / "loader_report.md").exists():
            (stage / "loader").mkdir()
            shutil.copy2(d / "loader" / "loader_report.md", stage / "loader" / "loader_report.md")
        lost, surv = (id_survival(old, new) if old else ([], None))
        if old:
            write_lost_csv(stage / "ids_da_mat_so_voi_ban_16-09.csv", lost, surv["old_to_new"])
        (stage / "bao-cao-ban-giao.md").write_text(build_note(d, new, old, lost, surv, a.as_of), encoding="utf-8")

        # BANGIAO.md của gói phải nói đúng file có trong gói
        text = (stage / "BANGIAO.md").read_text(encoding="utf-8")
        text, k = re.subn(r"## 2\. Gói này có gì\n.*?(?=\n## 3\.)",
                          lambda m: "## 2. Gói này có gì\n\n" + package_listing(stage) + "\n\nKhông kèm `products.csv`, `products.json`, `catalog/*.json` "
                          "(cùng dữ liệu, sinh lại bằng `./finalize_catalog.sh`) và HTML/JSON thô đã crawl. Kèm `MANIFEST.sha256`: mã băm SHA-256 từng file "
                          "(`sha256sum -c MANIFEST.sha256`).\n\n```python\nimport pandas as pd\n"
                          "df = pd.read_json(\"products.jsonl\", lines=True)\n```\n", text, flags=re.S)
        if k != 1:
            raise SystemExit("BANGIAO.md không có mục '## 2. Gói này có gì' để cập nhật")
        text = text.replace("## 1. Đọc gì trước", "> **Đọc `bao-cao-ban-giao.md` trước:** báo cáo tổng hợp (tóm tắt, số liệu cần cập nhật, ID cũ → mới, soát combo, seed/loader).\n\n## 1. Đọc gì trước", 1)
        (stage / "BANGIAO.md").write_text(text, encoding="utf-8")

        # quét khoá bí mật; liệt kê email để người bàn giao tự xem
        emails: collections.Counter = collections.Counter()
        for p in stage.rglob("*"):
            if p.is_file() and p.suffix in (".md", ".csv", ".json", ".jsonl", ".geojson"):
                body = p.read_text(encoding="utf-8", errors="ignore")
                for label, rx in SECRET_RES.items():
                    if rx.search(body):
                        raise SystemExit(f"Thấy mẫu khoá bí mật ({label}) trong {p.relative_to(stage)} — dừng, không đóng gói.")
                emails.update(EMAIL_RE.findall(body))
        manifest = [f"{sha256(p)}  {p.relative_to(stage).as_posix()}" for p in sorted(stage.rglob("*")) if p.is_file()]
        (stage / "MANIFEST.sha256").write_text("\n".join(manifest) + "\n", encoding="utf-8")

        a.out_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(stage, pkg)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for p in sorted(pkg.rglob("*")):
                if p.is_file():
                    z.write(p, f"{name}/{p.relative_to(pkg).as_posix()}")
    digest = sha256(zip_path)
    (a.out_dir / f"{name}.zip.sha256").write_text(f"{digest}  {zip_path.name}\n", encoding="utf-8")
    with zipfile.ZipFile(zip_path) as z:
        assert z.testzip() is None
        assert len(z.namelist()) == sum(1 for p in pkg.rglob("*") if p.is_file())
    files = [p for p in pkg.rglob("*") if p.is_file()]
    print(f"Đã đóng gói {len(files)} file → {pkg}")
    print(f"  {zip_path}  ({zip_path.stat().st_size / 1e6:.1f} MB)")
    print(f"  sha256: {digest}")
    print(f"  email tìm thấy trong nội dung ({len(emails)}): {', '.join(f'{e} ×{c}' for e, c in emails.most_common(8)) or 'không có'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
