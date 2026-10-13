// @vitest-environment jsdom
import React from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import popularFixture from '../../../shared/mocks/catalog/listProducts.200-popular.json';
import diversifiedFixture from '../../../shared/mocks/catalog/listProducts.200-diversified.json';

const api = vi.hoisted(() => ({ listProducts: vi.fn(), listDestinations: vi.fn(), fetchRecommendations: vi.fn(), fetchSuggestions: vi.fn() }));
const travel = vi.hoisted(() => ({
  currentPersona: null as unknown, activeEvents: [] as unknown[], navigate: vi.fn(), showToast: vi.fn(), authReady: true, openLoginModal: vi.fn(),
}));
vi.mock('../../src/services/catalog', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/services/catalog')>()),
  listProducts: api.listProducts,
}));
vi.mock('../../src/services/destinations', () => ({ listDestinations: api.listDestinations }));
vi.mock('../../src/services/recsys', () => ({ fetchRecommendations: api.fetchRecommendations }));
vi.mock('../../src/services/suggest', () => ({ fetchSuggestions: api.fetchSuggestions, SUGGESTION_LIMIT: 8 }));
vi.mock('../../src/context/TravelContext', () => ({ useTravel: () => travel }));

import { HomeView } from '../../src/components/home/HomeView';
import { productFromApi } from '../../src/services/catalog';
import { clearSectionCache } from '../../src/hooks/useLazySection';
import { clearSuggestionCache } from '../../src/features/search/instant/useInstantSearch';

describe('HomeView', () => {
  beforeEach(() => {
    clearSectionCache();
    clearSuggestionCache();
    window.localStorage.clear();
    Object.values(api).forEach((fn) => fn.mockReset());
    api.fetchSuggestions.mockResolvedValue([
      { type: 'destination', label: 'Hà Nội', productCount: 214 },
      { type: 'product', label: 'VinWonders Phú Quốc', productId: 'pq-a-01', taxonomy: 'attraction', destination: 'Phú Quốc' },
    ]);
    travel.currentPersona = null;
    travel.authReady = true;
    travel.navigate.mockReset();
    travel.openLoginModal.mockReset();
    api.listProducts.mockResolvedValue(popularFixture);
    api.listDestinations.mockResolvedValue([]);
    api.fetchRecommendations.mockRejectedValue(new Error('không cần'));
    // Không có IntersectionObserver trong jsdom nên mọi khối coi như đã vào vùng nhìn; dừng lại ở "đã tải một lần".
    vi.stubGlobal('matchMedia', () => ({ matches: true }));
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('guest: does not call /recommendations and loads the popular shelf exactly once (all categories, mixed by type)', async () => {
    render(<HomeView />);
    await waitFor(() => expect(api.listProducts).toHaveBeenCalledTimes(1));
    expect(api.listProducts.mock.calls[0][0]).toEqual({ diversify: 'taxonomy', sort: 'popular', availableOnly: true, limit: 8 });
    expect(api.fetchRecommendations).not.toHaveBeenCalled();
  });

  it('the "Vé tham quan" tab includes golf', async () => {
    render(<HomeView />);
    await waitFor(() => expect(api.listProducts).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole('tab', { name: 'Vé tham quan' }));
    await waitFor(() => expect(api.listProducts).toHaveBeenCalledTimes(2));
    expect(api.listProducts.mock.calls[1][0]).toEqual({ taxonomy: ['attraction', 'golf'], sort: 'popular', availableOnly: true, limit: 8 });
  });

  it('only the "Tất cả" shelf labels each card with its type', async () => {
    api.listProducts.mockResolvedValue(diversifiedFixture);
    render(<HomeView />);
    const shelf = () => screen.getByRole('region', { name: 'Phổ biến tại các điểm đến Việt Nam' });
    await waitFor(() => expect(within(shelf()).getAllByRole('link')).toHaveLength(8));
    expect(within(shelf()).getAllByText('Khách sạn')).toHaveLength(2);
    expect(within(shelf()).getAllByText('Vé tham quan')).toHaveLength(1);
    expect(within(shelf()).getAllByText('Golf')).toHaveLength(1);
    expect(within(shelf()).getAllByText('Combo')).toHaveLength(2);
    expect(within(shelf()).getAllByText('Vé máy bay')).toHaveLength(2);

    fireEvent.click(screen.getByRole('tab', { name: 'Khách sạn' }));
    await waitFor(() => expect(api.listProducts).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(within(shelf()).getAllByRole('link')).toHaveLength(8));
    expect(within(shelf()).queryAllByText('Khách sạn')).toHaveLength(0);
  });

  it('logged in: calls /recommendations once', async () => {
    travel.currentPersona = { id: 'VP1', name: 'Minh Anh' };
    render(<HomeView />);
    await waitFor(() => expect(api.fetchRecommendations).toHaveBeenCalledTimes(1));
    expect(api.fetchRecommendations.mock.calls[0][0]).toMatchObject({ k: 4 });
    expect(await screen.findByRole('button', { name: 'Thử lại' })).toBeTruthy(); // gợi ý lỗi: ẩn khối, chỉ có dòng thử lại
  });

  it('guest: shows the sign-in banner and its buttons open the login modal / register page', () => {
    render(<HomeView />);
    const banner = screen.getByRole('region', { name: 'Đăng nhập để nhận gợi ý' });
    expect(within(banner).getByText('Đăng nhập để nhận gợi ý theo chuyến đi của bạn')).toBeTruthy();
    fireEvent.click(within(banner).getByRole('button', { name: 'Đăng nhập' }));
    expect(travel.openLoginModal).toHaveBeenCalledTimes(1);
    fireEvent.click(within(banner).getByRole('button', { name: 'Đăng ký' }));
    expect(travel.navigate).toHaveBeenCalledWith('/register');
  });

  it('hides the sign-in banner while the session loads and once logged in', () => {
    travel.authReady = false;
    const { unmount } = render(<HomeView />);
    expect(screen.queryByRole('region', { name: 'Đăng nhập để nhận gợi ý' })).toBeNull();
    unmount();
    travel.authReady = true;
    travel.currentPersona = { id: 'VP1', name: 'Minh Anh' };
    render(<HomeView />);
    expect(screen.queryByRole('region', { name: 'Đăng nhập để nhận gợi ý' })).toBeNull();
  });

  it('only the selected popular tab calls the API', async () => {
    render(<HomeView />);
    await waitFor(() => expect(api.listProducts).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole('tab', { name: 'Vé máy bay' }));
    await waitFor(() => expect(api.listProducts).toHaveBeenCalledTimes(2));
    expect(api.listProducts.mock.calls[1][0]).toMatchObject({ taxonomy: 'flight', sort: 'popular' });
    expect(api.listProducts.mock.calls[1][0]).not.toHaveProperty('diversify');
    expect(screen.getByRole('tab', { name: 'Vé máy bay' }).getAttribute('aria-selected')).toBe('true');
  });

  it('links the four categories to their pages and no longer carries the hotel search form', () => {
    render(<HomeView />);
    const nav = screen.getByRole('region', { name: 'Danh mục dịch vụ' });
    expect(Array.from(nav.querySelectorAll('a')).map((a) => a.getAttribute('href'))).toEqual(['/flights', '/hotels', '/experiences', '/combos']);
    expect(screen.queryByText('Khách sạn / Điểm đến')).toBeNull();
    expect(screen.queryByText(/36 Khách sạn/)).toBeNull();
  });

  it('AI search sends the typed text to /search', () => {
    render(<HomeView />);
    fireEvent.change(screen.getByLabelText('Mô tả chuyến đi bạn muốn'), { target: { value: 'resort có hồ bơi' } });
    fireEvent.submit(screen.getByRole('search'));
    expect(travel.navigate).toHaveBeenCalledWith('/search?q=resort%20c%C3%B3%20h%E1%BB%93%20b%C6%A1i');
  });

  describe('recommendation block skeleton (product.md §4.1.5)', () => {
    const block = () => screen.queryByRole('region', { name: 'Gợi ý cho bạn' });
    const skeleton = () => screen.queryByRole('status', { name: 'Đang tải gợi ý cho bạn' });
    const recs = (count = 4) => ({
      strategy: 'cross_vertical', destination: 'Nha Trang', nextVertical: 'flight',
      recommendations: popularFixture.results.slice(0, count).map((item, i) => ({
        product: productFromApi(item as never), score: 0.9 - i / 10, rank: i + 1, because: [],
      })),
      diagnostics: { eventsUsed: 3, coldStart: false, excludedVerticals: [], modelVersion: 't' },
      generatedAt: '',
    });

    beforeEach(() => { travel.currentPersona = { id: 'VP1', name: 'Minh Anh' }; });

    it('logged in: shows a 4-card skeleton in the block until /recommendations answers, then the real cards', async () => {
      let answer!: (value: unknown) => void;
      api.fetchRecommendations.mockReturnValue(new Promise((resolve) => { answer = resolve; }));
      render(<HomeView />);
      expect(block()!.getAttribute('aria-busy')).toBe('true');
      expect(within(block()!).getByRole('heading', { name: 'Gợi ý' })).toBeTruthy();
      expect(skeleton()!.querySelectorAll(':scope > [aria-hidden="true"]')).toHaveLength(4);
      expect(within(block()!).queryByRole('button', { name: 'Vì sao có gợi ý này?' })).toBeNull();

      answer(recs());
      await waitFor(() => expect(skeleton()).toBeNull());
      expect(block()!.getAttribute('aria-busy')).toBe('false');
      expect(within(block()!).getByRole('button', { name: 'Vì sao có gợi ý này?' })).toBeTruthy();
      expect(within(block()!).getByText(popularFixture.results[0].name)).toBeTruthy();
    });

    it('an error removes the skeleton and leaves only the retry line; retrying shows the skeleton again', async () => {
      api.fetchRecommendations.mockRejectedValueOnce(new Error('503')).mockReturnValueOnce(new Promise(() => {}));
      render(<HomeView />);
      expect(skeleton()).toBeTruthy();
      fireEvent.click(await screen.findByRole('button', { name: 'Thử lại' }));
      expect(skeleton()).toBeTruthy();
      expect(screen.queryByRole('button', { name: 'Thử lại' })).toBeNull();
    });

    it('an empty answer removes the block instead of leaving the skeleton', async () => {
      api.fetchRecommendations.mockResolvedValue(recs(0));
      render(<HomeView />);
      expect(skeleton()).toBeTruthy();
      await waitFor(() => expect(block()).toBeNull());
      expect(screen.queryByRole('button', { name: 'Thử lại' })).toBeNull();
    });

    it('after the 10 s timeout the skeleton gives way to the retry line', async () => {
      vi.useFakeTimers();
      api.fetchRecommendations.mockImplementation(({ signal }: { signal: AbortSignal }) => new Promise((_, reject) => {
        signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
      }));
      try {
        render(<HomeView />);
        expect(skeleton()).toBeTruthy();
        await act(async () => { await vi.advanceTimersByTimeAsync(9_900); });
        expect(skeleton()).toBeTruthy();
        await act(async () => { await vi.advanceTimersByTimeAsync(200); });
        expect(skeleton()).toBeNull();
        expect(screen.getByRole('button', { name: 'Thử lại' })).toBeTruthy();
      } finally {
        vi.useRealTimers();
      }
    });

    it('guests and a still-restoring session never see the recommendation skeleton', () => {
      travel.currentPersona = null;
      const { unmount } = render(<HomeView />);
      expect(skeleton()).toBeNull();
      unmount();
      travel.authReady = false;
      render(<HomeView />);
      expect(skeleton()).toBeNull();
      expect(api.fetchRecommendations).not.toHaveBeenCalled();
    });
  });

  describe('instant search (FR-SRC-05)', () => {
    const box = () => screen.getByLabelText('Mô tả chuyến đi bạn muốn') as HTMLInputElement;

    it('typing shows suggestions by kind without pressing Enter; a product opens its detail page', async () => {
      render(<HomeView />);
      fireEvent.change(box(), { target: { value: 'Ha' } });
      expect(await screen.findByRole('option', { name: /Hà Nội/ })).toBeTruthy();
      expect(api.fetchSuggestions).toHaveBeenCalledTimes(1);
      expect(travel.navigate).not.toHaveBeenCalled();
      expect(screen.getByRole('button', { name: 'Xem tất cả kết quả cho “Ha”' })).toBeTruthy();

      fireEvent.click(screen.getByRole('option', { name: /VinWonders Phú Quốc/ }));
      expect(travel.navigate).toHaveBeenCalledWith('/product/pq-a-01');
      expect(screen.queryByRole('listbox')).toBeNull();
    });

    it('does not call the API for one character; the empty box offers popular keywords', async () => {
      render(<HomeView />);
      fireEvent.focus(box());
      expect(within(screen.getByRole('group', { name: 'Từ khoá phổ biến' })).getAllByRole('option').length).toBeGreaterThan(0);
      fireEvent.change(box(), { target: { value: 'H' } });
      await new Promise((r) => setTimeout(r, 300));
      expect(api.fetchSuggestions).not.toHaveBeenCalled();
    });

    it('a suggestion chip is remembered as a recent search', () => {
      render(<HomeView />);
      fireEvent.click(screen.getByRole('link', { name: 'Combo Phú Quốc 3N2Đ giá tốt' }));
      expect(JSON.parse(window.localStorage.getItem('vota_recent_searches') ?? '[]')).toEqual(['Combo Phú Quốc 3N2Đ giá tốt']);
    });
  });
});
