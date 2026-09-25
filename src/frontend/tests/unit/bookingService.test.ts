import { afterEach, describe, expect, it, vi } from 'vitest';
import * as booking from '../../src/services/booking';
import { ApiError } from '../../src/services/http';
import created from '../../../shared/mocks/booking/createBooking.201-default.json';
import pending from '../../../shared/mocks/booking/createBooking.409-pending-payment.json';
import unavailable from '../../../shared/mocks/booking/createBooking.503-payment-unavailable.json';
import cart from '../../../shared/mocks/booking/getCart.200-default.json';

const originalFetch = global.fetch;

function respond(status: number, body: unknown, headers: Record<string, string> = {}) {
  const fetchMock = vi.fn().mockImplementation(async () => new Response(JSON.stringify(body), {
    status, headers: { 'Content-Type': 'application/json', ...headers },
  }));
  global.fetch = fetchMock as unknown as typeof fetch;
  return fetchMock;
}

describe('booking service', () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('adds a cart item through the BFF and returns the whole CartResponse', async () => {
    const fetchMock = respond(200, cart);
    const result = await booking.addCartItem({ productId: 'nt-h-01', usingDate: '2026-10-15', quantity: 1, nights: 3 });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/v1/cart/items');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({ productId: 'nt-h-01', usingDate: '2026-10-15', quantity: 1, nights: 3 });
    expect(init.credentials).toBe('same-origin');
    expect(new Headers(init.headers).has('authorization')).toBe(false);
    expect(result.total).toBe(cart.total);
  });

  it('creates a hold without sending any amount and returns the Stripe checkout url', async () => {
    const fetchMock = respond(201, created);
    const body = {
      contact: { fullName: 'Nguyễn Minh Anh', email: 'minhanh@example.vn', phone: '0912345678' },
      itemDetails: [{ cartItemId: 'ci-8k3f2a', guestNames: ['Nguyễn Minh Anh'] }],
    };
    const result = await booking.createBooking(body);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/v1/bookings');
    expect(JSON.parse(init.body)).toEqual(body);
    expect(init.body).not.toMatch(/total|amount|price/i);
    expect(result.status).toBe('PENDING_PAYMENT');
    expect(result.payment?.checkoutUrl).toMatch(/^https:\/\/checkout\.stripe\.com\//);
  });

  it('turns the error envelope into an ApiError with code and details', async () => {
    respond(409, pending);
    const error = await booking.createBooking({ contact: created.contact, itemDetails: [] }).catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ code: 'BOOKING_PENDING_PAYMENT', status: 409, retryable: false });
    expect(error.details.referenceCode).toBe('VOTA-20260916-8K3F');

    respond(503, unavailable, { 'Retry-After': '5' });
    const outage = await booking.createBooking({ contact: created.contact, itemDetails: [] }).catch((e) => e);
    expect(outage).toMatchObject({ code: 'PAYMENT_PROVIDER_UNAVAILABLE', retryable: true });
  });

  it('reports a network failure as the client-side NETWORK_ERROR, retryable', async () => {
    global.fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch')) as unknown as typeof fetch;
    const error = await booking.getBooking('VOTA-20260916-8K3F').catch((e) => e);
    expect(error).toMatchObject({ code: 'NETWORK_ERROR', retryable: true, status: 0 });
  });

  it('cancels with an optional reason and encodes the reference code', async () => {
    const fetchMock = respond(200, created);
    await booking.cancelBooking('VOTA-20260916-8K3F', 'Đổi kế hoạch');
    await booking.cancelBooking('VOTA-20260916-8K3F');
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/bookings/VOTA-20260916-8K3F/cancel');
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ reason: 'Đổi kế hoạch' });
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({});
  });
});
