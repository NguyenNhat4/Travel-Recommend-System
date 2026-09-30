import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createPatchQueue } from '../../src/components/checkout/patchQueue';

/** Lời hứa hoàn tất khi test cho phép, để dựng "request đang bay". */
function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>((r) => { resolve = r; });
  return { promise, resolve };
}

function makeQueue(run: (id: string) => Promise<void>, onPending: (id: string, pending: boolean) => void) {
  const queue = createPatchQueue(400);
  queue.setHandlers({ run, onPending });
  return queue;
}

describe('createPatchQueue', () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  it('debounce: bấm liên tục chỉ chạy một lần, sau khoảng lặng 400 ms cuối cùng', async () => {
    const run = vi.fn().mockResolvedValue(undefined);
    const queue = makeQueue(run, vi.fn());
    queue.schedule('a');
    await vi.advanceTimersByTimeAsync(300);
    queue.schedule('a');
    await vi.advanceTimersByTimeAsync(300);
    queue.schedule('a');
    await vi.advanceTimersByTimeAsync(399);
    expect(run).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    expect(run).toHaveBeenCalledTimes(1);
    expect(run).toHaveBeenCalledWith('a');
  });

  it('các lần chạy của cùng một mục nối tiếp nhau; mục khác chạy song song', async () => {
    const gates = [deferred(), deferred()];
    const started: string[] = [];
    const run = vi.fn(async (id: string) => {
      started.push(id);
      if (id === 'a') await gates[started.filter((s) => s === 'a').length - 1].promise;
    });
    const queue = makeQueue(run, vi.fn());
    const first = queue.enqueue('a');
    const second = queue.enqueue('a');
    const other = queue.enqueue('b');
    await vi.advanceTimersByTimeAsync(0);
    expect(started).toEqual(['a', 'b']);            // lần 2 của "a" chưa được chạy khi lần 1 còn bay
    gates[0].resolve();
    await vi.advanceTimersByTimeAsync(0);
    expect(started).toEqual(['a', 'b', 'a']);
    gates[1].resolve();
    await Promise.all([first, second, other]);
    expect(run).toHaveBeenCalledTimes(3);
  });

  it('onPending: bật từ lúc chờ debounce, giữ nguyên qua các lần chạy liền nhau, chỉ tắt khi xong hết', async () => {
    const gates = [deferred(), deferred()];
    const events: boolean[] = [];
    const run = vi.fn(() => gates[run.mock.calls.length - 1].promise);
    const queue = makeQueue(run, (_id, pending) => events.push(pending));
    queue.schedule('a');
    expect(queue.isPending('a')).toBe(true);
    await vi.advanceTimersByTimeAsync(400);          // hết debounce, lần 1 đang bay
    queue.schedule('a');                             // khách bấm tiếp trong lúc PATCH đầu còn bay
    await vi.advanceTimersByTimeAsync(400);          // lần 2 vào hàng, chờ lần 1
    expect(run).toHaveBeenCalledTimes(1);
    gates[0].resolve();
    await vi.advanceTimersByTimeAsync(0);
    expect(run).toHaveBeenCalledTimes(2);            // lần 2 chạy ngay sau lần 1
    expect(events).toEqual([true]);                  // không nháy tắt giữa hai lần chạy
    gates[1].resolve();
    await vi.advanceTimersByTimeAsync(0);
    expect(queue.isPending('a')).toBe(false);
    expect(events).toEqual([true, false]);
  });

  it('flush chạy ngay mọi lần đang chờ debounce và đợi chúng xong', async () => {
    const gate = deferred();
    const run = vi.fn(() => gate.promise);
    const queue = makeQueue(run, vi.fn());
    queue.schedule('a');
    queue.schedule('b');
    let flushed = false;
    const flushing = queue.flush().then(() => { flushed = true; });
    await vi.advanceTimersByTimeAsync(0);
    expect(run).toHaveBeenCalledTimes(2);            // chưa tới 400 ms mà đã chạy
    expect(flushed).toBe(false);
    gate.resolve();
    await flushing;
    expect(flushed).toBe(true);
    await vi.advanceTimersByTimeAsync(1000);
    expect(run).toHaveBeenCalledTimes(2);            // hẹn giờ cũ đã bị huỷ, không chạy lần nữa
  });

  it('flush khi không có gì chờ thì trả về ngay', async () => {
    const queue = makeQueue(vi.fn(), vi.fn());
    await expect(queue.flush()).resolves.toBeUndefined();
  });

  it('một lần chạy ném lỗi không làm kẹt hàng đợi: mục vẫn hết "đang chờ" và lần sau vẫn chạy', async () => {
    const run = vi.fn().mockRejectedValueOnce(new Error('hỏng')).mockResolvedValue(undefined);
    const events: boolean[] = [];
    const queue = makeQueue(run, (_id, pending) => events.push(pending));
    await expect(queue.enqueue('a')).rejects.toThrow('hỏng');
    expect(queue.isPending('a')).toBe(false);
    await expect(queue.enqueue('a')).resolves.toBeUndefined();
    expect(run).toHaveBeenCalledTimes(2);
    expect(events).toEqual([true, false, true, false]);
  });
});
