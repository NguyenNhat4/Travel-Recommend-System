import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fetchRecommendations } from '../../src/services/recsys';
import { ApiError } from '../../src/services/http';

describe('recsys service fetchRecommendations', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('calls /api/v1/recommendations and keeps name and price from the API (grounding)', async () => {
    const mockBackendResponse = {
      strategy: 'cross_vertical',
      destination: 'Nha Trang',
      nextVertical: 'attraction',
      recommendations: [
        {
          productId: 'nt-attraction-01',
          name: 'Vé Vui Chơi VinWonders Nha Trang',
          taxonomy: 'attraction',
          destination: 'Nha Trang',
          unitPrice: 750000,
          currency: 'VND',
          priceUnit: 'PER_PERSON',
          available: true,
          imageUrl: 'https://example.com/vinwonders.jpg',
          score: 0.95,
          rank: 1,
          because: [
            { productId: 'nt-hotel-01', productName: 'V-OTA Resort Nha Trang', event: 'purchase', daysAgo: 2, contribution: 0.75 },
          ],
        },
      ],
      diagnostics: { eventsUsed: 4, coldStart: false, excludedVerticals: ['hotel'] },
      generatedAt: '2026-09-21T10:00:00Z',
    };

    let requestedUrl = '';
    global.fetch = vi.fn().mockImplementation(async (input: RequestInfo | URL) => {
      requestedUrl = String(input);
      return new Response(JSON.stringify(mockBackendResponse), { status: 200 });
    });

    const result = await fetchRecommendations({ k: 4, destination: 'Nha Trang' });

    expect(requestedUrl).toContain('/api/v1/recommendations?');
    // Danh tính theo cookie phiên; không bao giờ gửi cdp_user_id (IDOR, auth §3.5).
    expect(requestedUrl).not.toContain('cdp_user_id');
    expect(requestedUrl).toContain('k=4');
    expect(requestedUrl).toContain('destination=Nha+Trang');

    expect(result.strategy).toBe('cross_vertical');
    expect(result.destination).toBe('Nha Trang');
    expect(result.nextVertical).toBe('attraction');
    expect(result.recommendations).toHaveLength(1);
    expect(result.recommendations[0].product).toMatchObject({
      id: 'nt-attraction-01', name: 'Vé Vui Chơi VinWonders Nha Trang', unitPrice: 750000,
    });
    expect(result.recommendations[0].because[0].productName).toBe('V-OTA Resort Nha Trang');
    expect(result.diagnostics.excludedVerticals).toEqual(['hotel']);
  });

  it('throws instead of inventing recommendations when the backend fails', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error (backend down)'));
    await expect(fetchRecommendations({ k: 4 })).rejects.toBeInstanceOf(ApiError);
  });

  it('surfaces the error envelope of a 5xx response', async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      error: { code: 'SEARCH_UNAVAILABLE', message: 'Chưa sẵn sàng', retryable: true, requestId: 'r-1' },
    }), { status: 503 }));
    await expect(fetchRecommendations()).rejects.toMatchObject({ code: 'SEARCH_UNAVAILABLE', retryable: true });
  });
});
