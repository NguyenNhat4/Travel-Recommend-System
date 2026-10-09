// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import propertyFixture from '../../../shared/mocks/catalog/getProduct.200-property.json';
import variantsFixture from '../../../shared/mocks/catalog/listProducts.200-variants.json';
import similarFixture from '../../../shared/mocks/catalog/getSimilarProducts.200-default.json';
import popularFixture from '../../../shared/mocks/catalog/listProducts.200-popular.json';

const api = vi.hoisted(() => ({ getProduct: vi.fn(), listVariants: vi.fn(), listProducts: vi.fn(), getSimilarProducts: vi.fn(), trackProductView: vi.fn() }));
const travel = vi.hoisted(() => ({ currentPersona: null as unknown, navigate: vi.fn(), addToCart: vi.fn(), startBooking: vi.fn() }));
vi.mock('../../src/services/catalog', async (importOriginal) => ({ ...(await importOriginal<typeof import('../../src/services/catalog')>()), ...api }));
vi.mock('../../src/services/recsys', () => ({ fetchRecommendations: vi.fn().mockRejectedValue(new Error('x')) }));
vi.mock('../../src/context/TravelContext', () => ({ useTravel: () => travel }));

import { ProductDetailView } from '../../src/components/detail/ProductDetailView';
import { addDaysIso, todayVN } from '../../src/features/search/tripContext';

const WAIT = { timeout: 5000 };
// Cửa sổ mở bán của fixture bắt đầu 2026-10-01: chọn ngày trong cửa sổ, luôn sau hôm nay.
const IN = [addDaysIso(todayVN(), 3), '2026-10-05'].sort().at(-1)!;
const OUT = addDaysIso(IN, 2);

describe('ProductDetailView: trip context from the URL', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    travel.currentPersona = { id: 'VP1', name: 'Minh Anh' };
    api.getProduct.mockResolvedValue(JSON.parse(JSON.stringify(propertyFixture)));
    api.listVariants.mockResolvedValue(variantsFixture);
    api.getSimilarProducts.mockResolvedValue(similarFixture);
    api.listProducts.mockResolvedValue(popularFixture);
    travel.addToCart.mockResolvedValue(true);
    travel.startBooking.mockResolvedValue(null);
  });
  afterEach(() => {
    cleanup();
    window.history.replaceState({}, '', '/');
  });

  it('fills the hotel trip bar from ?checkIn&checkOut&adults&rooms when they fit the room', async () => {
    window.history.replaceState({}, '', `/product/nt-h-10?checkIn=${IN}&checkOut=${OUT}&adults=2&rooms=1`);
    render(<ProductDetailView productId="nt-h-10" />);
    await screen.findAllByRole('button', { name: /^Đặt ngay / }, WAIT);
    await waitFor(() => expect(screen.getByTestId('hotel-trip-bar').textContent).toContain(`${IN.slice(8, 10)}/${IN.slice(5, 7)} - ${OUT.slice(8, 10)}/${OUT.slice(5, 7)}, 2 đêm`));

    fireEvent.click(screen.getAllByRole('button', { name: /^Đặt ngay / })[0]);
    await waitFor(() => expect(travel.startBooking).toHaveBeenCalled());
    const [[booked]] = travel.startBooking.mock.calls[0];
    const { quantity, usingDate, checkOutDate: checkOut } = booked;
    const options = { guests: booked.guests };
    expect(usingDate).toBe(IN);
    expect(checkOut).toBe(OUT);
    expect(quantity).toBe(1);
    expect(options).toEqual({ guests: { adults: 2, children: 0 } });
  });

  it('ignores dates outside the booking window; guests over a room\'s capacity lock that room\'s Đặt ngay instead of being dropped', async () => {
    window.history.replaceState({}, '', `/product/nt-h-10?checkIn=2030-01-10&checkOut=2030-01-12&adults=5&rooms=1`);
    render(<ProductDetailView productId="nt-h-10" />);
    await screen.findAllByRole('button', { name: /^Đặt ngay / }, WAIT);

    // 2030-01-10 nằm ngoài cửa sổ đặt 3 tháng: giữ ngày mặc định. 5 khách vượt cả hai hạng phòng (tối đa 2 và 4 khách/phòng).
    expect(screen.getByTestId('hotel-trip-bar').textContent).not.toContain('10/01 - 12/01');
    const buttons = screen.getAllByRole('button', { name: /^Đặt ngay / }) as HTMLButtonElement[];
    expect(buttons.every((button) => button.disabled)).toBe(true);
    expect(screen.getAllByTestId('room-book-note')).toHaveLength(2);

    fireEvent.click(screen.getByRole('button', { name: /5 người lớn/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Tăng phòng' }));                // 2 phòng × 4 khách chứa được 5 khách
    expect((screen.getAllByRole('button', { name: /^Đặt ngay / })[1] as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(screen.getAllByRole('button', { name: /^Đặt ngay / })[1]);
    await waitFor(() => expect(travel.startBooking).toHaveBeenCalled());
    const [[booked]] = travel.startBooking.mock.calls[0];
    expect(booked.product).toMatchObject({ id: 'nt-h-10-r2' });
    expect(booked.quantity).toBe(2);
    expect(booked.guests).toEqual({ adults: 5, children: 0 });
    expect(booked.usingDate).not.toBe('2030-01-10');
  });
});
