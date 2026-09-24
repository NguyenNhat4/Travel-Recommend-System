import { afterEach, describe, expect, it, vi } from 'vitest';
import propertyFixture from '../../../shared/mocks/catalog/getProduct.200-property.json';
import variantsFixture from '../../../shared/mocks/catalog/listProducts.200-variants.json';
import notFoundFixture from '../../../shared/mocks/catalog/getProduct.404-not-found.json';
import {
  getProduct, hasVariants, listVariants, productFromApi, trackProductView,
} from '../../src/services/catalog';

const originalFetch = global.fetch;
afterEach(() => { global.fetch = originalFetch; });

function respond(body: unknown, status = 200) {
  global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status }));
  return global.fetch as ReturnType<typeof vi.fn>;
}

describe('productFromApi', () => {
  it('keeps API name/price and reads location from catalog attributes', () => {
    const product = productFromApi({
      productId: 'p1', name: 'Canvas Danang Beach Hotel', taxonomy: 'hotel', destination: 'Đà Nẵng',
      unitPrice: 1187297, currency: 'VND', priceUnit: 'PER_NIGHT', available: true, imageUrl: null,
      rating: 4.2, reviewCount: 1206,
      attributes: { level: 'property', latitude: 16.05, longitude: 108.24, address: '12 Võ Nguyên Giáp' },
    } as any);
    expect(product).toMatchObject({
      id: 'p1', name: 'Canvas Danang Beach Hotel', unitPrice: 1187297, level: 'property',
      coordinates: { lat: 16.05, lng: 108.24 }, address: '12 Võ Nguyên Giáp',
      aggregateRating: { score: 4.2, count: 1206 }, imageUrl: '/placeholders/hotel.svg',
    });
    expect(hasVariants(product)).toBe(true);
  });

  it('keeps a missing price as null, never 0', () => {
    const product = productFromApi({ ...(variantsFixture.results[0] as any), unitPrice: null });
    expect(product.unitPrice).toBeNull();
    expect(product.coordinates).toBeUndefined();
    expect(hasVariants(product)).toBe(false);
  });
});

describe('catalog API calls', () => {
  it('reads a product detail with its variant summary', async () => {
    const fetchMock = respond(propertyFixture);
    const detail = await getProduct('nt-h-10');
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/products/nt-h-10');
    expect(detail.variantSummary?.count).toBe(2);
  });

  it('lists the rooms of a property, cheapest first', async () => {
    const fetchMock = respond(variantsFixture);
    const page = await listVariants('nt-h-10');
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/products?parentProductId=nt-h-10&sort=price_asc&limit=50');
    expect(page.results.map((r) => r.productId)).toEqual(['nt-h-10-r1', 'nt-h-10-r2']);
  });

  it('turns 404 into PRODUCT_NOT_FOUND', async () => {
    respond(notFoundFixture, 404);
    await expect(getProduct('nt-h-99')).rejects.toMatchObject({ code: 'PRODUCT_NOT_FOUND', status: 404 });
  });

  it('posts product_view and swallows every error', async () => {
    const fetchMock = respond({}, 202);
    await trackProductView('nt-h-10');
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/events');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body as string)).toEqual({ eventName: 'product_view', productId: 'nt-h-10' });

    global.fetch = vi.fn().mockRejectedValue(new Error('offline'));
    await expect(trackProductView('nt-h-10')).resolves.toBeUndefined();
  });
});
