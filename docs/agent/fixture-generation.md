# Sinh fixture và expected bằng LLM

Cách sinh `evaluation_suite.json` bằng script. Cách chạy và chấm kết quả nằm ở [evaluation-suite.md](evaluation-suite.md).

Chạy từ repo root, dùng provider/model/key trong `.env` như backend:

```bash
.venv/bin/python -m src.evaluation.agent.generate_fixtures
```

Script loop tuần tự từng scenario, gọi LLM chọn ID catalog và sinh request/route/tool mong đợi.
Python dựng Search/Recommendation/Detail/inventory từ `shared/mocks/itinerary-agent/products.json`,
validate bằng OpenAPI hiện hành và validate arguments tool. Không để model viết giá hoặc tạo sản phẩm mới.
Sau khi tất cả case hợp lệ, ghi `evaluation_suite.json`, giữ bản cũ tại `evaluation_suite.json.bak`.
Nếu đã có backup, script yêu cầu chọn output khác hoặc tự lưu trữ backup trước; không ghi đè backup.
Case lỗi sau 3 lần thử khiến cả lần sinh dừng và suite gốc giữ nguyên. Timeout mặc định 90 giây/call.
Mỗi attempt hiện bước lỗi `provider`, `parse` hoặc `validation`. Provider chỉ hiện loại exception/HTTP status;
validation hiện đường dẫn/rule hoặc nguyên nhân đã kiểm soát, không in key/payload. Retry nhận nguyên nhân
để sửa proposal. Parser hỗ trợ JSON thuần và một khối Markdown JSON hoàn chỉnh.

```bash
# Sinh riêng vài case để kiểm tra prompt, ghi ra file riêng
.venv/bin/python -m src.evaluation.agent.generate_fixtures --ids ITIN-001 ITIN-005 --output /tmp/suite-preview.json
# Đổi model nếu cần
.venv/bin/python -m src.evaluation.agent.generate_fixtures --model gpt-4o-mini
```

`execution` được đặt trong mỗi scenario: `turns`, `checks`, `blockers`, `reviewCriteria`.
Runner ưu tiên execution trong suite khi mọi case đều có; vẫn hỗ trợ sidecar cũ nếu tồn tại.
Sinh toàn bộ suite mặc định trước khi chạy UI để không thiếu execution.
Route chấm qua `state.route` từng lượt; tool chấm calls thực tế tại port, khớp tên/số lần/arguments,
không phụ thuộc thứ tự chạy song song. Arguments runtime có thể thêm default; các field expected phải khớp chính xác,
kể cả `query`. Người review có thể bỏ `query` trong expected tool check nếu muốn chỉ chấm bộ lọc thay vì câu chữ.

Expected do LLM đề xuất vẫn cần review với mô tả case, được đánh dấu `generation.oracleReviewed=false`.
Validator chứng minh hình dạng contract và ID có nguồn, không chứng minh expected nghiệp vụ đúng.
Thiếu booking/lịch sử/điều kiện nguồn hoặc fixture injection phải giữ BLOCKED; recommendation sinh mới chỉ popular + because rỗng.
Inventory là toàn bộ catalog sample offline, không phải danh sách điểm đến của service thật.
Script gửi mô tả case và catalog sample đến provider đã cấu hình và có chi phí LLM.
Lệnh sinh không chạy agent; sau đó dùng UI để chạy graph và kiểm tra Expected/Actual.
