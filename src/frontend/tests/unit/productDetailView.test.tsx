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
// Khách sạn: nút Đặt ngay nằm trên từng thẻ hạng phòng (tên accessible "Đặt ngay {tên phòng}").
const roomButtons = () => screen.getAllByRole('button', { name: /^Đặt ngay / }) as HTMLButtonElement[];
const findRoomButtons = (name: RegExp = /^Đặt ngay /) => screen.findAllByRole('button', { name }, WAIT) as Promise<HTMLButtonElement[]>;

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

    const rooms = await findRoomButtons();
    expect(rooms).toHaveLength(2);                                  // mỗi hạng phòng một nút Đặt ngay ngay trên thẻ
    expect(rooms.every((button) => !button.disabled)).toBe(true);
    expect(screen.queryByRole('radio')).toBeNull();                // không còn ô chọn phòng
    expect(screen.queryByTestId('estimate')).toBeNull();           // không còn hộp đặt dính bên phải

    // Khách sạn chỉ đặt trực tiếp: không có nút thêm giỏ (AC-BKG-15).
    expect(screen.queryByRole('button', { name: 'Thêm vào giỏ hàng' })).toBeNull();
    expect(screen.getByTestId('direct-booking-note').textContent).toBe('Khách sạn được đặt trực tiếp, không thêm vào giỏ hàng.');

    fireEvent.click(rooms[1]);
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

  it('khách sạn: vượt sức chứa thì chỉ khoá phòng không chứa nổi, thêm phòng xong gửi số phòng và số khách', async () => {
    api.getProduct.mockResolvedValue(hotelProperty());
    render(<ProductDetailView productId="nt-h-10" />);
    await findRoomButtons();                                                          // nt-h-10-r1 chứa tối đa 2 khách, nt-h-10-r2 tối đa 4
    fireEvent.click(screen.getByRole('button', { name: /1 phòng, 1 người lớn/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Tăng người lớn' }));
    fireEvent.click(screen.getByRole('button', { name: 'Tăng trẻ em' }));
    // Ba khách: phòng 2 khách bị khoá kèm lý do riêng, phòng 4 khách vẫn đặt được.
    const [small, large] = roomButtons();
    expect(small.disabled).toBe(true);
    expect(large.disabled).toBe(false);
    expect(screen.getByTestId('room-book-note').textContent).toContain('3 khách cần ít nhất 2 phòng');
    fireEvent.click(screen.getByRole('button', { name: 'Tăng phòng' }));
    expect(screen.queryByTestId('room-book-note')).toBeNull();
    fireEvent.click(roomButtons()[0]);
    await waitFor(() => expect(travel.startBooking).toHaveBeenCalled());
    const [[item]] = travel.startBooking.mock.calls[0];
    expect(item.product).toMatchObject({ id: 'nt-h-10-r1' });
    expect(item.quantity).toBe(2);
    expect(item.guests).toEqual({ adults: 2, children: 1 });
  });

  it('khách sạn: thanh tìm kiếm có tên khách sạn, ngày và số khách; chọn ngày ngoài luật thì báo lỗi và khoá nút đặt', async () => {
    api.getProduct.mockResolvedValue(hotelProperty());
    render(<ProductDetailView productId="nt-h-10" />);
    await findRoomButtons();
    const bar = screen.getByTestId('hotel-trip-bar');
    expect((screen.getByRole('combobox', { name: 'Địa điểm hoặc tên khách sạn' }) as HTMLInputElement).value).toBe('Vinpearl Resort & Spa Nha Trang Bay');
    expect(bar.textContent).toMatch(/\d{2}\/\d{2} - \d{2}\/\d{2}, 1 đêm/);
    expect(bar.textContent).toContain('1 phòng, 1 người lớn');
    expect(screen.queryByTestId('date-error')).toBeNull();

    // Mở lịch, chọn nhận phòng rồi trả phòng cách 31 đêm: vượt 30 đêm.
    fireEvent.click(screen.getByRole('button', { name: /^Ngày ở:/ }));
    const dayButtons = () => Array.from(document.querySelectorAll<HTMLButtonElement>('[role="dialog"] .grid-cols-7 button:not(:disabled)'));
    fireEvent.click(dayButtons()[0]);                                                  // nhận phòng = ngày đầu tiên còn chọn được
    fireEvent.click(screen.getByRole('button', { name: 'Tháng sau' }));
    fireEvent.click(screen.getByRole('button', { name: 'Tháng sau' }));
    fireEvent.click(dayButtons().at(-1)!);                                             // trả phòng ở cuối tháng thứ ba: quá 30 đêm
    expect(screen.getByTestId('date-error').textContent).toContain('tối đa 30 đêm');
    expect(roomButtons().every((button) => button.disabled)).toBe(true);
  });

  it('khách sạn: nút tìm ghi ngày và số khách lên URL', async () => {
    window.history.pushState({}, '', '/product/nt-h-10');
    try {
      api.getProduct.mockResolvedValue(hotelProperty());
      render(<ProductDetailView productId="nt-h-10" />);
      await findRoomButtons();
      Element.prototype.scrollIntoView = vi.fn();
      fireEvent.click(screen.getByRole('button', { name: 'Tìm phòng' }));
      expect(window.location.search).toMatch(/checkIn=\d{4}-\d{2}-\d{2}&checkOut=\d{4}-\d{2}-\d{2}&adults=1&rooms=1/);
    } finally {
      window.history.pushState({}, '', '/');
    }
  });

  it('khách sạn: đổi địa điểm ở thanh tìm kiếm rồi bấm tìm thì sang /hotels theo địa điểm, ngày và số khách', async () => {
    api.getProduct.mockResolvedValue(hotelProperty());
    render(<ProductDetailView productId="nt-h-10" />);
    await findRoomButtons();
    // Ngày nhận/trả được đặt bởi useEffect sau khi phòng hiện ra; chờ hết báo lỗi ngày trước khi bấm tìm,
    // nếu không onSubmit thấy ngày trống và return sớm (lỗi flaky khi CI chạy song song).
    await waitFor(() => expect(screen.queryByTestId('date-error')).toBeNull(), WAIT);
    const input = screen.getByRole('combobox', { name: 'Địa điểm hoặc tên khách sạn' }) as HTMLInputElement;
    expect(input.value).toBe('Vinpearl Resort & Spa Nha Trang Bay');
    fireEvent.change(input, { target: { value: 'Đà Nẵng' } });
    fireEvent.click(screen.getByRole('button', { name: 'Tìm phòng' }));
    expect(travel.navigate).toHaveBeenCalledTimes(1);
    const href = new URL(travel.navigate.mock.calls[0][0], 'http://x');
    expect(href.pathname).toBe('/hotels');
    expect(href.searchParams.get('q')).toBe('Đà Nẵng');
    expect(href.searchParams.get('adults')).toBe('1');
    expect(href.searchParams.get('checkIn')).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it('khách sạn: lọc hạng phòng theo tiện ích phòng, phải có đủ mọi tiện ích đã chọn, xoá bộ lọc để xem lại tất cả', async () => {
    api.getProduct.mockResolvedValue(hotelProperty());
    const rooms = JSON.parse(JSON.stringify(variantsFixture));
    rooms.results[0].attributes = { ...rooms.results[0].attributes, amenities: ['Wifi miễn phí', 'Bồn tắm'] };
    rooms.results[1].attributes = { ...rooms.results[1].attributes, amenities: ['Wifi miễn phí', 'Ban công'] };
    api.listVariants.mockResolvedValue(rooms);
    render(<ProductDetailView productId="nt-h-10" />);
    await findRoomButtons();
    const filter = screen.getByTestId('room-amenity-filter');
    expect(roomButtons()).toHaveLength(2);
    expect(filter.textContent).toContain('Wifi miễn phí2');         // có ở cả hai phòng

    fireEvent.click(screen.getByRole('button', { name: /^Bồn tắm/ }));
    expect(roomButtons()).toHaveLength(1);
    expect(roomButtons()[0].getAttribute('aria-label')).toContain('Đặt ngay');
    expect(filter.textContent).toContain('1/2 hạng phòng phù hợp');

    fireEvent.click(screen.getByRole('button', { name: /^Ban công/ })); // không phòng nào có cả hai
    expect(screen.queryAllByRole('button', { name: /^Đặt ngay / })).toHaveLength(0);
    expect(screen.getByTestId('no-room-match')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Xoá bộ lọc' }));
    expect(roomButtons()).toHaveLength(2);
    expect(screen.queryByTestId('no-room-match')).toBeNull();
  });

  it('khách sạn: không có tiện ích phòng nào thì không hiện bộ lọc', async () => {
    api.getProduct.mockResolvedValue(hotelProperty());
    const rooms = JSON.parse(JSON.stringify(variantsFixture));
    rooms.results.forEach((r: { attributes: Record<string, unknown> }) => { r.attributes = { ...r.attributes, amenities: [] }; });
    api.listVariants.mockResolvedValue(rooms);
    render(<ProductDetailView productId="nt-h-10" />);
    await findRoomButtons();
    expect(screen.queryByTestId('room-amenity-filter')).toBeNull();
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
    // Không có hạng phòng nào: trang vẫn hiện, không có thanh ngày, không có nút Đặt ngay lẫn nút thêm giỏ.
    expect(await screen.findByText(/chưa có hạng phòng nào trên V-OTA/)).toBeTruthy();
    expect(screen.queryByRole('button', { name: /^Đặt ngay/ })).toBeNull();
    expect(screen.queryByTestId('hotel-trip-bar')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Thêm vào giỏ hàng' })).toBeNull();
  });

  it('books a product without variants directly: "Đặt ngay" starts a booking with only that product', async () => {
    api.getProduct.mockResolvedValue(ticketFixture);
    render(<ProductDetailView productId="nt-h-01" />);
    await screen.findByRole('heading', { level: 1, name: ticketFixture.name });
    expect(api.listVariants).not.toHaveBeenCalled();
    await screen.findByTestId('hotel-trip-bar', {}, WAIT);
    fireEvent.click(roomButtons()[0]);          // fixture là một hạng phòng khách sạn lẻ: đặt ngay trên thẻ của chính nó
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

  it('thẻ hạng phòng: thông số có icon, nhãn Giá tốt nhất ở phòng rẻ nhất, nút Đặt ngay trên thẻ; nút ảnh không đặt phòng', async () => {
    api.getProduct.mockResolvedValue(hotelProperty());
    const rooms = JSON.parse(JSON.stringify(variantsFixture));
    rooms.results[0].attributes = { ...rooms.results[0].attributes, roomSizeM2: 32, bed: '2 giường đơn', oceanView: true,
      images: ['https://img.example/r1.jpg', 'https://img.example/r1b.jpg'], amenities: ['Wifi miễn phí', 'Điều hoà không khí', 'Bồn tắm', 'Rèm cản sáng'] };
    api.listVariants.mockResolvedValue(rooms);
    render(<ProductDetailView productId="nt-h-10" />);
    await findRoomButtons();

    expect(screen.getAllByText('Giá tốt nhất')).toHaveLength(1);
    const facts = screen.getAllByRole('list', { name: 'Thông số phòng' })[0].textContent ?? '';
    expect(facts).toContain('32 m²');
    expect(facts).toContain('2 giường đơn');
    expect(facts).toContain('Hướng biển');
    const highlights = screen.getAllByRole('list', { name: 'Tiện ích nổi bật' })[0].textContent ?? '';
    expect(highlights).toContain('Wifi miễn phí');
    expect(highlights).not.toContain('Rèm cản sáng');                    // không có icon riêng: không nêu nổi bật

    expect(roomButtons()).toHaveLength(2);
    expect(screen.queryByText('Chọn phòng')).toBeNull();                 // không còn nút giả
    fireEvent.click(screen.getByRole('button', { name: 'Xem ảnh phòng (2)' }));
    fireEvent.click(screen.getByRole('button', { name: 'Đóng' }));
    expect(travel.startBooking).not.toHaveBeenCalled();                  // mở ảnh không đặt phòng
  });

  it('mỗi hạng phòng có ảnh nhỏ, xem ảnh phòng riêng và tiện ích riêng; không đặt nhầm phòng', async () => {
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
    expect(roomButtons()).toHaveLength(2);                               // vẫn là hai hạng phòng
    expect(travel.startBooking).not.toHaveBeenCalled();
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
    await screen.findByRole('heading', { level: 1, name: ticketFixture.name });
    rerender(<ProductDetailView productId="nt-h-01" />);
    await waitFor(() => expect(api.trackProductView).toHaveBeenCalledTimes(1));
    expect(api.trackProductView).toHaveBeenCalledWith('nt-h-01');

    cleanup();
    api.trackProductView.mockClear();
    travel.currentPersona = null;
    render(<ProductDetailView productId="nt-h-01" />);
    await screen.findByRole('heading', { level: 1, name: ticketFixture.name });
    expect(api.trackProductView).not.toHaveBeenCalled();
  });

  it('offers retry on a retryable error', async () => {
    api.getProduct.mockRejectedValueOnce(new ApiError('Mất kết nối. Vui lòng thử lại.', 'NETWORK_ERROR', 0, true))
      .mockResolvedValue(ticketFixture);
    render(<ProductDetailView productId="nt-h-01" />);
    fireEvent.click(await screen.findByRole('button', { name: 'Thử lại' }));
    expect(await screen.findByRole('heading', { level: 1, name: ticketFixture.name })).toBeTruthy();
  });
});
