// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const state = vi.hoisted(() => ({ navigate: vi.fn(), openFloatingWidget: vi.fn() }));
vi.mock('../../src/context/TravelContext', () => ({ useTravel: () => ({ navigate: state.navigate, showToast: vi.fn() }) }));
vi.mock('../../src/context/AssistantProvider', () => ({ useAssistant: () => ({ openFloatingWidget: state.openFloatingWidget }) }));
vi.mock('../../src/services/destinations', () => ({ listDestinations: vi.fn().mockResolvedValue([]) }));
vi.mock('../../src/components/common/ProductCard', () => ({
  ProductCard: ({ product, variant, tripQuery }: { product: { id: string; name: string }; variant: string; tripQuery?: string }) => (
    <div data-testid={`${variant}-${product.id}`} data-trip={tripQuery}>{product.name}</div>
  ),
}));

import { VerticalLanding } from '../../src/features/catalog/landing/VerticalLanding';
import { guestsOf, stayOf } from '../../src/features/catalog/landing/LandingResults';
import { clearSectionCache } from '../../src/hooks/useLazySection';

const item = (productId: string, taxonomy: string, unitPrice: number) => ({
  productId, name: productId, taxonomy, destination: 'Nha Trang', unitPrice, currency: 'VND',
  priceUnit: 'PER_NIGHT', available: true, score: 0.9, attributes: {},
});

const TRIP = { checkIn: '2099-10-20', checkOut: '2099-10-22', adults: 2, children: 1, rooms: 1 };

describe('guestsOf', () => {
  it('uses the party as is for one room and splits it across rooms (rounded up)', () => {
    expect(guestsOf({})).toBeUndefined();
    expect(guestsOf({ adults: 2, children: 1 })).toEqual({ adults: 2, children: 1 });
    expect(guestsOf({ adults: 2, children: 1, rooms: 1 })).toEqual({ adults: 2, children: 1 });
    expect(guestsOf({ adults: 4, children: 0, rooms: 2 })).toEqual({ adults: 2, children: 0 });
    expect(guestsOf({ adults: 3, children: 2, rooms: 2 })).toEqual({ adults: 3, children: 0 });
  });
});

describe('stayOf', () => {
  it('turns the trip dates into travelContext dates and leaves out a missing check-out', () => {
    expect(stayOf({})).toBeUndefined();
    expect(stayOf({ adults: 2 })).toBeUndefined();
    expect(stayOf({ checkIn: '2099-10-20' })).toEqual({ checkIn: '2099-10-20' });
    expect(stayOf({ checkIn: '2099-10-20', checkOut: '2099-10-22' })).toEqual({ checkIn: '2099-10-20', checkOut: '2099-10-22' });
  });
});

describe('trang danh mục ở chế độ tìm (?q=)', () => {
  const originalFetch = global.fetch;
  let bodies: Array<Record<string, unknown>>;
  let urls: string[];

  beforeEach(() => {
    clearSectionCache();
    state.navigate.mockReset();
    state.openFloatingWidget.mockReset();
    bodies = [];
    urls = [];
    global.fetch = vi.fn().mockImplementation(async (url, init) => {
      if (String(url) !== '/api/v1/search') return new Response('{}', { status: 200 });
      urls.push(String(url));
      const body = JSON.parse(((init as RequestInit)?.body as string) ?? '{}');
      bodies.push(body);
      return new Response(JSON.stringify({
        results: [item(`${body.taxonomy}-1`, body.taxonomy, 900000), item(`${body.taxonomy}-2`, body.taxonomy, 300000)],
        total: 2,
      }), { status: 200 });
    });
  });
  afterEach(() => {
    cleanup();
    global.fetch = originalFetch;
  });

  it('hotels: shows results under the sheet for hotels only, with the filter sidebar, and no shelves', async () => {
    render(<VerticalLanding vertical="hotels" query="khách sạn" destination="Nha Trang" trip={TRIP} />);
    expect(await screen.findByTestId('row-hotel-1')).toBeTruthy();
    expect(bodies).toHaveLength(1);
    expect(bodies[0]).toMatchObject({ taxonomy: 'hotel', destination: 'Nha Trang', query: 'khách sạn' });
    expect(urls.every((u) => u === '/api/v1/search')).toBe(true);

    expect(screen.getByRole('heading', { level: 2, name: 'Khách sạn tại Nha Trang' })).toBeTruthy();
    expect(screen.getByText('20/10 – 22/10 · 1 phòng, 2 người lớn, 1 trẻ em')).toBeTruthy();
    expect(screen.getByText('Bộ lọc tìm kiếm')).toBeTruthy();
    expect(screen.queryByText(/Điểm đến do câu tìm kiếm quyết định/)).toBeNull();
    expect(screen.queryByRole('heading', { name: 'Khách sạn và resort phổ biến tại Nha Trang' })).toBeNull();
    // Ngày và số khách đi tiếp tới trang chi tiết.
    expect(screen.getByTestId('row-hotel-1').getAttribute('data-trip')).toContain('checkIn=2099-10-20');
  });

  it('sends the party as travelContext.guests so the API filters by capacity', async () => {
    render(<VerticalLanding vertical="hotels" query="khách sạn" trip={TRIP} />);
    await screen.findByTestId('row-hotel-1');
    expect(bodies[0]).toMatchObject({ taxonomy: 'hotel', travelContext: { guests: { adults: 2, children: 1 } } });
  });

  it('sends the dates as travelContext.checkIn/checkOut next to the guests', async () => {
    render(<VerticalLanding vertical="hotels" query="khách sạn" trip={TRIP} />);
    await screen.findByTestId('row-hotel-1');
    expect(bodies[0]).toMatchObject({ travelContext: { checkIn: '2099-10-20', checkOut: '2099-10-22', guests: { adults: 2, children: 1 } } });
  });

  it('the star filter goes to the API together with the dates and the party', async () => {
    render(<VerticalLanding vertical="hotels" query="khách sạn" trip={TRIP} />);
    await screen.findByTestId('row-hotel-1');
    fireEvent.click(screen.getByRole('radio', { name: '5 sao (Luxury)' }));
    await waitFor(() => expect(bodies).toHaveLength(2));
    expect(bodies[1]).toMatchObject({
      taxonomy: 'hotel', starRatingMin: 5, offset: 0,
      travelContext: { checkIn: '2099-10-20', checkOut: '2099-10-22', guests: { adults: 2, children: 1 } },
    });
    expect(await screen.findByText('· 2 kết quả theo bộ lọc')).toBeTruthy();
  });

  it('a one-day product sends only checkIn', async () => {
    render(<VerticalLanding vertical="experiences" query="vé tham quan" trip={{ checkIn: '2099-10-20', adults: 2 }} />);
    await screen.findByTestId('row-attraction-1');
    const ctx = (bodies[0] as { travelContext: Record<string, unknown> }).travelContext;
    expect(ctx.checkIn).toBe('2099-10-20');
    expect(ctx).not.toHaveProperty('checkOut');
  });

  it('sends no guests when the URL has no party', async () => {
    render(<VerticalLanding vertical="hotels" query="khách sạn" trip={{}} />);
    await screen.findByTestId('row-hotel-1');
    expect(bodies[0]).not.toHaveProperty('travelContext');
  });

  it('prefills the sheet from the URL (destination, dates, party)', async () => {
    render(<VerticalLanding vertical="hotels" query="khách sạn" destination="Nha Trang" trip={TRIP} />);
    await screen.findByTestId('row-hotel-1');
    expect((screen.getByRole('combobox') as HTMLInputElement).value).toBe('Nha Trang');
    expect(screen.getByText('1 phòng, 2 người lớn, 1 trẻ em')).toBeTruthy();
  });

  it('free text becomes the title and the sheet text; the query goes to the API', async () => {
    render(<VerticalLanding vertical="hotels" query="resort yên tĩnh" trip={{}} />);
    expect(await screen.findByRole('heading', { level: 2, name: 'Kết quả cho “resort yên tĩnh”' })).toBeTruthy();
    expect(bodies[0]).toMatchObject({ taxonomy: 'hotel', query: 'resort yên tĩnh', destination: null });
    expect((screen.getByRole('combobox') as HTMLInputElement).value).toBe('resort yên tĩnh');
  });

  it('experiences: ?type=golf searches golf only and has no hotel filter sidebar', async () => {
    render(<VerticalLanding vertical="experiences" type="golf" query="sân golf" trip={{}} />);
    expect(await screen.findByTestId('row-golf-1')).toBeTruthy();
    expect(bodies.map((b) => b.taxonomy)).toEqual(['golf']);
    expect(screen.queryByText('Bộ lọc tìm kiếm')).toBeNull();
    expect(screen.getByRole('link', { name: 'Sân golf' }).getAttribute('aria-current')).toBe('page');
  });

  it('combos: searches combos only', async () => {
    render(<VerticalLanding vertical="combos" query="combo du lịch" trip={{}} />);
    expect(await screen.findByTestId('row-combo-1')).toBeTruthy();
    expect(bodies.map((b) => b.taxonomy)).toEqual(['combo']);
  });

  it('the destination chip clears the destination and keeps the page, query and trip', async () => {
    render(<VerticalLanding vertical="hotels" query="khách sạn" destination="Nha Trang" trip={TRIP} />);
    await screen.findByTestId('row-hotel-1');
    fireEvent.click(screen.getByRole('button', { name: 'Bỏ lọc Nha Trang' }));
    const target = new URL(state.navigate.mock.calls.at(-1)![0], 'http://x');
    expect(target.pathname).toBe('/hotels');
    expect(target.searchParams.get('destination')).toBeNull();
    expect(target.searchParams.get('q')).toBe('khách sạn');
    expect(target.searchParams.get('checkIn')).toBe('2099-10-20');
  });

  it('submitting the sheet stays on the category page (never /search)', async () => {
    render(<VerticalLanding vertical="hotels" query="khách sạn" destination="Nha Trang" trip={TRIP} />);
    await screen.findByTestId('row-hotel-1');
    fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));
    expect(new URL(state.navigate.mock.calls.at(-1)![0], 'http://x').pathname).toBe('/hotels');
  });

  it('shows the empty state with the assistant when nothing matches', async () => {
    global.fetch = vi.fn().mockImplementation(async () => new Response(JSON.stringify({ results: [], total: 0 }), { status: 200 }));
    render(<VerticalLanding vertical="hotels" query="xứ sở thần tiên" trip={{}} />);
    expect(await screen.findByText(/Chưa tìm thấy dịch vụ nào cho/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Nhờ Trợ lý AI gợi ý' }));
    await waitFor(() => expect(state.openFloatingWidget).toHaveBeenCalledWith('xứ sở thần tiên'));
  });
});
