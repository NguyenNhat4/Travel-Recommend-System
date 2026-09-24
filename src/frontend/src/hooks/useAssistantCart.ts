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

  const addItems = useCallback((items: AssistantCartItem[]) => {
    let added = 0;
    const failed: string[] = [];
    for (const item of items) {
      try {
        latest.current.addToCart(mapProductSummaryToProduct(item.product), 1, item.usingDate, item.checkOutDate);
        added += 1;
      } catch {
        failed.push(item.product.name);
      }
    }
    if (items.length <= 1 && failed.length === 0) return; // addToCart đã tự báo toast cho một mục.
    const summary = failed.length
      ? `Đã thêm ${added}/${items.length} mục vào giỏ. Chưa thêm được: ${failed.join(', ')}.`
      : `Đã thêm ${added} mục của lịch trình vào giỏ. Giá chính thức hiển thị ở giỏ hàng.`;
    showToast(summary, 'Xem giỏ', () => navigate('/cart'));
  }, [navigate, showToast]);

  return useCallback((items: AssistantCartItem[]) => {
    if (!items.length) return;
    if (!currentPersona) {
      openLoginModal(() => addItems(items));
      return;
    }
    addItems(items);
  }, [addItems, currentPersona, openLoginModal]);
}
