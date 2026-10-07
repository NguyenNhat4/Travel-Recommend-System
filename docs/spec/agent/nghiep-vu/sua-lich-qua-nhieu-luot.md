# Hội thoại nhiều lượt và sửa lịch

Phục vụ FR-AGT-01, FR-AGT-05. Mô tả theo code tại 2026-10-07; khi lệch, PRD và contract thắng.

## Mục đích

Người dùng nói tiếp trên cùng một hội thoại: trả lời câu hỏi, đổi ngày/số ngày/điểm đến, đổi một sản phẩm. Trợ lý nhớ
chuyến đi đã chốt và chỉ sửa phần người dùng đổi.

## Luồng chính

```mermaid
sequenceDiagram
    participant U as Người dùng
    participant G as Graph (một lượt)
    participant S as Store hội thoại
    U->>G: "Đà Nẵng 3 ngày từ 15/10, 2 người"
    G->>S: lưu intent, constraints, lịch sử, sản phẩm đã cho xem
    G-->>U: COMPLETED (khách sạn A, Bà Nà...)
    U->>G: "đổi khách sạn khác" + conversationId
    S-->>G: nạp lại trạng thái lượt trước
    G->>G: extract: loại khách sạn A (exclude_products)
    G->>G: tool: Similar theo khách sạn A + search
    G->>S: lưu trạng thái mới
    G-->>U: COMPLETED (khách sạn B), câu ghi nhận thay đổi
```

## Cái gì được nhớ giữa các lượt

| Lưu | Nội dung |
|---|---|
| `intent`, `constraints` | Chuyến đi và ràng buộc đã chốt |
| Lịch sử chat | Tối đa 20 tin, 8.000 ký tự tổng, 1.000 ký tự mỗi tin; tin trợ lý kèm [ghi chú lượt](glossary.md#ghi-chu-luot) ≤ 300 ký tự |
| [Sản phẩm đã cho xem](glossary.md#previous_selection) | `productId`, tên, loại của chỗ ở và hoạt động trong lịch gần nhất |
| Cờ hỏi | Đã hỏi gộp chưa, số vòng hỏi điểm đến/số ngày |
| Ngôn ngữ | `vi` / `en` |

Chỉ lượt trả 200 mới được lưu.

**Nơi lưu:**
- Store theo `conversationId` + chủ sở hữu: Redis TTL 24 giờ (dev/test dùng bộ nhớ trong).
- Người dùng đăng nhập (có `cdp_user_id`) còn được ghi từng lượt vào bảng `app.conversations` (Postgres). Khi store không
  còn, hội thoại được khôi phục từ đây.

## Business rule

- **Chỉ sửa phần được đổi.** Intent mới = intent cũ + phần LLM trích được lượt này + chip sửa tay (chip thắng).
- **"Đổi ngày" mà chưa nói ngày nào** thì hỏi giá trị mới, giữ intent cũ, không tìm lại. Xem
  [hieu-y-dinh-va-hoi-lai.md](hieu-y-dinh-va-hoi-lai.md).
- **Đổi một sản phẩm:**
  - sản phẩm cũ vào `exclude_products`, nhưng chỉ nhận id có trong sản phẩm đã cho xem;
  - planner được mời dùng Similar với gốc là sản phẩm đó;
  - code luôn giữ một search cho loại đang đổi. Xem [tim-ung-vien.md](tim-ung-vien.md).
- **Ràng buộc tồn tại qua các lượt** cho tới khi người dùng bỏ (`clear_fields`). Loại hàng mà Recommendation tạm loại thì
  không được lưu.
- **Câu ghi nhận thay đổi** do code viết, so intent đầu lượt với intent mới.
- **Ngữ cảnh đưa cho LLM là bản đã diễn giải,** không phải dump thô:
  - một dòng tóm tắt chuyến đi;
  - giai đoạn hội thoại;
  - ghi chú thay cho cả bài lịch trình cũ;
  - câu cuối của trợ lý nguyên văn nếu ≤ 500 ký tự.

  Chi tiết: [../langgraph-nodes.md](../langgraph-nodes.md) mục "Ngữ cảnh cho LLM".
- **Vé được tra lại** ở mọi lượt có tìm sản phẩm. Xem [ve-may-bay.md](ve-may-bay.md).

## Edge case

- `conversationId` không có ở store lẫn bảng hội thoại, hoặc thuộc người khác: 404.
- Lỗi đọc store: coi như không có. Lỗi ghi bảng hội thoại: chỉ log, không làm hỏng lượt.
- Lượt hỏi lại không đổi danh sách sản phẩm đã cho xem; chỉ lượt `COMPLETED` mới thay danh sách này.
- ⚠️ cần xác nhận: bảng hội thoại ghi `expires_at` = 24 giờ sau tin cuối, nhưng lúc khôi phục không lọc theo cột này. Hội
  thoại cũ hơn 24 giờ vẫn khôi phục được, trừ khi có job dọn bảng (chưa thấy trong code agent).

## Code liên quan

- [`agents/nodes.py`](../../../../src/backend/app/agents/nodes.py) — `intake_node_async` (nạp), `finalize_node_async` (lưu)
- [`agents/steps/history.py`](../../../../src/backend/app/agents/steps/history.py) — giới hạn lịch sử, ngữ cảnh cho LLM
- [`agents/steps/turn_notes.py`](../../../../src/backend/app/agents/steps/turn_notes.py) — ghi chú lượt
- [`agents/steps/classification.py`](../../../../src/backend/app/agents/steps/classification.py) — gộp intent, ràng buộc đổi món
- [`infrastructure/persistence/conversation_store.py`](../../../../src/backend/app/infrastructure/persistence/conversation_store.py), [`postgres_conversation_archive.py`](../../../../src/backend/app/infrastructure/persistence/postgres_conversation_archive.py)
