# Streamlit API Explorer để gọi tay các route backend

- Ngày: 2026-09-24
- Tác giả: người dùng / Claude
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: evaluation

## Mục tiêu

Người dùng cần một giao diện Streamlit để tương tác trực tiếp với các route của backend FastAPI (thử request, xem response, debug auth) mà không phải viết curl bằng tay.

## File thay đổi

- `src/evaluation/api_explorer/openapi_helpers.py` — thêm: hàm thuần đọc `/openapi.json`, sinh body mẫu, ép kiểu tham số, dựng URL và curl (che token), parse SSE.
- `src/evaluation/api_explorer/streamlit_app.py` — thêm: UI chọn route, form tham số/body, đăng nhập lấy Bearer, gắn `X-Service-Token`, gọi thường và SSE, lịch sử request.
- `src/evaluation/tests/test_api_explorer.py` — thêm: 8 unit test cho helper.

## Quyết định

- Route/tham số/body lấy động từ `/openapi.json` của backend đang chạy, không liệt kê cứng: route mới tự xuất hiện, không lệch với code. Nguồn sự thật cho contract vẫn là `src/shared/contracts/openapi.yaml`; công cụ này chỉ phản ánh những gì backend đang phục vụ.
- Đặt trong `src/evaluation/` cạnh app Streamlit sẵn có (`agent/streamlit_app.py`), dùng `streamlit` và `httpx` đã khai báo trong `src/evaluation/requirements.txt`; không thêm dependency.
- Công cụ dev/test, không đổi hành vi sản phẩm, contract, DDL hay kiến trúc backend nên coi là không lệch PRD và không tạo đề xuất trong `docs/prd/update/`. Không gắn mã FR/NFR vì không phải tính năng sản phẩm; nếu người dùng muốn gắn vào một mã thì báo lại.
- Token nằm trong `st.session_state` của tab, không ghi log/file. `X-Service-Token` mặc định đọc từ `AUTH_SERVICE_TOKEN` (biến môi trường hoặc đúng khoá đó trong `.env`). Lệnh curl hiển thị `$ACCESS_TOKEN`/`$AUTH_SERVICE_TOKEN` thay cho giá trị thật.
- Field Optional không có default trong body mẫu là `null` thay vì chuỗi rỗng để không làm lệch hành vi backend.

## Kiểm tra

- `python -m unittest src.evaluation.tests.test_api_explorer`: 8 test pass.
- Streamlit `AppTest` với backend thật ở :8000: app nạp không exception, liệt kê 18 route; gửi `/health`, `GET/POST /search`, `/recommendations` trả 200; `/similar/{id}` id rỗng trả 404 và stream không token trả 422, cả hai hiển thị lỗi đúng.
- Đường SSE kiểm bằng server giả trả 2 event: UI hiển thị đủ hai event kèm thời gian.
- Chưa kiểm: đăng nhập bằng tài khoản thật, `/auth/session*` với service token thật và stream itinerary thật qua LLM.
- Không đổi contract hay mock nên không chạy `validate_contract.py`.

## Còn lại / rủi ro

- Chưa có mục make; chạy bằng `.venv/bin/python -m streamlit run src/evaluation/api_explorer/streamlit_app.py --server.port 8503`.
- Body dạng multipart hoặc content-type khác `application/json` chưa hỗ trợ (backend hiện chỉ dùng JSON).
- `src/evaluation/README.md` chưa tồn tại (AGENTS.md ghi chú hỏi trước khi giả định nội dung) nên chưa viết README cho công cụ này; cách chạy nằm trong docstring đầu file và entry này.
