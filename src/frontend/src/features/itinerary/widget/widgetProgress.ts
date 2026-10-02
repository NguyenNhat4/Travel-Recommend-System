import type { AssistantProgress } from '../../../context/assistantState';

export type ProgressStepStatus = 'done' | 'active' | 'pending';

export interface ProgressStep {
  label: string;
  status: ProgressStepStatus;
}

export interface ProgressView {
  steps: ProgressStep[];
  /** Câu mô tả việc đang làm (cũng là nhãn của bước đang chạy), đọc cho trình đọc màn hình. */
  current: string;
}

// Ba bước theo docs/spec/product.md §6.1. Nhãn do Web sở hữu; `message` của sự kiện là chuỗi debug của backend,
// không bao giờ hiện cho người dùng.
const STEPS = [
  { label: 'Hiểu yêu cầu', running: 'Đang hiểu yêu cầu của bạn…' },
  { label: 'Tìm sản phẩm phù hợp', running: 'Đang tìm chỗ ở, vé tham quan, combo phù hợp…' },
  { label: 'Sắp xếp lịch trình', running: 'Đang sắp xếp lịch trình theo ngày…' },
] as const;

// Node đã xong (sự kiện `node.completed` thật) → bước đang chạy và câu phụ. Node không có ở đây (intake, classify,
// converse, clarify, narrate, finalize...) không đẩy bước lên, nên nhánh trò chuyện hay hỏi lại không có ✓ giả.
// Lấy node gần nhất chứ không lấy bước cao nhất: evaluate → retry là tìm lại thật, bước 2 phải chạy lại.
const AFTER_NODE: Record<string, { step: number; detail?: string }> = {
  extract: { step: 1 },
  tool: { step: 1 },
  retry: { step: 1, detail: 'Đang thử phương án khác…' },
  evaluate: { step: 2 },
  compose: { step: 2, detail: 'Đang viết lời tư vấn…' },
};

export function progressView(progress: AssistantProgress[]): ProgressView {
  let active = 0;
  let detail: string | undefined;
  for (const event of progress) {
    const next = event.nodeId ? AFTER_NODE[event.nodeId] : undefined;
    if (!next) continue;
    active = next.step;
    detail = next.detail;
  }
  // Bước đang chạy hiện việc con thật nếu có (thử lại, viết lời tư vấn) thay cho câu chung của bước.
  const current = detail ?? STEPS[active].running;
  return {
    steps: STEPS.map((step, index) => ({
      label: index === active ? current : step.label,
      status: index < active ? 'done' : index === active ? 'active' : 'pending',
    })),
    current,
  };
}
