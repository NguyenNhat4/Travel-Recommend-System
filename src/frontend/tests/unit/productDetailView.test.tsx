// @vitest-environment jsdom
import React from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import propertyFixture from '../../../shared/mocks/catalog/getProduct.200-property.json';
import ticketFixture from '../../../shared/mocks/catalog/getProduct.200-default.json';
import variantsFixture from '../../../shared/mocks/catalog/listProducts.200-variants.json';
import popularFixture from '../../../shared/mocks/catalog/listProducts.200-popular.json';

const api = vi.hoisted(() => ({
  getProduct: vi.fn(),
  listVariants: vi.fn(),
  listProducts: vi.fn(),
  trackProductView: vi.fn(),
}));
const recsys = vi.hoisted(() => ({ fetchRecommendations: vi.fn() }));
const travel = vi.hoisted(() => ({
  currentPersona: { id: 'VP0000001', name: 'Nguyễn Minh Anh' } as unknown,
  navigate: vi.fn(),
  addToCart: vi.fn(),
  startBooking: vi.fn(),
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
    api.listProducts.mockResolvedValue(popularFixture);
    recsys.fetchRecommendations.mockRejectedValue(new Error('không cần trong test'));
    travel.addToCart.mockResolvedValue(true);
    travel.startBooking.mockResolvedValue(null);
  });
  afterEach(() => cleanup());

  it('loads the real product and lists its rooms; Đặt ngay books the ROOM, not the hotel, and never the cart', async () => {
    api.getProduct.mockResolvedValue(hotelProperty());
    render(<ProductDetailView productId="nt-h-10" />);

    expect(await screen.findByRole('heading', { name: 'Vinpearl Resort & Spa Nha Trang Bay' }, WAIT)).toBeTruthy();
    expect(api.getProduct).toHaveBeenCalledWith('nt-h-10', expect.anything());
    await waitFor(() => expect(api.listVariants).toHaveBeenCalledWith('nt-h-10', expect.anything()), WAIT);

    const rooms = await screen.findAllByRole('radio', {}, WAIT);
    expect(rooms).toHaveLength(2);
    expect(rooms[0].getAttribute('aria-checked')).toBe('true'); // phòng rẻ nhất đặt được được chọn sẵn

    // Khách sạn chỉ đặt trực tiếp: không có nút thêm giỏ (AC-BKG-15).
    expect(screen.queryByRole('button', { name: 'Thêm vào giỏ hàng' })).toBeNull();
    expect(screen.getByTestId('direct-booking-note').textContent).toBe('Khách sạn được đặt trực tiếp, không thêm vào giỏ hàng.');

    fireEvent.click(rooms[1]);
    fireEvent.click(screen.getByRole('button', { name: 'Đặt ngay' }));
    await waitFor(() => expect(travel.startBooking).toHaveBeenCalled());
    expect(travel.addToCart).not.toHaveBeenCalled();
    const [[item]] = travel.startBooking.mock.calls[0];
    expect(item.product).toMatchObject({ id: 'nt-h-10-r2', unitPrice: 4150000, taxonomy: 'hotel' });
    expect(item.quantity).toBe(1);
    expect(item.usingDate).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(item.checkOutDate > item.usingDate).toBe(true);
    expect(item.guests).toEqual({ adults: 1, children: 0 });
  });

  it('thanh phân cấp về trang khách sạn của điểm đến, giữ ngày và số khách, không sang /search', async () => {
    window.history.pushState({}, '', '/product/nt-h-10?checkIn=2099-10-20&checkOut=2099-10-22&adults=2');
    try {
      api.getProduct.mockResolvedValue(hotelProperty());
      render(<ProductDetailView productId="nt-h-10" />);
      const link = await screen.findByRole('link', { name: /^Khách sạn tại / }, WAIT);
      await waitFor(() => expect(link.getAttribute('href')).toContain('checkIn=2099-10-20'), WAIT);
      const href = new URL(link.getAttribute('href')!, 'http://x');
      expect(href.pathname).toBe('/hotels');
      expect(href.searchParams.get('adults')).toBe('2');
      expect(screen.queryByRole('link', { name: 'Nha Trang' })).toBeNull();
    } finally {
      window.history.pushState({}, '', '/');
    }
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
    expect((screen.getByRole('button', { name: 'Đặt ngay' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Thêm 1 phòng' }));
    expect(screen.queryByTestId('capacity-issue')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Đặt ngay' }));
    await waitFor(() => expect(travel.startBooking).toHaveBeenCalled());
    const [[item]] = travel.startBooking.mock.calls[0];
    expect(item.product).toMatchObject({ id: 'nt-h-10-r1' });
    expect(item.quantity).toBe(2);
    expect(item.guests).toEqual({ adults: 2, children: 1 });
  });

  it('khách sạn: trả phòng không sau nhận phòng hoặc ngày trống thì báo lỗi, khoá nút đặt và không tự sửa ngày', async () => {
    api.getProduct.mockResolvedValue(hotelProperty());
    render(<ProductDetailView productId="nt-h-10" />);
    await screen.findAllByRole('radio', {}, WAIT);
    // Ô text dd/mm/yyyy đồng bộ từ ngày mặc định qua effect, sau ô date ẩn; chờ chính ô này để khỏi chạy đua trên CI chậm.
    await waitFor(() => expect((screen.getByLabelText('Nhận phòng') as HTMLInputElement).value).toMatch(/^\d{2}\/\d{2}\/\d{4}$/), WAIT);
    const checkIn = screen.getByLabelText('Nhận phòng') as HTMLInputElement;
    const checkOut = screen.getByLabelText('Trả phòng') as HTMLInputElement;
    expect(checkIn.value).toMatch(/^\d{2}\/\d{2}\/\d{4}$/);
    const book = () => screen.getByRole('button', { name: 'Đặt ngay' }) as HTMLButtonElement;
    expect(screen.queryByTestId('date-error')).toBeNull();
    expect(book().disabled).toBe(false);

    fireEvent.change(checkOut, { target: { value: checkIn.value } });
    expect(screen.getByTestId('date-error').textContent).toContain('Ngày trả phòng phải sau ngày nhận phòng');
    expect(checkOut.value).toBe(checkIn.value);
    expect(book().disabled).toBe(true);

    fireEvent.change(checkOut, { target: { value: '' } });
    expect(screen.getByTestId('date-error').textContent).toContain('ngày trả phòng');
    expect(book().disabled).toBe(true);

    fireEvent.change(checkIn, { target: { value: '' } });
    expect(screen.getByTestId('date-error').textContent).toContain('ngày nhận phòng');
    expect(book().disabled).toBe(true);
  });

  it('khách sạn: ngày nhận phòng theo lịch (không quá khứ, tối đa 3 tháng), tối đa 30 đêm, không phụ thuộc cửa sổ mở bán', async () => {
    api.getProduct.mockResolvedValue(hotelProperty());
    render(<ProductDetailView productId="nt-h-10" />);
    await screen.findAllByRole('radio', {}, WAIT);
    // Ô text dd/mm/yyyy đồng bộ từ ngày mặc định qua effect, sau ô date ẩn; chờ chính ô này để khỏi chạy đua trên CI chậm.
    await waitFor(() => expect((screen.getByLabelText('Nhận phòng') as HTMLInputElement).value).toMatch(/^\d{2}\/\d{2}\/\d{4}$/), WAIT);
    const checkIn = screen.getByLabelText('Nhận phòng') as HTMLInputElement;
    const checkOut = screen.getByLabelText('Trả phòng') as HTMLInputElement;
    const dmy = (offsetDays: number) => {
      const iso = new Date(Date.now() + offsetDays * 24 * 3600 * 1000).toLocaleDateString('en-CA', { timeZone: 'Asia/Ho_Chi_Minh' });
      return iso.split('-').reverse().join('/');
    };
    const error = () => screen.queryByTestId('date-error')?.textContent ?? '';

    // Hôm nay được nhận phòng; hôm qua thì không.
    fireEvent.change(checkIn, { target: { value: dmy(0) } });
    fireEvent.change(checkOut, { target: { value: dmy(1) } });
    expect(error()).toBe('');
    fireEvent.change(checkIn, { target: { value: dmy(-1) } });
    expect(error()).toContain('không được ở quá khứ');
    // Quá 3 tháng thì không đặt được.
    fireEvent.change(checkIn, { target: { value: dmy(120) } });
    fireEvent.change(checkOut, { target: { value: dmy(121) } });
    expect(error()).toContain('tối đa 3 tháng');
    // 30 đêm được, 31 đêm thì không.
    fireEvent.change(checkIn, { target: { value: dmy(1) } });
    fireEvent.change(checkOut, { target: { value: dmy(31) } });
    expect(error()).toBe('');
    fireEvent.change(checkOut, { target: { value: dmy(32) } });
    expect(error()).toContain('tối đa 30 đêm');
  });

  it('vé tham quan: hai bộ đếm Người lớn/Trẻ em kèm đơn giá từng loại; ước tính theo giá trẻ em; gửi guests', async () => {
    api.getProduct.mockResolvedValue({
      ...ticketFixture, productId: 'nt-a-vinwonders-buggy', name: 'Vé VinWonders + Buggy', taxonomy: 'attraction', unitPrice: 1500000,
      availableFrom: '2026-10-01', availableTo: '2027-03-31', attributes: { childPrice: 504000 },
    });
    render(<ProductDetailView productId="nt-a-vinwonders-buggy" />);
    await screen.findByRole('heading', { name: 'Vé VinWonders + Buggy' });
    await act(async () => {});                                                          // chờ effect đặt lại số khách chạy xong trước khi bấm
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
    // Tour, trải nghiệm có cả hai nút; Đặt ngay chỉ thanh toán sản phẩm này, không qua giỏ (AC-BKG-01).
    expect(screen.queryByTestId('direct-booking-note')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Đặt ngay' }));
    await waitFor(() => expect(travel.startBooking).toHaveBeenCalledWith([
      expect.objectContaining({ product: expect.objectContaining({ id: 'nt-a-vinwonders-buggy' }), quantity: 3, guests: { adults: 2, children: 1 } }),
    ]));
  });

  it('vé không có giá trẻ em riêng và chuyến bay: trẻ em cùng giá người lớn, chuyến bay có ghi chú về giá vé trẻ em', async () => {
    api.getProduct.mockResolvedValue({
      ...ticketFixture, productId: 'nt-f-vj601', name: 'VietJet Air VJ601', taxonomy: 'flight', unitPrice: 950000,
      availableFrom: '2026-10-19', availableTo: '2026-10-19', attributes: { flightNumber: 'VJ601' },
    });
    render(<ProductDetailView productId="nt-f-vj601" />);
    await screen.findByRole('heading', { name: 'VietJet Air VJ601' });
    // Effect đặt lại ngày/số khách theo mục đang chọn chạy sau lần render đầu; chờ nó xong để lần bấm không bị ghi đè.
    await act(async () => {});
    expect(screen.getByText('Dưới 12 tuổi · cùng giá người lớn')).toBeTruthy();
    expect(screen.queryByTestId('flight-child-note')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Thêm trẻ em' }));
    expect(screen.getByTestId('flight-child-note').textContent).toBe('Chưa có giá vé trẻ em riêng: trẻ em và em bé có ghế riêng, tính giá người lớn.');
    expect(screen.getByTestId('estimate-total').textContent).toContain('1.900.000');
    expect(screen.queryByRole('button', { name: 'Thêm vào giỏ hàng' })).toBeNull();
    expect(screen.getByTestId('direct-booking-note').textContent).toBe('Vé máy bay được đặt trực tiếp, không thêm vào giỏ hàng.');
  });

  it('combo: chỉ có bộ đếm số gói, chỉ gửi quantity', async () => {
    api.getProduct.mockResolvedValue({
      ...ticketFixture, productId: 'nt-c-01', name: 'Combo 3N2Đ', taxonomy: 'combo', unitPrice: 5200000,
      availableFrom: '2026-10-01', availableTo: '2027-03-31', attributes: {},
    });
    render(<ProductDetailView productId="nt-c-01" />);
    await screen.findByRole('heading', { name: 'Combo 3N2Đ' });
    // Effect đặt lại ngày/số khách theo mục đang chọn chạy sau lần render đầu; chờ nó xong để lần bấm không bị ghi đè.
    await act(async () => {});
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
    // Chưa có hạng phòng nào được chọn (unit = null): trang vẫn hiện, nút Đặt ngay bị khoá, không có nút thêm giỏ.
    expect(await screen.findByText(/chưa có hạng phòng nào trên V-OTA/)).toBeTruthy();
    expect((screen.getByRole('button', { name: 'Đặt ngay' }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByRole('button', { name: 'Thêm vào giỏ hàng' })).toBeNull();
  });

  it('books a product without variants directly: "Đặt ngay" starts a booking with only that product', async () => {
    api.getProduct.mockResolvedValue(ticketFixture);
    render(<ProductDetailView productId="nt-h-01" />);
    await screen.findByRole('heading', { name: ticketFixture.name });
    expect(api.listVariants).not.toHaveBeenCalled();
    await waitFor(() => expect(document.querySelector<HTMLInputElement>('input[type="date"]')?.value).toBeTruthy(), WAIT);
    fireEvent.click(screen.getByRole('button', { name: 'Đặt ngay' }));
    await waitFor(() => expect(travel.startBooking).toHaveBeenCalledTimes(1));
    const [items] = travel.startBooking.mock.calls[0];
    expect(items).toHaveLength(1);
    expect(items[0].product).toMatchObject({ id: 'nt-h-01' });
    expect(items[0].guests).toEqual({ adults: 1, children: 0 });
    expect(travel.addToCart).not.toHaveBeenCalled();
    expect(travel.navigate).not.toHaveBeenCalled();                                // startBooking tự mở trang thanh toán của đơn nháp
  });

  it('không còn mục Tương tự ở trang chi tiết', async () => {
    api.getProduct.mockResolvedValue(ticketFixture);
    render(<ProductDetailView productId="nt-h-01" />);
    await screen.findByRole('heading', { level: 1 }, WAIT);
    expect(screen.queryByText(/^Tương tự/)).toBeNull();
  });

  it('khách sạn: bộ ảnh nhiều tấm từ attributes.images, bấm mở trình xem ảnh lớn, ← → đổi ảnh, Esc đóng', async () => {
    const hotel = hotelProperty();
    hotel.attributes = { ...hotel.attributes, images: [
      'https://img.example/a.jpg', 'https://img.example/b.jpg', 'https://img.example/c.jpg', 'https://img.example/d.jpg',
      'https://img.example/e.jpg', 'https://img.example/f.jpg'] };
    hotel.imageUrl = 'https://img.example/a.jpg';
    api.getProduct.mockResolvedValue(hotel);
    render(<ProductDetailView productId="nt-h-10" />);
    const open = await screen.findByRole('button', { name: /^Xem 6 ảnh của / }, WAIT);
    expect(screen.getAllByText('6 ảnh').length).toBeGreaterThan(0);
    fireEvent.click(open);
    const dialog = screen.getByRole('dialog');
    expect(dialog.textContent).toContain('1 / 6');
    fireEvent.keyDown(document, { key: 'ArrowRight' });
    expect(dialog.textContent).toContain('2 / 6');
    fireEvent.keyDown(document, { key: 'ArrowLeft' });
    fireEvent.keyDown(document, { key: 'ArrowLeft' });
    expect(dialog.textContent).toContain('6 / 6');                       // vòng về ảnh cuối
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('khách sạn: tiện ích của khách sạn bỏ trùng, thu gọn 12 mục và mở hết bằng "Xem tất cả"', async () => {
    const hotel = hotelProperty();
    const names = Array.from({ length: 20 }, (_, i) => `Tiện ích ${i + 1}`);
    hotel.attributes = { ...hotel.attributes, amenities: [...names, 'tiện ích 1', '  ', 7] };
    api.getProduct.mockResolvedValue(hotel);
    render(<ProductDetailView productId="nt-h-10" />);
    const list = await screen.findByRole('list', { name: 'Tiện ích' }, WAIT);
    expect(list.querySelectorAll('li')).toHaveLength(12);
    fireEvent.click(screen.getByRole('button', { name: 'Xem tất cả (20)' }));
    expect(screen.getByRole('list', { name: 'Tiện ích' }).querySelectorAll('li')).toHaveLength(20);
    fireEvent.click(screen.getByRole('button', { name: 'Thu gọn' }));
    expect(screen.getByRole('list', { name: 'Tiện ích' }).querySelectorAll('li')).toHaveLength(12);
  });

  it('thẻ hạng phòng: thông số có icon, nhãn Giá tốt nhất ở phòng rẻ nhất, "Đã chọn" theo lựa chọn; nút ảnh không đổi lựa chọn', async () => {
    api.getProduct.mockResolvedValue(hotelProperty());
    const rooms = JSON.parse(JSON.stringify(variantsFixture));
    rooms.results[0].attributes = { ...rooms.results[0].attributes, roomSizeM2: 32, bed: '2 giường đơn', oceanView: true,
      images: ['https://img.example/r1.jpg', 'https://img.example/r1b.jpg'], amenities: ['Wifi miễn phí', 'Điều hoà không khí', 'Bồn tắm', 'Rèm cản sáng'] };
    api.listVariants.mockResolvedValue(rooms);
    render(<ProductDetailView productId="nt-h-10" />);
    const radios = await screen.findAllByRole('radio', {}, WAIT);

    expect(screen.getAllByText('Giá tốt nhất')).toHaveLength(1);
    const facts = screen.getAllByRole('list', { name: 'Thông số phòng' })[0].textContent ?? '';
    expect(facts).toContain('32 m²');
    expect(facts).toContain('2 giường đơn');
    expect(facts).toContain('Hướng biển');
    const highlights = screen.getAllByRole('list', { name: 'Tiện ích nổi bật' })[0].textContent ?? '';
    expect(highlights).toContain('Wifi miễn phí');
    expect(highlights).not.toContain('Rèm cản sáng');                    // không có icon riêng: không nêu nổi bật

    expect(radios[0].getAttribute('aria-checked')).toBe('true');
    expect(screen.getAllByText('Đã chọn')).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: 'Xem ảnh phòng (2)' }));
    fireEvent.click(screen.getByRole('button', { name: 'Đóng' }));
    expect(radios[0].getAttribute('aria-checked')).toBe('true');         // mở ảnh không đổi phòng
    fireEvent.click(radios[1]);
    expect(radios[1].getAttribute('aria-checked')).toBe('true');
    expect(radios[0].getAttribute('aria-checked')).toBe('false');
    expect(screen.getAllByText('Đã chọn')).toHaveLength(1);
  });

  it('mỗi hạng phòng có ảnh nhỏ, xem ảnh phòng riêng và tiện ích riêng; chọn phòng không bị ảnh hưởng', async () => {
    api.getProduct.mockResolvedValue(hotelProperty());
    const rooms = JSON.parse(JSON.stringify(variantsFixture));
    rooms.results[0].imageUrl = 'https://img.example/room1.jpg';
    rooms.results[0].attributes = { ...rooms.results[0].attributes, images: ['https://img.example/room1.jpg', 'https://img.example/room1b.jpg'],
      amenities: ['Két an toàn', 'Wifi miễn phí', 'Ấm đun nước'] };
    api.listVariants.mockResolvedValue(rooms);
    render(<ProductDetailView productId="nt-h-10" />);
    const photos = await screen.findByRole('button', { name: 'Xem ảnh phòng (2)' }, WAIT);
    fireEvent.click(photos);
    expect(screen.getByRole('dialog').textContent).toContain('1 / 2');
    fireEvent.click(screen.getByRole('button', { name: 'Đóng' }));
    expect(screen.queryByRole('dialog')).toBeNull();

    expect(screen.queryByRole('list', { name: 'Tiện ích phòng' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Tiện ích phòng (3)' }));
    expect(screen.getByRole('list', { name: 'Tiện ích phòng' }).textContent).toContain('Wifi miễn phí');
    fireEvent.click(screen.getByRole('button', { name: 'Ẩn tiện ích phòng' }));
    expect(screen.queryByRole('list', { name: 'Tiện ích phòng' })).toBeNull();
    expect(screen.getAllByRole('radio')).toHaveLength(2);                // vẫn là hai hạng phòng để chọn
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
