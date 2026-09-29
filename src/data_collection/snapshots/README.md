# Catalog snapshots

Mỗi thư mục ngày là đầu vào có version cho local demo. Snapshot được commit ở dạng `products.jsonl.gz`; file JSONL đã bung và mọi output loader/seed tiếp tục nằm dưới `src/data_collection/data/` và bị Git ignore.

`manifest.json` cố định số dòng cùng SHA-256 của file nén, catalog gốc và mapping combo. Seed kiểm tra toàn bộ trước khi sinh artifact hoặc ghi database. Không sửa file trong snapshot bằng tay; tạo phiên bản ngày mới khi catalog thay đổi.

Snapshot mặc định `2026-09-29` (`make demo-db`, `seed/config.py`) chứa:

- 11.708 sản phẩm theo đúng 13 trường catalog/`cdp.products` chính thức: snapshot `2026-09-23` cộng vé máy bay trip.com
  cào lại ngày 29/09/2026 (29 tuyến trong phạm vi `@deep`: 110 dòng tuyến/vé một chiều làm mới, 321 vé mới gồm 290 vé
  khứ hồi). `productId` sinh cố định theo `sourceRef` nên dòng làm mới giữ nguyên ID.
- 64 dòng mapping combo đã duyệt tay (giống `2026-09-23`).
- Không chứa profile, event, booking, secret hoặc Docker volume; các dữ liệu demo đó được seed tất định khi chạy.

Vé khứ hồi mang `attributes.priceValidUntil = 2026-09-30` (hạn báo giá của trip.com, không phải ngày bay): từ 01/10/2026
`fareClasses` của các vé này trả `availabilityStatus: EXPIRED`. Giá mới đến từ job cào trên VM, không từ snapshot.

Snapshot `2026-09-23` (11.387 sản phẩm) giữ lại để tái lập (bộ đánh giá search dùng nó); `2026-09-21` giữ để tái lập các
phép đo seed cũ.
