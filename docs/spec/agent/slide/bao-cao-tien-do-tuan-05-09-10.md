# Itinerary Agent — báo cáo tiến độ tuần 05–09/10/2026

- Người trình bày: Nguyễn Minh Nhật (phụ trách agent)
- Phục vụ: FR-AGT-01..05, NFR-REL-01, NFR-PERF-02, AC-AGT-02..04 (báo cáo tiến độ, không đổi yêu cầu).
- Ngày soạn: 2026-10-09. Nguồn để làm slide demo tiến độ.
- Phạm vi: nhánh `feat/agent`, từ thứ 7 03/10 đến 09/10. Thứ 7 và CN không có commit, nên số liệu thực tế là 05–09/10.
- Nguồn:
  - `git log`, các entry `history/2026-10-0*`, đề xuất trong `docs/prd/update-archive/` và `docs/prd/update/`;
  - LangSmith, các project `nhat-10-1`, `nhat-agent-tc`, `nhat-10-7`, lấy từ 05/10 đến 09/10 07:33 UTC;
  - biên bản runner trong `.logs/agent-eval/` và `src/evaluation/reports/`.

---

## Phần A — Dàn ý slide (bản 2, đã bỏ 3 slide theo góp ý)

| # | Slide | Ý chính |
|---|---|---|
| 1 | Tiêu đề | Itinerary Agent — tuần 05–09/10 |
| 2 | Vấn đề đầu tuần | Lỗi thấy trong trace thật: chưa có vé bay, lịch đi xa, điểm trùng, chọn phương án chậm |
| 3 | Vé máy bay trong lịch | Chặng đi/về lấy từ catalog, hỏi nơi đi, xếp lịch theo giờ bay |
| 4 | Lịch ít di chuyển | Gom các điểm gần nhau; Phú Quốc 149,7 → 15,6 km (số mô phỏng) |
| 5 | Khách sạn theo ngân sách | Luôn kèm "thêm X ₫ → bớt Y km"; 100% mẫu vừa ngân sách |
| 6 | Chọn phương án bằng hàng thẻ | 91 lượt thật: p50 0,04 s, trước đây khoảng 15 s |
| 7 | Lịch sạch hơn | Ví dụ VinWonders, Hòn Thơm; 129 mục trùng bị loại; đoàn đông tính theo số phòng |
| 8 | Trình bày kết quả | Km tính cả chặng sân bay, bản đồ, Ngân sách dự tính, thẻ vé, lịch sử hội thoại |
| 9 | Đánh giá (số từ LangSmith) | Grounding 100%; lượt lập lịch p50 16,5 s, mục tiêu dưới 5 s |
| 10 | Rủi ro và việc còn nợ | Latency; nhiều thay đổi ngày 09/10 chưa chạy E2E |
| 11 | Chờ chốt và tuần tới | 3 đề xuất agent đang chờ chốt |
| 12 | Demo trực tiếp | Kịch bản 4 bước |

Đã bỏ: "Tuần này trong một slide", "Hiểu ý và hỏi lại", "Công cụ cho dev".

---

## Phần B — Nội dung từng slide

### Slide 2 — Vấn đề đầu tuần (từ trace LangSmith thật)

| Vấn đề | Ví dụ |
|---|---|
| Lịch không có vé máy bay | Chưa có trường nơi đi |
| Hai điểm cách nhau 40 km xếp cùng một ngày | Bắc và Nam Phú Quốc |
| Hoạt động xếp trước giờ hạ cánh | Bay 19:50 ngày 1 mà Bà Nà vẫn ở buổi sáng ngày 1 |
| Điểm trùng | Phú Quốc 3 ngày: 5/6 buổi trùng nơi (Hòn Thơm, Water Taxi) |
| Chọn phương án chậm, kết quả lệch | Nhắn "lấy phương án 1" là chạy lại cả luồng, khoảng 15 s, số khác số đã báo |
| Đoàn đông chỉ ra một khách sạn | 10 người lớn: search hiểu là một phòng 10 người nên trả 0 khách sạn |

### Slide 3 — Vé máy bay trong lịch (06–07/10)

- Lịch có chặng đi và chặng về. Vé được chọn bằng luật từ chuyến bay thật trong catalog; LLM không tạo vé.
- Câu hỏi gộp có thêm nơi đi. Khách có thể bấm "Dùng vị trí hiện tại"; trình duyệt chỉ xin quyền khi khách bấm.
- Khách không cho nơi đi thì agent vẫn lập lịch, kèm lời mời cho biết nơi đi để thêm vé.
- **Xếp lịch theo giờ bay.** Ví dụ thật: VJ505 hạ cánh 21:10.
  - Ngày 1 chỉ còn "Di chuyển từ sân bay, nhận phòng".
  - Ngày cuối có "Ra sân bay", chừa 150 phút trước giờ bay.
- Query gửi Search không còn chứa ngân sách, ngày, số người. Trước đây "ngân sách 5 triệu" bị hiểu thành trần giá của
  **từng sản phẩm**.

### Slide 4 — Lịch ít di chuyển (07/10)

- Mỗi ngày gom các điểm gần nhau. Khách sạn được chọn **sau** hoạt động, theo khoảng cách tới các điểm.
- Tối ưu tổng quãng đường:
  - ngày 1: điểm sáng → điểm chiều → khách sạn;
  - ngày giữa: khách sạn → các điểm → khách sạn;
  - ngày cuối: khách sạn → các điểm.
- Chuyến từ 5 ngày được đổi khách sạn một lần, mỗi khách sạn ít nhất 2 đêm.
- Phần xếp lịch chạy dưới 200 ms (trước đây tới 950 ms với lịch 7 ngày).
- Mô phỏng tất định: snapshot 30/09, 30 mẫu, lịch 3 ngày.

  | Điểm đến | km/chuyến cũ | km/chuyến mới | Giá hoạt động |
  |---|---|---|---|
  | Phú Quốc | 149,7 | 15,6 | +14% |
  | Nha Trang | 38,4 | 22,3 | +18% |
  | Hà Nội | 58,8 | 49,4 | +17% |
  | Hội An | 80,5 | 76,2 | +2% |

- Lưu ý khi nói: đây là mô phỏng, không phải agent chạy LLM thật. Km là đường chim bay.

### Slide 5 — Khách sạn theo ngân sách, luôn có phương án khác (08/10)

- Vấn đề sau slide 4: ưu tiên gần làm tiền khách sạn tăng mạnh. Trung vị gấp 4,9 lần khách sạn rẻ nhất, có mẫu gấp
  37 lần.
- Đã thử quy đổi km ra tiền rồi bỏ. Luật đã chốt: **ưu tiên gần, nhưng phải vừa ngân sách**.
- Câu trả lời luôn có phương án khác dạng **"thêm X ₫ → bớt Y km"**. Số tiền và số km do code tính, không qua LLM.
- Bench trên catalog staging 07/10 (14.935 sản phẩm, 30 mẫu mỗi ô):
  - 100% mẫu vừa ngân sách;
  - 60–97% mẫu có phương án khác. Huế 0%, vì khách sạn ở đó chỉ có toạ độ tâm thành phố.

### Slide 6 — Chọn phương án bằng hàng thẻ (08/10)

- Mục "Nơi nghỉ" là một hàng thẻ khách sạn lướt ngang, tối đa 3 thẻ.
  - Chạm thẻ: cột phải và bản đồ xem trước lịch của phương án đó.
  - Bấm "Đổi": lịch đổi ngay, không sinh thêm tin nhắn.
- Lịch của từng phương án được dựng sẵn lúc lập lịch, nên khi khách chọn thì không gọi LLM và không tìm lại.
- **Số từ LangSmith:**
  - **91 lượt chọn phương án** (08–09/10): p50 0,04 s, p95 0,17 s, chậm nhất 0,79 s;
  - trước đây mỗi lần chọn chạy lại cả luồng, khoảng 15 s; lượt lập lịch hiện có p50 16,5 s.
- Chọn lại thẻ cũ thì về đúng số ban đầu. Ví dụ: 33,1 km, 23.001.910 ₫.

### Slide 7 — Lịch sạch hơn (08–09/10)

**Node `filter` bỏ điểm trùng trước khi xếp lịch.**
- Luật cùng tên chạy trước. Sau đó LLM chỉ ra các cặp trùng.
- LLM chỉ thấy mã và tên sản phẩm. Cặp có mã lạ bị bỏ qua, nên grounding vẫn 100%.

**Ví dụ thật từ trace (LangSmith `nhat-10-7`):**

| Lịch cũ có cả hai | Giữ lại | Ai phát hiện |
|---|---|---|
| "hòn Thơm" (điểm tự do, 0 đ) và "Cáp Treo Hòn Thơm" | Cáp Treo Hòn Thơm (giữ vé có phí) | LLM |
| "hòn Thơm", "Sun World Hòn Thơm" và "Cáp Treo Hòn Thơm" | 1 trong 3 | LLM |
| "[VinWonders Phú Quốc] Vé Vào Cửa Tiêu Chuẩn" và "Vé Vào Cửa + Buffet 350k" | 1 vé VinWonders | LLM |
| "[VinWonders Phú Quốc] Vé Vào Cửa Tiêu Chuẩn" và "Vé Vào Cửa + Mũ Thú + Voucher Ẩm Thực" | 1 vé VinWonders | LLM |
| Hai vé "[Grand World] Vé đi thuyền Venice (Water Taxi)" khác mã | 1 vé | Luật cùng tên |
| "[02 ngày] VinWonders + Vinpearl Safari…" và "[02 ngày] Vinpearl Safari + VinWonders…" | 1 gói | Luật đảo thứ tự tên |

- **Số từ LangSmith:** 24 lượt lập lịch có chạy `filter`. Tổng cộng 129 mục trùng bị loại: 62 do luật, 67 do LLM.
- Cái giá: `filter` mất p50 3,1 s mỗi lượt lập lịch.
- **Sửa thêm:**
  - Search lấy 50 kết quả thay vì 10, để lịch 7 ngày có cả buổi chiều.
  - Đoàn đông (10 người lớn): search lọc theo sức chứa một phòng, tiền khách sạn nhân theo số phòng. Trước đây trả 0
    khách sạn.
  - Ngày bay của combo trip.com ("15/10") được chuẩn hoá về ISO. Lỗi này từng làm lịch TP.HCM không dựng được.

### Slide 8 — Trình bày kết quả (07–09/10)

- Km tính cả chặng sân bay ↔ khách sạn. Mọi số km có dấu "≈" và một dòng lưu ý.
- Bản đồ xem trước cả chuyến: có sân bay, chỉ hiện khách sạn của phương án đang xem, đường vẽ dần.
- Khối "Ngân sách dự tính" chia theo Vé máy bay, Lưu trú, Vui chơi.
- Thẻ vé máy bay hiện ngay trong chat.
- Mục "Cách mình xếp lịch" giải thích tiêu chí. Mục này do code viết, không phải LLM.
- Lịch sử hội thoại lấy từ backend: tải lại trang hay mở tab mới vẫn mở lại được hội thoại cũ.

### Slide 9 — Đánh giá (số đo từ LangSmith)

**Latency theo loại lượt.** Lượt chạy tay qua web (`nhat-10-1`, `nhat-10-7`), 05–09/10, không tính 12 lượt khách bấm
Dừng:

| Loại lượt | Số lượt | p50 | p95 |
|---|---|---|---|
| Lập lịch (có `compose`) | 58 | 16,5 s | 25,3 s |
| Hỏi lại, hiện form (`clarify`) | 106 | 7,7 s | 11,7 s |
| Trò chuyện (`converse`) | 23 | 4,6 s | 6,5 s |
| Chọn phương án (`apply_option`) | 91 | 0,04 s | 0,17 s |
| Lỗi, rơi vào `dead_letter` | 6 | 14,0 s | 16,6 s |

- Mục tiêu dưới 5 s (`test-plan.md` §2.4, không chặn release). Chỉ chọn phương án và trò chuyện đạt mục tiêu này.

**Thời gian từng node trong lượt lập lịch** (84 lượt, gồm cả lượt golden):

| Node | p50 | p95 |
|---|---|---|
| `narrate` (LLM viết lời) | 6,0 s | 10,1 s |
| `tool` (Search, Recommendation) | 3,3 s | 8,3 s |
| `filter` (LLM tìm cặp trùng) | 3,1 s | 11,5 s |
| `extract` | 2,8 s | 4,5 s |
| `classify` | 2,0 s | 4,0 s |
| `compose` (xếp lịch) | < 0,1 s | < 0,1 s |

- Gần hết thời gian là chờ LLM và search. Phần xếp lịch gần như không tốn thời gian.
- Sau khi thêm `filter`, p50 lượt lập lịch tăng từ 15,6 s (60 lượt) lên 17,4 s (24 lượt).

**Bộ test case (golden).**
- LangSmith có 72 lượt golden: 05/10 (TC-01..04, TC-10), 06/10 (TC-01, TC-03) và 08/10 (TC-11).
  - Lượt lập lịch: 26 lượt, p50 14,4 s, p95 20,6 s.
  - Lượt hỏi lại: 46 lượt, p50 6,3 s, p95 9,0 s.
- PASS/FAIL lấy từ biên bản runner, vì LangSmith không lưu kết quả chấm:

  | Lần chạy | Kết quả | Ghi chú |
  |---|---|---|
  | 05/10 16:28, cả bộ | 11/14 | Fail TC-03, TC-04, TC-10 |
  | 05/10 22:09, cả bộ | 13/14 | Còn fail TC-04 lượt 3 |
  | 05/10, cả bộ chạy 3 lần | 41/42 | Fail TC-04 lượt 3 một lần |
  | 08/10, TC-11 chạy 3 lần | 3/6 | Hết trùng cả 3 lần; 3 fail do kiểm tra cũ "khách sạn = rẻ nhất" đã lỗi thời |

- Mọi lần chạy đều có Grounding 100%, Structured Output 100%, Tool Calling 100%.
- Cách tính: lấy root run theo tag; phân loại lượt theo node có trong trace (`compose`, `clarify`, `converse`,
  `apply_option`, `dead_letter`); p50 và p95 nội suy tuyến tính. Script đo chạy ngoài repo, chưa commit.

### Slide 10 — Rủi ro và việc còn nợ

- **Latency lượt lập lịch p50 16,5 s**, gấp hơn 3 lần mục tiêu. Hướng xử lý:
  - rút ngắn hoặc stream `narrate`;
  - chạy `filter` song song với việc khác, hoặc chỉ gọi LLM khi luật chưa đủ.
- Nhiều thay đổi ngày 09/10 mới qua unit test, chưa chạy E2E với LLM thật:
  - km tính cả sân bay;
  - đoàn đông;
  - search lấy 50 kết quả.
- Km là đường chim bay; đường bộ thật (OSRM) để sau.
- Khách sạn chỉ có toạ độ tâm thành phố (như ở Huế) thì không có phương án khác.
- Golden chưa có case cho chọn phương án, lọc trùng giữ vé, và chuyến hạ cánh muộn. Kiểm tra "khách sạn = rẻ nhất"
  trong eval đã lỗi thời.
- Chưa chạy lại cả bộ golden sau các thay đổi từ 07/10.

### Slide 11 — Chờ chốt và tuần tới

| Đề xuất (`docs/prd/update/`) | Nội dung |
|---|---|
| `2026-10-08-ung-vien-da-dang-va-diem-mien-phi` | Lấy đủ điểm tham quan của điểm đến, mỗi địa điểm một vé, có điểm miễn phí |
| `2026-10-09-hoi-dap-doi-ve-khach-san-sau-lich` | Sau khi có lịch, hỏi và đổi vé hoặc khách sạn mà không lập lịch lại |
| `2026-10-05-go-golden-dataset-cu` | Gỡ golden cũ, giữ bộ TC làm benchmark của agent |

Tuần tới:
- chạy lại cả bộ golden với LLM thật, viết report;
- giảm latency lượt lập lịch;
- thêm golden case cho các tính năng mới.

### Slide 12 — Demo trực tiếp (gợi ý kịch bản)

1. "Lên lịch trình 3 ngày ở Đà Nẵng, 2 người lớn, ngân sách 10 triệu, đi từ Hà Nội". Chỉ ra: vé đi/về, ngày 1 chỉ có nhận
   phòng, khối Ngân sách dự tính.
2. Chạm một thẻ ở "Nơi nghỉ" để xem trước bản đồ và chênh tiền/km. Bấm "Đổi" để thấy lịch đổi ngay.
3. "Phú Quốc 3 ngày" để cho thấy không còn Hòn Thơm hay VinWonders trùng.
4. Tải lại trang, mở "Lịch sử trò chuyện" để mở lại hội thoại.

Chuẩn bị trước:
- khởi động lại backend với code mới;
- kiểm tra key LLM còn hạn mức;
- chạy thử cả 4 bước một lần trước giờ demo.

---

## Phụ lục — commit theo ngày

| Ngày | Commit chính |
|---|---|
| T3 06/10 | `70c096a7` lỗi Cohere không còn im lặng |
| T4 07/10 | `e7d000b0` vé máy bay, xếp lịch theo giờ bay · `8365c7c2` lịch sử hội thoại · `16bb5bf9` lịch ít di chuyển |
| T5 08/10 | `8ab44dc5` nhiều khách sạn, ngân sách, phương án khác · `d57eea3f` search đủ tham số · `4ebd6420` ngày combo ISO · `d8791cd1` hàng thẻ phương án |
| T6 09/10 | `b63bdcd2` node filter · `0b503e89` giữ vé, km sân bay, bản đồ, ngân sách, thẻ vé · `ff2e598b` gói đảo tên · `ab5c597d` search 50 · `682d8684` đoàn đông theo số phòng |
