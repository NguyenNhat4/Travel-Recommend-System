# Deploy app Streamlit gán nhãn 600 search cases

- Ngày: 2026-09-23
- Tác giả: người dùng / Codex
- Nhánh: codex/role-a-day1
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs

## Mục tiêu

Tạo app Streamlit để người dùng và các thành viên trong nhóm lọc 600 query ứng viên Role A bằng ba quyết định `KEEP`, `REJECT`, `NEEDS_EDIT`, rồi deploy trực tiếp từ nhánh. Công việc phục vụ FR-SRC-01..04, NFR-SEC-01, NFR-MAINT-01 và AC-SRC-01.

## File thay đổi

- `docs/plan/2026-09-23-search-labeling-app.md` — thêm: mô tả luồng gán nhãn, cấu hình deploy tối giản, kiểm tra và cảnh báo lưu trữ tạm.
- `src/evaluation/search_bench/labeling.py` — thêm: model case/label, validation, consensus, CSV export và kho JSONL append-only.
- `src/evaluation/search_bench/streamlit_app.py` — thêm: giao diện lọc, điều hướng, gán nhãn, thống kê team và tải CSV.
- `src/evaluation/search_bench/requirements.txt` — thêm: dependency Streamlit cho Community Cloud.
- `src/evaluation/search_bench/tests/test_labeling.py` — thêm: unit test validation, latest/consensus, JSONL và CSV.
- `history/2026-09-23-streamlit-search-labeling.md` — thêm: entry này.

## Quyết định

- Theo yêu cầu rút gọn của người dùng, không tích hợp Google Drive, Google Sheets hay database.
- Giữ mật khẩu nhóm trong Streamlit Secrets; không commit secret vào Git và không để link public lộ trực tiếp dữ liệu benchmark.
- Nhãn được ghi append-only vào file JSONL dùng chung trên instance Streamlit; app cảnh báo rõ đây là lưu trữ tạm và yêu cầu tải CSV định kỳ.
- Không đổi OpenAPI, DDL, retrieval hoặc hành vi sản phẩm; đây là công cụ evaluation theo PRD hiện hành, không cần proposal PRD.

## Kiểm tra

- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s src/evaluation/search_bench/tests -v`: PASS, 3/3 test.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile ...`: PASS.
- `git diff --check`: PASS.
- Xác nhận `drafts_raw.tsv`: 601 dòng gồm header và đúng 600 case.
- Streamlit `AppTest`: chưa chạy cục bộ vì tải dependency vào môi trường tạm bị gián đoạn bởi mạng chậm; URL cloud sẽ được smoke test sau deploy.
- Không chạy `validate_contract.py`: không đổi OpenAPI hoặc mock.

## Còn lại / rủi ro

- File nhãn trên Streamlit Community Cloud có thể mất khi instance restart hoặc redeploy; team cần dùng nút tải CSV định kỳ. Đây là đánh đổi đã được người dùng chọn khi yêu cầu không dùng Drive.
- Cần smoke test URL sau khi Community Cloud build xong và kiểm tra màn hình mật khẩu cùng tổng 600 case.
