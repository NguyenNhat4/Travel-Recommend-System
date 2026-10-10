# Tối ưu tổng quãng đường của chuyến, cho phép đổi khách sạn giữa chuyến

- Ngày: 2026-10-07
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: feat/agent
- Trạng thái: dang dở
- Phạm vi: agent, contract, frontend, docs
- Thay thế: history/2026-10-07-de-xuat-toi-uu-quang-duong-nhieu-khach-san.md
- Bị thay thế bởi: history/2026-10-08-khach-san-theo-ngan-sach-va-phuong-an-khac.md

## Mục tiêu

Áp dụng đề xuất `docs/prd/update-archive/2026-10-07-toi-uu-quang-duong-nhieu-khach-san.md`, do Nguyễn Minh Nhật chốt ngày
2026-10-07. Mã liên quan: FR-AGT-03, NFR-REL-01, AC-AGT-04.

Lịch trình tối ưu đúng quãng đường người dùng phải đi:
- ngày 1: A → B → H₁;
- ngày giữa: H(d−1) → A → B → H_d;
- ngày cuối: H(n−1) → A → B.

Lịch được phép đổi khách sạn một lần giữa chuyến.

## File thay đổi

**PRD**
- `docs/prd/requirements.md` — sửa AC-AGT-04 theo đoạn "Thay bằng" của đề xuất. Riêng chuyến tối thiểu được đổi khách sạn
  là **5 ngày**, xem Quyết định.
- `docs/prd/update/2026-10-07-toi-uu-quang-duong-nhieu-khach-san.md` → `docs/prd/update-archive/` — chuyển, trạng thái
  `đã áp dụng`, có thêm mục "Sửa khi áp dụng". Dùng `mv` vì file chưa được track.

**Contract 1.19.0** (chỉ cộng thêm)
- `src/shared/contracts/schemas/itinerary-agent.yaml` — `ItineraryStay.fromNight`, `ItineraryPlan.stays` (tối đa 2 mục).
- `src/shared/contracts/openapi.yaml` — version 1.18.0 → 1.19.0.
- `src/shared/mocks/assistant/createItinerary.200-completed-two-stays.json` (mới), `src/shared/mocks/index.json`.
- `src/backend/app/main.py`, `src/backend/tests/contract/test_search_contract.py` — version 1.19.0.
- `src/frontend/src/types/api.gen.ts` — sinh lại bằng `openapi-typescript`.

**Backend**
- `src/backend/app/domain/itinerary/routing.py` (mới):
  - `route_cost`;
  - `optimize`: chọn khách sạn từng đêm, ghép ngày, thứ tự buổi, thay điểm bị bỏ.
- `src/backend/app/domain/itinerary/planning.py`:
  - `compose_plan` gọi `routing.optimize`; bỏ `_group_by_distance`;
  - proposal có `stays`, slot `CHANGE_STAY`;
  - `render_proposal`, `totals`, `validate_plan` hỗ trợ nhiều khách sạn;
  - thêm `_stay_issue`.
- `src/backend/app/domain/itinerary/types.py` — thêm `ProposedStay`, `Proposal.stays`.
- `src/backend/app/agents/steps/composition.py` — câu tiêu chí có vế đổi khách sạn; xét nguồn của mọi khách sạn.
- `src/backend/app/agents/steps/narration.py` — mục Nơi nghỉ liệt kê từng khách sạn kèm các đêm; payload LLM có `stays`.
- `src/backend/app/agents/steps/prompts.py` — luật cho nhiều khách sạn và dòng chuyển khách sạn.
- `src/backend/app/agents/steps/validation.py` — `answer_text`, `selection_snapshot` gồm mọi khách sạn.
- `src/backend/app/agents/steps/messages.py` — câu tiêu chí mới, `plan_criteria_change`, nhãn đêm.

**Frontend**
- `src/frontend/src/features/itinerary/widget/widgetPlan.ts` — map `stays` kèm `fromNight`, `dayRange`.
- `src/frontend/src/features/itinerary/widget/WidgetDays.tsx` — khách sạn của ngày lấy theo đêm, thay cho luật chia đôi.
- `src/frontend/src/components/assistant/AssistantResultPanel.tsx`:
  - `itineraryCartItems` đặt mỗi khách sạn từ ngày của đêm đầu tiên ở đó;
  - mục Nơi lưu trú hiện từng khách sạn.
- `src/frontend/src/types/travel.ts` — `ItineraryStayItem.fromNight`.

**Test**
- `src/backend/tests/unit/domain/test_itinerary_routing.py` (mới, 14 test), gồm:
  - so với vét cạn;
  - đổi khách sạn đúng 1 lần ở chuyến 5 ngày;
  - không đổi ở chuyến 4 ngày hoặc khi lợi dưới 15 km;
  - thứ tự buổi theo hướng khách sạn;
  - tất định;
  - chuyến 7 ngày dưới 1 giây.
- `src/backend/tests/unit/agents/test_composition_plan_criteria.py`:
  - đổi kỳ vọng câu chữ của 2 test, vì câu tiêu chí đổi nội dung có chủ đích;
  - thêm test câu đổi khách sạn.
- `src/backend/tests/unit/agents/test_narration.py` — thêm `TwoStaysTests` (3 test).
- `src/frontend/tests/unit/widgetDays.test.tsx`, `assistantResultPanel.test.tsx` — mỗi file thêm 1 test. Cả hai fail trên
  code cũ.

## Quyết định

- **Chuyến tối thiểu được đổi khách sạn là 5 ngày.** Đề xuất ghi "từ 4 ngày" cùng lúc với "mỗi khách sạn ít nhất 2 đêm",
  nhưng chuyến 4 ngày chỉ có 3 đêm nên không chia được 2 + 2. Người dùng chốt giữ "ít nhất 2 đêm".
- **Chuyến 1 ngày kết thúc ở khách sạn.** Chuyến này vẫn có 1 đêm (`max(1, days − 1)`). Nếu không tính chặng về khách
  sạn, khách sạn không ảnh hưởng gì tới quãng đường, và khách sạn rẻ ở xa 30 km sẽ thắng.
- **Điểm chưa rõ vị trí bị bỏ qua khi cộng chặng**: không cộng và không đoán. Khách sạn chưa rõ vị trí không được đem ra
  so; khi không khách sạn nào rõ vị trí thì dùng thứ tự cũ (nguồn, giá, sao).
- **Hiệu năng.** Thời gian ban đầu lên tới 950 ms ở chuyến 7 ngày, nay dưới 200 ms nhờ ba thay đổi:
  - nhớ khoảng cách theo `productId`;
  - xếp hạng mọi chuỗi khách sạn bằng tìm kiếm cục bộ, rồi chỉ giải chính xác 3 chuỗi đứng đầu (`EXACT_SHORTLIST`);
  - lọc rẻ trước khi thử thay một điểm.
- **Giải chính xác khi có tối đa 10 điểm; nhiều hơn thì tìm kiếm cục bộ, nên chỉ gần tối ưu.**
- **`stays` luôn được gửi khi có khách sạn; `stay = stays[0]`.** Nhờ vậy client cũ vẫn chạy.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py`: PASS (117 schemas, 94 fixtures).
- `pytest src/backend/tests/unit/domain src/backend/tests/unit/agents src/backend/tests/architecture`: 1152 passed.
- `pytest src/backend/tests`: 1859 passed, 35 skipped, 1 failed. Test fail là kiểm version `1.18.0`; sau khi sửa version,
  `pytest src/backend/tests/contract` cho 107 passed. Chưa chạy lại cả bộ sau lần sửa đó.
- `vitest run`: 719 passed (71 file). `tsc --noEmit`: sạch.
- Thời gian `compose_plan` (dữ liệu ngẫu nhiên, 10 khách sạn, 5 lần mỗi cỡ):

  | Cỡ chuyến | Thời gian lớn nhất |
  |---|---|
  | 3 ngày / 10 điểm | 5 ms |
  | 5 ngày / 12 điểm | 53 ms |
  | 7 ngày / 20 ứng viên | 185 ms |

- Mô phỏng tất định trên snapshot 30/09 (seed 42, 30 mẫu mỗi ô), so với bản AC-AGT-04 v1:
  - km nhỏ hơn hoặc bằng v1 ở mọi mẫu, trừ 3/30 mẫu Hà Nội 3 ngày. Ba mẫu này đi xa hơn dưới 1,4 km để lấy khách sạn rẻ
    hơn, đúng luật mức 2 km;
  - **tiền khách sạn tăng mạnh**: trung vị gấp 4,9 lần khách sạn rẻ nhất, tối đa gấp 37 lần (Phú Quốc 5 ngày). Việc này
    dẫn tới đề xuất `docs/prd/update/2026-10-07-quy-doi-km-ra-tien.md`.
- Dữ liệu cho mô phỏng: catalog staging được nạp vào Postgres local bằng `--catalog-only` (chỉ đọc từ cloud). Không có file
  nào của repo thay đổi.

## Còn lại / rủi ro

- **Đang chờ chốt `docs/prd/update/2026-10-07-quy-doi-km-ra-tien.md`.** Đề xuất thay luật so sánh mức 2 km bằng tổng
  tiền + km × đơn giá. Chưa sửa code theo đề xuất này.
- **Chưa cập nhật spec**:
  - `docs/spec/agent/nghiep-vu/xep-lich.md`, `glossary.md`;
  - `docs/spec/agent/langgraph-nodes.md` §5;
  - `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` §2.7, §4.2;
  - `docs/spec/hop-dong-tich-hop-frontend.md`.

  Lý do: luật so sánh sẽ đổi sau khi chốt đề xuất trên, nên viết một lần cho bản cuối. Spec hiện vẫn mô tả bản AC-AGT-04 v1.
- **Chưa viết report** `src/evaluation/reports/eval-2026-10-07-toi-uu-quang-duong.md`, vì cùng lý do.
- **Chưa chạy agent end-to-end** với LLM thật.
- Lượt "đổi khách sạn" không nêu tên khi lịch có hai khách sạn: chưa rõ đổi khách sạn nào.
