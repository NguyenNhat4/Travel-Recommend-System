# D3 — Baseline snapshot trên orchestrator, so với luồng cũ (13/10/2026)

Bước D3 của `docs/plan/2026-10-12-go-luong-cu-orchestrator-chinh.md`. Phục vụ FR-AGT-01, FR-AGT-05, FR-AGT-06,
FR-AGT-07, NFR-REL-01. Bảng dưới để người dùng duyệt (R2): mỗi hội thoại một dòng, đánh giá theo AC.

## Cấu hình

- Code: working tree trên `a50c5e62`, sau khi gỡ luồng cũ và cờ (`history/2026-10-13-go-luong-cu-orchestrator-duy-nhat.md`).
- Ghi: `HF_HUB_OFFLINE=1 .venv/bin/python -m src.backend.tests.unit.agents.behavior_snapshot.record --fresh`, chế độ
  `inprocess`, Postgres và Weaviate local, LLM thật theo `.env` (chung `gpt-6-luna`, orchestrator `gpt-6.1-sol`).
  Đồng hồ đứng yên ở 2026-10-13, ngân sách lượt 600 giây.
- Kết quả ghi: 63 kịch bản, 191 lượt; cassette LLM 347 mục, cassette tool 135 mục. Không kịch bản nào bị từ chối vì lượt
  không phát lại được. Log ghi không có dòng `ERROR`.
- Sau đó harness giữ thêm mã `ROUND_LIMIT`/`TOOL_LIMIT` trong event. Snapshot được dựng lại từ cassette, không gọi LLM;
  so với bản vừa ghi, chỉ thêm trường `reason`.
- Phát lại offline: `.venv/bin/python -m pytest -q src/backend/tests/unit/agents/test_behavior_snapshot.py` → 4 passed,
  `cassetteMiss` và `toolMiss` rỗng.
- Bản trước: snapshot luồng cũ (cờ tắt) tại `a50c5e62`, 57 kịch bản, 166 lượt. Sáu kịch bản `demo-K1`…`demo-K6` mới
  thêm nên không có bản trước.

**Caveat:**
- Mỗi kịch bản ghi **một lần** với LLM thật. Khác biệt của một lượt có thể là do lần ghi, không phải do kiến trúc. Lỗi
  lặp lại ở nhiều kịch bản (nút, đổi sau lịch, vé nhiều điểm đến) thì đáng tin; lỗi chỉ thấy một lần thì cần chạy lại ở
  D5 trước khi sửa.
- Luồng cũ cũng không đạt hết AC. "Trước tốt hơn" không có nghĩa là trước đạt AC.

## Số tổng (57 kịch bản có bản trước, 166 lượt)

| Chỉ số | Luồng cũ | Orchestrator |
|---|---|---|
| Lượt `COMPLETED` | 23 | 17 |
| Lượt `NEEDS_CLARIFICATION` | 142 | 148 |
| HTTP | 200, 400 | 200, 400 |
| Nút trung bình mỗi lượt `NEEDS_CLARIFICATION` | 2,23 | 1,00 |
| Lượt `NEEDS_CLARIFICATION` không có nút | 13 | 39 |
| Lượt `NEEDS_CLARIFICATION` có thẻ | 66 | 72 |
| Số thẻ trung bình (lượt có thẻ) | 3,38 | 3,00 |
| Số từ trung vị: `NEEDS_CLARIFICATION` / `COMPLETED` | 49 / 337 | 45 / 316 |
| Lượt chạm `TOOL_LIMIT` (cả 63 kịch bản) | — | 6 |

Bảy kịch bản giống hệt (guardrail, tin rác, ngoài cửa sổ ngày…): X05, X06, X09, messy-M09, review-R08, v5-SC-H, v5-SC-H3.

## Lỗi mới hoặc rộng hơn so với D1

Mức độ theo plan D1. Mã D1-xx: `eval-2026-10-13-demo-orchestrator.md`.

| Mã | Triệu chứng | Hội thoại | AC | Mức |
|---|---|---|---|---|
| D3-01 | Sau câu hỏi lại "nghỉ ở đâu?", người dùng trả lời "Đà nẵng". Orchestrator khám phá Đà Nẵng mà không ghi điểm đến, nên lượt sau hỏi lại điểm đến. Nghi ngờ (đọc code, chưa kiểm): lượt 1 đã đồng ý lập lịch, mà `run_jobs_node` chỉ ghi điểm đến khám phá vào `intent` khi chưa đồng ý | tc-TC-03 | AC-AGT-01 (giữ thông tin đã biết, không lặp câu hỏi) | chặn demo |
| D3-02 | "huỷ đơn hôm qua đc ko" bị hỏi "chuyến đi kéo dài mấy ngày?". Trước: nói không huỷ thay được, chỉ "Lịch sử đặt chỗ" | messy-M14 | AC-AGT-07 Ngoài phạm vi | xấu |
| D3-03 | "mình không biết đi đâu hết, mình ở nhà" bị coi là dừng, chào tạm biệt | v5-SC-MAIN | AC-AGT-01 (dừng chỉ khi không muốn đi) | xấu |
| D3-04 | Chê nơi vừa gợi ý ("chỗ khác đi", "không thích Nha Trang"): chỉ hỏi chọn 3 nơi bằng chữ, 0 thẻ, 0 nút. Trước: tự đổi hướng, 4 thẻ | X13, messy-M02, tc-TC-13, v5-SC-A, demo-K5 | AC-AGT-07 Khó tính | xấu |
| D3-05 | "xung quanh đó ăn gì ngon": chỉ nói chưa tìm được, không làm phần kiểm được | messy-M03 | AC-AGT-07 Giọng điệu | nhỏ |
| D1-07 rộng hơn | Không chỉ lượt mơ hồ. Chào hỏi, "không biết", ngoài phạm vi, câu hỏi chọn nơi ("Hà Nội hay Hội An?", "Thiên Mụ hay…?", "điểm đến nào?") đều 0 nút; lượt khám phá thường chỉ còn nút lập lịch | 39 lượt | AC-AGT-07 Nút (ít nhất hai hướng) | xấu |
| D1-04 rộng hơn | Đổi khách sạn có hướng sau khi có lịch ("rẻ hơn", "có hồ bơi", "gần biển hơn") không đi luồng đổi: orchestrator khám phá rồi nói chưa có phương án, lịch giữ nguyên | X11, messy-M11, demo-K3, demo-K6 | AC-AGT-05 | chặn demo |
| D1-02 (T1) xác nhận | Vé "đi đâu cũng được" chạm `TOOL_LIMIT` (10 lời gọi), trả "chưa thấy chuyến bay còn vé nào". Phát lại được | demo-K2, messy-M06, review-R07 (2 lượt), v5-SC-F | AC-AGT-08; invariant thất bại khác không có | chặn demo |

Orchestrator làm tốt hơn luồng cũ:
- Hỏi vé thì trả lời bằng vé thật, thay vì hỏi loại vé hay nói không kiểm được (X01, X02).
- Nêu một nơi chưa đồng ý lập lịch thì khám phá có thẻ, thay vì hỏi thông tin chuyến (X10, messy-M01, M07, M13,
  review-R01, tc-TC-02).
- "Khách sạn ở Sầm Sơn" tìm được khách sạn; luồng cũ nói không có (review-R06).
- "đặt giúp tao cái ks" nói rõ không đặt thay được và đưa 3 khách sạn (messy-M14 L2).

## Từng hội thoại

"Nút" là số nút gợi ý; "ít nút" nghĩa là giảm ở lượt khám phá hoặc trò chuyện (D1-07) hoặc ở câu vé (D1-06).

| Hội thoại | Lượt khác (trước → sau) | Đánh giá |
|---|---|---|
| X01-plan-doi | L4 COMPLETED → hỏi lại, thẻ 2→0; L6 thẻ 0→1; nút ít hơn | L4 "đổi chuyến bay": lịch không có chuyến bay (tiền vé 0), nên không có chuyến để đổi; hỏi lại đổi ngày hay tuyến là chấp nhận được. Trước: lập lại lịch, vẫn không có vé. L6 tốt hơn: vé thật |
| X02-ve | L1–L2 thẻ 0→1; L3 thẻ 4→1; nút ít hơn | Tốt hơn: trả lời vé thật. Ít nút (D1-06) |
| X03-ve-thieu | L4 nút 3→1 | Ít nút (D1-06) |
| X04-dong-y | L1–L2 nút →0; L4 thẻ 4→5; L6 hoạt động 6→5 | Chào và "không biết" 0 nút: không đạt AC-AGT-07 Nút (D1-07). Lịch hợp lệ |
| X05-guardrail | — | Giống |
| X06-rac | — | Giống |
| X07-ngoai-pham-vi | L1 nút 2→0 | Ngoài phạm vi 0 nút: không đạt AC-AGT-07 (D1-07) |
| X08-form | L2 nút 2→0 | Form hiện ngay: đạt AC-AGT-01 |
| X09-ngoai-cua-so | — | Giống |
| X10-ngoai-catalog | L2 thẻ 0→5 | Tốt hơn: "Đà Lạt có gì" khám phá thay vì hỏi thông tin chuyến |
| X11-dai-ngay | L3 COMPLETED → hỏi lại; L1 hoạt động 4→6 | L3 "đổi khách sạn rẻ hơn" không đổi lịch: không đạt AC-AGT-05 (D1-04) |
| X12-chon-the | L2–L3 COMPLETED → hỏi lại | Chọn phương án khi lượt 1 chưa có lịch: hỏi "phương án nào". Chấp nhận được, vì không có phương án để chọn |
| X13-che | L3 thẻ 4→0, nút 3→0; nút ít hơn | "chỗ khác đi" chỉ hỏi chọn (D3-04) |
| X14-chip | L2 hoạt động 2→3 | Lịch hợp lệ |
| messy-M01 | L2 thẻ 0→3; L1 nút 3→0 | Tốt hơn ở L2. "hi" 0 nút (D1-07) |
| messy-M02 | L2 thẻ 4→0, nút 3→0; L3 thẻ 0→1 | "chán, chỗ khác" chỉ hỏi chọn (D3-04) |
| messy-M03 | L4 thẻ 3→0 | "ăn gì ngon" không làm phần kiểm được (D3-05) |
| messy-M04 | L3 thẻ 4→1 | Ít thẻ (D1-08), ít nút |
| messy-M05 | nút ít hơn | Ít nút |
| messy-M06 | nút →0 | Vé "đi đâu cũng được" chạm `TOOL_LIMIT`, nói không có chuyến (T1; luồng cũ cũng 0 thẻ). L2 hệ quả: không biết "chỗ đó" |
| messy-M07 | L1 thẻ 0→4; L3 thẻ 4→2 | Tốt hơn: "ks gần biển" có thẻ ngay |
| messy-M08 | L1 nút 2→0 | "gần phố cổ" hỏi Hà Nội hay Hội An bằng chữ, 0 nút: không đạt (plan mục 1.5, D1-07) |
| messy-M09 | — | Giống |
| messy-M10 | L4 hoạt động 5→3; L5 4→3 | Lịch hợp lệ, ít hoạt động hơn |
| messy-M11 | L4 COMPLETED → hỏi lại | "đổi ks rẻ hơn đi" không đổi lịch: không đạt AC-AGT-05 (D1-04) |
| messy-M12 | L1 thẻ 4→7 | Câu ba ý chạm `TOOL_LIMIT` nhưng vẫn trả đủ ba phần |
| messy-M13 | L3 thẻ 0→5; L1 nút 2→0 | Tốt hơn: "hn" khám phá thay vì hỏi số ngày |
| messy-M14 | L2 thẻ 0→3; L3 nút 2→0 | L2 tốt hơn. L3 "huỷ đơn" bị hỏi số ngày (D3-02) |
| messy-M15 | nút ít hơn | Ít nút |
| messy-M16 | L1 nút 3→0 | Câu đủ người, ngày, sở thích chỉ được hỏi "điểm đến nào?", không nút. Trước: gợi ý 4 nơi biển kèm nút (D1-07) |
| review-R01 | L3 thẻ 0→5 | Tốt hơn: "Huế" khám phá |
| review-R02 | nút ít hơn | Ít nút |
| review-R03 | L2 thẻ 3→2; nút ít hơn | Ít nút |
| review-R04 | L1–L2 nút 2→0 | "chùa thiên mậu" hỏi lại bằng chữ, không nút; trước có nút Thiên Mụ (D1-07) |
| review-R05 | L2–L3 thẻ 4→1 | Ít thẻ (D1-08), ít nút |
| review-R06 | L1 thẻ 0→1 | Tốt hơn: Sầm Sơn có khách sạn; trước nói không có |
| review-R07 | L2 thẻ 4→0; nút →0 | "Vé máy bay rẻ nhất" chạm `TOOL_LIMIT`, nói không có chuyến; trước tìm được (T1, chặn demo) |
| review-R08 | — | Giống |
| tc-TC-01 | L3 hoạt động 1→2 | Lịch hợp lệ |
| tc-TC-02 | L1 thẻ 0→3; L2 nút 3→0 | Tốt hơn ở L1. "ko biết đi đâu" 0 nút (D1-07) |
| tc-TC-03 | L2 thẻ 0→3; L3 COMPLETED → hỏi lại | Hỏi lại điểm đến đã nói (D3-01, chặn demo) |
| tc-TC-04 | nút ít hơn | Ít nút |
| tc-TC-10 | L2 nút 2→1 | Ít nút |
| tc-TC-11 | L2 hoạt động 4→5 | Lịch hợp lệ |
| tc-TC-12 | L1 thẻ 4→3 | Ít nút |
| tc-TC-13 | L2 thẻ 4→0, nút 3→0; L3 nút 2→0 | "chán, Đà Nẵng đi rồi" chỉ hỏi chọn (D3-04). Đặt vé 0 nút (D1-07) |
| tc-TC-14 | L1 hoạt động 5→3 | Lịch hợp lệ, ít hoạt động hơn |
| v5-SC-A | L2 thẻ 4→0, nút 3→0 | "không thích đi Nha Trang" chỉ hỏi chọn (D3-04) |
| v5-SC-B | nút ít hơn | "Văn Miếu tối có mở" trả lời được, 0 nút (D1-07) |
| v5-SC-C | nút ít hơn | Ít nút |
| v5-SC-E | L2 nút 3→1 | Ít nút |
| v5-SC-F | L2 thẻ 4→0 | "đi đâu cũng được, đắt nhất" chạm `TOOL_LIMIT`, nói không có chuyến; trước tìm được (T1) |
| v5-SC-G | L1 nút 2→0; L2 thẻ 4→2 | "hồ bơi gần phố cổ" hỏi bằng chữ, 0 nút (D1-07) |
| v5-SC-H | — | Giống |
| v5-SC-H3 | — | Giống |
| v5-SC-MAIN | nút ít hơn; L2 nút 2→0 | "không biết đi đâu, mình ở nhà" bị coi là dừng (D3-03) |
| v5-SC-OUT | L1 nút 2→0 | Ngoài phạm vi 0 nút (D1-07) |
| demo-K1 (mới) | — | L3–L4 "gần Hồ Gươm", "rẻ hơn" 0 thẻ (D1-01). L5 hỏi ngân sách (D1-11). L6 chọn phương án khi chưa có lịch (D1-12) |
| demo-K2 (mới) | — | L3 chạm `TOOL_LIMIT`, nói không có chuyến (D1-02) |
| demo-K3 (mới) | — | L1, L4 có lịch. L2 "đổi sang khách sạn có hồ bơi" khám phá thay vì đổi (D1-04). L3 "bỏ vé" chỉ trả lời (D1-05) |
| demo-K4 (mới) | — | L2 "xem thêm" 1 thẻ (D1-08). L4 câu dự phòng 7 từ (D1-03) |
| demo-K5 (mới) | — | L3 "chán, đi rồi" 0 thẻ, 0 nút (D3-04, D1-07). L4 hỏi gộp 5 thông tin |
| demo-K6 (mới) | — | L2 có lịch. L3 "gần biển hơn" khám phá, không đổi lịch (D1-04) |

## Lệnh tái sinh

```bash
docker compose up -d --wait postgres weaviate
HF_HUB_OFFLINE=1 .venv/bin/python -m src.backend.tests.unit.agents.behavior_snapshot.record --fresh   # ghi lại, LLM thật
.venv/bin/python -m pytest -q src/backend/tests/unit/agents/test_behavior_snapshot.py               # phát lại offline
```

Bảng so sánh dựng bằng script ở scratchpad của phiên, đọc `snapshot.json` của `a50c5e62` và bản mới. Các cột lấy từ
`response.status`, `searchResults`, `suggestions`, `itinerary.days[].slots`, `message`/`question`.
