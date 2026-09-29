# Giữ `estimatedTotal` khi người dùng nêu ngân sách; frontend không hiển thị null thành 0 ₫

- Ngày: 2026-09-29
- Tác giả: Nguyễn Minh Nhật / Claude Opus 5
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: agent, backend, frontend, docs

## Mục tiêu

Người dùng báo footer widget lịch trình hiện **TỔNG TIỀN 0 ₫** dù lịch trình có đúng một khách sạn giá
358.808 ₫/đêm. Truy vết ra hai lỗi độc lập, cả hai đều làm mất thông tin người dùng cần thấy (FR-AGT-02
"tính toán chi phí dự kiến").

## Nguyên nhân

1. **Backend huỷ dữ kiện để tránh phải kết luận.** `_budget_warnings` tính đúng tổng rồi xoá đi ngay khi
   `intent.budget` khác `null`: `plan.update(estimatedTotal=None, budgetStatus="UNKNOWN")`. Ý đồ đúng (tổng
   vài sản phẩm không chứng minh được ngân sách cả chuyến) nhưng thực thi sai chỗ: `estimatedTotal` là **dữ
   kiện**, `budgetStatus` mới là **phán xét**. Hệ quả nghịch lý: nêu ngân sách thì mất tổng tiền, không nêu
   thì thấy.
2. **Frontend biến `null` thành `0`.** `estimatedTotal ?? 0` rồi format thẳng → "chưa tính được" hiển thị
   thành "miễn phí".

Hệ quả kéo theo chưa ai phát hiện: `BudgetBar` (`AssistantResultPanel.tsx:314`) render với điều kiện
`intent.budget != null && itinerary.estimatedTotal != null`, mà backend bảo đảm `budget != null` ⟹
`estimatedTotal = null`. Hai vế loại trừ nhau tuyệt đối nên **thanh ngân sách, nhãn WITHIN_BUDGET/OVER_BUDGET
và nút "Giảm chi phí cho vừa ngân sách" chưa từng hiển thị lần nào** — code chết từ lúc viết.

## File thay đổi

- `src/backend/app/agents/steps/composition.py` — sửa: `_budget_warnings` không còn xoá `estimatedTotal` và
  `budgetStatus`; thêm warning `BUDGET_ON_PRODUCT_COST` (thay `UNKNOWN_BUDGET`) nói rõ đối chiếu ngân sách
  chỉ dựa trên chi phí sản phẩm. Docstring ghi lý do để không ai khôi phục hành vi cũ.
- `src/backend/app/domain/itinerary/planning.py` — sửa: bỏ nhánh `deliberately_uncertified` trong
  `validate_plan`. Nó tồn tại chỉ để dung thứ cho việc xoá ở trên; bỏ đi làm kiểm tra **chặt hơn** vì giờ
  `estimatedTotal` và `budgetStatus` luôn phải khớp `totals()`.
- `src/backend/tests/unit/agents/test_itinerary_runtime.py` — sửa: đổi
  `test_total_budget_is_not_certified_from_a_product_subtotal` thành
  `test_a_stated_budget_keeps_the_total_and_says_what_it_covers` — khẳng định tổng khác `null`,
  `budgetStatus` là WITHIN_BUDGET/OVER_BUDGET, có `PRODUCT_COST_ONLY` + `BUDGET_ON_PRODUCT_COST`, không có
  `UNKNOWN_TOTAL`.
- `src/frontend/src/types/travel.ts` — sửa: `totalEstimatedPrice: number | null` kèm chú thích null ≠ 0.
- `src/frontend/src/services/assistant.ts`, `src/frontend/src/features/itinerary/widget/widgetPlan.ts` —
  sửa: `?? 0` → `?? null`.
- `src/frontend/src/services/shareService.ts` — sửa: `compact.p || 0` → `compact.p ?? null` (giữ null qua
  link chia sẻ; `|| 0` còn nuốt cả tổng bằng 0 hợp lệ).
- `src/frontend/src/features/itinerary/widget/WidgetPlanPanel.tsx` — sửa: nhãn "Tổng tiền" → "Chi phí sản
  phẩm" kèm dòng phụ "Chưa gồm ăn uống, đi lại và phát sinh"; null hiện "Chưa tính được" + tooltip giải thích.
- `src/frontend/src/components/assistant/ChatMessageBubble.tsx` — sửa: bỏ đoạn giá khi null thay vì in 0.
- `src/frontend/src/components/assistant/SavedTripsModal.tsx`,
  `src/frontend/src/components/assistant/ShareItineraryModal.tsx` — sửa: null hiện "Chưa tính được"; sửa
  nhãn "Ước tính toàn chuyến" (sai — chưa bao giờ là toàn chuyến) thành "Chi phí sản phẩm trong lịch trình".
- `src/frontend/tests/unit/assistantService.test.ts` — thêm: 2 test cho mapper giữ null và giữ số đã biết.
- `docs/spec/hop-dong-tich-hop-frontend.md` — sửa: bảng trường `COMPLETED` ghi rõ ngữ nghĩa null của
  `estimatedTotal`, bổ sung `UNKNOWN` vào `budgetStatus`, liệt kê ba warning về tiền.
- `history/2026-09-29-giu-estimated-total-khi-co-ngan-sach.md` — thêm: entry này.

## Quyết định

- **Không tạo đề xuất `docs/prd/update/`.** Hành vi cũ mới là thứ lệch PRD: `docs/prd/architecture.md` §3 ghi
  *"Backend tự tính tổng tiền; **giá thiếu** thì tổng là `null`"* — chỉ khi thiếu giá, không phải khi có
  ngân sách. `docs/spec/hop-dong-tich-hop-frontend.md` §4 còn có sẵn ví dụ `estimatedTotal: 12350000` +
  `budgetStatus: "WITHIN_BUDGET"` với `budget: 15000000`. Thay đổi này đưa code về đúng PRD + spec.
- **Giữ nguyên contract.** `schemas/itinerary-agent.yaml` chỉ ràng buộc `estimatedTotal = null ⟹
  budgetStatus = UNKNOWN`; chiều ngược lại tự do. `validate_contract.py` PASS không cần sửa gì.
- **Trả `budgetStatus` thật thay vì giữ `UNKNOWN`.** Giữ `UNKNOWN` thì thanh ngân sách vẫn xám và nút "Giảm
  chi phí" vẫn không hiện — được số tiền, mất tính năng. Sự thận trọng được chuyển vào chỗ đúng của nó:
  warning `BUDGET_ON_PRODUCT_COST` và nhãn "Chi phí sản phẩm" trên UI, thay vì im lặng.
- Đổi tên warning `UNKNOWN_TOTAL` (khi có ngân sách) thành `BUDGET_ON_PRODUCT_COST`: code cũ gắn nhãn "không
  biết tổng" nhưng message lại nói về ngân sách. `ItineraryWarning.code` là string tự do nên không phải sửa
  contract.

## Kiểm tra

- `.venv/bin/python -m pytest src/backend/tests/unit src/backend/tests/architecture -q` → **502 passed**.
- `cd src/frontend && npx tsc --noEmit` → không lỗi.
- `cd src/frontend && npm test` → **141 passed / 24 file** (139 trước khi thêm 2 test mới).
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python src/shared/contracts/tests/validate_contract.py` → **PASS**
  (88 schemas, 4 itinerary statuses, 62 fixtures).
- Chưa chạy bộ golden (`src/evaluation/agent/golden.py`) vì cần LLM thật; nên chạy trước demo theo
  `docs/spec/agent/golden-run.md` mục 6.

## Còn lại / rủi ro

- **`BudgetBar` lần đầu tiên render được.** Nó chưa từng chạy thật nên chưa ai nhìn thấy; cần kiểm bằng mắt
  một lượt có ngân sách. Nút "Giảm chi phí cho vừa ngân sách" gửi câu `"Giảm chi phí để vừa ngân sách"` —
  chưa kiểm agent xử lý câu này ra sao.
- **`estimatedTotal = null` vẫn xảy ra thật, không chỉ ở fixture.** 300/11.387 sản phẩm trong `cdp.products`
  có `unit_price IS NULL` → `priceUnit = UNKNOWN` → `_known_cost` trả `None`. Toàn bộ nằm ở `attraction`
  (299/610 = 49%) và `golf` (1/6); `hotel`, `flight`, `combo` sạch 100%. Theo điểm đến: 12/32 điểm đến
  **không có hoạt động nào có giá**, 5 điểm đến chỉ có 1. Việc bổ sung giá thuộc workstream Data
  (`src/data_collection`), không sửa được từ backend.
- **Nghi vấn dữ liệu chưa xử lý:** 299 sản phẩm null giá đó đều có `available = true`, trong khi
  `docs/spec/agent/truong-du-lieu-san-pham-cho-agent.md` §2.1 định nghĩa `available` là "nguồn có trả giá
  lúc crawl". Loader (`load_products.py:109`) chép thẳng cờ từ bản crawl, không liên quan tới giá. Cần Data
  xác nhận định nghĩa nào đúng.
