import { useCallback, useEffect, useRef } from 'react';
import { useTravel } from '../context/TravelContext';
import { mapProductSummaryToProduct } from '../services/assistant';
import type { AssistantCartItem } from '../components/assistant/AssistantResultPanel';

/**
 * Thêm một hoặc nhiều mục của lịch trình vào giỏ, tuần tự, gom kết quả vào một toast
 * (docs/spec/hop-dong-tich-hop-frontend.md §4.8). Khách chưa đăng nhập thì mở LoginModal
 * một lần rồi thêm cả nhóm sau khi đăng nhập.
 */
export function useAssistantCart() {
  const { addToCart, currentPersona, openLoginModal, showToast, navigate } = useTravel();
  // Callback sau đăng nhập chạy ở render sau; đọc bản addToCart mới nhất qua ref để không dùng closure cũ.
  const latest = useRef({ addToCart, currentPersona });
  useEffect(() => {
    latest.current = { addToCart, currentPersona };
  }, [addToCart, currentPersona]);

  const addItems = useCallback(async (items: AssistantCartItem[]) => {
    if (items.length === 1) {
      const [item] = items;
      await latest.current.addToCart(mapProductSummaryToProduct(item.product), 1, item.usingDate, item.checkOutDate);
      return; // addToCart đã tự báo toast cho một mục.
    }
    // Tuần tự, mỗi mục một request; một mục lỗi không chặn mục còn lại.
    let added = 0;
    const failed: string[] = [];
    for (const item of items) {
      const ok = await latest.current.addToCart(
        mapProductSummaryToProduct(item.product), 1, item.usingDate, item.checkOutDate, { silent: true });
      if (ok) added += 1;
      else failed.push(item.product.name);
    }
    const summary = failed.length
      ? `Đã thêm ${added}/${items.length} mục vào giỏ. Chưa thêm được: ${failed.join(', ')}.`
      : `Đã thêm ${added} mục của lịch trình vào giỏ. Giá chính thức hiển thị ở giỏ hàng.`;
    showToast(summary, 'Xem giỏ', () => navigate('/cart'));
  }, [navigate, showToast]);

  return useCallback((items: AssistantCartItem[]) => {
    if (!items.length) return;
    if (!currentPersona) {
      openLoginModal(() => { void addItems(items); });
      return;
    }
    void addItems(items);
  }, [addItems, currentPersona, openLoginModal]);
}
