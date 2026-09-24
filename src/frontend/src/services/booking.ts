/**
 * Chi tiết sản phẩm, giỏ phía server và đặt chỗ (docs/spec/hop-dong-tich-hop-frontend.md §4.3–4.6).
 *
 * Giỏ lưu ở backend theo tài khoản; checkout ghi purchase sang CDP trước khi trả 201, nên
 * GET /recommendations gọi ngay sau đó đã phản ánh lượt đặt (vòng K1). Mọi số tiền lấy từ response,
 * Web không tự cộng.
 */
import type { components } from '../types/api.gen';
import type { BookingRecord, CartItem, Destination, Product, Taxonomy } from '../types/travel';
import { mapProductSummaryToProduct } from './assistant';
import { apiFetch } from './http';

type Schemas = components['schemas'];
export type ProductSummary = Schemas['ProductSummary'];
export type ProductDetail = Schemas['ProductDetail'];
export type CartResponse = Schemas['CartResponse'];
export type BookingResponse = Schemas['BookingResponse'];
export type CheckoutRequest = Schemas['CheckoutRequest'];

/** Lỗi theo Error Envelope; `message` là tiếng Việt, hiển thị thẳng cho người dùng (backend §8.1). */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly code: string,
    readonly status: number,
    readonly retryable = false,
    readonly details?: Record<string, unknown>,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await apiFetch(path, {
    ...init,
    headers: { Accept: 'application/json', ...(init.body ? { 'Content-Type': 'application/json' } : {}) },
    cache: 'no-store',
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const error = body?.error;
    throw new ApiError(
      error?.message || 'Có lỗi xảy ra. Vui lòng thử lại.',
      error?.code || 'INTERNAL_ERROR',
      response.status,
      Boolean(error?.retryable),
      error?.details,
    );
  }
  return body as T;
}

const json = (value: unknown) => JSON.stringify(value);

export const fetchProductDetail = (productId: string) =>
  request<ProductDetail>(`/api/v1/products/${encodeURIComponent(productId)}`);

export const fetchCart = () => request<CartResponse>('/api/v1/cart');

export const addCartItem = (body: Schemas['AddCartItemRequest']) =>
  request<CartResponse>('/api/v1/cart/items', { method: 'POST', body: json(body) });

export const updateCartItem = (cartItemId: string, body: Schemas['UpdateCartItemRequest']) =>
  request<CartResponse>(`/api/v1/cart/items/${encodeURIComponent(cartItemId)}`, { method: 'PATCH', body: json(body) });

export const removeCartItem = (cartItemId: string) =>
  request<CartResponse>(`/api/v1/cart/items/${encodeURIComponent(cartItemId)}`, { method: 'DELETE' });

export const createBooking = (body: CheckoutRequest) =>
  request<BookingResponse>('/api/v1/bookings', { method: 'POST', body: json(body) });

export const fetchBooking = (referenceCode: string) =>
  request<BookingResponse>(`/api/v1/bookings/${encodeURIComponent(referenceCode)}`);

// ---- chiếu sang kiểu UI đang dùng (types/travel.ts) ----

function addDays(isoDate: string, days: number): string {
  const date = new Date(`${isoDate}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

/** ProductSummary/ProductDetail → Product của UI, giữ mô tả và điểm đánh giá khi có. */
export function toProduct(summary: ProductSummary | ProductDetail): Product {
  const product = mapProductSummaryToProduct(summary);
  const detail = summary as ProductDetail;
  return {
    ...product,
    description: detail.description || product.description,
    availableFrom: summary.availableFrom ?? undefined,
    availableTo: summary.availableTo ?? undefined,
    aggregateRating: summary.rating != null && summary.reviewCount != null
      ? { score: summary.rating, count: summary.reviewCount }
      : undefined,
  };
}

type Line = { product: ProductSummary; usingDate: string; quantity: number; nights?: number | null; lineTotal: number };

function toCartItem(id: string, line: Line): CartItem {
  const product = toProduct(line.product);
  return {
    id,
    productId: product.id,
    product,
    destination: product.destination,
    taxonomy: product.taxonomy as Taxonomy,
    usingDate: line.usingDate,
    checkOutDate: line.nights ? addDays(line.usingDate, line.nights) : undefined,
    quantity: line.quantity,
    nights: line.nights ?? undefined,
    totalPrice: line.lineTotal,
  };
}

export function cartItemsFromResponse(cart: CartResponse): CartItem[] {
  return cart.items.map((item) => toCartItem(item.cartItemId, item));
}

export function bookingRecordFromResponse(booking: BookingResponse, userId: string): BookingRecord {
  const items = booking.groups.flatMap((group) => group.items.map((item) => toCartItem(item.bookingItemId, item)));
  return {
    referenceCode: booking.referenceCode,
    createdAt: booking.createdAt,
    userId,
    contact: { fullName: booking.contact.fullName, email: booking.contact.email, phoneNumber: booking.contact.phone },
    items,
    totalAmount: booking.total,
    destination: booking.groups[0]?.destination as Destination,
  };
}

// ---- hiển thị trước tình trạng chỗ; backend kiểm lại khi thêm giỏ và checkout (backend §7.1–7.2) ----

/**
 * Còn chỗ cho `days` ngày liên tiếp từ `start`: nằm trong cửa sổ bán và lịch `attributes.availability`
 * là "1" ở mọi ngày. Cùng quy tắc với `domain/booking/rules.py` của backend.
 */
export function isOpen(product: Pick<ProductSummary, 'availableFrom' | 'availableTo' | 'attributes'>,
                       start: string, days: number): boolean {
  if (product.availableFrom && start < product.availableFrom) return false;
  if (product.availableTo && start > product.availableTo) return false;
  const availability = (product.attributes as Record<string, unknown> | undefined)?.availability as
    { from?: string; calendar?: string } | undefined;
  if (!availability?.calendar || !availability.from) return true;
  const offset = Math.round((Date.parse(`${start}T00:00:00Z`) - Date.parse(`${availability.from}T00:00:00Z`)) / 86_400_000);
  if (offset < 0 || offset + days > availability.calendar.length) return false;
  return [...availability.calendar.slice(offset, offset + days)].every((c) => c === '1');
}

/** Ngày sớm nhất từ `today` còn đủ `days` ngày trống; null khi trong cửa sổ không còn ngày nào. */
export function firstOpenDate(product: Pick<ProductSummary, 'availableFrom' | 'availableTo' | 'attributes'>,
                              today: string, days = 1): string | null {
  let day = product.availableFrom && product.availableFrom > today ? product.availableFrom : today;
  const last = product.availableTo || addDays(today, 60);
  for (let i = 0; i <= 90 && day <= last; i += 1, day = addDays(day, 1)) {
    if (isOpen(product, day, days)) return day;
  }
  return null;
}

export { addDays };
