/**
 * BFF cho giỏ và đơn nháp của khách chưa đăng nhập (docs/spec/booking/dat-truc-tiep-theo-don-nhap.md §8.1, §8.4).
 * Route handler gọi thẳng với Request Web chuẩn; FastAPI được giả bằng fetch mock, session store là bản in-memory.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GET as proxyGet, POST as proxyPost } from '../../src/app/api/[...path]/route';
import { GET as getSession } from '../../src/app/api/auth/session/route';
import { POST as login } from '../../src/app/api/auth/login/route';
import { MemorySessionStore, setSessionStoreForTests } from '../../src/services/server/sessionStore';

const ORIGIN = 'http://localhost:3000';
const UA = 'vitest-browser';
const SERVICE = 's'.repeat(40);
const GUEST = `g_${'a'.repeat(22)}`;
const USER = { userId: 'u-1', cdpUserId: 'VP0000001', email: 'minh.anh@example.com', fullName: 'Minh Anh' };

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });
}

function cookieLines(response: Response) {
  return response.headers.getSetCookie();
}

function jarOf(response: Response): Record<string, string> {
  const jar: Record<string, string> = {};
  for (const line of cookieLines(response)) {
    const [name, ...value] = line.split(';')[0].split('=');
    jar[name] = decodeURIComponent(value.join('='));
  }
  return jar;
}

function browser(url: string, init: { method?: string; sid?: string; csrf?: string; guest?: string; body?: unknown;
  headers?: Record<string, string> } = {}) {
  const headers: Record<string, string> = { 'user-agent': UA, origin: ORIGIN, ...(init.headers ?? {}) };
  const cookies = [
    init.sid ? `vota_sid=${init.sid}` : null, init.csrf ? `vota_csrf=${init.csrf}` : null,
    init.guest ? `vota_guest=${init.guest}` : null,
  ].filter(Boolean);
  if (cookies.length) headers.cookie = cookies.join('; ');
  if (init.csrf) headers['x-csrf-token'] = init.csrf;
  if (init.body !== undefined) headers['content-type'] = 'application/json';
  return new Request(`${ORIGIN}${url}`, {
    method: init.method ?? 'GET', headers, body: init.body === undefined ? undefined : JSON.stringify(init.body),
  });
}

const ctx = (path: string) => ({ params: Promise.resolve({ path: path.split('/').filter(Boolean) }) });

async function anonymous() {
  const jar = jarOf(await getSession(browser('/api/auth/session')));
  return { sid: jar.vota_sid, csrf: jar.vota_csrf };
}

async function authenticated() {
  const anon = await anonymous();
  vi.stubGlobal('fetch', vi.fn(async () => json({
    state: 'authenticated', accessToken: 'access-1', refreshToken: 'rt_1', expiresIn: 600, user: USER,
  })));
  const jar = jarOf(await login(browser('/api/auth/login', {
    method: 'POST', sid: anon.sid, csrf: anon.csrf, body: { email: USER.email, password: 'Demo@2026' },
  })));
  vi.unstubAllGlobals();
  return { sid: jar.vota_sid, csrf: jar.vota_csrf };
}

/** fetch giả: ghi lại mọi lời gọi tới FastAPI; `merge` quyết định phản hồi của endpoint gộp. */
function backend(merge: () => Response = () => json({ mergedCartItems: 1, skippedDuplicates: 0, mergedDrafts: 0 })) {
  const calls: Array<{ url: string; method: string; headers: Headers; body: string | null }> = [];
  vi.stubGlobal('fetch', vi.fn(async (url: URL, init: RequestInit) => {
    const body = typeof init.body === 'string' ? init.body
      : init.body ? new TextDecoder().decode(init.body as ArrayBuffer) : null;
    calls.push({ url: String(url), method: String(init.method), headers: new Headers(init.headers), body });
    return String(url).endsWith('/guest-bookings/merge') ? merge() : json({ items: [] });
  }));
  return calls;
}

beforeEach(() => {
  setSessionStoreForTests(new MemorySessionStore());
  process.env.BACKEND_BASE_URL = 'http://127.0.0.1:8000';
  process.env.AUTH_SERVICE_TOKEN = SERVICE;
  process.env.ALLOWED_ORIGINS = ORIGIN;
});

afterEach(() => {
  vi.unstubAllGlobals();
  setSessionStoreForTests(undefined);
  delete process.env.ALLOWED_ORIGINS;
  delete process.env.GUEST_BOOKING_TTL_DAYS;
});

describe('khách chưa đăng nhập', () => {
  it('phát cookie vota_guest và chuyển mã khách cho FastAPI kèm service token, không kèm Authorization', async () => {
    const anon = await anonymous();
    const calls = backend();
    const response = await proxyGet(browser('/api/v1/cart', { sid: anon.sid }), ctx('v1/cart'));

    expect(response.status).toBe(200);
    const sent = calls[0].headers;
    expect(sent.get('x-service-token')).toBe(SERVICE);
    expect(sent.get('x-guest-id')).toMatch(/^g_[A-Za-z0-9_-]{22}$/);
    expect(sent.get('authorization')).toBeNull();
    expect(sent.get('cookie')).toBeNull();
    const [line] = cookieLines(response);
    expect(line).toContain(`vota_guest=${sent.get('x-guest-id')}`);
    expect(line).toContain('HttpOnly');
    expect(line).toContain('SameSite=Lax');
    expect(line).toContain('Max-Age=259200');                 // 3 ngày
  });

  it('dùng lại mã khách đã có; GET không đặt lại cookie, request ghi thì đặt lại hạn', async () => {
    const anon = await anonymous();
    const calls = backend();
    const read = await proxyGet(browser('/api/v1/booking-drafts/d-1', { sid: anon.sid, guest: GUEST }),
      ctx('v1/booking-drafts/d-1'));
    expect(calls[0].headers.get('x-guest-id')).toBe(GUEST);
    expect(cookieLines(read)).toEqual([]);

    const write = await proxyPost(browser('/api/v1/cart/items', {
      method: 'POST', sid: anon.sid, csrf: anon.csrf, guest: GUEST, body: { productId: 'p', usingDate: '2026-10-15', quantity: 1 },
    }), ctx('v1/cart/items'));
    expect(calls[1].headers.get('x-guest-id')).toBe(GUEST);
    expect(cookieLines(write)[0]).toContain(`vota_guest=${GUEST}`);
  });

  it('bỏ header mã khách và service token do trình duyệt tự đặt, và cookie sai định dạng', async () => {
    const anon = await anonymous();
    const calls = backend();
    await proxyGet(browser('/api/v1/cart', {
      sid: anon.sid, guest: 'VP0000001', headers: { 'x-guest-id': GUEST, 'x-service-token': 'gia-mao' },
    }), ctx('v1/cart'));
    expect(calls[0].headers.get('x-service-token')).toBe(SERVICE);
    expect(calls[0].headers.get('x-guest-id')).not.toBe(GUEST);          // không lấy từ header của trình duyệt
    expect(calls[0].headers.get('x-guest-id')).not.toBe('VP0000001');    // cookie sai định dạng: phát mã mới

    // Ngoài giỏ và đơn nháp, khách không được gắn mã khách hay service token (đơn luôn cần đăng nhập).
    await proxyGet(browser('/api/v1/products', { sid: anon.sid, guest: GUEST, headers: { 'x-guest-id': GUEST } }),
      ctx('v1/products'));
    await proxyGet(browser('/api/v1/bookings/VOTA-20260916-AB12', { sid: anon.sid, guest: GUEST }),
      ctx('v1/bookings/VOTA-20260916-AB12'));
    for (const call of calls.slice(1)) {
      expect(call.headers.get('x-guest-id')).toBeNull();
      expect(call.headers.get('x-service-token')).toBeNull();
    }
  });

  it('không cho trình duyệt gọi endpoint gộp nội bộ', async () => {
    const anon = await anonymous();
    const calls = backend();
    const response = await proxyPost(browser('/api/v1/guest-bookings/merge', {
      method: 'POST', sid: anon.sid, csrf: anon.csrf, body: { guestId: GUEST },
    }), ctx('v1/guest-bookings/merge'));
    expect(response.status).toBe(404);
    expect(calls).toEqual([]);
  });
});

describe('đã đăng nhập mà còn cookie khách', () => {
  it('gộp trước rồi mới chuyển tiếp request, và xoá cookie khách', async () => {
    const auth = await authenticated();
    const calls = backend();
    const response = await proxyGet(browser('/api/v1/cart', { sid: auth.sid, guest: GUEST }), ctx('v1/cart'));

    expect(calls.map((c) => c.url)).toEqual([
      'http://127.0.0.1:8000/api/v1/guest-bookings/merge', 'http://127.0.0.1:8000/api/v1/cart',
    ]);
    const merge = calls[0];
    expect(merge.method).toBe('POST');
    expect(merge.headers.get('x-service-token')).toBe(SERVICE);
    expect(merge.headers.get('authorization')).toBe('Bearer access-1');
    expect(JSON.parse(merge.body ?? '{}')).toEqual({ guestId: GUEST });
    expect(calls[1].headers.get('authorization')).toBe('Bearer access-1');
    expect(calls[1].headers.get('x-guest-id')).toBeNull();   // đã có danh tính: không gửi mã khách
    expect(cookieLines(response)[0]).toMatch(/^vota_guest=;.*Max-Age=0/);
  });

  it('gộp cả khi request đầu tiên là thanh toán', async () => {
    const auth = await authenticated();
    const calls = backend();
    await proxyPost(browser('/api/v1/bookings', {
      method: 'POST', sid: auth.sid, csrf: auth.csrf, guest: GUEST, body: { draftId: 'd-1', contact: {}, itemDetails: [] },
    }), ctx('v1/bookings'));
    expect(calls.map((c) => c.url.replace('http://127.0.0.1:8000/api/v1/', ''))).toEqual(['guest-bookings/merge', 'bookings']);
  });

  it('Backend lỗi khi gộp thì giữ cookie để lần sau thử lại và vẫn chuyển tiếp request', async () => {
    const auth = await authenticated();
    const calls = backend(() => json({ error: { code: 'INTERNAL_ERROR', message: 'x', retryable: true, requestId: 'r' } }, 503));
    const response = await proxyGet(browser('/api/v1/cart', { sid: auth.sid, guest: GUEST }), ctx('v1/cart'));
    expect(response.status).toBe(200);
    expect(calls).toHaveLength(2);
    expect(cookieLines(response)).toEqual([]);
  });

  it('không gọi gộp khi không có cookie khách hoặc request không thuộc đặt chỗ', async () => {
    const auth = await authenticated();
    const calls = backend();
    await proxyGet(browser('/api/v1/cart', { sid: auth.sid }), ctx('v1/cart'));
    await proxyGet(browser('/api/v1/products', { sid: auth.sid, guest: GUEST }), ctx('v1/products'));
    expect(calls.map((c) => c.url.replace('http://127.0.0.1:8000/api/v1/', ''))).toEqual(['cart', 'products']);
  });
});
