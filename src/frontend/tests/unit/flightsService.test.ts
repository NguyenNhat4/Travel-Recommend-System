import { afterEach, describe, expect, it, vi } from 'vitest';
import { listRouteFlights, listRoutesTo } from '../../src/services/flights';

const originalFetch = global.fetch;
afterEach(() => { global.fetch = originalFetch; });

const product = (productId: string, level: string) => ({ productId, name: productId, taxonomy: 'flight', destination: 'Đà Nẵng', unitPrice: 1, currency: 'VND', priceUnit: 'PER_PERSON', available: true, attributes: { level } });

/** Backend giả trả `total` mục, chia trang theo `limit`/`offset` như thật. */
function backend(total: number, level = 'flight') {
  const calls: URL[] = [];
  global.fetch = vi.fn().mockImplementation(async (input: string) => {
    const url = new URL(input, 'http://x');
    calls.push(url);
    const limit = Number(url.searchParams.get('limit'));
    const offset = Number(url.searchParams.get('offset'));
    const results = Array.from({ length: Math.max(0, Math.min(limit, total - offset)) }, (_, i) => product(`p${offset + i}`, level));
    return new Response(JSON.stringify({ results, total, limit, offset }), { status: 200 });
  });
  return calls;
}

describe('listRouteFlights', () => {
  it('asks for the children of one route, cheapest first, and reads every page', async () => {
    const calls = backend(120);
    const flights = await listRouteFlights('route-1');
    expect(flights).toHaveLength(120);
    expect(calls.map((u) => u.searchParams.get('offset'))).toEqual(['0', '50', '100']);
    for (const url of calls) {
      expect(url.pathname).toBe('/api/v1/products');
      expect(url.searchParams.get('parentProductId')).toBe('route-1');
      expect(url.searchParams.get('sort')).toBe('price_asc');
      expect(url.searchParams.get('limit')).toBe('50');
    }
  });

  it('stops after one request when everything fits in a page', async () => {
    const calls = backend(3);
    expect(await listRouteFlights('route-1')).toHaveLength(3);
    expect(calls).toHaveLength(1);
  });

  it('does not loop forever when the backend reports a total it never delivers', async () => {
    global.fetch = vi.fn().mockImplementation(async () => new Response(JSON.stringify({
      results: Array.from({ length: 50 }, (_, i) => product(`p${i}`, 'flight')), total: 999999, limit: 50, offset: 0,
    }), { status: 200 }));
    await listRouteFlights('route-1');
    expect((global.fetch as ReturnType<typeof vi.fn>).mock.calls.length).toBe(10);
  });
});

describe('listRoutesTo', () => {
  it('filters flight products by destination and keeps only route-level ones', async () => {
    const calls = backend(2, 'route');
    expect(await listRoutesTo('Đà Nẵng')).toHaveLength(2);
    expect(calls[0].searchParams.get('taxonomy')).toBe('flight');
    expect(calls[0].searchParams.get('destination')).toBe('Đà Nẵng');
    expect(calls[0].searchParams.get('parentProductId')).toBeNull();

    backend(2, 'flight');
    expect(await listRoutesTo('Đà Nẵng')).toEqual([]);
  });
});
