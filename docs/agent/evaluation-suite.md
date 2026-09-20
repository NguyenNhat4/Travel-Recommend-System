# Chạy case, batch và cách chấm

Chạy bộ 25 case qua Streamlit, cách tính kết quả và các fixture còn thiếu. Cách sinh suite: [fixture-generation.md](fixture-generation.md).

## Chạy case và batch

- **Chạy từng case:** chọn ITIN-001–025, xem request/expected/fixture, bấm **Chạy case**. Case luôn bắt đầu với store mới. **Chạy lượt tiếp theo** giữ conversation trong cùng case, hữu ích cho ITIN-025; **Reset case** xóa tiến độ case.
- **Chạy tất cả:** chạy tuần tự 25 case, hiển thị tiến độ/bảng kết quả; lỗi một case không ngăn case tiếp theo. Chọn **Xem lại kết quả đã chạy** để xem response, graph và bảng Expected/Actual của lần chạy đó, không gọi lại model.

Graph lấy topology từ `build_graph().get_graph()`, gồm 9 node và START/END. **Chạy từng case** hiển thị sơ đồ ngay dưới nút Run trước khi chạy và cập nhật sau mỗi node được stream. Khi hoàn tất, graph hiện trực tiếp phía trên bảng Expected/Actual, không cần mở tab. Node/cạnh đã chạy tô xanh; node báo lỗi như `classify: LLM_UNAVAILABLE` tô đỏ; đường lặp retry giữ đúng thứ tự events.

Chọn **Lượt hội thoại** và **State sau node** để xem lại graph tại bước tương ứng, mặc định là bước cuối; tab **State từng node** hiển thị đúng snapshot đã chọn. Trong **Mermaid từ LangGraph**, mã sơ đồ và file `.mmd` được sinh bằng `graph.get_graph().draw_mermaid()` theo skill mastering-langgraph; UI dùng Graphviz để tô đường thực thi trực tiếp. Tool calls lấy tại port gồm cả detail/destinations. Chạy batch độc lập với case/hội thoại đang mở. Custom query vẫn là chat nhiều lượt với catalog fixture chung, dùng graph hiện tại và LLM thật.

## Dữ liệu và cách chấm

- `evaluation_suite.json`: 25 case, mô tả nghiệp vụ và fixture; script sinh bổ sung execution trong từng case. Không sửa các expected nghiệp vụ để giúp agent PASS.
- `evaluation_execution.json`: sidecar cũ được hỗ trợ nếu chưa có execution trong toàn bộ suite; file này có thể chưa tồn tại trong checkout. Expected không được đưa vào model đang được đánh giá hoặc dùng làm model output. Fixture injection còn thiếu phải BLOCKED.
- `suite_fixtures.py`: cô lập fixture từng case, giữ dữ liệu sản phẩm. Search thêm `score=1.0` khi thiếu để đáp ứng `ScoredProduct` (metadata đánh giá, không đo chất lượng ranking). Lọc theo destination/taxonomy/giá/sao/snapshot/phân trang; không giả semantic ranking theo query. ProductDetail từ projection thiếu description dùng `""`, thiếu attributes dùng `{}`, ngày dùng null; không bổ sung policy/quyền lợi/giá. `list_destinations` chỉ trả khi có fixture inventory rõ ràng, không suy inventory từ Search rỗng.
- `assertions.py`: kiểm tra response theo OpenAPI, grounding bằng retrieval thực tế cùng lượt, số/ngày, giá và đơn vị, stay/thuộc tính, hoạt động/nghỉ, tool policy, continuation và các field intent/constraints. Grounding không có sản phẩm là NOT_APPLICABLE, không phải PASS.

| Kết quả | Ý nghĩa |
| --- | --- |
| PASS | Assertion tự động đạt và tiêu chí nghiệp vụ đã được người dùng review đạt |
| FAIL | Có tiêu chí sai; xem Expected/Actual và trace |
| ERROR | Runner/model/upstream/validation lỗi; xem runtime error và các assertion riêng |
| BLOCKED | Thiếu context/fixture/handler hoặc fixture trái contract; vẫn hiện kết quả phần đã chạy và số lỗi tự động |
| REVIEW | Assertion tự động đạt, còn tiêu chí nghiệp vụ cần đọc response/trace |
| PARTIAL | Chưa chạy hết lượt hội thoại |

Trong **Review tiêu chí nghiệp vụ**, chọn kết luận và lưu nhận xét. Review không ghi đè lỗi tự động, ERROR hoặc BLOCKED. Báo cáo ghi thời điểm review; batch được tính lại summary và lưu thành report mới có `reviewOfRunId`, không sửa report cũ. Một quyết định review áp dụng cho mọi dòng REVIEW của case.

`passRate` = PASS / (PASS + FAIL + ERROR + REVIEW); BLOCKED/PARTIAL nằm riêng và không tính PASS. `automatedCheckPassRate` chỉ đo assertion tự động PASS/FAIL, không gồm review, grounding không áp dụng hay assertion bị chặn. p95 đo thời gian case (ITIN-025 gồm hai lượt), không chứng minh SLA HTTP request/production.

Report mới lưu tại `src/evaluation/reports/eval-<timestamp>-<id>.json`, không ghi đè report cũ; có model, timestamp, suite fingerprint, checks, calls, node snapshots và response. UI có nút tải JSON; không tự đọc report cũ như kết quả mới. Nếu đổi suite/execution, reset session case để tránh dùng request cũ. Batch đã chạy giữ fingerprint trong report.

## Fixture còn thiếu

Các blocker được ghi ngay trong execution/UI. Đáng chú ý: case 9 thiếu inventory điểm đến; 12–13 thiếu conversation trước; 14–16 thiếu booking/lịch sử hợp lệ; case 14 còn có `because.event=booked` ngoài enum OpenAPI. Các case 3, 7, 18, 22, 23, 25 mô tả sản phẩm/thiếu giá/injection nhưng fixture rỗng. Giữ nguyên dữ liệu và báo thiếu, không tạo catalog/booking mới để giúp case đạt.

Bộ đánh giá này chứng minh hành vi graph với LLM và fixture được cung cấp, không chứng minh Search/Recommendation thật, booking thật hoặc tồn kho. Các module demo/scenario test cũ dùng interface trước graph 9 node không còn là runner của UI này.

## Kiểm tra local

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest src.evaluation.tests.test_evaluation_runner src.evaluation.tests.test_streamlit_custom_query -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python src/shared/contracts/tests/validate_contract.py
```

Test runner và Streamlit AppTest dùng LLM stub, graph thật và fixture; không gọi provider thật và không ghi report ra repository. AppTest không thay bằng chứng browser/model thật. Kiểm tra browser trong task triển khai đã dùng Chrome headless, UI thật và model stub; lần chạy provider thật cần báo riêng.
