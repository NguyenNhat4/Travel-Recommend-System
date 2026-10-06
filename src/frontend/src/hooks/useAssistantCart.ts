import { useCallback, useEffect, useRef } from 'react';
import { useTravel, type BookNowItem } from '../context/TravelContext';
import { mapProductSummaryToProduct } from '../services/assistant';
import { isCartEligible } from '../services/booking';
import type { AssistantCartItem } from '../components/assistant/AssistantResultPanel';
import { maxOccupancyFromAttributes, partyCartRequest } from '../components/checkout/guestCounts';

/** Số lượng và `guests` khi thêm một mục của lịch trình: theo đoàn `intent.party` nếu có, không thì 1 như trước (§6.9). */
function cartArgs(item: AssistantCartItem): { quantity: number; guests?: { adults: number; children: number } } {
  if (!item.party) return { quantity: 1 };
  return partyCartRequest(item.product.taxonomy, item.party, maxOccupancyFromAttributes(item.product.attributes as Record<string, unknown> | undefined));
}

/** Một mục của lịch trình thành một mục Đặt ngay: ngày theo lịch trình, số khách theo đoàn. */
export function bookNowItemOf(item: AssistantCartItem): BookNowItem {
  const { quantity, guests } = cartArgs(item);
  return {
    product: mapProductSummaryToProduct(item.product), quantity, usingDate: item.usingDate,
    checkOutDate: item.checkOutDate, guests,
  };
}

/**
 * Thêm một hoặc nhiều mục của lịch trình vào giỏ, tuần tự, gom kết quả vào một toast
 * (docs/spec/hop-dong-tich-hop-frontend.md §4.8). Chỉ tour, trải nghiệm và tiện ích khác vào giỏ được; khách sạn và vé máy
 * bay bị bỏ qua ở đây vì chúng chỉ đặt trực tiếp (docs/spec/booking/dat-truc-tiep-theo-don-nhap.md R-DIR-02). Không cần đăng
 * nhập: khách chưa đăng nhập có giỏ riêng. `onAdded` chạy sau khi mọi request đã xong và có ít nhất một mục vào giỏ.
 * `feedback` báo trạng thái đang thêm/đã xong cho nút của sản phẩm; cùng một nhóm mục đang chạy thì bấm lại bị bỏ qua.
 */
export function useAssistantCart() {
  const { addToCart, showToast, navigate } = useTravel();
  // Đọc bản addToCart mới nhất qua ref để callback bất đồng bộ không dùng closure cũ.
  const latest = useRef({ addToCart });
  const pending = useRef(new Set<string>());
  useEffect(() => {
    latest.current = { addToCart };
  }, [addToCart]);

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
    const eligible = items.filter((item) => isCartEligible(item.product.taxonomy));
    if (!eligible.length) return;
    const key = JSON.stringify(eligible.map((item) => [item.product.productId, item.usingDate, item.checkOutDate, item.party]));
    if (pending.current.has(key)) return;
    pending.current.add(key);
    let added = 0;
    try {
      feedback?.onStart();
      added = await addItems(eligible);
      if (added > 0) onAdded?.(added);
    } finally {
      pending.current.delete(key);
      feedback?.onSettled(added);
    }
  }, [addItems]);
}

/**
 * Đặt ngay một mục của lịch trình, hoặc "Thanh toán tất cả": một đơn nháp cho mọi mục đặt được rồi mở trang thanh toán
 * (FR-BKG-01, spec §13). Nhiều mục thì cho phép bỏ qua mục không đặt được (`allowPartial`); `startBooking` báo các mục bị bỏ.
 */
export function useBookItinerary() {
  const { startBooking } = useTravel();
  return useCallback(
    (items: AssistantCartItem[]) => startBooking(items.map(bookNowItemOf), { allowPartial: items.length > 1 }),
    [startBooking],
  );
}
