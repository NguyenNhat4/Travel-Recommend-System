// @vitest-environment jsdom
import React from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import pendingFixture from '../../../shared/mocks/booking/createBooking.201-default.json';
import confirmedFixture from '../../../shared/mocks/booking/getBooking.200-default.json';
import failedFixture from '../../../shared/mocks/booking/getBooking.200-payment-failed.json';
import expiredFixture from '../../../shared/mocks/booking/getBooking.200-expired.json';
import cancelledFixture from '../../../shared/mocks/booking/getBooking.200-cancelled-refunded.json';
import tooLateFixture from '../../../shared/mocks/booking/cancelBooking.409-too-late.json';
import familyFixture from '../../../shared/mocks/booking/createBooking.201-family.json';
import rebookDraft from '../../../shared/mocks/booking/createBookingDraft.201-hotel.json';
import notRebookable from '../../../shared/mocks/booking/createBooking.409-pending-payment.json';
import popularFixture from '../../../shared/mocks/catalog/listProducts.200-popular.json';
import type { BookingResponse } from '../../src/services/booking';

const api = vi.hoisted(() => ({
  getBooking: vi.fn(),
  cancelBooking: vi.fn(),
  redirectToCheckout: vi.fn(),
  createBookingDraft: vi.fn(),
  fetchRecommendations: vi.fn(),
}));
const catalog = vi.hoisted(() => ({ getProduct: vi.fn() }));
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

vi.mock('../../src/context/AssistantProvider', () => ({ useAssistant: () => ({ openFloatingWidget: vi.fn() }) }));
vi.mock('../../src/services/booking', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/services/booking')>()),
  getBooking: api.getBooking,
  cancelBooking: api.cancelBooking,
  redirectToCheckout: api.redirectToCheckout,
  createBookingDraft: api.createBookingDraft,
  PAYMENT_POLL_INTERVAL_MS: 5,
}));
vi.mock('../../src/services/recsys', () => ({ fetchRecommendations: api.fetchRecommendations }));
vi.mock('../../src/services/catalog', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/services/catalog')>()),
  getProduct: catalog.getProduct,
}));
vi.mock('../../src/context/TravelContext', () => ({ useTravel: () => travel }));

import { ConfirmationView } from '../../src/components/confirmation/ConfirmationView';
import { resetProductInfoCache } from '../../src/components/confirmation/useProductInfo';
import { productFromApi } from '../../src/services/catalog';
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
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    api.getBooking.mockResolvedValueOnce(pending()).mockResolvedValueOnce(pending()).mockResolvedValue(confirmed());
    render(<ConfirmationView referenceCode="VOTA-20260916-8K3F" paymentReturn="return" />);
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });
    expect(screen.getByText('Đang kiểm tra thanh toán...')).toBeTruthy();
    expect(api.getBooking).toHaveBeenCalledTimes(1);
    expect(api.fetchRecommendations).not.toHaveBeenCalled();

    // Flush each poll separately so React commits and schedules the next one.
    await act(async () => { await vi.advanceTimersByTimeAsync(5); });
    expect(screen.getByText('Đang kiểm tra thanh toán...')).toBeTruthy();
    expect(api.getBooking).toHaveBeenCalledTimes(2);
    expect(api.fetchRecommendations).not.toHaveBeenCalled();
    await act(async () => { await vi.advanceTimersByTimeAsync(5); });
    expect(screen.getByText('Đặt chỗ thành công!')).toBeTruthy();
    expect(api.getBooking).toHaveBeenCalledTimes(3);
    expect(api.fetchRecommendations).toHaveBeenCalledWith(
      expect.objectContaining({ k: 4, destination: 'Nha Trang' }));
    expect(travel.markJustBooked).toHaveBeenCalled();
    expect(travel.refreshCart).toHaveBeenCalled();
    await act(async () => { await vi.advanceTimersByTimeAsync(5); });
    expect(api.getBooking).toHaveBeenCalledTimes(3);
  });

  it('tells the customer the money arrived while the booking is still being confirmed', async () => {
    const paid = pending();
    paid.payment!.status = 'SUCCEEDED';
    paid.payment!.checkoutUrl = null;
    api.getBooking.mockResolvedValue(paid);
    render(<ConfirmationView referenceCode="VOTA-20260916-8K3F" />);
    expect(await screen.findByText('Đã nhận thanh toán, đang xác nhận đơn')).toBeTruthy();
  });

  it('treats a hold past its deadline as expired and offers to rebook', async () => {
    const late = pending();
    late.holdExpiresAt = '2026-09-16T10:29:00Z';
    api.getBooking.mockResolvedValue(late);
    render(<ConfirmationView referenceCode="VOTA-20260916-8K3F" />);
    expect(await screen.findByText('Hết thời gian giữ chỗ')).toBeTruthy();
    expect(screen.queryByText('Tiếp tục thanh toán')).toBeNull();
    expect(screen.getByRole('button', { name: 'Đặt lại' })).toBeTruthy();
  });

  it.each([
    [failedFixture, 'Thanh toán không thành công', 'Thanh toán không thành công sau 3 lần. Bạn có thể đặt lại các dịch vụ của đơn này theo giá hiện tại.'],
    [expiredFixture, 'Hết thời gian giữ chỗ', 'Đơn chưa được thanh toán trong 30 phút. Bạn có thể đặt lại các dịch vụ của đơn này theo giá hiện tại.'],
    [cancelledFixture, 'Đã huỷ đơn', 'Đã hoàn 12.840.000 ₫ về thẻ.'],
  ])('renders closed booking %#', async (fixture, title, text) => {
    api.getBooking.mockResolvedValue(clone(fixture));
    render(<ConfirmationView referenceCode={fixture.referenceCode} />);
    expect(await screen.findByText(title)).toBeTruthy();
    expect(screen.getByText(text.replace(/ /g, ' '), { normalizer: (s) => s.replace(/ /g, ' ') })).toBeTruthy();
    expect(api.fetchRecommendations).not.toHaveBeenCalled();
    expect(screen.queryByText('Huỷ đơn')).toBeNull();
  });

  it.each([[failedFixture], [expiredFixture]])('"Đặt lại" on an unpaid order %# makes a new draft from the order and opens its payment page', async (fixture) => {
    api.getBooking.mockResolvedValue(clone(fixture));
    api.createBookingDraft.mockResolvedValue(rebookDraft);
    render(<ConfirmationView referenceCode={fixture.referenceCode} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Đặt lại' }));
    await waitFor(() => expect(travel.navigate).toHaveBeenCalledWith(`/checkout?draft=${rebookDraft.draftId}`));
    // Chỉ gửi mã đơn: mục, số khách và giá do Backend dựng lại theo giá hiện tại; không chép tên hay ngày sinh hành khách (R-RBK).
    expect(api.createBookingDraft).toHaveBeenCalledWith({ fromBooking: fixture.referenceCode, allowPartial: true });
    expect(travel.navigate).not.toHaveBeenCalledWith('/cart');
  });

  it('"Đặt lại" says which part could not be rebooked, and stays on the page when the backend refuses', async () => {
    api.getBooking.mockResolvedValue(clone(expiredFixture));
    api.createBookingDraft.mockResolvedValueOnce({
      ...rebookDraft,
      rejectedItems: [{ productId: 'nt-a-02', usingDate: '2026-10-16', code: 'PRODUCT_UNAVAILABLE', message: 'Sản phẩm đã hết chỗ.' }],
    });
    render(<ConfirmationView referenceCode={expiredFixture.referenceCode} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Đặt lại' }));
    await waitFor(() => expect(travel.showToast).toHaveBeenCalledWith('1 dịch vụ không còn đặt được nên không nằm trong lần đặt lại này.'));

    travel.navigate.mockClear();
    api.createBookingDraft.mockRejectedValueOnce(apiError(notRebookable as any, 409));
    fireEvent.click(screen.getByRole('button', { name: 'Đặt lại' }));
    await waitFor(() => expect(travel.showToast).toHaveBeenCalledWith(notRebookable.error.message));
    expect(travel.navigate).not.toHaveBeenCalled();
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

describe('ConfirmationView — khung chờ (product.md §4.6.3)', () => {
  const recsFor = (count: number) => ({
    strategy: 'cross_vertical', destination: 'Nha Trang',
    recommendations: popularFixture.results.slice(0, count).map((item, i) => ({
      product: productFromApi(item as never), score: 0.8, rank: i + 1, because: [],
    })),
    diagnostics: { eventsUsed: 1, coldStart: false, excludedVerticals: [], modelVersion: 't' }, generatedAt: '',
  });
  const recsSkeleton = () => screen.queryByRole('status', { name: 'Đang tải gợi ý cho chuyến đi' });

  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(NOW);
    travel.getBookingByCode.mockReturnValue(undefined);
  });
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it('while the booking loads the page shows its skeleton (status card, detail blocks, payment panel), then the booking', async () => {
    let answer!: (booking: BookingResponse) => void;
    api.getBooking.mockReturnValue(new Promise((resolve) => { answer = resolve; }));
    api.fetchRecommendations.mockReturnValue(new Promise(() => {}));
    render(<ConfirmationView referenceCode="VOTA-20260916-8K3F" />);
    const page = screen.getByRole('status', { name: 'Đang tải đơn đặt chỗ' });
    expect(page.getAttribute('aria-busy')).toBe('true');
    expect(page.querySelectorAll('.rounded-2xl.border').length).toBe(4);
    expect(screen.queryByText('Đặt chỗ thành công!')).toBeNull();

    answer(confirmed());
    expect(await screen.findByText('Đặt chỗ thành công!')).toBeTruthy();
    expect(screen.queryByRole('status', { name: 'Đang tải đơn đặt chỗ' })).toBeNull();
  });

  it('the booking shows at once while the next-trip block holds its place with a 3-card skeleton until recs arrive', async () => {
    let answer!: (value: unknown) => void;
    api.getBooking.mockResolvedValue(confirmed());
    api.fetchRecommendations.mockReturnValue(new Promise((resolve) => { answer = resolve; }));
    render(<ConfirmationView referenceCode="VOTA-20260916-8K3F" />);
    expect(await screen.findByText('Đặt chỗ thành công!')).toBeTruthy();
    expect(recsSkeleton()!.querySelectorAll('[aria-hidden="true"].rounded-xl')).toHaveLength(3);

    answer(recsFor(3));
    expect(await screen.findByText('TIẾP THEO CHO CHUYẾN NHA TRANG')).toBeTruthy();
    expect(recsSkeleton()).toBeNull();
  });

  it('a failed or empty recommendation call removes the skeleton without leaving an empty block', async () => {
    api.getBooking.mockResolvedValue(confirmed());
    api.fetchRecommendations.mockRejectedValue(new Error('503'));
    const { unmount } = render(<ConfirmationView referenceCode="VOTA-20260916-8K3F" />);
    await screen.findByText('Đặt chỗ thành công!');
    await waitFor(() => expect(recsSkeleton()).toBeNull());
    expect(screen.queryByText(/TIẾP THEO CHO CHUYẾN/)).toBeNull();
    unmount();

    api.fetchRecommendations.mockResolvedValue(recsFor(0));
    render(<ConfirmationView referenceCode="VOTA-20260916-8K3F" />);
    await screen.findByText('Đặt chỗ thành công!');
    await waitFor(() => expect(recsSkeleton()).toBeNull());
    expect(screen.queryByText(/TIẾP THEO CHO CHUYẾN/)).toBeNull();
  });

  it('an unpaid booking never shows the recommendation skeleton', async () => {
    api.getBooking.mockResolvedValue(pending());
    render(<ConfirmationView referenceCode="VOTA-20260916-8K3F" />);
    expect(await screen.findByText('Đơn đang được giữ chỗ')).toBeTruthy();
    expect(recsSkeleton()).toBeNull();
  });
});

describe('ConfirmationView — hành khách và dòng giá của từng dịch vụ', () => {
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

  const item = (name: string) => screen.getAllByTestId('booking-item').find((el) => el.textContent?.includes(name))!;

  it('khách sạn hiện khách theo phòng và đánh dấu người đại diện; vé hiện đủ tên kèm nhãn trẻ em; không có ngày sinh', async () => {
    api.getBooking.mockResolvedValue({ ...clone(familyFixture), status: 'CONFIRMED' });
    render(<ConfirmationView referenceCode="VOTA-20260929-7Q2M" />);
    await screen.findByText('Đặt chỗ thành công!');
    const hotel = item('Lucky Sun');
    expect(hotel.textContent).toContain('1 phòng · 3 khách');
    const rooms = hotel.querySelector('[data-testid="item-travelers"]')!;
    expect(rooms.textContent).toContain('Phòng 1:');
    expect(rooms.textContent).toContain('Nguyễn Minh Anh');
    expect(rooms.textContent).toContain('Đại diện nhận phòng');
    expect(rooms.textContent).toContain('Nguyễn Gia Bảo (trẻ em)');
    const ticket = item('VinWonders');
    expect(ticket.textContent).toContain('3 khách');
    expect(ticket.querySelector('[data-testid="item-travelers"]')!.textContent).toBe('Nguyễn Minh Anh, Trần Thu Hà, Nguyễn Gia Bảo (trẻ em)');
    expect(ticket.textContent).not.toContain('Đại diện nhận phòng');
    expect(document.body.textContent).not.toMatch(/birth|ngày sinh/i); // response không trả ngày sinh nên trang không có chỗ để hiện
  });

  it('hiện các dòng giá theo loại khách của Backend', async () => {
    api.getBooking.mockResolvedValue({ ...clone(familyFixture), status: 'CONFIRMED' });
    render(<ConfirmationView referenceCode="VOTA-20260929-7Q2M" />);
    await screen.findByText('Đặt chỗ thành công!');
    const lines = item('VinWonders').querySelector('[data-testid="fare-lines"]')!;
    expect(lines.textContent).toContain('2 × 1.500.000');
    expect(lines.textContent).toContain('1 × 504.000');
    expect(item('Lucky Sun').querySelector('[data-testid="fare-lines"]')!.textContent).toContain('× 2 đêm × 1 phòng');
  });

  it('đơn tạo trước thay đổi (không có travelers) vẫn hiện tên khách như trước', async () => {
    api.getBooking.mockResolvedValue(confirmed());
    render(<ConfirmationView referenceCode="VOTA-20260916-8K3F" />);
    await screen.findByText('Đặt chỗ thành công!');
    const hotel = item('Vinpearl Resort');
    expect(hotel.querySelector('[data-testid="item-travelers"]')!.textContent).toBe('Nguyễn Minh Anh');
    expect(hotel.textContent).toContain('1 phòng');
    expect(hotel.textContent).not.toContain('Đại diện nhận phòng');
  });
});

describe('ConfirmationView — chi tiết đơn đầy đủ (FR-BKG-15)', () => {
  const detail = (patch: Partial<BookingResponse> = {}): BookingResponse => ({ ...clone(familyFixture), status: 'CONFIRMED', ...patch });
  const product = (productId: string, over: Record<string, unknown> = {}) => ({
    productId, name: productId, taxonomy: 'hotel', destination: 'Nha Trang', unitPrice: 1, currency: 'VND', available: true,
    priceUnit: 'PER_NIGHT', attributes: {}, imageUrl: null, ...over,
  });

  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(NOW);
    travel.getBookingByCode.mockReturnValue(undefined);
    resetProductInfoCache();
    catalog.getProduct.mockRejectedValue(new Error('offline'));
    api.fetchRecommendations.mockResolvedValue({
      strategy: 'cross_vertical', destination: 'Nha Trang', recommendations: [],
      diagnostics: { eventsUsed: 1, coldStart: false, excludedVerticals: [], modelVersion: 't' }, generatedAt: '',
    });
  });
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it('có đường dẫn về Đơn hàng của tôi và các khối khách hàng, hành khách, dịch vụ, chính sách', async () => {
    api.getBooking.mockResolvedValue(detail());
    render(<ConfirmationView referenceCode="VOTA-20260929-7Q2M" />);
    await screen.findByText('Đặt chỗ thành công!');
    expect(screen.getByRole('link', { name: 'Đơn hàng của tôi' }).getAttribute('href')).toBe('/profile/booking_history');
    for (const title of ['Thông tin khách hàng', 'Thông tin hành khách', 'Thông tin dịch vụ', 'Chính sách hoàn huỷ', 'Thông tin thanh toán']) {
      expect(screen.getByRole('heading', { name: title })).toBeTruthy();
    }
    const customer = screen.getByRole('heading', { name: 'Thông tin khách hàng' }).parentElement!;
    expect(within(customer).getByText('Nguyễn Minh Anh')).toBeTruthy();
    expect(screen.getByText('0912345678')).toBeTruthy();
    expect(screen.getByText('minhanh@example.vn')).toBeTruthy();
  });

  it('khách sạn hiện giờ nhận và trả phòng mặc định chung', async () => {
    api.getBooking.mockResolvedValue(detail());
    render(<ConfirmationView referenceCode="VOTA-20260929-7Q2M" />);
    await screen.findByText('Đặt chỗ thành công!');
    const hotel = screen.getAllByTestId('booking-item').find((el) => el.textContent?.includes('Lucky Sun'))!;
    const timeline = hotel.querySelector('[data-testid="item-timeline"]')!;
    expect(timeline.textContent).toContain('Nhận phòng');
    expect(timeline.textContent).toContain('Sau 14:00');
    expect(timeline.textContent).toContain('Trả phòng');
    expect(timeline.textContent).toContain('Trước 12:00');
    expect(timeline.textContent).toContain('2 đêm · 3 khách');
  });

  it('địa chỉ, hạng sao, bản đồ và tiện ích lấy từ khách sạn cha trong catalog; lỗi catalog không làm hỏng trang', async () => {
    api.getBooking.mockResolvedValue(detail());
    catalog.getProduct.mockImplementation(async (id: string) => {
      if (id === 'nt-h-luckysun-d3') return product(id, { name: 'Phòng Deluxe 3 Người', attributes: { level: 'room', parentProductId: 'nt-h-luckysun', wifi: true, freeBreakfast: true } });
      if (id === 'nt-h-luckysun') return product(id, { name: 'Lucky Sun Hotel Nha Trang Beach', attributes: { level: 'property', starRating: 4, address: '12 Trần Phú, Nha Trang' } });
      throw new Error('offline');
    });
    render(<ConfirmationView referenceCode="VOTA-20260929-7Q2M" />);
    await screen.findByText('Đặt chỗ thành công!');
    expect((await screen.findAllByText('Lucky Sun Hotel Nha Trang Beach')).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/12 Trần Phú, Nha Trang/).length).toBeGreaterThan(0);
    expect(screen.getByRole('img', { name: '4 sao' })).toBeTruthy();
    const map = screen.getAllByRole('link', { name: /Bản đồ/ })[0];
    expect(map.getAttribute('href')).toContain('google.com/maps');
    expect(map.getAttribute('href')).toContain(encodeURIComponent('12 Trần Phú'));
    expect(screen.getByText('Wi-Fi miễn phí')).toBeTruthy();
    expect(screen.getByText('Bữa sáng')).toBeTruthy();
  });

  it('không lấy được catalog thì vẫn hiện đơn từ dữ liệu của đơn, không có địa chỉ giả', async () => {
    api.getBooking.mockResolvedValue(detail());
    render(<ConfirmationView referenceCode="VOTA-20260929-7Q2M" />);
    await screen.findByText('Đặt chỗ thành công!');
    await waitFor(() => expect(catalog.getProduct).toHaveBeenCalled());
    expect(screen.queryByRole('link', { name: /Bản đồ/ })).toBeNull();
    expect(screen.queryByRole('img', { name: /sao/ })).toBeNull();
    expect(screen.getAllByTestId('booking-item')).toHaveLength(3);
  });

  it('chính sách hoàn huỷ nêu hạn hoàn 100% của Backend và đánh dấu mốc đang áp dụng', async () => {
    api.getBooking.mockResolvedValue(detail({ cancellableUntil: '2026-10-16T17:00:00Z' }));
    render(<ConfirmationView referenceCode="VOTA-20260929-7Q2M" />);
    await screen.findByText('Đặt chỗ thành công!');
    const policy = screen.getByRole('heading', { name: 'Chính sách hoàn huỷ' }).parentElement!;
    expect(policy.textContent).toContain('Miễn phí huỷ, hoàn 100%');
    expect(policy.textContent).toMatch(/Trước .*17\/10\/2026/);
    expect(policy.textContent).toContain('Không huỷ trực tuyến được');
    expect(policy.textContent).toContain('Huỷ áp dụng cho cả đơn');
    expect(policy.querySelectorAll('li')[0].className).not.toContain('opacity-50'); // còn trong hạn: mốc đầu đang áp dụng
    expect(policy.querySelectorAll('li')[1].className).toContain('opacity-50');
  });

  it('khung thanh toán có mã đơn, từng dòng giá, tổng khớp Backend và nút huỷ khi còn hạn', async () => {
    api.getBooking.mockResolvedValue(detail({ cancellableUntil: '2026-10-16T17:00:00Z' }));
    render(<ConfirmationView referenceCode="VOTA-20260929-7Q2M" />);
    await screen.findByText('Đặt chỗ thành công!');
    const panel = screen.getByRole('heading', { name: 'Thông tin thanh toán' }).parentElement!;
    expect(within(panel).getByTestId('panel-reference').textContent).toBe('VOTA-20260929-7Q2M');
    expect(within(panel).getByTestId('panel-total').textContent?.replace(/\u00a0/g, ' ')).toBe('6.960.384 ₫');
    expect(within(panel).getByText('3.504.000 ₫', { normalizer: (t) => t.replace(/\u00a0/g, ' ') })).toBeTruthy();
    expect(within(panel).getByRole('button', { name: 'Huỷ đơn' })).toBeTruthy();
    expect(within(panel).getByRole('button', { name: /Sao chép/ })).toBeTruthy();
  });

  it('đơn quá hạn huỷ thì khung thanh toán không có nút huỷ', async () => {
    api.getBooking.mockResolvedValue(detail({ cancellableUntil: '2026-09-01T00:00:00Z' }));
    render(<ConfirmationView referenceCode="VOTA-20260929-7Q2M" />);
    await screen.findByText('Đặt chỗ thành công!');
    expect(screen.queryByRole('button', { name: 'Huỷ đơn' })).toBeNull();
  });
});
