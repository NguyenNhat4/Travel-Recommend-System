# Orc tự chủ (assistant v2): rút gọn E02–E10, chạy model thật, nối widget sau công tắc (E11)

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: dang dở
- Phạm vi: agent, backend, contract, frontend, evaluation, docs
- Thay thế một phần: `2026-10-13-orc-tu-chu-e02-e05-nen-tang.md` (schema, registry, dispatcher, tra vé viết lại)

## Mục tiêu

Tiếp tục thực thi plan `docs/plan/2026-10-13-orc-tu-chu-goi-tool-va-chon-san-pham.md` sau phiên Codex (E00–E05 có
history; E06–E11 đã có file nhưng chưa history, chưa chạy với model thật). Người dùng yêu cầu thêm "Simplicity First":
code tối thiểu, không thêm thứ không được yêu cầu. Phục vụ FR-AGT-01–07, NFR-REL-01, NFR-SEC-01/04, NFR-MAINT-01/02;
AC-AGT-02, 04–09. PRD đã chốt ở E00 (`docs/prd/update-archive/2026-10-13-orc-tu-chu-goi-tool-va-chon-san-pham.md`).

## Bằng chứng dẫn tới viết lại

- Schema quyết định gửi model mỗi lần gọi là 193 KB, 159 KB là mô tả rập khuôn do `describe()` sinh.
- Gọi thật OpenAI strict mode: `uniqueItems` bị từ chối (400). Schema cũ có từ khoá này nên mọi lượt v2 với model thật
  hỏng ngay ở lần gọi đầu; các test cũ dùng model giả nên không bắt được.
- `HARD_REQUIREMENT_UNVERIFIED` luôn là vi phạm nên lịch có yêu cầu bắt buộc không bao giờ hợp lệ; câu cảnh báo tiếng
  Anh chèn vào lời đáp tiếng Việt; uiAction luôn 422; không có lọc đầu vào NFR-SEC-04 trước model; store Redis
  giải mã JSON trong Lua (cjson biến mảng rỗng thành `{}`).

## File thay đổi

Backend (viết lại gọn, cùng chức năng plan yêu cầu):
- `src/backend/app/application/itinerary/orc_contracts.py` — sửa: schema tám tool + quyết định execute/respond viết sẵn
  dạng strict (24 KB), mô tả tiếng Việt viết tay, lỗi schema chỉ đúng tham số; bỏ `describe`, `tool_result_schema`.
- `src/backend/app/application/itinerary/product_registry.py` — sửa: một productId một mã `pN`, mã lịch sử phải tra lại
  (STALE_REF), bản rút gọn cho model, con trỏ trang theo điều kiện truy vấn.
- `src/backend/app/application/itinerary/orc_dispatch.py` — sửa: chạy đúng lời gọi orc chọn, ngân sách 10 request
  (không race), thử lại một lần lỗi tạm thời, cache trong lượt, `free_only` đếm riêng có phí/chưa rõ giá, build_itinerary.
- `src/backend/app/application/itinerary/flight_lookup.py` — sửa: đọc hết trang chuyến của tuyến (tối đa 4), thống kê cả
  đợt (rẻ/đắt/trung vị, ngày có/không có chuyến, ngày gần nhất), khung giờ, giá minh hoạ chỉ khi hết giá thật.
- `src/backend/app/application/itinerary/build_itinerary.py` — xoá: gộp vào dispatcher (một hàm).
- `src/backend/app/domain/itinerary/draft_validation.py` — sửa: kiểm giờ/ngày/mở cửa/phòng/bay/khoảng đệm 90/150,
  tiền (thiếu giá là unknown), cảnh báo gom theo mã, tối ưu thứ tự trong ngày giữ đúng tập sản phẩm, lịch rỗng là vi phạm.
- `src/backend/app/domain/itinerary/orc_guardrails.py` — sửa: thẻ có nguồn, trần 10/loại, số qua fact, công bố cảnh báo,
  đồng ý lập lịch, nút trùng; lộ secret là fatal.
- `src/backend/app/application/itinerary/v2_final.py` — sửa: dựng response theo contract, đoạn product thành
  `[Tên](product:id)`, câu cảnh báo vi/en do code viết, lệnh cho nút vé và nút chọn phương án.
- `src/backend/app/application/itinerary/v2_use_cases.py` — sửa: khoá lượt, nhận uiAction server đã cấp, ghi một lần.
- `src/backend/app/infrastructure/persistence/assistant_v2_store.py` — sửa: memory + Redis (SET NX, WATCH/MULTI), mở
  tiếp hội thoại v1.
- `src/backend/app/agents/orc_v2.py` — sửa: graph precheck → decide ⇄ dispatch → guard, prompt tiếng Việt (luật hành vi
  từ prompt v1, bỏ luật quy trình cũ), mã lời gọi do server đánh, thử lại model, tiến trình theo lời gọi thật; gộp runtime.
- `src/backend/app/agents/runtime_v2.py` — xoá: gộp vào `orc_v2.py`.
- `src/backend/app/api/v2/routes/assistant.py` — sửa: mất kết nối không huỷ lượt, lỗi theo Error Envelope.
- `src/backend/app/main.py` — sửa: nối runtime v2.

Contract, frontend, evaluation, docs:
- `src/shared/contracts/schemas/assistant-v2.yaml` — sửa: `Alternative.uiAction`, `Itinerary.party`.
- `src/shared/contracts/tests/validate_assistant_v2.py` — sửa: ca âm 11 thẻ vẫn chỉ sai vì trần.
- `src/shared/mocks/assistant-v2/itinerary-{over,unknown,zero}.json` — sửa: thêm `party`.
- `src/frontend/src/types/assistant-v2.gen.ts` — sinh lại.
- `src/frontend/src/features/itinerary/widget/widgetV2.ts` — thêm: chuyển câu trả lời/tiến trình v2 sang dạng widget.
- `src/frontend/src/context/AssistantProvider.tsx` — sửa: nhánh v2 khi `NEXT_PUBLIC_ASSISTANT_API=v2` (mặc định v1).
- `src/frontend/tests/unit/widgetV2.test.ts` — thêm.
- `src/evaluation/agent/assistant_v2_cases.py` — thêm: chạy ca §6 qua API thật, `--repeat`.
- Tests: `src/backend/tests/fakes/orc_tools.py` (thêm), `tests/unit/agents/test_orc_{contracts,registry,tool_dispatch,loop}.py`,
  `tests/unit/application/test_{assistant_v2_final,assistant_v2_store,assistant_v2_use_case,orc_flight_lookup}.py`,
  `tests/unit/domain/test_orc_{draft_validation,guardrails}.py`, `tests/contract/test_assistant_v2_contract.py` (viết lại),
  `tests/integration/test_assistant_v2_redis.py` (thêm), `tests/unit/application/test_build_itinerary.py` (xoá).
- `docs/spec/agent/working-context.md`, `docs/spec/hop-dong-tich-hop-itinerary-assistant.md` (§4.7),
  `docs/spec/contracts-guide.md`, `src/backend/README.md` — sửa: mô tả v2.

## Quyết định

- Không lệch PRD. Hai bổ sung contract v2 (chưa có client dùng) là thêm field: `Alternative.uiAction` (PRD: xác nhận
  phương án gửi uiAction), `Itinerary.party` (đặt chỗ từ lịch cần số khách đã tính tiền).
- Thiếu giá không phải miễn phí (PRD mới). Dữ liệu Huế không có điểm nào có căn cứ miễn phí nên ca "chỉ chỗ miễn phí"
  trả lời thật là chưa tìm thấy: giới hạn dữ liệu, cần nhóm Data ghi `ticketed=false` cho điểm công cộng.
- Search ngữ nghĩa trả ít kết quả cho câu chung (3/20 điểm Đà Nẵng): không đổi thuật toán Search (ngoài phạm vi);
  prompt hướng orc dùng `list_products` khi xem chung một nơi.
- Hiểu sai ý sửa bằng prompt/mô tả tool, không thêm luật cứng (lấy quyết định thô bằng script trước khi sửa).
- Widget giữ v1 mặc định; v2 bật bằng `NEXT_PUBLIC_ASSISTANT_API=v2` để nghiệm thu E12 trên giao diện, chuyển ở E13.

## Kiểm tra

- Ghi ở phần cuối khi chạy đủ (đang cập nhật).

## Còn lại / rủi ro

- Ghi ở phần cuối khi chạy đủ (đang cập nhật).
