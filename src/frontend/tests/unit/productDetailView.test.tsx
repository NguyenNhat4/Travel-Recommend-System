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
    const [unit, quantity, usingDate, checkOut, options] = travel.addToCart.mock.calls[0];
    expect(unit).toMatchObject({ id: 'nt-h-10-r2', unitPrice: 4150000, taxonomy: 'hotel' });
    expect(quantity).toBe(1);
    expect(usingDate).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(checkOut > usingDate).toBe(true);
    expect(options).toEqual({ guests: { adults: 1, children: 0 } });
  });

  it('khách sạn: gợi ý sức chứa; vượt sức chứa thì khoá nút đặt và gợi ý thêm phòng, thêm phòng xong gửi số phòng và số khách', async () => {
    api.getProduct.mockResolvedValue(hotelProperty());
    render(<ProductDetailView productId="nt-h-10" />);
    await screen.findAllByRole('radio', {}, WAIT);                                    // phòng rẻ nhất (nt-h-10-r1, tối đa 2 khách) được chọn sẵn
    // Phòng hiện ra trước khi effect đặt lại ngày/số khách theo phòng chạy; bấm sớm thì effect đó ghi đè lựa chọn.
    await waitFor(() => expect(document.querySelector<HTMLInputElement>('input[type="date"]')?.value).toBeTruthy(), WAIT);
    expect(screen.getByText('Tối đa 2 khách/phòng')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Thêm người lớn' }));
    fireEvent.click(screen.getByRole('button', { name: 'Thêm trẻ em' }));
    const issue = screen.getByTestId('capacity-issue');
    expect(issue.textContent).toContain('3 khách vượt sức chứa 2 khách của 1 phòng. Cần ít nhất 2 phòng.');
    expect((screen.getByRole('button', { name: 'Thêm vào giỏ hàng' }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole('button', { name: 'Đặt ngay' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Thêm 1 phòng' }));
    expect(screen.queryByTestId('capacity-issue')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Thêm vào giỏ hàng' }));
    await waitFor(() => expect(travel.addToCart).toHaveBeenCalled());
    const [unit, quantity, , , options] = travel.addToCart.mock.calls[0];
    expect(unit).toMatchObject({ id: 'nt-h-10-r1' });
    expect(quantity).toBe(2);
    expect(options).toEqual({ guests: { adults: 2, children: 1 } });
  });

  it('vé tham quan: hai bộ đếm Người lớn/Trẻ em kèm đơn giá từng loại; ước tính theo giá trẻ em; gửi guests', async () => {
    api.getProduct.mockResolvedValue({
      ...ticketFixture, productId: 'nt-a-vinwonders-buggy', name: 'Vé VinWonders + Buggy', taxonomy: 'attraction', unitPrice: 1500000,
      availableFrom: '2026-10-01', availableTo: '2027-03-31', attributes: { childPrice: 504000 },
    });
    render(<ProductDetailView productId="nt-a-vinwonders-buggy" />);
    await screen.findByRole('heading', { name: 'Vé VinWonders + Buggy' });
    expect(screen.getByText('Từ 12 tuổi · 1.500.000 ₫')).toBeTruthy();
    expect(screen.getByText('Dưới 12 tuổi · 504.000 ₫')).toBeTruthy();
    expect(screen.getByTestId('estimate-total').textContent).toContain('1.500.000');
    fireEvent.click(screen.getByRole('button', { name: 'Thêm người lớn' }));
    fireEvent.click(screen.getByRole('button', { name: 'Thêm trẻ em' }));
    expect(screen.getByTestId('estimate-lines').textContent).toContain('2 × 1.500.000');
    expect(screen.getByTestId('estimate-lines').textContent).toContain('1 × 504.000');
    expect(screen.getByTestId('estimate-total').textContent).toContain('3.504.000');
    fireEvent.click(screen.getByRole('button', { name: 'Thêm vào giỏ hàng' }));
    await waitFor(() => expect(travel.addToCart).toHaveBeenCalled());
    const [unit, quantity, , checkOut, options] = travel.addToCart.mock.calls[0];
    expect(unit).toMatchObject({ id: 'nt-a-vinwonders-buggy' });
    expect(quantity).toBe(3);
    expect(checkOut).toBeUndefined();
    expect(options).toEqual({ guests: { adults: 2, children: 1 } });
  });

  it('vé không có giá trẻ em riêng và chuyến bay: trẻ em cùng giá người lớn, chuyến bay có ghi chú về giá vé trẻ em', async () => {
    api.getProduct.mockResolvedValue({
      ...ticketFixture, productId: 'nt-f-vj601', name: 'VietJet Air VJ601', taxonomy: 'flight', unitPrice: 950000,
      availableFrom: '2026-10-19', availableTo: '2026-10-19', attributes: { flightNumber: 'VJ601' },
    });
    render(<ProductDetailView productId="nt-f-vj601" />);
    await screen.findByRole('heading', { name: 'VietJet Air VJ601' });
    expect(screen.getByText('Dưới 12 tuổi · cùng giá người lớn')).toBeTruthy();
    expect(screen.queryByTestId('flight-child-note')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Thêm trẻ em' }));
    expect(screen.getByTestId('flight-child-note').textContent).toBe('Chưa có giá vé trẻ em riêng: trẻ em và em bé có ghế riêng, tính giá người lớn.');
    expect(screen.getByTestId('estimate-total').textContent).toContain('1.900.000');
  });

  it('combo: chỉ có bộ đếm số gói, chỉ gửi quantity', async () => {
    api.getProduct.mockResolvedValue({
      ...ticketFixture, productId: 'nt-c-01', name: 'Combo 3N2Đ', taxonomy: 'combo', unitPrice: 5200000,
      availableFrom: '2026-10-01', availableTo: '2027-03-31', attributes: {},
    });
    render(<ProductDetailView productId="nt-c-01" />);
    await screen.findByRole('heading', { name: 'Combo 3N2Đ' });
    expect(screen.queryByRole('button', { name: 'Thêm người lớn' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Thêm gói' }));
    expect(screen.getByTestId('estimate-total').textContent).toContain('10.400.000');
    fireEvent.click(screen.getByRole('button', { name: 'Thêm vào giỏ hàng' }));
    await waitFor(() => expect(travel.addToCart).toHaveBeenCalled());
    const [, quantity, , , options] = travel.addToCart.mock.calls[0];
    expect(quantity).toBe(2);
    expect(options).toBeUndefined();
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
    expect(travel.addToCart.mock.calls[0][4]).toEqual({ silent: true, guests: { adults: 1, children: 0 } });
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
