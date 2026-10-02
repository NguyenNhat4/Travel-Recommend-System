'use client';

/**
 * Nguồn mục của trang thanh toán (docs/spec/booking/dat-truc-tiep-theo-don-nhap.md §6, §13):
 *
 * - `/checkout` thanh toán toàn bộ giỏ (tour, trải nghiệm, tiện ích khác);
 * - `/checkout?draft=<mã>` thanh toán đúng một đơn nháp của Đặt ngay, không kèm mục nào trong giỏ.
 *
 * Hai nguồn trả cùng một hình dạng mục (`CartItem`), nên ba bước của checkout và bộ luật dùng chung.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { useTravel } from '../../context/TravelContext';
import * as bookingApi from '../../services/booking';
import type { ApiCartItem, UpdateCartItemRequest } from '../../services/booking';
import { ApiError } from '../../services/http';

/** Phần của `CartResponse` / `BookingDraft` mà trang thanh toán đọc. */
export interface CheckoutData {
  items: ApiCartItem[];
  itemCount: number;
  subtotal: number;
  total: number;
  currency: string;
}

export interface ExpiredItem {
  productId: string;
  taxonomy: string;
  inCart: boolean;
}

export type SourceStatus = 'loading' | 'ready' | 'expired' | 'not-found';

export interface CheckoutSource {
  kind: 'cart' | 'draft';
  draftId: string | null;
  data: CheckoutData | null;
  status: SourceStatus;
  /** Hạn của đơn nháp (ISO); null với giỏ. */
  expiresAt: string | null;
  /** Mục của đơn nháp đã hết hạn và việc mục đó còn nằm trong giỏ không (từ `410 BOOKING_DRAFT_EXPIRED`). */
  expiredItems: ExpiredItem[];
  refresh: () => Promise<CheckoutData | null>;
  updateItem: (cartItemId: string, updates: UpdateCartItemRequest, options?: { silent?: boolean }) => Promise<ApiError | null>;
  removeItem: (cartItemId: string) => Promise<void>;
  /** Backend báo đơn nháp đã hết hạn hoặc không còn (khi bấm Thanh toán): chuyển sang màn hình tương ứng. */
  fail: (error: ApiError) => boolean;
}

function expiredItemsOf(error: ApiError): ExpiredItem[] {
  const items = error.details?.items;
  return Array.isArray(items) ? items.filter((i) => i && typeof i.productId === 'string') : [];
}

export function useCheckoutSource(): CheckoutSource {
  const { cart, authReady, refreshCart, updateCartItem, showToast } = useTravel();
  // Đọc `draft` bằng `useSearchParams`, không đọc `window.location`: khi chuyển trang bằng `router.push`, Next render trang
  // mới TRƯỚC khi cập nhật `window.location`, nên đọc location lúc render sẽ ra URL của trang cũ (mất `draft`, trang tưởng
  // đang thanh toán giỏ rỗng và đẩy khách về /cart).
  const draftId = useSearchParams()?.get('draft') || null;
  const [draft, setDraft] = useState<bookingApi.BookingDraft | null>(null);
  const [status, setStatus] = useState<SourceStatus>('loading');
  const [expiredItems, setExpiredItems] = useState<ExpiredItem[]>([]);
  // Response về không theo thứ tự gửi (PATCH nối tiếp và GET khi chuyển bước): chỉ nhận bản mới hơn bản đã áp.
  const seq = useRef({ issued: 0, applied: 0 });
  const loadedFor = useRef<string | null>(null);

  // Bản mới nhất của đơn nháp và giỏ, để `fail` đọc được mà không phải dựng lại callback.
  const known = useRef<{ draft: bookingApi.BookingDraft | null; cart: typeof cart }>({ draft: null, cart });
  useEffect(() => { known.current = { draft, cart }; });

  const fail = useCallback((error: ApiError): boolean => {
    if (error.code === 'BOOKING_DRAFT_EXPIRED') {
      // POST /bookings báo hết hạn mà không kèm danh sách mục: suy từ đơn nháp đang mở. Mục còn trong giỏ là mục loại vào giỏ
      // được và đang nằm trong giỏ với cùng sản phẩm, cùng ngày (bản chép lúc Đặt ngay, R-CPY).
      const fromError = expiredItemsOf(error);
      const { draft: open, cart: basket } = known.current;
      setExpiredItems(fromError.length || !open ? fromError : open.items.map((item) => ({
        productId: item.product.productId, taxonomy: item.product.taxonomy,
        inCart: bookingApi.isCartEligible(item.product.taxonomy) && (basket
          ? basket.items.some((c) => c.product.productId === item.product.productId && c.usingDate === item.usingDate)
          : true),
      })));
      setStatus('expired');
      return true;
    }
    if (error.code === 'BOOKING_DRAFT_NOT_FOUND') {
      setStatus('not-found');
      return true;
    }
    return false;
  }, []);

  const track = useCallback(async (request: () => Promise<bookingApi.BookingDraft>): Promise<bookingApi.BookingDraft> => {
    const ticket = ++seq.current.issued;
    const response = await request();
    if (ticket > seq.current.applied) {
      seq.current.applied = ticket;
      setDraft(response);
      setStatus('ready');
    }
    return response;
  }, []);

  const refreshDraft = useCallback(async (): Promise<CheckoutData | null> => {
    if (!draftId) return null;
    try {
      return await track(() => bookingApi.getBookingDraft(draftId));
    } catch (error) {
      if (error instanceof ApiError && fail(error)) return null;
      console.warn('[checkout] GET /booking-drafts failed', error);
      return null;
    }
  }, [draftId, track, fail]);

  // Tải đơn nháp khi phiên đã sẵn sàng (khách chưa đăng nhập cũng đọc được đơn nháp của chính mình).
  useEffect(() => {
    if (!draftId) return;
    // Đổi sang đơn nháp khác trên cùng trang (hai lần Đặt ngay liên tiếp): bỏ dữ liệu của đơn nháp trước.
    if (loadedFor.current !== draftId) {
      loadedFor.current = draftId;
      setDraft(null);
      setExpiredItems([]);
      setStatus('loading');
    }
    if (authReady) void refreshDraft();
  }, [draftId, authReady, refreshDraft]);

  const updateDraftItem = useCallback(async (
    cartItemId: string, updates: UpdateCartItemRequest, options: { silent?: boolean } = {},
  ): Promise<ApiError | null> => {
    if (!draftId) return null;
    try {
      await track(() => bookingApi.updateBookingDraftItem(draftId, cartItemId, updates));
      return null;
    } catch (error) {
      const apiError = error instanceof ApiError ? error : new ApiError('Không cập nhật được lần đặt này.', 'INTERNAL_ERROR', 0, true);
      if (fail(apiError)) return apiError;
      if (apiError.code === 'CART_ITEM_NOT_FOUND') {
        await refreshDraft();
        return apiError;
      }
      if (!options.silent) showToast(apiError.message);
      return apiError;
    }
  }, [draftId, track, fail, refreshDraft, showToast]);

  const removeDraftItem = useCallback(async (cartItemId: string) => {
    if (!draftId) return;
    try {
      await track(() => bookingApi.removeBookingDraftItem(draftId, cartItemId));
    } catch (error) {
      if (error instanceof ApiError && fail(error)) return;
      await refreshDraft();
    }
  }, [draftId, track, fail, refreshDraft]);

  const removeCartItem = useCallback(async (cartItemId: string) => {
    await bookingApi.removeCartItem(cartItemId).then(() => refreshCart()).catch(() => refreshCart());
  }, [refreshCart]);

  return useMemo<CheckoutSource>(() => (draftId
    ? {
      kind: 'draft', draftId, data: draft, status, expiresAt: draft?.expiresAt ?? null, expiredItems,
      refresh: refreshDraft, updateItem: updateDraftItem, removeItem: removeDraftItem, fail,
    }
    : {
      kind: 'cart', draftId: null, data: cart, status: cart ? 'ready' : 'loading', expiresAt: null, expiredItems: [],
      refresh: refreshCart, updateItem: updateCartItem, removeItem: removeCartItem, fail: () => false,
    }), [draftId, draft, status, expiredItems, refreshDraft, updateDraftItem, removeDraftItem, fail, cart, refreshCart,
    updateCartItem, removeCartItem]);
}
