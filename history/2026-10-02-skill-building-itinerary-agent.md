# Skill `building-itinerary-agent` cho coding agent theo chuẩn Agent Skills

- Ngày: 2026-10-02
- Tác giả: nhatnm / Claude
- Nhánh: feat/itinerary-agent-guardrails
- Trạng thái: hoàn thành
- Phạm vi: agent, docs

## Mục tiêu

Người dùng muốn một skill để coding agent (Claude Code, Codex, Copilot, cùng chịu `AGENTS.md`) làm Itinerary Agent theo
thực hành ngành. Chọn phạm vi: skill cho coding agent, dùng được ở nhiều công cụ (không phải skill chạy bên trong agent).
Phục vụ quy trình phát triển FR-AGT-01..05, NFR-REL-01; không đổi hành vi sản phẩm.

## File thay đổi

- `.agents/skills/building-itinerary-agent/SKILL.md` — thêm: frontmatter theo chuẩn Agent Skills (`name`, `description`
  đã đặt trong ngoặc kép, `metadata`) và checklist 7 bước:
  1. nạp context;
  2. tái hiện bằng bằng chứng;
  3. chọn lớp, ưu tiên luật hơn LLM;
  4. test trước;
  5. tự kiểm invariant;
  6. lệnh kiểm tra theo tầng bằng chứng;
  7. bàn giao (history, đề xuất).
- `.agents/skills/building-itinerary-agent/references/eval-loop.md` — thêm: vòng golden (lỗi thật → case → baseline →
  `--repeat 3` → cả bộ → đọc trace), mẫu case, lệnh.
- `.agents/skills/building-itinerary-agent/references/industry-patterns.md` — thêm: 9 thực hành ngành. Mỗi thực hành
  kèm nguồn, chỗ đã có trong repo và câu hỏi cần trả lời trước khi thêm.
- `.claude/skills/building-itinerary-agent` — thêm: symlink tới `../../.agents/skills/building-itinerary-agent`.
- `AGENTS.md` — sửa §7: ngoại lệ cho `.agents/skills/<tên>/`. Skill chỉ chứa quy trình; quy tắc vẫn chỉ ở AGENTS.md.
- `history/2026-10-02-skill-building-itinerary-agent.md` — thêm: entry này.

## Quyết định

- **Vị trí.**
  - Codex quét `$REPO_ROOT/.agents/skills`; Copilot đọc `.github/skills`, `.claude/skills`, `.agents/skills`.
  - Claude Code đọc `.claude/skills` và theo symlink.
  - Một bản ở `.agents/skills` cộng symlink cho Claude Code là đủ, không phải chép hai nơi.
- **Không thêm quy tắc mới.** Skill trỏ về `AGENTS.md` và `docs/spec/agent/working-context.md`; khi lệch, hai file đó thắng.
- **Theo hướng dẫn viết skill của Anthropic:**
  - tên dạng gerund, khớp thư mục;
  - `description` nói làm gì và khi nào dùng, kèm từ khoá;
  - `SKILL.md` ngắn (84 dòng), tham chiếu một tầng;
  - workflow có checklist; vòng eval đặt trước tài liệu.
- **Frontmatter chỉ dùng trường của chuẩn chung.** Không dùng `paths` hay `when_to_use` vì chúng chỉ có ở Claude Code;
  validator chặt có thể từ chối trường lạ.
- **Không lệch PRD.** PRD không quy định công cụ của coding agent; `.agents/` là thư mục công cụ giống `.github/`.
  Theo AGENTS.md §8, quy trình agent không đưa vào PRD.
- **Nguồn thực hành ngành** (kiểm ngày 2026-10-02):
  - Anthropic: Building effective agents; Writing effective tools for agents; Effective context engineering;
    Demystifying evals for AI agents (2026-01-09).
  - OpenAI: A practical guide to building agents.
  - A2UI (Google), LangGraph Streaming, 12-Factor Agents.
  - Chuẩn: https://agentskills.io/specification

## Kiểm tra

- Script kiểm frontmatter (luật của chuẩn: `name` 1–64 ký tự, chữ thường/số/gạch nối, khớp thư mục, không chứa
  "anthropic"/"claude"; `description` 1–1024 ký tự, không thẻ XML; chỉ trường của chuẩn; `metadata` string→string;
  dưới 500 dòng; link `references/` tồn tại; symlink đọc ra cùng nội dung): 11/11 PASS.
  - Lần đầu script bắt được lỗi YAML: `description` không có ngoặc kép, chứa "Keywords:", nên parser chặt từ chối.
  - Đã sửa bằng cách đặt trong ngoặc kép.
- Validator tham chiếu `skills-ref` 0.1.1 (lệnh `agentskills`, cài trong venv tạm ngoài repo):
  - `agentskills validate .agents/skills/building-itinerary-agent`: `Valid skill`.
  - `agentskills validate .claude/skills/building-itinerary-agent`: `Valid skill`.
- Mọi đường dẫn code và tài liệu skill trích dẫn đều tồn tại (kiểm bằng script).

## Còn lại / rủi ro

- Chưa chạy 3 bài eval của skill trong phiên mới của Claude Code và Codex. Ba bài: thêm warning code, sửa prompt
  narrate, đổi thẻ trong widget. Tiêu chí: skill được kích hoạt, đọc đúng tài liệu, chạy golden subset, ghi history.
- Clone trên Windows không bật `core.symlinks` thì `.claude/skills/building-itinerary-agent` thành file văn bản. Khi đó
  Claude Code không thấy skill; Codex và Copilot vẫn đọc `.agents/skills`.
- Skill cần cập nhật khi `working-context.md` đổi đường dẫn hoặc lệnh golden đổi cờ.
