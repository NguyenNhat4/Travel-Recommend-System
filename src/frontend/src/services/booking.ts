/**
 * Giỏ hàng server-side, giữ chỗ, thanh toán Stripe và huỷ đơn — qua BFF `/api/v1/*`
 * (docs/spec/hop-dong-tich-hop-frontend.md §4.4–§4.6, docs/spec/booking/so-do-luong-dat-cho-thanh-toan.md).
 *
 * Web không gửi và không tự tính số tiền: mọi con số lấy từ `CartResponse` / `BookingResponse`.
 */
import type { components } from '../types/api.gen';
import { apiJson } from './http';

export type CartResponse = components['schemas']['CartResponse'];
export type ApiCartItem = components['schemas']['CartItem'];
export type AddCartItemRequest = components['schemas']['AddCartItemRequest'];
export type UpdateCartItemRequest = components['schemas']['UpdateCartItemRequest'];
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
