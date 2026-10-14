# E00: áp dụng PRD orc tự chủ và lập plan có hiệu lực

- Ngày: 2026-10-13
- Tác giả: Nguyễn Minh Nhật / Codex
- Nhánh: codex/orc-autonomous-tools
- Trạng thái: hoàn thành (E00); toàn plan dang dở
- Phạm vi: docs

## Mục tiêu

Người dùng yêu cầu tạo branch và thực thi đề xuất 13/10. Đây là chốt toàn bộ đề xuất, không chốt các đề xuất khác. Phục vụ FR-AGT-01–07, FR-SRC-01/03/04, FR-REC-01/03, NFR-REL-01, NFR-SEC-01/04, NFR-MAINT-01/02, NFR-PERF-02.

## File thay đổi

- `docs/prd/architecture.md` — sửa §3/§6: vòng orc, tools, hai ngân sách, grounding, commit, v2.
- `docs/prd/requirements.md` — sửa FR-AGT và AC-AGT-02/04–09; giữ AC-01/03.
- `docs/prd/user-flow.md` — sửa luồng/trạng thái tiền/tiến trình và lựa chọn UI.
- `docs/prd/update-archive/2026-10-13-orc-tu-chu-goi-tool-va-chon-san-pham.md` — chuyển từ update (file đầu task untracked), ghi đã áp dụng, người chốt/ngày.
- `docs/plan/2026-10-13-orc-tu-chu-goi-tool-va-chon-san-pham.md` — thêm kế hoạch có hiệu lực, ma trận AC giữ/thay, baseline và tiến độ.
- `history/2026-10-13-orc-tu-chu-e00-prd.md` — thêm entry.

## Quyết định

PRD trước source. v1 giữ semantics hiện có; v2 không phục hồi classifier/cờ đã gỡ. Các đề xuất Catalog tự lấy và debug Phần B vẫn chờ riêng. D1/D3/T1–T4 còn là ca hồi quy. Không gọi scripted model là nghiệm thu tự chủ.

## Kiểm tra

- Baseline contract trước sửa: PASS 130 schemas, 106 fixtures; CDP 12 schemas.
- Snapshot + architecture offline: 2 failed, 10 passed, 7.81s, exit 1; snapshot khác cassette (178 lượt miss). Đúng tồn đọng history sửa phạm vi; chưa sửa source agent. Lần sandbox treo đã dừng exit 130, rerun ngoài sandbox có timeout 120s hoàn tất.
- git diff --check: PASS.

## Còn lại / rủi ro

E01–E13 theo plan; baseline không phải xanh và chưa duyệt lại bằng model thật. Không commit/push/deploy trong E00.
