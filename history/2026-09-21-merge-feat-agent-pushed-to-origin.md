# Gộp bản feat/agent được push thẳng lên origin vào release-mvp-v1

- Ngày: 2026-09-21
- Tác giả: Nguyễn Minh Nhật / Claude Code
- Nhánh: release-mvp-v1
- Trạng thái: hoàn thành
- Phạm vi: backend, agent, contract

## Mục tiêu

Lúc chuẩn bị push, `git fetch` cho thấy `origin/release-mvp-v1` đã đi trước 18 commit: có người
push thẳng nhánh `feat/agent` (SHA gốc `ef5d885`, `91449cb`, `0ae75e9`…) vào release, kèm
`b7bb4ab` "Add route geometry tests and OSRM fixture".

Local đang giữ **bản replay** của đúng loạt commit đó cộng các fix sau này, nên mỗi file chung tồn
tại hai lịch sử khác SHA. Phải gộp, không được force push vì sẽ xoá 18 commit của người khác.

## File thay đổi

Sáu conflict, tất cả đều là chỗ HEAD **mới hơn** — phía origin là bản trước các fix đã ghi ở
`history/2026-09-21-fix-conflict-marker-common-yaml.md`,
`history/2026-09-21-resolve-contract-refs-in-enum-bounds.md`,
`history/2026-09-21-merge-agent-into-release-mvp-v1.md` và
`history/2026-09-21-lock-assistant-api-to-contract.md`:

- `src/backend/app/application/itinerary/contracts.py` — giữ HEAD: có `_resolve()` đi theo `$ref`
  nội bộ. Phía origin là bản gây `KeyError: 'enum'` khiến `build_graph()` không import được.
- `src/backend/app/api/v1/routes/assistant.py` — giữ HEAD: đã gỡ route `/chat` ngoài contract.
- `src/backend/app/domain/itinerary/schemas.py` — giữ HEAD: đã gỡ `ChatRequest`/`ChatResponse`.
- `src/backend/tests/unit/agents/test_itinerary_tools.py` — giữ HEAD: hai assertion đã sửa
  (`includeVariants` mặc định, `priceUnit` trong fixture product).
- `src/shared/contracts/schemas/common.yaml` — giữ HEAD: mô tả `details` là tập cha, có thêm
  `MIN_STAY_NOT_MET` và `PRODUCT_NOT_INDEXED` mà phía origin thiếu. Lần này **không** còn conflict
  marker bị commit như đợt trước.
- `.gitignore` — gộp hai phía, không chọn một.

## Quyết định

- **Giữ HEAD cho cả 5 file code/contract, không phải vì "ours thắng" mà vì đã đối chiếu từng chỗ:**
  mỗi conflict là một fix đã có entry lịch sử, phía origin là trạng thái trước fix đó. Lấy phía
  origin sẽ hoàn nguyên các lỗi đã sửa.
- **`.gitignore` lấy block secret của origin** (`.env`, `.env.*`, `!**/.env.example`, `*.pem`,
  `*.key`, `*.p12`) vì rộng hơn bản mình vừa thêm, cộng với `.embcache/` và các mục eval của HEAD.
- **Không force push.** 18 commit phía origin là việc thật của người khác.

## Kiểm tra

- `pytest src/backend/tests`: **125 passed, 2 skipped**.
- `validate_contract.py`: **PASS**.
- `grep` conflict marker trong `src/`, `docs/`, `.gitignore`: sạch.

## Còn lại / rủi ro

- **Lịch sử nhánh giờ có hai bản của cùng một loạt thay đổi agent** (bản gốc `feat/agent` và bản
  replay). Nội dung đã hội tụ về một trạng thái, nhưng `git log` sẽ khó đọc và `git blame` trên các
  file agent có thể trỏ về commit replay thay vì commit gốc.
- Để tránh lặp lại: thống nhất **một** đường đưa code lên release. `feat/agent` hiện đã nằm trong
  release theo cả hai đường.
- Commit `b7bb4ab` (route geometry test, OSRM fixture) merge vào không conflict và chưa được rà
  riêng ở đây; test toàn bộ backend vẫn xanh.
