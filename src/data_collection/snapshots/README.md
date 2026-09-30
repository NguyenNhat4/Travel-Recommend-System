# Catalog snapshots

Mỗi thư mục ngày là đầu vào có version cho local demo. Snapshot được commit ở dạng `products.jsonl.gz`; file JSONL đã bung và mọi output loader/seed tiếp tục nằm dưới `src/data_collection/data/` và bị Git ignore.

`manifest.json` cố định số dòng cùng SHA-256 của file nén, catalog gốc và mapping combo. Seed kiểm tra toàn bộ trước khi sinh artifact hoặc ghi database. Không sửa file trong snapshot bằng tay; tạo phiên bản ngày mới khi catalog thay đổi.

Snapshot mặc định `2026-09-30` (`make demo-db`, `seed/config.py`) chứa:

- 11.718 sản phẩm theo đúng 13 trường catalog/`cdp.products` chính thức: snapshot `2026-09-23` cộng vé máy bay trip.com
  cào lại ngày 30/09/2026 (29 tuyến trong phạm vi `@deep`: 110 dòng tuyến / vé một chiều làm mới, 331 vé mới gồm 290 vé
  khứ hồi). `productId` sinh cố định theo `sourceRef` nên dòng làm mới giữ nguyên ID.
- Hạng vé: 268/290 vé khứ hồi có `cabinClass: ECONOMY`, đọc từ thẻ khứ hồi trên trang tuyến trip.com ("Economy class").
  22 vé khứ hồi (thẻ trống hạng / lẫn hạng) và mọi vé một chiều: chưa biết hạng. Snapshot không có hạng thương gia; seed
  sinh thêm 797 vé Thương gia mô phỏng "(giá minh hoạ)" khi nạp (`docs/spec/MOCK_DATA_SPEC.md` §2 bước 1, mục 5).
- 64 dòng mapping combo đã duyệt tay (giống `2026-09-23`).
- Không chứa profile, event, booking, secret hoặc Docker volume; các dữ liệu demo đó được seed tất định khi chạy.

Vé khứ hồi mang `attributes.priceValidUntil = 2026-10-01` (hạn báo giá của trip.com, không phải ngày bay). Seed ngày nào cũng
có đủ 290 vé khứ hồi đặt được: vé có ngày đi ngoài cửa sổ được dời vào cửa sổ cả hai chặng (`docs/spec/MOCK_DATA_SPEC.md` §2
bước 1), giá giữ nguyên nên chỉ là giá tham khảo. Từ 02/10/2026 `fareClasses` của các vé này trả `availabilityStatus: EXPIRED`.
Giá mới đến từ job cào trên VM, không từ snapshot.

Snapshot `2026-09-29` (11.708, vé khứ hồi chưa có hạng) giữ lại để tái lập.
Snapshot `2026-09-23` (11.387 sản phẩm) giữ lại để tái lập (bộ đánh giá search dùng nó); `2026-09-21` giữ để tái lập các
phép đo seed cũ.
