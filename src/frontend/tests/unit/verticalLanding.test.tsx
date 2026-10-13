// @vitest-environment jsdom
import React from 'react';
import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import popularFixture from '../../../shared/mocks/catalog/listProducts.200-popular.json';

const api = vi.hoisted(() => ({ listProducts: vi.fn(), listDestinations: vi.fn() }));
vi.mock('../../src/context/AssistantProvider', () => ({ useAssistant: () => ({ openFloatingWidget: vi.fn() }) }));
vi.mock('../../src/services/catalog', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/services/catalog')>()),
  listProducts: api.listProducts,
}));
vi.mock('../../src/services/destinations', () => ({ listDestinations: api.listDestinations }));
vi.mock('../../src/context/TravelContext', () => ({ useTravel: () => ({ navigate: vi.fn(), showToast: vi.fn() }) }));

import { VerticalLanding } from '../../src/features/catalog/landing/VerticalLanding';
import { clearSectionCache } from '../../src/hooks/useLazySection';

type Observer = { callback: (entries: Array<{ isIntersecting: boolean }>) => void; target?: Element };

/** IntersectionObserver giả: không khối nào "vào vùng nhìn" cho tới khi test gọi reveal(). */
function stubObserver() {
  const observers: Observer[] = [];
  class Fake {
    entry: Observer;
    constructor(callback: Observer['callback']) { this.entry = { callback }; observers.push(this.entry); }
    observe(target: Element) { this.entry.target = target; }
    disconnect() {}
  }
  vi.stubGlobal('IntersectionObserver', Fake);
  return {
    revealAll: () => act(() => {
      observers.filter((o) => o.target).forEach((o) => o.callback([{ isIntersecting: true }]));
    }),
  };
}

const paramsOf = (call: unknown[]) => call[0] as Record<string, unknown>;

describe('VerticalLanding', () => {
  beforeEach(() => {
    clearSectionCache();
    api.listProducts.mockReset();
    api.listDestinations.mockReset();
    api.listProducts.mockResolvedValue(popularFixture);
    api.listDestinations.mockResolvedValue([{ destination: 'Nha Trang', productCount: 12 }]);
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('loads only the first shelf up front; the cheap shelf and destinations wait until they scroll into view', async () => {
    const io = stubObserver();
    render(<VerticalLanding vertical="hotels" />);
    await waitFor(() => expect(api.listProducts).toHaveBeenCalledTimes(1));
    expect(paramsOf(api.listProducts.mock.calls[0])).toMatchObject({ taxonomy: 'hotel', sort: 'popular', availableOnly: true, limit: 8 });
    expect(api.listDestinations).not.toHaveBeenCalled();

    await io.revealAll();
    await waitFor(() => expect(api.listProducts).toHaveBeenCalledTimes(2));
    expect(paramsOf(api.listProducts.mock.calls[1])).toMatchObject({ taxonomy: 'hotel', sort: 'price_asc' });
    await waitFor(() => expect(api.listDestinations).toHaveBeenCalledTimes(1));
  });

  it('renders the hero, the products from the API and the assistant banner — nothing hard-coded', async () => {
    render(<VerticalLanding vertical="hotels" />);
    expect(screen.getByRole('heading', { level: 1, name: 'Khách sạn & resort' })).toBeTruthy();
    expect(screen.getByRole('form', { name: 'Tìm khách sạn' })).toBeTruthy();
    const first = popularFixture.results[0].name;
    expect((await screen.findAllByText(first)).length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: 'Lên lịch trình với trợ lý AI' })).toBeTruthy();
  });

  it('adds ?destination= to the requests and the titles and has no "Xem thêm" link', async () => {
    render(<VerticalLanding vertical="flights" destination="Nha Trang" />);
    // Tấm tìm kiếm vé máy bay cũng tải danh sách sân bay (không có destination), nên tìm kệ phổ biến theo `sort`.
    const popularShelf = () => api.listProducts.mock.calls.map(paramsOf).find((p) => p.sort === 'popular');
    await waitFor(() => expect(popularShelf()).toBeDefined());
    expect(popularShelf()).toMatchObject({ taxonomy: 'flight', destination: 'Nha Trang' });
    expect(await screen.findByRole('heading', { name: 'Chặng bay phổ biến đến Nha Trang' })).toBeTruthy();
    expect(screen.queryByRole('link', { name: /Xem thêm/ })).toBeNull();
  });

  it('shows the empty message with a way out when the destination has no products', async () => {
    api.listProducts.mockResolvedValue({ ...popularFixture, results: [], total: 0 });
    render(<VerticalLanding vertical="hotels" destination="Sa Pa" />);
    expect(await screen.findByText('Chưa có khách sạn tại Sa Pa.')).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Xem tất cả khách sạn' }).getAttribute('href')).not.toContain('destination=');
  });

  it('shows a retry inside the failed shelf only, and the retry refetches', async () => {
    api.listProducts.mockRejectedValueOnce(new Error('down')).mockResolvedValue(popularFixture);
    render(<VerticalLanding vertical="hotels" />);
    const retry = await screen.findByRole('button', { name: 'Thử lại' });
    expect(screen.getByRole('heading', { level: 1 })).toBeTruthy();
    retry.click();
    await waitFor(() => expect(api.listProducts.mock.calls.length).toBeGreaterThanOrEqual(2));
  });

  it('/experiences has two tabs; ?type=golf switches the taxonomy and the active tab', async () => {
    render(<VerticalLanding vertical="experiences" type="golf" />);
    await waitFor(() => expect(api.listProducts).toHaveBeenCalled());
    expect(paramsOf(api.listProducts.mock.calls[0])).toMatchObject({ taxonomy: 'golf' });
    const tabs = screen.getByRole('navigation', { name: 'Loại dịch vụ' });
    expect(within(tabs).getByRole('link', { name: 'Sân golf' }).getAttribute('aria-current')).toBe('page');
    expect(within(tabs).getByRole('link', { name: 'Vé tham quan' }).getAttribute('href')).toBe('/experiences');
  });

  it('hides the cheap shelf when it has fewer than 3 cards', async () => {
    api.listProducts.mockImplementation(async (params: { sort: string }) => (
      params.sort === 'price_asc' ? { ...popularFixture, results: popularFixture.results.slice(0, 2) } : popularFixture
    ));
    render(<VerticalLanding vertical="combos" />);
    await waitFor(() => expect(api.listProducts).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.queryByRole('heading', { name: 'Combo giá tốt nhất' })).toBeNull());
    expect(screen.getByRole('heading', { name: 'Combo được chọn nhiều' })).toBeTruthy();
  });
});
