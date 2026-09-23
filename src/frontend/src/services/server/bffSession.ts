/**
 * Phiên BFF (docs/spec/hop-dong-tich-hop-auth.md §3.3–§3.4, §3.8, §6, §7). CHỈ chạy phía server.
 *
 * Trình duyệt chỉ giữ hai cookie: `vota_sid` (HttpOnly, con trỏ tới bản ghi Redis) và `vota_csrf`
 * (đọc được, cho double-submit). Access/refresh token chỉ nằm trong Redis và trên dây BFF → FastAPI.
 * BFF không ký token: nó xin token từ FastAPI bằng X-Service-Token.
 */
import { createHash, randomBytes, timingSafeEqual } from 'node:crypto';
import { getSessionStore, type SessionRecord, type SessionStore, type SessionUser } from './sessionStore';

const IDLE_TTL_SECONDS = Number(process.env.SESSION_IDLE_TTL_SECONDS || 1800);
const ABSOLUTE_TTL_SECONDS = Number(process.env.SESSION_ABSOLUTE_TTL_SECONDS || 43200);
const REFRESH_MARGIN_SECONDS = 60;
const LOCK_TTL_MS = 5000;
const LOCK_WAIT_MS = 2000;
const MUTATING = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

export const sessionCookieName = () => process.env.SESSION_COOKIE_NAME || 'vota_sid';
export const csrfCookieName = () => process.env.CSRF_COOKIE_NAME || 'vota_csrf';

const nowSeconds = () => Math.floor(Date.now() / 1000);
const opaque = (prefix: string) => `${prefix}_${randomBytes(16).toString('base64url')}`;
const sha256 = (value: string) => `sha256:${createHash('sha256').update(value).digest('hex')}`;
const shortSid = (sid: string) => sid.slice(0, 8);

export function logAuth(event: string, fields: Record<string, unknown> = {}) {
  // Không bao giờ ghi token, sid đầy đủ, CSRF token hay email thô (§15.2).
  console.info(JSON.stringify({ event, ts: new Date().toISOString(), ...fields }));
}

// --- lỗi theo Error Envelope --------------------------------------------------------------------

export function errorResponse(status: number, code: string, message: string, requestId: string, extraHeaders?: HeadersInit) {
  const headers = new Headers(extraHeaders);
  headers.set('content-type', 'application/json');
  headers.set('x-request-id', requestId);
  return new Response(JSON.stringify({ error: { code, message, retryable: false, requestId } }), { status, headers });
}

export function requestIdOf(request: Request) {
  const incoming = request.headers.get('x-request-id');
  return incoming ? incoming.slice(0, 64) : `web-${randomBytes(6).toString('hex')}`;
}

// --- cookie -------------------------------------------------------------------------------------

export function readCookie(request: Request, name: string): string | null {
  const header = request.headers.get('cookie');
  if (!header) return null;
  for (const part of header.split(';')) {
    const [key, ...rest] = part.trim().split('=');
    if (key === name) return decodeURIComponent(rest.join('='));
  }
  return null;
}

function secureCookies() {
  // Secure trừ khi chạy development trên localhost (§6 chú thích 1).
  return !(process.env.APP_ENV === 'development' || process.env.NODE_ENV === 'development' || process.env.NODE_ENV === 'test');
}

function cookie(name: string, value: string, { httpOnly, maxAge }: { httpOnly: boolean; maxAge?: number }) {
  const parts = [`${name}=${encodeURIComponent(value)}`, 'Path=/', 'SameSite=Lax'];
  if (httpOnly) parts.push('HttpOnly');
  if (secureCookies()) parts.push('Secure');
  if (maxAge !== undefined) parts.push(`Max-Age=${maxAge}`);
  return parts.join('; ');
}

export function sessionCookies(sid: string, record: SessionRecord): string[] {
  // Không đặt Max-Age: cookie phiên. Hạn thật do Redis (idle) và absoluteExp quyết định.
  return [
    cookie(sessionCookieName(), sid, { httpOnly: true }),
    cookie(csrfCookieName(), record.csrfToken, { httpOnly: false }),
  ];
}

export function clearedCookies(): string[] {
  return [
    cookie(sessionCookieName(), '', { httpOnly: true, maxAge: 0 }),
    cookie(csrfCookieName(), '', { httpOnly: false, maxAge: 0 }),
  ];
}

export function withCookies(response: Response, cookies: string[]) {
  for (const value of cookies) response.headers.append('set-cookie', value);
  return response;
}

// --- vòng đời phiên -----------------------------------------------------------------------------

export type LoadedSession =
  | { kind: 'none' }
  | { kind: 'expired'; reason: 'idle' | 'absolute' | 'ua_mismatch' }
  | { kind: 'active'; sid: string; record: SessionRecord };

const uaHashOf = (request: Request) => sha256(request.headers.get('user-agent') || '');

export async function loadSession(request: Request, store?: SessionStore): Promise<LoadedSession> {
  const sid = readCookie(request, sessionCookieName());
  if (!sid) return { kind: 'none' };
  const s = store ?? await getSessionStore();
  const record = await s.get(sid);
  if (!record) {
    logAuth('auth.session.expired', { sid: shortSid(sid), reason: 'idle' });
    return { kind: 'expired', reason: 'idle' };
  }
  if (record.absoluteExp <= nowSeconds()) {
    await destroySession(sid, record, s);
    logAuth('auth.session.expired', { sid: shortSid(sid), reason: 'absolute' });
    return { kind: 'expired', reason: 'absolute' };
  }
  if (record.uaHash !== uaHashOf(request)) {
    // §3.8 dòng H: User-Agent đổi giữa chừng = cookie bị mang sang trình duyệt khác.
    await destroySession(sid, record, s);
    logAuth('session.ua_mismatch', { sid: shortSid(sid) });
    return { kind: 'expired', reason: 'ua_mismatch' };
  }
  record.lastSeenAt = nowSeconds();
  await s.set(sid, record, IDLE_TTL_SECONDS); // gia hạn idle, KHÔNG gia hạn absoluteExp
  return { kind: 'active', sid, record };
}

function baseRecord(request: Request): SessionRecord {
  const now = nowSeconds();
  return {
    v: 1, state: 'anonymous', user: null, anonId: opaque('a'), amr: [], accessToken: null, accessTokenExp: null,
    refreshToken: null, csrfToken: opaque('c'), createdAt: now, lastSeenAt: now,
    absoluteExp: now + ABSOLUTE_TTL_SECONDS, uaHash: uaHashOf(request),
  };
}

/** §3.8 dòng A: lần đầu vào site. */
export async function createAnonymousSession(request: Request, store?: SessionStore) {
  const s = store ?? await getSessionStore();
  const sid = opaque('s');
  const record = baseRecord(request);
  await s.set(sid, record, IDLE_TTL_SECONDS);
  return { sid, record };
}

export interface IssuedTokens {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
  user: SessionUser;
}

/**
 * §3.8 dòng B, C, F: nâng lên authenticated. LUÔN xoay sid và CSRF token (chống session fixation):
 * sid cũ bị xoá, bản ghi mới được phát.
 */
export async function establishSession(request: Request, previous: { sid: string; record: SessionRecord } | null,
                                       tokens: IssuedTokens, store?: SessionStore) {
  const s = store ?? await getSessionStore();
  if (previous) await destroySession(previous.sid, previous.record, s);
  const sid = opaque('s');
  const record: SessionRecord = {
    ...baseRecord(request),
    state: 'authenticated', user: tokens.user, anonId: null, amr: ['pwd'],
    accessToken: tokens.accessToken, accessTokenExp: nowSeconds() + tokens.expiresIn,
    refreshToken: tokens.refreshToken,
  };
  await s.set(sid, record, IDLE_TTL_SECONDS);
  await s.addUserSession(tokens.user.userId, sid);
  if (previous) logAuth('auth.session.rotated', { oldSid: shortSid(previous.sid), newSid: shortSid(sid), reason: 'login' });
  return { sid, record };
}

export async function destroySession(sid: string, record: SessionRecord | null, store?: SessionStore) {
  const s = store ?? await getSessionStore();
  await s.del(sid);
  if (record?.user) await s.removeUserSession(record.user.userId, sid);
}

/** §3.8 dòng J: đổi mật khẩu → huỷ mọi phiên khác của user, phiên hiện tại sống tiếp với sid mới. */
export async function rotateAfterPasswordChange(request: Request, current: { sid: string; record: SessionRecord },
                                                store?: SessionStore) {
  const s = store ?? await getSessionStore();
  const userId = current.record.user!.userId;
  for (const other of await s.userSessions(userId)) {
    if (other !== current.sid) {
      await s.del(other);
      await s.removeUserSession(userId, other);
    }
  }
  await s.del(current.sid);
  await s.removeUserSession(userId, current.sid);
  const sid = opaque('s');
  const record = { ...current.record, csrfToken: opaque('c') };
  await s.set(sid, record, IDLE_TTL_SECONDS);
  await s.addUserSession(userId, sid);
  logAuth('auth.session.rotated', { oldSid: shortSid(current.sid), newSid: shortSid(sid), reason: 'password_change' });
  return { sid, record };
}

// --- CSRF (§7) ----------------------------------------------------------------------------------

function allowedOrigins(request: Request) {
  const configured = (process.env.ALLOWED_ORIGINS || '').split(',').map((o) => o.trim()).filter(Boolean);
  return configured.length ? configured : [new URL(request.url).origin];
}

function sameToken(a: string, b: string) {
  const left = Buffer.from(a);
  const right = Buffer.from(b);
  return left.length === right.length && timingSafeEqual(left, right);
}

/** Trả null khi qua; ngược lại là lý do. GET/HEAD/OPTIONS không kiểm và không được đổi state. */
export function csrfFailure(request: Request, record: SessionRecord | null): string | null {
  if (!MUTATING.has(request.method.toUpperCase())) return null;
  const origin = request.headers.get('origin') ?? (() => {
    const referer = request.headers.get('referer');
    try { return referer ? new URL(referer).origin : null; } catch { return null; }
  })();
  if (!origin || !allowedOrigins(request).includes(origin)) return 'origin';
  const header = request.headers.get('x-csrf-token');
  if (!record || !header || !sameToken(header, record.csrfToken)) return 'token';
  return null;
}

// --- gọi FastAPI --------------------------------------------------------------------------------

export function backendBase() {
  const base = process.env.BACKEND_BASE_URL;
  if (!base) return null;
  return base.endsWith('/') ? base : `${base}/`;
}

export async function callBackend(path: string, init: { method: string; body?: unknown; requestId: string;
  clientIp?: string | null; bearer?: string | null; service?: boolean }) {
  const base = backendBase();
  if (!base) throw new Error('BACKEND_BASE_URL chưa cấu hình');
  const headers = new Headers({ 'content-type': 'application/json', 'x-request-id': init.requestId });
  if (init.service) headers.set('x-service-token', process.env.AUTH_SERVICE_TOKEN || '');
  if (init.bearer) headers.set('authorization', `Bearer ${init.bearer}`);
  if (init.clientIp) headers.set('x-forwarded-for', init.clientIp);
  return fetch(new URL(`api/v1/${path}`, base), {
    method: init.method, headers, cache: 'no-store',
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
  });
}

export function clientIpOf(request: Request) {
  // Chỉ chuyển tiếp; FastAPI tự quyết có tin hay không theo TRUSTED_PROXIES (§9.4).
  return request.headers.get('x-forwarded-for')?.split(',')[0]?.trim() || request.headers.get('x-real-ip') || null;
}

/**
 * §3.4: access token còn > 60s thì dùng tiếp; ≤ 60s thì refresh trước khi proxy. Nhiều tab cùng
 * refresh: một bên giữ khoá `lock:refresh:{sid}`, bên thua chờ tối đa 2s rồi đọc lại phiên.
 * Trả null khi refresh thất bại — caller huỷ phiên và trả 401 SESSION_EXPIRED.
 */
export async function ensureFreshAccessToken(sid: string, record: SessionRecord, requestId: string,
                                             store?: SessionStore): Promise<SessionRecord | null> {
  if (record.state !== 'authenticated' || !record.refreshToken) return record;
  if ((record.accessTokenExp ?? 0) - nowSeconds() > REFRESH_MARGIN_SECONDS) return record;
  const s = store ?? await getSessionStore();
  const lockKey = `lock:refresh:${sid}`;
  if (!(await s.tryLock(lockKey, LOCK_TTL_MS))) {
    const deadline = Date.now() + LOCK_WAIT_MS;
    while (Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 100));
      const reread = await s.get(sid);
      if (!reread) return null;
      if ((reread.accessTokenExp ?? 0) - nowSeconds() > REFRESH_MARGIN_SECONDS) return reread;
    }
    return null;
  }
  try {
    const response = await callBackend('auth/session/token', {
      method: 'POST', service: true, requestId, body: { refreshToken: record.refreshToken },
    });
    if (!response.ok) {
      logAuth('auth.session.refresh_failed', { sid: shortSid(sid), status: response.status });
      return null;
    }
    const body = await response.json();
    const updated: SessionRecord = {
      ...record, accessToken: body.accessToken, refreshToken: body.refreshToken,
      accessTokenExp: nowSeconds() + Number(body.expiresIn), user: body.user ?? record.user,
    };
    await s.set(sid, updated, IDLE_TTL_SECONDS);
    return updated;
  } finally {
    await s.unlock(lockKey);
  }
}

export function publicState(record: SessionRecord) {
  return {
    state: record.state,
    ...(record.state === 'authenticated' && record.user ? { user: record.user } : {}),
    csrfToken: record.csrfToken,
  };
}
