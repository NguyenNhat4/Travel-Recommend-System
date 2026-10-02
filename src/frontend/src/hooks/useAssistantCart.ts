import { useCallback, useEffect, useRef } from 'react';
import { useTravel } from '../context/TravelContext';
import { mapProductSummaryToProduct } from '../services/assistant';
import type { AssistantCartItem } from '../components/assistant/AssistantResultPanel';
import { maxOccupancyFromAttributes, partyCartRequest } from '../components/checkout/guestCounts';

/** Số lượng và `guests` khi thêm một mục của lịch trình: theo đoàn `intent.party` nếu có, không thì 1 như trước (§6.9). */
function cartArgs(item: AssistantCartItem): { quantity: number; guests?: { adults: number; children: number } } {
  if (!item.party) return { quantity: 1 };
  return partyCartRequest(item.product.taxonomy, item.party, maxOccupancyFromAttributes(item.product.attributes as Record<string, unknown> | undefined));
}

/**
 * Thêm một hoặc nhiều mục của lịch trình vào giỏ, tuần tự, gom kết quả vào một toast
 * (docs/spec/hop-dong-tich-hop-frontend.md §4.8). Khách chưa đăng nhập thì mở LoginModal
 * một lần rồi thêm cả nhóm sau khi đăng nhập. `onAdded` chạy sau khi mọi request đã xong và có ít nhất
 * một mục vào giỏ — ví dụ để chuyển sang `/checkout` khi giỏ đã đủ.
 */
export function useAssistantCart() {
  const { addToCart, currentPersona, openLoginModal, showToast, navigate } = useTravel();
  // Callback sau đăng nhập chạy ở render sau; đọc bản addToCart mới nhất qua ref để không dùng closure cũ.
  const latest = useRef({ addToCart, currentPersona });
  const pending = useRef(new Set<string>());
  useEffect(() => {
    latest.current = { addToCart, currentPersona };
  }, [addToCart, currentPersona]);

  const addItems = useCallback(async (items: AssistantCartItem[]): Promise<number> => {
    if (items.length === 1) {
      const [item] = items;
      const { quantity, guests } = cartArgs(item);
      // addToCart đã tự báo toast cho một mục.
      return await latest.current.addToCart(
        mapProductSummaryToProduct(item.product), quantity, item.usingDate, item.checkOutDate, guests ? { guests } : undefined) ? 1 : 0;
    }
    // Tuần tự, mỗi mục một request; một mục lỗi không chặn mục còn lại.
    let added = 0;
    const failed: string[] = [];
    for (const item of items) {
      const { quantity, guests } = cartArgs(item);
      const ok = await latest.current.addToCart(
        mapProductSummaryToProduct(item.product), quantity, item.usingDate, item.checkOutDate, { silent: true, ...(guests ? { guests } : {}) });
      if (ok) added += 1;
      else failed.push(item.product.name);
    }
    const summary = failed.length
      ? `Đã thêm ${added}/${items.length} mục vào giỏ. Chưa thêm được: ${failed.join(', ')}.`
      : `Đã thêm ${added} mục của lịch trình vào giỏ. Giá chính thức hiển thị ở giỏ hàng.`;
    showToast(summary, 'Xem giỏ', () => navigate('/cart'));
    return added;
  }, [navigate, showToast]);

  return useCallback(async (items: AssistantCartItem[], onAdded?: (added: number) => void,
    feedback?: { onStart: () => void; onSettled: (added: number) => void }): Promise<void> => {
    if (!items.length) return;
    const run = async () => {
      const key = JSON.stringify(items.map((item) => [item.product.productId, item.usingDate, item.checkOutDate, item.party]));
      if (pending.current.has(key)) return;
      pending.current.add(key);
      let added = 0;
      try {
        feedback?.onStart();
        added = await addItems(items);
        if (added > 0) onAdded?.(added);
      } finally {
        pending.current.delete(key);
        feedback?.onSettled(added);
      }
    };
    if (!currentPersona) {
      openLoginModal(() => { void run(); });
      return;
    }
    await run();
  }, [addItems, currentPersona, openLoginModal]);
}
