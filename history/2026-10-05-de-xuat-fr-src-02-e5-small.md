# Đề xuất PRD: đổi model embedding tìm kiếm FR-SRC-02 sang `intfloat/multilingual-e5-small` local (chờ chốt)

- Ngày: 2026-10-05
- Tác giả: nhóm Search (chốt nội bộ 05/10) / Claude (agent soạn)
- Nhánh: `fix/search`
- Trạng thái: hoàn thành (đề xuất đã soạn; **chưa chốt**, chưa sửa PRD, chưa sửa source theo đề xuất)
- Phạm vi: docs

## Mục tiêu

Nhóm chốt 05/10 chuyển model embedding sang e5-small / 384 và không gọi Cohere nữa, nhưng PRD FR-SRC-02 vẫn ghi Cohere `embed-multilingual-v3.0`
/ 1024. Theo AGENTS.md mục 8, mọi thay đổi lệch PRD phải có đề xuất trong `docs/prd/update/` được chốt trước khi sửa source → soạn đề xuất,
dừng phần adapter backend / đo HTTP cho tới khi chốt.

## File thay đổi

- `docs/prd/update/2026-10-05-fr-src-02-embedding-local-e5-small.md` — thêm: đề xuất theo mẫu mục 8 (lý do, nội dung thay từng mục PRD,
  gate nghiệm thu, source sẽ sửa sau khi chốt); bổ sung số pipeline thật từ `src/evaluation/reports/eval-2026-10-05-search-e5s-dest-nodia.md`.

## Quyết định

- Ghi thẳng lỗ hổng bằng chứng: **chưa có so sánh e5-small với Cohere v3 trên cùng thang đo** (người dùng chốt 05/10 bỏ bước này) → đề xuất
  không khẳng định e5 thắng Cohere, chỉ "không kém có ý nghĩa trong nhóm model local đã so" + gate nghiệm thu trước khi bật production.
- Lý do vận hành lấy từ số đã đo (Cohere miss p95 437 ms trên VM, 500 sau 64 s retry 01/10, Trial 100 lượt/phút) — không thêm số mới.
- Khác đề xuất 30/09 bị từ chối (local chỉ cho demo): đề xuất này thay provider production có gate và đường lui (collection song song).
- Cutoff: nêu rõ không chép 0,62; cosine e5 dồn hẹp nên cutoff tuyệt đối không tách câu ngoài catalog — hiệu chỉnh trên dev/test hoặc chuyển
  sang ngưỡng theo margin.

## Kiểm tra

- Không có lệnh; đối chiếu các mục PRD bị ảnh hưởng (`requirements.md` FR-SRC-02, NFR-PERF-03; `architecture.md` §4, §5; `data-model.md` §1;
  `deployment-plan.md` §2, §5; `implementation-plan.md`) bằng grep trước khi liệt kê.

## Còn lại / rủi ro

- Chờ người dùng / Lead chốt. Sau khi chốt: sửa PRD trước, rồi adapter `infrastructure/embeddings/` (transformers + torch), `core/config.py`,
  job embed, Dockerfile, contract §7.1 `modelVersion`, đo HTTP local + VM, chuyển đề xuất sang `docs/prd/update-archive/`.
- Gate 1 của đề xuất (không thua Cohere trên test split) cần một arm APP Cohere chạy lại trên cùng gold — máy này đã bỏ Cohere, phải chạy ở
  nơi còn khoá hoặc dùng run cũ 01/10 (`eval-2026-10-01-search-v1-3arm.md`) kèm caveat index chưa ổn định (report 05/10 §9).
