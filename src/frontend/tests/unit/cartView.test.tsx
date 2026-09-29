// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import familyCart from '../../../shared/mocks/booking/getCart.200-family.json';
import unavailableCart from '../../../shared/mocks/booking/getCart.200-item-unavailable.json';

const api = vi.hoisted(() => ({ getProduct: vi.fn(), fetchRecommendations: vi.fn() }));
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
    api.fetchRecommendations.mockRejectedValue(new Error('không cần trong test'));
    api.getProduct.mockResolvedValue({ productId: 'nt-a-vinwonders-buggy', attributes: { childPrice: 504000 } });
    travel.updateCartItem.mockResolvedValue(null);
  });
  afterEach(() => cleanup());

  it('mỗi mục hiện đoàn khách ("2 người lớn · 1 trẻ em") và các dòng giá của Backend', () => {
    render(<CartView />);
    const ticket = rowOf('VinWonders');
    expect(within(ticket).getByTestId('cart-item-summary').textContent).toBe('Ngày dùng: 2026-10-18 · 2 người lớn · 1 trẻ em');
    expect(within(ticket).getByTestId('fare-lines').textContent).toContain('2 × 1.500.000');
    expect(within(ticket).getByTestId('fare-lines').textContent).toContain('1 × 504.000');
    const hotel = rowOf('Lucky Sun');
    expect(within(hotel).getByTestId('cart-item-summary').textContent).toContain('2 đêm · 1 phòng · 2 người lớn · 1 trẻ em');
    expect(within(hotel).getByTestId('fare-lines').textContent).toContain('× 2 đêm × 1 phòng');
    expect(screen.getAllByText('6.960.384 ₫').length).toBeGreaterThan(0);          // tổng lấy từ CartResponse
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

  it('khách sạn: vượt sức chứa thì báo cần thêm phòng và khoá nút Cập nhật; thêm phòng thì gửi số phòng và số khách', async () => {
    render(<CartView />);
    const hotel = rowOf('Lucky Sun');                                              // phòng tối đa 3 khách, đang 2 người lớn + 1 trẻ em
    fireEvent.click(within(hotel).getByRole('button', { name: /^Sửa số khách của/ }));
    const editor = within(hotel).getByTestId('guest-editor');
    expect(editor.textContent).toContain('Tối đa 3 khách/phòng');
    fireEvent.click(within(editor).getByLabelText('Thêm trẻ em'));
    expect(within(editor).getByTestId('capacity-issue').textContent).toContain('4 khách vượt sức chứa 3 khách của 1 phòng. Cần ít nhất 2 phòng.');
    expect((within(editor).getByRole('button', { name: 'Cập nhật' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(within(editor).getByRole('button', { name: 'Thêm 1 phòng' }));
    fireEvent.click(within(editor).getByRole('button', { name: 'Cập nhật' }));
    await waitFor(() => expect(travel.updateCartItem).toHaveBeenCalledWith('ci-hotel', { quantity: 2, guests: { adults: 2, children: 2 } }));
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
});
