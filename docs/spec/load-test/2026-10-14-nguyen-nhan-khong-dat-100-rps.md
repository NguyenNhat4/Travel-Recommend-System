# Vì sao staging không chịu được 100 rps

- Ngày: 2026-10-14 (giờ Việt Nam, +07)
- Trạng thái: điều tra xong ở mức đọc số liệu và code. **Chưa kiểm chứng bằng profile trên VM.** Các mục "giả thuyết" ở dưới cần đo thêm.
- Liên quan: [báo cáo stress đọc liên tục](2026-10-14-stress-doc-lien-tuc.md), [đợt 3](2026-10-13-run-3.md). Đợt 3 có tham chiếu tới `2026-10-13-nguyen-nhan-khong-dat-500-rps.md`, file đó không có trong repo; tài liệu này thay thế vai trò của nó cho đợt đo 100–500 rps.

## Câu trả lời ngắn

Một VM app (2 vCPU) chỉ xử lý được khoảng 30–36 rps với hỗn hợp endpoint hiện tại. Phần lớn chi phí nằm ở `GET /products/{id}/similar`: một lượt mất khoảng 0,8 s phía server, trong đó có khoảng 340 ms mỗi lần mở kết nối tới Weaviate (vùng khác), và phần dựng bộ lọc gần 6.000 ID tốn CPU của tiến trình Python. Khi tải tăng, mọi endpoint đều chậm theo, kể cả danh mục vốn chỉ mất 21 ms khi tải nhẹ. Health check timeout khiến autohealing thay VM giữa lúc chạy, làm mất capacity và phát sinh lỗi 5xx. Trần cụm là 2 VM (max replica), nên 100 rps vượt xa khả năng hiện tại.

Không phải nút thắt chính: cụm DB (CPU 4–6%), máy sinh tải (máy local 16 CPU cũng đạt cùng trần).

## Bằng chứng

### 1. Thời gian xử lý phía server theo route

Lấy từ log sự kiện `http.request` của VM app (`duration_ms`, đo trong backend). Đơn vị ms.

| Route | 20 rps, 1 VM (seg005) p50 / p95 | R1 100 rps, p50 | R9 100 rps local, p50 | R2 500 rps, p50 |
|---|---|---|---|---|
| `/api/v1/products` | 21 / 36 | 1.810 | 1.889 | 1.618 |
| `/api/v1/products/{id}` | 22 / 42 | 6.499 | 12.080 | 11.073 |
| `/api/v1/recommendations` | 53 / 84 | 3.230 | 4.955 | 3.492 |
| `/api/v1/products/{id}/similar` | **776 / 1.560** | 2.517 | 3.557 | 2.396 |
| `/api/v1/destinations` | 5 / 14 | 2.232 | 2.607 | 2.241 |

- Ở tải nhẹ, thời gian phía server của `similar` (p50 776 ms) gần bằng thời gian phía client (p50 812 ms). Phần chậm nằm trong backend, không nằm ở mạng bên ngoài.
- Ở tải cao, mọi route chậm lên gấp 50–100 lần, kể cả route rẻ nhất. Đây là dấu hiệu hàng đợi trên tài nguyên dùng chung, không phải do từng endpoint tự chậm.
- Mẫu log là 4.000 dòng đầu mỗi cửa sổ, nên đây là ước lượng, không phải toàn bộ.

### 2. Trần CPU của một VM

- Autoscaler ghi tín hiệu CPU 0,550 với 1 VM ở 00:09 (14/10), và 0,22–0,25 với 2 VM ở các lần giảm (00:28, 01:11, 04:03, 08:27). Chi tiết ở [báo cáo stress](2026-10-14-stress-doc-lien-tuc.md), mục 3.3.
- VM là `e2-standard-2` (2 vCPU). Nếu CPU 0,55 ở 20 rps tương ứng với khoảng 1,1 vCPU bận, thì mỗi request tốn khoảng 55 ms CPU. Khi đó trần một VM là 2 vCPU / 55 ms ≈ 36 rps, khớp với mức 25–32 iter/s đo được ở R1, R2, R9 và cal-200.
- Ở 100 rps cần khoảng 5,5 vCPU. Max 2 VM chỉ có 4 vCPU. Đây là ước lượng dựa trên giả định trên, chưa đo trực tiếp CPU theo route.

### 3. Backend chạy một tiến trình uvicorn

Đã kiểm trên VM `vota-ha-app-2ztd`: lệnh `python -m uvicorn src.backend.app.main:app --host 0.0.0.0 --port 8002 --no-access-log`, không có `--workers`. Một tiến trình có một event loop, và phần Python chạy chung một GIL. Thêm vCPU không tự nhân throughput.

### 4. Đường đi của `similar` trong code

- `application/catalog/use_cases.py` `GetSimilarProducts.__call__`: gọi `asyncio.to_thread(self.similar.lookup, ...)`. Thread pool mặc định của asyncio có kích thước `min(32, cpu+4)`. Trên VM 2 vCPU, con số này là **6 thread**. Với khoảng 0,8 s mỗi lượt, một tiến trình chỉ phục vụ được khoảng 7–8 lượt `similar` mỗi giây.
- `application/search/use_cases.py` `SimilarProducts.lookup`: lọc mask trên toàn bộ search unit, lặp qua `parent_of`, rồi gọi `allowed_ids()` để tạo danh sách ~6.000 ID.
- `infrastructure/vectors/weaviate_store.py`: mỗi ID đi qua `object_uuid` (`uuid5`), rồi `Filter.by_id().contains_any(...)` gửi tới Weaviate với `near_vector`.
- `docs/prd/deployment-plan.md` ghi Weaviate Cloud ở `eu-central-1`. App chạy ở `asia-southeast1`.

### 5. Độ trễ tới Weaviate

Đo từ container backend trên `vota-ha-app-2ztd`, chỉ đo thời gian TCP connect tới cổng 443 của host Weaviate (không in host): 384, 340, 340, 340, 338, 339 ms. Đây là một lượt khứ hồi xuyên vùng, chưa tính TLS và gRPC.

### 6. Chi phí CPU phía client của bộ lọc

Benchmark cô lập (`analysis/sim_cpu.py`, môi trường Python trên máy local, weaviate-client 4.23, N = 6.026, 6.021 ID được phép):

| Bước | Median |
|---|---|
| `allowed_ids()` | 0,66 ms |
| `object_uuid` × 6.021 | 23,9 ms |
| `Filter.by_id().contains_any` (tổng) | 38,0 ms |

Chưa đo: chi phí serialize gRPC của bộ lọc, và chi phí trên VM e2 (thường chậm hơn máy local). Con số trên VM có thể cao hơn.

### 7. Health check và autohealing

- R2 (12:39–12:43, 13/10): health check `/health/live` của `vota-ha-app-z2wq` TIMEOUT lúc 12:42:14, trong lúc đang tải. `vota-ha-app-fn9m` UNHEALTHY lúc 12:43:21. Autohealing tái tạo `fn9m` lúc 12:43:27.
- R9 (23:45–23:46, 13/10): `vota-ha-app-z2wq` UNHEALTHY lúc 23:46:45. Autohealing tái tạo `z2wq` lúc 23:46:51, sát lúc k6 dừng khẩn (23:46:37). Log đã truy vấn không có sự kiện TIMEOUT trước đó, nên không chắc chuỗi bắt đầu từ lúc nào.
- Health check `vota-ha-app-live`: cổng 3000, interval 15 s, timeout 5 s, unhealthy threshold 4.
- Không có sự kiện OOM hay die của container trong các cửa sổ run (bộ lọc `docker_events` đã thử).

### 8. Các yếu tố đã loại trừ

- **Máy sinh tải:** R9 chạy từ máy local (16 CPU) cho cùng trần (24,9 iter/s) với VM 2 vCPU (R1: 31,8 iter/s). Máy sinh tải không phải nút thắt chính.
- **Cụm DB:** CPU `vota-ha-pg-a` và `vota-ha-pg-b` trung bình 4–6% trong R1, R2, R9 và các đoạn 20 rps. Đỉnh 16–19% chỉ xuất hiện lẻ tẻ. Cụm DB là `e2-custom-1-1024` (1 vCPU / 1 GB), nên cần theo dõi nhưng không phải điểm nghẽn theo CPU.
- **Mạng từ internet tới app:** thời gian phía server gần bằng thời gian phía client ở tải nhẹ.

## Giả thuyết cần kiểm chứng

| # | Giả thuyết | Trạng thái |
|---|---|---|
| H1 | Trần một VM do 2 vCPU và một tiến trình uvicorn; max 2 VM tạo trần cụm | Có bằng chứng (mục 2, 3) |
| H2 | `similar` chiếm phần lớn thời gian xử lý và CPU của app: dựng bộ lọc 6.000 ID (client), chờ Weaviate xuyên vùng, và giới hạn 6 thread | Có bằng chứng gián tiếp (mục 1, 4, 5, 6). Chưa đo CPU theo route |
| H3 | GIL bị tranh chấp: các thread `similar` chạy Python làm chậm event loop, nên mọi route chậm theo | Phù hợp với hiện tượng ở mục 1. Chưa profile |
| H4 | `/products/{id}` chịu thêm chi phí kết nối DB mới mỗi request qua pgbouncer. Route này chậm hơn `/products` rõ rệt khi tải cao (6–12 s so với 1,6–1,9 s) | Chưa đo pgbouncer. Chưa kiểm chứng |
| H5 | Health check timeout dưới tải, dẫn tới autohealing thay VM và mất capacity, sinh 5xx | Có bằng chứng (mục 7) |

## Đề xuất kiểm chứng (chưa làm)

Staging đang deploy blue/green từ 09:31 (+07), VM được thay vào 09:48–09:51. Nên đo sau khi deploy xong.

1. Profile một VM ở 20 và 40 rps bằng `py-spy` (hoặc đo CPU theo route) để tách CPU của `similar` khỏi phần còn lại.
2. Chạy tách riêng: chỉ `similar` ở 5–8 rps, chỉ `products` ở 40 rps. So sánh CPU VM và thời gian phía server.
3. Trong lúc tải, xem `SHOW POOLS` của pgbouncer trên VM app để kiểm H4.
4. Đo lại benchmark bộ lọc trên VM thật, không chỉ máy local.

## Hướng xử lý (để thảo luận, không làm trong điều tra này)

- Cache kết quả `similar` theo `product_id`. Index ít đổi nên kết quả gần như cố định, và đây là 10% traffic nặng nhất.
- Thay việc gửi ~6.000 ID bằng lọc phía Weaviate (theo taxonomy) hoặc danh sách láng giềng tính sẵn.
- Dùng async client của Weaviate hoặc tách pool riêng cho `similar`, để không chiếm 6 thread mặc định.
- Chạy nhiều worker uvicorn (ví dụ 2) trên VM 2 vCPU, sau khi kiểm chứng tác động lên bộ nhớ (container backend đã dùng 2,7 GiB trên giới hạn 3 GiB ở một thời điểm đo).
- Tách health check `/health/live` khỏi đường xử lý nặng, hoặc đánh giá lại timeout, để tránh autohealing dưới tải.
- Đánh giá lại trần max replica và loại VM. Đây là quyết định vận hành.

Kế hoạch `docs/plan/2026-10-13-cache-va-presort-catalog.md` chỉ xử lý `GET /products`, chưa xử lý `similar`.

## Kiểm tra

- Số liệu route và tín hiệu autoscaler lấy từ log Cloud Logging (`http.request`, `compute.autoscalers.resize`), đã đổi sang +07.
- Đo TCP tới Weaviate: chạy trong container `vota-backend-green` trên `vota-ha-app-2ztd`, chỉ in thời gian. Không in host.
- Benchmark bộ lọc: `analysis/sim_cpu.py` (ngoài repo, trong scratchpad). Chạy bằng venv tạm có `weaviate-client` 4.23.1 và numpy 2.5.4.
- Cửa sổ đo của R1, R2, R9 lấy từ log k6 và đã đối chiếu với log MIG.
- Chưa kiểm: CPU theo route trên VM, pgbouncer, thống kê DB của leader hiện tại (leader đã đổi sang `vota-ha-pg-b`).
