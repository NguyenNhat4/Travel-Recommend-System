// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { WidgetProductDetail } from '../../src/features/itinerary/widget/WidgetProductDetail';
import type { ProductDetail } from '../../src/services/catalog';

const mocks = vi.hoisted(() => ({ getProduct: vi.fn(), trackProductView: vi.fn() }));

// Như trang chi tiết: chỉ ghi product_view khi đã đăng nhập.
vi.mock('../../src/context/TravelContext', () => ({ useTravel: () => ({ currentPersona: { id: 'u1' } }) }));

vi.mock('../../src/services/catalog', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/services/catalog')>()),
  getProduct: mocks.getProduct,
  trackProductView: mocks.trackProductView,
}));

const detail = (attributes: Record<string, unknown>): ProductDetail => ({
  productId: 'vanmieu', name: 'Văn Miếu – Quốc Tử Giám', taxonomy: 'attraction', destination: 'Hà Nội',
  unitPrice: null, currency: 'VND', priceUnit: 'PER_PERSON', available: true,
  imageUrl: 'https://cdn.example.vn/main.jpg', rating: 4.6, reviewCount: 13246,
  description: 'Trường đại học đầu tiên của Việt Nam.', attributes,
} as unknown as ProductDetail);

const located = {
  images: ['https://cdn.example.vn/main.jpg', 'https://cdn.example.vn/2.jpg', 'https://cdn.example.vn/3.jpg'],
  address: '58 P. Quốc Tử Giám, Hà Nội', latitude: 21.0293, longitude: 105.8355, openingHours: '08:00–17:00 hằng ngày',
};

describe('WidgetProductDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.trackProductView.mockResolvedValue(undefined);
  });
  afterEach(cleanup);

  it('shows only catalog data: gallery, description, address with directions, hours and rating', async () => {
    mocks.getProduct.mockResolvedValue(detail(located));
    const { container } = render(<WidgetProductDetail productId="vanmieu" onClose={vi.fn()} />);
    expect(await screen.findByText('Trường đại học đầu tiên của Việt Nam.')).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Văn Miếu – Quốc Tử Giám' })).toBeTruthy();
    expect(Array.from(container.querySelectorAll('img')).map((image) => image.getAttribute('src')))
      .toEqual(located.images);   // ảnh đại diện trùng ảnh đầu của bộ ảnh chỉ hiện một lần
    expect(screen.getByText('58 P. Quốc Tử Giám, Hà Nội')).toBeTruthy();
    expect(screen.getByRole('link', { name: /Chỉ đường/ }).getAttribute('href'))
      .toBe('https://www.google.com/maps/dir/?api=1&destination=21.0293,105.8355');
    expect(screen.getByText('08:00–17:00 hằng ngày')).toBeTruthy();
    expect(screen.getByText('4.6/5')).toBeTruthy();
    expect(screen.getByText(/13\.246 đánh giá/)).toBeTruthy();
    expect(screen.getByText('Tham quan tự do')).toBeTruthy();
    expect(screen.queryByRole('link', { name: /Xem trang chi tiết/ })).toBeNull();
    expect(mocks.trackProductView).toHaveBeenCalledWith('vanmieu');
  });

  it('hides directions when the catalog has no coordinates', async () => {
    mocks.getProduct.mockResolvedValue(detail({ images: [] }));
    render(<WidgetProductDetail productId="vanmieu" onClose={vi.fn()} />);
    await screen.findByText('Trường đại học đầu tiên của Việt Nam.');
    expect(screen.queryByRole('link', { name: /Chỉ đường/ })).toBeNull();
  });

  it('keeps the detail link for a priced product', async () => {
    mocks.getProduct.mockResolvedValue({ ...detail(located), unitPrice: 100000 });
    render(<WidgetProductDetail productId="vanmieu" onClose={vi.fn()} />);
    const link = await screen.findByRole('link', { name: /Xem trang chi tiết/ });
    expect(link.getAttribute('href')).toBe('/product/vanmieu');
    expect(screen.queryByText('Tham quan tự do')).toBeNull();
  });

  it('hides the detail link when ticketed=false even if a price is present', async () => {
    mocks.getProduct.mockResolvedValue({ ...detail({ ...located, ticketed: false }), unitPrice: 100000 });
    render(<WidgetProductDetail productId="vanmieu" onClose={vi.fn()} />);
    await screen.findByText('Tham quan tự do');
    expect(screen.queryByRole('link', { name: /Xem trang chi tiết/ })).toBeNull();
  });

  it('shows a loading status before the catalog detail arrives', async () => {
    let resolveDetail!: (product: ProductDetail) => void;
    mocks.getProduct.mockReturnValue(new Promise<ProductDetail>((resolve) => { resolveDetail = resolve; }));
    render(<WidgetProductDetail productId="vanmieu" onClose={vi.fn()} />);
    expect(screen.getByRole('status').textContent).toContain('Đang tải chi tiết');
    expect(screen.queryByRole('heading', { name: 'Văn Miếu – Quốc Tử Giám' })).toBeNull();
    resolveDetail(detail(located));
    await screen.findByRole('heading', { name: 'Văn Miếu – Quốc Tử Giám' });
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('switches catalog images and keeps each thumbnail label tied to its original image', async () => {
    mocks.getProduct.mockResolvedValue(detail(located));
    render(<WidgetProductDetail productId="vanmieu" onClose={vi.fn()} />);
    const mainImage = await screen.findByRole('img', { name: 'Văn Miếu – Quốc Tử Giám' });
    fireEvent.click(screen.getByRole('button', { name: 'Xem ảnh 2 của Văn Miếu – Quốc Tử Giám' }));
    expect(mainImage.getAttribute('src')).toBe(located.images[1]);
    fireEvent.click(screen.getByRole('button', { name: 'Xem ảnh 1 của Văn Miếu – Quốc Tử Giám' }));
    expect(mainImage.getAttribute('src')).toBe(located.images[0]);
  });

  it('keeps the summary visible and offers a retry when the detail fails to load', async () => {
    mocks.getProduct.mockRejectedValueOnce(new Error('network')).mockResolvedValueOnce(detail(located));
    const summary = { id: 'vanmieu', name: 'Văn Miếu – Quốc Tử Giám', taxonomy: 'attraction', destination: 'Hà Nội',
      unitPrice: null, currency: 'VND', imageUrl: 'https://cdn.example.vn/main.jpg', description: '', attributes: {},
      available: true } as never;
    render(<WidgetProductDetail productId="vanmieu" summary={summary} onClose={vi.fn()} />);
    expect(screen.getByRole('heading', { name: 'Văn Miếu – Quốc Tử Giám' })).toBeTruthy();
    fireEvent.click(await screen.findByRole('button', { name: /Thử lại/ }));
    await waitFor(() => expect(screen.getByText('Trường đại học đầu tiên của Việt Nam.')).toBeTruthy());
  });

  it('closes from the X button and adds to cart only when the parent allows it', async () => {
    mocks.getProduct.mockResolvedValue(detail(located));
    const onClose = vi.fn();
    const onAddToCart = vi.fn();
    render(<WidgetProductDetail productId="vanmieu" onClose={onClose} onAddToCart={onAddToCart} />);
    await screen.findByText('Trường đại học đầu tiên của Việt Nam.');
    fireEvent.click(screen.getByRole('button', { name: 'Thêm vào giỏ' }));
    fireEvent.click(screen.getByRole('button', { name: 'Đóng chi tiết' }));
    expect(onAddToCart).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
