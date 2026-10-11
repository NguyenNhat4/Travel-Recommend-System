# Nghiệp vụ Itinerary Agent — đọc nhanh

Phục vụ FR-AGT-01..07, AC-AGT-01..08, NFR-REL-01 (`docs/prd/requirements.md`). Cập nhật theo code tại 2026-10-11.

Bộ tài liệu này dành cho dev mới, hoặc cho chính mình khi quay lại sau một thời gian. Nó trả lời trợ lý lập lịch trình
**đang làm gì** và **theo luật nào**, không giải thích cách cài đặt. Mỗi file có mục "Code liên quan" để mở tiếp.

- **Nguồn sự thật là code** tại ngày ghi ở đầu file. Khi lệch nhau thì PRD (`docs/prd/`) và contract
  (`src/shared/contracts/`) thắng, không phải bộ này.
- **⚠️ cần xác nhận** đánh dấu chỗ code mâu thuẫn với PRD, dang dở, hoặc chưa rõ ý đồ. Đừng coi là luật.
- **Mỗi khái niệm chỉ mô tả ở một file.** Nơi khác link tới đó; tra nhanh nghĩa ở [glossary.md](glossary.md).

## Bản đồ trong một hình

```mermaid
flowchart LR
    U([Tin nhắn]) --> G{Đồng ý<br/>lập lịch chưa?}
    G -- chưa --> TK[Trò chuyện,<br/>khám phá]
    TK --> TKO([Thẻ + nút +<br/>lời mời lập lịch])
    U --> V{Hỏi giá vé?}
    V -- có --> TV[Tư vấn vé]
    TV --> TVO([Câu gọn +<br/>thẻ ngày–giá])
    G -- rồi --> H[Hỏi gộp,<br/>form]
    H -- đủ --> T[Tìm và lọc<br/>ứng viên]
    T --> VE[Chọn vé]
    T --> X[Xếp lịch,<br/>tính tiền]
    VE --> X
    X --> D[Diễn giải,<br/>kiểm tra]
    D --> O([Lịch trình])
    O -.->|đổi vé, khách sạn,<br/>phương án N| S[Sửa lịch]
    S --> X
```

Ba câu cần nhớ:

1. **Chưa đồng ý thì không hỏi thông tin chuyến.** Trợ lý gợi ý, giới thiệu bằng thẻ thật, rồi mời lập lịch (FR-AGT-06).
2. **Hỏi vé thì trả lời, không lập lại lịch.** Có thể hỏi trước hoặc sau khi có lịch (FR-AGT-07).
3. **LLM hiểu câu chữ và viết lời; code chọn sản phẩm, giá, vé và xếp lịch.** Mọi thứ trả ra đều qua `finalize` kiểm
   grounding (NFR-REL-01).

## Thứ tự đọc

| # | File | Đọc để biết |
|---|---|---|
| 1 | [glossary.md](glossary.md) | Thuật ngữ |
| 2 | [vong-doi-mot-luot.md](vong-doi-mot-luot.md) | Một tin nhắn đi qua 15 node nào, ra kết quả gì |
| 3 | [tro-chuyen-va-kham-pha.md](tro-chuyen-va-kham-pha.md) | Trước khi đồng ý lập lịch: trò chuyện, khám phá, khi nào là đồng ý |
| 4 | [hieu-y-dinh-va-hoi-lai.md](hieu-y-dinh-va-hoi-lai.md) | Sau khi đồng ý: trường bắt buộc, hỏi gộp, form |
| 5 | [tu-van-ve-may-bay.md](tu-van-ve-may-bay.md) | Hỏi giá, giờ vé máy bay |
| 6 | [tim-ung-vien.md](tim-ung-vien.md) | Gọi tool nào, lọc ứng viên, khi nào `NO_RESULTS`/`FALLBACK` |
| 7 | [ve-may-bay.md](ve-may-bay.md) | Vé tự chọn trong lịch, lý do thiếu vé |
| 8 | [xep-lich.md](xep-lich.md) | Chỗ ở, hoạt động, buổi, giờ bay, tiền, lịch tham khảo |
| 9 | [dien-giai-va-kiem-tra.md](dien-giai-va-kiem-tra.md) | LLM viết gì, code điền gì, `finalize` chặn gì |
| 10 | [sua-lich-qua-nhieu-luot.md](sua-lich-qua-nhieu-luot.md) | Nhớ gì giữa các lượt, đổi khách sạn, đổi vé, chọn phương án |

## Tổng hợp ⚠️ cần xác nhận

| Chỗ | File |
|---|---|
| Lọc theo ngày chỉ so ngày khởi hành, không theo ngày dùng thật | [tim-ung-vien.md](tim-ung-vien.md) |
| Vé được tra và chọn lại mọi lượt; AC-AGT-02 nói chỉ khi chuyến đi đổi hoặc người dùng chọn chuyến khác | [ve-may-bay.md](ve-may-bay.md) |
| Không có vé thì buổi không có khung giờ, không kiểm thời lượng | [xep-lich.md](xep-lich.md) |
| Toạ độ tâm thành phố, km đường chim bay, LLM lọc trùng không tất định | [xep-lich.md](xep-lich.md) |
| Chọn phương án có hai khách sạn chỉ giữ được khách sạn đêm 1 | [sua-lich-qua-nhieu-luot.md](sua-lich-qua-nhieu-luot.md) |
| `expires_at` của hội thoại không được dùng khi khôi phục | [sua-lich-qua-nhieu-luot.md](sua-lich-qua-nhieu-luot.md) |

## Tài liệu khác

- Kỹ thuật graph, node, trace, guardrail: [../langgraph-nodes.md](../langgraph-nodes.md), [../state-fields.md](../state-fields.md)
- Hợp đồng API và tool: [../../hop-dong-tich-hop-itinerary-assistant.md](../../hop-dong-tich-hop-itinerary-assistant.md)
- Widget hiển thị: [../../../guide/doc-code-ui-tro-ly.md](../../../guide/doc-code-ui-tro-ly.md)
- Sửa, tune, đánh giá agent: [../working-context.md](../working-context.md)
