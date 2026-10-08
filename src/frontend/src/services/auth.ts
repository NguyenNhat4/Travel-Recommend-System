/**
 * Auth phía client — chỉ nói chuyện với BFF `/api/auth/*` (docs/spec/hop-dong-tich-hop-auth.md §4).
 * Trình duyệt không bao giờ nhận token; response chỉ có state và thông tin người dùng.
 */
import { apiFetch, bootstrapSession } from './http';

export interface AuthUser {
  userId: string;
  cdpUserId: string;
  email: string;
  fullName: string;
  phone?: string | null;
}

export interface SessionView {
  state: 'anonymous' | 'pending_mfa' | 'authenticated';
  user?: AuthUser;
}

export class AuthError extends Error {
  constructor(
    message: string,
    readonly code: string,
    readonly status: number,
    readonly details?: Record<string, unknown>,
    readonly retryAfterSeconds?: number,
  ) {
    super(message);
  }
}

async function toAuthError(response: Response): Promise<AuthError> {
  let body: any = null;
  try { body = await response.json(); } catch { /* không có envelope */ }
  const error = body?.error ?? {};
  const retryAfter = Number(response.headers.get('retry-after')) || error.details?.retryAfterSeconds;
  return new AuthError(error.message || 'Có lỗi xảy ra. Vui lòng thử lại.', error.code || 'INTERNAL_ERROR',
    response.status, error.details, retryAfter || undefined);
}

export async function getSession(): Promise<SessionView> {
  const body = (await bootstrapSession()) as SessionView | null;
  return body ?? { state: 'anonymous' };
}

async function post(path: string, payload?: unknown): Promise<Response> {
  const response = await apiFetch(path, {
    method: 'POST',
    headers: payload === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: payload === undefined ? undefined : JSON.stringify(payload),
  });
  if (!response.ok) throw await toAuthError(response);
  return response;
}

export async function login(email: string, password: string): Promise<SessionView> {
  return (await post('/api/auth/login', { email, password })).json();
}

export async function register(email: string, password: string, fullName: string): Promise<SessionView> {
  return (await post('/api/auth/register', { email, password, fullName })).json();
}

export async function logout(): Promise<void> {
  try {
    await post('/api/auth/logout');
  } finally {
    await bootstrapSession(); // phiên khách mới cho CSRF của các request sau
  }
}

export interface ProfileChanges {
  fullName?: string;
  /** `null` xoá số điện thoại. */
  phone?: string | null;
}

/** Sửa họ tên và số điện thoại của chính mình (FR-USR-04). Lỗi nhập hợp lệ là 422 VALIDATION_ERROR. */
export async function updateProfile(changes: ProfileChanges): Promise<AuthUser> {
  const response = await apiFetch('/api/v1/auth/me', {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(changes),
  });
  if (!response.ok) throw await toAuthError(response);
  return response.json();
}

/**
 * Đổi mật khẩu (FR-USR-04). Sai mật khẩu hiện tại là 401 `INVALID_CREDENTIALS`; mật khẩu mới yếu là 400 `WEAK_PASSWORD`.
 * Thành công thì BFF đăng xuất các phiên khác và cấp lại cookie cho phiên này.
 */
export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  const response = await apiFetch('/api/v1/auth/password', {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ currentPassword, newPassword }),
  });
  if (!response.ok) throw await toAuthError(response);
}

