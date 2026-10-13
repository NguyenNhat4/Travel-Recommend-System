# D1 — Kiểm chứng kịch bản demo trên orchestrator, LLM thật (13/10/2026)

Bước D1 của `docs/plan/2026-10-12-go-luong-cu-orchestrator-chinh.md`. Phục vụ FR-AGT-01, FR-AGT-05, FR-AGT-06,
FR-AGT-07, NFR-PERF-02, NFR-REL-01.

## Cấu hình

- Code: `a50c5e62` cộng các comment của D0 (không đổi hành vi). Chạy trước D2 và trước khi gỡ luồng cũ, cờ
  `ITINERARY_ORCHESTRATOR=on`.
- Backend: `uvicorn src.backend.app.main:app --port 8011`, không reload, `HF_HUB_OFFLINE=1`,
  `ITINERARY_DATA_MODE=inprocess`.
  - RecSys: 4147 search unit, Postgres và Weaviate local (`docker compose`).
  - Bật prewarm Search như staging.
- Model:
  - Chung: `gpt-6-luna`, nhiệt độ 1, reasoning `none`.
  - Orchestrator: `gpt-6.1-sol`, OpenAI, reasoning `low`.
- Timeout theo `.env` local: request 90 giây, LLM 30 giây, tool 20 giây.
- Gọi `POST /api/v1/assistant/itineraries/stream` tuần tự (giới hạn 10 tin/phút/IP). Khách chưa đăng nhập.
- Kịch bản K1–K6 đúng như plan mục D1. Bản chính chạy 3 lần, bản diễn đạt khác chạy 1 lần: 100 lượt.
- Dữ liệu thô: `src/evaluation/reports/eval-2026-10-13-demo-orchestrator.json` (gitignored).

**Caveat:**
- Máy local, không phải staging. Timeout tool trên staging chưa rõ: biến nằm trong Secret Manager; compose mặc định 1
  giây, local 20 giây. Phải kiểm ở D6.
- Số lời gọi tool lấy từ dòng log `itinerary.tool`, chỉ có ở lời gọi qua `ItineraryToolGateway.execute`. Lời gọi
  `list_products`, `get_product_detail` của job không ghi dòng này, nên số đếm thấp hơn thật. Chưa dùng số này để kết
  luận về T1–T4.
- LLM không tất định.
- "Chi tiết sản phẩm" chỉ kiểm `GET /products/{id}` cho sản phẩm trong câu trả lời cuối của mỗi hội thoại, không phải mọi
  lượt.
- Không chạy K7 (lỗi và chậm); để D6.

## Thời gian mỗi lượt (giây, nguyên văn từ script)

| Loại lượt | Số lượt | p50 | max |
|---|---|---|---|
| chỉ trả lời / hỏi lại | 16 | 7.4 | 14.0 |
| có job (khám phá) | 44 | 18.6 | 34.2 |
| hỏi lại thông tin chuyến | 19 | 5.4 | 13.0 |
| hỏi vé | 12 | 7.7 | 9.8 |
| lập lịch (COMPLETED) | 9 | 18.8 | 22.6 |
| Tất cả | 100 | 12.7 | 34.2 |

p95 tất cả: 24.0.
- `run.failed`: 0. HTTP khác 200: 0.
- Lượt `gatekeep` phải sửa câu: 4. Lượt kết thúc bằng câu dự phòng: 4 (đều là K4 lượt 4).
- `GET /products/{id}` cho sản phẩm của câu trả lời cuối: 0 lỗi (K3, K4, K6).

## Mốc `compose` → có câu trả lời (tiêu chí preview, plan tiến trình §3.5)

Khoảng có ích = `t_final − max(5 giây, t_compose)`.
- 9/9 lượt lập lịch có khoảng này từ 2 giây trở lên (3,6–4,7 giây).
- `compose` xong ở giây 11,9–18,8, câu trả lời có ở giây 16,6–22,7.
- Tiêu chí đạt. Người dùng có thể xem xét chốt Phần C.

## Lỗi thấy được

Mức độ theo plan D1:
- "chặn demo": sai, không trả lời được việc chính, hoặc tra cứu thất bại mà nói không có dữ liệu.
- "xấu": dài, ít thẻ, thiếu nút, không nhất quán.
- "nhỏ": còn lại.

| Mã | Kịch bản, lượt | Triệu chứng (số lần / số lần chạy) | Lớp nghi ngờ | AC | Mức |
|---|---|---|---|---|---|
| D1-01 | K1 lượt 3 "tìm khách sạn gần Hồ Gươm" | 0 thẻ, "chưa xác định được tọa độ Hồ Gươm" (4/4). Lượt "rẻ hơn" sau đó 0 thẻ (3/4). Nguyên nhân đọc code: mốc `near` khớp tên bằng `closest_matches`, mà "Hồ Gươm" và "Hồ Hoàn Kiếm" chỉ chung một từ (cần ≥ 2) | `jobs._explore` (mốc), prompt orchestrator (tên mốc) | FR-AGT-06 | chặn demo |
| D1-02 | K2 lượt 3 "từ Hà Nội đi đâu rẻ nhất?" | "Mình chưa thấy chuyến bay còn vé nào từ Hà Nội trong 30 ngày tới", 0 thẻ (4/4), trong khi lượt 1 tìm được vé. Cùng triệu chứng với A08b trong lần chạy thử 12/10. Khớp T1, chưa xác nhận bằng log | `fares._origin_routes` (T1) | AC-AGT-08 | chặn demo |
| D1-03 | K4 lượt 4 "chỗ thứ hai còn phòng ngày 24/10 không?" | `gatekeep` sửa câu, rồi dùng câu dự phòng "Bạn có thể xem [Cherry Hotel Apartment]." (7 từ), không trả lời câu hỏi (4/4), 22–34 giây | job `about_shown`, `gatekeep` | FR-AGT-06 | chặn demo |
| D1-04 | K3 lượt 2 "đổi sang khách sạn có hồ bơi" sau khi có lịch | Orchestrator khám phá ra 3–4 thẻ khách sạn thay vì đổi khách sạn trong lịch và lập lại lịch (4/4) | prompt orchestrator (`plan`), luật đổi | FR-AGT-05, AC-AGT-05 | chặn demo |
| D1-05 | K3 lượt 3 "bỏ vé máy bay, mình tự đi" | Chỉ trả lời "sẽ không đưa vé máy bay", không lập lại lịch (4/4) | như D1-04 | FR-AGT-05 | xấu |
| D1-06 | Mọi lượt hỏi vé (K2) | Chỉ có nút "Lên lịch … cho mình"; mất nút của câu vé ("Đắt nhất thì sao?", "Ngày nào còn vé?"). Unit test cũng thấy (3 ca `xfail` strict) | `gatekeep` đường tắt câu vé | AC-AGT-08 | xấu |
| D1-07 | K5 lượt 1, 3 ("không biết đi đâu", "chán, đi rồi") | Không có nút gợi ý (sugg rỗng) ở đa số lần chạy | `gatekeep`/`replies.checked_suggestions` | AC-AGT-07 | xấu |
| D1-08 | K4 lượt 1–3 | Hỏi riêng khách sạn mà chỉ 1–2 thẻ ("xem thêm" 1 thẻ) | dữ liệu hồ bơi, job `more` | AC-AGT-06 | xấu |
| D1-09 | Lượt lập lịch (K3, K6) | Lời diễn giải 186–364 từ | `narrate` | AC-AGT-07 (gọn) | xấu |
| D1-10 | K6 lượt 1 "cuối tuần này" | Lúc hiểu 2 ngày, lúc hỏi lại số ngày (1/3 hiểu) | prompt `extract` | AC-AGT-01 | xấu |
| D1-11 | K1 lượt 5 | Đủ ngày, số người, nơi đi vẫn hỏi ngân sách một lần (4/4). Đúng thiết kế AC-AGT-01 (hỏi gộp một lần chi tiết còn thiếu, ngân sách không bắt buộc) | — | AC-AGT-01 | nhỏ |
| D1-12 | K1 lượt 6 (chọn phương án 2) | Không có lịch nên không có phương án; orchestrator hỏi lại. Do kịch bản (D1-11) | — | — | nhỏ |
| D1-13 | K1 lượt 2 | "Chưa kiểm được giờ mở cửa" LOTTE Hanoi Sky; có thể catalog không có giờ mở | dữ liệu | — | nhỏ |

Thời gian: lượt có job p50 18,6 giây, max 34 giây. 5 giây của PRD chỉ là gợi ý. Tiến trình có kết quả thật là cách chính
để người xem thấy trợ lý đang làm gì.

## Lệnh tái sinh

Script đọc SSE (`run_d1.py`) và script tổng hợp (`analyze.py`) đang ở scratchpad của phiên. D6 đưa script chạy kịch bản
vào `src/evaluation/agent/` để chạy lại trên staging. Sáu kịch bản bản chính đã thêm vào snapshot hành vi
(`src/backend/tests/unit/agents/behavior_snapshot/scenarios.json`, id `demo-K1`…`demo-K6`), phát lại offline được sau
D3.
