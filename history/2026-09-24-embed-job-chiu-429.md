# Job embed chịu được Cohere 429 và giữ tiến độ

- Ngày: 2026-09-24
- Tác giả: nhatnm / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: backend

## Mục tiêu

`make index-vectors` lỗi `429 Too Many Requests` từ `https://api.cohere.com/v2/embed`. Hai nguyên nhân trong code: embedder chỉ thử 3 lần, chờ 1s rồi 2s, bỏ qua `Retry-After`; job embed toàn bộ 3178 text rồi mới ghi, nên một lần 429 làm mất hết vector đã gọi. Sửa này hiện thực đúng điều PRD đã ghi (nạp vector Weaviate, FR-REC), không lệch PRD.

## File thay đổi

- `src/backend/app/infrastructure/embeddings/cohere_embedder.py` — sửa: `max_attempts = 6`, chờ theo `Retry-After` (tối đa 120s) hoặc lùi mũ tới 60s.
- `src/backend/jobs/embed_products.py` — sửa: embed và ghi Weaviate theo từng lô 96; xoá orphan sau cùng. Chạy lại chỉ embed phần còn thiếu.
- `history/2026-09-24-embed-job-chiu-429.md` — thêm.

## Quyết định

- Ghi theo lô thay vì embed hết trước, vì job đã so `textHash`/`modelVersion` nên chạy lại tự bỏ qua phần đã có.
- Không đổi `batch_size` (96, mức tối đa của Cohere).

## Kiểm tra

- `pytest src/backend/tests -k "embed or cohere or weaviate"`: 7 passed.
- `python -m src.backend.jobs.embed_products --dry-run` vào cluster thật: searchUnits 3183, unchanged 5, embedded 3178.
- Chưa chạy job thật sau khi sửa; chưa kiểm được hành vi khi gặp 429 thật.

## Còn lại / rủi ro

- Nếu 429 do hết quota key trial (giới hạn theo tháng) thì retry không cứu được; cần key production.
- `make index-vectors` còn khởi động Weaviate docker local dù `.env` trỏ cloud (pull image ~6 phút); không sửa, khác phạm vi.
- Chưa index xong nên RecSys vẫn tắt.
