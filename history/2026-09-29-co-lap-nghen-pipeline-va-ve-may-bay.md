# Cô lập nghẽn pipeline và triển khai biến thể vé đặt được

- Ngày: 2026-09-29
- Tác giả: Đăng Khôi / Codex
- Nhánh: test/newcrawl
- Trạng thái: dang dở
- Phạm vi: data | backend | frontend | contract | docs

## Mục tiêu

Kiểm tra điểm có thể chặn toàn bộ luồng và khắc phục theo mô hình task/dependency/retry/checkpoint của Airflow; bổ sung vé phổ thông/thương gia và khứ hồi đặt được với ít thay đổi. Catalog 11.387 dòng đã ở DB VM phải được giữ, không reset và không cào lại toàn bộ chỉ để thêm vé.

## File thay đổi

- `docs/plan/2026-09-29-on-dinh-pipeline-va-ve-may-bay.md` — thêm: phạm vi đã làm, giới hạn còn lại, đề xuất fareClasses cho FE.
- `docs/prd/data-model.md` — sửa: ngày cố định, hạng vé, khứ hồi và giá một khách theo đề xuất đã chốt.
- `docs/prd/requirements.md` — sửa: áp dụng yêu cầu biến thể vé đặt được.
- `docs/prd/update-archive/2026-09-29-ve-khu-hoi-dat-duoc.md` — thêm: áp dụng và chuyển đề xuất đã chốt từ docs/prd/update/ sang update-archive/.
- `docs/spec/data-collection/schema.md` — sửa: bổ sung từ vựng thuộc tính vé và quy tắc giá.
- `src/backend/app/application/booking/views.py` — sửa: trả attributes của vé trong giỏ/đơn bằng contract optional đã có.
- `src/backend/tests/unit/application/booking/test_flight_booking.py` — thêm: kiểm thử hành vi nguồn lỗi/timeout/resume hoặc lựa chọn, giá và đặt vé tương ứng.
- `src/data_collection/README.md` — sửa: hướng dẫn isolation, timeout, resume, streaming và báo cáo kiểm DB tạm.
- `src/data_collection/collectors/booking_flights.py` — sửa: đối chiếu hạng hiển thị trong từng chặng với yêu cầu tìm kiếm.
- `src/data_collection/fresh_catalog.py` — sửa: cô lập lỗi nguồn, giới hạn retry, trì hoãn index lỗi, giữ lỗi khi resume, quality gate từng nguồn và supervisor CLI.
- `src/data_collection/fresh_catalog_db.py` — sửa: timeout kết nối/khóa/SQL và cập nhật thuộc tính báo giá ngày cố định.
- `src/data_collection/fresh_settings.py` — sửa: thêm run.maxHours và timeout.processing.
- `src/data_collection/normalise.py` — sửa: khứ hồi, biến thể Booking theo ngày/hạng, checkpoint lỗi và ngưỡng theo nguồn.
- `src/data_collection/normalise_stream.py` — sửa: fingerprint mapperVersion đồng bộ checkpoint.
- `src/data_collection/pipeline_errors.py` — sửa: phân loại lỗi khóa/timeout PostgreSQL để retry có giới hạn.
- `src/data_collection/pipeline_runtime.py` — thêm: supervisor tiến trình, cưỡng chế dừng và giải phóng khóa có thứ tự.
- `src/data_collection/seed/load_products.py` — sửa: giữ nguyên ngày hai chặng, không phục hồi báo giá hết hạn bằng ngày demo.
- `src/data_collection/stream_feed.py` — sửa: chỉ đánh dấu bản nháp đã gộp sau khi thao tác thành công.
- `src/data_collection/tests/fixtures/normalise_sample/expected_products.jsonl` — sửa: golden thêm 40 khứ hồi; 54 dòng cũ chỉ khác tripType oneWay cho chuyến.
- `src/data_collection/tests/test_booking_flights.py` — sửa: kiểm thử hành vi nguồn lỗi/timeout/resume hoặc lựa chọn, giá và đặt vé tương ứng.
- `src/data_collection/tests/test_flight_variants.py` — thêm: kiểm thử hành vi nguồn lỗi/timeout/resume hoặc lựa chọn, giá và đặt vé tương ứng.
- `src/data_collection/tests/test_fresh_catalog_job.py` — sửa: kiểm thử hành vi nguồn lỗi/timeout/resume hoặc lựa chọn, giá và đặt vé tương ứng.
- `src/data_collection/tests/test_live_monitor.py` — sửa: kiểm thử hành vi nguồn lỗi/timeout/resume hoặc lựa chọn, giá và đặt vé tương ứng.
- `src/data_collection/tests/test_pipeline_errors.py` — sửa: kiểm thử hành vi nguồn lỗi/timeout/resume hoặc lựa chọn, giá và đặt vé tương ứng.
- `src/data_collection/tests/test_pipeline_graph.py` — sửa: kiểm thử hành vi nguồn lỗi/timeout/resume hoặc lựa chọn, giá và đặt vé tương ứng.
- `src/data_collection/tests/test_pipeline_hardening.py` — thêm: kiểm thử hành vi nguồn lỗi/timeout/resume hoặc lựa chọn, giá và đặt vé tương ứng.
- `src/data_collection/tests/test_timeouts_recrawl.py` — sửa: kiểm thử hành vi nguồn lỗi/timeout/resume hoặc lựa chọn, giá và đặt vé tương ứng.
- `src/frontend/src/components/cart/CartView.tsx` — sửa: hiển thị thông tin vé đã chọn.
- `src/frontend/src/components/checkout/CheckoutView.tsx` — sửa: hiển thị vé trong tóm tắt thanh toán.
- `src/frontend/src/components/common/FlightSummary.tsx` — thêm: hiển thị hạng, chặng đi/về và giá tổng.
- `src/frontend/src/components/detail/ProductDetailView.tsx` — sửa: hiển thị từng lựa chọn chuyến và hạng vé.
- `src/frontend/src/types/api.gen.ts` — sửa: sinh lại type từ OpenAPI.
- `src/frontend/tests/unit/flight-summary.test.tsx` — thêm: kiểm thử hành vi nguồn lỗi/timeout/resume hoặc lựa chọn, giá và đặt vé tương ứng.
- `src/shared/contracts/schemas/catalog.yaml` — sửa: thêm các thuộc tính vé optional, giữ level và request giỏ.
- `docs/prd/update/2026-09-29-ve-khu-hoi-dat-duoc.md` — đổi tên sang update-archive sau khi áp dụng PRD.

Danh sách đối chiếu git status và hash `/tmp/pipeline-hardening-baseline.json`, vì working tree đã có nhiều thay đổi CP/L/P/monitor/Cohere từ trước. Không quy các thay đổi có sẵn đó cho task này. Bản trước sửa nằm tại `/tmp/pipeline-before-implementation/` (file tạm, không bảo đảm tồn tại qua khởi động lại).

## Quyết định

- Người dùng đã chốt đề xuất vé trong phiên ("ok đã chốt"). PRD được cập nhật trước source; đề xuất đã chuyển sang update-archive. FR-CAT-01/03, FR-SRC-02, luồng FR-BKG-05.
- Giữ 13 trường, level flight, ID cũ và request productId/usingDate/quantity. Mỗi báo giá hành trình/ngày/hạng là ID riêng. Không suy hạng, không nhân giá economy thành business, không chia tổng nhóm thành giá một khách.
- Lỗi một nguồn không bỏ các nguồn độc lập. Catalog rỗng/toàn bộ không hợp lệ vẫn chặn nạp; DB hỏng thì không thể hoàn tất nạp. Index lỗi không rollback dữ liệu đã commit.
- CLI có hạn giờ toàn lượt 18h, xử lý 30 phút/bước; DB connect 10s, lock 5s, statement 5min, idle transaction 1min. Cưỡng chế dừng có thể kết thúc cả worker; dữ liệu đã commit/checkpoint dùng để resume. Gọi run_job trực tiếp không có supervisor.
- Streaming vẫn mặc định tắt theo quyết định trước; không tự bật trên VM. Lần gộp cuối còn chờ nguồn chậm cho tới khi xong/timeout. Daily chỉ có Trip khách sạn nên lỗi Trip không có nguồn thay thế.
- User cung cấp fareClasses từ FE và hỏi phương án tốt nhất. Đề xuất thêm productId vào từng phần tử, không thêm fareClassCode vào request giỏ. Chưa thêm fareClasses vào API; hành lý/suất ăn/đổi vé cần dữ liệu nguồn và nullable, soldOut cần tách khỏi quote hết hạn.
- Kiểm thử phát hiện phản hồi giỏ/đơn thiếu attributes: sửa views trả thuộc tính vé qua trường optional đã có. Không thay DDL hay logic thanh toán.
- Không commit, không nạp/reset DB VM, không index lên dịch vụ ngoài trong task. Lượt crawl BUSINESS nhỏ trả 0 offers, không được dùng như dữ liệu mới.

## Kiểm tra

- Môi trường: `/home/dangkhoi/miniconda3/envs/vsf2/bin/python`.
- `PYTHONPATH=src:src/data_collection .../python -m pytest src/data_collection/tests -q -rs`, với STREAM_TEST_ADMIN_URL trỏ Postgres local: **528 passed, 3 skipped**, log `/tmp/pipeline-hardening-final.log`. DB integration tạo/xóa riêng database tạm.
- Ba skip: test_api_sources/test_pipeline_demo thiếu raw cục bộ; test_daily cần CATALOG_ONLY_TEST_DATABASE_URL của DB dùng một lần. Không tính skip là pass.
- Bao gồm fault injection: nguồn parser lỗi, tụt số bản ghi từng nguồn, dependency bị bỏ riêng, resume vẫn partial, loại coverage Trip lỗi, worker/con giữ khóa rồi timeout và giải phóng khóa sau khi ghi trạng thái.
- `.../python -m pytest src/backend/tests/unit/application/booking/test_flight_booking.py src/backend/tests/unit/application/booking/test_booking_flow.py src/backend/tests/unit/domain/booking/test_booking_domain.py src/backend/tests/contract/test_booking_contract.py -q`: **60 passed**; test gateway giả, không thanh toán thật.
- `node node_modules/vitest/vitest.mjs run tests/unit/flight-summary.test.tsx tests/unit/bookingService.test.ts tests/unit/catalogService.test.ts`: **13 passed**. `tsc --noEmit`: PASS.
- `PYTHONDONTWRITEBYTECODE=1 .../python src/shared/contracts/tests/validate_contract.py`: PASS (88 schemas, local refs, 62 fixtures và các kiểm tra CDP).
- `/tmp/verify-flight-catalog.py`: snapshot 11.387 sản phẩm + một vé fixture, seed 2.000 profiles / 7.145 events / 307 combo items vào database tạm local; `db/verify.sql` **18/18 PASS**. Giữ đủ 11.387 ID cũ; vé khứ hồi is_bookable, from=to ngày đi, giá tổng và ngày về đúng. Xác minh timeout DB 5s/5min/1min. Database tạm đã xóa, không tải vé fixture lên VM.
- Golden sample: 54 dòng cũ giữ nội dung, trừ tripType oneWay trên chuyến; thêm 40 dòng khứ hồi. Đây là fixture, không phải báo giá hiện tại.
- Lượt cào thử Booking BUSINESS SGN–HAN 2026-10-10: timeout khi chờ flight card, 1 failed / 0 offers. Log `/tmp/flight-business-sample.log`.
- `git diff --check`: PASS.
- Lượt chạy đầu khi tiếp tục thiếu PYTHONPATH nên collection lỗi; đã sửa lệnh và chạy lại đầy đủ. Test booking ban đầu phát hiện thiếu attributes, đã sửa source và chạy lại pass. Lệnh cuối phiên trước bị usage-limit ở bước auto-review nên chưa chạy; các kiểm tra trên là kết quả thực sau khi tiếp tục.

## Còn lại / rủi ro

- Báo giá thương gia mới và bằng chứng giá khứ hồi một người lớn chưa có đủ; không tự tạo dữ liệu demo thay thế. Raw Trip lịch sử có ngày/hạn giá cũ, thiếu hạng.
- Thống nhất fareClasses với FE; chưa có enum mã hạng FE/cách phân biệt soldOut và báo giá hết hạn.
- Chưa kiểm tay bằng trình duyệt hay chạy smoke trên VM. Cần một lượt nhỏ đúng môi trường để điều chỉnh timeout/tài nguyên và kiểm streaming trước khi triển khai rộng.
- Chưa sinh/nạp bản catalog tăng thêm lên VM. Dữ liệu và giỏ/đơn trên VM chưa thay đổi.
- Tài liệu kế hoạch: docs/plan/2026-09-29-on-dinh-pipeline-va-ve-may-bay.md. Task chưa đạt hoàn thành end-to-end vì còn dữ liệu nguồn và xác minh môi trường thực tế.
