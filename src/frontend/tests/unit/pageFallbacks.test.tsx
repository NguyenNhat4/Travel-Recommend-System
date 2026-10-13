// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

// View của trang "treo" (như lúc trang mới tải, `useSearchParams` chưa đọc được) để ranh giới Suspense của trang hiện fallback.
const { Suspended } = vi.hoisted(() => {
  const { use } = require('react') as typeof import('react');
  const never = new Promise<never>(() => {});
  return { Suspended: () => { use(never); return null; } };
});

vi.mock('../../src/components/search/SearchView', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/components/search/SearchView')>()),
  SearchView: Suspended,
}));
vi.mock('../../src/components/checkout/CheckoutView', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/components/checkout/CheckoutView')>()),
  CheckoutView: Suspended,
}));
vi.mock('../../src/features/bookings/BookingHistoryView', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/bookings/BookingHistoryView')>()),
  BookingHistoryView: Suspended,
}));

import SearchPage from '../../src/app/(storefront)/search/page';
import CheckoutPage from '../../src/app/(storefront)/checkout/page';
import BookingHistoryPage from '../../src/app/(storefront)/profile/booking_history/page';

describe('fallback Suspense của trang: khung trang thay vì để trống', () => {
  afterEach(cleanup);

  it('/search: ô tìm kiếm, tiêu đề, tab và ba hàng nhóm bốn ô', () => {
    render(<SearchPage />);
    const skeleton = screen.getByRole('status', { name: 'Đang tải trang tìm kiếm' });
    expect(skeleton.getAttribute('aria-busy')).toBe('true');
    expect(skeleton.querySelectorAll('.aspect-square')).toHaveLength(12);
    expect(skeleton.querySelector('.animate-pulse, .animate-spin')).toBeNull();
  });

  it('/checkout: cùng khung với lúc đơn nháp chưa về', () => {
    render(<CheckoutPage />);
    const skeleton = screen.getByRole('status', { name: 'Đang tải thông tin thanh toán' });
    expect(skeleton.querySelector(':scope > .border-b')!.querySelectorAll('.w-7.h-7.rounded-full')).toHaveLength(3);
    expect(document.querySelector('.animate-spin')).toBeNull();
  });

  it('/profile/booking_history: tiêu đề thật, thanh lọc khung và ba thẻ đơn khung', () => {
    render(<BookingHistoryPage />);
    expect(screen.getByRole('heading', { level: 1, name: 'Lịch sử đặt chỗ' })).toBeTruthy();
    const skeleton = screen.getByRole('status', { name: 'Đang tải đơn hàng' });
    // Thanh tab + chip, dòng số đơn + lọc ngày, ba thẻ đơn.
    expect(skeleton.querySelectorAll(':scope > [aria-hidden="true"]')).toHaveLength(5);
    expect(screen.queryByRole('tab')).toBeNull();
  });
});
