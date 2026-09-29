# Đặt secret mật khẩu nhóm cho app gán nhãn và chặn secrets.toml khỏi Git

- Ngày: 2026-09-24
- Tác giả: người dùng / Claude Code
- Nhánh: bench/embed-search-day1 (PR vào `bench/embed-search`)
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng chốt mật khẩu nhóm cho app soát draft gold để nhiều annotator cùng gán nhãn. `require_password()` trong `streamlit_app.py` đọc `st.secrets["labeling"]["app_password"]`, nhưng `.gitignore` chưa chặn `.streamlit/secrets.toml` — tạo file secret trước khi đóng lỗ này là rủi ro lộ mật khẩu. Đồng thời `.env.example` chưa hề có `COHERE_API_KEY` dù FR-SRC-02 bắt buộc Cohere, nên người dựng môi trường mới không biết cần khoá nào.

Phục vụ NFR-SEC-01; FR-SRC-01..04 (công cụ đánh giá search).

## File thay đổi

- `.gitignore` — sửa: thêm `.streamlit/secrets.toml` và `**/.streamlit/secrets.toml` kèm comment. Chỉ chặn `secrets.toml`, không chặn cả thư mục `.streamlit/`, để sau này còn commit được `config.toml`.
- `.env.example` — sửa: thêm khối "search bench" với `COHERE_API_KEY=` rỗng, ba biến `SBENCH_*` dạng comment, và ghi chú rằng mật khẩu app nhãn không đặt ở đây (đặt trong `.streamlit/secrets.toml` hoặc Cloud Secrets, fallback `LABELING_APP_PASSWORD`).
- `docs/plan/2026-09-23-search-labeling-app.md` — sửa: mục "Cấu hình deployment" ghi rõ hai nơi đặt secret (file local gitignored + Cloud Settings → Secrets), cảnh báo app **mở công khai** nếu không cấu hình secret, giải thích mật khẩu là cổng trong app (Cloud: mọi mạng đều vào được và dùng chung một file nhãn; local: phải cùng LAN), và quyết định gộp `streamlit` vào `requirements.txt` của bench kèm plan B.
- `history/2026-09-24-secret-streamlit-app-nhan.md` — thêm: entry này.

Không commit: `.streamlit/secrets.toml` (tạo ở máy, đã bị `.gitignore` chặn).

## Quyết định

- Giá trị mật khẩu **không** xuất hiện trong bất kỳ file được commit, entry `history/` hay mô tả PR nào (`history/README.md`: không ghi secret; AGENTS.md §3: không commit/log secret). Tài liệu chỉ ghi placeholder.
- Thêm rule gitignore **trước** khi tạo file secret, rồi kiểm bằng `git check-ignore -v` — không tạo file rồi mới chặn.
- Chặn theo tên file thay vì cả thư mục `.streamlit/`: `config.toml` (theme, cấu hình server) là thứ nên commit được về sau.
- `.env.example` để `COHERE_API_KEY=` rỗng: `config.load_env` bỏ qua giá trị rỗng nên placeholder không thể che khoá thật trong `.env`.
- Không thêm `LABELING_APP_PASSWORD` thành biến trong `.env`: app Streamlit không đọc `.env`, chỉ đọc biến môi trường thật và `st.secrets` — ghi vào `.env` sẽ tạo cảm giác an toàn sai.
- Không lệch PRD: `docs/prd/deployment-plan.md` §2 đã có `COHERE_API_KEY` là biến bí mật, không commit; thay đổi này hiện thực đúng quy tắc đó.

## Kiểm tra

- `git check-ignore -v .streamlit/secrets.toml` → `.gitignore:43:**/.streamlit/secrets.toml`; `src/evaluation/.streamlit/secrets.toml` cũng khớp.
- `git status --short --untracked-files=all | grep -i streamlit`: không có dòng nào sau khi tạo file secret local.
- `grep -c "^COHERE_API_KEY=$" .env.example` = 1 (placeholder rỗng, không có giá trị thật).
- `git grep -n "<mật khẩu>"` trên cây làm việc: không có kết quả (kiểm ở lượt verify cuối).
- Không chạy `validate_contract.py` / `db/verify.sql`: không đổi OpenAPI, mock, schema hay seed.

## Còn lại / rủi ro

- Chưa deploy Streamlit Community Cloud nên chưa dán secret vào Cloud Settings → Secrets và chưa smoke test URL công khai. Cho tới lúc đó chỉ chạy local được.
- File nhãn trên Cloud là ephemeral (`bench_out/search/labels/labels.jsonl`); mất khi app restart/redeploy/ngủ. Team phải tải CSV định kỳ — đánh đổi đã chốt từ 23/09.
- Nếu ai đó chạy `streamlit run` từ thư mục khác gốc repo thì Streamlit không thấy `.streamlit/secrets.toml` và app chạy **không có mật khẩu**. Đã ghi vào plan doc; chưa có kiểm tra tự động cho trường hợp này.
