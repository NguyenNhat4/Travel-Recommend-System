// @vitest-environment jsdom
import { cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { components } from '../../src/types/api.gen';

const travel = vi.hoisted(() => ({
  addToCart: vi.fn(),
  currentPersona: { id: 'VP0000001', name: 'Nguyễn Minh Anh', email: 'minhanh@example.vn' } as unknown,
  openLoginModal: vi.fn(),
  showToast: vi.fn(),
  navigate: vi.fn(),
}));
vi.mock('../../src/context/TravelContext', () => ({ useTravel: () => travel }));

import { useAssistantCart } from '../../src/hooks/useAssistantCart';

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

    it('vé tính theo người gửi guests = đoàn và số lượng = tổng khách; khách sạn gửi số phòng theo sức chứa; combo gửi 1 gói', async () => {
      travel.addToCart.mockResolvedValue(true);
      const { result } = renderHook(() => useAssistantCart());
      await result.current([
        withTaxonomy('ticket', 'attraction'),
        withTaxonomy('flight', 'flight'),
        withTaxonomy('hotel-2', 'hotel', { maxOccupancy: 2 }),      // 3 khách / 2 = 2 phòng (≤ 2 người lớn)
        withTaxonomy('hotel-4', 'hotel', { maxOccupancy: 4 }),      // 1 phòng đủ chứa 3 khách
        withTaxonomy('hotel-nc', 'hotel'),                          // không có sức chứa: 1 phòng
        withTaxonomy('combo', 'combo'),
      ]);
      expect(travel.addToCart.mock.calls.map((call) => [call[0].id, call[1], call[4]])).toEqual([
        ['ticket', 3, { silent: true, guests: party }],
        ['flight', 3, { silent: true, guests: party }],
        ['hotel-2', 2, { silent: true, guests: party }],
        ['hotel-4', 1, { silent: true, guests: party }],
        ['hotel-nc', 1, { silent: true, guests: party }],
        ['combo', 1, { silent: true, guests: party }],
      ]);
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

  it('asks a guest to log in once, then adds the whole group', async () => {
    travel.currentPersona = null;
    travel.addToCart.mockResolvedValue(true);
    const onAdded = vi.fn();
    const { result } = renderHook(() => useAssistantCart());

    await result.current(items, onAdded);
    expect(travel.addToCart).not.toHaveBeenCalled();
    expect(travel.openLoginModal).toHaveBeenCalledTimes(1);

    await travel.openLoginModal.mock.calls[0][0]();
    await vi.waitFor(() => expect(onAdded).toHaveBeenCalledWith(3));
  });
});
