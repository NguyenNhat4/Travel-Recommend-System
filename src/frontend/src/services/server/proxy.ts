/**
 * Proxy catch-all `/api/*` → FastAPI (docs/spec/hop-dong-tich-hop-auth.md §4.1). CHỈ chạy phía server.
 *
 * Ba việc trước khi chuyển tiếp: đọc phiên, kiểm CSRF cho method ghi, gắn `Authorization` từ phiên.
 * FastAPI không bao giờ thấy cookie của trình duyệt, và client không tự đặt được `Authorization`.
 */
import {
  backendBase,
  clearedCookies,
  csrfFailure,
  destroySession,
  ensureFreshAccessToken,
  errorResponse,
  loadSession,
  logAuth,
  requestIdOf,
  rotateAfterPasswordChange,
  sessionCookies,
  withCookies,
} from './bffSession';

type RouteContext = { params: Promise<{ path: string[] }> };

// Header client không được tự đặt, hoặc không được lọt sang FastAPI.
const STRIPPED_REQUEST_HEADERS = ['host', 'content-length', 'cookie', 'authorization', 'x-service-token', 'x-csrf-token'];
const FORWARDED_RESPONSE_HEADERS = ['content-type', 'cache-control', 'location', 'retry-after'];

function sessionExpired(requestId: string) {
  return withCookies(errorResponse(401, 'SESSION_EXPIRED', 'Phiên đăng nhập đã hết hạn.', requestId), clearedCookies());
}

export async function proxyToBackend(request: Request, context: RouteContext) {
  const { path } = await context.params;
  const requestId = requestIdOf(request);
  const base = backendBase();
  if (!base) return errorResponse(503, 'INTERNAL_ERROR', 'Backend service is not configured', requestId);
  const target = new URL(`api/${path.join('/')}`, base);
  target.search = new URL(request.url).search;

  let loaded;
  try {
    loaded = await loadSession(request);
  } catch (error) {
    console.error('Session store unavailable', error);
    return errorResponse(503, 'INTERNAL_ERROR', 'Dịch vụ phiên tạm thời không khả dụng.', requestId);
  }
  // Cookie có nhưng phiên đã chết (idle/absolute/UA lệch): báo rõ, không âm thầm thành khách.
  if (loaded.kind === 'expired') return sessionExpired(requestId);
  let current = loaded.kind === 'active' ? loaded : null;

  const csrf = csrfFailure(request, current?.record ?? null);
  if (csrf) {
    logAuth('auth.csrf.failed', { reason: csrf, path: target.pathname });
    return errorResponse(403, 'CSRF_FAILED', 'Phiên trang đã cũ. Vui lòng tải lại trang rồi thử lại.', requestId);
  }

  const headers = new Headers(request.headers);
  for (const header of STRIPPED_REQUEST_HEADERS) headers.delete(header);
  headers.set('x-request-id', requestId);

  if (current?.record.state === 'authenticated') {
    const record = await ensureFreshAccessToken(current.sid, current.record, requestId).catch(() => null);
    if (!record?.accessToken) {
      await destroySession(current.sid, current.record);
      return sessionExpired(requestId);
    }
    current = { ...current, record };
    headers.set('authorization', `Bearer ${record.accessToken}`);
  }

  const body = ['GET', 'HEAD'].includes(request.method) ? undefined : await request.arrayBuffer();

  let response: Response;
  try {
    response = await fetch(target, {
      method: request.method, headers, body, cache: 'no-store', signal: request.signal,
    });
  } catch (error) {
    console.error('Backend proxy error', error);
    return errorResponse(502, 'INTERNAL_ERROR', 'Backend service unavailable', requestId);
  }

  const responseHeaders = new Headers();
  for (const header of FORWARDED_RESPONSE_HEADERS) {
    const value = response.headers.get(header);
    if (value) responseHeaders.set(header, value);
  }
  responseHeaders.set('x-request-id', response.headers.get('x-request-id') || requestId);

  const proxied = new Response(response.body, {
    status: response.status, statusText: response.statusText, headers: responseHeaders,
  });

  // §3.8 dòng J: đổi mật khẩu thành công → huỷ phiên khác, xoay sid của phiên hiện tại.
  if (current && request.method === 'PUT' && path.join('/') === 'v1/auth/password' && response.status === 204) {
    const rotated = await rotateAfterPasswordChange(request, current);
    return withCookies(proxied, sessionCookies(rotated.sid, rotated.record));
  }
  return proxied;
}
