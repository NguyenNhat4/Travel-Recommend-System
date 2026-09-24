import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  ApiError,
  addCartItem,
  bookingRecordFromResponse,
  cartItemsFromResponse,
  createBooking,
  firstOpenDate,
  isOpen,
  type BookingResponse,
  type CartResponse,
  type ProductSummary,
} from '../../src/services/booking';

const room: ProductSummary = {
  productId: '11111111-1111-4111-8111-111111111111',
  name: 'Amanda Boutique Hotel - Phòng Deluxe Giường Đôi',
  taxonomy: 'hotel',
  destination: 'Đà Nẵng',
  status: 'ACTIVE',
  unitPrice: 550000,
  currency: 'VND',
  priceUnit: 'PER_NIGHT',
  available: true,
  availableFrom: '2026-09-24',
  availableTo: '2026-10-23',
  attributes: { level: 'room', availability: { from: '2026-09-24', days: 30, calendar: '1100' + '1'.repeat(26) } },
};

describe('availability shown before booking (same rule as backend domain/booking)', () => {
  it('needs every night open inside the sale window', () => {
    expect(isOpen(room, '2026-09-24', 2)).toBe(true);
    expect(isOpen(room, '2026-09-25', 2)).toBe(false); // đêm 26/09 kín
    expect(isOpen(room, '2026-10-24', 1)).toBe(false); // ngoài cửa sổ bán
    expect(isOpen(room, '2026-10-22', 3)).toBe(false); // vượt cuối lịch
    expect(isOpen({ ...room, attributes: {} }, '2026-09-26', 5)).toBe(true); // không có lịch thì không chặn
  });

  it('defaults to the first open night from today', () => {
    expect(firstOpenDate(room, '2026-09-25')).toBe('2026-09-25');
    expect(firstOpenDate(room, '2026-09-26')).toBe('2026-09-28');
    expect(firstOpenDate({ ...room, attributes: { availability: { from: '2026-09-24', calendar: '0'.repeat(30) } } },
      '2026-09-24')).toBeNull();
  });
});

describe('booking service HTTP', () => {
  const originalFetch = global.fetch;
  beforeEach(() => vi.restoreAllMocks());
  afterEach(() => { global.fetch = originalFetch; });

  it('surfaces the Vietnamese message and code of the error envelope', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ error: { code: 'VALIDATION_ERROR', message: 'Vui lòng chọn một hạng phòng', retryable: false,
        details: { fields: ['productId'] } } }),
    } as Response);
    const error = await addCartItem({ productId: 'property', usingDate: '2026-10-01', quantity: 1 }).catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ code: 'VALIDATION_ERROR', status: 400, message: 'Vui lòng chọn một hạng phòng' });
  });

  it('posts the checkout to the BFF', async () => {
    let request: { url: string; init?: RequestInit } | null = null;
    global.fetch = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
      request = { url, init };
      return { ok: true, status: 201, json: async () => ({ referenceCode: 'VOTA-20260924-AB12' }) } as Response;
    });
    await createBooking({ contact: { fullName: 'A', email: 'a@b.vn', phone: '0912345678' }, itemDetails: [] });
    expect(request!.url).toBe('/api/v1/bookings');
    expect(request!.init?.method).toBe('POST');
    expect(JSON.parse(String(request!.init?.body)).contact.phone).toBe('0912345678');
  });
});

describe('response mapping keeps backend money', () => {
  it('maps cart lines with nights and the backend lineTotal', () => {
    const cart: CartResponse = {
      cartId: 'c1', cdpUserId: 'VP1', itemCount: 1, subtotal: 2_200_000, total: 2_200_000, currency: 'VND',
      updatedAt: '2026-09-24T10:00:00Z',
      items: [{ cartItemId: 'ci-1', product: room, usingDate: '2026-09-24', quantity: 2, nights: 2, lineTotal: 2_200_000 }],
    };
    const [item] = cartItemsFromResponse(cart);
    expect(item).toMatchObject({ id: 'ci-1', productId: room.productId, checkOutDate: '2026-09-26', nights: 2,
      quantity: 2, totalPrice: 2_200_000, destination: 'Đà Nẵng' });
  });

  it('flattens booking groups and keeps the reference code', () => {
    const booking: BookingResponse = {
      referenceCode: 'VOTA-20260924-AB12', createdAt: '2026-09-24T10:00:00Z', status: 'CONFIRMED',
      contact: { fullName: 'A', email: 'a@b.vn', phone: '0912345678' }, total: 1_100_000, currency: 'VND',
      groups: [{ destination: 'Đà Nẵng', eventGroupId: 'WEB20260924ABCDEF', groupTotal: 1_100_000, items: [{
        bookingItemId: 'bi-1', product: room, usingDate: '2026-09-24', quantity: 1, nights: 2, lineTotal: 1_100_000,
        guestNames: ['A'], specialRequest: null }] }],
    };
    const record = bookingRecordFromResponse(booking, 'VP1');
    expect(record).toMatchObject({ referenceCode: 'VOTA-20260924-AB12', destination: 'Đà Nẵng', totalAmount: 1_100_000,
      contact: { phoneNumber: '0912345678' } });
    expect(record.items).toHaveLength(1);
  });
});
