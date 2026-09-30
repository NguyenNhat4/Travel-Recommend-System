// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import propertyFixture from '../../../shared/mocks/catalog/getProduct.200-property.json';
import variantsFixture from '../../../shared/mocks/catalog/listProducts.200-variants.json';
import similarFixture from '../../../shared/mocks/catalog/getSimilarProducts.200-default.json';
import popularFixture from '../../../shared/mocks/catalog/listProducts.200-popular.json';

const api = vi.hoisted(() => ({ getProduct: vi.fn(), listVariants: vi.fn(), listProducts: vi.fn(), getSimilarProducts: vi.fn(), trackProductView: vi.fn() }));
const travel = vi.hoisted(() => ({ currentPersona: null as unknown, navigate: vi.fn(), addToCart: vi.fn() }));
vi.mock('../../src/services/catalog', async (importOriginal) => ({ ...(await importOriginal<typeof import('../../src/services/catalog')>()), ...api }));
vi.mock('../../src/services/recsys', () => ({ fetchRecommendations: vi.fn().mockRejectedValue(new Error('x')) }));
vi.mock('../../src/context/TravelContext', () => ({ useTravel: () => travel }));

import { ProductDetailView } from '../../src/components/detail/ProductDetailView';
import { addDaysIso, todayVN } from '../../src/features/search/tripContext';

const WAIT = { timeout: 5000 };
const dateInputs = () => Array.from(document.querySelectorAll<HTMLInputElement>('input[type="date"]'));
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
  });
  afterEach(() => {
    cleanup();
    window.history.replaceState({}, '', '/');
  });

  it('fills the booking box from ?checkIn&checkOut&adults&rooms when they fit the room', async () => {
    window.history.replaceState({}, '', `/product/nt-h-10?checkIn=${IN}&checkOut=${OUT}&adults=2&rooms=1`);
    render(<ProductDetailView productId="nt-h-10" />);
    await screen.findAllByRole('radio', {}, WAIT);
    await waitFor(() => expect(dateInputs()[0].value).toBe(IN));

    fireEvent.click(screen.getByRole('button', { name: 'Thêm vào giỏ hàng' }));
    await waitFor(() => expect(travel.addToCart).toHaveBeenCalled());
    const [, quantity, usingDate, checkOut, options] = travel.addToCart.mock.calls[0];
    expect(usingDate).toBe(IN);
    expect(checkOut).toBe(OUT);
    expect(quantity).toBe(1);
    expect(options).toEqual({ guests: { adults: 2, children: 0 } });
  });

  it('ignores dates outside the room window and guests over its capacity, keeping the defaults', async () => {
    window.history.replaceState({}, '', `/product/nt-h-10?checkIn=2030-01-10&checkOut=2030-01-12&adults=5&rooms=1`);
    render(<ProductDetailView productId="nt-h-10" />);
    await screen.findAllByRole('radio', {}, WAIT);
    await waitFor(() => expect(dateInputs()[0].value).not.toBe(''));

    fireEvent.click(screen.getByRole('button', { name: 'Thêm vào giỏ hàng' }));
    await waitFor(() => expect(travel.addToCart).toHaveBeenCalled());
    const [, , usingDate, , options] = travel.addToCart.mock.calls[0];
    expect(usingDate).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(usingDate).not.toBe('2030-01-10');
    expect(options).toEqual({ guests: { adults: 1, children: 0 } });
  });
});
