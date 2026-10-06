/**
 * Hiện thực của các route BFF `/api/auth/*` (docs/spec/hop-dong-tich-hop-auth.md §4). File `route.ts`
 * trong `app/api/auth/` chỉ re-export từ đây để `app/` không chứa logic (docs/prd/architecture.md §6.2).
 */
import {
  callBackend,
  clearedCookies,
  clientIpOf,
  createAnonymousSession,
  csrfFailure,
  destroySession,
  ensureFreshAccessToken,
  errorResponse,
  establishSession,
  loadSession,
  publicState,
  requestIdOf,
  sessionCookies,
  withCookies,
  type IssuedTokens,
} from './bffSession';
import { hashId, log, routeOf } from '../../lib/logger';

function json(body: unknown, status: number, requestId: string) {
  return new Response(JSON.stringify(body), {
    status, headers: { 'content-type': 'application/json', 'x-request-id': requestId },
  });
}

/** Chuyển nguyên Error Envelope của FastAPI (401/409/429/…); giữ Retry-After cho 429. */
async function passThrough(response: Response, requestId: string) {
  const headers = new Headers({ 'content-type': 'application/json', 'x-request-id': requestId });
  const retryAfter = response.headers.get('retry-after');
  if (retryAfter) headers.set('retry-after', retryAfter);
  return new Response(await response.text(), { status: response.status, headers });
}

function backendUnavailable(requestId: string) {
  return errorResponse(502, 'INTERNAL_ERROR', 'Không kết nối được dịch vụ xác thực.', requestId);
}

/** GET /api/auth/session — khôi phục phiên sau reload. Không bao giờ 401: khách nhận state anonymous. */
export async function getSession(request: Request) {
  const requestId = requestIdOf(request);
  const loaded = await loadSession(request);
  if (loaded.kind === 'active') {
    const record = await ensureFreshAccessToken(loaded.sid, loaded.record, requestId);
    if (record) return json(publicState(record), 200, requestId);
    await destroySession(loaded.sid, loaded.record);
  }
  const fresh = await createAnonymousSession(request);
  return withCookies(json(publicState(fresh.record), 200, requestId), sessionCookies(fresh.sid, fresh.record));
}

async function guardWrite(request: Request, requestId: string) {
  const loaded = await loadSession(request);
  const current = loaded.kind === 'active' ? loaded : null;
  const failure = csrfFailure(request, current?.record ?? null);
  if (failure) {
    log.warn('bff.csrf.rejected', { request_id: requestId, reason: failure, route: routeOf(new URL(request.url).pathname) });
    return { error: errorResponse(403, 'CSRF_FAILED', 'Phiên trang đã cũ. Vui lòng tải lại trang rồi thử lại.', requestId) };
  }
  return { current };
}

async function signIn(request: Request, requestId: string, current: Awaited<ReturnType<typeof guardWrite>>['current'],
                      credentials: { email: string; password: string }) {
  const response = await callBackend('auth/session', {
    method: 'POST', service: true, requestId, clientIp: clientIpOf(request), body: credentials,
  });
  if (!response.ok) {
    log.info('bff.auth.login', { request_id: requestId, outcome: 'failed', status: response.status });
    return passThrough(response, requestId);
  }
  const tokens = (await response.json()) as IssuedTokens;
  // §3.8 dòng F: đang đăng nhập tài khoản khác → đăng xuất tài khoản cũ ở backend trước.
  if (current?.record.refreshToken) {
    await callBackend('auth/session/revoke', {
      method: 'POST', service: true, requestId, body: { refreshToken: current.record.refreshToken },
    }).catch(() => undefined);
  }
  const next = await establishSession(request, current ? { sid: current.sid, record: current.record } : null, tokens);
  log.info('bff.auth.login', { request_id: requestId, outcome: 'ok', user_id_hash: hashId(tokens.user?.userId) });
  return withCookies(json(publicState(next.record), 200, requestId), sessionCookies(next.sid, next.record));
}

async function readJson(request: Request): Promise<Record<string, unknown>> {
  try {
    const body = await request.json();
    return body && typeof body === 'object' ? body : {};
  } catch {
    return {};
  }
}

/** POST /api/auth/login { email, password } */
export async function login(request: Request) {
  const requestId = requestIdOf(request);
  const guard = await guardWrite(request, requestId);
  if (guard.error) return guard.error;
  const body = await readJson(request);
  try {
    return await signIn(request, requestId, guard.current, { email: String(body.email ?? ''), password: String(body.password ?? '') });
  } catch {
    return backendUnavailable(requestId);
  }
}

/** POST /api/auth/register { email, password, fullName } — tạo tài khoản rồi mở phiên như đăng nhập. */
export async function register(request: Request) {
  const requestId = requestIdOf(request);
  const guard = await guardWrite(request, requestId);
  if (guard.error) return guard.error;
  const body = await readJson(request);
  const payload = { email: String(body.email ?? ''), password: String(body.password ?? ''), fullName: String(body.fullName ?? '') };
  try {
    const created = await callBackend('auth/register', {
      method: 'POST', requestId, clientIp: clientIpOf(request), body: payload,
    });
    log.info('bff.auth.register', { request_id: requestId, outcome: created.ok ? 'ok' : 'failed', status: created.status });
    if (!created.ok) return passThrough(created, requestId);
    return await signIn(request, requestId, guard.current, { email: payload.email, password: payload.password });
  } catch {
    return backendUnavailable(requestId);
  }
}

/** POST /api/auth/logout — xoá cookie kể cả khi backend lỗi. */
export async function logout(request: Request) {
  const requestId = requestIdOf(request);
  const guard = await guardWrite(request, requestId);
  if (guard.error) return guard.error;
  const current = guard.current;
  if (current) {
    if (current.record.refreshToken) {
      await callBackend('auth/session/revoke', {
        method: 'POST', service: true, requestId, body: { refreshToken: current.record.refreshToken },
      }).catch(() => undefined);
    }
    await destroySession(current.sid, current.record);
    log.info('bff.auth.logout', { request_id: requestId, user_id_hash: hashId(current.record.user?.userId) });
  }
  return withCookies(new Response(null, { status: 204, headers: { 'x-request-id': requestId } }), clearedCookies());
}

/** POST /api/auth/refresh — chủ động làm mới; bình thường proxy tự refresh. */
export async function refresh(request: Request) {
  const requestId = requestIdOf(request);
  const guard = await guardWrite(request, requestId);
  if (guard.error) return guard.error;
  const current = guard.current;
  if (!current || current.record.state !== 'authenticated') {
    return errorResponse(401, 'UNAUTHENTICATED', 'Vui lòng đăng nhập để tiếp tục.', requestId);
  }
  const forced = { ...current.record, accessTokenExp: 0 };
  const updated = await ensureFreshAccessToken(current.sid, forced, requestId).catch(() => null);
  if (!updated) {
    await destroySession(current.sid, current.record);
    return withCookies(errorResponse(401, 'SESSION_EXPIRED', 'Phiên đăng nhập đã hết hạn.', requestId), clearedCookies());
  }
  return new Response(null, { status: 204, headers: { 'x-request-id': requestId } });
}
