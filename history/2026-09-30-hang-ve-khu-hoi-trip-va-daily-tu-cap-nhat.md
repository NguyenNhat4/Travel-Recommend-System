# Hạng vé khứ hồi từ trip.com, snapshot 2026-09-30, và job daily tự cập nhật khi push

- Ngày: 2026-09-30
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: data, docs, deploy (Dockerfile)

## Mục tiêu

Người yêu cầu:
- "muốn có hạng vé để team FE lấy lên nữa, data sài được là được, và thêm vào phần crawl cào luôn hạng vé";
- chọn "Làm luôn" cho crawl; chọn "Tìm nguồn hãng bay" cho hạng thương gia;
- "khi tôi push lên lại thì team deploy không phải sửa gì, nó tự động pass và tự cập nhật"; CI/CD giữ như trên git.

Phục vụ FR-CAT-01, FR-CAT-03. Hạng vé lấy từ bằng chứng của nguồn (FR-CAT-01: "Hạng vé có bằng chứng"), không suy hạng: không
lệch PRD.

## File thay đổi

- `src/data_collection/collectors/trip.py` — sửa:
  - `extract` lưu thêm `rtCards` (ngày đi / về, hạng từng chặng của thẻ khứ hồi trên trang tuyến);
  - `parse_route` gọi `apply_rt_cabins`: thẻ phải khớp cặp chặng JSON-LD (cùng số lượng, thứ tự, ngày) mới gắn `cabinClass`,
    lệch thì cả trang giữ chưa biết;
  - thẻ trống / lẫn hạng thì cặp đó giữ chưa biết; chuyến nối chặng nhận hạng khi mọi chặng con cùng hạng;
  - khối gom nhiều thẻ bị bỏ.
- `src/data_collection/seed/load_products.py`, `src/data_collection/seed/__main__.py` — sửa: thêm cờ `--real-flight-dates` (chỉ
  với `--catalog-only`). Vé báo giá ngày cố định giữ ngày thật và khoá vé hết hạn báo giá, như `apply_window` của job mới.
- `src/data_collection/daily.py` — sửa: bước nạp gọi `seed --catalog-only --real-flight-dates`.
  - Sửa hồi quy của commit `a894f76` (29/09): seed dời ngày vé mà `daily.py` (dữ liệu thật) cũng đi qua seed.
- `Dockerfile.daily` — sửa: cài thêm `argon2-cffi` (ràng buộc phiên bản lấy từ `src/backend/requirements.txt`).
  - `seed/__main__` import `seed_histories`, file này import argon2.
  - Image daily build từ nhánh release thiếu thư viện này nên `python -m data_collection.seed` lỗi (kiểm bằng image build local).
- `src/data_collection/snapshots/2026-09-30/` — thêm:
  - snapshot `2026-09-23` + vé trip.com cào ngày 30/09/2026 (lượt local `full-20260930T032030Z-14441`, chỉ `sources.tripFlights`,
    `@deep`);
  - 11.718 sản phẩm: thay 110 dòng cùng `sourceRef`, thêm 331;
  - 290 vé khứ hồi, trong đó 268 có `cabinClass: ECONOMY`.
- `Makefile`, `src/data_collection/seed/config.py` — sửa: snapshot mặc định → `2026-09-30`.
- `src/data_collection/snapshots/README.md`, `src/data_collection/README.md` — sửa: mô tả snapshot mặc định. Khối seed-report do
  seed ghi lại.
- `docs/spec/MOCK_DATA_SPEC.md` — sửa: cây thư mục trỏ `snapshots/2026-09-30/`.
- `docs/guide/hien-thi-hang-ve-may-bay.md` — sửa: 268 vé `ECO` "Phổ thông", phần còn lại "Giá rẻ nhất", hạn báo giá 01/10.
- `docs/guide/trien-khai-job-cao-du-lieu.md` — sửa:
  - thêm mục "Push là tự cập nhật (job cũ, không cần sửa CI/CD)";
  - mục nạp staging dùng snapshot `2026-09-30`.
- `src/data_collection/tests/test_trip_routes.py` — thêm 5 test hạng vé khứ hồi.
- `src/data_collection/tests/test_flight_variants.py` — thêm 2 test:
  - `convert(real_flight_dates=True)`;
  - cờ CLI tới loader, và `daily.py` truyền cờ.
- `src/data_collection/tests/test_fresh_monitor.py` — sửa: lệnh `monitor` giờ có `--host` (commit `0a9be80` hôm qua làm test này
  fail, bị sót vì chỉ chạy `test_monitor_public.py`); thêm kiểm chế độ public.
- `history/2026-09-30-hang-ve-khu-hoi-trip-va-daily-tu-cap-nhat.md` — thêm: entry này.

## Quyết định

- Nguồn hạng vé: thẻ khứ hồi trên trang tuyến trip.com, đúng trang collector đã cào; `robots.txt` cho phép.
  - JSON-LD không có hạng.
  - Trang tìm kiếm có tham số hạng (`showfarefirst`) bị `robots.txt` cấm, nên không dùng.
- Không đổi CI/CD (người yêu cầu). Job cũ `daily.py` dùng chung collector, normalise, seed, nên push là đủ.
- Hạng thương gia: chưa có (xem "Còn lại").

## Kiểm tra

- Trang thật HAN–SGN: 10/10 vé khứ hồi `ECONOMY`.
- Toàn bộ raw của lượt 30/09: 598/660 cặp chặng có hạng.
- Lượt cào lại: 268/290 vé khứ hồi `ECONOMY`.
- Kiểm test bắt được lỗi (tắt từng hành vi rồi khôi phục, `cmp` sạch): mỗi lần đều ≥ 1 test fail. Các hành vi đã tắt:
  - không gắn hạng;
  - bỏ kiểm ngày về;
  - không lọc khối gom;
  - bỏ kiểm số thẻ;
  - nhận thẻ lẫn hạng;
  - nhận thẻ trống hạng;
  - lệch ngày chỉ bỏ một cặp.
- Một lượt cào chạy song song lúc đang tắt thử test đã bị dừng và cào lại sạch. Kết quả dùng cho snapshot là lượt chạy sau cùng.
- `data_collection` `pytest tests`: 423 passed, 3 skipped.
- Bước CI crawler chạy local:
  - `compileall src/data_collection`: ok;
  - `bash -n` các script: ok;
  - `scripts/tests/test-install-vota-cron.sh`: passed;
  - `docker build -f Dockerfile.daily`: exit 0.
- Trong image daily vừa build:
  - collector đọc 10/10 `ECONOMY`;
  - `seed --catalog-only --real-flight-dates --generate-only` exit 0, giữ ngày thật;
  - `import src.backend.jobs.embed_products` ok.
  - Trước khi thêm argon2: seed lỗi `ModuleNotFoundError: argon2`.
- Seed đầy đủ snapshot `2026-09-30` vào database nháp (đã xoá), as_of 2026-09-30:
  - 11.718 sản phẩm; 290/290 vé khứ hồi đặt được, 268 `ECONOMY`;
  - `db/verify.sql` 0 FAIL, `db/verify_insider.sql` 0 FAIL.

## Còn lại / rủi ro

- Hạng thương gia: Vietnam Airlines có trang tuyến công khai (`robots.txt`: `Disallow:` rỗng).
  - Trang có thẻ giá theo hạng kèm ngày khởi hành ("Thương gia, Khởi hành 05/12/2026, từ 3.907.181 VND") và bảng giá tham khảo
    theo hạng.
  - Thẻ không có số hiệu chuyến / giờ bay, nên chưa khớp mô hình `level: flight` hiện tại.
  - Cần quyết định cách mô hình hoá (có thể lệch PRD); chưa code.
- Giờ bay: thẻ trip.com hiển thị giờ lệch +1 giờ so với `departureTime` JSON-LD (vd. 22:25 so với 14:25Z = 21:25 giờ VN). Chưa rõ
  bên nào đúng; chưa sửa.
- Chưa commit.
