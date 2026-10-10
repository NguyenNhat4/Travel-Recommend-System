// @vitest-environment jsdom
import { cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { components } from '../../src/types/api.gen';

const travel = vi.hoisted(() => ({
  addToCart: vi.fn(),
  startBooking: vi.fn(),
  currentPersona: { id: 'VP0000001', name: 'Nguyễn Minh Anh', email: 'minhanh@example.vn' } as unknown,
  openLoginModal: vi.fn(),
  showToast: vi.fn(),
  navigate: vi.fn(),
}));
vi.mock('../../src/context/TravelContext', () => ({ useTravel: () => travel }));

import { bookNowItemOf, useAssistantCart, useBookItinerary } from '../../src/hooks/useAssistantCart';

function summary(productId: string, name: string): components['schemas']['ProductSummary'] {
  return {
    productId, name, taxonomy: 'attraction', destination: 'Nha Trang', status: 'ACTIVE',
    unitPrice: 100000, currency: 'VND', priceUnit: 'PER_PERSON', available: true, imageUrl: null,
  };
}

const items = [
  { product: summary('p-1', 'VinWonders'), usingDate: '2026-10-01' },
  { product: summary('p-2', 'Tháp Bà'), usingDate: '2026-10-02' },
  { product: summary('p-3', 'Hòn Mun'), usingDate: '2026-10-03' },
];

describe('useAssistantCart', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    travel.currentPersona = { id: 'VP0000001', name: 'Nguyễn Minh Anh', email: 'minhanh@example.vn' };
  });
  afterEach(cleanup);

  it('adds items one at a time with their own dates, then calls onAdded after the last one', async () => {
    const order: string[] = [];
    let inFlight = 0;
    travel.addToCart.mockImplementation(async (product: { id: string }) => {
      inFlight += 1;
      expect(inFlight).toBe(1);
      await new Promise((resolve) => setTimeout(resolve, 0));
      order.push(product.id);
      inFlight -= 1;
      return true;
    });
    const onAdded = vi.fn(() => order.push('done'));
    const { result } = renderHook(() => useAssistantCart());

    await result.current(items, onAdded);

    expect(order).toEqual(['p-1', 'p-2', 'p-3', 'done']);
    expect(onAdded).toHaveBeenCalledWith(3);
    expect(travel.addToCart.mock.calls.map((call) => [call[2], call[4]])).toEqual([
      ['2026-10-01', { silent: true }], ['2026-10-02', { silent: true }], ['2026-10-03', { silent: true }],
    ]);
  });

  describe('với đoàn của lịch trình (intent.party)', () => {
    const party = { adults: 2, children: 1 };
    const withTaxonomy = (productId: string, taxonomy: string, attributes?: Record<string, unknown>) => ({
      product: { ...summary(productId, productId), taxonomy, ...(attributes ? { attributes } : {}) } as components['schemas']['ProductSummary'],
      usingDate: '2026-10-01', party,
    });

    it('chỉ tour, trải nghiệm và tiện ích khác vào giỏ: vé gửi guests = đoàn, combo gửi 1 gói; khách sạn và vé máy bay bị bỏ qua', async () => {
      travel.addToCart.mockResolvedValue(true);
      const onAdded = vi.fn();
      const { result } = renderHook(() => useAssistantCart());
      await result.current([
        withTaxonomy('ticket', 'attraction'),
        withTaxonomy('flight', 'flight'),
        withTaxonomy('hotel-2', 'hotel', { maxOccupancy: 2 }),
        withTaxonomy('golf', 'golf'),
        withTaxonomy('combo', 'combo'),
      ], onAdded);
      expect(travel.addToCart.mock.calls.map((call) => [call[0].id, call[1], call[4]])).toEqual([
        ['ticket', 3, { silent: true, guests: party }],
        ['golf', 3, { silent: true, guests: party }],
        ['combo', 1, { silent: true, guests: party }],
      ]);
      expect(onAdded).toHaveBeenCalledWith(3);
      expect(travel.showToast.mock.calls[0][0]).toBe('Đã thêm 3 mục của lịch trình vào giỏ. Giá chính thức hiển thị ở giỏ hàng.');
    });

    it('chỉ có khách sạn hoặc vé máy bay thì không gọi thêm giỏ lần nào', async () => {
      const onAdded = vi.fn();
      const { result } = renderHook(() => useAssistantCart());
      await result.current([withTaxonomy('hotel-2', 'hotel'), withTaxonomy('flight', 'flight')], onAdded);
      expect(travel.addToCart).not.toHaveBeenCalled();
      expect(onAdded).not.toHaveBeenCalled();
    });

    it('Đặt ngay: số lượng theo loại (vé = tổng khách, khách sạn = số phòng theo sức chứa, combo = 1 gói) kèm ngày của lịch trình', () => {
      const stay = { ...withTaxonomy('hotel-2', 'hotel', { maxOccupancy: 2 }), checkOutDate: '2026-10-03' };
      expect(bookNowItemOf(stay)).toMatchObject({                                 // 3 khách / 2 = 2 phòng
        product: { id: 'hotel-2' }, quantity: 2, usingDate: '2026-10-01', checkOutDate: '2026-10-03', guests: party,
      });
      expect(bookNowItemOf(withTaxonomy('hotel-4', 'hotel', { maxOccupancy: 4 })).quantity).toBe(1);
      expect(bookNowItemOf(withTaxonomy('hotel-nc', 'hotel')).quantity).toBe(1);   // không có sức chứa: 1 phòng
      expect(bookNowItemOf(withTaxonomy('flight', 'flight'))).toMatchObject({ quantity: 3, guests: party });
      expect(bookNowItemOf(withTaxonomy('combo', 'combo')).quantity).toBe(1);
      expect(bookNowItemOf({ product: summary('p-1', 'VinWonders'), usingDate: '2026-10-01' })).toMatchObject({ quantity: 1, usingDate: '2026-10-01' });
    });

    it('một mục: gửi kèm guests và không thêm silent (addToCart tự báo toast)', async () => {
      travel.addToCart.mockResolvedValue(true);
      const { result } = renderHook(() => useAssistantCart());
      await result.current([withTaxonomy('ticket', 'attraction')]);
      expect(travel.addToCart).toHaveBeenCalledTimes(1);
      const [, quantity, usingDate, checkOut, options] = travel.addToCart.mock.calls[0];
      expect([quantity, usingDate, checkOut, options]).toEqual([3, '2026-10-01', undefined, { guests: party }]);
    });

    it('kéo đoàn về giới hạn của giỏ: ít nhất 1 người lớn, tối đa 9 khách', async () => {
      travel.addToCart.mockResolvedValue(true);
      const { result } = renderHook(() => useAssistantCart());
      await result.current([{ ...withTaxonomy('ticket', 'attraction'), party: { adults: 12, children: 3 } }]);
      await result.current([{ ...withTaxonomy('ticket', 'attraction'), party: { adults: 0, children: 2 } }]);
      expect(travel.addToCart.mock.calls.map((call) => [call[1], call[4]])).toEqual([
        [9, { guests: { adults: 9, children: 0 } }],
        [3, { guests: { adults: 1, children: 2 } }],
      ]);
    });
  });

  it('keeps going after a rejected item and names it in one toast', async () => {
    travel.addToCart.mockImplementation(async (product: { id: string }) => product.id !== 'p-2');
    const onAdded = vi.fn();
    const { result } = renderHook(() => useAssistantCart());

    await result.current(items, onAdded);

    expect(travel.addToCart).toHaveBeenCalledTimes(3);
    expect(onAdded).toHaveBeenCalledWith(2);
    expect(travel.showToast).toHaveBeenCalledTimes(1);
    expect(travel.showToast.mock.calls[0][0]).toBe('Đã thêm 2/3 mục vào giỏ. Chưa thêm được: Tháp Bà.');
  });

  it('does not call onAdded when nothing reached the cart', async () => {
    travel.addToCart.mockResolvedValue(false);
    const onAdded = vi.fn();
    const { result } = renderHook(() => useAssistantCart());

    await result.current(items, onAdded);

    expect(onAdded).not.toHaveBeenCalled();
  });

  it('a guest adds to the cart without being asked to log in', async () => {
    travel.currentPersona = null;
    travel.addToCart.mockResolvedValue(true);
    const onAdded = vi.fn();
    const { result } = renderHook(() => useAssistantCart());

    await result.current(items, onAdded);

    expect(travel.openLoginModal).not.toHaveBeenCalled();
    expect(travel.addToCart).toHaveBeenCalledTimes(3);
    expect(onAdded).toHaveBeenCalledWith(3);
  });
});

describe('useBookItinerary', () => {
  const party = { adults: 2, children: 1 };
  const item = (productId: string, taxonomy: string, extra: Record<string, unknown> = {}) => ({
    product: { ...summary(productId, productId), taxonomy } as components['schemas']['ProductSummary'], usingDate: '2026-10-01', party, ...extra,
  });
  beforeEach(() => {
    vi.clearAllMocks();
    travel.startBooking.mockResolvedValue(null);
  });
  afterEach(cleanup);

  it('Đặt ngay một mục: đơn nháp chỉ có mục đó, lỗi của mục là lỗi của cả lần đặt (không allowPartial)', async () => {
    const { result } = renderHook(() => useBookItinerary());
    await result.current(item('hotel', 'hotel', { checkOutDate: '2026-10-03' }));
    expect(travel.startBooking).toHaveBeenCalledTimes(1);
    const [lines, options] = travel.startBooking.mock.calls[0];
    expect(lines.map((line: any) => [line.product.id, line.quantity, line.usingDate, line.checkOutDate])).toEqual([
      ['hotel', 1, '2026-10-01', '2026-10-03'],
    ]);
    expect(options).toBeUndefined();
    expect(travel.addToCart).not.toHaveBeenCalled();
  });

  it('mỗi mục của lịch trình một đơn nháp riêng: không có thanh toán gộp', async () => {
    const { result } = renderHook(() => useBookItinerary());
    await result.current(item('ticket', 'attraction'));
    await result.current(item('flight', 'flight'));
    expect(travel.startBooking).toHaveBeenCalledTimes(2);
    expect(travel.startBooking.mock.calls.map(([lines]: any) => lines.length)).toEqual([1, 1]);
  });

  it('ignores duplicate submissions until the same cart operation settles', async () => {
    let finish!: (ok: boolean) => void;
    travel.addToCart.mockReturnValue(new Promise<boolean>((resolve) => { finish = resolve; }));
    const feedback = { onStart: vi.fn(), onSettled: vi.fn() };
    const { result } = renderHook(() => useAssistantCart());
    const first = result.current([items[0]], undefined, feedback);
    await result.current([items[0]], undefined, feedback);
    expect(travel.addToCart).toHaveBeenCalledTimes(1);
    expect(feedback.onStart).toHaveBeenCalledTimes(1);
    expect(feedback.onSettled).not.toHaveBeenCalled();
    finish(true);
    await first;
    expect(feedback.onSettled).toHaveBeenCalledWith(1);
  });
});
