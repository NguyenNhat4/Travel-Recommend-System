/**
 * Giỏ hàng server-side, đơn nháp của Đặt ngay, giữ chỗ, thanh toán Stripe và huỷ đơn — qua BFF `/api/v1/*`
 * (docs/spec/hop-dong-tich-hop-frontend.md §4.4–§4.6, docs/spec/booking/so-do-luong-dat-cho-thanh-toan.md,
 * docs/spec/booking/dat-truc-tiep-theo-don-nhap.md).
 *
 * Giỏ chỉ nhận tour, trải nghiệm và tiện ích khác; khách sạn và vé máy bay đặt trực tiếp qua đơn nháp. Giỏ và đơn nháp dùng
 * được cả khi chưa đăng nhập (BFF tự gắn mã khách); tạo đơn thì cần đăng nhập.
 *
 * Web không gửi và không tự tính số tiền: mọi con số lấy từ `CartResponse` / `BookingResponse`.
 */
import type { components } from '../types/api.gen';
import { apiJson } from './http';

export type CartResponse = components['schemas']['CartResponse'];
export type ApiCartItem = components['schemas']['CartItem'];
export type AddCartItemRequest = components['schemas']['AddCartItemRequest'];
export type UpdateCartItemRequest = components['schemas']['UpdateCartItemRequest'];
export type BookingDraft = components['schemas']['BookingDraft'];
export type CreateBookingDraftRequest = components['schemas']['CreateBookingDraftRequest'];
export type RejectedDraftItem = components['schemas']['RejectedDraftItem'];
export type CheckoutRequest = components['schemas']['CheckoutRequest'];
export type CheckoutItemDetail = components['schemas']['CheckoutItemDetail'];
export type CheckoutTraveler = components['schemas']['CheckoutTraveler'];
export type CheckoutRoom = components['schemas']['CheckoutRoom'];
export type GuestCounts = components['schemas']['GuestCounts'];
export type FareLine = components['schemas']['FareLine'];
export type BookingTraveler = components['schemas']['BookingTraveler'];
export type ValidationFieldError = components['schemas']['ValidationFieldError'];
export type ApiBookingItem = components['schemas']['BookingItem'];
export type BookingResponse = components['schemas']['BookingResponse'];
export type BookingStatus = components['schemas']['BookingStatus'];
export type PaymentFailureReason = components['schemas']['PaymentFailureReason'];

const JSON_HEADERS = { 'Content-Type': 'application/json' };

export function getCart(): Promise<CartResponse> {
  return apiJson('/api/v1/cart', { cache: 'no-store' });
}

export function addCartItem(body: AddCartItemRequest): Promise<CartResponse> {
  return apiJson('/api/v1/cart/items', { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(body) });
}

export function updateCartItem(cartItemId: string, body: UpdateCartItemRequest): Promise<CartResponse> {
  return apiJson(`/api/v1/cart/items/${encodeURIComponent(cartItemId)}`, {
    method: 'PATCH', headers: JSON_HEADERS, body: JSON.stringify(body),
  });
}

export function removeCartItem(cartItemId: string): Promise<CartResponse> {
  return apiJson(`/api/v1/cart/items/${encodeURIComponent(cartItemId)}`, { method: 'DELETE' });
}

/** Đặt ngay: đơn nháp chỉ gồm các mục của lần đặt này, hiệu lực 30 phút (`expiresAt`). */
export function createBookingDraft(body: CreateBookingDraftRequest): Promise<BookingDraft> {
  return apiJson('/api/v1/booking-drafts', { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(body) });
}

/** `404 BOOKING_DRAFT_NOT_FOUND` khi không có hoặc của người khác; `410 BOOKING_DRAFT_EXPIRED` khi quá hạn. */
export function getBookingDraft(draftId: string): Promise<BookingDraft> {
  return apiJson(`/api/v1/booking-drafts/${encodeURIComponent(draftId)}`, { cache: 'no-store' });
}

export function updateBookingDraftItem(draftId: string, cartItemId: string, body: UpdateCartItemRequest): Promise<BookingDraft> {
  return apiJson(`/api/v1/booking-drafts/${encodeURIComponent(draftId)}/items/${encodeURIComponent(cartItemId)}`, {
    method: 'PATCH', headers: JSON_HEADERS, body: JSON.stringify(body),
  });
}

export function removeBookingDraftItem(draftId: string, cartItemId: string): Promise<BookingDraft> {
  return apiJson(`/api/v1/booking-drafts/${encodeURIComponent(draftId)}/items/${encodeURIComponent(cartItemId)}`, { method: 'DELETE' });
}

/** Loại sản phẩm thêm được vào giỏ; khách sạn và vé máy bay chỉ đặt trực tiếp (R-DIR-02, khớp `is_cart_eligible` của Backend). */
export function isCartEligible(taxonomy: string): boolean {
  return taxonomy !== 'hotel' && taxonomy !== 'flight';
}

/** Đường dẫn trang thanh toán của một đơn nháp. */
export function checkoutPathOf(draftId: string): string {
  return `/checkout?draft=${encodeURIComponent(draftId)}`;
}

/** 201 = đã giữ chỗ, chờ thanh toán; Web chuyển trình duyệt tới `payment.checkoutUrl`. */
export function createBooking(body: CheckoutRequest): Promise<BookingResponse> {
  return apiJson('/api/v1/bookings', { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(body) });
}

export function getBooking(referenceCode: string, signal?: AbortSignal): Promise<BookingResponse> {
  return apiJson(`/api/v1/bookings/${encodeURIComponent(referenceCode)}`, { cache: 'no-store', signal });
}

export function cancelBooking(referenceCode: string, reason?: string): Promise<BookingResponse> {
  return apiJson(`/api/v1/bookings/${encodeURIComponent(referenceCode)}/cancel`, {
    method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(reason ? { reason } : {}),
  });
}

/** Chuyển trình duyệt sang trang thanh toán do Stripe host. Tách hàm để test thay được. */
export function redirectToCheckout(url: string): void {
  window.location.assign(url);
}

/** Polling sau khi quay về từ Stripe: 2 giây/lần, tối đa 15 lần (spec booking §6.1). */
export const PAYMENT_POLL_INTERVAL_MS = 2000;
export const PAYMENT_POLL_MAX_ATTEMPTS = 15;

export function bookingItems(booking: BookingResponse): ApiBookingItem[] {
  return booking.groups.flatMap((group) => group.items);
}
