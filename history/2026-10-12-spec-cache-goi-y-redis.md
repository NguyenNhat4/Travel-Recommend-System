# Spec cache gợi ý Redis: K1 theo dấu vân tay event, đóng S5, cập nhật plan

- Ngày: 2026-10-12
- Tác giả: tqanh123 / Claude Code
- Nhánh: fix/recommendation
- Trạng thái: hoàn thành
- Phạm vi: docs
- Liên quan: `docs/prd/update-archive/2026-10-12-cache-goi-y-tren-redis.md` (đã chốt, đã áp dụng vào PRD), `docs/plan/2026-10-12-goi-y-trang-chu-cache-redis-va-ke-pho-bien.md`, `history/2026-10-12-recsys-cache-goi-y-loi.md`, `history/2026-10-12-recsys-cache-goi-y-redis.md`, `history/2026-10-12-lam-am-cache-goi-y-sau-dang-nhap.md`

## Mục tiêu

Đưa spec về khớp với cache đã cài: cache **kết quả** gợi ý trên Redis, khoá theo dấu vân tay event. Bản `[P3]` cũ là cache user vector có bước xoá cache đồng bộ khi ghi `purchase`. Đóng phụ thuộc S5 và cập nhật trạng thái plan.

Phục vụ NFR-PERF-01; giữ nguyên FR-REC-02, AC-REC-02 (K1).

## File thay đổi

- `docs/spec/hop-dong-tich-hop-search-recommendation.md` — sửa:
  - §1.2: trách nhiệm Backend là cache theo dấu vân tay event, thay cho "vô hiệu hoá cache đồng bộ";
  - §5 (K1): luồng mới và quy tắc cache (khoá, mọi request vẫn đọc CDP, TTL, 64 KB, Redis lỗi, CDP lỗi, chống tính trùng, làm ấm sau đăng nhập);
  - §7.1: nhãn hai dòng hit/miss; đoạn giải thích khi nào trượt cache và đo ở đâu;
  - tiêu chí 26: cách đo;
  - §10 S5: đã chốt, cùng đoạn kết luận.
- `docs/spec/hop-dong-tich-hop-backend.md` — sửa:
  - thêm §6.6 "Cache kết quả gợi ý": phạm vi, nơi lưu, response không đổi, Redis lỗi, làm ấm, tắt bằng biến môi trường;
  - §7.4 mục 5: cache không cản K1;
  - §8.5: ngân sách `/recommendations` tách hit/miss.
- `docs/spec/hop-dong-tich-hop-cdp.md` — sửa: §6 mục 5. Cache kết quả không cache lịch sử, nên K1 đúng mà không cần xoá cache.
- `docs/spec/hop-dong-tich-hop-auth.md` — sửa: §16.1 bảng khoá Redis thêm `rec:v1:{hash}`, `rec:v1:lock:{hash}`.
- `docs/guide/recommendation-system-ste100.md` — sửa:
  - §7: luồng K1 có cache;
  - §11: dòng "User vector cache" và "Event limit" đã đóng ngày 2026-10-12.
- `docs/plan/2026-10-12-goi-y-trang-chu-cache-redis-va-ke-pho-bien.md` — sửa:
  - trạng thái: hoàn thành phần code, test và tài liệu;
  - mô tả nối dây đúng với code (cache trong engine, không bọc `recommend`);
  - thêm mục "Còn lại": bench chưa chạy, đo sau deploy, secret, hai điểm khác đề xuất.
- `history/2026-10-12-spec-cache-goi-y-redis.md` — thêm: entry này.

## Quyết định

- **Không đổi con số ngân sách** (300 ms trúng, 800 ms trượt). Chỉ ghi rõ mỗi đường làm gì, và nói thẳng rằng đường trượt chưa đạt trên VM hiện tại, vì ANN vẫn qua Weaviate Cloud khác vùng. Đổi ngân sách là việc của PRD (NFR-PERF-01), không làm ở đây.
- **Ghi "chưa có số đo thật".** Môi trường bench prodcopy không còn. Số lấy từ log `recsys.recommend` sau lần deploy đầu.
- **`compose.ha.yml` không đổi** (biến đọc từ `env_file`). Plan ghi lại điểm này cùng điểm "cache nằm trong engine" như hai chỗ hiện thực khác phần "thay đổi source" của đề xuất.

## Kiểm tra

- `grep -rn "Vô hiệu hóa cache user vector" docs/spec` (cả chữ thường): không còn kết quả.
- `grep -rn "\[P3\]" docs/spec`: chỉ còn 2 dòng, là câu nhắc bản cũ ở §5 và dòng S5 đã gạch.
- Tài liệu, không có code đổi; không chạy test.

## Còn lại / rủi ro

- Đo tỷ lệ trúng, `stage_ms` và p95 sau deploy, rồi ghi report vào `src/evaluation/reports/`.
