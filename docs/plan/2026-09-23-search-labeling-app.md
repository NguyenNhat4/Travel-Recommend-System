# Streamlit review cho 600 search cases

Phục vụ **FR-SRC-01..04**, **NFR-SEC-01**, **NFR-MAINT-01** và **AC-SRC-01** trong `docs/prd/requirements.md`.

## Mục tiêu

Deploy một app Streamlit gọn để nhiều annotator review độc lập 600 query ứng viên của Role A trước khi chọn khoảng 200 query cho bước tạo pool. Đây là review chất lượng draft (`KEEP`, `REJECT`, `NEEDS_EDIT`), chưa phải relevance label 0/1/2 và chưa tạo `gold_v1`.

## Luồng sử dụng

1. Annotator nhập mật khẩu nhóm rồi nhập tên.
2. App hiển thị query, slice, filter, `expected_no_result`, `source_refs` và ghi chú grounding.
3. Annotator chọn `KEEP`, `REJECT` kèm lý do, hoặc `NEEDS_EDIT` kèm query thay thế.
4. Mỗi lần lưu tạo một event append-only trong file JSONL dùng chung trên instance Streamlit. Nhãn mới nhất theo `(case_id, annotator)` là trạng thái hiện hành.
5. App hiển thị tiến độ cá nhân, số case team đã chạm, bất đồng giữa annotator và cho tải CSV nhãn mới nhất.

## Cấu hình deployment

Entrypoint: `src/evaluation/search_bench/streamlit_app.py`.

Streamlit Secret, **không commit vào Git**:

```toml
[labeling]
app_password = "<MAT_KHAU_NHOM>"
```

Đặt ở hai nơi, cùng nội dung:

- **Local** — `.streamlit/secrets.toml` ở gốc repo (Streamlit đọc `./.streamlit/secrets.toml` theo thư mục chạy lệnh, nên `streamlit run` phải chạy từ gốc repo). `.gitignore` đã chặn `.streamlit/secrets.toml` và `**/.streamlit/secrets.toml`; kiểm bằng `git check-ignore -v .streamlit/secrets.toml` trước khi tạo file.
- **Streamlit Community Cloud** — app → Settings → Secrets, dán đúng khối TOML trên. Không bao giờ ghi giá trị thật vào file trong repo, entry `history/`, hay mô tả PR.

Fallback: biến môi trường `LABELING_APP_PASSWORD` (chỉ dùng khi `st.secrets` lỗi; app **không** đọc `.env`). Nếu không cấu hình cả hai thì `require_password()` trả về sớm và app **mở công khai, không hỏi mật khẩu** — phải đặt secret trước khi để link ra ngoài.

Mật khẩu chỉ là cổng bên trong app, không liên quan mạng: deploy Community Cloud thì ai có URL và mật khẩu đều gán nhãn được từ bất kỳ mạng nào, và mọi người dùng chung một instance nên chia sẻ cùng một file nhãn (metric "Team đã chạm" / "Case bất đồng" mới đúng). Chạy local thì người khác phải cùng LAN với máy chạy app (`Network URL` mà Streamlit in ra).

Phụ thuộc: Cloud chỉ tự nhận `requirements.txt` cạnh entrypoint hoặc ở gốc repo, mà entrypoint buộc nằm trong `src/evaluation/search_bench/` (app import `labeling` cùng thư mục và đọc `gold/drafts_raw.tsv` cạnh nó). Vì vậy `streamlit>=1.64,<2` nằm chung `src/evaluation/search_bench/requirements.txt` với các dependency bench; Cloud sẽ cài thêm pandas/pyarrow/scipy/cohere/weaviate-client mà app không dùng (build lần đầu chậm hơn, toàn bộ là wheel). Nếu vượt giới hạn của Cloud thì tách entrypoint sang package riêng có `requirements.txt` một dòng.

Đây là bản tối giản theo yêu cầu: không dùng Google Drive hay database. File nhãn trên Streamlit là tạm thời (`bench_out/search/labels/labels.jsonl`, đã gitignore) và có thể mất khi app restart hoặc redeploy; team cần tải CSV định kỳ bằng nút trong app.

## Kiểm tra và rollback

- Unit test các rule label, trạng thái latest/consensus, JSONL round-trip và CSV export.
- Smoke test app render với đúng 600 case.
- Smoke test URL sau deploy: trang yêu cầu mật khẩu, sau đăng nhập hiển thị 600 case.
- Rollback bằng cách redeploy commit trước; tải CSV trước khi redeploy nếu cần giữ nhãn.

## Bổ sung 28/09: chế độ "Bổ sung câu hỏi" và "Tra cứu catalog"

Sidebar có ô **Chế độ**. Chế độ cũ đổi tên thành "Soát câu hỏi" và giữ nguyên hành vi. Cache danh sách case giờ khoá theo mtime của `drafts_raw.tsv`, nên dòng mới hiện ra ngay, không phải khởi động lại app (lỗi "72 câu bổ sung" cũ).

- **Bổ sung câu hỏi** (`draft_authoring.py`): mỗi slice là một box, slice mỏng mở sẵn (quota = `min_per_slice` và hết ý định dự phòng).
  - **Trong box:** bảng ý định đã có (mã, cách nói, `review_note`, trạng thái trong `drafts.txt`) và form thêm ý định mới, 1–3 cách nói.
  - **Kiểm trước khi ghi** (lỗi thì không ghi):
    - trùng câu;
    - trùng khoá ý định (`dest_type`, `out_of_catalog`);
    - `source_refs` phải là search unit;
    - `filter_json` hợp lệ và khớp ≥ 1 sản phẩm; multi_constraint cảnh báo nếu ngoài khoảng 5–40;
    - `out_of_catalog`: catalog không được nhắc tới điểm đến, kể cả trong tên sản phẩm hoặc tỉnh.
  - **Ghi:** thêm vào `gold/drafts_raw.tsv`. Mã mới cấp theo khối 3 (c0673–c0675, …), để `intent_key` vẫn coi 3 mã liền nhau là 1 ý định.
  - **Tuỳ chọn KEEP:** ghi `KEEP` vào `gold/overrides.tsv`, note có tên người thêm.
  - `drafts.txt` chỉ đổi khi chạy `gold drafts --fill`. Câu dự phòng chỉ vào đó khi nâng quota `gold.slices`.
- **Tra cứu catalog** (`catalog_lookup.py`, đọc `items.parquet` + `amenity_vocab.json` của `sb catalog build`), 4 tab:
  - **điểm đến có dữ liệu:** số search unit theo loại;
  - **tìm sản phẩm:** tên hoặc địa danh không dấu, điểm đến, loại, sao, giá, có / không có tiện ích. Hiện filter JSON và số sản phẩm khớp; chọn sản phẩm rồi "Mang sang Bổ sung câu hỏi" để điền sẵn `source_refs` và filter;
  - **tiện ích theo điểm đến:** tỷ lệ sản phẩm có từng tiện ích, dùng để chọn tiện ích cho câu phủ định hoặc off-taxonomy;
  - **kiểm tra ngoài catalog:** địa danh có bị sản phẩm nào nhắc tới không.
- **Biến môi trường** (dùng cho test / chạy riêng):
  - `SBENCH_GOLD_DIR` — thư mục `gold/`;
  - `SBENCH_DATASET` — mặc định `jsonl`;
  - `SBENCH_HOME` — nơi đặt dữ liệu bench.
- **Kiểm tra:** `tests/test_catalog_lookup.py`, `tests/test_draft_authoring.py`, `tests/test_streamlit_app.py` (AppTest render 3 chế độ và lưu một ý định qua form trên bản sao `gold/` trong tmp).

## Bổ sung 28/09 (chiều): chế độ "Bộ 200 câu đã chọn"

`draft_selection.py`: tính lại bộ câu y như `gold drafts --fill`. Các bước: nhãn app → ghi đè `overrides.tsv` → chọn theo quota → `--fill` cùng hàng rào grounding `gold.make_fill_guard`, dùng chung với CLI.

- **Bảng 200 câu:** ghi nguồn từng câu (người soát / `overrides.tsv` / `--fill` kèm lý do lấp) và lọc được theo slice, nguồn, chữ. Ô đếm hiện số câu `--fill` chưa ai soát.
- **Dropdown "Thay bằng" cho từng câu**, có 4 kiểu lựa chọn:
  - **giữ** (chỉ với câu `--fill`) → ghi KEEP, câu đó hết là `--fill`;
  - **cách nói khác của cùng ý định** → REJECT `duplicate` cho câu hiện tại, KEEP cho câu mới;
  - **ý định khác cùng slice** chưa có trong bộ → REJECT `other` + KEEP, giữ NEEDS_EDIT nếu câu được chọn đang có;
  - **loại** → REJECT, `--fill` tự lấp ý định kế tiếp.
  - Ở `dest_type` / `out_of_catalog`, ý định trùng khoá với một câu khác đang chọn không được đưa vào danh sách. Dấu ⚠ đánh dấu ý định từng bị loại vì lỗi thật.
- **Ghi quyết định:** vào `gold/overrides.tsv` qua `upsert_overrides`. Dòng cùng `case_id` được thay tại chỗ, các dòng khác giữ nguyên byte. Cả file được kiểm bằng `gold.read_overrides` trước khi ghi.
- **Ghi `drafts.txt`:** app cho xem trước các dòng sẽ bỏ / thêm, rồi mới ghi khi bấm "Ghi drafts.txt".
- **Kho nhãn** mặc định là đường dẫn tuyệt đối `paths.sbench_home()/labels/labels.jsonl`; sidebar hiện đường dẫn này.
- **Viết câu thay thế** (28/09, tối): dropdown "Thay bằng" có thêm mục "✎ Viết câu thay thế", có 2 kiểu:
  - **Cùng ý định:** NEEDS_EDIT trên chính case đó, giữ mã case, filter và source_refs. Kiểm câu không rỗng và không trùng câu đã có trong slice.
  - **Ý định mới:** tạo case mới qua `draft_authoring.append_intent` (KEEP), và ghi REJECT `other` cho câu cũ.
    - Ô chọn source_refs lọc theo điểm đến / loại / từ khoá. Mặc định là điểm đến và loại của source_refs cũ, đã chọn sẵn source_refs cũ.
    - Bảng hiện thông tin các sản phẩm đã chọn: tên, loại, điểm đến, sao, giá, tiện ích, hạng phòng.
    - Câu mới chưa vào bộ (vì slice có ý định KEEP khác vượt quota đứng trước) thì app cảnh báo.
- **source_refs:** mỗi câu đang xem có bảng source_refs kèm giải thích. source_refs là product_id của các sản phẩm trong catalog thoả câu hỏi, tức bằng chứng grounding. Chúng không phải nhãn gold và không ghi vào `drafts.txt`.

## Bổ sung 28/09 (tối): luật chọn draft mới và chế độ "Gán nhãn 0/1/2"

**Luật chọn draft** (người dùng chốt):
- `drafts.txt` = mọi câu người soát chọn.
- Không cần đủ 200, không cắt theo `gold.slices` (chỉ còn là mục tiêu tham khảo), không tự lấp.
- Mỗi slice cần ≥ `gold.min_per_slice` = 3 câu.

**Chế độ "Bộ câu đã chọn"** theo luật này:
- ô đếm "slice đạt ≥ 3" và bảng theo slice;
- mục "➕ Thêm câu chưa chọn": các câu `--fill` từng đề xuất đánh dấu ⭐ và đứng đầu danh sách;
- vẫn thay / viết lại / loại được từng câu; thao tác loại không tự lấp câu khác.

**Chế độ "Gán nhãn 0/1/2"** (`labeling_core.py`, theo `docs/spec/bench/prompts/may2-label-app.md`):
- **Người gán:** chọn A hoặc B ở sidebar. App chỉ mở `pool_X.csv` (theo `pool_meta.json`) và `labels/labels_X.csv`, không đọc file nhãn của người kia.
- **Chặn pool lệch:** kiểm sha của pool trước khi đọc; lệch thì chặn và nhắc kiểm `.gitattributes`.
- **Tiếp tục đúng chỗ:** mở app là nhảy tới câu chưa xong đầu tiên. Có nút ← / →, "Câu chưa xong tiếp theo", và bộ lọc "Chỉ câu chưa xong".
- **Tiến độ:** số câu xong, số cặp đã gán, phân bố nhãn 2 · 1 · 0.
- **Mỗi trang một câu:** hiện query, slice, `filter_text`, và nhắc riêng với câu ngoài catalog. Bảng ứng viên giữ đúng thứ tự trong file, chỉ gồm các cột `DISPLAY_COLUMNS` (không có product_id, nguồn, rank, giá). Cột `children` chỉ hiện ở parent_child.
- **Gán nhãn:** cột "nhãn" là dropdown 2/1/0, mặc định trống (không tự điền 0), kèm cột "ghi chú". Mỗi lần sửa là ghi ngay qua `upsert_label`; `labeled_at` có múi giờ, `pool_sha` lấy từ meta.
- **parent_child:** nhãn 2 hiện thêm ô chọn hạng phòng; chưa chọn thì chưa lưu.
- **Ngoài phạm vi:** không làm phím tắt 0/1/2.
- **Dùng thử khi chưa có pool thật:** nút "Dùng bản thử fixture gold_small" chép pool của fixture vào `bench_out/search/label_try/`, nhãn ghi ở đó.
