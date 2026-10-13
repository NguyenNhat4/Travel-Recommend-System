// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import defaultList from '../../../shared/mocks/booking/listBookings.200-default.json';
import cancelledList from '../../../shared/mocks/booking/listBookings.200-cancelled.json';
import emptyList from '../../../shared/mocks/booking/listBookings.200-empty.json';
import draftFixture from '../../../shared/mocks/booking/createBookingDraft.201-hotel.json';

// Router phải là một đối tượng ổn định như `useRouter` của Next, nếu không effect tải dữ liệu chạy lại mỗi lần render.
const nav = vi.hoisted(() => {
  const replace = vi.fn();
  return { search: '', replace, router: { replace } };
});
const api = vi.hoisted(() => ({ listBookings: vi.fn(), createBookingDraft: vi.fn() }));
const travel = vi.hoisted(() => ({
  currentPersona: { id: 'VP0000001', name: 'Minh Anh' },
  openLoginModal: vi.fn(), navigate: vi.fn(), showToast: vi.fn(), refreshCart: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(nav.search),
  useRouter: () => nav.router,
}));
vi.mock('../../src/context/TravelContext', () => ({ useTravel: () => travel }));
vi.mock('../../src/services/booking', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/services/booking')>()),
  listBookings: api.listBookings,
  createBookingDraft: api.createBookingDraft,
}));

import { BookingHistoryView } from '../../src/features/bookings/BookingHistoryView';
import { ApiError } from '../../src/services/http';

const clone = <T,>(value: T) => JSON.parse(JSON.stringify(value)) as T;
const pagesOf = (total: number, page = 1) => ({ page, pageSize: 5, totalItems: total, totalPages: Math.ceil(total / 5) });

describe('BookingHistoryView — Đơn hàng của tôi', () => {
  beforeEach(() => {
    nav.search = '';
    api.listBookings.mockResolvedValue(clone(defaultList));
  });
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('mở vào tab Sắp đến, hỏi Backend đúng tham số và hiện thẻ đơn', async () => {
    render(<BookingHistoryView />);
    const skeleton = screen.getByRole('status', { name: 'Đang tải đơn hàng' });
    expect(skeleton.getAttribute('aria-busy')).toBe('true');
    expect(skeleton.querySelectorAll(':scope > [aria-hidden="true"]')).toHaveLength(3);
    expect(await screen.findAllByTestId('booking-card')).toHaveLength(2);
    expect(screen.queryByRole('status', { name: 'Đang tải đơn hàng' })).toBeNull();
    expect(api.listBookings).toHaveBeenCalledWith(
      { tab: 'upcoming', taxonomy: undefined, days: undefined, page: 1, pageSize: 5 }, expect.any(AbortSignal));
    expect(screen.getByRole('tab', { name: 'Sắp đến' }).getAttribute('aria-selected')).toBe('true');
    const [pending] = screen.getAllByTestId('booking-card');
    expect(within(pending).getByText('Chờ thanh toán')).toBeTruthy();
    expect(within(pending).getByRole('link', { name: 'Tiếp tục thanh toán' }).getAttribute('href')).toBe('/booking/VOTA-20261006-4K7Q');
  });

  it('chỉ có ba tab và năm loại dịch vụ, không có tab Tất cả', async () => {
    render(<BookingHistoryView />);
    await screen.findAllByTestId('booking-card');
    expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual(['Sắp đến', 'Hoàn thành', 'Đã huỷ']);
    const chips = within(screen.getByRole('group', { name: 'Loại dịch vụ' })).getAllByRole('button').map((b) => b.textContent);
    expect(chips).toEqual(['Tất cả', 'Khách sạn', 'Vé máy bay', 'Vé tham quan', 'Combo', 'Sân Golf']);
  });

  it('đọc bộ lọc từ URL và gửi cho Backend', async () => {
    nav.search = 'tab=cancelled&taxonomy=flight&days=7&page=2';
    api.listBookings.mockResolvedValue({ ...clone(cancelledList), pagination: pagesOf(7, 2) });
    render(<BookingHistoryView />);
    await screen.findAllByTestId('booking-card');
    expect(api.listBookings).toHaveBeenCalledWith(
      { tab: 'cancelled', taxonomy: 'flight', days: 7, page: 2, pageSize: 5 }, expect.any(AbortSignal));
    expect(screen.getByRole('button', { name: 'Ngày đặt 7 ngày qua' })).toBeTruthy();
    expect(screen.getByRole('button', { name: /Vé máy bay/ }).getAttribute('aria-pressed')).toBe('true');
  });

  it('đổi tab, dịch vụ, ngày: cập nhật URL và về trang 1', async () => {
    nav.search = 'page=3';
    api.listBookings.mockResolvedValue({ ...clone(defaultList), pagination: pagesOf(14, 3) });
    render(<BookingHistoryView />);
    await screen.findAllByTestId('booking-card');

    fireEvent.click(screen.getByRole('tab', { name: 'Hoàn thành' }));
    expect(nav.replace).toHaveBeenLastCalledWith('/profile/booking_history?tab=done', { scroll: false });
    fireEvent.click(screen.getByRole('button', { name: /Khách sạn/ }));
    expect(nav.replace).toHaveBeenLastCalledWith('/profile/booking_history?taxonomy=hotel', { scroll: false });
    fireEvent.click(screen.getByRole('button', { name: /^Ngày đặt/ }));
    fireEvent.click(screen.getByRole('option', { name: '30 ngày qua' }));
    expect(nav.replace).toHaveBeenLastCalledWith('/profile/booking_history?days=30', { scroll: false });
  });

  it('phân trang: hiện số trang, chuyển trang giữ nguyên bộ lọc', async () => {
    nav.search = 'tab=done&days=60';
    api.listBookings.mockResolvedValue({ ...clone(defaultList), pagination: pagesOf(12, 1) });
    render(<BookingHistoryView />);
    await screen.findAllByTestId('booking-card');
    expect(screen.getByText('Hiển thị 1–5 trong 12 đơn')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Trang trước' })).toHaveProperty('disabled', true);
    fireEvent.click(screen.getByRole('button', { name: 'Trang 3' }));
    expect(nav.replace).toHaveBeenLastCalledWith('/profile/booking_history?tab=done&days=60&page=3', { scroll: false });
    fireEvent.click(screen.getByRole('button', { name: 'Trang sau' }));
    expect(nav.replace).toHaveBeenLastCalledWith('/profile/booking_history?tab=done&days=60&page=2', { scroll: false });
  });

  it('chỉ một trang thì không hiện thanh phân trang', async () => {
    render(<BookingHistoryView />);
    await screen.findAllByTestId('booking-card');
    expect(screen.queryByRole('navigation', { name: 'Phân trang' })).toBeNull();
  });

  it('trang vượt quá số trang hiện có thì lùi về trang cuối', async () => {
    nav.search = 'page=9';
    api.listBookings.mockResolvedValue({ data: [], pagination: pagesOf(12, 9) });
    render(<BookingHistoryView />);
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith('/profile/booking_history?page=3', { scroll: false }));
  });

  it('chưa có đơn nào: lời nhắn thân thiện và nút tìm khách sạn', async () => {
    api.listBookings.mockResolvedValue(clone(emptyList));
    render(<BookingHistoryView />);
    expect(await screen.findByText('Bạn chưa có chuyến đi nào.')).toBeTruthy();
    expect(screen.getByRole('link', { name: /Tìm khách sạn/ }).getAttribute('href')).toBe('/hotels');
  });

  it('bộ lọc không khớp: có nút Xoá bộ lọc, bấm thì bỏ dịch vụ và ngày nhưng giữ tab', async () => {
    nav.search = 'tab=done&taxonomy=golf&days=7';
    api.listBookings.mockResolvedValue(clone(emptyList));
    render(<BookingHistoryView />);
    expect(await screen.findByText('Không có đơn nào khớp bộ lọc.')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Xoá bộ lọc' }));
    expect(nav.replace).toHaveBeenLastCalledWith('/profile/booking_history?tab=done', { scroll: false });
  });

  it('lỗi mạng: báo lỗi, hiện mã yêu cầu, thử lại gọi lại API', async () => {
    api.listBookings.mockRejectedValueOnce(new ApiError('Mạng lỗi', 'NETWORK_ERROR', 0, true, 'req-77', null));
    render(<BookingHistoryView />);
    expect(await screen.findByRole('alert')).toBeTruthy();
    expect(screen.getByText('Mã yêu cầu: req-77')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /Thử lại/ }));
    expect(await screen.findAllByTestId('booking-card')).toHaveLength(2);
    expect(api.listBookings).toHaveBeenCalledTimes(2);
  });

  it('chưa đăng nhập (401): mời đăng nhập, đăng nhập xong thì tải lại', async () => {
    api.listBookings.mockRejectedValueOnce(new ApiError('Cần đăng nhập', 'UNAUTHENTICATED', 401, false, null, null));
    render(<BookingHistoryView />);
    fireEvent.click(await screen.findByRole('button', { name: /Đăng nhập/ }));
    expect(travel.openLoginModal).toHaveBeenCalledTimes(1);
    const afterLogin = travel.openLoginModal.mock.calls[0][0] as () => void;
    afterLogin();
    expect(await screen.findAllByTestId('booking-card')).toHaveLength(2);
  });

  it('Đặt lại: tạo đơn nháp từ đơn cũ rồi mở trang thanh toán; mục bỏ ra được báo', async () => {
    nav.search = 'tab=cancelled';
    api.listBookings.mockResolvedValue(clone(cancelledList));
    api.createBookingDraft.mockResolvedValue({ ...clone(draftFixture), rejectedItems: [{}] });
    render(<BookingHistoryView />);
    const cards = await screen.findAllByTestId('booking-card');
    expect(within(cards[0]).queryByRole('button', { name: 'Đặt lại' })).toBeNull(); // đơn tự huỷ không đặt lại
    fireEvent.click(within(cards[1]).getByRole('button', { name: 'Đặt lại' }));
    await waitFor(() => expect(travel.navigate).toHaveBeenCalledWith(`/checkout?draft=${encodeURIComponent((draftFixture as { draftId: string }).draftId)}`));
    expect(api.createBookingDraft).toHaveBeenCalledWith({ fromBooking: 'VOTA-20260827-1D6A', allowPartial: true });
    expect(travel.showToast).toHaveBeenCalledWith(expect.stringContaining('1 dịch vụ không còn đặt được'));
  });
});
