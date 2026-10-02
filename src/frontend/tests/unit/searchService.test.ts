import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  SEARCH_GROUPS, TAB_GROUPS, parseGroupParam, searchCacheKey, searchGroupApi, searchOverviewApi, searchProductsApi, viewItems,
} from '../../src/services/search';

describe('search service searchProductsApi', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('calls /api/v1/search with POST and maps backend response correctly', async () => {
    const mockBackendResponse = {
      results: [
        {
          productId: 'nt-hotel-01',
          name: 'V-OTA Resort & Spa Nha Trang Bay',
          taxonomy: 'hotel',
          destination: 'Nha Trang',
          unitPrice: 2294500,
          imageUrl: 'https://example.com/hotel.jpg',
          score: 0.92,
        },
      ],
      total: 1,
      cutoff: 0.62,
      topScore: 0.92,
      facets: {
        taxonomy: { hotel: 1, flight: 0, attraction: 0, combo: 0, golf: 0 },
        destination: { 'Nha Trang': 1 },
      },
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockBackendResponse,
    });

    const response = await searchProductsApi('resort nha trang');

    const [url, init] = vi.mocked(global.fetch).mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/search');
    expect(init.method).toBe('POST');
    expect(init.credentials).toBe('same-origin');
    expect(new Headers(init.headers).get('content-type')).toBe('application/json');
    expect(init.body).toBe(JSON.stringify({
      query: 'resort nha trang',
      taxonomy: null,
      destination: null,
      limit: 20,
      offset: 0,
    }));

    expect(response.total).toBe(1);
    expect(response.results.length).toBe(1);
    expect(response.results[0].product.name).toBe('V-OTA Resort & Spa Nha Trang Bay');
    expect(response.results[0].relevanceScore).toBe(0.92);
    expect(response.categoryCounts.hotel).toBe(1);
  });

  it('searches the category name, not hotels, when the query is empty (e.g. /search?type=flight)', async () => {
    global.fetch = vi.fn().mockImplementation(async () => new Response(JSON.stringify({ results: [], total: 0 }), { status: 200 }));

    await searchProductsApi('  ', { taxonomy: 'flight' });
    await searchProductsApi('', { taxonomy: 'golf' });
    await searchProductsApi('');

    const queries = vi.mocked(global.fetch).mock.calls.map(([, init]) => JSON.parse((init as RequestInit).body as string).query);
    expect(queries).toEqual(['vé máy bay', 'sân golf', 'khách sạn']);
  });

  it('throws instead of returning local results when the backend fails', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error (backend down)'));
    await expect(searchProductsApi('VinWonders')).rejects.toMatchObject({ code: 'NETWORK_ERROR', retryable: true });
  });

  it('keeps unpriced products last when sorting by price', async () => {
    const item = (productId: string, unitPrice: number | null) => ({
      productId, name: productId, taxonomy: 'hotel', destination: 'Nha Trang', unitPrice, currency: 'VND',
      priceUnit: unitPrice == null ? 'UNKNOWN' : 'PER_NIGHT', available: true, score: 0.8,
    });
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      results: [item('free', null), item('dear', 9), item('cheap', 1)], total: 3, topScore: 0.8,
    }), { status: 200 }));
    const asc = await searchProductsApi('x', {}, 'price_asc');
    expect(asc.results.map((r) => r.product.id)).toEqual(['cheap', 'dear', 'free']);
    expect(asc.isWeakMatch).toBe(false);
  });
});

describe('search groups', () => {
  const originalFetch = global.fetch;
  const item = (productId: string, taxonomy: string, unitPrice: number | null, score: number, starRating?: number) => ({
    productId, name: productId, taxonomy, destination: 'Nha Trang', unitPrice, currency: 'VND',
    priceUnit: 'PER_NIGHT', available: true, score, attributes: starRating ? { starRating } : {},
  });
  const bodies = () => vi.mocked(global.fetch).mock.calls.map(([, init]) => JSON.parse((init as RequestInit).body as string));

  afterEach(() => { global.fetch = originalFetch; });

  it('maps ?type= to a group, accepting old taxonomies', () => {
    expect(parseGroupParam('stay')).toBe('stay');
    expect(parseGroupParam('hotel')).toBe('stay');
    expect(parseGroupParam('attraction')).toBe('exp');
    expect(parseGroupParam('golf')).toBe('exp');
    expect(parseGroupParam('combo')).toBe('more');
    expect(parseGroupParam('flight')).toBe('flight');
    expect(parseGroupParam('nonsense')).toBeUndefined();
    expect(parseGroupParam(null)).toBeUndefined();
  });

  it('never queries flights for the tab groups', () => {
    for (const group of TAB_GROUPS) expect(SEARCH_GROUPS[group].taxonomies).not.toContain('flight');
  });

  it('runs one request per taxonomy of the group and merges by score', async () => {
    global.fetch = vi.fn().mockImplementation(async (_url, init) => {
      const { taxonomy } = JSON.parse((init as RequestInit).body as string);
      const results = taxonomy === 'golf'
        ? [item('golf-1', 'golf', 100, 0.9)]
        : [item('att-1', 'attraction', 50, 0.95), item('att-2', 'attraction', 60, 0.5)];
      return new Response(JSON.stringify({ results, total: taxonomy === 'golf' ? 1 : 40 }), { status: 200 });
    });
    const page = await searchGroupApi('nha trang', 'exp', { destination: 'Nha Trang', limit: 6 });
    expect(bodies().map((b) => b.taxonomy).sort()).toEqual(['attraction', 'golf']);
    expect(bodies().every((b) => b.limit === 6 && b.offset === 0 && b.destination === 'Nha Trang')).toBe(true);
    expect(page.items.map((r) => r.product.id)).toEqual(['att-1', 'golf-1', 'att-2']);
    expect(page.total).toBe(41);
    expect(page.hasMore).toBe(true);
  });

  it('reports hasMore false once the offset reaches the total', async () => {
    global.fetch = vi.fn().mockImplementation(async () => new Response(JSON.stringify({ results: [item('h', 'hotel', 1, 0.9)], total: 7 }), { status: 200 }));
    expect((await searchGroupApi('x', 'stay', { limit: 6, offset: 0 })).hasMore).toBe(true);
    expect((await searchGroupApi('x', 'stay', { limit: 6, offset: 6 })).hasMore).toBe(false);
  });

  it('counts tabs from one unfiltered request and leaves flights out', async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      results: [], total: 201, facets: { taxonomy: { hotel: 128, flight: 13, attraction: 48, combo: 11, golf: 1 }, destination: {} },
    }), { status: 200 }));
    const overview = await searchOverviewApi('Nha Trang');
    expect(overview.counts).toEqual({ stay: 128, exp: 49, more: 11 });
    expect(overview.total).toBe(188);
    expect(bodies()).toHaveLength(1);
    expect(bodies()[0]).toMatchObject({ taxonomy: null, limit: 1 });
  });

  it('sorts and filters loaded items, keeping unpriced ones last', () => {
    const make = (id: string, price: number | null, star?: number) => ({
      product: { id, unitPrice: price, attributes: star ? { starRating: star } : {} },
      relevanceScore: 0, matchTags: [],
    }) as never;
    const items = [make('mid', 500, 4), make('none', null), make('low', 100, 3), make('high', 900, 5)];
    expect(viewItems(items, { sort: 'price_asc' }).map((r) => r.product.id)).toEqual(['low', 'mid', 'high', 'none']);
    expect(viewItems(items, { sort: 'price_desc' }).map((r) => r.product.id)).toEqual(['high', 'mid', 'low', 'none']);
    expect(viewItems(items, { sort: 'relevance', maxPrice: 500 }).map((r) => r.product.id)).toEqual(['mid', 'low']);
    expect(viewItems(items, { sort: 'relevance', minStarRating: 4 }).map((r) => r.product.id)).toEqual(['mid', 'none', 'high']);
  });

  it('builds a cache key that separates group, limit and destination', () => {
    const a = searchCacheKey('group', 'Nha Trang ', null, 'stay', 6, 0);
    expect(a).toBe(searchCacheKey('group', 'nha trang', undefined, 'stay', 6, 0));
    expect(a).not.toBe(searchCacheKey('group', 'nha trang', null, 'stay', 20, 0));
    expect(a).not.toBe(searchCacheKey('group', 'nha trang', 'Phú Quốc', 'stay', 6, 0));
  });
});
