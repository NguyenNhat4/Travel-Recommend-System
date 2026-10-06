# Đánh giá Itinerary Agent qua Streamlit

Code demo và bộ đánh giá nằm ở thư mục này (`streamlit_app.py`). Trước khi sửa hoặc tune, đọc
[working context](../../../docs/spec/agent/working-context.md), rồi chỉ mở nhánh Evaluation trong bảng chọn
context. Tài liệu đầy đủ nằm ở [docs/spec/agent/](../../../docs/spec/agent/README.md): cách chạy, trace LangGraph,
response/lỗi và cách chấm.

Chạy bộ test case bằng giao diện (chọn case, xem tiến độ và lý do fail, so các lần chạy, thêm case bằng form):
`make agent-eval`, mở http://127.0.0.1:8503. Code ở `eval_app.py`, `eval_runs.py`, `case_builder.py`; cách dùng ở
[golden-run.md](../../../docs/spec/agent/golden-run.md) mục 2.1.
