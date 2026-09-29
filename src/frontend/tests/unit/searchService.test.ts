import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { searchProductsApi } from '../../src/services/search';

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
