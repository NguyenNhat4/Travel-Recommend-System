// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({ listRoutesTo: vi.fn(), listRouteFlights: vi.fn() }));
const travel = vi.hoisted(() => ({
  addToCart: vi.fn(), startBooking: vi.fn(), navigate: vi.fn(), showToast: vi.fn(), openLoginModal: vi.fn(), currentPersona: { id: 'u1' } as { id: string } | null,
}));
vi.mock('../../src/services/flights', () => api);
vi.mock('../../src/context/TravelContext', () => ({ useTravel: () => travel }));
vi.mock('next/link', () => ({ default: ({ href, children, ...rest }: any) => <a href={href} {...rest}>{children}</a> }));

import { FlightResultsView } from '../../src/features/flights/results/FlightResultsView';
import type { FlightSearch } from '../../src/features/flights/results/flightHref';
import { clearSectionCache } from '../../src/hooks/useLazySection';

const route = (productId: string, originCity: string, originAirport: string, destination: string, destinationAirport: string) => ({
  productId, name: `Vé máy bay ${originCity} - ${destination}`, taxonomy: 'flight', destination, unitPrice: 600000, currency: 'VND', priceUnit: 'PER_PERSON', available: true,
  attributes: { level: 'route', originCity, originAirports: [originAirport], destinationAirports: [destinationAirport] },
});

let n = 0;
function flight(flightNumber: string, date: string, dep: string, arr: string, price: number, over: Record<string, unknown> = {}, from = 'HAN', to = 'SGN', attrs: Record<string, unknown> = {}) {
  n += 1;
  return {
    productId: `id-${flightNumber}`, name: `VietJet Air ${flightNumber}`, taxonomy: 'flight', destination: to === 'SGN' ? 'TP. Hồ Chí Minh' : 'Hà Nội',
    unitPrice: price, currency: 'VND', priceUnit: 'PER_PERSON', available: true, availableFrom: date, availableTo: date,
    attributes: {
      level: 'flight', airline: 'VietJet Air', airlineCode: 'VJ', flightNumber, originAirport: from, destinationAirport: to,
      originCity: to === 'SGN' ? 'Hà Nội' : 'TP. Hồ Chí Minh', destinationCity: to === 'SGN' ? 'TP. Hồ Chí Minh' : 'Hà Nội',
      departureAt: `${date}T${dep}:00+07:00`, arrivalAt: `${date}T${arr}:00+07:00`, durationMinutes: 130, nonstop: true, tripType: 'oneWay', ...attrs,
    },
    fareClasses: [{ productId: `id-${flightNumber}`, code: null, name: 'Giá rẻ nhất', price, currency: 'VND', availabilityStatus: 'AVAILABLE', carryOnKg: null, checkedKg: null }],
    ...over,
  };
}

const OUT_ROUTE = route('r-out', 'Hà Nội', 'HAN', 'TP. Hồ Chí Minh', 'SGN');
const BACK_ROUTE = route('r-back', 'TP. Hồ Chí Minh', 'SGN', 'Hà Nội', 'HAN');
const FLIGHTS: Record<string, unknown[]> = {
  'r-out': [
    flight('VJ100', '2999-10-05', '10:00', '12:10', 700000),
    flight('VN200', '2999-10-05', '19:00', '21:10', 900000, { fareClasses: undefined }, 'HAN', 'SGN', { airline: 'Vietnam Airlines', airlineCode: 'VN' }),
    flight('VJ300', '2999-10-08', '06:00', '08:10', 650000),
  ],
  'r-back': [
    flight('VJ900', '2999-10-12', '05:05', '07:15', 632000, {}, 'SGN', 'HAN'),
    flight('VJ901', '2999-10-04', '05:05', '07:15', 500000, {}, 'SGN', 'HAN'), // trước chiều đi: không nối được
  ],
};

const SEARCH: FlightSearch = { origin: 'Hà Nội', destination: 'TP. Hồ Chí Minh', trip: { checkIn: '2999-10-05', checkOut: '2999-10-12', adults: 2, children: 1 } };

function renderView(search: FlightSearch = SEARCH) {
  return render(<FlightResultsView search={search} />);
}
const cards = () => screen.getAllByRole('article');
const cardOf = (card: HTMLElement) => card.querySelector('[aria-label^="Chi tiết chuyến"]')!.getAttribute('aria-label')!.replace('Chi tiết chuyến ', '');
const cardNumbers = () => cards().map((card) => card.querySelector('[aria-label^="Chi tiết chuyến"]')!.getAttribute('aria-label')!.replace('Chi tiết chuyến ', ''));
async function ready() {
  await waitFor(() => expect(screen.queryAllByRole('article').length).toBeGreaterThan(0));
}

describe('FlightResultsView', () => {
  beforeEach(() => {
    clearSectionCache();
    Object.values(travel).forEach((fn) => typeof fn === 'function' && (fn as ReturnType<typeof vi.fn>).mockReset());
    travel.currentPersona = { id: 'u1' };
    travel.addToCart.mockResolvedValue(true);
    api.listRoutesTo.mockReset();
    api.listRouteFlights.mockReset();
    api.listRoutesTo.mockImplementation(async (destination: string) => (destination === 'Hà Nội' ? [BACK_ROUTE] : [OUT_ROUTE]));
    api.listRouteFlights.mockImplementation(async (routeId: string) => FLIGHTS[routeId] ?? []);
  });
  afterEach(cleanup);

  it('loads the route by origin and destination, then its flights, and lists the day cheapest first', async () => {
    renderView();
    await ready();
    expect(api.listRoutesTo).toHaveBeenCalledWith('TP. Hồ Chí Minh', expect.anything());
    expect(api.listRouteFlights).toHaveBeenCalledWith('r-out', expect.anything());
    expect(cardNumbers()).toEqual(['VJ100', 'VN200']);
    expect(screen.getByRole('heading', { name: 'Chọn vé chiều đi' })).toBeTruthy();
    // Dải ngày chỉ có ngày có chuyến, kèm giá thấp nhất.
    expect(screen.getByRole('button', { name: /05\/10.*2 chuyến.*700\.000/ }).getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByRole('button', { name: /08\/10.*1 chuyến.*650\.000/ })).toBeTruthy();
    expect(screen.queryByRole('button', { name: /06\/10/ })).toBeNull();
  });

  it('shows only what the data says: no baggage, no fare label for a flight without fare classes', async () => {
    renderView();
    await ready();
    const vn = cards().find((c) => cardOf(c) === 'VN200')!;
    expect(within(vn).queryByText(/kg/)).toBeNull();
    expect(within(vn).queryByText(/Giá rẻ nhất/)).toBeNull();
    expect(within(cards().find((c) => cardOf(c) === 'VJ100')!).getByText('Giá rẻ nhất')).toBeTruthy();
  });

  it('says there is no flight on the searched day instead of listing another day, and offers the nearest days to pick', async () => {
    renderView({ ...SEARCH, trip: { ...SEARCH.trip, checkIn: '2999-10-06' } });
    const empty = await screen.findByTestId('no-flights-on-date');
    expect(empty.textContent).toContain('Không có chuyến bay Hà Nội → TP. Hồ Chí Minh ngày');
    expect(empty.textContent).toContain('06/10/2999');
    expect(screen.queryAllByRole('article')).toHaveLength(0);                              // không chuyến của ngày khác nào được hiện
    // Dải ngày vẫn có, nhưng không ngày nào được chọn sẵn.
    expect(screen.getByRole('button', { name: /05\/10.*2 chuyến/ }).getAttribute('aria-pressed')).toBe('false');
    expect(screen.getByRole('button', { name: /08\/10.*1 chuyến/ }).getAttribute('aria-pressed')).toBe('false');
    const offers = within(empty).getAllByRole('button').map((button) => button.textContent);
    expect(offers).toHaveLength(2);
    expect(offers[0]).toMatch(/05\/10 · từ 700k/);
    expect(offers[1]).toMatch(/08\/10 · từ 650k/);

    fireEvent.click(within(empty).getByRole('button', { name: /08\/10/ }));
    expect(cardNumbers()).toEqual(['VJ300']);
    expect(screen.queryByTestId('no-flights-on-date')).toBeNull();
    expect(screen.getByRole('button', { name: /08\/10.*1 chuyến/ }).getAttribute('aria-pressed')).toBe('true');
  });

  it('return leg: a searched return day without flights gets the same notice; no return day opens the first connecting day', async () => {
    renderView({ ...SEARCH, trip: { ...SEARCH.trip, checkOut: '2999-10-10' } });
    await ready();
    fireEvent.click(screen.getByRole('button', { name: 'Chọn chuyến VJ100' }));
    const empty = await screen.findByTestId('no-flights-on-date');
    expect(empty.textContent).toContain('Không có chuyến bay TP. Hồ Chí Minh → Hà Nội ngày');
    expect(empty.textContent).toContain('10/10/2999');
    expect(empty.textContent).toContain('cất cánh sau chuyến chiều đi đã chọn');
    expect(screen.queryAllByRole('article')).toHaveLength(0);
    // VJ901 (04/10) cất cánh trước chiều đi nên không được gợi ý; chỉ còn 12/10.
    expect(within(empty).getAllByRole('button').map((button) => button.textContent)).toEqual([expect.stringMatching(/12\/10 · từ 632k/)]);
    cleanup();

    renderView({ ...SEARCH, trip: { ...SEARCH.trip, checkOut: undefined } });
    await ready();
    fireEvent.click(screen.getByRole('button', { name: 'Khứ hồi' }));
    fireEvent.click(screen.getByRole('button', { name: 'Chọn chuyến VJ100' }));
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Chọn vé chiều về' })).toBeTruthy());
    await waitFor(() => expect(cardNumbers()).toEqual(['VJ900']));
    expect(screen.queryByTestId('no-flights-on-date')).toBeNull();
  });

  it('filters by time of day and by airline, and resets', async () => {
    renderView();
    await ready();
    fireEvent.click(screen.getByRole('button', { name: /^Tối/ }));
    expect(cardNumbers()).toEqual(['VN200']);
    fireEvent.click(screen.getByRole('button', { name: /Đặt lại/ }));
    expect(cardNumbers()).toEqual(['VJ100', 'VN200']);

    fireEvent.click(screen.getByRole('checkbox', { name: /VietJet Air/ }));
    expect(cardNumbers()).toEqual(['VN200']);
    fireEvent.click(screen.getByRole('checkbox', { name: /VietJet Air/ }));
    expect(cardNumbers()).toEqual(['VJ100', 'VN200']);
  });

  it('picks the outbound flight, moves to the return step and offers only flights that can follow', async () => {
    renderView();
    await ready();
    fireEvent.click(screen.getByRole('button', { name: 'Chọn chuyến VJ100' }));
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Chọn vé chiều về' })).toBeTruthy());
    await waitFor(() => expect(cardNumbers()).toEqual(['VJ900']));
    expect(api.listRoutesTo).toHaveBeenCalledWith('Hà Nội', expect.anything());
    expect(screen.getByText('Chọn vé chiều về để tiếp tục.')).toBeTruthy();
    expect((screen.getByRole('button', { name: 'Đặt vé' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('totals both legs for the whole party as an estimate and books both legs in ONE direct booking, never the cart', async () => {
    renderView();
    await ready();
    fireEvent.click(screen.getByRole('button', { name: 'Chọn chuyến VJ100' }));
    await waitFor(() => expect(cardNumbers()).toEqual(['VJ900']));
    fireEvent.click(screen.getByRole('button', { name: 'Chọn chuyến VJ900' }));

    // (700.000 + 632.000) × 3 khách
    expect(screen.getByTestId('ticket-total').textContent).toMatch(/3\.996\.000/);
    const pay = screen.getByRole('button', { name: 'Đặt vé' }) as HTMLButtonElement;
    expect(pay.disabled).toBe(false);
    fireEvent.click(pay);

    // Một đơn nháp cho cả hai chặng: không thêm giỏ, không tự chuyển trang (startBooking mở trang thanh toán của đơn nháp).
    await waitFor(() => expect(travel.startBooking).toHaveBeenCalledTimes(1));
    expect(travel.addToCart).not.toHaveBeenCalled();
    expect(travel.navigate).not.toHaveBeenCalled();
    const [[out, back]] = travel.startBooking.mock.calls[0];
    expect(out.product).toMatchObject({ id: 'id-VJ100', taxonomy: 'flight', unitPrice: 700000 });
    expect(out).toMatchObject({ quantity: 3, usingDate: '2999-10-05', guests: { adults: 2, children: 1 } });
    expect(back.product).toMatchObject({ id: 'id-VJ900' });
    expect(back.usingDate).toBe('2999-10-12');
  });

  it('a signed-out visitor can book too: no login prompt here, login comes at the Pay button', async () => {
    travel.currentPersona = null;
    renderView();
    await ready();
    fireEvent.click(screen.getByRole('button', { name: /Một chiều/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Chọn chuyến VJ100' }));
    fireEvent.click(screen.getByRole('button', { name: 'Đặt vé' }));
    await waitFor(() => expect(travel.startBooking).toHaveBeenCalledTimes(1));
    expect(travel.openLoginModal).not.toHaveBeenCalled();
  });

  it('a one-way ticket needs no return leg and books a single item', async () => {
    renderView({ ...SEARCH, trip: { checkIn: '2999-10-05', adults: 1 } });
    await ready();
    expect(screen.queryByText('Chiều về')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Chọn chuyến VJ100' }));
    expect(screen.getByRole('heading', { name: 'Chọn vé chiều đi' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Đặt vé' }));
    await waitFor(() => expect(travel.startBooking).toHaveBeenCalledTimes(1));
    expect(travel.startBooking.mock.calls[0][0]).toHaveLength(1);
    expect(api.listRoutesTo).not.toHaveBeenCalledWith('Hà Nội', expect.anything());
  });

  it('still books one-way when the catalog has no return route, and says so', async () => {
    api.listRoutesTo.mockImplementation(async (destination: string) => (destination === 'Hà Nội' ? [] : [OUT_ROUTE]));
    renderView();
    await ready();
    await waitFor(() => expect(screen.getByText(/Chưa có chuyến chiều về/)).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: 'Chọn chuyến VJ100' }));
    expect((screen.getByRole('button', { name: 'Đặt vé' }) as HTMLButtonElement).disabled).toBe(false);
  });

  it('a failed booking keeps the visitor on the page and lets them try again', async () => {
    travel.startBooking.mockResolvedValue(null);                                    // startBooking đã tự báo lỗi bằng toast
    renderView({ ...SEARCH, trip: { checkIn: '2999-10-05', adults: 1 } });
    await ready();
    fireEvent.click(screen.getByRole('button', { name: 'Chọn chuyến VJ100' }));
    const pay = screen.getByRole('button', { name: 'Đặt vé' }) as HTMLButtonElement;
    fireEvent.click(pay);
    await waitFor(() => expect(travel.startBooking).toHaveBeenCalledTimes(1));
    expect(travel.navigate).not.toHaveBeenCalled();
    await waitFor(() => expect((screen.getByRole('button', { name: 'Đặt vé' }) as HTMLButtonElement).disabled).toBe(false));
  });

  it('offers the origins that do fly to the destination when the typed origin has no route', async () => {
    renderView({ ...SEARCH, origin: 'Huế' });
    await waitFor(() => expect(screen.getByText(/Chưa có chặng Huế → TP\. Hồ Chí Minh/)).toBeTruthy());
    const link = screen.getByRole('link', { name: /Hà Nội/ });
    const url = new URL(link.getAttribute('href')!, 'http://x');
    expect(url.pathname).toBe('/flights');
    expect(url.searchParams.get('origin')).toBe('Hà Nội');
    expect(url.searchParams.get('destination')).toBe('TP. Hồ Chí Minh');
  });

  it('shows a retryable error when the catalog cannot be read', async () => {
    api.listRoutesTo.mockRejectedValueOnce(new Error('boom'));
    renderView();
    await waitFor(() => expect(screen.getByText(/Chưa tải được chuyến bay/)).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: 'Thử lại' }));
    await ready();
    expect(cardNumbers()).toEqual(['VJ100', 'VN200']);
  });
});
