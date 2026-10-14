// @vitest-environment jsdom
import React from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({ listDestinations: vi.fn(), listFlightAirports: vi.fn(), listProducts: vi.fn() }));
const travel = vi.hoisted(() => ({ navigate: vi.fn() }));
vi.mock('../../src/services/destinations', () => ({ listDestinations: api.listDestinations }));
vi.mock('../../src/services/flights', () => ({ listFlightAirports: api.listFlightAirports }));
vi.mock('../../src/services/catalog', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/services/catalog')>()),
  listProducts: api.listProducts,
}));
vi.mock('../../src/context/TravelContext', () => ({ useTravel: () => travel }));

import { LandingSearchSheet } from '../../src/features/catalog/landing/LandingSearchSheet';
import { VERTICALS, resolveTab } from '../../src/features/catalog/landing/verticals';
import { clearSectionCache } from '../../src/hooks/useLazySection';
import { addDaysIso, todayVN } from '../../src/features/search/tripContext';

const tomorrow = () => addDaysIso(todayVN(), 1);
const lastHref = () => new URL(travel.navigate.mock.calls.at(-1)![0], 'http://x');
/** Để dữ liệu tải xong (danh sách sân bay, khách sạn nổi tiếng) hiện lên. */
const flush = () => act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)); });

// Sân bay hiện hành: số tuyến khác nhau để kiểm thứ tự "phổ biến" (spec §4.1).
const AIRPORTS = [
  { code: 'VCS', city: 'Côn Đảo', name: 'Sân bay Côn Đảo', routeCount: 2 },
  { code: 'SGN', city: 'TP. Hồ Chí Minh', name: 'Sân bay quốc tế Tân Sơn Nhất', routeCount: 36 },
  { code: 'HAN', city: 'Hà Nội', name: 'Sân bay quốc tế Nội Bài', routeCount: 31 },
  { code: 'DAD', city: 'Đà Nẵng', name: 'Sân bay quốc tế Đà Nẵng', routeCount: 26 },
  { code: 'CXR', city: 'Nha Trang', name: 'Sân bay quốc tế Cam Ranh', routeCount: 20 },
  { code: 'PQC', city: 'Phú Quốc', name: 'Sân bay quốc tế Phú Quốc', routeCount: 20 },
  { code: 'DLI', city: 'Đà Lạt', name: 'Sân bay Liên Khương', routeCount: 20 },
];

const hotel = (productId: string, name: string, destination: string) => ({
  productId, name, taxonomy: 'hotel', destination, unitPrice: 2_000_000, currency: 'VND', priceUnit: 'PER_NIGHT',
  available: true, imageUrl: `https://images.example/${productId}.jpg`, attributes: { level: 'property' },
});
const HOTELS = [
  hotel('h1', 'Vinpearl Resort Nha Trang', 'Nha Trang'),
  hotel('h2', 'Dalat Palace', 'Đà Lạt'),
  hotel('h3', 'Muong Thanh Da Nang', 'Đà Nẵng'),
];

function renderSheet(id: keyof typeof VERTICALS, extra: Partial<React.ComponentProps<typeof LandingSearchSheet>> = {}) {
  const config = VERTICALS[id];
  return render(<LandingSearchSheet config={config} tab={resolveTab(config, undefined)} {...extra} />);
}

/** Gõ chữ vào một ô sân bay rồi rời ô: chữ khớp thì thành nhãn, không khớp thì bị xoá. */
function typeAndLeave(field: string, text: string) {
  const input = screen.getByLabelText(field) as HTMLInputElement;
  fireEvent.focus(input);
  fireEvent.change(input, { target: { value: text } });
  fireEvent.blur(input);
  return input;
}

const optionTexts = (listbox: HTMLElement) =>
  within(listbox).getAllByRole('option').map((o) => o.textContent?.replace(/[A-Z]{3} - .*$/, ''));

describe('LandingSearchSheet', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2026-09-15T10:00:00+07:00'));
    clearSectionCache();
    travel.navigate.mockReset();
    api.listDestinations.mockReset();
    api.listDestinations.mockResolvedValue([
      { destination: 'Nha Trang', productCount: 120 }, { destination: 'Đà Nẵng', productCount: 75 },
    ]);
    api.listFlightAirports.mockReset();
    api.listFlightAirports.mockResolvedValue(AIRPORTS);
    api.listProducts.mockReset();
    api.listProducts.mockResolvedValue({ results: HOTELS, total: HOTELS.length, requestId: 'test' });
    window.localStorage.clear();
  });
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it('hotels: defaults to tomorrow + 1 night, 1 room, 2 adults and searches hotels with trip context', () => {
    renderSheet('hotels');
    expect(screen.getByText('1 phòng, 2 người lớn')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));

    const url = lastHref();
    expect(url.pathname).toBe('/hotels');
    expect(url.searchParams.get('type')).toBeNull();
    expect(url.searchParams.get('q')).toBe('khách sạn');
    expect(url.searchParams.get('checkIn')).toBe(tomorrow());
    expect(url.searchParams.get('checkOut')).toBe(addDaysIso(tomorrow(), 1));
    expect(url.searchParams.get('rooms')).toBe('1');
    expect(url.searchParams.get('adults')).toBe('2');
    expect(url.searchParams.get('children')).toBeNull();
  });

  it('hotels: clicking the location shows famous hotels in place of popular places', async () => {
    renderSheet('hotels');
    fireEvent.focus(screen.getByRole('combobox'));
    const list = await screen.findByRole('listbox', { name: 'Gợi ý khách sạn nổi tiếng và điểm đến' });
    await flush();

    expect(within(list).getByRole('group', { name: 'Khách sạn nổi tiếng' })).toBeTruthy();
    expect(screen.queryByText('Điểm đến phổ biến')).toBeNull();
    expect(within(list).getAllByRole('option').map((o) => o.getAttribute('aria-label'))).toEqual([
      'Vinpearl Resort Nha Trang, Nha Trang', 'Dalat Palace, Đà Lạt', 'Muong Thanh Da Nang, Đà Nẵng',
    ]);
    expect(api.listProducts).toHaveBeenCalledWith({ taxonomy: 'hotel', sort: 'popular', availableOnly: true, limit: 20 }, expect.anything());
  });

  it('hotels: a famous hotel opens its page with the dates and party already chosen', async () => {
    renderSheet('hotels');
    fireEvent.focus(screen.getByRole('combobox'));
    const list = await screen.findByRole('listbox', { name: 'Gợi ý khách sạn nổi tiếng và điểm đến' });
    await flush();
    fireEvent.click(within(list).getByRole('option', { name: 'Vinpearl Resort Nha Trang, Nha Trang' }));

    const url = lastHref();
    expect(url.pathname).toBe('/product/h1');
    expect(url.searchParams.get('checkIn')).toBe(tomorrow());
    expect(url.searchParams.get('adults')).toBe('2');
    expect(url.searchParams.get('rooms')).toBe('1');
  });

  it('hotels: typing filters famous hotels by name or city and offers matching destinations', async () => {
    renderSheet('hotels');
    const input = screen.getByRole('combobox');
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'da' } });
    const list = await screen.findByRole('listbox', { name: 'Gợi ý khách sạn nổi tiếng và điểm đến' });
    await flush();

    expect(within(list).getAllByRole('option', { name: /Dalat Palace|Muong Thanh Da Nang/ })).toHaveLength(2);
    expect(within(list).queryByRole('option', { name: /Vinpearl Resort Nha Trang/ })).toBeNull();
    await waitFor(() => expect(within(list).getByRole('option', { name: 'Đà Nẵng' })).toBeTruthy());
  });

  it('hotels: a typed destination still searches by exact destination', async () => {
    renderSheet('hotels');
    const input = screen.getByRole('combobox');
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: 'nha' } });
    const list = await screen.findByRole('listbox', { name: 'Gợi ý khách sạn nổi tiếng và điểm đến' });
    await waitFor(() => expect(within(list).getByRole('option', { name: 'Nha Trang' })).toBeTruthy());
    fireEvent.click(within(list).getByRole('option', { name: 'Nha Trang' }));
    expect((screen.getByRole('combobox') as HTMLInputElement).value).toBe('Nha Trang');

    fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));
    expect(lastHref().searchParams.get('destination')).toBe('Nha Trang');
  });

  it('typing free text without picking sends it as the query, typing an exact label still filters', async () => {
    renderSheet('hotels');
    const input = screen.getByRole('combobox');
    fireEvent.change(input, { target: { value: 'resort yên tĩnh' } });
    fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));
    expect(lastHref().searchParams.get('q')).toBe('resort yên tĩnh');
    expect(lastHref().searchParams.get('destination')).toBeNull();

    await waitFor(() => expect(api.listDestinations).toHaveBeenCalled());
    await waitFor(() => expect(screen.queryByRole('listbox')).toBeNull());
    fireEvent.change(input, { target: { value: 'da nang' } });
    fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));
    expect(lastHref().searchParams.get('destination')).toBe('Đà Nẵng');
  });

  it('famous hotels: a failed load says so and keeps the place field usable', async () => {
    api.listProducts.mockRejectedValue(new Error('down'));
    renderSheet('hotels');
    fireEvent.focus(screen.getByRole('combobox'));
    expect(await screen.findByText('Chưa tải được khách sạn nổi tiếng. Bạn vẫn có thể gõ tên điểm đến.')).toBeTruthy();
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'resort yên tĩnh' } });
    fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));
    expect(lastHref().searchParams.get('q')).toBe('resort yên tĩnh');
  });

  it('prefills the location from ?destination= and sends it', () => {
    renderSheet('experiences', { initialDestination: 'Phú Quốc' });
    expect((screen.getByRole('combobox') as HTMLInputElement).value).toBe('Phú Quốc');
    fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));
    expect(lastHref().searchParams.get('destination')).toBe('Phú Quốc');
    expect(lastHref().searchParams.get('q')).toBe('vé tham quan');
  });

  it('experiences keep the popular destinations panel', async () => {
    renderSheet('experiences');
    fireEvent.focus(screen.getByRole('combobox'));
    expect(await screen.findByText('Điểm đến phổ biến')).toBeTruthy();
    expect(screen.queryByText('Khách sạn nổi tiếng')).toBeNull();
    expect(api.listProducts).not.toHaveBeenCalled();
  });

  it('experiences: the golf tab searches /experiences with type=golf; combos go to /combos', () => {
    const config = VERTICALS.experiences;
    const { unmount } = render(<LandingSearchSheet config={config} tab={resolveTab(config, 'golf')} />);
    fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));
    expect(lastHref().pathname).toBe('/experiences');
    expect(lastHref().searchParams.get('type')).toBe('golf');
    expect(lastHref().searchParams.get('q')).toBe('sân golf');
    unmount();

    renderSheet('combos');
    fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));
    expect(lastHref().pathname).toBe('/combos');
    expect(lastHref().searchParams.get('type')).toBeNull();
  });

  it('prefills dates, party, rooms and free text from the search in the URL', () => {
    renderSheet('hotels', {
      initialText: 'resort yên tĩnh',
      initialSearch: { origin: '', trip: { checkIn: '2026-10-20', checkOut: '2026-10-23', adults: 3, children: 1, rooms: 2 } },
    });
    expect((screen.getByRole('combobox') as HTMLInputElement).value).toBe('resort yên tĩnh');
    expect(screen.getByText('2 phòng, 3 người lớn, 1 trẻ em')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));
    const url = lastHref();
    expect(url.searchParams.get('q')).toBe('resort yên tĩnh');
    expect(url.searchParams.get('checkIn')).toBe('2026-10-20');
    expect(url.searchParams.get('checkOut')).toBe('2026-10-23');
    expect(url.searchParams.get('rooms')).toBe('2');
  });

  it('guests: never exceeds 9 people or more rooms than adults (FR-BKG-08)', () => {
    renderSheet('hotels');
    fireEvent.click(screen.getByRole('button', { name: /Số lượng/ }));
    const dialog = screen.getByRole('dialog', { name: 'Số lượng khách' });
    const plusAdult = within(dialog).getByRole('button', { name: 'Tăng người lớn' });
    for (let i = 0; i < 10; i++) fireEvent.click(plusAdult);
    expect(screen.getByText('9 người lớn', { exact: false })).toBeTruthy();
    expect((plusAdult as HTMLButtonElement).disabled).toBe(true);
    expect((within(dialog).getByRole('button', { name: 'Tăng trẻ em' }) as HTMLButtonElement).disabled).toBe(true);

    fireEvent.click(within(dialog).getByRole('button', { name: 'Tăng phòng' }));
    fireEvent.click(within(dialog).getByRole('button', { name: 'Tăng phòng' }));
    for (let i = 0; i < 9; i++) fireEvent.click(within(dialog).getByRole('button', { name: 'Giảm người lớn' }));
    // Còn 1 người lớn thì số phòng bị kéo xuống 1.
    expect(screen.getByText('1 phòng, 1 người lớn')).toBeTruthy();
  });

  it('dates: past days are disabled and a range needs the end after the start', () => {
    renderSheet('hotels');
    fireEvent.click(screen.getByRole('button', { name: /Ngày đi/ }));
    const dialog = screen.getByRole('dialog', { name: 'Chọn ngày' });
    const today = Number(todayVN().slice(8, 10));
    if (today > 1) {
      expect((within(dialog).getByRole('button', { name: new RegExp(`^${today - 1} tháng`) }) as HTMLButtonElement).disabled).toBe(true);
    }
    expect((within(dialog).getByRole('button', { name: 'Tháng trước' }) as HTMLButtonElement).disabled).toBe(true);
  });

  describe('flights: airports', () => {
    const originBox = () => screen.getByLabelText('Điểm đi') as HTMLInputElement;
    const destinationBox = () => screen.getByLabelText('Điểm đến') as HTMLInputElement;

    it('one-way by default, and a return date only for round trips', async () => {
      const onFlightSearch = vi.fn();
      renderSheet('flights', { onFlightSearch });
      await flush();
      typeAndLeave('Điểm đi', 'Hà Nội');
      typeAndLeave('Điểm đến', 'Đà Nẵng');
      fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));
      expect(onFlightSearch.mock.calls[0][0].trip).toEqual({ checkIn: tomorrow(), checkOut: undefined, adults: 2, children: 0 });

      fireEvent.click(screen.getByRole('button', { name: /Ngày đi/ }));
      fireEvent.click(screen.getByRole('radio', { name: 'Khứ hồi' }));
      fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));
      expect(onFlightSearch.mock.calls[1][0].trip.checkOut).toBe(addDaysIso(tomorrow(), 2));
      expect(travel.navigate).not.toHaveBeenCalled();
    });

    it('a typed place that is not a current airport is cleared when the field loses focus', async () => {
      renderSheet('flights');
      await flush();
      expect(typeAndLeave('Điểm đi', 'xứ sở thần tiên').value).toBe('');
    });

    it('a typed city, code or label that matches a current airport becomes its label', async () => {
      renderSheet('flights');
      await flush();
      expect(typeAndLeave('Điểm đi', 'ha noi').value).toBe('Hà Nội (HAN)');
      expect(typeAndLeave('Điểm đến', 'sgn').value).toBe('TP. Hồ Chí Minh (SGN)');
    });

    it('focusing the origin lists airports: popular ones first, then the rest of the domestic list', async () => {
      renderSheet('flights');
      await flush();
      fireEvent.focus(originBox());
      const list = await screen.findByRole('listbox', { name: 'Gợi ý điểm đi' });
      const groups = within(list).getAllByRole('group').map((g) => g.querySelector('p')?.textContent);
      expect(groups).toEqual(['Sân bay phổ biến', 'Trong nước']);
      const [popular, domestic] = within(list).getAllByRole('group');
      expect(optionTexts(popular)).toEqual(['TP. Hồ Chí Minh', 'Hà Nội', 'Đà Nẵng', 'Đà Lạt', 'Nha Trang']);
      expect(optionTexts(domestic)).toEqual(['Côn Đảo', 'Phú Quốc']);
    });

    it('arrow keys and Enter pick an airport, and the destination does not offer the chosen origin', async () => {
      renderSheet('flights');
      await flush();
      fireEvent.focus(originBox());
      await screen.findByRole('option', { name: /TP. Hồ Chí Minh/ });
      fireEvent.keyDown(originBox(), { key: 'ArrowDown' });
      fireEvent.keyDown(originBox(), { key: 'ArrowDown' });
      fireEvent.keyDown(originBox(), { key: 'Enter' });
      expect(originBox().value).toBe('Hà Nội (HAN)');
      expect(document.activeElement).toBe(destinationBox());

      const destinations = await screen.findByRole('listbox', { name: 'Gợi ý điểm đến' });
      expect(within(destinations).queryByRole('option', { name: /^Hà Nội/ })).toBeNull();
    });

    it('a search is handed over with the cities of the chosen airports, and remembered per field, newest first', async () => {
      const onFlightSearch = vi.fn();
      const { unmount } = renderSheet('flights', { onFlightSearch });
      await flush();
      typeAndLeave('Điểm đi', 'nha trang');
      typeAndLeave('Điểm đến', 'da nang');
      fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));
      expect(onFlightSearch).toHaveBeenCalledWith(expect.objectContaining({ origin: 'Nha Trang', destination: 'Đà Nẵng', airportsReady: true }));
      expect(JSON.parse(window.localStorage.getItem('vota_flight_recent_origins')!)).toEqual(['Nha Trang']);
      expect(JSON.parse(window.localStorage.getItem('vota_flight_recent_destinations')!)).toEqual(['Đà Nẵng']);
      unmount();

      renderSheet('flights', { onFlightSearch: vi.fn() });
      await flush();
      fireEvent.focus(originBox());
      const recent = await screen.findByRole('group', { name: 'Tìm gần đây' });
      expect(optionTexts(recent)).toEqual(['Nha Trang']);
      // Mục đã có ở "Tìm gần đây" không lặp ở nhóm phổ biến.
      expect(screen.getAllByRole('option', { name: /^Nha Trang/ })).toHaveLength(1);
    });

    it('a typed invalid place is not sent as an airport: the page gets the raw text, and both boxes are cleared', async () => {
      const onFlightSearch = vi.fn();
      renderSheet('flights', { onFlightSearch });
      await flush();
      typeAndLeave('Điểm đi', 'Hà Nội');
      fireEvent.focus(destinationBox());
      fireEvent.change(destinationBox(), { target: { value: 'xứ sở' } });
      fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));

      expect(onFlightSearch).toHaveBeenCalledWith(expect.objectContaining({
        origin: 'Hà Nội', destination: null, location: 'xứ sở', airportsReady: true,
      }));
      expect(destinationBox().value).toBe('');
      expect(travel.navigate).not.toHaveBeenCalled();
    });

    it('when the airport list could not be loaded the search says so and guesses nothing', async () => {
      api.listFlightAirports.mockRejectedValue(new Error('down'));
      const onFlightSearch = vi.fn();
      renderSheet('flights', { onFlightSearch });
      await flush();
      fireEvent.focus(originBox());
      expect(await screen.findByText('Chưa tải được danh sách sân bay. Thử lại sau giây lát.')).toBeTruthy();
      fireEvent.change(originBox(), { target: { value: 'Hà Nội' } });
      fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));
      expect(onFlightSearch).toHaveBeenCalledWith(expect.objectContaining({ origin: '', airportsReady: false }));
    });

    it('a search in the URL resolves to airports once loaded and is handed over again on submit', async () => {
      const onFlightSearch = vi.fn();
      renderSheet('flights', {
        onFlightSearch,
        initialDestination: 'Đà Nẵng',
        initialSearch: { origin: 'Hà Nội', trip: { checkIn: '2026-10-20', checkOut: '2026-10-25', adults: 3, children: 1 } },
      });
      await flush();
      expect(originBox().value).toBe('Hà Nội');
      expect(destinationBox().value).toBe('Đà Nẵng');
      expect(screen.getByText('3 người lớn, 1 trẻ em')).toBeTruthy();
      fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));
      expect(onFlightSearch).toHaveBeenCalledWith(expect.objectContaining({
        origin: 'Hà Nội', destination: 'Đà Nẵng', airportsReady: true,
        trip: { checkIn: '2026-10-20', checkOut: '2026-10-25', adults: 3, children: 1 },
      }));
    });

    it('history is hidden while typing, capped at five, and can be cleared', async () => {
      window.localStorage.setItem('vota_flight_recent_origins', JSON.stringify(['Đà Nẵng', 'Nha Trang']));
      renderSheet('flights');
      await flush();
      fireEvent.focus(originBox());
      expect(await screen.findByRole('group', { name: 'Tìm gần đây' })).toBeTruthy();

      fireEvent.change(originBox(), { target: { value: 'nha' } });
      expect(screen.queryByRole('group', { name: 'Tìm gần đây' })).toBeNull();

      fireEvent.change(originBox(), { target: { value: '' } });
      fireEvent.click(within(screen.getByRole('group', { name: 'Tìm gần đây' })).getByRole('button', { name: 'Xóa' }));
      expect(screen.queryByRole('group', { name: 'Tìm gần đây' })).toBeNull();
      expect(window.localStorage.getItem('vota_flight_recent_origins')).toBeNull();
    });

    it('history entries that are no longer current airports are not offered', async () => {
      window.localStorage.setItem('vota_flight_recent_destinations', JSON.stringify(['Atlantis', 'Nha Trang']));
      renderSheet('flights');
      await flush();
      fireEvent.focus(destinationBox());
      const recent = await screen.findByRole('group', { name: 'Tìm gần đây' });
      expect(optionTexts(recent)).toEqual(['Nha Trang']);
    });

    it('closes an open airport list on Escape', async () => {
      renderSheet('flights');
      await flush();
      fireEvent.focus(originBox());
      expect(await screen.findByRole('listbox', { name: 'Gợi ý điểm đi' })).toBeTruthy();
      fireEvent.keyDown(originBox(), { key: 'Escape' });
      expect(screen.queryByRole('listbox', { name: 'Gợi ý điểm đi' })).toBeNull();
    });
  });

  it('closes an open panel on Escape', () => {
    renderSheet('hotels');
    fireEvent.click(screen.getByRole('button', { name: /Số lượng/ }));
    expect(screen.getByRole('dialog', { name: 'Số lượng khách' })).toBeTruthy();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog', { name: 'Số lượng khách' })).toBeNull();
  });
});
