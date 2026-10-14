import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  PREVIEW_LIMIT, SEARCH_GROUPS, TAB_GROUPS, parseGroupParam, searchCacheKey, searchGroupApi, searchOverviewApi, searchProductsApi,
  shelfCacheKey, sortItems,
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
    expect(response.topScore).toBe(0.92);
    expect(response.isWeakMatch).toBe(false);
  });

  it('sends the price and star filters to the API instead of filtering the page', async () => {
    const item = (productId: string, unitPrice: number | null) => ({
      productId, name: productId, taxonomy: 'hotel', destination: 'Nha Trang', unitPrice, currency: 'VND', available: true, score: 0.9,
    });
    global.fetch = vi.fn().mockImplementation(async () => new Response(JSON.stringify({
      results: [item('dear', 9_000_000), item('free', null)], total: 2, topScore: 0.9,
    }), { status: 200 }));

    const filtered = await searchProductsApi('x', { taxonomy: 'hotel', minPrice: 100, maxPrice: 2_000_000, minStarRating: 4 });
    const body = JSON.parse(vi.mocked(global.fetch).mock.calls[0][1]!.body as string);
    expect(body).toMatchObject({ priceMin: 100, priceMax: 2_000_000, starRatingMin: 4 });
    // Backend đã lọc: trang giữ nguyên những gì nó trả, total là số của backend.
    expect(filtered.results.map((r) => r.product.id)).toEqual(['dear', 'free']);
    expect(filtered.total).toBe(2);

    await searchProductsApi('x', { taxonomy: 'hotel' });
    const plain = JSON.parse(vi.mocked(global.fetch).mock.calls[1][1]!.body as string);
    expect(plain).not.toHaveProperty('priceMin');
    expect(plain).not.toHaveProperty('priceMax');
    expect(plain).not.toHaveProperty('starRatingMin');
  });

  it('flags a weak match only when topScore is below the threshold, never when it is null', async () => {
    const respond = (topScore: number | null) => {
      global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ results: [], total: 0, topScore }), { status: 200 }));
    };
    respond(0.2);
    expect((await searchProductsApi('x')).isWeakMatch).toBe(true);
    respond(null);
    const empty = await searchProductsApi('x');
    expect(empty.isWeakMatch).toBe(false);
    expect(empty.topScore).toBeNull();
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

  it('narrows a group to one taxonomy (Sân golf tab at /experiences) with one request', async () => {
    global.fetch = vi.fn().mockImplementation(async () => new Response(JSON.stringify({ results: [item('golf-1', 'golf', 100, 0.9)], total: 3 }), { status: 200 }));
    const page = await searchGroupApi('sân golf', 'exp', { limit: 20, taxonomy: 'golf' });
    expect(bodies().map((b) => b.taxonomy)).toEqual(['golf']);
    expect(page.total).toBe(3);
    // Loại không thuộc nhóm thì bỏ qua và chạy cả nhóm.
    await searchGroupApi('x', 'stay', { limit: 20, taxonomy: 'golf' });
    expect(bodies().slice(1).map((b) => b.taxonomy)).toEqual(['hotel']);
  });

  it('sends guests as travelContext.guests, and only when given', async () => {
    global.fetch = vi.fn().mockImplementation(async () => new Response(JSON.stringify({ results: [item('h', 'hotel', 1, 0.9)], total: 1 }), { status: 200 }));
    await searchGroupApi('x', 'stay', { limit: 20, guests: { adults: 2, children: 1 } });
    expect(bodies()[0]).toMatchObject({ travelContext: { guests: { adults: 2, children: 1 } } });
    await searchGroupApi('x', 'stay', { limit: 20 });
    expect(bodies()[1]).not.toHaveProperty('travelContext');
  });

  it('sends the stay as travelContext dates, with or without guests, omitting an absent checkOut', async () => {
    global.fetch = vi.fn().mockImplementation(async () => new Response(JSON.stringify({ results: [item('h', 'hotel', 1, 0.9)], total: 1 }), { status: 200 }));
    await searchGroupApi('x', 'stay', { limit: 20, stay: { checkIn: '2026-10-10', checkOut: '2026-10-12' }, guests: { adults: 2, children: 0 } });
    expect(bodies()[0]).toMatchObject({ travelContext: { checkIn: '2026-10-10', checkOut: '2026-10-12', guests: { adults: 2, children: 0 } } });
    await searchGroupApi('x', 'exp', { limit: 20, taxonomy: 'golf', stay: { checkIn: '2026-10-10' } });
    expect((bodies()[1] as { travelContext: Record<string, unknown> }).travelContext).toEqual({ checkIn: '2026-10-10' });
  });

  it('reports hasMore false once the offset reaches the total', async () => {
    global.fetch = vi.fn().mockImplementation(async () => new Response(JSON.stringify({ results: [item('h', 'hotel', 1, 0.9)], total: 7 }), { status: 200 }));
    expect((await searchGroupApi('x', 'stay', { limit: 6, offset: 0 })).hasMore).toBe(true);
    expect((await searchGroupApi('x', 'stay', { limit: 6, offset: 6 })).hasMore).toBe(false);
  });

  it('passes the price and star filters of a group to every request of the group', async () => {
    global.fetch = vi.fn().mockImplementation(async () => new Response(JSON.stringify({ results: [], total: 0 }), { status: 200 }));
    await searchGroupApi('x', 'stay', { limit: 20, maxPrice: 2_000_000, minStarRating: 4 });
    expect(bodies()[0]).toMatchObject({ taxonomy: 'hotel', priceMax: 2_000_000, starRatingMin: 4 });
    expect(bodies()[0]).not.toHaveProperty('priceMin');
  });

  it('keeps the best topScore of the group, null when every request is empty', async () => {
    global.fetch = vi.fn().mockImplementation(async (_url, init) => {
      const { taxonomy } = JSON.parse((init as RequestInit).body as string);
      const topScore = taxonomy === 'golf' ? null : 0.8;
      return new Response(JSON.stringify({ results: [], total: 0, topScore }), { status: 200 });
    });
    expect((await searchGroupApi('x', 'exp', { limit: 6 })).topScore).toBe(0.8);
    expect((await searchGroupApi('x', 'exp', { limit: 6, taxonomy: 'golf' })).topScore).toBeNull();
  });

  it('counts tabs from the shelf requests (one per taxonomy, never an unfiltered one), so tab = row = "Xem thêm"', async () => {
    // facets của một request không lọc taxonomy nhỏ hơn total của từng loại (suất vớt BM25 dùng chung): không được dùng.
    const totals: Record<string, number> = { hotel: 13, attraction: 11, golf: 1, combo: 9 };
    global.fetch = vi.fn().mockImplementation(async (_url, init) => {
      const { taxonomy } = JSON.parse((init as RequestInit).body as string);
      return new Response(JSON.stringify({
        results: [item(`${taxonomy}-1`, taxonomy, 1, 0.9)], total: totals[taxonomy], topScore: taxonomy === 'combo' ? 0.2 : 0.9,
        facets: { taxonomy: { [taxonomy]: totals[taxonomy] }, destination: {} },
      }), { status: 200 });
    });
    const keys: string[] = [];
    const overview = await searchOverviewApi('Nha Trang', null, (key, fetcher) => { keys.push(key); return fetcher(); });

    expect(overview.counts).toEqual({ stay: 13, exp: 12, more: 9 });
    expect(overview.total).toBe(34);
    expect(overview.isWeakMatch).toBe(false);   // topScore cao nhất của các nhóm (0.9), không phải của nhóm yếu nhất
    expect(bodies().map((b) => b.taxonomy).sort()).toEqual(['attraction', 'combo', 'golf', 'hotel']);
    expect(bodies().every((b) => b.limit === PREVIEW_LIMIT && b.offset === 0)).toBe(true);
    // Cùng khóa bộ đệm với hàng của tab "Tất cả", nên hàng đọc lại kết quả thay vì gọi lần nữa.
    expect(keys).toEqual(TAB_GROUPS.map((group) => shelfCacheKey('Nha Trang', null, group)));
  });

  it('sorts loaded items by price, keeping unpriced ones last; relevance keeps the backend order', () => {
    const make = (id: string, price: number | null) => ({
      product: { id, unitPrice: price, attributes: {} }, relevanceScore: 0, matchTags: [],
    }) as never;
    const items = [make('mid', 500), make('none', null), make('low', 100), make('high', 900)];
    expect(sortItems(items, 'price_asc').map((r) => r.product.id)).toEqual(['low', 'mid', 'high', 'none']);
    expect(sortItems(items, 'price_desc').map((r) => r.product.id)).toEqual(['high', 'mid', 'low', 'none']);
    expect(sortItems(items, 'relevance').map((r) => r.product.id)).toEqual(['mid', 'none', 'low', 'high']);
  });

  it('builds a cache key that separates group, limit and destination', () => {
    const a = searchCacheKey('group', 'Nha Trang ', null, 'stay', 6, 0);
    expect(a).toBe(searchCacheKey('group', 'nha trang', undefined, 'stay', 6, 0));
    expect(a).not.toBe(searchCacheKey('group', 'nha trang', null, 'stay', 20, 0));
    expect(a).not.toBe(searchCacheKey('group', 'nha trang', 'Phú Quốc', 'stay', 6, 0));
    const golf = searchCacheKey('group', 'nha trang', null, 'exp', 20, 0, 'golf');
    expect(golf).not.toBe(searchCacheKey('group', 'nha trang', null, 'exp', 20, 0, 'attraction'));
    expect(golf).not.toBe(searchCacheKey('group', 'nha trang', null, 'exp', 20, 0));
    const dated = searchCacheKey('group', 'x', null, 'stay', 20, 0, 'hotel', undefined, { checkIn: '2026-10-10', checkOut: '2026-10-12' });
    expect(dated).not.toBe(searchCacheKey('group', 'x', null, 'stay', 20, 0, 'hotel', undefined, { checkIn: '2026-10-11', checkOut: '2026-10-12' }));
    expect(dated).not.toBe(searchCacheKey('group', 'x', null, 'stay', 20, 0, 'hotel'));
    const two = searchCacheKey('group', 'x', null, 'stay', 20, 0, 'hotel', { adults: 2, children: 0 });
    expect(two).not.toBe(searchCacheKey('group', 'x', null, 'stay', 20, 0, 'hotel', { adults: 3, children: 0 }));
    expect(two).not.toBe(searchCacheKey('group', 'x', null, 'stay', 20, 0, 'hotel'));
    const star = searchCacheKey('group', 'x', null, 'stay', 20, 0, undefined, undefined, undefined, { minStarRating: 4 });
    expect(star).not.toBe(searchCacheKey('group', 'x', null, 'stay', 20, 0));
    expect(star).not.toBe(searchCacheKey('group', 'x', null, 'stay', 20, 0, undefined, undefined, undefined, { minStarRating: 5 }));
    expect(star).not.toBe(searchCacheKey('group', 'x', null, 'stay', 20, 0, undefined, undefined, undefined, { maxPrice: 4 }));
    expect(searchCacheKey('group', 'x', null, 'stay', 20, 0, undefined, undefined, undefined, {})).toBe(searchCacheKey('group', 'x', null, 'stay', 20, 0));
    expect(shelfCacheKey('x', null, 'stay')).toBe(searchCacheKey('group', 'x', null, 'stay', PREVIEW_LIMIT, 0));
  });
});

describe('weak match rule with backgroundScore (contract 1.30.0)', () => {
  const originalFetch = global.fetch;
  afterEach(() => { global.fetch = originalFetch; });

  it('applies margin + ceiling only when F is large enough and not in filter-only mode', async () => {
    const { isWeakMatch } = await import('../../src/services/search');
    expect(isWeakMatch(0.86, 0.84, 200)).toBe(true);          // top chỉ nhỉnh hơn nền, dưới trần
    expect(isWeakMatch(0.91, 0.89, 200)).toBe(false);         // trên trần 0.88
    expect(isWeakMatch(0.86, 0.85, 3)).toBe(false);           // điểm đến nhỏ: nền ≈ top, không gắn nhãn
    expect(isWeakMatch(0.86, 0.84, 200, true)).toBe(false);   // chỉ-filter
    expect(isWeakMatch(0.86, null, 200)).toBe(false);         // backend không phát nền → luật cũ
    expect(isWeakMatch(null, 0.5, 200)).toBe(false);
  });

  it('maps backgroundScore, filteredCount and queryPlan.unexplained', async () => {
    global.fetch = vi.fn().mockImplementation(async () => new Response(JSON.stringify({
      results: [], total: 0, topScore: null, backgroundScore: null,
      diagnostics: { filteredCount: 40, queryPlan: { emptyReason: 'unexplained', unexplained: ['Nguyễn Khắc Tiệp'] } },
    }), { status: 200 }));
    const r = await searchProductsApi('Nguyễn Khắc Tiệp');
    expect(r.unexplained).toEqual(['Nguyễn Khắc Tiệp']);
    expect(r.isWeakMatch).toBe(false);
    const overview = await searchOverviewApi('Nguyễn Khắc Tiệp');
    expect(overview.unexplained).toEqual(['Nguyễn Khắc Tiệp']);
  });
});
