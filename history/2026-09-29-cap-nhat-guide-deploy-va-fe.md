# Cập nhật hai guide (deploy, FE) theo snapshot 2026-09-29 và seed dời ngày vé khứ hồi

- Ngày: 2026-09-29
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người yêu cầu hỏi hai guide đã cập nhật chưa. Hai guide viết trước khi có:
- snapshot `2026-09-29` (commit `7b23c17`);
- seed dời ngày vé khứ hồi (commit `a894f76`).

## File thay đổi

- `docs/guide/hien-thi-hang-ve-may-bay.md` — sửa:
  - thêm mục "Có dữ liệu trên máy":
    - chạy `make demo-db-reset`, không cần index;
    - 290 vé khứ hồi đặt được, thuộc 29 tuyến giữa 6 thành phố;
    - vé dời ngày mang giá tham khảo; cách kiểm nhanh;
  - `limit` tối đa 20;
  - `EXPIRED` từ 01/10 trên máy dev vẫn đặt được;
  - vé cũ không có `tripType` thì coi là một chiều.
- `docs/guide/trien-khai-job-cao-du-lieu.md` — sửa:
  - thêm mục nạp catalog snapshot lên staging một lần bằng seed `--catalog-only`: tunnel, tài khoản, lệnh, kết quả mong đợi,
    `--generate-only`;
  - ghi khác biệt seed (dời ngày) và job (giữ ngày thật, khoá vé hết hạn báo giá);
  - `make demo-db*` chỉ dùng cho máy dev.
- `history/2026-09-29-cap-nhat-guide-deploy-va-fe.md` — thêm: entry này.

## Quyết định

- Không đổi quy tắc hay contract; guide chỉ dẫn lại PRD, spec và snapshot README.

## Kiểm tra

- Số liệu đối chiếu với snapshot `2026-09-29`: 290 khứ hồi, 29 tuyến; sân bay CXR, DAD, DLI, HAN, PQC, SGN; 385 + 112 vé một
  chiều / vé cũ.
- `--catalog-only` + `--generate-only` dừng trước khi ghi DB (`seed/__main__.py`).
- `inserted=321 · updated=110` lấy từ lần mô phỏng staging trên database nháp (entry
  `2026-09-29-snapshot-catalog-ve-khu-hoi.md`).

## Còn lại / rủi ro

- Chưa nạp staging (chờ tunnel và tài khoản).
- Chưa commit.
