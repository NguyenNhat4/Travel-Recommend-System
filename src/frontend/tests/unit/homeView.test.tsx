// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import popularFixture from '../../../shared/mocks/catalog/listProducts.200-popular.json';

const api = vi.hoisted(() => ({ listProducts: vi.fn(), listDestinations: vi.fn(), fetchRecommendations: vi.fn(), fetchSuggestions: vi.fn() }));
const travel = vi.hoisted(() => ({
  currentPersona: null as unknown, activeEvents: [] as unknown[], navigate: vi.fn(), showToast: vi.fn(),
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

  it('guest: does not call /recommendations and loads the popular shelf exactly once (all categories)', async () => {
    render(<HomeView />);
    await waitFor(() => expect(api.listProducts).toHaveBeenCalledTimes(1));
    expect(api.listProducts.mock.calls[0][0]).toEqual({ sort: 'popular', availableOnly: true, limit: 8 });
    expect(api.fetchRecommendations).not.toHaveBeenCalled();
  });

  it('logged in: calls /recommendations once', async () => {
    travel.currentPersona = { id: 'VP1', name: 'Minh Anh' };
    render(<HomeView />);
    await waitFor(() => expect(api.fetchRecommendations).toHaveBeenCalledTimes(1));
    expect(api.fetchRecommendations.mock.calls[0][0]).toMatchObject({ k: 4 });
    expect(await screen.findByRole('button', { name: 'Thử lại' })).toBeTruthy(); // gợi ý lỗi: ẩn khối, chỉ có dòng thử lại
  });

  it('only the selected popular tab calls the API', async () => {
    render(<HomeView />);
    await waitFor(() => expect(api.listProducts).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole('tab', { name: 'Vé máy bay' }));
    await waitFor(() => expect(api.listProducts).toHaveBeenCalledTimes(2));
    expect(api.listProducts.mock.calls[1][0]).toMatchObject({ taxonomy: 'flight', sort: 'popular' });
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
