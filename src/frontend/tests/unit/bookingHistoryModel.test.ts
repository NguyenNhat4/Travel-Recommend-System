import { describe, expect, it } from 'vitest';
import defaultList from '../../../shared/mocks/booking/listBookings.200-default.json';
import cancelledList from '../../../shared/mocks/booking/listBookings.200-cancelled.json';
import type { BookingSummary } from '../../src/services/booking';
import {
  canRebook, cardNote, cardStatus, emptyCopy, filtersToSearch, formatDay, isFiltered, itemSubtitle, parseFilters,
  visiblePages, DEFAULT_FILTERS,
} from '../../src/features/bookings/historyModel';

const summary = (patch: Partial<BookingSummary> = {}): BookingSummary =>
  ({ ...(defaultList.data[1] as BookingSummary), ...patch });

describe('bộ lọc của trang Đơn hàng của tôi nằm trên URL', () => {
  it('đọc đủ bốn tham số và đổi ngược lại thành query', () => {
    const filters = parseFilters(new URLSearchParams('tab=done&taxonomy=flight&days=30&page=3'));
    expect(filters).toEqual({ tab: 'done', taxonomy: 'flight', days: 30, page: 3 });
    expect(filtersToSearch(filters)).toBe('?tab=done&taxonomy=flight&days=30&page=3');
  });

  it('đường dẫn mặc định gọn: bỏ mọi giá trị mặc định', () => {
    expect(filtersToSearch(DEFAULT_FILTERS)).toBe('');
    expect(filtersToSearch({ ...DEFAULT_FILTERS, tab: 'cancelled' })).toBe('?tab=cancelled');
  });

  it.each([
    ['tab=all', 'tab'], ['taxonomy=train', 'taxonomy'], ['days=14', 'days'], ['page=0', 'page'], ['page=abc', 'page'], ['page=1.5', 'page'],
  ])('giá trị lạ %s về mặc định, không làm trang lỗi', (query, key) => {
    const parsed = parseFilters(new URLSearchParams(query)) as unknown as Record<string, unknown>;
    expect(parsed[key]).toBe((DEFAULT_FILTERS as unknown as Record<string, unknown>)[key]);
  });

  it('chỉ lọc dịch vụ hoặc ngày mới tính là đang lọc; đổi tab hay trang thì không', () => {
    expect(isFiltered({ ...DEFAULT_FILTERS, tab: 'done', page: 2 })).toBe(false);
    expect(isFiltered({ ...DEFAULT_FILTERS, taxonomy: 'hotel' })).toBe(true);
    expect(isFiltered({ ...DEFAULT_FILTERS, days: 7 })).toBe(true);
  });
});

describe('phân trang đánh số', () => {
  it.each([
    [1, 1, [1]],
    [1, 3, [1, 2, 3]],
    [1, 10, [1, 2, 'gap', 10]],
    [5, 10, [1, 'gap', 4, 5, 6, 'gap', 10]],
    [10, 10, [1, 'gap', 9, 10]],
    [3, 5, [1, 2, 3, 4, 5]],
  ])('trang %i trong %i trang', (current, total, expected) => {
    expect(visiblePages(current as number, total as number)).toEqual(expected);
  });
});

describe('nhãn và ghi chú của thẻ đơn', () => {
  it('đơn đang giữ chỗ nói rõ hạn giữ', () => {
    const pending = defaultList.data[0] as BookingSummary;
    expect(cardStatus(pending)).toEqual({ label: 'Chờ thanh toán', tone: 'warn' });
    expect(cardNote(pending)?.text).toMatch(/^Giữ đến /);
    expect(canRebook(pending)).toBe(false);
  });

  it('đơn đã xác nhận chuyển nhãn sang Hoàn thành khi ở tab Hoàn thành, và không có ghi chú', () => {
    expect(cardStatus(summary({ tab: 'upcoming' })).label).toBe('Đã xác nhận');
    expect(cardStatus(summary({ tab: 'done' }))).toEqual({ label: 'Hoàn thành', tone: 'ok' });
    expect(cardNote(summary())).toBeNull();
  });

  it('đơn giữ chỗ quá hạn (Backend xếp vào Đã huỷ) hiện là hết hạn giữ chỗ và đặt lại được', () => {
    const lapsed = summary({ status: 'PENDING_PAYMENT', tab: 'cancelled', cancellableUntil: null });
    expect(cardStatus(lapsed)).toEqual({ label: 'Hết hạn giữ chỗ', tone: 'off' });
    expect(cardNote(lapsed)?.title).toBe('Hết thời gian giữ chỗ');
    expect(canRebook(lapsed)).toBe(true);
  });

  it('thanh toán thất bại nêu lý do từ Backend và đặt lại được', () => {
    const failed = cancelledList.data[1] as BookingSummary;
    expect(failed.status).toBe('PAYMENT_FAILED');
    expect(cardStatus(failed)).toEqual({ label: 'Thanh toán thất bại', tone: 'bad' });
    expect(cardNote(failed)?.text).toContain('3 lần');
    expect(canRebook(failed)).toBe(true);
  });

  it.each([
    ['REFUNDED', /đã về thẻ/], ['REFUND_PENDING', /Đang hoàn/], ['REFUND_FAILED', /sẽ liên hệ/], ['EXPIRED', /không phát sinh hoàn tiền/],
  ] as const)('đơn đã huỷ với thanh toán %s', (paymentStatus, text) => {
    const cancelled = cardNote(summary({ status: 'CANCELLED', tab: 'cancelled', paymentStatus }));
    expect(`${cancelled?.title} ${cancelled?.text}`).toMatch(text);
    expect(canRebook(summary({ status: 'CANCELLED', tab: 'cancelled', paymentStatus }))).toBe(false);
  });

  it('dòng phụ của dịch vụ: khách sạn theo đêm, vé theo khách, combo theo gói', () => {
    const [hotel, ticket] = defaultList.data[1].items as BookingSummary['items'];
    expect(itemSubtitle(hotel)).toBe('Khách sạn · 12/10/2026 – 14/10/2026 · 2 đêm');
    expect(itemSubtitle(ticket)).toBe('Vé tham quan · 13/10/2026 · 2 khách');
    expect(itemSubtitle({ ...ticket, taxonomy: 'combo' })).toContain('2 gói');
    expect(formatDay('2026-09-05')).toBe('05/09/2026');
  });
});

describe('lời nhắn khi danh sách trống', () => {
  it('chưa có đơn: mời đặt, theo từng tab', () => {
    expect(emptyCopy(DEFAULT_FILTERS)).toMatchObject({ title: 'Bạn chưa có chuyến đi nào.', cta: { href: '/hotels' } });
    expect(emptyCopy({ ...DEFAULT_FILTERS, tab: 'done' }).title).toBe('Bạn chưa hoàn thành chuyến đi nào.');
    expect(emptyCopy({ ...DEFAULT_FILTERS, tab: 'cancelled' }).cta).toBeNull();
  });

  it('đang lọc: nói bộ lọc không khớp, không mời đặt', () => {
    const copy = emptyCopy({ ...DEFAULT_FILTERS, taxonomy: 'golf' });
    expect(copy.title).toBe('Không có đơn nào khớp bộ lọc.');
    expect(copy.cta).toBeNull();
  });
});
