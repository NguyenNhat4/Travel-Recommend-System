# Rút gọn golden dataset còn 14 case (mỗi category một case)

- Ngày: 2026-09-25
- Tác giả: nhatutc2 / Claude Code
- Nhánh: feat/agent
- Trạng thái: hoàn thành
- Phạm vi: evaluation, docs
- Thay thế: 2026-09-25-hoi-ngay-di-truoc-khi-lap-lich.md (phần golden dataset)

## Mục tiêu

Người dùng yêu cầu giảm kích thước bộ golden: mỗi category một case, chọn case agent dễ fail nhất. Bộ 75 case (sau khi chèn lượt hỏi ngày đi còn 130 lượt) quá lớn để chạy nhanh và rẻ bằng LLM thật. Quyết định này thay yêu cầu trước đó "giữ 75 case".

## File thay đổi

- `src/evaluation/datasets/itinerary_agent_golden.yaml` — sửa: 75 → 14 case, 23 lượt, 245 dòng; comment đầu file nói rõ đây là bộ smoke rút gọn. Không sửa nội dung 14 case giữ lại.
- `src/evaluation/tests/test_golden.py` — sửa: test mỗi category đúng một case (14 case, id không trùng); ngưỡng số case hỏi ngày từ 40 xuống 5; test `clear_request` không còn ngoại lệ G-005.
- `src/evaluation/agent/golden.py` — sửa: chỉ đổi ví dụ `--only` trong docstring.
- `docs/spec/agent/golden-dataset-how-to-add-more-case.md` — sửa: bảng category thành bảng 14 case kèm lý do chọn; quy ước một-case-một-category; id tiếp theo là G-076; ví dụ case dùng placeholder ngày.
- `docs/spec/agent/golden-run.md`, `README.md`, `evaluation-plan.md` — sửa: số case/lượt, ví dụ `--only`, các chỗ dẫn tới id đã bỏ.
- `docs/spec/agent/presentation-slides.html` — sửa: chỉ lệnh ví dụ `--only G-051,G-062` ở slide 13.

## Quyết định

- Chọn theo hai tiêu chí, ghi thẳng trong bảng ở `golden-dataset-how-to-add-more-case.md`: (1) case đã fail trong `eval-2026-09-24-golden.md` (G-051, G-072, G-057, G-059, G-062, G-047), (2) category chưa từng fail thì chọn ca khó nhất theo đánh giá của tôi (G-075, G-073, G-071, G-064, G-045, G-049); category chỉ có một case thì giữ (G-046, G-066). Đây là **ước lượng**, không phải số đo: biên bản 24/09 chạy trước các sửa đổi hôm nay (hỏi ngày đi, vertical bị loại) nên có case đã hết fail, có case mới fail.
- Bộ này là bộ smoke bắt hồi quy, không đo độ phủ; các số liệu golden trong slide và kịch bản (75 case, 124 lượt, 113 lượt PASS) là kết quả của lần chạy 24/09 nên giữ nguyên, không sửa.
- Khoá quy ước bằng test thay vì chỉ ghi tài liệu, để không ai thêm case thứ hai vào một category mà không đổi quy ước có chủ đích.
- Không có case đổi điểm đến (G-039, G-060), không có case cách nói tương đối "từ ngày mai" (G-005), không có case hỏi ngày rồi trả lời ngày cụ thể: các tình huống này mất độ phủ, chỉ còn trong lịch sử git.

## Kiểm tra

- `pytest src/evaluation/tests/test_golden.py`: 50 passed. `load_dataset`: 14 case, 23 lượt, 14 category, 7 case có lượt hỏi ngày.
- Chưa chạy golden thật (cần LLM và catalog, tốn phí); chưa đo thời gian chạy (ước chừng dưới 2 phút, chưa kiểm chứng).

## Còn lại / rủi ro

- Ba case nhiễu phân loại đã đo ở bộ cũ (G-013, G-032) không còn được theo dõi; muốn đo lại thì dùng dataset ở git.
- Biên bản golden tiếp theo sẽ không so sánh trực tiếp được với biên bản 24/09 (khác số case).
- `docs/spec/agent/README.md` vẫn trỏ tới `golden-dataset.md` không tồn tại (file thật là `golden-dataset-how-to-add-more-case.md`); lỗi có từ trước, chưa sửa.
