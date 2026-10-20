// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import updated from '../../../shared/mocks/auth/updateMe.200-default.json';

const travel = vi.hoisted(() => ({
  currentPersona: { id: 'VP0092381', name: 'Nguyễn Minh Anh', email: 'minhanh@example.vn', phone: null as string | null },
  authReady: true,
  updateProfile: vi.fn(),
  openLoginModal: vi.fn(),
  showToast: vi.fn(),
}));
const auth = vi.hoisted(() => ({ changePassword: vi.fn() }));

vi.mock('../../src/context/TravelContext', () => ({ useTravel: () => travel }));
vi.mock('../../src/services/auth', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/services/auth')>()),
  changePassword: auth.changePassword,
}));

import { ProfileView } from '../../src/features/profile/ProfileView';
import { AuthError } from '../../src/services/auth';
import { ApiError } from '../../src/services/http';

const name = () => screen.getByLabelText('Họ và tên') as HTMLInputElement;
const phone = () => screen.getByLabelText(/Số điện thoại/) as HTMLInputElement;
const save = () => screen.getByRole('button', { name: 'Lưu thay đổi' }) as HTMLButtonElement;
const type = (el: HTMLElement, value: string) => fireEvent.change(el, { target: { value } });

describe('ProfileView — hồ sơ cá nhân', () => {
  beforeEach(() => {
    travel.currentPersona = { id: 'VP0092381', name: 'Nguyễn Minh Anh', email: 'minhanh@example.vn', phone: null };
    travel.authReady = true;
  });
  afterEach(() => { cleanup(); vi.clearAllMocks(); });

  it('hiện họ tên, email chỉ xem và số điện thoại; Lưu và Huỷ thay đổi tắt khi chưa đổi gì', () => {
    render(<ProfileView />);
    expect(name().value).toBe('Nguyễn Minh Anh');
    const mail = screen.getByLabelText('Email') as HTMLInputElement;
    expect(mail.value).toBe('minhanh@example.vn');
    expect(mail.readOnly).toBe(true);
    expect(phone().value).toBe('');
    expect(save().disabled).toBe(true);
    expect((screen.getByRole('button', { name: 'Huỷ thay đổi' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('báo lỗi dưới ô khi rời ô, không báo lúc đang gõ; Lưu tắt khi còn lỗi', () => {
    render(<ProfileView />);
    type(phone(), '034548');
    expect(screen.queryByText(/^10 chữ số, bắt đầu bằng 0\./)).not.toBeNull(); // chỉ là gợi ý chung
    expect(phone().getAttribute('aria-invalid')).toBeNull();
    fireEvent.blur(phone());
    expect(screen.getByText('Số điện thoại gồm 10 chữ số, bắt đầu bằng 0.')).toBeTruthy();
    expect(phone().getAttribute('aria-invalid')).toBe('true');
    expect(save().disabled).toBe(true);
    type(name(), '');
    fireEvent.blur(name());
    expect(screen.getByText('Nhập họ và tên.')).toBeTruthy();
  });

  it('lưu: chỉ gửi trường đã đổi, hiện thông báo, ô cập nhật theo kết quả Backend và nút Lưu tắt lại', async () => {
    travel.updateProfile.mockResolvedValue(updated);
    render(<ProfileView />);
    type(phone(), '0912345678');
    expect(save().disabled).toBe(false);
    fireEvent.click(save());
    await screen.findByText('Đã lưu thông tin của bạn.');
    expect(travel.updateProfile).toHaveBeenCalledWith({ phone: '0912345678' });
    expect(phone().value).toBe('0912345678'); // Backend trả về số đã chuẩn hoá
    expect(save().disabled).toBe(true);
  });

  it('xoá số điện thoại gửi null; đổi cả hai gửi cả hai', async () => {
    travel.currentPersona = { ...travel.currentPersona, phone: '0345484496' };
    travel.updateProfile.mockResolvedValue({ ...updated, phone: null });
    render(<ProfileView />);
    type(phone(), '');
    fireEvent.click(save());
    await waitFor(() => expect(travel.updateProfile).toHaveBeenCalledWith({ phone: null }));
    type(name(), 'Tên Khác');
    type(phone(), '0988888888');
    travel.updateProfile.mockResolvedValue({ ...updated, fullName: 'Tên Khác', phone: '0988888888' });
    fireEvent.click(save());
    await waitFor(() => expect(travel.updateProfile).toHaveBeenLastCalledWith({ fullName: 'Tên Khác', phone: '0988888888' }));
  });

  it('Huỷ thay đổi trả về giá trị đã lưu', () => {
    render(<ProfileView />);
    type(name(), 'Gõ dở');
    fireEvent.click(screen.getByRole('button', { name: 'Huỷ thay đổi' }));
    expect(name().value).toBe('Nguyễn Minh Anh');
    expect(save().disabled).toBe(true);
  });

  it.each([
    [new AuthError('x', 'VALIDATION_ERROR', 422), /chưa hợp lệ/],
    [new ApiError('x', 'NETWORK_ERROR', 0, true), /Mất kết nối/],
    [new AuthError('x', 'INTERNAL_ERROR', 500), /Chưa lưu được/],
  ])('lỗi khi lưu hiện thông báo rõ và giữ nguyên nội dung đang nhập (%#)', async (error, text) => {
    travel.updateProfile.mockRejectedValue(error);
    render(<ProfileView />);
    type(name(), 'Tên Mới');
    fireEvent.click(save());
    expect((await screen.findByRole('alert')).textContent).toMatch(text);
    expect(name().value).toBe('Tên Mới');
    expect(save().disabled).toBe(false);
  });

  it('chưa đăng nhập: mời đăng nhập thay vì hiện form', () => {
    travel.currentPersona = null as never;
    render(<ProfileView />);
    fireEvent.click(screen.getByRole('button', { name: /Đăng nhập/ }));
    expect(travel.openLoginModal).toHaveBeenCalledTimes(1);
    expect(screen.queryByLabelText('Họ và tên')).toBeNull();
    expect(screen.queryByRole('status', { name: 'Đang tải hồ sơ' })).toBeNull();
  });

  it('phiên đang khôi phục: hiện khung hồ sơ (ba ô, hai thẻ), chưa mời đăng nhập và chưa có form', () => {
    travel.currentPersona = null as never;
    travel.authReady = false;
    render(<ProfileView />);
    const skeleton = screen.getByRole('status', { name: 'Đang tải hồ sơ' });
    expect(skeleton.querySelectorAll(':scope > .rounded-2xl')).toHaveLength(2);
    expect(skeleton.querySelectorAll('.h-11.w-full')).toHaveLength(3);
    expect(screen.queryByRole('button', { name: /Đăng nhập/ })).toBeNull();
    expect(screen.queryByLabelText('Họ và tên')).toBeNull();
  });
});

describe('ProfileView — đổi mật khẩu', () => {
  beforeEach(() => { travel.currentPersona = { id: 'VP0092381', name: 'Nguyễn Minh Anh', email: 'minhanh@example.vn', phone: null }; });
  afterEach(() => { cleanup(); vi.clearAllMocks(); });

  const open = () => { render(<ProfileView />); fireEvent.click(screen.getByRole('button', { name: 'Đổi mật khẩu' })); };
  const fill = (current: string, next: string, confirm: string) => {
    type(screen.getByLabelText('Mật khẩu hiện tại'), current);
    type(screen.getByLabelText('Mật khẩu mới'), next);
    type(screen.getByLabelText('Nhập lại mật khẩu mới'), confirm);
  };
  const submit = () => fireEvent.click(screen.getAllByRole('button', { name: 'Đổi mật khẩu' }).at(-1)!);

  it('mở form khi bấm; mật khẩu mới ngắn hơn 8 ký tự bị chặn trong form, không gọi API', () => {
    open();
    fill('Demo@2026', '1234567', '1234567');
    submit();
    expect(screen.getByText(/ít nhất 8 ký tự/)).toBeTruthy();
    expect(auth.changePassword).not.toHaveBeenCalled();
  });

  it('nhập lại không khớp bị chặn', () => {
    open();
    fill('Demo@2026', 'ngua o chay tren de', 'khac hoan toan');
    submit();
    expect(screen.getByText('Mật khẩu nhập lại chưa khớp.')).toBeTruthy();
    expect(auth.changePassword).not.toHaveBeenCalled();
  });

  it('thành công: gọi API, đóng form và báo các thiết bị khác đã đăng xuất', async () => {
    auth.changePassword.mockResolvedValue(undefined);
    open();
    fill('Demo@2026', 'ngua o chay tren de', 'ngua o chay tren de');
    submit();
    await screen.findByText('Đã đổi mật khẩu. Các thiết bị khác đã được đăng xuất.');
    expect(auth.changePassword).toHaveBeenCalledWith('Demo@2026', 'ngua o chay tren de');
    expect(screen.queryByLabelText('Mật khẩu hiện tại')).toBeNull();
  });

  it('sai mật khẩu hiện tại hiện lỗi dưới ô đó và giữ form mở', async () => {
    auth.changePassword.mockRejectedValue(new AuthError('Email hoặc mật khẩu không đúng.', 'INVALID_CREDENTIALS', 401));
    open();
    fill('sai-roi', 'ngua o chay tren de', 'ngua o chay tren de');
    submit();
    expect(await screen.findByText('Mật khẩu hiện tại không đúng.')).toBeTruthy();
    expect(screen.getByLabelText('Mật khẩu hiện tại')).toBeTruthy();
  });

  it('mật khẩu yếu theo Backend hiện lỗi dưới ô mật khẩu mới', async () => {
    auth.changePassword.mockRejectedValue(new AuthError('x', 'WEAK_PASSWORD', 400));
    open();
    fill('Demo@2026', 'password1234', 'password1234');
    submit();
    expect((await screen.findByText(/chưa đủ an toàn/)).id).toBe('pw-next-error');
  });

  it('nút Hiện đổi kiểu ô nhập', () => {
    open();
    const input = screen.getByLabelText('Mật khẩu mới') as HTMLInputElement;
    expect(input.type).toBe('password');
    fireEvent.click(screen.getAllByRole('button', { name: /Hiện/ })[1]);
    expect(input.type).toBe('text');
  });
});
