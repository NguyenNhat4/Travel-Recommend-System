# Đề xuất: lịch trình ít di chuyển (gom điểm gần nhau, khách sạn gần các điểm)

- Ngày: 2026-10-07
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: docs
- Bị thay thế bởi: history/2026-10-07-lich-trinh-it-di-chuyen.md

## Mục tiêu

Người dùng yêu cầu lịch trình giảm việc đi lại: mỗi ngày gom các hoạt động gần nhau, và một khách sạn cho cả chuyến nằm
gần các hoạt động đó. Hiện `compose_plan` không xét vị trí: chọn khách sạn và hoạt động rẻ nhất, rải đều theo số lượng.

Đây là hành vi mới chưa có trong PRD. Theo AGENTS.md §8, phải có đề xuất được chốt trước khi sửa source. Mã liên quan:
FR-AGT-03, NFR-REL-01.

## File thay đổi

- `docs/prd/update/2026-10-07-lich-trinh-it-di-chuyen.md` — thêm, trạng thái `chờ chốt`. Nội dung: thêm AC-AGT-04 vào
  `requirements.md` §3.

## Quyết định

Các quyết định dưới đây do người dùng chọn trong phiên plan ngày 2026-10-07:
- **Một khách sạn cho cả chuyến**, không đổi khách sạn theo cụm. Đổi theo cụm sẽ phải đổi `stay` trong contract, cách tính
  tiền, widget và đặt phòng.
- **Gần trước, rẻ sau.** Hai lựa chọn chênh dưới 2 km coi như gần ngang nhau, khi đó so giá. Cần mức này vì khoảng cách là
  số thực, gần như không bao giờ bằng nhau, nên nếu so khoảng cách trực tiếp thì giá không bao giờ được dùng tới.
- **Rút gọn đợt này:** chỉ dùng khoảng cách đường chim bay, không thêm service, không đổi contract. Ba việc để đợt sau, mỗi
  việc một đề xuất riêng:
  - quãng đường bộ thật bằng OSRM và hiện km/phút;
  - nâng hạng khách sạn theo ngân sách (greedy);
  - đánh dấu toạ độ tâm thành phố.
- **Câu trả lời nêu tiêu chí xếp lịch:** người dùng yêu cầu.
- **Độ chính xác của km đã được kiểm, không đảm bảo đúng tuyệt đối.** Kiểm trên snapshot 2026-09-30:
  - đường chim bay khác đường đi thật, nhất là ở đảo và nơi phải đi thuyền hoặc cáp treo;
  - khoảng 30 sản phẩm tour và xe đưa đón mang toạ độ tâm thành phố: Hà Nội (21.0283, 105.854) có 15 sản phẩm, Ninh
    Bình (20.2573, 105.9719) có 15 sản phẩm.

  Đường chim bay đủ dùng để so điểm nào gần hơn, nhưng chưa đủ tin cậy để hiện số km cho người dùng.

## Kiểm tra

- Không chạy test: thay đổi chỉ là tài liệu đề xuất.
- Số liệu toạ độ lấy bằng script đọc-only trên `src/data_collection/snapshots/2026-09-30/products.jsonl.gz`.

## Còn lại / rủi ro

- **Đang dừng ở bước 1 của AGENTS.md §8: chờ người dùng chốt đề xuất.** Chưa sửa PRD, spec hay code.
- Sau khi chốt, làm theo kế hoạch đã duyệt:
  1. thêm AC-AGT-04 vào `requirements.md`, `git mv` đề xuất sang `update-archive/`;
  2. viết test fail trước;
  3. thêm `domain/itinerary/geo.py`, sửa `compose_plan`;
  4. thêm câu tiêu chí `PLAN_CRITERIA`;
  5. sửa spec agent;
  6. tạo entry history mới, entry này ghi `Bị thay thế bởi`.
