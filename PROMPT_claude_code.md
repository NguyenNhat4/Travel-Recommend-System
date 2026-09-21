# Prompt mở đầu cho Claude Code (dán nguyên vào phiên đầu tiên trong repo)

Đọc `CLAUDE.md` (mục Database), rồi `docs/MOCK_DATA_SPEC.md`, rồi `docs/DATABASE_SCHEMA.md` §2, §5, §8, §9 trước khi viết gì.

Nhiệm vụ: dựng database và mock data tuần 1 đúng spec.
1. Nếu còn `docker-compose.db.yml`/`CLAUDE.database.md` thì gộp vào file gốc rồi xoá. Chạy `docker compose up -d postgres`, xác nhận 15 bảng + 3 view ở `vota` và 5 bảng + view `live_events` ở `insider`.
2. Tạo package `src/data_collection/seed/` theo bố cục ở MOCK_DATA_SPEC §1, CLI `python -m data_collection.seed --as-of <hôm nay> --seed 42 --reset`.
3. Làm từng bước §2 → §6 của spec, sau mỗi bước chạy `db/verify.sql` phần liên quan, sửa tới khi PASS rồi mới sang bước sau.
4. Cuối cùng chạy toàn bộ với `--reset`, in bảng tóm tắt và ghi `data-collection/README.md` (as_of, seed, số dòng từng bảng, tỷ lệ map combo, danh sách hàng đợi soát tay).

Ràng buộc: không sửa `db/*.sql`; không thêm cột/bảng; không nạp vector; `cdp.*` chỉ ghi bởi loader/seed, code app chỉ đọc qua CdpClient. Nếu spec mâu thuẫn hoặc thiếu, dừng lại và hỏi — đừng đoán.
