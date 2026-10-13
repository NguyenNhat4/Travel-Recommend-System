import { afterEach, describe, expect, it, vi } from 'vitest';
import { GET } from '../../src/app/api/[...path]/route';
import { MemorySessionStore, setSessionStoreForTests } from '../../src/services/server/sessionStore';

// Trình duyệt chỉ thấy Cache-Control của danh mục nếu BFF chuyển tiếp nguyên header từ backend.
describe('BFF giữ Cache-Control của danh mục', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    delete process.env.BACKEND_BASE_URL;
    setSessionStoreForTests(undefined);
  });

  it('chuyển nguyên Cache-Control của GET /products từ backend ra trình duyệt', async () => {
    process.env.BACKEND_BASE_URL = 'http://127.0.0.1:8000';
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{"results":[],"total":0}', {
      status: 200,
      headers: { 'content-type': 'application/json', 'cache-control': 'public, max-age=60, s-maxage=300' },
    })));
    setSessionStoreForTests(new MemorySessionStore());

    const request = new Request('http://localhost:3000/api/v1/products?sort=popular&limit=5', {
      headers: { 'user-agent': 'vitest' },
    });
    const response = await GET(request, { params: Promise.resolve({ path: ['v1', 'products'] }) });

    expect(response.status).toBe(200);
    expect(response.headers.get('cache-control')).toBe('public, max-age=60, s-maxage=300');
  });
});
