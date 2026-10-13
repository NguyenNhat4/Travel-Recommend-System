// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import familyCart from '../../../shared/mocks/booking/getCart.200-family.json';
import unavailableCart from '../../../shared/mocks/booking/getCart.200-item-unavailable.json';

const api = vi.hoisted(() => ({ getProduct: vi.fn(), fetchRecommendations: vi.fn() }));
const http = vi.hoisted(() => ({ fetch: vi.fn() }));
const travel = vi.hoisted(() => ({
  cart: null as unknown,
  currentPersona: { id: 'VP0000001', name: 'Nguyễn Minh Anh' } as unknown,
  authReady: true,
  navigate: vi.fn(),
  removeFromCart: vi.fn(),
  updateCartItem: vi.fn(),
  addToCart: vi.fn(),
  openLoginModal: vi.fn(),
  activeEvents: [] as unknown[],
}));

vi.mock('../../src/context/AssistantProvider', () => ({ useAssistant: () => ({ openFloatingWidget: vi.fn() }) }));
vi.mock('../../src/services/catalog', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/services/catalog')>()),
  getProduct: api.getProduct,
}));
vi.mock('../../src/services/recsys', () => ({ fetchRecommendations: api.fetchRecommendations }));
vi.mock('../../src/context/TravelContext', () => ({ useTravel: () => travel }));

import { CartView } from '../../src/components/cart/CartView';
import { ApiError } from '../../src/services/http';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
/** `formatVnd` chèn khoảng trắng không ngắt trước ₫; đưa về khoảng trắng thường để so chuỗi. */
const textOf = (el: Element) => (el.textContent ?? '').replace(/\u00a0/g, ' ');
const rowOf = (text: string) => screen.getAllByTestId('cart-item').find((row) => row.textContent?.includes(text))!;

describe('CartView — khách và dòng giá theo loại khách', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    travel.cart = clone(familyCart);
    travel.currentPersona = { id: 'VP0000001', name: 'Nguyễn Minh Anh' };
    api.fetchRecommendations.mockResolvedValue({ destination: 'Nha Trang', recommendations: [] });
    vi.stubGlobal('fetch', http.fetch);
    api.getProduct.mockResolvedValue({ productId: 'nt-a-vinwonders-buggy', attributes: { childPrice: 504000 } });
    travel.updateCartItem.mockResolvedValue(null);
  });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it('mỗi mục hiện đoàn khách ("2 người lớn · 1 trẻ em") và các dòng giá của Backend', () => {
    render(<CartView />);
    const ticket = rowOf('VinWonders');
    expect(within(ticket).getByTestId('cart-item-summary').textContent).toBe('Ngày dùng: 2026-10-18 · 2 người lớn · 1 trẻ em');
    expect(within(ticket).getByTestId('fare-lines').textContent).toContain('2 × 1.500.000');
    expect(within(ticket).getByTestId('fare-lines').textContent).toContain('1 × 504.000');
    expect(screen.getAllByText('3.504.000 ₫').length).toBeGreaterThan(0);          // tổng lấy từ CartResponse
  });

  it('Thanh toán khi đã đăng nhập: vào /checkout ngay', () => {
    render(<CartView />);
    fireEvent.click(screen.getByRole('button', { name: /Tiến hành đặt chỗ/ }));
    expect(travel.navigate).toHaveBeenCalledWith('/checkout');
    expect(travel.openLoginModal).not.toHaveBeenCalled();
  });

  it('Thanh toán khi chưa đăng nhập: mở hộp đăng nhập, đăng nhập xong mới vào /checkout', () => {
    travel.currentPersona = null;
    render(<CartView />);
    fireEvent.click(screen.getByRole('button', { name: /Tiến hành đặt chỗ/ }));
    expect(travel.navigate).not.toHaveBeenCalled();
    expect(travel.openLoginModal).toHaveBeenCalledTimes(1);
    travel.openLoginModal.mock.calls[0][0]();
    expect(travel.navigate).toHaveBeenCalledWith('/checkout');
  });

  it('[Sửa] mở bộ đếm với số khách hiện tại; giá vé trẻ em hiện sau khi tải thuộc tính sản phẩm', async () => {
    render(<CartView />);
    const ticket = rowOf('VinWonders');
    fireEvent.click(within(ticket).getByRole('button', { name: /^Sửa số khách của/ }));
    const editor = within(ticket).getByTestId('guest-editor');
    expect(within(editor).getByLabelText('Bớt người lớn')).toBeTruthy();
    expect(editor.textContent).toContain('Dưới 12 tuổi');
    expect(editor.textContent).not.toContain('cùng giá người lớn');               // chưa biết giá thì không khẳng định
    await waitFor(() => expect(textOf(editor)).toContain('Dưới 12 tuổi · 504.000 ₫'));
    expect(api.getProduct).toHaveBeenCalledWith('nt-a-vinwonders-buggy', expect.anything());
    expect((within(editor).getByRole('button', { name: 'Cập nhật' }) as HTMLButtonElement).disabled).toBe(true);   // chưa đổi gì
  });

  it('bớt trẻ em rồi Cập nhật: PATCH số khách và số lượng của đúng mục, xong thì đóng bộ đếm', async () => {
    render(<CartView />);
    const ticket = rowOf('VinWonders');
    fireEvent.click(within(ticket).getByRole('button', { name: /^Sửa số khách của/ }));
    const editor = within(ticket).getByTestId('guest-editor');
    fireEvent.click(within(editor).getByLabelText('Bớt trẻ em'));
    fireEvent.click(within(editor).getByRole('button', { name: 'Cập nhật' }));
    await waitFor(() => expect(travel.updateCartItem).toHaveBeenCalledWith('ci-vinwonders', { quantity: 2, guests: { adults: 2, children: 0 } }));
    await waitFor(() => expect(within(ticket).queryByTestId('guest-editor')).toBeNull());
  });

  it('giỏ chỉ giữ tour, trải nghiệm, tiện ích: có ghi chú khách sạn và vé máy bay đặt trực tiếp; không còn khối "Thường được đặt cùng chuyến"', () => {
    render(<CartView />);
    expect(screen.getByTestId('cart-direct-note').textContent).toContain('Khách sạn và vé máy bay không nằm trong giỏ');
    expect(screen.queryByText(/Thường được đặt cùng chuyến/)).toBeNull();
    expect(api.fetchRecommendations).not.toHaveBeenCalled();
    expect(http.fetch).not.toHaveBeenCalled();
  });

  it('khách chưa đăng nhập vẫn xem và sửa được giỏ của mình, không bị yêu cầu đăng nhập', () => {
    travel.currentPersona = null;
    render(<CartView />);
    expect(screen.queryByText('Đăng nhập để xem giỏ hàng')).toBeNull();
    expect(rowOf('VinWonders')).toBeTruthy();
    expect(within(rowOf('VinWonders')).getByRole('button', { name: /^Sửa số khách của/ })).toBeTruthy();
    expect((screen.getByRole('button', { name: /Tiến hành đặt chỗ/ }) as HTMLButtonElement).disabled).toBe(false);
    expect(travel.openLoginModal).not.toHaveBeenCalled();
  });

  it('Backend từ chối: bộ đếm giữ nguyên để khách sửa tiếp (context đã báo lỗi bằng toast)', async () => {
    travel.updateCartItem.mockResolvedValue(new ApiError('Vượt sức chứa.', 'VALIDATION_ERROR', 400, false));
    render(<CartView />);
    const ticket = rowOf('VinWonders');
    fireEvent.click(within(ticket).getByRole('button', { name: /^Sửa số khách của/ }));
    const editor = within(ticket).getByTestId('guest-editor');
    fireEvent.click(within(editor).getByLabelText('Thêm người lớn'));
    fireEvent.click(within(editor).getByRole('button', { name: 'Cập nhật' }));
    await waitFor(() => expect(travel.updateCartItem).toHaveBeenCalled());
    expect(within(ticket).getByTestId('guest-editor')).toBeTruthy();
  });

  it('Huỷ đóng bộ đếm mà không gọi Backend', () => {
    render(<CartView />);
    const ticket = rowOf('VinWonders');
    fireEvent.click(within(ticket).getByRole('button', { name: /^Sửa số khách của/ }));
    fireEvent.click(within(ticket).getByRole('button', { name: 'Huỷ' }));
    expect(within(ticket).queryByTestId('guest-editor')).toBeNull();
    expect(travel.updateCartItem).not.toHaveBeenCalled();
  });

  it('mục hết chỗ không có nút Sửa, chỉ có Xóa; nút đặt chỗ bị khoá', () => {
    travel.cart = clone(unavailableCart);
    render(<CartView />);
    const sold = rowOf('Vinpearl Safari');
    expect(within(sold).queryByRole('button', { name: /^Sửa số khách của/ })).toBeNull();
    expect(within(sold).getByText('Xóa')).toBeTruthy();
    expect((screen.getByRole('button', { name: /Tiến hành đặt chỗ/ }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('giỏ chưa về: hiện khung giỏ (một nhóm hai mục và hộp tóm tắt) thay cho vòng xoay, không báo giỏ trống', () => {
    travel.cart = null;
    render(<CartView />);
    const skeleton = screen.getByRole('status', { name: 'Đang tải giỏ hàng' });
    expect(skeleton.getAttribute('aria-busy')).toBe('true');
    expect(skeleton.querySelectorAll('.divide-y > div')).toHaveLength(2);
    expect(screen.queryByText('Giỏ hàng của bạn đang trống')).toBeNull();
    expect(screen.queryByRole('button', { name: /Tiến hành đặt chỗ/ })).toBeNull();
  });

  it('giỏ về thì khung chờ biến mất và hiện các mục thật', () => {
    travel.cart = null;
    const { rerender } = render(<CartView />);
    expect(screen.getByRole('status', { name: 'Đang tải giỏ hàng' })).toBeTruthy();
    travel.cart = clone(familyCart);
    rerender(<CartView />);
    expect(screen.queryByRole('status', { name: 'Đang tải giỏ hàng' })).toBeNull();
    expect(screen.getAllByTestId('cart-item').length).toBeGreaterThan(0);
  });
});
