import { afterEach, describe, expect, it, vi } from 'vitest';
import { listDestinations } from '../../src/services/destinations';

describe('destination service', () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('loads destination options from the catalog route', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        destinations: [
          { destination: 'Hội An', productCount: 12 },
          { destination: 'Nha Trang', productCount: 34 },
        ],
      }),
    });

    await expect(listDestinations()).resolves.toEqual([
      { destination: 'Hội An', productCount: 12 },
      { destination: 'Nha Trang', productCount: 34 },
    ]);

    const [url, init] = vi.mocked(global.fetch).mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/destinations');
    expect(init.method).toBe('GET');
    expect(init.credentials).toBe('same-origin');
    expect(init.cache).toBe('no-store');
  });

  it('rejects a malformed response instead of inventing fallback destinations', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ destinations: ['Nha Trang'] }),
    });

    await expect(listDestinations()).rejects.toThrow('Danh sách điểm đến không hợp lệ');
  });
});
