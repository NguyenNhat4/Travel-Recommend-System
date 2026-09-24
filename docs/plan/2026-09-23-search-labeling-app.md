# Streamlit review cho 600 search cases

Phục vụ **FR-SRC-01..04**, **NFR-SEC-01**, **NFR-MAINT-01** và **AC-SRC-01** trong `docs/prd/requirements.md`.

## Mục tiêu

Deploy một app Streamlit gọn để nhiều annotator review độc lập 600 query ứng viên của Role A trước khi chọn khoảng 200 query cho bước tạo pool. Đây là review chất lượng draft (`KEEP`, `REJECT`, `NEEDS_EDIT`), chưa phải relevance label 0/1/2 và chưa tạo `gold_v1`.

## Luồng sử dụng

1. Annotator nhập mật khẩu nhóm rồi nhập tên.
2. App hiển thị query, slice, filter, `expected_no_result`, `source_refs` và ghi chú grounding.
3. Annotator chọn `KEEP`, `REJECT` kèm lý do, hoặc `NEEDS_EDIT` kèm query thay thế.
4. Mỗi lần lưu tạo một event append-only trong file JSONL dùng chung trên instance Streamlit. Nhãn mới nhất theo `(case_id, annotator)` là trạng thái hiện hành.
5. App hiển thị tiến độ cá nhân, số case team đã chạm, bất đồng giữa annotator và cho tải CSV nhãn mới nhất.

## Cấu hình deployment

Entrypoint: `src/evaluation/search_bench/streamlit_app.py`.

Streamlit Secret, không commit vào Git:

```toml
[labeling]
app_password = "<MAT_KHAU_NHOM>"
```

Đây là bản tối giản theo yêu cầu: không dùng Google Drive hay database. File nhãn trên Streamlit là tạm thời và có thể mất khi app restart hoặc redeploy; team cần tải CSV định kỳ bằng nút trong app.

## Kiểm tra và rollback

- Unit test các rule label, trạng thái latest/consensus, JSONL round-trip và CSV export.
- Smoke test app render với đúng 600 case.
- Smoke test URL sau deploy: trang yêu cầu mật khẩu, sau đăng nhập hiển thị 600 case.
- Rollback bằng cách redeploy commit trước; tải CSV trước khi redeploy nếu cần giữ nhãn.
