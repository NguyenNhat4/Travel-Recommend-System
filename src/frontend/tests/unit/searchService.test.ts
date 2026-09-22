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

    expect(global.fetch).toHaveBeenCalledWith('/api/v1/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: 'resort nha trang',
        taxonomy: null,
        destination: null,
        limit: 20,
        offset: 0,
      }),
    });

    expect(response.total).toBe(1);
    expect(response.results.length).toBe(1);
    expect(response.results[0].product.name).toBe('V-OTA Resort & Spa Nha Trang Bay');
    expect(response.results[0].relevanceScore).toBe(0.92);
    expect(response.categoryCounts.hotel).toBe(1);
  });

  it('falls back to local search if backend fetch fails', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error (backend down)'));

    const response = await searchProductsApi('VinWonders');

    expect(response).toBeDefined();
    expect(response.results.length).toBeGreaterThan(0);
    expect(response.query).toBe('VinWonders');
  });
});
