# Đồng bộ AGENTS.md với bộ PRD `docs/prd/`

- Ngày: 2026-09-22
- Tác giả: mihhquan / Claude Opus 5
- Nhánh: feat/auth
- Trạng thái: hoàn thành
- Phạm vi: docs

## Mục tiêu

Người dùng yêu cầu sửa `AGENTS.md` cho đúng PRD của dự án. Bộ PRD 9 tài liệu (`docs/prd/`) được tạo ở commit `0763443` nhưng `AGENTS.md` **không tham chiếu tới `docs/prd/` ở bất kỳ đâu** — agent làm đúng mục 1.1/1.2 sẽ không bao giờ đọc PRD, nên không biết FR/NFR, tiêu chí nghiệm thu, phạm vi out-of-scope hay Definition of Done của dự án.

## File đã đọc

Toàn bộ 9 tài liệu PRD (`README.md`, `project-brief.md`, `requirements.md`, `user-flow.md`, `data-model.md`, `architecture.md`, `api-contract.md`, `test-plan.md`, `implementation-plan.md`, `deployment-plan.md`), `AGENTS.md`, `src/ARCHITECTURE.md` §5–§12, `src/shared/contracts/openapi.yaml` (danh sách path), `src/shared/contracts/schemas/auth.yaml`, `db/vota_schema.sql`, `docs/spec/DATABASE_SCHEMA.md` (§8), `docs/spec/hop-dong-tich-hop-auth.md`, `history/2026-09-21-lock-assistant-api-to-contract.md`.

## File thay đổi

- `AGENTS.md` — sửa:
  - §1.1: thêm `docs/prd/README.md` làm mục bắt buộc đọc số 1; mỗi feature phải gắn được vào một mã FR/NFR trong `docs/prd/requirements.md`.
  - §1.2: bổ sung tài liệu PRD tương ứng vào 11 dòng hiện có (kèm số mục cụ thể, ví dụ `requirements.md` §1.4 cho Itinerary Agent, `architecture.md` §2 cho Backend, `user-flow.md` cho Frontend, `data-model.md` cho Database) và thêm 2 dòng mới: môi trường/migration/CI (`deployment-plan.md`, `test-plan.md` §4) và lập kế hoạch/DoD (`implementation-plan.md`).
  - §1.3: thêm yêu cầu ghi rõ mã FR/NFR và tiêu chí nghiệm thu (AC) mà feature phục vụ.
  - §2: tách thứ tự ưu tiên thành **hai thang** — "giao diện kỹ thuật" (contract/DDL) và "yêu cầu sản phẩm" (PRD) — vì hai nhóm trả lời hai loại câu hỏi khác nhau; bổ sung `db/*.sql` vào thang kỹ thuật; thêm cảnh báo `docs/prd/api-contract.md` là tài liệu minh hoạ kèm danh sách lệch đã biết với `openapi.yaml`.
  - §3: thêm ràng buộc grounding 100% (NFR-REL-01) và danh sách hạng mục out-of-scope theo `project-brief.md` §4.2; trỏ biến bí mật về `deployment-plan.md` §2.
  - §4: dẫn chiếu DoD (`implementation-plan.md` §4) và tháp kiểm thử 5 tầng (`test-plan.md`), thêm mức bao phủ ≥ 80% và yêu cầu `db/verify.sql` PASS; sửa "`src/` hoặc `docs/`" thành "`src/`, `docs/` hoặc `db/`" cho khớp §5.
  - §6 (mở đầu): ghi rõ `docs/prd/data-model.md` là mô tả cấp PRD, khi lệch thì `db/*.sql` và `docs/spec/*` thắng.
  - §6.4: tách và ghi rõ hai mục chờ chốt có mâu thuẫn với PRD (chiều vector, bộ persona).

## Quyết định

- **Không sửa quy tắc kỹ thuật của `AGENTS.md` theo PRD khi PRD lệch với code/contract đã triển khai.** Căn cứ: chính PRD tự trỏ về `openapi.yaml` (`api-contract.md` dòng 3), về `db/*.sql` (`data-model.md` §5.1) và về `AGENTS.md` (`README.md`, mục Nguyên Tắc Vận Hành). PRD là tầng "làm gì / vì sao", contract và DDL là tầng "giao diện cụ thể" — nên §2 được tách thành hai thang ưu tiên thay vì một danh sách tuyến tính, vì gộp chung sẽ ngụ ý sai rằng PRD thay thế được contract (hoặc ngược lại).
- **Ghi lệch vào `AGENTS.md` thay vì im lặng sửa một bên.** Theo đúng §2: không tự chọn phương án cho mục đang chờ xác nhận, áp dụng quy tắc tạm thời và báo người dùng.

## Kiểm tra

- Trích toàn bộ đường dẫn file trong `AGENTS.md` bằng `grep -oE` rồi kiểm tra tồn tại: mọi đường dẫn đầy đủ đều có thật. Các tên rút gọn trong văn xuôi (`data-model.md`, `openapi.yaml`, `schemas/auth.yaml`, `seed_*.py`...) đã đối chiếu thủ công — đều resolve đúng. Hai ngoại lệ đã biết và đã ghi chú sẵn trong file: `src/evaluation/README.md` (chưa tồn tại) và `data/products.jsonl` / `products.synthetic.jsonl` (file dữ liệu sinh ra lúc chạy, nằm trong `.gitignore`).
- Đối chiếu từng số mục PRD được trích dẫn với heading thật của tài liệu đó (`requirements.md` §1.2–1.8, `architecture.md` §2–§4, `data-model.md` §2.1/§2.2/§3/§5.1, `test-plan.md` §2.4–2.5/§4, `deployment-plan.md` §2, `implementation-plan.md` §4, `project-brief.md` §4.2/§5) — khớp.
- Đối chiếu path PRD với `grep -nE "^  /" src/shared/contracts/openapi.yaml` để lập danh sách lệch trong §2 — xác nhận `/assistant/chat`, `/assistant/conversations`, `/auth/logout`, `/auth/persona-switch`, `/products/{id}/availability` đều không có trong contract.
- Đối chiếu persona: `db/vota_schema.sql:196` và `docs/spec/DATABASE_SCHEMA.md:425-428,661` dùng `P1_frequent/P2_first_time/P3_dormant/P4_no_history`; `schemas/auth.yaml:159` dùng `personaLabel`.
- Không chạy `validate_contract.py` vì không đổi contract/mock.

## Còn lại / rủi ro

Ba mâu thuẫn PRD ↔ hệ thống đã triển khai, đã ghi trong `AGENTS.md` nhưng **cần người dùng quyết định sửa ở phía nào**:

1. **Bộ persona (nghiêm trọng nhất).** DDL dùng 4 trạng thái cold-start `P1_frequent`/`P2_first_time`/`P3_dormant`/`P4_no_history` trên cột `app.users.persona` — mỗi giá trị kích hoạt một nhánh recommendation khác nhau trong kịch bản demo. PRD mô tả 4 persona phong cách du lịch `P1_family`/`P2_biz`/`P3_explorer`/`P4_deal` trên `persona_tag`/`personaTag`, trong khi contract chỉ có `personaLabel`. Đây là hai **taxonomy khác nhau về bản chất**, không phải khác tên. Sửa DDL theo PRD sẽ làm hỏng seed, `verify.sql` và kịch bản demo recommendation.
2. **Chiều vector.** PRD ghi 768 chiều với `text-embedding-3-small`/`bge-m3`, nhưng hai model đó sinh vector 1536 và 1024 chiều. Con số trong PRD tự mâu thuẫn với model được nêu.
3. **`docs/prd/api-contract.md` lệch với `openapi.yaml`** ở 5 endpoint + tên trường `bookingCode`/`referenceCode`, và thiếu `/cart*`, `/auth/register`, `/auth/password`, `/destinations`. Riêng `/assistant/chat` là route đã bị gỡ có chủ đích (`history/2026-09-21-lock-assistant-api-to-contract.md`) — nếu không sửa PRD, một agent sau có thể khôi phục nhầm.

Ngoài ra, chỉ tiêu độ trễ trợ lý AI đang có ba con số khác nhau: `src/ARCHITECTURE.md` §10 ghi < 5 s, `docs/prd/requirements.md` NFR-PERF-02 ghi ≤ 4 s, `docs/prd/project-brief.md` §3.2 ghi < 3 s. Search/recommendation cũng lệch: 300 ms (ARCHITECTURE) so với 250 ms (PRD). Chưa sửa vì `AGENTS.md` không phát biểu con số nào.
