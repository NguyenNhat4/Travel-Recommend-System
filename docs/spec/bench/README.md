# Bước 0 trước khi chia việc cho 2 máy: hợp đồng dữ liệu gold

Phục vụ: **FR-SRC-01..04**, **AC-SRC-01** (`docs/prd/requirements.md`) và test-plan §2.5 (`docs/prd/test-plan.md`).

> **Trạng thái 25/09:** chưa chia 2 máy. Bộ này đã commit trên `bench/embed-search` (`38ad63c`), không phải main, vì main chưa có `src/evaluation/search_bench/`. Việc của máy 1 làm luôn trên nhánh này; bước 4–5 bên dưới áp dụng khi thật sự chia máy (tách nhánh từ `bench/embed-search`).

Bộ file này là phần chung mà cả hai máy cùng dựa vào. Commit bộ này lên main trước, sau đó mỗi máy mới tách nhánh riêng.

```text
src/evaluation/search_bench/gold_schema.py                 hợp đồng: định dạng pool, nhãn, merged, meta, gold.jsonl
src/evaluation/search_bench/tests/test_gold_fixtures.py    11 test kiểm hợp đồng + fixture
src/evaluation/search_bench/tests/fixtures/gold_small/     dữ liệu giả 7 câu, kèm đáp án (README.md trong thư mục)
docs/spec/bench/prompts/may1-gold-cli.md                   việc cho máy 1: guide + pool/split + kappa/merge/import/check
docs/spec/bench/prompts/may2-label-app.md                  việc cho máy 2: app Streamlit gán 0/1/2
```

## Áp dụng

1. Chép vào repo, giữ nguyên đường dẫn. Nếu repo đặt code ở chỗ khác, đổi đường dẫn trong hai file prompt và dòng `sys.path` của `make_fixtures.py`.
   - Bộ này **không kèm `__init__.py`**, để không ghi đè file sẵn có của repo.
   - Nếu `src/evaluation/search_bench/tests/` chưa có `__init__.py` thì vẫn chạy được theo kiểu namespace package.
2. Cài thư viện: `pip install "pydantic>=2" pytest`.
3. Chạy kiểm tra, phải ra `11 passed`:
   ```bash
   cd src && python -m pytest evaluation/search_bench/tests/test_gold_fixtures.py -q
   ```
4. Commit lên main với message `gold: schema + fixtures (bước 0)`. Hai máy cùng pull.
5. Máy 1 tạo nhánh `feat/gold-cli`, máy 2 tạo nhánh `feat/label-app`. Mỗi máy đưa file prompt tương ứng cho Claude Code.

## Lưu ý khi hai máy dùng git khác hệ điều hành

Sha của file pool được ghi vào `pool_meta.json` và vào từng dòng nhãn. Git trên Windows với `core.autocrlf=true` sẽ đổi ký tự xuống dòng khi checkout, làm sha lệch: test đỏ và app chặn không cho gán. Trước khi commit bước 0, thêm các dòng sau vào `.gitattributes` ở gốc repo để git giữ nguyên từng byte (đã thêm ngày 25/09). Pattern có `/` được neo ở gốc repo, nên phải ghi đủ đường dẫn tới `src/evaluation/search_bench/gold/`:

```text
src/evaluation/search_bench/gold/** -text
src/evaluation/search_bench/tests/fixtures/gold_small/** -text
```

Mở file pool bằng Excel rồi lưu lại cũng làm đổi sha. App sẽ chặn trong trường hợp này; đó là hành vi đúng, vì pool không được sửa tay.

## Đã chốt trong bộ này

- **Có `expected_children`** cho slice parent_child. App cho chọn hạng phòng khi gán nhãn 2; import ghi vào `gold.jsonl`.
- **`filter` tách thành hai phần:** điều kiện ở cấp parent (`filter_json`) và điều kiện giá, sức chứa, ngày ở cấp room/flight (`child_filter_json`).
- **Pool không có cột giá.** Người gán không thấy thứ hạng hay nguồn (dense/BM25) của ứng viên.
- **Luật destination (đề xuất, gold-guide phải chốt):** query có nêu destination thì sai destination → 0, kể cả đúng loại. Fixture đang gán theo luật này. Luật này **mâu thuẫn** với câu "đúng loại hoặc đúng nơi → 1" trong spec Part 5 cũ.

## Còn phải làm tay trước khi gán thật

- [ ] Soát 42 câu do `--fill` tự lấp; sửa 3 góp ý (`c0241` còn chữ "không ghi nhận"; `c0503`, `c0531` ghi "0.5 triệu"). — *28/09: đã sửa 3 góp ý (NEEDS_EDIT trong `gold/overrides.tsv`, `drafts.txt` sửa theo); còn soát 42 câu `--fill` — cần `bench_out/search/labels/labels.jsonl` của máy đã chạy app soát để `gold drafts --fill --dry-run` in danh sách* — *28/09 chiều: luật mới không tự lấp nữa — 42 câu này chỉ còn là gợi ý ⭐ trong app (Bộ câu đã chọn → Thêm câu chưa chọn); chỉ vào bộ nếu người soát chọn*
- [ ] Thêm 2 câu dự phòng cho mỗi slice đang đúng bằng 10 câu: `amenity_multi`, `amenity_negation`, `amenity_offtaxonomy`, `cross_vertical`, `out_of_catalog`. Không có dư thì chỉ một câu thiếu nhãn 2 là `gold check` báo đỏ. — *28/09: app có chế độ "Bổ sung câu hỏi" (mỗi slice một box, kiểm grounding) và "Tra cứu catalog"; 4 slice đầu hết ý định dự phòng trong `drafts_raw.tsv`, cần soạn mới; câu dự phòng chỉ vào `drafts.txt` khi nâng quota `gold.slices` (chờ chốt 210 hay giữ 200)* — *28/09 chiều: không còn cần — mỗi slice chỉ cần ≥ 3 câu; hiện chỉ `out_of_catalog` (2 câu) còn thiếu*
- [x] Đóng băng `drafts.txt`, rồi chạy pool thật trên máy có Weaviate (việc 0 và mục "Sau khi xong" trong prompt máy 1). — *29/09: `drafts.txt` đã chốt 132 câu (mọi slice ≥ 3); `c0276` chép sang `overrides.tsv` để map được `case_id`; split viết lại cho 132 câu. Còn chạy `sb gold pool` + `sb gold split` khi có khoá Cohere còn lượt (11 câu cần embed truy vấn)* — *29/09: đã chạy — `gold/pool.csv` (132 câu / 3.359 dòng), `pool_A.csv` (78 câu / 1.999 cặp), `pool_B.csv` (79 câu / 2.000 cặp), `pool_meta.json`; hai người mở app, chế độ "Gán nhãn 0/1/2"*
- [ ] Mốc 1: guide xong, hai người đọc và thống nhất các ví dụ khó.
- [ ] Mốc 2: app xuất nhãn trên fixture → `kappa` / `merge` của máy 1 chạy ra đúng đáp án.

## Gán nhãn chung qua một link (29/09)

Hai người ở hai mạng khác nhau gán trên **một app chạy ở máy giữ `gold/`**. Nhãn ghi thẳng vào `gold/labels/labels_A.csv` và `labels_B.csv` của máy đó, rồi chỉ máy đó commit.

- **Chế độ dùng chung** (`LABELING_SHARED=1`):
  - mỗi người một mã truy cập riêng (`LABELING_CODE_A`, `LABELING_CODE_B`, ≥ 12 ký tự, khác nhau); nhập mã nào thì bị khoá vào đúng pool / file nhãn của người đó;
  - chỉ còn chế độ gán nhãn: không chọn được người kia, không nhập đường dẫn, không có nút fixture, không có các chế độ sửa `gold/`, không hiện đường dẫn máy chạy app;
  - thiếu mã hoặc mã yếu thì app không mở gì.
- **Chạy app dùng chung:** từ `src/`, chạy `..\.venv-sbench\Scripts\python -m evaluation.search_bench gold share` (thêm `$env:PYTHONUTF8="1"` trên PowerShell). Lệnh này:
  - lần đầu tạo mã truy cập ở `bench_out/search/label_share/codes.env` (thư mục đã gitignore; mỗi mã 22 ký tự ngẫu nhiên, không in ra màn hình); gửi mã riêng cho từng người, không dán vào git hay kênh chung;
  - ghi launcher ra `<ổ đĩa của repo>\vota-label-share\app.py`, **ngoài repo git**. Chạy thẳng trong repo thì Streamlit gửi cho mọi trình duyệt mở link, kể cả trước khi nhập mã, tên repo GitHub, nhánh, danh sách file chưa commit và đường dẫn script;
  - chạy Streamlit chỉ trên `127.0.0.1:8502`, ẩn traceback (`client.showErrorDetails=type`) và thanh công cụ dev; tiến trình không mang biến môi trường bí mật (`*KEY*`, `*TOKEN*`, `*SECRET*`, `*PASSWORD*`).

  App đầy đủ ở cổng 8501 vẫn chỉ dùng trên máy này.
- **Tạo link công khai** bằng Cloudflare quick tunnel (không cần tài khoản):
  1. Cài `cloudflared`: `winget install --id Cloudflare.cloudflared`, hoặc tải bản Windows ở trang releases của cloudflare/cloudflared trên GitHub.
  2. Chạy `cloudflared tunnel --url http://127.0.0.1:8502`.
  3. Gửi link `https://….trycloudflare.com` nó in ra.

  Link đổi mỗi lần chạy lại tunnel. Tắt tunnel (Ctrl+C) khi không gán nữa.
- **Lưu nhãn:** mỗi lần lưu có khoá theo file (`labeling_core._file_lock`), nên hai người cùng lúc, hoặc một người hai tab, không mất nhãn. Vẫn nên mỗi người chỉ mở một tab. Ghi chú tối đa 1.000 ký tự.
- **Nhãn máy:** `sb gold machine-import <file.json …> --model <tên>` ghi nhãn máy vào `labels_<X>.csv` + `provenance_<X>.csv`.
  - Chỉ ghi cặp còn trống; cặp người đã gán giữ nguyên; từ chối câu chung.
  - Lệnh từ chối chạy khi app dùng chung còn nghe ở cổng 8502, vì hai tiến trình không dùng chung khoá ghi file.
  - Duyệt trong app theo `gold-guide.md` mục "Nhãn máy và duyệt".
- **Giới hạn còn lại:** endpoint `/_stcore/metrics` của Streamlit (không tắt được) cho người có link biết số phiên đang mở, không lộ nội dung.
