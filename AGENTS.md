# Quy tắc cho AI agent

File này áp dụng cho mọi AI coding agent (Claude Code, Codex, Cursor, Copilot...) làm việc trong repository. `CLAUDE.md` chỉ import file này; sửa quy tắc tại đây.

## 1. Bắt buộc đọc tài liệu trước khi làm feature mới

Trước khi viết hoặc sửa code cho **feature mới, endpoint mới, module mới hoặc thay đổi hành vi**, agent PHẢI dùng tool đọc (Read/cat) các file quy tắc bên dưới trong phiên hiện tại. Không được dựa vào trí nhớ, phiên trước hoặc suy đoán từ tên file.

### 1.1. Luôn đọc (mọi feature)

1. `src/ARCHITECTURE.md` — cấu trúc repo, quy tắc phụ thuộc, quy ước thêm module.
2. `src/shared/contracts/MVP.md` — bộ trường tối thiểu hiện hành (1.2.0).
3. `docs/spec/contract-baseline-v1.1.md` — quyết định đã chốt và phần còn chờ xác nhận.
4. `README.md` của workstream sẽ sửa (`src/<workstream>/README.md`).
5. Lịch sử thay đổi trong `history/` (xem mục 5): `history/README.md`, 10 entry mới nhất, mọi entry từng chạm vào đường dẫn/workstream sắp sửa và mọi entry có `Trạng thái: dang dở` thuộc phạm vi đó.

### 1.2. Đọc thêm theo phạm vi

| Phạm vi thay đổi | File phải đọc |
|---|---|
| API / request / response bất kỳ | `src/shared/contracts/README.md`, `src/shared/contracts/openapi.yaml`, file `paths/<domain>.yaml` và `schemas/<domain>.yaml` liên quan, `schemas/common.yaml` |
| Backend (`src/backend`) | `src/backend/README.md`, `docs/spec/hop-dong-tich-hop-backend.md` (các mục của domain liên quan) |
| Frontend (`src/frontend`) | `src/frontend/README.md`, `docs/spec/hop-dong-tich-hop-frontend.md`, `docs/spec/ux-research-brief.md` |
| Itinerary Agent (`src/backend/app/agents`, use case itinerary) | `docs/spec/hop-dong-tich-hop-itinerary-assistant.md`, `docs/agent/README.md` và các file nó liên kết, `src/shared/mocks/itinerary-agent/README.md` |
| Search / Recommendation | `docs/spec/hop-dong-tich-hop-backend.md` (mục Search, Recommendation), `docs/spec/recsys-internship-handbook-v3-vi.md` |
| CDP clone, `CdpClient`, ghi hành vi người dùng | `docs/spec/hop-dong-tich-hop-cdp.md`, `src/cdp_clone/README.md`, `src/shared/contracts/cdp-clone.openapi.yaml` |
| Mock / fixture (`src/shared/mocks`) | `src/shared/README.md`, `src/shared/mocks/index.json`, schema response tương ứng |
| Data collection (`src/data_collection`) | `src/data_collection/README.md`, `src/data_collection/docs/SCHEMA.md` |
| Evaluation (`src/evaluation`) | `src/evaluation/README.md`, `docs/spec/recsys-internship-handbook-v3-vi.md` |
| Insider clone (`src/insider_clone`) | `src/insider_clone/README.md`, `docs/spec/recsys-internship-handbook-v3-vi.md` (phần Insider) |
| Tính năng sản phẩm / luồng người dùng mới | `docs/product.md` |

Với file dài (> 500 dòng), được phép đọc mục lục (`grep -n "^#"`) rồi đọc đầy đủ các mục liên quan, nhưng phải đọc hết mục đó, không chỉ vài dòng đầu.

### 1.3. Xác nhận trước khi code

Trước lần sửa code đầu tiên, agent phải ghi ngắn cho người dùng:

- Danh sách file đã đọc, gồm các entry `history/` đã đọc.
- Các quy tắc/ràng buộc từ tài liệu áp dụng cho feature này.
- Quyết định hoặc việc dang dở từ lịch sử liên quan tới feature này.
- Điểm mâu thuẫn hoặc chưa rõ (nếu có).

Nếu chưa đọc đủ file theo mục 1.1 và 1.2, **không được bắt đầu code**.

## 2. Khi tài liệu mâu thuẫn hoặc thiếu

Thứ tự ưu tiên (cao xuống thấp):

1. `src/shared/contracts/openapi.yaml` và các file `paths/`, `schemas/` — nguồn sự thật cho API.
2. `src/shared/contracts/MVP.md` — thay thế danh sách required/optional của baseline 1.1.
3. `docs/spec/contract-baseline-v1.1.md`.
4. `src/ARCHITECTURE.md`.
5. `docs/spec/hop-dong-tich-hop-*.md`, `docs/product.md`, handbook.

Không tự chọn phương án cho các mục đang "chờ xác nhận" trong baseline; áp dụng quy tắc tạm thời đã ghi và báo người dùng. Nếu tài liệu không đề cập, hỏi người dùng thay vì tự đặt quy ước mới.

## 3. Quy tắc khi triển khai

- Thay đổi giao diện giữa các team: cập nhật OpenAPI (`paths/`, `schemas/`) **trước**, rồi mới code backend/frontend. Không sửa bản bundle sinh tự động.
- Không xóa/đổi tên field hoặc đổi semantics trong v1; thay đổi phá vỡ tương thích phải lên v2.
- Tuân thủ quy tắc phụ thuộc backend và quy tắc frontend trong `src/ARCHITECTURE.md` (mục 5, 6, 12).
- Code mới đặt theo cấu trúc trong `src/ARCHITECTURE.md` (`src/backend`, `src/frontend`...). Các thư mục cũ ở gốc `src/` (`src/agents`, `src/api`, `src/models`, `src/services`, `src/main.py`, `src/config.py`) không được mở rộng nếu chưa hỏi người dùng.
- Grounding: mọi sản phẩm, giá, `productId` phải đến từ Search/Recommendation/Catalog; không để LLM tạo dữ liệu sản phẩm.
- Không commit hoặc log secret, API key, JWT.

## 4. Trước khi báo hoàn thành

- Có thay đổi contract hoặc mock: chạy `PYTHONDONTWRITEBYTECODE=1 python3 src/shared/contracts/tests/validate_contract.py` từ repo root và báo kết quả.
- Thêm test theo mục 10 của `src/ARCHITECTURE.md` (unit, contract, integration tương ứng).
- Nếu feature làm thay đổi quy ước, cập nhật tài liệu liên quan trong cùng thay đổi.
- Có thay đổi trong `src/` hoặc `docs/`: đã tạo entry trong `history/` theo mục 5.

## 5. Bắt buộc ghi lịch sử thay đổi

Mọi thay đổi (thêm, sửa, xóa, đổi tên file) trong `src/` hoặc `docs/` PHẢI có một entry trong `history/`, kể cả sửa nhỏ, refactor, fix bug hay chỉ sửa tài liệu.

- Đọc `history/README.md` và làm đúng định dạng, tên file, mẫu tại đó.
- Mỗi task một file mới `history/YYYY-MM-DD-<slug>.md`; không gộp vào entry của người khác.
- Liệt kê **đầy đủ** file đã đổi (đối chiếu `git status` trước khi viết), lý do, quyết định, lệnh kiểm tra đã chạy và kết quả thật, việc còn lại.
- Tạo entry trước khi báo hoàn thành và trước khi commit; entry nằm trong cùng commit với thay đổi.
- Dừng giữa chừng hoặc bị chặn: vẫn tạo entry với `Trạng thái: dang dở` và ghi rõ đang dừng ở đâu.
- Không sửa nội dung entry cũ; quyết định mới thay thế quyết định cũ thì tạo entry mới theo `history/README.md`.

Thiếu entry lịch sử thì thay đổi được coi là **chưa hoàn thành**.
