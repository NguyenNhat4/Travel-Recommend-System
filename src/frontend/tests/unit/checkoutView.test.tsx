// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import cartFixture from '../../../shared/mocks/booking/getCart.200-default.json';
import unavailableCart from '../../../shared/mocks/booking/getCart.200-item-unavailable.json';
import createdFixture from '../../../shared/mocks/booking/createBooking.201-default.json';
import pendingError from '../../../shared/mocks/booking/createBooking.409-pending-payment.json';
import priceChanged from '../../../shared/mocks/booking/createBooking.409-price-changed.json';
import providerDown from '../../../shared/mocks/booking/createBooking.503-payment-unavailable.json';

const api = vi.hoisted(() => ({
  createBooking: vi.fn(),
  getBooking: vi.fn(),
  cancelBooking: vi.fn(),
  redirectToCheckout: vi.fn(),
}));
const travel = vi.hoisted(() => ({
  cart: null as unknown,
  currentPersona: { id: 'VP0000001', name: 'Nguyễn Minh Anh', email: 'minhanh@example.vn' },
  authReady: true,
  navigate: vi.fn(),
  refreshCart: vi.fn(),
  updateCartItem: vi.fn(),
  rememberBooking: vi.fn(),
  openLoginModal: vi.fn(),
}));

vi.mock('../../src/services/booking', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/services/booking')>()),
  ...api,
}));
vi.mock('../../src/context/TravelContext', () => ({ useTravel: () => travel }));

import { CheckoutView } from '../../src/components/checkout/CheckoutView';
import { ApiError } from '../../src/services/http';

function apiError(body: { error: { code: string; message: string; retryable: boolean; details?: any } }, status: number) {
  const e = body.error;
  return new ApiError(e.message, e.code, status, e.retryable, 'req-1', e.details ?? null);
}

const payButton = () => screen.getByRole('button', { name: /Thanh toán/ }) as HTMLButtonElement;

function fillForm() {
  fireEvent.change(screen.getByLabelText('Số điện thoại'), { target: { value: '0912345678' } });
  fireEvent.click(screen.getByRole('checkbox'));
}

describe('CheckoutView', () => {
  beforeEach(() => {
    travel.cart = JSON.parse(JSON.stringify(cartFixture));
  });
  afterEach(() => cleanup());

  it('keeps Pay disabled until contact, terms and payment method are valid; only Stripe is selectable', () => {
    render(<CheckoutView />);
    expect(payButton().disabled).toBe(true);
    const radios = screen.getAllByRole('radio') as HTMLInputElement[];
    expect(radios.map((r) => [r.value, r.checked, r.disabled])).toEqual([
      ['stripe', true, false], ['ewallet', false, true], ['bank_transfer', false, true],
    ]);
    expect(screen.getAllByText('Sắp có')).toHaveLength(2);
    fireEvent.change(screen.getByLabelText('Số điện thoại'), { target: { value: '912345678' } });
    fireEvent.click(screen.getByRole('checkbox'));
    expect(payButton().disabled).toBe(true);                         // số điện thoại sai định dạng
    fireEvent.change(screen.getByLabelText('Số điện thoại'), { target: { value: '0912345678' } });
    expect(payButton().disabled).toBe(false);
    expect(payButton().textContent).toContain('12.840.000');         // tổng lấy từ CartResponse
  });

  it('creates the hold with per-item details and redirects to the Stripe page', async () => {
    api.createBooking.mockResolvedValue(createdFixture);
    render(<CheckoutView />);
    fillForm();
    fireEvent.click(payButton());
    await waitFor(() => expect(api.redirectToCheckout).toHaveBeenCalledWith(createdFixture.payment.checkoutUrl));
    expect(api.createBooking).toHaveBeenCalledWith({
      contact: { fullName: 'Nguyễn Minh Anh', email: 'minhanh@example.vn', phone: '0912345678' },
      itemDetails: [
        { cartItemId: 'ci-8k3f2a', guestNames: ['Nguyễn Minh Anh'] },   // hotel: 1 tên khách
        { cartItemId: 'ci-2m9d7c' },                                   // vé tham quan: không gửi guestNames
      ],
    });
    expect(travel.rememberBooking).toHaveBeenCalledWith(createdFixture);
  });

  it('offers to continue or cancel the existing hold on 409 BOOKING_PENDING_PAYMENT', async () => {
    api.createBooking.mockRejectedValue(apiError(pendingError, 409));
    api.getBooking.mockResolvedValue(createdFixture);
    render(<CheckoutView />);
    fillForm();
    fireEvent.click(payButton());
    const dialog = await screen.findByRole('dialog');
    expect(dialog.textContent).toContain('VOTA-20260916-8K3F');
    fireEvent.click(screen.getByText('Tiếp tục thanh toán đơn đó'));
    await waitFor(() => expect(api.redirectToCheckout).toHaveBeenCalledWith(createdFixture.payment.checkoutUrl));
  });

  it('shows the provider outage with a retry button and stays on the page', async () => {
    api.createBooking.mockRejectedValueOnce(apiError(providerDown, 503)).mockResolvedValue(createdFixture);
    render(<CheckoutView />);
    fillForm();
    fireEvent.click(payButton());
    expect((await screen.findByRole('alert')).textContent).toContain('Cổng thanh toán tạm thời không phản hồi');
    fireEvent.click(screen.getByText('Thử lại'));
    await waitFor(() => expect(api.redirectToCheckout).toHaveBeenCalled());
  });

  it('acknowledges a price change by re-saving the cart line before the customer pays again', async () => {
    api.createBooking.mockRejectedValue(apiError(priceChanged, 409));
    render(<CheckoutView />);
    fillForm();
    fireEvent.click(payButton());
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toMatch(/VinWonders Nha Trang đã đổi từ 880\.000.* thành 950\.000/);
    fireEvent.click(screen.getByText('Cập nhật và tiếp tục'));
    await waitFor(() => expect(travel.updateCartItem).toHaveBeenCalledWith('ci-2m9d7c', { quantity: 3 }));
  });

  it('blocks payment while the cart holds a sold-out item', () => {
    travel.cart = JSON.parse(JSON.stringify(unavailableCart));
    render(<CheckoutView />);
    fillForm();
    expect(payButton().disabled).toBe(true);
  });
});
