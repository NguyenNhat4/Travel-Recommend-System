# App gán nhãn: lưu bằng nút Lưu thay cho lưu sau mỗi lần sửa

- Ngày: 2026-09-29
- Tác giả: tqanh123 / Claude Code
- Nhánh: bench/embed-search
- Trạng thái: hoàn thành — chưa áp dụng cho app dùng chung đang chạy (người dùng dặn không khởi động lại; chạy lại `sb gold share` khi hai người nghỉ)
- Phạm vi: evaluation, docs

## Mục tiêu

Người dùng yêu cầu: không lưu sau mỗi lần đổi một nhãn nữa, thêm một nút Lưu.

Trước đây mỗi lần sửa một ô, app ghi file rồi dựng lại cả bảng (đổi key của bảng). Người gán phải chờ và bị mất vị trí đang xem sau từng nhãn, nhất là khi đi qua tunnel.

Phục vụ FR-SRC-01..04, AC-SRC-01, test-plan §2.5 (gold cho đánh giá search).

## File thay đổi

- `src/evaluation/search_bench/labeling_core.py` — sửa:
  - thêm `apply_changes(s, qid, changes)` → (lỗi, product_id đã lưu): lưu một lượt nhiều dòng của một câu qua `save_label` / `clear_label`, dòng lỗi không làm hỏng dòng khác;
  - thêm `MSG_NEED_CHILDREN`;
  - sửa docstring module.
- `src/evaluation/search_bench/streamlit_app.py` — sửa chế độ gán nhãn:
  - bảng `data_editor` bỏ `on_change`, nên chỉnh bảng không ghi file và bảng không bị dựng lại;
  - `_lbl_pending` đọc thay đổi chưa lưu (bảng + ô hạng phòng);
  - nút **💾 Lưu (N)** (`_lbl_save_click`), khoá khi không có gì để lưu, kèm dòng "N thay đổi chưa lưu";
  - chuyển câu (Trước / Sau / ô chọn câu / Câu chưa xong tiếp theo) tự lưu câu đang mở trước (`_lbl_save`); lưu lỗi (vd. nhãn 2 chưa tick hạng phòng) thì ở lại câu đó và báo lỗi;
  - ô hạng phòng hiện theo nhãn đang chỉnh (chưa cần lưu) và chỉ lưu khi bấm Lưu;
  - "Thoát" (app dùng chung) lưu trước rồi mới xoá state;
  - bỏ `_lbl_edit`, `_lbl_children`, các khoá `lbl-pend-*` / `lbl-pendnote-*`.
- `src/evaluation/search_bench/tests/test_labeling_core.py` — thêm `test_apply_changes_saves_valid_rows_and_reports_the_rest`.
- `src/evaluation/search_bench/tests/test_streamlit_app.py` — sửa `test_label_mode_resume_progress_and_children` theo hành vi mới: tick hạng phòng chưa ghi file; nút "💾 Lưu (1)"; bấm Lưu thì ghi; sửa rồi bấm "Sau →" thì tự lưu; nhãn 2 bỏ hết hạng phòng thì không cho rời câu và báo lỗi.
- `docs/spec/bench/prompts/may2-label-app.md` — sửa: ghi chú 29/09 ở mục "Lưu ngay sau mỗi thay đổi".
- `history/2026-09-29-nut-luu-gan-nhan.md` — thêm: entry này.

## Quyết định

- **Tự lưu khi rời câu.** Người dùng chỉ yêu cầu nút Lưu. Mình thêm tự lưu khi chuyển câu và khi thoát, để không mất công nếu quên bấm. Câu có dòng lỗi thì không cho rời, để lỗi không bị bỏ qua.
- **Lưu một phần.** Trong một lượt lưu, dòng hợp lệ vẫn được ghi. Bảng chỉ được dựng lại (tăng `lbl-ver`) khi không còn lỗi, để các dòng lỗi vẫn còn trên bảng cho người gán sửa.
- **Chưa tự lưu khi đóng tab trình duyệt.** Streamlit không có sự kiện này, nên thay đổi chưa lưu của câu đang mở sẽ mất. Dòng "N thay đổi chưa lưu" nhắc người gán.

## Kiểm tra

- `pytest evaluation/search_bench/tests`: **276 passed, 10 skipped**.
- `pyflakes` các file đổi: sạch.
- AppTest không điều khiển được `data_editor`: phần đọc thay đổi của bảng giữ nguyên cách parse `edited_rows` của bản trước; phần lưu kiểm qua `apply_changes`; nút Lưu / tự lưu kiểm qua ô hạng phòng.

## Còn lại / rủi ro

- **App dùng chung đang chạy bản cũ** (vẫn lưu sau mỗi lần sửa). Khi hai người nghỉ: dừng tiến trình `sb gold share`, chạy lại lệnh đó. Link cloudflared giữ nguyên, hai người nhập lại mã.
- Chưa commit.
