import { describe, expect, it } from 'vitest';
import {
  initialsOf, isDirty, profileChanges, validatePassword, validateProfile,
} from '../../src/features/profile/profileModel';

const saved = { fullName: 'Trần Minh Quân', phone: '0345484496' };

describe('luật hồ sơ (FR-USR-04), cùng luật với Backend', () => {
  it('họ tên bắt buộc, cắt khoảng trắng, tối đa 100 ký tự', () => {
    expect(validateProfile({ fullName: '', phone: '' }).fullName).toBe('Nhập họ và tên.');
    expect(validateProfile({ fullName: '   ', phone: '' }).fullName).toBe('Nhập họ và tên.');
    expect(validateProfile({ fullName: 'A'.repeat(101), phone: '' }).fullName).toMatch(/tối đa 100/);
    expect(validateProfile({ fullName: ` ${'A'.repeat(100)} `, phone: '' })).toEqual({});
  });

  it.each(['034548', '1345484496', '03454844961', '0345 484 496', 'abcdefghij', '+84345484496'])(
    'số điện thoại %s bị từ chối', (phone) => {
      expect(validateProfile({ fullName: 'Quân', phone }).phone).toBe('Số điện thoại gồm 10 chữ số, bắt đầu bằng 0.');
    });

  it('số điện thoại để trống hoặc đúng 10 chữ số bắt đầu bằng 0 thì hợp lệ', () => {
    expect(validateProfile({ fullName: 'Quân', phone: '' })).toEqual({});
    expect(validateProfile({ fullName: 'Quân', phone: ' 0912345678 ' })).toEqual({});
  });

  it('chỉ gửi trường đã đổi; xoá số thành null; không đổi gì thì không có thay đổi', () => {
    expect(profileChanges(saved, { ...saved })).toEqual({});
    expect(isDirty(saved, { ...saved, fullName: '  Trần Minh Quân  ' })).toBe(false); // chỉ khác khoảng trắng
    expect(profileChanges(saved, { ...saved, fullName: ' Tên mới ' })).toEqual({ fullName: 'Tên mới' });
    expect(profileChanges(saved, { ...saved, phone: '0912345678' })).toEqual({ phone: '0912345678' });
    expect(profileChanges(saved, { ...saved, phone: '  ' })).toEqual({ phone: null });
    expect(profileChanges({ fullName: 'Quân', phone: '' }, { fullName: 'Quân', phone: '' })).toEqual({});
  });
});

describe('luật mật khẩu', () => {
  const ok = { current: 'Demo@2026', next: 'ngua o chay tren de', confirm: 'ngua o chay tren de' };
  it('đủ điều kiện thì không có lỗi', () => expect(validatePassword(ok)).toEqual({}));
  it('thiếu mật khẩu hiện tại, mới ngắn hơn 8 hoặc dài hơn 128, trùng mật khẩu cũ, nhập lại lệch', () => {
    expect(validatePassword({ ...ok, current: '' }).current).toMatch(/hiện tại/);
    expect(validatePassword({ ...ok, next: '1234567', confirm: '1234567' }).next).toMatch(/ít nhất 8/);
    expect(validatePassword({ ...ok, next: 'x'.repeat(129), confirm: 'x'.repeat(129) }).next).toMatch(/tối đa 128/);
    expect(validatePassword({ ...ok, next: ok.current, confirm: ok.current }).next).toMatch(/khác mật khẩu hiện tại/);
    expect(validatePassword({ ...ok, confirm: 'khac' }).confirm).toMatch(/chưa khớp/);
  });
});

describe('chữ cái đầu ảnh đại diện', () => {
  it('lấy chữ cái đầu của tên cuối, rỗng thì KH', () => {
    expect(initialsOf('Trần Minh Quân')).toBe('Q');
    expect(initialsOf('  ')).toBe('KH');
  });
});
