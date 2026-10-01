/**
 * Hàng đợi đồng bộ số khách của giỏ theo từng mục (docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md §6.4).
 *
 * - `schedule(id)`: chờ `debounceMs` không còn thao tác mới rồi mới chạy (khách bấm liên tục chỉ tốn một request).
 * - Các lần chạy của CÙNG một mục nối tiếp nhau, không bao giờ song song: `PATCH` ghi giá trị tuyệt đối, nên PATCH sau
 *   phải tới sau PATCH trước thì giỏ mới khớp với lựa chọn cuối cùng của khách.
 * - `onPending` đúng ở cả ba giai đoạn (chờ debounce, chờ tới lượt, đang chạy) và không nháy tắt giữa hai lần chạy liền nhau.
 * - `flush()` chạy ngay mọi lần đang chờ debounce và đợi mọi mục xong (dùng khi rời bước hoặc bấm Tiếp tục).
 *
 * Code thuần, không phụ thuộc React, để kiểm bằng fake timers.
 */
export interface PatchHandlers {
  /** Thực hiện một lần đồng bộ cho mục (tự bỏ qua nếu không có gì cần gửi). Lỗi của request do bên gọi ghi lại, không ném ra đây. */
  run: (id: string) => Promise<void>;
  /** Gọi mỗi khi trạng thái "đang chờ hoặc đang chạy" của một mục đổi. */
  onPending: (id: string, pending: boolean) => void;
}

export interface PatchQueue {
  /** Đặt hàm xử lý mới nhất (gọi lại sau mỗi lần vẽ để hàm luôn thấy state mới); hàng đợi giữ nguyên qua các lần vẽ. */
  setHandlers: (handlers: PatchHandlers) => void;
  /** Hẹn một lần đồng bộ sau `debounceMs`; gọi lại trong lúc chờ thì tính lại từ đầu. */
  schedule: (id: string) => void;
  /** Xếp ngay một lần đồng bộ (không debounce) và trả về lời hứa hoàn tất của lần đó. */
  enqueue: (id: string) => Promise<void>;
  /** Chạy ngay mọi lần đang chờ debounce, đợi tất cả xong. */
  flush: () => Promise<void>;
  isPending: (id: string) => boolean;
}

export function createPatchQueue(debounceMs: number): PatchQueue {
  let handlers: PatchHandlers = { run: async () => undefined, onPending: () => undefined };
  const timers = new Map<string, ReturnType<typeof setTimeout>>();
  /** Số lần chạy đang xếp hàng hoặc đang chạy của mỗi mục. */
  const inQueue = new Map<string, number>();
  /** Đuôi hàng đợi của mỗi mục; không bao giờ reject nên nối tiếp được. */
  const tails = new Map<string, Promise<void>>();
  const reported = new Map<string, boolean>();

  const isPending = (id: string) => timers.has(id) || (inQueue.get(id) ?? 0) > 0;
  const report = (id: string) => {
    const now = isPending(id);
    if (reported.get(id) === now) return;
    reported.set(id, now);
    handlers.onPending(id, now);
  };

  const enqueue = (id: string): Promise<void> => {
    inQueue.set(id, (inQueue.get(id) ?? 0) + 1);
    report(id);
    const result = (tails.get(id) ?? Promise.resolve()).then(() => handlers.run(id)).finally(() => {
      inQueue.set(id, (inQueue.get(id) ?? 1) - 1);
      report(id);
    });
    tails.set(id, result.catch(() => undefined));
    return result;
  };

  const schedule = (id: string) => {
    const existing = timers.get(id);
    if (existing !== undefined) clearTimeout(existing);
    timers.set(id, setTimeout(() => {
      timers.delete(id);
      void enqueue(id);
    }, debounceMs));
    report(id);
  };

  const flush = async () => {
    for (const [id, timer] of [...timers]) {
      clearTimeout(timer);
      timers.delete(id);
      void enqueue(id);
    }
    await Promise.all(tails.values());
  };

  return { setHandlers: (next) => { handlers = next; }, schedule, enqueue, flush, isPending };
}
