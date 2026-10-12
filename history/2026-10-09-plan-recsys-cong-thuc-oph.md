# Plan công thức điểm mới cho recommendation (OPH-L), quyết định 09/10 và hai đề xuất PRD

- Ngày: 2026-10-09
- Tác giả: tqanh123 / Claude Code
- Nhánh: feat/recSys_update-2
- Trạng thái: hoàn thành (plan + đề xuất); phần code bench theo dõi ở entry riêng
- Phạm vi: docs, evaluation

## Mục tiêu

Đọc brainstorm `docs/spec/bench/recommendation_persona_profile_latency.md`, brainstorm công thức tính điểm mới, lập plan code + bench
so với công thức production; ghi quyết định của người dùng và tách các đề xuất PRD đã chốt. FR-REC-01, FR-REC-02, FR-REC-03,
FR-REC-04, NFR-PERF-01, NFR-PERF-03.

## File thay đổi

- `docs/plan/2026-10-09-recsys-cong-thuc-oph.md` — thêm: plan (tóm tắt, §0 quyết định 09/10, bối cảnh, 4 ứng viên, công thức OPH-L, thang ablation, kế hoạch code, giao thức bench, PRD, rủi ro, các bước)
- `docs/prd/update/2026-10-09-recsys-uu-tien-chuyen-da-dat.md` — thêm: đề xuất [D] sửa I-3 (chuyến đã đặt ưu tiên hơn lượt xem lẻ đến sau), đã chốt, chưa áp dụng
- `docs/prd/update/2026-10-09-persona-trang-thai-cold-start-va-phong-cach-du-lich.md` — thêm: đề xuất [E] persona = 4 trạng thái cold-start, phong cách du lịch là đặc trưng của khách, dormant 365 ngày; đã chốt, chưa áp dụng
- `docs/spec/bench/recommendation_persona_profile_latency.md` — thêm (file người dùng viết): chèn khối trạng thái "ghi chú nghiên cứu, không chuẩn tắc", mã FR/NFR và các điểm lệch code

## Quyết định

- Brainstorm qua 4 hướng thiết kế (OPH, L3P, LW-Seg, F20 làm nguyên văn brainstorm), ba giám khảo chấm theo: đo được, lợi kỳ vọng, chi phí/tuân thủ. OPH 22,5/30 làm khung; ghép phần sửa nghiệp vụ của L3P và đặc trưng cart của LW-Seg.
- Loại phần lớn hạng ngữ cảnh của brainstorm (tier, freshness, repeat_penalty, last_destination, home_city làm tín hiệu điểm đến): không có tín hiệu hoặc lộ đáp án trên prodcopy (plan §2.5).
- Người dùng 09/10 (plan §0): duyệt plan; cho merge `feat/recSys_update`; `pop_h` vào phạm vi; cho tune `W_ORIGIN`/`W_CART`; đồng ý G1-LLBO(b), G1-open′, LIMIT 500, đánh dấu brainstorm doc; I-3 tách đề xuất [D] và chốt; dùng bản dự phòng OPH-prod (G7); dormant 365 ngày; persona = 4 trạng thái cold-start, PRD đổi persona phong cách du lịch thành đặc trưng của khách.
- `diagnostics.dormant` của contract giữ 90 ngày (không đổi semantics v1); 365 ngày áp cho segment `P3_dormant` và `strategy = dormant`.
- [D] và [E] chưa áp dụng vào PRD/engine: đổi engine bây giờ sẽ đổi mốc B0 của bench. Áp dụng ở Pha B (plan §5.2) hoặc khi người dùng yêu cầu.
- Tiêu chí G7 do plan đề nghị (plan §7.6), người dùng chốt dùng bản dự phòng.

## Kiểm tra

- Đối chiếu `profile.py`: `W_SHORT, W_POP, W_LONG = 0.7, 0.15, 0.15` (dòng 20); `trip_is_open` là if/else (dòng 74-81); `score_candidates` không đọc persona (dòng 145-149).
- Merge `feat/recSys_update` vào `feat/recSys_update-2` (commit `eff8abc`): 9 file conflict do hai commit eval(recsys) đã được viết lại bên kia, lấy bản `feat/recSys_update`; `git diff feat/recSys_update HEAD` rỗng.
- Lane A (`a4f57e1`) có trong nhánh: split prodcopy đóng băng, `baseline_v2-*`, `eval_split(..., idx)` có `destHit@20`.
- Chưa chạy code hoặc bench nào.

## Còn lại / rủi ro

- S1 (harness bench) trở đi theo plan §10.
- Áp dụng [D] và [E] (PRD trước, rồi engine, spec, seed, AGENTS.md §6.4) ở Pha B.
- Với ngưỡng 365 ngày, khách `P3_dormant` chủ yếu nằm ở LLBO (nhóm churned của seed); temporal/nexttrip gần như không có. Phase 0 đếm lại.
