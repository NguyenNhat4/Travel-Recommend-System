# Không gợi lại sản phẩm đã mua; combo và sản phẩm thành phần được coi là cùng một lần mua

- Ngày: 2026-10-08
- Người đề xuất: tqanh123 / Claude Code soạn
- Trạng thái: đã áp dụng
- Chốt bởi / ngày: tqanh123, 2026-10-09 (G5a — "chốt cả [A] và [C] như đề nghị"); PRD cập nhật 2026-10-09
- PRD bị ảnh hưởng: `docs/prd/requirements.md` §1.3 FR-REC-02; §3 AC-REC-02 (sửa câu), AC-REC-03 (mới)
- Mã FR/NFR: FR-REC-02

## Lý do

1. **PRD chưa có luật "không gợi lại sản phẩm đã mua".** FR-REC-02 chỉ nói loại *loại sản phẩm* (taxonomy) đã mua trong
   chuyến đang mở. Việc loại chính *sản phẩm* đã mua hiện chỉ nằm ở spec
   (`docs/spec/hop-dong-tich-hop-search-recommendation.md` §4.5: "Ngoài ra loại mọi `productId` khách đã từng mua") và engine
   đã làm (`use_cases.py`, `bought_units`). Theo AGENTS.md §8 đây là hành vi PRD chưa ghi → ghi vào PRD.
2. **Combo chưa được xử lý.** Khách mua phòng H rồi vẫn thấy combo "vé bay + phòng H"; khách mua combo "VinWonders + Teddy
   Bear" rồi vẫn thấy vé Teddy Bear riêng. Engine chỉ loại đúng unit đã mua; `catalog.combo_items` (thành phần combo) không
   được đọc vào `UnitIndex`. Yêu cầu người dùng 08/10: mua sản phẩm → không gợi combo chứa nó; mua combo → không gợi sản
   phẩm thành phần.
3. **Dữ liệu bản sao production 08/10:** 183 combo / 442 dòng `combo_items`, 163 dòng có `item_product_id` (35 sản phẩm:
   153 attraction, 8 phòng, 2 khách sạn); 1.008 / 14.145 lượt mua là combo (930 khách). Nếu áp luật: 586 khách đã mua combo
   không còn thấy 788 (khách, thành phần); 232 khách đã mua thành phần không còn thấy 797 (khách, combo). Chỉ **1** khách
   từng mua cả thành phần lẫn combo chứa nó → chỉ số offline (LLBO / temporal / nexttrip) gần như không đổi; đúng / sai phải
   kiểm bằng unit test và kịch bản tổng hợp, không bằng bench.
4. **AC-REC-02 hiện có phần không thể đạt:** "tour tham quan tại Bà Nà / Hội An". Hội An là một điểm đến riêng trong catalog
   (123 khách sạn, 27 tham quan); khi chuyến Đà Nẵng đang mở, engine khoá điểm đến X = Đà Nẵng (FR-REC-02) nên không bao giờ
   gợi Hội An; ô khám phá (đề xuất `2026-10-08-recsys-o-kham-pha-khi-co-chuyen-mo.md`) cũng không giúp vì Đà Nẵng đủ 4 ô
   (12 chuyến bay, 7 tham quan — Núi Bà Nà, Sun World Bà Nà Hills, Cáp treo Bà Nà đều gợi ý được). Sửa câu AC cho đúng
   thiết kế; luật "điểm đến lân cận" là hành vi mới, không đề xuất ở đây.

## Nội dung đề xuất

### `docs/prd/requirements.md` §1.3 — FR-REC-02

Hiện tại (câu cuối của mục):

> **Sau khi chuyến đã diễn ra xong**, hệ thống gợi ý cho chuyến kế tiếp: không loại loại sản phẩm đã mua, không khoá điểm đến X; dùng lịch sử dài hạn và mức phổ biến. *(Chốt 2026-10-01, đề xuất `update-archive/2026-10-01-category-exclusion-theo-chuyen-dang-dien-ra.md`; N là tham số engine.)*

Thêm ngay sau câu trên:

> **Trong mọi trường hợp**, hệ thống không gợi ý lại sản phẩm khách đã mua, xét theo đơn vị tìm kiếm (mua một hạng phòng là
> đã mua khách sạn đó; mua một chuyến bay là đã mua tuyến đó) và trên toàn bộ lịch sử mua. **Combo và các sản phẩm thành phần
> của nó** (`catalog.combo_items`) được coi là cùng một lần mua theo cả hai chiều: đã mua một sản phẩm thì không gợi ý combo
> chứa sản phẩm đó; đã mua một combo thì không gợi ý các sản phẩm thành phần của combo đó. Quan hệ chỉ xét một bậc (mua combo
> A không loại combo B chỉ vì B chung một thành phần với A).

### `docs/prd/requirements.md` §3 — AC-REC-02

Hiện tại:

> | **AC-REC-02** | Người dùng hoàn tất đặt phòng tại Đà Nẵng | Tại trang xác nhận và khi quay lại trang chủ, khối gợi ý ưu tiên hiển thị vé máy bay đến Đà Nẵng và tour tham quan tại Bà Nà / Hội An. |

Thay bằng:

> | **AC-REC-02** | Người dùng hoàn tất đặt phòng tại Đà Nẵng | Tại trang xác nhận và khi quay lại trang chủ, khối gợi ý ưu tiên hiển thị vé máy bay đến Đà Nẵng và hoạt động trải nghiệm tại Đà Nẵng (ví dụ Bà Nà); không có khách sạn (đã mua) và không có combo chứa phòng vừa đặt. |

### `docs/prd/requirements.md` §3 — AC-REC-03 (mới, thêm sau AC-REC-02)

> | **AC-REC-03** | Người dùng đã mua combo gồm vé VinWonders và vé Bảo tàng Gấu Teddy (hoặc đã mua một trong hai vé lẻ) | Khối gợi ý không hiển thị lại combo đó, không hiển thị hai vé thành phần (trường hợp mua combo), và không hiển thị combo chứa vé đã mua (trường hợp mua vé lẻ); các sản phẩm khác cùng điểm đến vẫn được gợi ý. |

### Quyết định cần chốt cùng đề xuất

| Câu hỏi | Đề nghị |
|---|---|
| Đơn vị so khớp | Theo **search unit** (phòng → khách sạn, chuyến bay → tuyến), nhất quán với luật `bought_units` hiện có |
| Phạm vi thời gian | **Mọi lần mua** trong lịch sử (như `bought_units`), không chỉ chuyến đang mở |
| Dòng `combo_items` được tin | `item_product_id IS NOT NULL AND (confidence ≥ 0,8 OR source = 'manual')` — 90 / 163 dòng có `confidence = 0,60` là khớp theo địa điểm (ví dụ "cáp treo" khớp mọi cáp treo cùng nơi), không đủ tin để loại một sản phẩm khỏi gợi ý |
| Bắc cầu | **Một bậc** (không lan sang combo khác chung thành phần) |
| Luật "combo kéo theo hotel" (spec §4.5, `PRODUCT_SCHEMA.md` §5 luật 5: mua combo có khách sạn thì loại *taxonomy* hotel trong chuyến mở) | **Ngoài phạm vi** đề xuất này — đã có trong spec nhưng chưa cài; xử lý riêng |
| Cold start (`_cold_start`, khách < 3 event) | Giữ nguyên (hiện không loại gì) — ghi nhận, không đổi ở đây |

## Thay đổi source sau khi chốt

- `docs/prd/requirements.md` §1.3 FR-REC-02, §3 AC-REC-02 / AC-REC-03 (trước), rồi:
- `src/backend/app/infrastructure/vectors/postgres_store.py`: `_COMBO_QUERY` đọc thêm `item_product_id, confidence, source`
  (fingerprint catalog đổi một lần; text / textHash / vector không đổi); `CatalogUnits.combo_members`.
- `src/backend/app/application/ports/unit_index.py`: field `combo_members` (mặc định rỗng), `components_of` / `combos_with`
  resolve qua `resolve()` (phòng → khách sạn), `purchase_closure(units)` một bậc.
- `src/backend/app/application/recommendation/use_cases.py`: tập đã mua tính từ raw event qua `idx.resolve` (đóng cả khe
  "purchase không có vector thì không loại") rồi `purchase_closure` trước khi lấy ứng viên.
- Gương harness cùng commit: `src/evaluation/recsys_bench/models/funnel.py`, `ceiling.py` (lý do `combo_bought`),
  `splits._meta_for_targets` (`comboRelatedTarget`), `theme_study/theme_exp.py` + `eval_slots.py` (ô khám phá).
- Spec: `docs/spec/hop-dong-tich-hop-search-recommendation.md` §4.5 (câu luật), §9 tiêu chí mới cho Recommendation;
  `docs/spec/PRODUCT_SCHEMA.md` §5 luật 5 ghi rõ phần đã cài / chưa cài.
- Test: `src/backend/tests/unit` (closure trong `UnitIndex`; mua R1 → C1 vắng; mua C1 → H1, A1 vắng; chuyến đã xong vẫn
  loại; purchase không vector vẫn loại), `tests/architecture` không đổi; `recsys_bench/tests` cho gương harness.
- `ENGINE_RULES_VERSION` tăng (configHash bench đổi → ghi baseline gate mới theo `docs/spec/bench/recsys-offline-eval.md` §3.1).
- Contract OpenAPI không đổi.
