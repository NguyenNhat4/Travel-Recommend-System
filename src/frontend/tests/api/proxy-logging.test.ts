import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GET } from '../../src/app/api/[...path]/route';
import { createAnonymousSession } from '../../src/services/server/bffSession';
import { MemorySessionStore, setSessionStoreForTests } from '../../src/services/server/sessionStore';

describe('BFF proxy logging', () => {
  let stdout: string[];

  beforeEach(() => {
    stdout = [];
    process.env.BACKEND_BASE_URL = 'http://127.0.0.1:8000';
    vi.spyOn(process.stdout, 'write').mockImplementation(((chunk: string | Uint8Array) => {
      stdout.push(String(chunk));
      return true;
    }) as typeof process.stdout.write);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    delete process.env.BACKEND_BASE_URL;
    setSessionStoreForTests(undefined);
  });

  async function call(requestId?: string) {
    const fetchMock = vi.fn(async () => new Response('{"items":[]}', { status: 200, headers: { 'content-type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);
    const store = new MemorySessionStore();
    setSessionStoreForTests(store);
    const ua = { 'user-agent': 'vitest' };
    const { sid, record } = await createAnonymousSession(new Request('http://localhost:3000/', { headers: ua }), store);
    const request = new Request('http://localhost:3000/api/v1/bookings/VOTA-1234?email=a@b.com', {
      headers: {
        ...ua, cookie: `vota_sid=${sid}; vota_csrf=${record.csrfToken}`, authorization: 'Bearer client-supplied-token',
        ...(requestId ? { 'x-request-id': requestId } : {}),
      },
    });
    const response = await GET(request, { params: Promise.resolve({ path: ['v1', 'bookings', 'VOTA-1234'] }) });
    return { fetchMock, response, sid, csrf: record.csrfToken };
  }

  const rows = () => stdout.join('').split('\n').filter(Boolean).map((l) => JSON.parse(l));

  it('ghi bff.proxy với route mẫu, không ghi cookie, authorization, sid, csrf hay query', async () => {
    const { sid, csrf } = await call('req-123');
    const proxyRow = rows().find((r) => r.event === 'bff.proxy');
    expect(proxyRow).toMatchObject({
      service: 'frontend', severity: 'INFO', request_id: 'req-123', method: 'GET',
      route: '/api/v1/bookings/{id}', status: 200, authenticated: false,
    });
    expect(typeof proxyRow.upstream_ms).toBe('number');
    const out = stdout.join('');
    for (const secret of [sid, csrf, 'client-supplied-token', 'a@b.com', 'VOTA-1234']) {
      expect(out, secret).not.toContain(secret);
    }
  });

  it('chuyển tiếp X-Request-ID xuống backend và sinh mới khi thiếu', async () => {
    const withId = await call('req-123');
    const [, init] = withId.fetchMock.mock.calls[0] as unknown as [URL, RequestInit];
    expect(new Headers(init.headers).get('x-request-id')).toBe('req-123');
    expect(withId.response.headers.get('x-request-id')).toBe('req-123');

    const generated = await call();
    const [, init2] = generated.fetchMock.mock.calls[0] as unknown as [URL, RequestInit];
    expect(new Headers(init2.headers).get('x-request-id')).toMatch(/^web-[0-9a-f]{12}$/);
  });

  it('ghi bff.csrf.rejected (WARNING) khi request ghi thiếu CSRF', async () => {
    vi.stubGlobal('fetch', vi.fn());
    const { POST } = await import('../../src/app/api/[...path]/route');
    const response = await POST(
      new Request('http://localhost:3000/api/v1/cart/items', { method: 'POST', headers: { origin: 'http://evil.example' }, body: '{}' }),
      { params: Promise.resolve({ path: ['v1', 'cart', 'items'] }) },
    );
    expect(response.status).toBe(403);
    expect(rows().find((r) => r.event === 'bff.csrf.rejected')).toMatchObject({ severity: 'WARNING', reason: 'origin' });
  });

  it('ghi bff.proxy.upstream_error (ERROR) khi backend không phản hồi', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('connect ECONNREFUSED postgresql://u:pw123@db/x'); }));
    const response = await GET(new Request('http://localhost:3000/api/v1/search'), { params: Promise.resolve({ path: ['v1', 'search'] }) });
    expect(response.status).toBe(502);
    const row = rows().find((r) => r.event === 'bff.proxy.upstream_error');
    expect(row).toMatchObject({ severity: 'ERROR', route: '/api/v1/search' });
    expect(stdout.join('')).not.toContain('pw123');
  });
});
