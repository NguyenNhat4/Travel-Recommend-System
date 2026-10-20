# Plan cải thiện tiến trình, giá phòng và lời tư vấn agent

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Codex
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: hoàn thành (lập plan); triển khai chưa làm
- Phạm vi: docs

## Mục tiêu

Theo yêu cầu “lên cái plan”: gộp Think/Act/Observe, chỉ gợi ý buổi sáng, hai khách thành hai phòng và lời khám phá dạng liệt kê. Người dùng tự eval chất lượng sau triển khai.

## File thay đổi

- `docs/plan/2026-10-13-cai-thien-agent-tien-trinh-gia-phong-va-loi-goi-y.md` — thêm: phạm vi, bằng chứng, ưu tiên, bước sửa, kiểm kỹ thuật và ca tự eval.
- `history/2026-10-13-plan-cai-thien-agent-tien-trinh-va-gia.md` — thêm: entry này.

## Quyết định

- Không dùng skill, không sửa source/PRD/contract; không commit/push/deploy.
- Giữ hai file untracked của task đề xuất tiến trình trước đó; không gộp chúng thành thay đổi của task này.
- Đọc PRD README, requirements FR-AGT và AC-AGT-02/04/07/09, architecture phần orc/tools/grounding, implementation-plan DoD; history README, các entry mới nhất/triển khai v2/giọng kể và tiến trình; plan v2 và đề xuất tiến trình liên quan.
- Kiểm source: `stay_rooms` dùng priceAdults, validator và final tái dùng helper; prompt v2 đã có luật kể chuyện; frontend adapter v2 còn gắn ba bước và đổi eligible thành inScope. Đây là bằng chứng tĩnh, không kết luận runtime lỗi của người dùng.
- Chưa có trace đầy đủ: ba lỗi là phản hồi cần tái hiện; checklist audit tách khỏi lỗi xác nhận. Không coi kiểm lịch sử là kiểm mới.
- Hướng Think/Act/Observe đã được người dùng đồng ý; bước triển khai rút đề xuất và cập nhật PRD theo hướng đó trước code. Thay công thức phòng nếu trái AC-AGT-04 cần đề xuất riêng, không tự chốt.

## Kiểm tra

- Đối chiếu mã FR/NFR và các file chính trực tiếp trong repo.
- Kiểm khoảng trắng/dấu conflict hai tài liệu mới: PASS; `git diff --check` cho diff tracked: PASS.
- Chưa chạy tests runtime vì chỉ thêm plan/history.

## Còn lại / rủi ro

- Chưa triển khai; chưa tái hiện bằng model/catalog thật, chưa có trace đầy đủ của hội thoại.
- Cần xác định v1/v2 đang chạy; sửa v2 không tự làm lỗi v1 hết. Không tự chuyển phiên bản.
