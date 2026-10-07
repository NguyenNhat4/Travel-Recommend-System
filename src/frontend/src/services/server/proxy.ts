/**
 * Proxy catch-all `/api/*` → FastAPI (docs/spec/hop-dong-tich-hop-auth.md §4.1). CHỈ chạy phía server.
 *
 * Ba việc trước khi chuyển tiếp: đọc phiên, kiểm CSRF cho method ghi, gắn `Authorization` từ phiên.
 * FastAPI không bao giờ thấy cookie của trình duyệt, và client không tự đặt được `Authorization`.
 *
 * Giỏ và đơn nháp của khách chưa đăng nhập (docs/spec/booking/dat-truc-tiep-theo-don-nhap.md §8): phiên chưa đăng nhập gọi
 * `/cart*`, `/booking-drafts*` thì proxy gửi kèm `X-Service-Token` + `X-Guest-Id` lấy từ cookie `vota_guest` (phát nếu chưa
 * có). Phiên đã đăng nhập mà còn cookie đó thì proxy gộp dữ liệu khách vào tài khoản trước, rồi xoá cookie.
 */
import {
  backendBase,
  callBackend,
  clearedCookies,
  clearedGuestCookie,
  csrfFailure,
  destroySession,
  ensureFreshAccessToken,
  errorResponse,
  guestCookie,
  loadSession,
  newGuestId,
  readGuestId,
  requestIdOf,
  rotateAfterPasswordChange,
  sessionCookies,
  withCookies,
} from './bffSession';
import { hashId, log, routeOf, serializeError } from '../../lib/logger';

type RouteContext = { params: Promise<{ path: string[] }> };

// Header client không được tự đặt, hoặc không được lọt sang FastAPI.
const STRIPPED_REQUEST_HEADERS = ['host', 'content-length', 'cookie', 'authorization', 'x-service-token', 'x-csrf-token', 'x-guest-id'];
// Khách chưa đăng nhập dùng được giỏ và đơn nháp; gộp vào tài khoản trước mọi request đặt chỗ đầu tiên sau khi đăng nhập.
const GUEST_PATHS = /^v1\/(cart|booking-drafts)(\/|$)/;
const BOOKING_PATHS = /^v1\/(cart|booking-drafts|bookings)(\/|$)/;
// Chỉ BFF gọi (X-Service-Token); trình duyệt không được chạm.
const INTERNAL_PATHS = /^v1\/guest-bookings(\/|$)/;
const MUTATING = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);
const FORWARDED_RESPONSE_HEADERS = ['content-type', 'cache-control', 'location', 'retry-after'];

/**
 * R-BFF-01/02: gộp giỏ và đơn nháp của khách vào tài khoản. True = đã xong (kể cả khi không còn gì để gộp hoặc mã khách bị
 * từ chối), xoá cookie được; false = Backend không phản hồi, giữ cookie để request sau thử lại.
 */
async function mergeGuest(guestId: string, accessToken: string, requestId: string): Promise<boolean> {
  try {
    const response = await callBackend('guest-bookings/merge', {
      method: 'POST', service: true, bearer: accessToken, requestId, body: { guestId },
    });
    if (response.status >= 500) {
      log.warn('bff.guest.merge', { request_id: requestId, outcome: 'failed', status: response.status, guest_hash: hashId(guestId) });
      return false;
    }
    log.info('bff.guest.merge', { request_id: requestId, outcome: 'ok', status: response.status, guest_hash: hashId(guestId) });
    return true;
  } catch (error) {
    log.warn('bff.guest.merge', { request_id: requestId, outcome: 'failed', status: 0, guest_hash: hashId(guestId), error });
    return false;
  }
}

function sessionExpired(requestId: string) {
  return withCookies(errorResponse(401, 'SESSION_EXPIRED', 'Phiên đăng nhập đã hết hạn.', requestId), clearedCookies());
}

/**
 * Bọc body SSE của trợ lý để ghi `bff.stream.open/close`. Chỉ đếm byte và thời gian, không đọc nội dung.
 * `close` ghi đúng một lần: stream hết (`done`), upstream lỗi (`error`) hoặc trình duyệt ngắt (`cancelled`).
 */
function trackStream(body: ReadableStream<Uint8Array>, base: Record<string, unknown>): ReadableStream<Uint8Array> {
  const startedAt = Date.now();
  const reader = body.getReader();
  let bytes = 0;
  let closed = false;
  const finish = (outcome: string, error?: unknown) => {
    if (closed) return;
    closed = true;
    const fields = { ...base, outcome, duration_ms: Date.now() - startedAt, response_bytes: bytes };
    if (error) log.warn('bff.stream.close', { ...fields, error });
    else log.info('bff.stream.close', fields);
  };
  log.info('bff.stream.open', base);
  return new ReadableStream<Uint8Array>({
    async pull(controller) {
      try {
        const { done, value } = await reader.read();
        if (done) { finish('done'); controller.close(); return; }
        bytes += value.byteLength;
        controller.enqueue(value);
      } catch (error) {
        finish('error', error);
        controller.error(error);
      }
    },
    async cancel(reason) {
      finish('cancelled');
      await reader.cancel(reason).catch(() => undefined);
    },
  });
}

export async function proxyToBackend(request: Request, context: RouteContext) {
  const startedAt = Date.now();
  const { path } = await context.params;
  const requestId = requestIdOf(request);
  const base = backendBase();
  if (!base) return errorResponse(503, 'INTERNAL_ERROR', 'Backend service is not configured', requestId);
  const joined = path.join('/');
  if (INTERNAL_PATHS.test(joined)) return errorResponse(404, 'NOT_FOUND', 'Không tìm thấy.', requestId);
  const target = new URL(`api/${joined}`, base);
  target.search = new URL(request.url).search;

  let loaded;
  try {
    loaded = await loadSession(request);
  } catch (error) {
    log.error('bff.proxy.upstream_error', { request_id: requestId, target: 'session_store', error: serializeError(error) });
    return errorResponse(503, 'INTERNAL_ERROR', 'Dịch vụ phiên tạm thời không khả dụng.', requestId);
  }
  // Cookie có nhưng phiên đã chết (idle/absolute/UA lệch): báo rõ, không âm thầm thành khách.
  if (loaded.kind === 'expired') return sessionExpired(requestId);
  let current = loaded.kind === 'active' ? loaded : null;

  const csrf = csrfFailure(request, current?.record ?? null);
  if (csrf) {
    log.warn('bff.csrf.rejected', { request_id: requestId, reason: csrf, method: request.method, route: routeOf(target.pathname) });
    return errorResponse(403, 'CSRF_FAILED', 'Phiên trang đã cũ. Vui lòng tải lại trang rồi thử lại.', requestId);
  }

  const headers = new Headers(request.headers);
  for (const header of STRIPPED_REQUEST_HEADERS) headers.delete(header);
  headers.set('x-request-id', requestId);
  const extraCookies: string[] = [];

  if (current?.record.state === 'authenticated') {
    const record = await ensureFreshAccessToken(current.sid, current.record, requestId).catch(() => null);
    if (!record?.accessToken) {
      await destroySession(current.sid, current.record);
      return sessionExpired(requestId);
    }
    current = { ...current, record };
    headers.set('authorization', `Bearer ${record.accessToken}`);
    const guestId = readGuestId(request);
    if (guestId && BOOKING_PATHS.test(joined) && await mergeGuest(guestId, record.accessToken, requestId)) {
      extraCookies.push(clearedGuestCookie());
    }
  } else if (GUEST_PATHS.test(joined)) {
    // Backend chỉ tin X-Guest-Id khi đi kèm X-Service-Token, tức khi request đến từ BFF (R-GST-02, R-GST-03).
    const existing = readGuestId(request);
    const guestId = existing ?? newGuestId();
    headers.set('x-service-token', process.env.AUTH_SERVICE_TOKEN || '');
    headers.set('x-guest-id', guestId);
    // Phát cookie lần đầu; request ghi đặt lại hạn 3 ngày, khớp TTL của Redis (R-GST-01).
    if (!existing || MUTATING.has(request.method.toUpperCase())) extraCookies.push(guestCookie(guestId));
    if (!existing) log.info('bff.guest.issue', { request_id: requestId, guest_hash: hashId(guestId) });
  }

  const body = ['GET', 'HEAD'].includes(request.method) ? undefined : await request.arrayBuffer();

  const route = routeOf(target.pathname);
  const authenticated = current?.record.state === 'authenticated';
  const upstreamStart = Date.now();
  let response: Response;
  try {
    response = await fetch(target, {
      method: request.method, headers, body, cache: 'no-store', signal: request.signal,
    });
  } catch (error) {
    // Trình duyệt tự huỷ (đổi trang, effect chạy lại, Strict Mode ở dev): không phải lỗi backend, không ghi log.
    if (request.signal.aborted) return new Response(null, { status: 499 });
    log.error('bff.proxy.upstream_error', {
      request_id: requestId, method: request.method, route, upstream_ms: Date.now() - upstreamStart, authenticated,
      error: serializeError(error),
    });
    return errorResponse(502, 'INTERNAL_ERROR', 'Backend service unavailable', requestId);
  }

  const responseHeaders = new Headers();
  for (const header of FORWARDED_RESPONSE_HEADERS) {
    const value = response.headers.get(header);
    if (value) responseHeaders.set(header, value);
  }
  responseHeaders.set('x-request-id', response.headers.get('x-request-id') || requestId);

  const upstreamMs = Date.now() - upstreamStart;
  const summary = {
    request_id: requestId, method: request.method, route, status: response.status, upstream_ms: upstreamMs, authenticated,
  };
  const isStream = (response.headers.get('content-type') || '').includes('text/event-stream');
  const logProxy = response.status >= 500 ? log.error : response.status >= 400 ? log.warn : log.info;
  logProxy('bff.proxy', { ...summary, duration_ms: Date.now() - startedAt, ...(isStream ? { stream: true } : {}) });

  const responseBody = isStream && response.body ? trackStream(response.body, { request_id: requestId, route }) : response.body;
  const proxied = new Response(responseBody, {
    status: response.status, statusText: response.statusText, headers: responseHeaders,
  });

  // §3.8 dòng J: đổi mật khẩu thành công → huỷ phiên khác, xoay sid của phiên hiện tại.
  if (current && request.method === 'PUT' && joined === 'v1/auth/password' && response.status === 204) {
    const rotated = await rotateAfterPasswordChange(request, current);
    return withCookies(proxied, [...sessionCookies(rotated.sid, rotated.record), ...extraCookies]);
  }
  return withCookies(proxied, extraCookies);
}
