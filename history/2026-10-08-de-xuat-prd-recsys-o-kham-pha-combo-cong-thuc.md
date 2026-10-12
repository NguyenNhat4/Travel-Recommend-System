# Ba đề xuất PRD RecSys: loại sản phẩm đã mua + combo, ô khám phá, chuẩn hoá sở thích giữa hai chuyến

- Ngày: 2026-10-08
- Tác giả: tqanh123 / Claude Code
- Nhánh: feat/recSys_update
- Trạng thái: dang dở — chờ người dùng chốt (G5a cho [A], [C]; [B] chờ G6 + G2)
- Phạm vi: docs
- Tiếp theo: `history/2026-10-08-wp0-6-nhanh-dich-va-lo-trinh-giai-doan.md`

## Mục tiêu

Tách đề xuất PRD đang chờ (`2026-10-08-recsys-bam-so-thich-va-o-kham-pha.md`, nội dung cũ: chỉ F7 + ô B) thành ba đề xuất
độc lập để phần miễn phí không bị chặn bởi quyết định công thức (AGENTS.md §8), và đưa yêu cầu mới của người dùng (loại
combo hai chiều) vào PRD. FR-REC-02, FR-REC-04, AC-REC-02/03.

## File thay đổi

- `docs/prd/update/2026-10-08-recsys-bam-so-thich-va-o-kham-pha.md` → đổi tên (`git mv`) thành
  `docs/prd/update/2026-10-08-recsys-o-kham-pha-khi-co-chuyen-mo.md` — viết lại: **[A]** ô khám phá B (chỉ lấp ô trống, 1
  món / điểm đến, whitelist hotel/attraction/combo, loại món đã mua kể cả combo liên quan, nối sau món X; cần 1 lượt
  `near_vector` → điều kiện latency; công tắc tắt); số từ lượt đo `--how ulong`; ghi P2 là chi tiết triển khai.
- `docs/prd/update/2026-10-08-recsys-loai-san-pham-da-mua-va-combo.md` — thêm: **[C]** không gợi lại sản phẩm đã mua
  (theo search unit, mọi lần mua); combo ↔ thành phần cùng lần mua hai chiều, một bậc; ngưỡng dòng `combo_items` tin cậy;
  AC-REC-03 mới; sửa câu AC-REC-02 (bỏ "Hội An" — không thể đạt theo thiết kế).
- `docs/prd/update/2026-10-08-recsys-chuan-hoa-so-thich-giua-hai-chuyen.md` — thêm: **[B]** F14c + destCap2 khi không có
  chuyến mở; tiêu chí G1; ghi rõ **chưa trình chốt** tới khi có số G6.
- `history/2026-10-08-de-xuat-prd-recsys-o-kham-pha-combo-cong-thuc.md` — thêm: entry này.

Không sửa `docs/prd/` (chỉ sửa sau khi chốt, AGENTS.md §8.3). Không sửa `src/backend`.

## Quyết định

- Ba file thay vì một: trạng thái `chờ chốt` của công thức không được chặn ô B và loại combo.
- [C] đề nghị: xét theo search unit; mọi lần mua; dòng mapping tin cậy `confidence ≥ 0,8 OR source = 'manual'` (90 / 163
  dòng 0,60 là khớp theo địa điểm); một bậc; "combo kéo theo hotel" (spec §4.5, chưa cài) ngoài phạm vi; cold start giữ
  nguyên. Người dùng chốt từng mục.
- [A] theo đúng bản đã đo: whitelist taxonomy, **không** loại taxonomy đã mua trong chuyến (khách sạn ở điểm đến khác là gợi ý
  cho chuyến sau).
- [B] giữ tham số đã đo (q = 0,8529 / 0,9387; 0,50 / 0,35 / 0,15; cap 2) và luật đóng G2 đề nghị D1–D5.

## Kiểm tra

- Mỗi đề xuất theo mẫu AGENTS.md §8 (header, Lý do, Nội dung đề xuất dạng "hiện tại → thay bằng", Thay đổi source sau khi
  chốt). Trích PRD lấy từ `docs/prd/requirements.md` sau merge `origin/release-mvp-v2` (FR-REC-02 dòng 46, FR-REC-04 dòng
  48, AC-REC-02 dòng 158).
- Số trong [A] khớp `src/evaluation/recsys_bench/theme_study/results/2026-10-08-g2-wp4/wp4_slots_p2_f14c_ulong.json`; số trong
  [B] khớp `ci_full_vs_prod.json` / `ci_destcap_splits.json`; số trong [C] từ truy vấn read-only trên `vota_prodcopy` 08/10.

## Còn lại / rủi ro

- Chờ G5a: sau khi chốt [A], [C] → sửa `docs/prd/requirements.md` trước, rồi PR-A (plan
  `docs/plan/2026-10-08-recsys-trien-khai-theo-giai-doan.md`), `git mv` hai đề xuất sang `update-archive/`.
- [B] chỉ trình sau report G6; nếu G2 bị từ chối thì chuyển [B] sang `update-archive/` với trạng thái `từ chối`.
- Ô B: chi phí 1 lượt `near_vector` trên Weaviate Cloud chưa đo được từ local — nếu vỡ ngưỡng thì tắt bằng công tắc.
