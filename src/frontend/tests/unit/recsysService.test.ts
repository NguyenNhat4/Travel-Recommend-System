import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  fetchRecommendations,
  PERSONA_CDP_USER_MAP,
} from '../../src/services/recsys';

describe('recsys service fetchRecommendations', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('maps persona IDs to CDP user IDs correctly', () => {
    expect(PERSONA_CDP_USER_MAP.P1).toBe('VP0000001');
    expect(PERSONA_CDP_USER_MAP.P2).toBe('VP0000002');
    expect(PERSONA_CDP_USER_MAP.P3).toBe('VP0000003');
    expect(PERSONA_CDP_USER_MAP.P4).toBe('VP0000004');
  });

  it('calls /api/v1/recommendations and parses backend response', async () => {
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
          imageUrl: 'https://example.com/vinwonders.jpg',
          score: 0.95,
          rank: 1,
          because: [
            {
              productId: 'nt-hotel-01',
              productName: 'V-OTA Resort Nha Trang',
              event: 'purchase',
              daysAgo: 2,
              contribution: 0.75,
            },
          ],
        },
      ],
      diagnostics: {
        eventsUsed: 4,
        coldStart: false,
        excludedVerticals: ['hotel'],
      },
      generatedAt: '2026-09-21T10:00:00Z',
    };

    let requestedUrl = '';
    global.fetch = vi.fn().mockImplementation(async (input: RequestInfo | URL) => {
      requestedUrl = String(input);
      return {
        ok: true,
        status: 200,
        json: async () => mockBackendResponse,
      } as Response;
    });

    const result = await fetchRecommendations({
      k: 4,
      destination: 'Nha Trang',
    });

    expect(requestedUrl).toContain('/api/v1/recommendations?');
    // Danh tính theo cookie phiên; không bao giờ gửi cdp_user_id (IDOR, auth §3.5).
    expect(requestedUrl).not.toContain('cdp_user_id');
    expect(requestedUrl).toContain('k=4');
    expect(requestedUrl).toContain('destination=Nha+Trang');

    expect(result.strategy).toBe('cross_vertical');
    expect(result.destination).toBe('Nha Trang');
    expect(result.nextVertical).toBe('attraction');
    expect(result.recommendations).toHaveLength(1);
    expect(result.recommendations[0].product.name).toBe('Vé Vui Chơi VinWonders Nha Trang (Cáp Treo Hai Chiều)');
    expect(result.recommendations[0].because).toHaveLength(1);
    expect(result.recommendations[0].because[0].productName).toBe('V-OTA Resort Nha Trang');
    expect(result.diagnostics.coldStart).toBe(false);
  });

  // Màn gợi ý là bằng chứng engine thật chạy: lỗi thì báo lỗi, không thay bằng gợi ý mô phỏng (frontend §4.1).
  it('throws instead of returning simulated recommendations when the backend fails', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error (backend down)'));
    await expect(fetchRecommendations({ k: 4 })).rejects.toThrow('backend down');

    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) } as Response);
    await expect(fetchRecommendations({ k: 4 })).rejects.toThrow('500');
  });
});
