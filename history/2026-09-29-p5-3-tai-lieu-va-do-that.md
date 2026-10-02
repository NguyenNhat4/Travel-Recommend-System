# P5.3: tài liệu, cấu hình VM và đo thật index song song

- Ngày: 2026-09-29
- Tác giả: Đăng Khôi / Claude Code
- Nhánh: test/newcrawl
- Trạng thái: hoàn thành
- Phạm vi: backend, data, docs

## Mục tiêu

P5.3 của `docs/plan/2026-09-29-index-cohere-song-song.md`:
- người vận hành biết chỉnh `COHERE_EMBED_CONCURRENCY` / `COHERE_CALLS_PER_MINUTE` khi đổi key;
- có số đo thật.

Theo mục đã chốt 2 và 3: không ghi biến vào PRD; đo thật chỉ trên sandbox.

## File thay đổi

- `.env.example` — sửa: hai biến mới ở khối Search / Recommendation, giá trị cho key Trial / Production.
- `src/data_collection/fresh-catalog.env.example` — sửa: hai biến cho job VM.
- `src/backend/README.md` — sửa: mục Search / Recommendation mô tả job index song song, giới hạn tốc độ, `--force`.
- `docs/plan/2026-09-29-index-cohere-song-song.md` — sửa: "Cần chốt" → "Đã chốt"; dòng tiến độ.
- `history/2026-09-29-p5-3-tai-lieu-va-do-that.md` — thêm: entry này.

## Quyết định

- Không sửa `docs/prd/deployment-plan.md` §2 (mục đã chốt 2): biến tinh chỉnh không bí mật, như `SEARCH_CUTOFF`.

## Kiểm tra

- **Đo thật** trên sandbox (`vota_crawl`, Weaviate local `ProductCrawl`, 290 search unit, `force=True`, `calls_per_minute`
  90):

  | Chế độ | Lượt gọi Cohere | Bị 429 | Thời gian |
  |---|---|---|---|
  | tuần tự (1 lô) | 4 | 0 | 7,4 s |
  | song song (4 lô) | 4 | 0 | 3,9 s |

  - Weaviate sau đo vẫn 290 object.
  - Thời gian gồm cả đọc catalog và danh sách object Weaviate, nên chưa tới 4 lần nhanh hơn.
  - Tổng 8 lượt gọi của quota Trial.
- Chưa đo trên catalog đầy đủ (3.183 search unit, ~34 lượt gọi): mục đã chốt 3.

## Còn lại / rủi ro

- Người yêu cầu kiểm tay (plan P5.2 "Bạn kiểm"): `./local_crawl.sh run index` sau khi đổi vài sản phẩm; Search trên sandbox
  như trước.
- Job VM nhận hai biến mới khi cập nhật `/etc/vota/fresh-catalog.env`; không đặt thì dùng mặc định 4 / 90.
- 8 chỗ trong repo còn hướng dẫn `conda activate vsf` / `envs/vsf`:
  - `src/data_collection/README.md`, `local_crawl.sh`, `finalize_catalog.sh`, `run_extra_queue.sh`;
  - `docs/spec/data-collection/RUN_BY_CITY.md`.
  - Chưa đổi sang `vsf2`, chờ người yêu cầu quyết.
- Chưa commit.
