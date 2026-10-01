# Gán nhãn gold chung qua một link, lưu về máy giữ gold/

- Ngày: 2026-09-29
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành — người dùng đã tự chạy cloudflared, hai người đang gán qua link. App đang chạy **bản trước các sửa #4–#7** (người dùng dặn không khởi động lại); chạy lại `sb gold share` để áp dụng.
- Phạm vi: evaluation, docs

## Mục tiêu

Người dùng muốn hai người, ở hai máy **khác mạng**, gán nhãn qua **một link chung**, và nhãn lưu về máy này (máy giữ `gold/`). Người dùng chọn phương án link công khai qua Cloudflare quick tunnel.

Phục vụ FR-SRC-01..04, AC-SRC-01, test-plan §2.5 (gold cho đánh giá search). Không lệch PRD: đây là công cụ gán nhãn nội bộ của bench.

## File thay đổi

- `src/evaluation/search_bench/streamlit_app.py` — sửa: chế độ dùng chung `LABELING_SHARED=1`.
  - `require_shared_access` kiểm mã truy cập riêng `LABELING_CODE_A` / `LABELING_CODE_B`: ≥ 12 ký tự, khác nhau, so bằng `hmac.compare_digest` với cả hai mã; sai mã thì chờ 1 giây.
  - `render_labeling(shared_who)` khoá theo người gán: không có ô chọn người, ô đường dẫn, nút fixture hay các chế độ sửa `gold/`.
  - Nút "Thoát". `_public` bỏ đường dẫn máy chạy app khỏi mọi thông báo lỗi; lỗi mở phiên chỉ hiện câu chung chung (chi tiết ghi ra stderr của server).
  - Ô ghi chú giới hạn 1.000 ký tự.
- `src/evaluation/search_bench/labeling_core.py` — sửa:
  - `_file_lock`: khoá theo file nhãn, dùng cho `save_label` và `clear_label`;
  - `_with_retry`: thử lại ngắn khi Windows từ chối thay file;
  - `NOTE_MAX` = 1.000.
- `src/evaluation/search_bench/__main__.py` — thêm lệnh `sb gold share`.
  - Lần đầu tạo `bench_out/search/label_share/codes.env` (gitignore, mỗi mã 22 ký tự `token_urlsafe(16)`), không in mã ra màn hình.
  - Ghi launcher `<ổ đĩa>\vota-label-share\app.py` **ngoài repo git**; từ chối nếu thư mục nằm trong repo git.
  - Chạy Streamlit chỉ trên `127.0.0.1:<port>`, với `showErrorDetails=type`, `toolbarMode=viewer`, không file watcher.
  - Tiến trình con bỏ mọi biến môi trường có `KEY` / `TOKEN` / `SECRET` / `PASSWORD`.
  - `--dry-run` chỉ chuẩn bị launcher và mã.
- `src/evaluation/search_bench/tests/test_streamlit_app.py` — thêm:
  - `test_shared_mode_needs_strong_distinct_codes`;
  - `test_shared_mode_locks_labeler_and_hides_everything_else`.
- `src/evaluation/search_bench/tests/test_labeling_core.py` — thêm `test_concurrent_saves_do_not_lose_labels`, `test_note_too_long_is_rejected`.
- `src/evaluation/search_bench/tests/test_gold_cli.py` — thêm `test_share_dry_run_writes_launcher_outside_git_and_codes`.
- `docs/spec/bench/README.md` — sửa: thêm mục "Gán nhãn chung qua một link (29/09)".
- `history/2026-09-29-gan-nhan-chung-qua-link.md` — thêm: entry này.

Ngoài repo, không commit:
- `bench_out/search/label_share/codes.env` (mã truy cập);
- `H:\vota-label-share\app.py` (launcher).

## Quyết định

- **Một app ở máy giữ `gold/`, không đồng bộ file giữa hai máy.** Nhãn ghi thẳng vào `gold/labels/labels_<X>.csv` trên máy này. Sau đó `kappa` / `merge` chạy tại chỗ.
- **Instance riêng cho chia sẻ** (cổng 8502, chỉ 127.0.0.1). Instance đầy đủ ở 8501 giữ nguyên, chỉ dùng trên máy này. Instance dùng chung chỉ có chế độ gán nhãn, vì các chế độ khác sửa `overrides.tsv` / `drafts_raw.tsv`.
- **Mã theo người thay cho mật khẩu nhóm.** Mật khẩu nhóm cũ vẫn để người gán tự chọn A hoặc B và mở được file của người kia, trái mục "Gán độc lập" của `gold-guide.md`. Mã riêng khoá cứng người gán và giữ các câu chung độc lập. Mã 22 ký tự ngẫu nhiên (~128 bit), nên chặn 1 giây mỗi lần sai là đủ.
- **Launcher ngoài repo git.** Review bảo mật tìm ra (mức high) rằng Streamlit trả lời yêu cầu `load_git_info` của bất kỳ trình duyệt nào, kể cả trước khi nhập mã. Câu trả lời gồm tên repo GitHub, nhánh, file chưa commit, cùng đường dẫn tuyệt đối của script. Streamlit 1.64 không có tuỳ chọn tắt.
  - Kiểm: `GitRepo(launcher).get_repo_info()` = `None`.
  - Chạy thẳng trong repo thì ra `('Zeno2k3/Travel-Recommendation-Product', 'bench/embed-search', …)`.
- **Khoá file có lỗi tinh vi trên Windows.**
  - Bản đầu lấy khoá theo `Path.resolve()`. Trên Windows, chuỗi trả về đổi sau khi thư mục `labels/` được tạo (lần ghi đầu), nên cùng một file ra nhiều đối tượng khoá (đo được 20 khoá cho 15 lần chạy, 14 lần ghi chen nhau) và vẫn mất nhãn.
  - Đổi sang `os.path.normcase(os.path.abspath())`: 40/40 lần chạy đồng thời không mất nhãn; bỏ khoá thì 10/10 lần mất nhãn.
- **Tải và chạy `cloudflared` bị bộ phân loại quyền của Claude Code chặn.** Không tìm đường vòng. Người dùng tự cài và chạy tunnel (README).
- **Chấp nhận:** `/_stcore/metrics` của Streamlit (không tắt được) cho người có link biết số phiên đang mở; không lộ nội dung.

## Kiểm tra

- `pytest evaluation/search_bench/tests`: **275 passed, 10 skipped** sau các sửa #4–#7.
- Test đột biến khoá file: bỏ khoá → `test_concurrent_saves_do_not_lose_labels` đỏ 10/10; có khoá → xanh 40/40.
- `sb gold share --dry-run`: launcher `H:\vota-label-share\app.py`, lệnh có `--server.address 127.0.0.1`.
- App dùng chung chạy thật: `netstat` chỉ `127.0.0.1:8502 LISTENING`, `/_stcore/health` = ok.
- AppTest trên chính launcher với bản sao pool thật:
  - mã A: 78 câu / 1.999 cặp; mã B: 79 câu / 2.000 cặp;
  - không có ô chọn người; caption không lộ đường dẫn;
  - `gold/labels/` thật không bị tạo.
- **Review bảo mật đối kháng** (workflow `shared-label-security-review`): 3 người tấn công theo 3 nhóm mục tiêu, mỗi phát hiện có 2 người cố bác bỏ. 8 phát hiện:
  - **#0 [high] lộ repo git, nhánh, đường dẫn trước khi nhập mã** → launcher ngoài repo (ở trên).
  - **#1 [medium] thông báo lỗi lộ đường dẫn tuyệt đối** → `_public`; lỗi mở phiên chỉ hiện câu chung chung.
  - **#2 [low] ghi chú quá 131.072 ký tự làm file nhãn không đọc lại được** → `NOTE_MAX` = 1.000.
  - **#3 [low] `/_stcore/metrics` lộ số phiên:** cả hai phiếu xác minh đều bác (không vi phạm mục tiêu nào); chấp nhận, ghi README.
  - **#4 [medium] hai tab cùng người, Windows báo `PermissionError` khi đọc lúc tab kia đang ghi, mất một lần sửa** → `load_labels` cũng qua khoá (đổi sang `RLock`) và thử lại. Test `test_concurrent_reads_and_writes_do_not_fail`: bỏ khoá ở phần đọc thì đỏ 15/15, có khoá xanh 15/15.
  - **#5 [medium] "Thoát" rồi đăng nhập người kia trên cùng trình duyệt, nhãn chờ và ghi chú của A lọt vào labels_B.csv** → `_clear_label_state` xoá mọi khoá `lbl*` khi thoát và khi đăng nhập. Test `test_shared_logout_drops_pending_state_of_previous_labeler`.
  - **#6 [medium] khách chưa có mã đẩy file vào `/_stcore/upload_file`, làm đầy RAM** (reviewer đo +203 MB với 10 file) → `--server.maxUploadSize 0` trong `sb gold share` (reviewer kiểm: 413).
  - **#7 [low] mở hàng trăm phiên làm app chậm cho cả hai người** → cổng nhập mã chạy ngay sau định nghĩa hàm (`SHARED_WHO`), khách chưa có mã không chạy phần lớn script. Chỉ giảm nhẹ; chặn hẳn cần Cloudflare Access hoặc named tunnel có chính sách truy cập (cần tài khoản).
  - Bước xác minh của #6 và #7 bị bộ lọc an toàn từ chối. Mình tự đọc bằng chứng: hợp lý, không có dấu hiệu bất thường.
- **Test cũ `test_label_mode_resume_progress_and_children`:** dùng việc "không có `gold/labels/`" làm dấu hiệu, nay sai vì hai người đã gán thật (A 76 nhãn, B 16 nhãn, `pool_sha` khớp meta). Đổi sang kiểm "không có nhãn qid `c9…` của fixture trong `gold/labels/`".

## Còn lại / rủi ro

- **Người dùng:**
  1. Cài `cloudflared` (`winget install --id Cloudflare.cloudflared`).
  2. Chạy `cloudflared tunnel --url http://127.0.0.1:8502`.
  3. Gửi link cho hai người, kèm mã riêng từ `bench_out/search/label_share/codes.env`.
- Link đổi mỗi lần chạy lại tunnel. Tắt tunnel khi không gán.
- Máy này phải bật (không ngủ) trong lúc hai người gán.
- Gán xong: `sb gold kappa gold/labels/labels_A.csv gold/labels/labels_B.csv` → `merge` → `import` → `check`, rồi commit file nhãn.
