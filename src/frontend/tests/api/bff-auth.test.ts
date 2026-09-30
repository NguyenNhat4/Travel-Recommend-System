/**
 * BFF auth (docs/spec/hop-dong-tich-hop-auth.md §4, §6, §7, §20.4). Route handler gọi thẳng với
 * Request Web chuẩn; FastAPI được giả bằng fetch mock, session store là bản in-memory.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GET as proxyGet, POST as proxyPost, PUT as proxyPut } from '../../src/app/api/[...path]/route';
import { GET as getSession } from '../../src/app/api/auth/session/route';
import { POST as login } from '../../src/app/api/auth/login/route';
import { POST as logout } from '../../src/app/api/auth/logout/route';
import { POST as register } from '../../src/app/api/auth/register/route';
import { MemorySessionStore, setSessionStoreForTests, type SessionRecord } from '../../src/services/server/sessionStore';

const ORIGIN = 'http://localhost:3000';
const UA = 'vitest-browser';
const USER = { userId: 'u-1', cdpUserId: 'VP0000001', email: 'minh.anh@example.com', fullName: 'Minh Anh' };

let store: MemorySessionStore;

function json(body: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json', ...headers } });
}

function cookiesOf(response: Response): Record<string, string> {
  const jar: Record<string, string> = {};
  for (const line of response.headers.getSetCookie()) {
    const [pair] = line.split(';');
    const [name, ...value] = pair.split('=');
    jar[name] = decodeURIComponent(value.join('='));
  }
  return jar;
}

function browser(url: string, init: { method?: string; sid?: string; csrf?: string | null; body?: unknown;
  headers?: Record<string, string>; origin?: string | null; ua?: string } = {}) {
  const headers: Record<string, string> = { 'user-agent': init.ua ?? UA, ...(init.headers ?? {}) };
  if (init.origin !== null) headers.origin = init.origin ?? ORIGIN;
  if (init.sid) headers.cookie = `vota_sid=${init.sid}; vota_csrf=${init.csrf ?? ''}`;
  if (init.csrf) headers['x-csrf-token'] = init.csrf;
  if (init.body !== undefined) headers['content-type'] = 'application/json';
  return new Request(`${ORIGIN}${url}`, {
    method: init.method ?? 'GET', headers, body: init.body === undefined ? undefined : JSON.stringify(init.body),
  });
}

const ctx = (path: string) => ({ params: Promise.resolve({ path: path.split('/').filter(Boolean) }) });

async function anonymous() {
  const response = await getSession(browser('/api/auth/session'));
  const jar = cookiesOf(response);
  return { sid: jar.vota_sid, csrf: jar.vota_csrf, response };
}

async function authenticated(expiresIn = 600) {
  const anon = await anonymous();
  const fetchMock = vi.fn(async () => json({
    state: 'authenticated', accessToken: 'access-1', refreshToken: 'rt_1', expiresIn, user: USER,
  }));
  vi.stubGlobal('fetch', fetchMock);
  const response = await login(browser('/api/auth/login', {
    method: 'POST', sid: anon.sid, csrf: anon.csrf, body: { email: USER.email, password: 'Demo@2026' },
  }));
  const jar = cookiesOf(response);
  vi.unstubAllGlobals();
  return { sid: jar.vota_sid, csrf: jar.vota_csrf, oldSid: anon.sid, response };
}

beforeEach(() => {
  store = new MemorySessionStore();
  setSessionStoreForTests(store);
  process.env.BACKEND_BASE_URL = 'http://127.0.0.1:8000';
  process.env.AUTH_SERVICE_TOKEN = 's'.repeat(40);
  process.env.ALLOWED_ORIGINS = ORIGIN;
});

afterEach(() => {
  vi.unstubAllGlobals();
  setSessionStoreForTests(undefined);
  delete process.env.ALLOWED_ORIGINS;
});

describe('GET /api/auth/session', () => {
  it('creates an anonymous session with HttpOnly sid and a readable CSRF cookie', async () => {
    const { response, sid, csrf } = await anonymous();
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body).toEqual({ state: 'anonymous', csrfToken: csrf });
    const [sidCookie, csrfCookie] = response.headers.getSetCookie();
    expect(sidCookie).toContain('HttpOnly');
    expect(sidCookie).toContain('SameSite=Lax');
    expect(csrfCookie).not.toContain('HttpOnly');
    expect(await store.get(sid)).toMatchObject({ state: 'anonymous', user: null, accessToken: null });
  });

  it('restores an authenticated session without ever returning tokens', async () => {
    const { sid } = await authenticated();
    const response = await getSession(browser('/api/auth/session', { sid }));
    const text = await response.text();
    expect(JSON.parse(text)).toMatchObject({ state: 'authenticated', user: USER });
    expect(text).not.toContain('access-1');
    expect(text).not.toContain('rt_1');
  });
});

describe('POST /api/auth/login', () => {
  it('asks FastAPI with the service token, rotates sid and keeps tokens server-side', async () => {
    const anon = await anonymous();
    const fetchMock = vi.fn(async (_url: URL, _init: RequestInit) => json({
      state: 'authenticated', accessToken: 'access-1', refreshToken: 'rt_1', expiresIn: 600, user: USER,
    }));
    vi.stubGlobal('fetch', fetchMock);
    const response = await login(browser('/api/auth/login', {
      method: 'POST', sid: anon.sid, csrf: anon.csrf, body: { email: USER.email, password: 'Demo@2026' },
    }));

    expect(response.status).toBe(200);
    const text = await response.text();
    expect(text).not.toContain('access-1');
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toBe('http://127.0.0.1:8000/api/v1/auth/session');
    expect(new Headers(init.headers).get('x-service-token')).toBe('s'.repeat(40));

    const jar = cookiesOf(response);
    expect(jar.vota_sid).not.toBe(anon.sid);       // chống session fixation
    expect(jar.vota_csrf).not.toBe(anon.csrf);     // CSRF xoay cùng sid
    expect(await store.get(anon.sid)).toBeNull();
    expect(await store.get(jar.vota_sid)).toMatchObject({ accessToken: 'access-1', refreshToken: 'rt_1' });
  });

  it('passes backend errors through, keeping Retry-After on 429', async () => {
    const anon = await anonymous();
    vi.stubGlobal('fetch', vi.fn(async () => json(
      { error: { code: 'TOO_MANY_ATTEMPTS', message: 'x', retryable: true, requestId: 'r' } }, 429, { 'retry-after': '900' },
    )));
    const response = await login(browser('/api/auth/login', {
      method: 'POST', sid: anon.sid, csrf: anon.csrf, body: { email: USER.email, password: 'bad' },
    }));
    expect(response.status).toBe(429);
    expect(response.headers.get('retry-after')).toBe('900');
    expect((await response.json()).error.code).toBe('TOO_MANY_ATTEMPTS');
  });

  it('rejects writes without the CSRF header or from a foreign origin', async () => {
    const anon = await anonymous();
    vi.stubGlobal('fetch', vi.fn());
    const noHeader = await login(browser('/api/auth/login', {
      method: 'POST', sid: anon.sid, body: { email: 'a', password: 'b' },
    }));
    expect(noHeader.status).toBe(403);
    expect((await noHeader.json()).error.code).toBe('CSRF_FAILED');
    const foreign = await login(browser('/api/auth/login', {
      method: 'POST', sid: anon.sid, csrf: anon.csrf, origin: 'https://evil.example', body: {},
    }));
    expect(foreign.status).toBe(403);
    const noOrigin = await login(browser('/api/auth/login', {
      method: 'POST', sid: anon.sid, csrf: anon.csrf, origin: null, body: {},
    }));
    expect(noOrigin.status).toBe(403);
    expect(fetch).not.toHaveBeenCalled();
  });

  it('switching account revokes the previous refresh token (§3.8 F)', async () => {
    const first = await authenticated();
    const fetchMock = vi.fn(async (url: URL) => String(url).endsWith('/revoke')
      ? new Response(null, { status: 204 })
      : json({ state: 'authenticated', accessToken: 'access-2', refreshToken: 'rt_2', expiresIn: 600,
               user: { ...USER, userId: 'u-2', cdpUserId: 'VP0000002' } }));
    vi.stubGlobal('fetch', fetchMock);
    await login(browser('/api/auth/login', {
      method: 'POST', sid: first.sid, csrf: first.csrf, body: { email: 'quoc.bao@example.com', password: 'Demo@2026' },
    }));
    const revoke = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/auth/session/revoke'));
    expect(revoke).toBeTruthy();
    expect(await store.get(first.sid)).toBeNull();
  });
});

describe('POST /api/auth/register', () => {
  it('creates the account through v1 register then opens a BFF session', async () => {
    const anon = await anonymous();
    const fetchMock = vi.fn(async (url: URL) => String(url).endsWith('/auth/register')
      ? json({ accessToken: 'v1', tokenType: 'Bearer', expiresIn: 600, user: USER }, 201)
      : json({ state: 'authenticated', accessToken: 'access-1', refreshToken: 'rt_1', expiresIn: 600, user: USER }));
    vi.stubGlobal('fetch', fetchMock);
    const response = await register(browser('/api/auth/register', {
      method: 'POST', sid: anon.sid, csrf: anon.csrf,
      body: { email: USER.email, password: 'ngua o chay tren de', fullName: 'Minh Anh' },
    }));
    expect(response.status).toBe(200);
    expect(fetchMock.mock.calls.map(([url]) => new URL(String(url)).pathname))
      .toEqual(['/api/v1/auth/register', '/api/v1/auth/session']);
  });
});

describe('POST /api/auth/logout', () => {
  it('clears cookies and the session even when the backend fails', async () => {
    const { sid, csrf } = await authenticated();
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('backend down'); }));
    const response = await logout(browser('/api/auth/logout', { method: 'POST', sid, csrf }));
    expect(response.status).toBe(204);
    expect(response.headers.getSetCookie().every((c) => c.includes('Max-Age=0'))).toBe(true);
    expect(await store.get(sid)).toBeNull();
  });
});

describe('catch-all proxy', () => {
  it('drops browser cookie/authorization, attaches the session bearer and echoes X-Request-ID', async () => {
    const { sid } = await authenticated();
    const fetchMock = vi.fn(async (_url: URL, _init: RequestInit) =>
      json({ strategy: 'personal' }, 200, { 'x-request-id': 'req-123' }));
    vi.stubGlobal('fetch', fetchMock);
    const response = await proxyGet(browser('/api/v1/recommendations?k=4', {
      sid, headers: { authorization: 'Bearer someone-elses-token', 'x-request-id': 'req-123' },
    }), ctx('v1/recommendations'));

    expect(response.status).toBe(200);
    expect(response.headers.get('x-request-id')).toBe('req-123');
    const headers = new Headers(fetchMock.mock.calls[0][1].headers);
    expect(headers.get('authorization')).toBe('Bearer access-1');
    expect(headers.get('cookie')).toBeNull();
    expect(headers.get('x-request-id')).toBe('req-123');
  });

  it('guests go through without Authorization', async () => {
    const fetchMock = vi.fn(async (_url: URL, _init: RequestInit) => json({ strategy: 'popular' }));
    vi.stubGlobal('fetch', fetchMock);
    const response = await proxyGet(browser('/api/v1/recommendations', {
      headers: { authorization: 'Bearer forged' },
    }), ctx('v1/recommendations'));
    expect(response.status).toBe(200);
    expect(new Headers(fetchMock.mock.calls[0][1].headers).get('authorization')).toBeNull();
  });

  it('browser abort is answered 499 without an error log; a real network failure stays 502', async () => {
    const errorLog = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const controller = new AbortController();
    vi.stubGlobal('fetch', vi.fn(async () => { controller.abort(); throw new DOMException('aborted', 'AbortError'); }));
    const aborted = await proxyGet(new Request(`${ORIGIN}/api/v1/recommendations?k=4`, {
      headers: { 'user-agent': UA }, signal: controller.signal,
    }), ctx('v1/recommendations'));
    expect(aborted.status).toBe(499);
    expect(errorLog).not.toHaveBeenCalled();

    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('fetch failed'); }));
    const down = await proxyGet(browser('/api/v1/recommendations?k=4'), ctx('v1/recommendations'));
    expect(down.status).toBe(502);
    expect(errorLog).toHaveBeenCalledTimes(1);
    errorLog.mockRestore();
  });

  it('write without X-CSRF-Token is 403 CSRF_FAILED and never reaches FastAPI', async () => {
    const { sid } = await authenticated();
    vi.stubGlobal('fetch', vi.fn());
    const response = await proxyPost(browser('/api/v1/search', { method: 'POST', sid, body: { query: 'x' } }),
      ctx('v1/search'));
    expect(response.status).toBe(403);
    expect((await response.json()).error.code).toBe('CSRF_FAILED');
    expect(fetch).not.toHaveBeenCalled();
  });

  it('a tampered or expired sid is 401 SESSION_EXPIRED, not a 500 and not a silent guest', async () => {
    vi.stubGlobal('fetch', vi.fn());
    const response = await proxyGet(browser('/api/v1/recommendations', { sid: 's_tampered' }), ctx('v1/recommendations'));
    expect(response.status).toBe(401);
    expect((await response.json()).error.code).toBe('SESSION_EXPIRED');
    expect(response.headers.getSetCookie().some((c) => c.startsWith('vota_sid=;'))).toBe(true);
    expect(fetch).not.toHaveBeenCalled();
  });

  it('a different User-Agent destroys the session (§3.8 H)', async () => {
    const { sid } = await authenticated();
    vi.stubGlobal('fetch', vi.fn());
    const response = await proxyGet(browser('/api/v1/recommendations', { sid, ua: 'other-browser' }), ctx('v1/recommendations'));
    expect(response.status).toBe(401);
    expect(await store.get(sid)).toBeNull();
  });

  it('refreshes a nearly expired token once, even for concurrent requests', async () => {
    const { sid } = await authenticated(30); // còn 30s < 60s
    const fetchMock = vi.fn(async (url: URL, _init?: RequestInit) => {
      if (String(url).endsWith('/auth/session/token')) {
        await new Promise((resolve) => setTimeout(resolve, 50));
        return json({ state: 'authenticated', accessToken: 'access-2', refreshToken: 'rt_2', expiresIn: 600, user: USER });
      }
      return json({ ok: true });
    });
    vi.stubGlobal('fetch', fetchMock);
    const responses = await Promise.all([1, 2, 3].map(() =>
      proxyGet(browser('/api/v1/recommendations', { sid }), ctx('v1/recommendations'))));
    expect(responses.map((r) => r.status)).toEqual([200, 200, 200]);
    const refreshCalls = fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/auth/session/token'));
    expect(refreshCalls).toHaveLength(1);
    const bearers = fetchMock.mock.calls.filter(([url]) => String(url).includes('/recommendations'))
      .map(([, init]) => new Headers((init as RequestInit).headers).get('authorization'));
    expect(bearers).toEqual(['Bearer access-2', 'Bearer access-2', 'Bearer access-2']);
    expect((await store.get(sid)) as SessionRecord).toMatchObject({ refreshToken: 'rt_2' });
  });

  it('refresh rejected by FastAPI ends the session with 401 SESSION_EXPIRED', async () => {
    const { sid } = await authenticated(10);
    vi.stubGlobal('fetch', vi.fn(async () => json({ error: { code: 'INVALID_TOKEN' } }, 401)));
    const response = await proxyGet(browser('/api/v1/recommendations', { sid }), ctx('v1/recommendations'));
    expect(response.status).toBe(401);
    expect((await response.json()).error.code).toBe('SESSION_EXPIRED');
    expect(await store.get(sid)).toBeNull();
  });

  it('password change keeps this session under a new sid and kills the others (§3.8 J)', async () => {
    const current = await authenticated();
    const other = await authenticated();
    vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 204 })));
    const response = await proxyPut(browser('/api/v1/auth/password', {
      method: 'PUT', sid: current.sid, csrf: current.csrf, body: { currentPassword: 'a', newPassword: 'b'.repeat(8) },
    }), ctx('v1/auth/password'));
    expect(response.status).toBe(204);
    const jar = cookiesOf(response);
    expect(jar.vota_sid).not.toBe(current.sid);
    expect(await store.get(jar.vota_sid)).toMatchObject({ state: 'authenticated' });
    expect(await store.get(current.sid)).toBeNull();
    expect(await store.get(other.sid)).toBeNull();
  });
});

describe('client code never stores tokens (§20.4)', () => {
  it('no file under src/ touches localStorage/sessionStorage with a token', () => {
    const offenders: string[] = [];
    const walk = (dir: string) => {
      for (const name of readdirSync(dir)) {
        const path = join(dir, name);
        if (statSync(path).isDirectory()) walk(path);
        else if (/\.(ts|tsx)$/.test(name)) {
          for (const line of readFileSync(path, 'utf8').split('\n')) {
            if (/^\s*(\*|\/\/|\/\*)/.test(line)) continue; // bỏ qua chú thích
            if (/(localStorage|sessionStorage)/.test(line) && /token|jwt|session\b|authorization/i.test(line)) {
              offenders.push(`${path}: ${line.trim()}`);
            }
          }
        }
      }
    };
    walk(join(__dirname, '../../src'));
    expect(offenders).toEqual([]);
  });
});
