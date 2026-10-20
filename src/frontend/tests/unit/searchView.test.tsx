// @vitest-environment jsdom
import React from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { scrollEdges } from '../../src/components/search/HScroller';

const state = vi.hoisted(() => ({ params: new URLSearchParams('q=Nha+Trang'), navigate: vi.fn() }));
const suggest = vi.hoisted(() => ({ fetchSuggestions: vi.fn() }));
vi.mock('../../src/services/suggest', () => ({ fetchSuggestions: suggest.fetchSuggestions, SUGGESTION_LIMIT: 8 }));
vi.mock('next/navigation', () => ({ useSearchParams: () => state.params }));
vi.mock('../../src/context/TravelContext', () => ({ useTravel: () => ({ navigate: state.navigate, showToast: vi.fn() }) }));
vi.mock('../../src/context/AssistantProvider', () => ({ useAssistant: () => ({ openFloatingWidget: vi.fn() }) }));
vi.mock('../../src/components/common/ProductCard', () => ({
  ProductCard: ({ product, variant }: { product: { id: string; name: string }; variant: string }) => <div data-testid={`${variant}-${product.id}`}>{product.name}</div>,
}));

import { SearchView } from '../../src/components/search/SearchView';
import { SortMenu } from '../../src/components/search/SortMenu';
import { clearSectionCache } from '../../src/hooks/useLazySection';
import { clearSuggestionCache } from '../../src/features/search/instant/useInstantSearch';

const item = (productId: string, taxonomy: string, unitPrice: number) => ({
  productId, name: productId, taxonomy, destination: 'Nha Trang', unitPrice, currency: 'VND',
  priceUnit: 'PER_NIGHT', available: true, score: 0.9, attributes: {},
});
const TOTALS: Record<string, number> = { hotel: 128, attraction: 48, golf: 1, combo: 11 };

function stubSearch() {
  const calls: Array<Record<string, unknown>> = [];
  global.fetch = vi.fn().mockImplementation(async (_url, init) => {
    const body = JSON.parse((init as RequestInit).body as string);
    calls.push(body);
    const n = Math.min(body.limit, 3);
    const results = Array.from({ length: n }, (_, i) => item(`${body.taxonomy}-${body.offset + i}`, body.taxonomy, 1000 * (i + 1)));
    // Có bộ lọc sao/giá thì backend trả ít hơn; hybrid luôn khai totalExact: false (không được thành dấu "+").
    const total = body.starRatingMin !== undefined || body.priceMax !== undefined ? 30 : TOTALS[body.taxonomy];
    return new Response(JSON.stringify({ results, total, topScore: 0.9, diagnostics: { totalExact: false } }), { status: 200 });
  });
  return calls;
}

describe('scrollEdges', () => {
  it('reports the start, the end and a row that does not overflow', () => {
    expect(scrollEdges(0, 400, 1000)).toEqual({ atStart: true, atEnd: false });
    expect(scrollEdges(300, 400, 1000)).toEqual({ atStart: false, atEnd: false });
    expect(scrollEdges(600, 400, 1000)).toEqual({ atStart: false, atEnd: true });
    expect(scrollEdges(599, 400, 1000)).toEqual({ atStart: false, atEnd: true });
    expect(scrollEdges(0, 400, 400)).toEqual({ atStart: true, atEnd: true });
  });
});

describe('SortMenu', () => {
  afterEach(cleanup);

  it('opens a popup, picks a sort and closes; Esc closes without choosing', () => {
    const onChange = vi.fn();
    render(<SortMenu value="relevance" onChange={onChange} />);
    expect(screen.queryByRole('menu')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /Sắp xếp/ }));
    expect(within(screen.getByRole('menu')).getAllByRole('menuitemradio')).toHaveLength(3);
    fireEvent.click(screen.getByRole('menuitemradio', { name: /Giá thấp → cao/ }));
    expect(onChange).toHaveBeenCalledWith('price_asc');
    expect(screen.queryByRole('menu')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: /Sắp xếp/ }));
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('menu')).toBeNull();
    expect(onChange).toHaveBeenCalledTimes(1);
  });
});

describe('SearchView', () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    clearSectionCache();
    clearSuggestionCache();
    window.localStorage.clear();
    suggest.fetchSuggestions.mockReset();
    suggest.fetchSuggestions.mockResolvedValue([{ type: 'destination', label: 'Hà Nội', productCount: 214 }]);
    document.cookie = 'vota_csrf=test'; // có cookie CSRF thì apiFetch không gọi bootstrap phiên trước POST
    state.navigate.mockReset();
    state.params = new URLSearchParams('q=Nha+Trang');
  });
  afterEach(() => {
    cleanup();
    global.fetch = originalFetch;
  });

  it('"Tất cả" shows three group rows with a few items each, no flights, no sort and no destination filter', async () => {
    const calls = stubSearch();
    render(<SearchView />);
    await waitFor(() => expect(screen.getByTestId('tile-hotel-0')).toBeTruthy());
    await screen.findByRole('tab', { name: /Lưu trú \(128\)/ });

    expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual(['Tất cả (188)', 'Lưu trú (128)', 'Tour và trải nghiệm (49)', 'Tiện ích khác (11)']);
    // Không có dấu "+" dù backend khai totalExact: false.
    expect(screen.getByText('Tìm thấy 188 dịch vụ phù hợp')).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Sắp xếp/ })).toBeNull();
    expect(screen.queryByText('Điểm đến')).toBeNull();
    expect(calls.some((c) => c.taxonomy === 'flight')).toBe(false);
    // Chỉ xem nhanh: mỗi request của hàng lấy 6 mục đầu, không lấy hết.
    expect(calls.filter((c) => c.taxonomy).every((c) => c.limit === 6)).toBe(true);
  });

  it('while counting, the header shows a skeleton line instead of a spinner; the count replaces it', async () => {
    stubSearch();
    render(<SearchView />);
    expect(screen.getByRole('status', { name: 'Đang đếm kết quả' })).toBeTruthy();
    expect(document.querySelector('.animate-spin')).toBeNull();
    expect(await screen.findByText('Tìm thấy 188 dịch vụ phù hợp')).toBeTruthy();
    expect(screen.queryByRole('status', { name: 'Đang đếm kết quả' })).toBeNull();
  });

  it('tab counts and row counts come from the same requests, so they always agree', async () => {
    const calls = stubSearch();
    render(<SearchView />);
    await screen.findByRole('tab', { name: /Lưu trú \(128\)/ });
    await waitFor(() => expect(screen.getByText('11 kết quả')).toBeTruthy());
    expect(screen.getByText('128 kết quả')).toBeTruthy();
    expect(screen.getByText('49 kết quả')).toBeTruthy();
    expect(screen.getByRole('button', { name: /Xem tất cả 128/ })).toBeTruthy();
    // Không có request tổng quan không lọc taxonomy; mỗi loại đúng một request, hàng và tab dùng chung.
    expect(calls.every((c) => typeof c.taxonomy === 'string')).toBe(true);
    expect(calls.map((c) => c.taxonomy).sort()).toEqual(['attraction', 'combo', 'golf', 'hotel']);
  });

  it('stay tab: star and price filters go to the API, reset to page one and show the filtered count', async () => {
    const calls = stubSearch();
    state.params = new URLSearchParams('q=Nha+Trang&type=stay');
    render(<SearchView />);
    await screen.findByTestId('row-hotel-0');
    expect(screen.getByRole('button', { name: 'Xem thêm (3/128)' })).toBeTruthy();
    expect(screen.queryByText(/kết quả theo bộ lọc/)).toBeNull();

    fireEvent.click(screen.getByRole('radio', { name: '4 sao trở lên' }));
    expect(await screen.findByText('· 30 kết quả theo bộ lọc')).toBeTruthy();
    expect(calls.at(-1)).toMatchObject({ taxonomy: 'hotel', starRatingMin: 4, offset: 0, limit: 20 });
    expect(screen.getByRole('button', { name: 'Xem thêm (3/30)' })).toBeTruthy();
    // Số trên tab là số chưa áp bộ lọc.
    expect(screen.getByRole('tab', { name: 'Lưu trú (128)' })).toBeTruthy();

    // Thanh trượt giá: một request sau khi dừng kéo, không phải một request mỗi nấc.
    const before = calls.length;
    const slider = screen.getByRole('slider', { name: 'Mức giá tối đa' });
    fireEvent.change(slider, { target: { value: '3000000' } });
    fireEvent.change(slider, { target: { value: '2000000' } });
    await waitFor(() => expect(calls.length).toBe(before + 1));
    expect(calls.at(-1)).toMatchObject({ starRatingMin: 4, priceMax: 2000000, offset: 0 });

    // Bỏ hết bộ lọc: về danh sách ban đầu (từ bộ đệm), không còn số theo bộ lọc.
    fireEvent.click(screen.getByRole('button', { name: 'Xóa tất cả' }));
    expect(await screen.findByRole('button', { name: 'Xem thêm (3/128)' })).toBeTruthy();
    expect(screen.queryByText(/kết quả theo bộ lọc/)).toBeNull();
  });

  it('the search box suggests while typing and keeps Enter, chips and the see-all button going to /search', async () => {
    stubSearch();
    render(<SearchView />);
    const box = screen.getByRole('combobox');
    fireEvent.change(box, { target: { value: 'Ha' } });
    expect(await screen.findByRole('option', { name: /Hà Nội/ })).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Xem tất cả kết quả cho “Ha”' }));
    expect(state.navigate).toHaveBeenLastCalledWith(expect.stringContaining('q=Ha'));

    fireEvent.change(box, { target: { value: 'Phú Quốc' } });
    fireEvent.submit(box.closest('form') as HTMLFormElement);
    expect(state.navigate).toHaveBeenLastCalledWith(expect.stringContaining('q=Ph'));
    fireEvent.click(screen.getByRole('button', { name: 'Sân golf nghỉ dưỡng' }));
    expect(state.navigate).toHaveBeenLastCalledWith(expect.stringContaining('golf'));
    expect(JSON.parse(window.localStorage.getItem('vota_recent_searches') ?? '[]')).toEqual(['Sân golf nghỉ dưỡng', 'Phú Quốc', 'Ha']);
  });

  it('"Xem tất cả" goes to the group tab, which loads a full page with a sort popup and load-more', async () => {
    const calls = stubSearch();
    render(<SearchView />);
    await screen.findByTestId('tile-hotel-0');
    fireEvent.click(screen.getAllByRole('button', { name: /Xem tất cả/ })[0]);
    expect(state.navigate).toHaveBeenCalledWith('/search?q=Nha+Trang&type=stay');
    cleanup();

    state.params = new URLSearchParams('q=Nha+Trang&type=stay');
    render(<SearchView />);
    await screen.findByTestId('row-hotel-0');
    expect(calls.some((c) => c.taxonomy === 'hotel' && c.limit === 20 && c.offset === 0)).toBe(true);
    expect(screen.getByRole('button', { name: /Sắp xếp/ })).toBeTruthy();
    expect(screen.getByText('Hạng sao khách sạn')).toBeTruthy();

    // Bộ đệm: trang đầu của tab đã tải nên "Xem thêm" chỉ gọi trang kế.
    calls.length = 0;
    fireEvent.click(await screen.findByRole('button', { name: /Xem thêm/ }));
    await screen.findByTestId('row-hotel-20');
    expect(calls.filter((c) => c.taxonomy === 'hotel').map((c) => c.offset)).toEqual([20]);
  });

  it('a group tab holds its place with five row skeletons until the first page arrives', async () => {
    stubSearch();
    state.params = new URLSearchParams('q=Nha+Trang&type=stay');
    render(<SearchView />);
    const skeleton = screen.getByRole('status', { name: 'Đang tải kết quả' });
    expect(skeleton.getAttribute('aria-busy')).toBe('true');
    expect(skeleton.querySelectorAll(':scope > [aria-hidden="true"]')).toHaveLength(5);
    expect(skeleton.querySelector('.animate-pulse')).toBeNull();
    await screen.findByTestId('row-hotel-0');
    expect(screen.queryByRole('status', { name: 'Đang tải kết quả' })).toBeNull();
  });

  it('non-stay tabs have the sort popup but no star/price sidebar; sorting is in the popup', async () => {
    stubSearch();
    state.params = new URLSearchParams('q=Nha+Trang&type=exp');
    render(<SearchView />);
    await screen.findByTestId('row-attraction-0');
    expect(screen.getByRole('button', { name: /Sắp xếp/ })).toBeTruthy();
    expect(screen.queryByText('Hạng sao khách sạn')).toBeNull();
  });

  it('keeps ?type=flight as a flat list with no tabs', async () => {
    const calls = stubSearch();
    state.params = new URLSearchParams('q=v%C3%A9+m%C3%A1y+bay&type=flight');
    render(<SearchView />);
    await act(async () => {});
    expect(screen.queryAllByRole('tab')).toHaveLength(0);
    expect(calls.every((c) => c.taxonomy === 'flight')).toBe(true);
  });

  it('shows a destination from the URL as a removable chip, without a destination checkbox list', async () => {
    stubSearch();
    state.params = new URLSearchParams('q=Nha+Trang&type=stay&destination=Nha+Trang');
    render(<SearchView />);
    await screen.findByTestId('row-hotel-0');
    fireEvent.click(screen.getByRole('button', { name: 'Bỏ lọc Nha Trang' }));
    expect(state.navigate).toHaveBeenCalledWith('/search?q=Nha+Trang&type=stay');
    expect(screen.queryByRole('checkbox')).toBeNull();
  });
});
