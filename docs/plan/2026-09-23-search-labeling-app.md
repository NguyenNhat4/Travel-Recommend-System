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

Streamlit Secret, **không commit vào Git**:

```toml
[labeling]
app_password = "<MAT_KHAU_NHOM>"
```

Đặt ở hai nơi, cùng nội dung:

- **Local** — `.streamlit/secrets.toml` ở gốc repo (Streamlit đọc `./.streamlit/secrets.toml` theo thư mục chạy lệnh, nên `streamlit run` phải chạy từ gốc repo). `.gitignore` đã chặn `.streamlit/secrets.toml` và `**/.streamlit/secrets.toml`; kiểm bằng `git check-ignore -v .streamlit/secrets.toml` trước khi tạo file.
- **Streamlit Community Cloud** — app → Settings → Secrets, dán đúng khối TOML trên. Không bao giờ ghi giá trị thật vào file trong repo, entry `history/`, hay mô tả PR.

Fallback: biến môi trường `LABELING_APP_PASSWORD` (chỉ dùng khi `st.secrets` lỗi; app **không** đọc `.env`). Nếu không cấu hình cả hai thì `require_password()` trả về sớm và app **mở công khai, không hỏi mật khẩu** — phải đặt secret trước khi để link ra ngoài.

Mật khẩu chỉ là cổng bên trong app, không liên quan mạng: deploy Community Cloud thì ai có URL và mật khẩu đều gán nhãn được từ bất kỳ mạng nào, và mọi người dùng chung một instance nên chia sẻ cùng một file nhãn (metric "Team đã chạm" / "Case bất đồng" mới đúng). Chạy local thì người khác phải cùng LAN với máy chạy app (`Network URL` mà Streamlit in ra).

Phụ thuộc: Cloud chỉ tự nhận `requirements.txt` cạnh entrypoint hoặc ở gốc repo, mà entrypoint buộc nằm trong `src/evaluation/search_bench/` (app import `labeling` cùng thư mục và đọc `gold/drafts_raw.tsv` cạnh nó). Vì vậy `streamlit>=1.64,<2` nằm chung `src/evaluation/search_bench/requirements.txt` với các dependency bench; Cloud sẽ cài thêm pandas/pyarrow/scipy/cohere/weaviate-client mà app không dùng (build lần đầu chậm hơn, toàn bộ là wheel). Nếu vượt giới hạn của Cloud thì tách entrypoint sang package riêng có `requirements.txt` một dòng.

Đây là bản tối giản theo yêu cầu: không dùng Google Drive hay database. File nhãn trên Streamlit là tạm thời (`bench_out/search/labels/labels.jsonl`, đã gitignore) và có thể mất khi app restart hoặc redeploy; team cần tải CSV định kỳ bằng nút trong app.

## Kiểm tra và rollback

- Unit test các rule label, trạng thái latest/consensus, JSONL round-trip và CSV export.
- Smoke test app render với đúng 600 case.
- Smoke test URL sau deploy: trang yêu cầu mật khẩu, sau đăng nhập hiển thị 600 case.
- Rollback bằng cách redeploy commit trước; tải CSV trước khi redeploy nếu cần giữ nhãn.
