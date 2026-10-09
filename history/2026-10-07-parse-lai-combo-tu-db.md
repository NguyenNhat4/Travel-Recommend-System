# Job cào parse lại thành phần mọi combo từ DB, không phụ thuộc combo có được cào lại

- Ngày: 2026-10-07
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành (chưa commit, chưa deploy)
- Phạm vi: data, docs

## Mục tiêu

Kiểm tra chỉ đọc ngày 07/10 (`history/2026-10-07-bench-embeddinggemma2-vs-e5-small.md`, nhánh `bench_search_recomSys`) thấy 9 combo
trên production (6 Công Viên Nước Hà Tĩnh, Grand World "trọn vẹn 03 khu", 2 combo "Phá Đảo 04 Khu" Cửa Hội) vẫn giữ
`catalog.combo_items` của bản parse cũ, thiếu dòng "Vé vào cửa <địa điểm>" mà bản sửa parser `bb41479` đã thêm. Nguyên nhân:
`load_into_db` chỉ parse lại combo có trong lượt cào, mà 9 combo này không được cào lại từ 01/10. Người dùng: không gỡ các combo
này, vấn đề là bị chặn cào nên dữ liệu đang thiếu; muốn sửa job để không phụ thuộc việc cào. Phục vụ FR-CAT-01, FR-SRC-01
(text tìm kiếm của combo gồm nhãn thành phần).

## File thay đổi

- `src/data_collection/fresh_catalog_db.py` — sửa:
  - Thêm `sync_combo_items`: parse lại `catalog.combo_items` của mọi combo trong `cdp.products` từ tên + mô tả đang lưu trong
    DB. Thành phần map sang sản phẩm của toàn catalog. Chỉ xoá + ghi lại combo có thành phần đổi.
  - Thêm `combo_items_from_db`, `_catalog_view`, `_canonical_ids`, `_comparable`: bỏ dòng `mergedInto` và vé Thương gia mô
    phỏng. Dòng duyệt tay quy ID theo `sourceRef`/`sameAs`/`mergedInto`. Dòng duyệt tay trỏ sản phẩm không có hoặc sai loại
    thì bỏ (`manualSkipped`), giữ dòng parse, không làm hỏng FK.
  - `maintain_catalog` (đầu mỗi lượt, chạy cả khi mọi nguồn lỗi) gọi `sync_combo_items` trên trạng thái sau cập nhật của
    chính transaction.
  - `load_into_db` bỏ ghi `combo_items` từ file của lượt, gọi `sync_combo_items` sau upsert. Vẫn chạy `parse_combos` trên file
    của lượt để lấy `priceBasis`/`nights`/`minPax` cho combo mới.
  - Thêm CLI xem trước chỉ đọc (`conn.read_only`):
    `python src/data_collection/fresh_catalog_db.py combo-items --database-url <dsn>`. Kết quả kèm `combosLabelsChanged`
    và nhãn trước/sau của combo đổi nhãn (nhãn đổi thì text index đổi, job index embed lại).
- `src/data_collection/seed/parse_combos.py` — sửa: tách `merge_manual` (ghép dòng duyệt tay) dùng chung cho CLI và job; hành
  vi CLI không đổi.
- `src/data_collection/pipeline_graph.py` — sửa: nhãn bước `maintain` thêm "parse lại thành phần combo".
- `src/data_collection/tests/test_fresh_catalog_job.py` — sửa/thêm: test maintain gọi `sync_combo_items` với trạng thái sau cập
  nhật; lớp `ComboItemsFromDbTests` (6 test: combo không có trong lượt cào nhận vé vào cửa map trên toàn catalog; kết quả trùng
  parser theo file trên cùng catalog; kiểu dữ liệu DB; dòng gộp / mô phỏng không làm đích; dòng duyệt tay theo alias và dòng
  sai loại; so sánh kiểu cột).
- `src/data_collection/tests/test_combo_items_sync_db.py` — thêm: 5 test với Postgres thật (cần `STREAM_TEST_ADMIN_URL`, DB tạm):
  nạp lần đầu, maintain sửa combo cũ rồi lần sau 0 ghi, nạp lô không có combo vẫn sửa, dry-run không ghi, dòng duyệt tay sai
  loại không hỏng FK.
- `src/data_collection/tests/test_simulated_business.py` — sửa: phần dọn của test DB xoá cả `combo_items` trỏ tới tuyến test
  (combo có sẵn trong DB giờ có thể map sang tuyến đó).
- `src/data_collection/README.md`, `docs/spec/MOCK_DATA_SPEC.md` §3 — sửa: mô tả parse lại combo từ DB và lệnh xem trước.
- `history/2026-10-07-parse-lai-combo-tu-db.md` — thêm entry này.

## Quyết định

- Không lệch PRD: `docs/spec/DATABASE_SCHEMA.md` ghi `catalog` "dựng lại được từ cdp.products bất kỳ lúc nào" và `parse_combos`
  "chạy lại được"; thay đổi chỉ làm job đúng điều đó. Không đổi DDL, contract.
- Parse từ text trong DB, không từ text lượt cào: upsert giữ tên/mô tả cũ cho mọi loại trừ vé máy bay, và job index embed text
  trong DB. Hai đường (maintain, nạp) cùng đọc DB nên không lật qua lật lại giữa hai bản parse.
- Dòng duyệt tay chỉ lấy từ file của snapshot mặc định (như seed và `load_into_db` trước đây), không giữ dòng `manual` chỉ có
  trong DB.
- `priceBasis`/`nights`/`minPax` của combo đã có trong DB vẫn không cập nhật (như trước: `price_attributes` giữ attributes cũ);
  ngoài phạm vi.
- Bước maintain chỉ chạy khi có lượt được chọn (lượt full hằng ngày, hoặc `fresh-run index`), không chạy ở tick rảnh.

## Kiểm tra

- Trước khi sửa (`vsf2`, `PYTHONPATH=src:src/data_collection`): `pytest src/data_collection/tests` 509 passed, 21 skipped.
- Sau khi sửa: 515 passed, 26 skipped.
- Test DB thật trên Postgres local `:55433`:
  - `STREAM_TEST_ADMIN_URL`: `test_combo_items_sync_db.py` 5/5 passed.
  - `test_stream_feed_db.py`: 1 passed, 1 failed (`test_rows_loaded_separately_then_merged_leave_one_visible`). Fail cả trên
    HEAD `728e01b` trong worktree sạch: lỗi có sẵn, khách sạn không phòng bị ẩn theo quy tắc FR-CAT-02 ngày 06/10.
  - `SIMULATED_TEST_DATABASE_URL` (bản sao `vota_simbiz_test_*` của `vota`): `test_simulated_business.py` 10/10 passed sau khi
    sửa phần dọn. Trước khi sửa phần dọn: 1 lỗi FK ở bước dọn; HEAD qua 10/10.
- Xem trước chỉ đọc trên DB local:
  - `vota`: 133 combo, 48 đổi, 0 dòng duyệt tay bị bỏ, 1,7 s.
  - `vota_append_eval_20261005` (172 combo, chưa có `combo_items`): 172 đổi.
- 64 dòng duyệt tay: 0 dòng rơi vào position mà parser hiện sinh nhãn khác.
- Chạy thật trên bản sao `vota` (đã xoá sau khi kiểm):
  - `maintain_catalog` lần 1: 48 combo đổi, 98 dòng ghi, 3,5 s. 9 combo nêu ở Mục tiêu nhận "Vé vào cửa …".
  - Lần 2: 0 đổi.
  - `load_into_db` với lô chỉ 3 điểm tham quan (không combo): 0 đổi, combo vẫn đúng.
- So text index của backend (`PostgresCatalogReader`) giữa `vota` và bản sao: 3.183 unit, đúng 48 text đổi, toàn combo.

- Xem trước chỉ đọc trên DB VM (người dùng chạy qua tunnel, 07/10, bản chưa có thông tin nhãn): 183 combo, 112 sẽ ghi lại,
  0 dòng duyệt tay bị bỏ.
  - Theo số dòng: 11 combo thêm dòng, 11 bớt dòng, 90 giữ nguyên số dòng.
  - Có đủ 9 combo nêu ở Mục tiêu, cộng 3 combo "WONDER15 Phá Đảo 04 Khu Cửa Hội".
  - 39 combo là bay + ở của Trip (nguồn bị robots cấm cào nên không bao giờ được parse lại).

## Còn lại / rủi ro

- Chưa commit, chưa deploy. Lượt đầu sau deploy sẽ ghi lại `combo_items` của mọi combo có bản parse khác. Job index sau đó embed
  lại các combo này. Nên chạy lệnh xem trước chỉ đọc trên DB VM trước khi deploy để biết số combo đổi.
- Lượt `full` trên VM thất bại liên tục từ 29/09. Lượt 07/10 dừng vì `stream.db.batch vượt hạn 1800s`: lô bắt đầu 02:14 không
  xong, log im từ 02:38. Chưa điều tra.
- `release-mvp-v2` có commit mới (`d6b3663`, khoá DB cho crawler) chạm `fresh_catalog.py`; nhánh này chưa merge. Thay đổi ở đây
  không sửa `fresh_catalog.py`.
- Combo "Công viên nước + Vòng Quay Thời Gian" (Hà Tĩnh) không nhận "Vé vào cửa" vì parser hiện coi "Vòng quay" là attraction;
  hành vi parser, không đổi ở đây.
