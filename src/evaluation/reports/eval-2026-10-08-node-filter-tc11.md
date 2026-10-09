# Node `filter` lọc điểm tham quan trùng: golden TC-11, LLM thật (AC-AGT-04)

- Ngày chạy: 2026-10-08
- Code: commit `d8791cd1` + thay đổi chưa commit của `history/2026-10-08-node-filter-loc-trung-lap.md` (bản cuối: không bắc
  cầu, trường `duplicate`).
- Dataset: `src/evaluation/datasets/agent_test_cases_nhat.yaml`, case TC-11 (2 lượt), `--repeat 3`.
- Cấu hình: model `gpt-6-luna` (agent và giám khảo), dataMode `http` tới backend local `127.0.0.1:8000`, Postgres local,
  `ITINERARY_LLM_TIMEOUT_SECONDS=30`, LangSmith project `nhat-10-7` (trace `TC-11#1`, `TC-11#2`).
- Phục vụ: FR-AGT-03, FR-AGT-04, AC-AGT-04 (đề xuất `docs/prd/update-archive/2026-10-08-loc-trung-lap-bang-llm.md`).

## Lệnh tái sinh số

```bash
.venv/bin/python -m src.evaluation.agent.golden --only TC-11 --repeat 3 --timeout 90 --trace-project nhat-10-7
```

## Caveat khi trích dẫn

- 3 lần lặp, một câu hỏi, một điểm đến: chứng minh lỗi gốc của trace 08/10/2026 không còn, không đo tỷ lệ gộp nhầm chung.
- Cả 3 FAIL đều do kiểm tra cũ "stay = hotel rẻ nhất" (C1 trong `schedule_findings`, có từ 23/09), lệch với luật chọn khách
  sạn theo quãng đường (AC-AGT-04, từ 07/10); không liên quan node `filter`. Giám khảo (tiêu chí "không hai điểm cùng nơi")
  đạt cả 3 lần.
- Lần chạy trước bản cuối (cùng ngày, chỉ ở scratchpad) có gộp nhầm: Bảo tàng Gấu bị bỏ vì "trùng" Water Taxi (bắc cầu qua
  combo) và Vinpearl Safari bị bỏ vì LLM trả cặp (hòn Thơm, Safari) với lý do "hai địa điểm khác nhau". Bản cuối sửa cả hai.
- LLM của `filter` mất 2,4–3,4 s mỗi lượt (đọc trên LangSmith), cộng thẳng vào latency lượt lập lịch.

## Biên bản nguyên văn của runner

## Golden dataset — Itinerary Agent

- Commit: `d8791cd1`
- Chạy lúc: 2026-10-08T15:34:13.602312+00:00
- Model: `gpt-6-luna` · dataMode: `http` · mode: `dataset`
- productCount: 4147
- LangSmith project: `nhat-10-7`
- LLM giám khảo: `gpt-6-luna` (finding `[judge]`)

### Ba chỉ số PRD (test-plan.md §2.4)

| Chỉ số | Ngưỡng | Đo được |
|---|---|---|
| Grounding Rate | 100% | 100.0% |
| Structured Output Integrity | 100% | 100.0% |
| Tool Calling Accuracy | ≥ 95% | 100.0% (trên 6 lượt tính được) |

Latency: p50=12378ms, p95=22695ms, max=20904ms (mục tiêu < 5000ms, không gate).

Tổng 6 lượt, PASS 3, FAIL 3.

### Lượt FAIL

#### TC-11 lượt 2 — 'Chưa có ngân sách, cứ lên lịch giúp mình.'
httpStatus=200 status=COMPLETED latency=20904ms
- stay=4afe1590-e517-5017-ac8f-608e7f9bfe95 nhưng hotel rẻ nhất là 5e6bdd78-9689-5f54-a484-5f3f9957f7ff

#### TC-11 lượt 2 — 'Chưa có ngân sách, cứ lên lịch giúp mình.'
httpStatus=200 status=COMPLETED latency=18148ms
- stay=fd27e50c-018e-5186-9d94-967d3a8433b0 nhưng hotel rẻ nhất là 6f14469a-627c-5db4-9b7d-7c29121ae16a

#### TC-11 lượt 2 — 'Chưa có ngân sách, cứ lên lịch giúp mình.'
httpStatus=200 status=COMPLETED latency=15858ms
- stay=5e6bdd78-9689-5f54-a484-5f3f9957f7ff nhưng hotel rẻ nhất là 6f14469a-627c-5db4-9b7d-7c29121ae16a

### Đã loại

Điểm tham quan node `filter` bỏ vì trùng trước khi xếp lịch (AC-AGT-04).

| Case | Lượt | Bỏ | Trùng với | Do |
|---|---|---|---|---|
| TC-11 | 2 | [Grand World Phú Quốc] - Vé đi thuyền Venice (Water Taxi) (`e35d0af0`) | [Grand World Phú Quốc] - Vé đi thuyền Venice (Water Taxi) (`f540ef2f`) | rule |
| TC-11 | 2 | Sun World Hòn Thơm (`76da210a`) | hòn Thơm (`903db93c`) | llm |
| TC-11 | 2 | Cáp Treo Hòn Thơm (`fdb01f88`) | hòn Thơm (`903db93c`) | llm |
| TC-11 | 2 | [Grand World Phú Quốc] - Vé đi thuyền Venice (Water Taxi) (`e35d0af0`) | [Grand World Phú Quốc] - Vé đi thuyền Venice (Water Taxi) (`f540ef2f`) | rule |
| TC-11 | 2 | Sun World Hòn Thơm (`76da210a`) | hòn Thơm (`903db93c`) | llm |
| TC-11 | 2 | Cáp Treo Hòn Thơm (`fdb01f88`) | hòn Thơm (`903db93c`) | llm |
| TC-11 | 2 | [Safari Passport] - 10 trạm khám phá Vinpearl Safari + Đóng dấu hộ chiếu + Bộ quà tặng độc quyền (`e137ef0d`) | Vinpearl Safari Phú Quốc (`1f4564f5`) | llm |
| TC-11 | 2 | [Grand World Phú Quốc] - Bảo Tàng Gấu Teddy Bear Museum (`1801ef95`) | [Grand World Phú Quốc] - Bảo Tàng Gấu Teddy Bear Museum (`bceffc48`) | rule |
| TC-11 | 2 | [Vinpearl Safari Phú Quốc] - Vé Vào Cửa Tiêu Chuẩn (`94948214`) | [Vinpearl Safari Phú Quốc] - Vé Vào Cửa Tiêu Chuẩn (`f58f09c9`) | rule |
| TC-11 | 2 | [Vinpearl Safari Phú Quốc] - Vé Vào Cửa Tiêu Chuẩn (`86b3bb5a`) | [Vinpearl Safari Phú Quốc] - Vé Vào Cửa Tiêu Chuẩn (`f58f09c9`) | rule |
| TC-11 | 2 | [Vinpearl Safari Phú Quốc] - Vé Vào Cửa Tiêu Chuẩn (`f58f09c9`) | [Vinpearl Safari Phú Quốc] - Tour Night Safari (`a750db7b`) | llm |
| TC-11 | 2 | [Vinpearl Safari Phú Quốc] - Tour Night Safari + BBQ trong rừng (`b38c926e`) | [Vinpearl Safari Phú Quốc] - Tour Night Safari (`a750db7b`) | llm |