/**
 * Mọi request từ trình duyệt tới BFF đi qua đây (docs/spec/hop-dong-tich-hop-auth.md §4.2).
 *
 * - `credentials: 'same-origin'`: cookie phiên HttpOnly đi kèm; JavaScript không đọc được nó.
 * - Method ghi gửi `X-CSRF-Token` đọc từ cookie `vota_csrf` (double-submit).
 * - Không component nào chạm token: không Authorization, không sessionStorage/localStorage.
 * - `403 CSRF_FAILED` hoặc `401 SESSION_EXPIRED`: khôi phục phiên (GET /api/auth/session) rồi gửi lại
 *   ĐÚNG MỘT lần. SESSION_EXPIRED còn phát sự kiện để UI mở modal "Phiên đăng nhập đã hết hạn".
 */
export const CSRF_COOKIE = 'vota_csrf';
export const SESSION_EXPIRED_EVENT = 'vota:session-expired';
const MUTATING = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

export function readCsrfCookie(): string | null {
  if (typeof document === 'undefined') return null;
  for (const part of document.cookie.split(';')) {
    const [key, ...rest] = part.trim().split('=');
    if (key === CSRF_COOKIE) return decodeURIComponent(rest.join('='));
  }
  return null;
}

export function newRequestId(): string {
  const random = typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID().replace(/-/g, '').slice(0, 16)
    : Math.random().toString(36).slice(2, 18);
  return `web-${random}`;
}

let bootstrapping: Promise<unknown> | null = null;

/** GET /api/auth/session — tạo phiên khách khi chưa có, để có CSRF token. Gộp các lời gọi song song. */
export function bootstrapSession(): Promise<unknown> {
  bootstrapping ??= fetch('/api/auth/session', { credentials: 'same-origin', cache: 'no-store' })
    .then((response) => (response.ok ? response.json() : null))
    .finally(() => { bootstrapping = null; });
  return bootstrapping;
}

async function errorCode(response: Response): Promise<string | null> {
  try {
    return (await response.clone().json())?.error?.code ?? null;
  } catch {
    return null;
  }
}

export async function apiFetch(input: string, init: RequestInit = {}, retried = false): Promise<Response> {
  const method = (init.method || 'GET').toUpperCase();
  const headers = new Headers(init.headers);
  headers.delete('authorization');
  if (!headers.has('x-request-id')) headers.set('X-Request-ID', newRequestId());
  if (MUTATING.has(method)) {
    if (typeof document !== 'undefined' && !readCsrfCookie()) await bootstrapSession();
    const csrf = readCsrfCookie();
    if (csrf) headers.set('X-CSRF-Token', csrf);
  }
  const response = await fetch(input, { ...init, method, headers, credentials: 'same-origin' });
  if (retried || (response.status !== 401 && response.status !== 403)) return response;

  const code = await errorCode(response);
  if (code !== 'CSRF_FAILED' && code !== 'SESSION_EXPIRED') return response;
  if (code === 'SESSION_EXPIRED' && typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT));
  }
  await bootstrapSession();
  headers.delete('x-request-id');
  return apiFetch(input, { ...init, headers }, true);
}
