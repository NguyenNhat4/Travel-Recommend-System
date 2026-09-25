// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import pendingFixture from '../../../shared/mocks/booking/createBooking.201-default.json';
import confirmedFixture from '../../../shared/mocks/booking/getBooking.200-default.json';
import failedFixture from '../../../shared/mocks/booking/getBooking.200-payment-failed.json';
import expiredFixture from '../../../shared/mocks/booking/getBooking.200-expired.json';
import cancelledFixture from '../../../shared/mocks/booking/getBooking.200-cancelled-refunded.json';
import tooLateFixture from '../../../shared/mocks/booking/cancelBooking.409-too-late.json';
import type { BookingResponse } from '../../src/services/booking';

const api = vi.hoisted(() => ({
  getBooking: vi.fn(),
  cancelBooking: vi.fn(),
  redirectToCheckout: vi.fn(),
  fetchRecommendations: vi.fn(),
}));
const travel = vi.hoisted(() => ({
  getBookingByCode: vi.fn(),
  rememberBooking: vi.fn(),
  refreshCart: vi.fn(),
  markJustBooked: vi.fn(),
  navigate: vi.fn(),
  showToast: vi.fn(),
  currentPersona: { id: 'VP0000001', name: 'Minh Anh' },
  activeEvents: [],
}));

vi.mock('../../src/services/booking', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/services/booking')>()),
  getBooking: api.getBooking,
  cancelBooking: api.cancelBooking,
  redirectToCheckout: api.redirectToCheckout,
  PAYMENT_POLL_INTERVAL_MS: 5,
}));
vi.mock('../../src/services/recsys', () => ({ fetchRecommendations: api.fetchRecommendations }));
vi.mock('../../src/context/TravelContext', () => ({ useTravel: () => travel }));

import { ConfirmationView } from '../../src/components/confirmation/ConfirmationView';
import { ApiError } from '../../src/services/http';

const NOW = Date.parse('2026-09-16T10:30:00Z');
const clone = (b: unknown) => JSON.parse(JSON.stringify(b)) as BookingResponse;
const pending = () => clone(pendingFixture);
const confirmed = () => clone(confirmedFixture);

function apiError(body: { error: { code: string; message: string; retryable: boolean; details?: any } }, status: number) {
  const e = body.error;
  return new ApiError(e.message, e.code, status, e.retryable, null, e.details ?? null);
}

describe('ConfirmationView — trạng thái đơn', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(NOW);
    travel.getBookingByCode.mockReturnValue(undefined);
    api.fetchRecommendations.mockResolvedValue({
      strategy: 'cross_vertical', destination: 'Nha Trang', recommendations: [],
      diagnostics: { eventsUsed: 1, coldStart: false, excludedVerticals: [], modelVersion: 't' }, generatedAt: '',
    });
  });
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it('shows the hold with countdown and continues to the same Stripe session', async () => {
    api.getBooking.mockResolvedValue(pending());
    render(<ConfirmationView referenceCode="VOTA-20260916-8K3F" />);
    expect(await screen.findByText('Đơn đang được giữ chỗ')).toBeTruthy();
    expect(screen.getByTestId('hold-countdown').textContent).toBe('22:00');
    fireEvent.click(screen.getByText('Tiếp tục thanh toán'));
    expect(api.redirectToCheckout).toHaveBeenCalledWith(pendingFixture.payment.checkoutUrl);
    expect(api.fetchRecommendations).not.toHaveBeenCalled();
  });

  it('polls after returning from Stripe until the webhook confirmed the booking, then shows next-trip recs', async () => {
    api.getBooking.mockResolvedValueOnce(pending()).mockResolvedValueOnce(pending()).mockResolvedValue(confirmed());
    render(<ConfirmationView referenceCode="VOTA-20260916-8K3F" paymentReturn="return" />);
    expect(await screen.findByText('Đang kiểm tra thanh toán...')).toBeTruthy();
    expect(await screen.findByText('Đặt chỗ thành công!')).toBeTruthy();
    expect(api.getBooking.mock.calls.length).toBeGreaterThanOrEqual(3);
    await waitFor(() => expect(api.fetchRecommendations).toHaveBeenCalledWith(
      expect.objectContaining({ k: 4, destination: 'Nha Trang' })));
    expect(travel.markJustBooked).toHaveBeenCalled();
    expect(travel.refreshCart).toHaveBeenCalled();
  });

  it('tells the customer the money arrived while the booking is still being confirmed', async () => {
    const paid = pending();
    paid.payment!.status = 'SUCCEEDED';
    paid.payment!.checkoutUrl = null;
    api.getBooking.mockResolvedValue(paid);
    render(<ConfirmationView referenceCode="VOTA-20260916-8K3F" />);
    expect(await screen.findByText('Đã nhận thanh toán, đang xác nhận đơn')).toBeTruthy();
  });

  it('treats a hold past its deadline as expired and points back to the cart', async () => {
    const late = pending();
    late.holdExpiresAt = '2026-09-16T10:29:00Z';
    api.getBooking.mockResolvedValue(late);
    render(<ConfirmationView referenceCode="VOTA-20260916-8K3F" />);
    expect(await screen.findByText('Hết thời gian giữ chỗ')).toBeTruthy();
    expect(screen.queryByText('Tiếp tục thanh toán')).toBeNull();
  });

  it.each([
    [failedFixture, 'Thanh toán không thành công', 'Thanh toán không thành công sau 3 lần. Giỏ hàng vẫn còn, bạn có thể đặt lại.'],
    [expiredFixture, 'Hết thời gian giữ chỗ', 'Đơn chưa được thanh toán trong 30 phút. Giỏ hàng vẫn còn, bạn có thể đặt lại.'],
    [cancelledFixture, 'Đã huỷ đơn', 'Đã hoàn 12.840.000 ₫ về thẻ.'],
  ])('renders closed booking %#', async (fixture, title, text) => {
    api.getBooking.mockResolvedValue(clone(fixture));
    render(<ConfirmationView referenceCode={fixture.referenceCode} />);
    expect(await screen.findByText(title)).toBeTruthy();
    expect(screen.getByText(text.replace(/ /g, ' '), { normalizer: (s) => s.replace(/ /g, ' ') })).toBeTruthy();
    expect(api.fetchRecommendations).not.toHaveBeenCalled();
    expect(screen.queryByText('Huỷ đơn')).toBeNull();
  });

  it('shows not found for someone else’s or unknown reference', async () => {
    api.getBooking.mockRejectedValue(new ApiError('x', 'BOOKING_NOT_FOUND', 404, false));
    render(<ConfirmationView referenceCode="VOTA-20260916-ZZZZ" />);
    expect(await screen.findByText('Không tìm thấy đơn đặt chỗ này')).toBeTruthy();
  });

  it('cancels a paid booking in time after showing the refund amount', async () => {
    api.getBooking.mockResolvedValue(confirmed());
    api.cancelBooking.mockResolvedValue(clone(cancelledFixture));
    render(<ConfirmationView referenceCode="VOTA-20260916-8K3F" />);
    fireEvent.click(await screen.findByText('Huỷ đơn'));
    const dialog = screen.getByRole('dialog');
    expect(dialog.textContent).toContain('12.840.000');
    expect(dialog.textContent).toContain('không thể hoàn tác');
    fireEvent.click(screen.getByText('Xác nhận huỷ'));
    expect(await screen.findByText('Đã huỷ đơn')).toBeTruthy();
    expect(api.cancelBooking).toHaveBeenCalledWith('VOTA-20260916-8K3F');
  });

  it('explains the deadline when the backend says it is too late', async () => {
    api.getBooking.mockResolvedValue(confirmed());
    api.cancelBooking.mockRejectedValue(apiError(tooLateFixture, 409));
    render(<ConfirmationView referenceCode="VOTA-20260916-8K3F" />);
    fireEvent.click(await screen.findByText('Huỷ đơn'));
    fireEvent.click(screen.getByText('Xác nhận huỷ'));
    expect((await screen.findByRole('alert')).textContent).toMatch(/Đã quá hạn huỷ trực tuyến \(hạn: .*14\/10\/2026\)/);
  });
});
