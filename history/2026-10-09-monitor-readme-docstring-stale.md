# Sửa ghi chú monitor stale trong README và docstring; ghi nhận monitor staging công khai

- Ngày: 2026-10-09
- Tác giả: Khoa15 (yêu cầu) / Claude Code (Haiku 5.5, thực hiện)
- Nhánh: khoa/ha-runtime-bootstrap-fix
- Trạng thái: hoàn thành
- Phạm vi: data, docs

## Mục tiêu

Ghi chú về monitor job cào trong `src/data_collection` phải khớp code và trạng thái staging hiện tại: monitor staging đang công khai (hai đường deploy khác nhau), embedding đã là e5-small thay vì Cohere, tên tab và nhóm cấu hình khớp UI, và docstring không còn nói "không đọc DB".

## File thay đổi

- `src/data_collection/README.md` — sửa: bỏ `COHERE_API_KEY` khỏi embed của job mới (giữ dòng cho job `daily.py` cũ); mô tả biến `MONITOR_HOST`/`MONITOR_PUBLIC`/`MONITOR_READ_ONLY` và trạng thái công khai staging thay cho "Không mở cổng monitor ra internet"; đổi tên tab (Tiến độ & tốc độ, Log, Trước → sau, Chuẩn hoá – phần ổn định); nhóm "Chạy liên tục" nằm trong Cấu hình → Chạy liên tục; ô thử truy vấn và Embedding dùng e5-small; bỏ khẳng định "Collection `Product` trên Cloud chỉ do job này ghi" và ghi tên mặc định `ProductE5Small`; log runner giữ 30 ngày nhưng `cleanup` xoá quá 7 ngày; `cleanup` xoá image dangling.
- `src/data_collection/monitor.py` — sửa docstring module: mô tả chế độ mặc định (loopback), công khai (`--host 0.0.0.0 --allow-public-host`), `--read-only`; liệt kê đúng những gì monitor đọc, ghi và gọi ra ngoài. Không đổi code.
- `history/2026-10-09-monitor-readme-docstring-stale.md` — thêm: entry này.

## Quyết định

- Chỉ sửa tài liệu. Không đổi code, CD, firewall, Terraform; không deploy.
- Tài liệu mô tả trạng thái đã triển khai, không đánh giá rủi ro: staging công khai theo hai đường. CD non-HA (`.github/workflows/crawler-ci-cd.yml`) chạy `fresh-monitor` đọc-ghi với `MONITOR_HOST=0.0.0.0 MONITOR_PUBLIC=1`; staging-ha (`scripts/deploy-staging-ha-crawler.sh`) chạy chỉ đọc qua `monitor.praxis.io.vn`. Người yêu cầu xác nhận đây là staging và mức bảo mật là quyết định của họ.
- Không tạo đề xuất PRD. `docs/prd/deployment-plan.md` không ghi nhận đường truy cập công khai; entry `2026-10-09-monitor-chi-doc-deploy-thu-cong` cũng ghi nhận lệch này là có chủ đích và không tạo đề xuất. Nếu muốn chốt PRD thì cần đề xuất riêng.
- `COHERE_API_KEY` giữ trong bảng biến của job `daily.py` cũ vì `daily.py:513-514` vẫn kiểm khoá này trước bước index; job catalog mới không cần khoá.
- Không đưa vào tài liệu khẳng định không kiểm chứng được trong repo ("Collection `Product` trên Cloud chỉ do job này ghi").

## Kiểm tra

- `python3 -m py_compile src/data_collection/monitor.py` → ok.
- Venv tạm trong scratchpad, cài `src/data_collection/requirements.txt`. `PYTHONPATH=src/data_collection python -m unittest tests/test_monitor_public.py tests/test_monitor_storage.py tests/test_monitor_backend_calls.py` → 8 tests OK.
- `python monitor.py --help` hiển thị docstring mới.
- Tìm lại sau khi sửa: README không còn "Không mở cổng monitor ra internet", "Luồng & nguồn", "Log trực tiếp", "Nháp / Chính thức", "Chiến thuật)" trong mục Chạy liên tục. Chuỗi "Cohere" còn lại trong README chỉ là dòng `COHERE_API_KEY` của job `daily.py` cũ.
- Không chạy các test khác của `src/data_collection`.

## Còn lại / rủi ro

- Ghi chú sai ngoài phạm vi (chưa sửa, cần người yêu cầu xác nhận):
  - `src/data_collection/fresh_settings.py` dòng 4, 136, 175 — chuỗi help hiển thị trên tab Cấu hình, còn nhắc Cohere.
  - `src/data_collection/pipeline_errors.py` dòng 11 — bảng nhãn lỗi nhắc Cohere.
  - `src/data_collection/run_daily_docker.sh` dòng 365 — comment nói CD gọi lệnh `monitor`; CD thực gọi `fresh-monitor`. Dòng 10 của header nói "chưa có đăng nhập" cùng ý.
  - `src/data_collection/cron_daily.sh` dòng 4, `src/data_collection/daily.py` dòng 70 — còn nhắc Cohere.
  - `AGENTS.md` §6.2 còn ghi Cohere 1024 chiều.
- `--read-only` (`monitor.py`) và `MONITOR_READ_ONLY` (`run_daily_docker.sh`) đang là thay đổi chưa commit. README và docstring mô tả chúng; nếu commit entry này mà không commit hai thay đổi đó thì tài liệu trỏ tới tính năng chưa có trên nhánh.
- Chưa commit.
