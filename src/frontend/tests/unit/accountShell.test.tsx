// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

const nav = vi.hoisted(() => ({ pathname: '/profile' }));
vi.mock('next/navigation', () => ({ usePathname: () => nav.pathname }));
vi.mock('../../src/context/TravelContext', () => ({
  useTravel: () => ({ currentPersona: { id: 'VP1', name: 'Trần Minh Quân', email: 'q@example.vn' } }),
}));

import { AccountShell } from '../../src/features/profile/AccountShell';

describe('AccountShell — khung hai trang tài khoản', () => {
  afterEach(cleanup);

  it('có hai mục trỏ đúng địa chỉ; /profile là mục đang mở ở trang hồ sơ', () => {
    nav.pathname = '/profile';
    render(<AccountShell><p>nội dung</p></AccountShell>);
    const profile = screen.getByRole('link', { name: 'Hồ sơ cá nhân' });
    const history = screen.getByRole('link', { name: 'Lịch sử đặt chỗ' });
    expect(profile.getAttribute('href')).toBe('/profile');
    expect(history.getAttribute('href')).toBe('/profile/booking_history');
    expect(profile.getAttribute('aria-current')).toBe('page');
    expect(history.getAttribute('aria-current')).toBeNull();
    expect(screen.getByText('nội dung')).toBeTruthy();
  });

  it('ở /profile/booking_history chỉ mục lịch sử được đánh dấu, hồ sơ thì không', () => {
    nav.pathname = '/profile/booking_history';
    render(<AccountShell><p>x</p></AccountShell>);
    expect(screen.getByRole('link', { name: 'Lịch sử đặt chỗ' }).getAttribute('aria-current')).toBe('page');
    expect(screen.getByRole('link', { name: 'Hồ sơ cá nhân' }).getAttribute('aria-current')).toBeNull();
  });

  it('thẻ người dùng hiện tên và email', () => {
    render(<AccountShell><p>x</p></AccountShell>);
    expect(screen.getByText('Trần Minh Quân')).toBeTruthy();
    expect(screen.getByText('q@example.vn')).toBeTruthy();
  });
});
