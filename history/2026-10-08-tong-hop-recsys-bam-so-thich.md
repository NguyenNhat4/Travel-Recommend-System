# Báo cáo tổng hợp điều tra RecSys bám sở thích (để review)

- Ngày: 2026-10-08
- Tác giả: Pham Nguyen Dang Khoi / Claude Code
- Nhánh: bench_search_recomSys
- Trạng thái: dang dở
- Phạm vi: docs, evaluation
- Bị thay thế bởi: `history/2026-10-08-bao-cao-cuoi-va-ban-giao-recsys-so-thich.md`

## Mục tiêu

Gộp mọi phát hiện và số đo 07–08/10 vào một tài liệu để agent khác review. FR-REC-01, FR-REC-02, FR-REC-04.

## File thay đổi

- `docs/spec/bench/recsys-bam-so-thich-tong-hop.md` — thêm: tổng hợp (xuất phát, cách đo, phát hiện A–D, kết quả, phương án, việc sau, caveat)

## Quyết định

- Đặt ở `docs/spec/bench/` (phân tích / quyết định tổng hợp, AGENTS.md §7); số thô vẫn ở report `src/evaluation/reports/`.

## Kiểm tra

- Số trong tài liệu lấy từ các file JSON / log đã ghi trong report; thêm P2 + F7 trên split thật (`profile_p2f7.json`).

## Còn lại / rủi ro

- Bước 2 (F12b, F13a/b, F14 trên P2) chưa xong khi viết.
