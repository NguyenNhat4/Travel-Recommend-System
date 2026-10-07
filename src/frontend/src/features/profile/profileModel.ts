/**
 * Quy tắc của trang hồ sơ (FR-USR-04). Cùng luật với Backend (`UpdateProfileRequest`): họ tên 1–100 ký tự sau khi cắt khoảng
 * trắng; số điện thoại để trống hoặc đúng 10 chữ số bắt đầu bằng 0; mật khẩu mới 8–128 ký tự. Backend là nơi quyết định cuối cùng.
 */
export const NAME_MAX = 100;
export const PASSWORD_MIN = 8;
export const PASSWORD_MAX = 128;
const PHONE_PATTERN = /^0[0-9]{9}$/;

export interface ProfileForm {
  fullName: string;
  phone: string;
}

export type ProfileErrors = Partial<Record<keyof ProfileForm, string>>;

export function validateProfile(form: ProfileForm): ProfileErrors {
  const errors: ProfileErrors = {};
  const name = form.fullName.trim();
  if (!name) errors.fullName = 'Nhập họ và tên.';
  else if (name.length > NAME_MAX) errors.fullName = `Họ và tên tối đa ${NAME_MAX} ký tự.`;
  const phone = form.phone.trim();
  if (phone && !PHONE_PATTERN.test(phone)) errors.phone = 'Số điện thoại gồm 10 chữ số, bắt đầu bằng 0.';
  return errors;
}

/** Chỉ các trường đã đổi, đúng hình dạng body của `PATCH /auth/me`; `phone: null` là xoá số. */
export function profileChanges(saved: ProfileForm, form: ProfileForm): { fullName?: string; phone?: string | null } {
  const changes: { fullName?: string; phone?: string | null } = {};
  if (form.fullName.trim() !== saved.fullName.trim()) changes.fullName = form.fullName.trim();
  if (form.phone.trim() !== saved.phone.trim()) changes.phone = form.phone.trim() || null;
  return changes;
}

export function isDirty(saved: ProfileForm, form: ProfileForm): boolean {
  return Object.keys(profileChanges(saved, form)).length > 0;
}

export interface PasswordForm {
  current: string;
  next: string;
  confirm: string;
}

export type PasswordErrors = Partial<Record<keyof PasswordForm, string>>;

export function validatePassword(form: PasswordForm): PasswordErrors {
  const errors: PasswordErrors = {};
  if (!form.current) errors.current = 'Nhập mật khẩu hiện tại.';
  if (form.next.length < PASSWORD_MIN) errors.next = `Mật khẩu mới cần ít nhất ${PASSWORD_MIN} ký tự.`;
  else if (form.next.length > PASSWORD_MAX) errors.next = `Mật khẩu mới tối đa ${PASSWORD_MAX} ký tự.`;
  else if (form.next === form.current) errors.next = 'Mật khẩu mới cần khác mật khẩu hiện tại.';
  if (form.confirm !== form.next) errors.confirm = 'Mật khẩu nhập lại chưa khớp.';
  return errors;
}

/** Chữ cái đầu của họ tên cho ảnh đại diện: hai từ cuối, như `personaFromUser`. */
export function initialsOf(fullName: string): string {
  return fullName.split(/\s+/).filter(Boolean).slice(-1).map((w) => w[0]).join('').toUpperCase() || 'KH';
}
