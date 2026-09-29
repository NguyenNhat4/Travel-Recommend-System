// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import propertyFixture from '../../../shared/mocks/catalog/getProduct.200-property.json';
import ticketFixture from '../../../shared/mocks/catalog/getProduct.200-default.json';
import variantsFixture from '../../../shared/mocks/catalog/listProducts.200-variants.json';
import similarFixture from '../../../shared/mocks/catalog/getSimilarProducts.200-default.json';
import popularFixture from '../../../shared/mocks/catalog/listProducts.200-popular.json';

const api = vi.hoisted(() => ({
  getProduct: vi.fn(),
  listVariants: vi.fn(),
  listProducts: vi.fn(),
  getSimilarProducts: vi.fn(),
  trackProductView: vi.fn(),
}));
const recsys = vi.hoisted(() => ({ fetchRecommendations: vi.fn() }));
const travel = vi.hoisted(() => ({
  currentPersona: { id: 'VP0000001', name: 'Nguyễn Minh Anh' } as unknown,
  navigate: vi.fn(),
  addToCart: vi.fn(),
}));

vi.mock('../../src/services/catalog', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/services/catalog')>()),
  ...api,
}));
vi.mock('../../src/services/recsys', () => recsys);
vi.mock('../../src/context/TravelContext', () => ({ useTravel: () => travel }));

import { ProductDetailView } from '../../src/components/detail/ProductDetailView';
import { ApiError } from '../../src/services/http';

const hotelProperty = () => JSON.parse(JSON.stringify(propertyFixture));
// Nhiều worker chạy song song làm render chậm: chờ lâu hơn mặc định 1 giây để test không chập chờn.
const WAIT = { timeout: 5000 };

describe('ProductDetailView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    travel.currentPersona = { id: 'VP0000001', name: 'Nguyễn Minh Anh' };
    api.listVariants.mockResolvedValue(variantsFixture);
    api.getSimilarProducts.mockResolvedValue(similarFixture);
    api.listProducts.mockResolvedValue(popularFixture);
    recsys.fetchRecommendations.mockRejectedValue(new Error('không cần trong test'));
    travel.addToCart.mockResolvedValue(true);
  });
  afterEach(() => cleanup());

  it('loads the real product and lists its rooms; the cart gets the ROOM, not the hotel', async () => {
    api.getProduct.mockResolvedValue(hotelProperty());
    render(<ProductDetailView productId="nt-h-10" />);

    expect(await screen.findByRole('heading', { name: 'Vinpearl Resort & Spa Nha Trang Bay' }, WAIT)).toBeTruthy();
    expect(api.getProduct).toHaveBeenCalledWith('nt-h-10', expect.anything());
    await waitFor(() => expect(api.listVariants).toHaveBeenCalledWith('nt-h-10', expect.anything()), WAIT);

    const rooms = await screen.findAllByRole('radio', {}, WAIT);
    expect(rooms).toHaveLength(2);
    expect(rooms[0].getAttribute('aria-checked')).toBe('true'); // phòng rẻ nhất đặt được được chọn sẵn

    fireEvent.click(rooms[1]);
    fireEvent.click(screen.getByRole('button', { name: 'Thêm vào giỏ hàng' }));
    await waitFor(() => expect(travel.addToCart).toHaveBeenCalled());
    const [unit, quantity, usingDate, checkOut] = travel.addToCart.mock.calls[0];
    expect(unit).toMatchObject({ id: 'nt-h-10-r2', unitPrice: 4150000, taxonomy: 'hotel' });
    expect(quantity).toBe(1);
    expect(usingDate).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(checkOut > usingDate).toBe(true);
  });

  it('disables booking when a hotel has no bookable room', async () => {
    api.getProduct.mockResolvedValue({ ...hotelProperty(), variantSummary: { count: 0, minPrice: null, maxPrice: null, maxOccupancy: null } });
    api.listVariants.mockResolvedValue({ ...variantsFixture, results: [], total: 0 });
    render(<ProductDetailView productId="nt-h-10" />);
    expect(await screen.findByText(/chưa có hạng phòng nào trên V-OTA/)).toBeTruthy();
    expect((screen.getByRole('button', { name: 'Thêm vào giỏ hàng' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('books a product without variants directly and "Đặt ngay" goes to checkout', async () => {
    api.getProduct.mockResolvedValue(ticketFixture);
    render(<ProductDetailView productId="nt-h-01" />);
    await screen.findByRole('heading', { name: ticketFixture.name });
    expect(api.listVariants).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Đặt ngay' }));
    await waitFor(() => expect(travel.navigate).toHaveBeenCalledWith('/checkout'));
    expect(travel.addToCart.mock.calls[0][0]).toMatchObject({ id: 'nt-h-01' });
  });

  it('shows similar products from the API', async () => {
    api.getProduct.mockResolvedValue(ticketFixture);
    render(<ProductDetailView productId="nt-h-01" />);
    expect(await screen.findByText(similarFixture.results[0].name)).toBeTruthy();
  });

  it('shows the "no longer on V-OTA" page with popular products on 404', async () => {
    api.getProduct.mockRejectedValue(new ApiError('Sản phẩm này không còn trên V-OTA.', 'PRODUCT_NOT_FOUND', 404, false));
    render(<ProductDetailView productId="nt-hotel-01" />);
    expect(await screen.findByText('Sản phẩm này không còn trên V-OTA')).toBeTruthy();
    expect(await screen.findByText(popularFixture.results[0].name)).toBeTruthy();
    expect(api.trackProductView).not.toHaveBeenCalled();
  });

  it('records product_view once for a signed-in user, never for a guest', async () => {
    api.getProduct.mockResolvedValue(ticketFixture);
    const { rerender } = render(<ProductDetailView productId="nt-h-01" />);
    await screen.findByRole('heading', { name: ticketFixture.name });
    rerender(<ProductDetailView productId="nt-h-01" />);
    await waitFor(() => expect(api.trackProductView).toHaveBeenCalledTimes(1));
    expect(api.trackProductView).toHaveBeenCalledWith('nt-h-01');

    cleanup();
    api.trackProductView.mockClear();
    travel.currentPersona = null;
    render(<ProductDetailView productId="nt-h-01" />);
    await screen.findByRole('heading', { name: ticketFixture.name });
    expect(api.trackProductView).not.toHaveBeenCalled();
  });

  it('offers retry on a retryable error', async () => {
    api.getProduct.mockRejectedValueOnce(new ApiError('Mất kết nối. Vui lòng thử lại.', 'NETWORK_ERROR', 0, true))
      .mockResolvedValue(ticketFixture);
    render(<ProductDetailView productId="nt-h-01" />);
    fireEvent.click(await screen.findByRole('button', { name: 'Thử lại' }));
    expect(await screen.findByRole('heading', { name: ticketFixture.name })).toBeTruthy();
  });
});
