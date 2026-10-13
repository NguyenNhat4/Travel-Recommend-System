// @vitest-environment jsdom
import React from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({ listRoutesTo: vi.fn(), listRouteFlights: vi.fn(), listDestinations: vi.fn(), listFlightAirports: vi.fn() }));
const travel = vi.hoisted(() => ({
  addToCart: vi.fn(), navigate: vi.fn(), showToast: vi.fn(), openLoginModal: vi.fn(), currentPersona: { id: 'u1' },
}));
vi.mock('../../src/services/flights', () => ({
  listRoutesTo: api.listRoutesTo, listRouteFlights: api.listRouteFlights, listFlightAirports: api.listFlightAirports,
}));
vi.mock('../../src/services/destinations', () => ({ listDestinations: api.listDestinations }));
vi.mock('../../src/context/TravelContext', () => ({ useTravel: () => travel }));
vi.mock('next/link', () => ({ default: ({ href, children, ...rest }: any) => <a href={href} {...rest}>{children}</a> }));

import { FlightsPage, missingFlightInput } from '../../src/features/flights/FlightsPage';
import { addDaysIso, todayVN } from '../../src/features/search/tripContext';
import { clearSectionCache } from '../../src/hooks/useLazySection';

// Tấm tìm kiếm luôn gửi ngày đi (mặc định là ngày mai), và trang chỉ hiện chuyến của đúng ngày đó: chuyến mẫu bay ngày mai.
const FLIGHT_DAY = addDaysIso(todayVN(), 1);

const route = {
  productId: 'r1', name: 'Vé máy bay Hà Nội - Đà Nẵng', taxonomy: 'flight', destination: 'Đà Nẵng', unitPrice: 600000, currency: 'VND', priceUnit: 'PER_PERSON', available: true,
  attributes: { level: 'route', originCity: 'Hà Nội', originAirports: ['HAN'], destinationAirports: ['DAD'] },
};
const flight = {
  productId: 'f1', name: 'VietJet Air VJ100', taxonomy: 'flight', destination: 'Đà Nẵng', unitPrice: 700000, currency: 'VND', priceUnit: 'PER_PERSON', available: true,
  availableFrom: FLIGHT_DAY, availableTo: FLIGHT_DAY,
  attributes: {
    level: 'flight', airline: 'VietJet Air', airlineCode: 'VJ', flightNumber: 'VJ100', originAirport: 'HAN', destinationAirport: 'DAD', originCity: 'Hà Nội',
    destinationCity: 'Đà Nẵng', departureAt: `${FLIGHT_DAY}T10:00:00+07:00`, arrivalAt: `${FLIGHT_DAY}T11:20:00+07:00`, durationMinutes: 80, nonstop: true, tripType: 'oneWay',
  },
};

const AIRPORTS = [
  { code: 'HAN', city: 'Hà Nội', name: 'Sân bay quốc tế Nội Bài', routeCount: 31 },
  { code: 'DAD', city: 'Đà Nẵng', name: 'Sân bay quốc tế Đà Nẵng', routeCount: 26 },
];

const Shelves = () => <div data-testid="shelves">Chặng bay phổ biến</div>;
const flush = () => act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)); });

describe('missingFlightInput', () => {
  const trip = {};
  it('says what is missing and is null once both airports are there', () => {
    expect(missingFlightInput({ origin: '', location: '', destination: null, trip })).toBe('Chọn sân bay đi và sân bay đến để xem chuyến bay.');
    expect(missingFlightInput({ origin: '', originText: ' ', location: 'Đà Nẵng', destination: 'Đà Nẵng', trip })).toBe('Bạn chưa chọn sân bay đi.');
    expect(missingFlightInput({ origin: 'Hà Nội', location: '', destination: null, trip })).toBe('Bạn chưa chọn sân bay đến.');
    expect(missingFlightInput({ origin: 'Hà Nội', location: 'xứ sở', destination: null, trip })).toMatch(/Chưa nhận ra sân bay đến “xứ sở”/);
    expect(missingFlightInput({ origin: '', originText: 'abc', location: 'Đà Nẵng', destination: 'Đà Nẵng', trip })).toMatch(/Chưa nhận ra sân bay đi “abc”/);
    expect(missingFlightInput({ origin: 'Hà Nội', location: 'Đà Nẵng', destination: 'Đà Nẵng', trip })).toBeNull();
  });

  it('an airport list that failed to load is named, not reported as a missing field', () => {
    expect(missingFlightInput({ origin: '', location: '', destination: null, trip, airportsReady: false })).toBe('Chưa tải được danh sách sân bay. Thử lại sau giây lát.');
  });
});

describe('FlightsPage', () => {
  beforeEach(() => {
    clearSectionCache();
    api.listRoutesTo.mockReset().mockResolvedValue([route]);
    api.listRouteFlights.mockReset().mockResolvedValue([flight]);
    api.listDestinations.mockReset().mockResolvedValue([{ destination: 'Đà Nẵng', productCount: 75 }]);
    api.listFlightAirports.mockReset().mockResolvedValue(AIRPORTS);
    travel.navigate.mockReset();
    window.history.replaceState(null, '', '/flights');
  });
  afterEach(cleanup);

  it('before any search it asks the visitor to choose the airports, and keeps the catalog blocks below', () => {
    render(<FlightsPage initial={null}><Shelves /></FlightsPage>);
    expect(screen.getByRole('heading', { name: 'Nhập chuyến đi để xem chuyến bay' })).toBeTruthy();
    expect(screen.getByTestId('shelves')).toBeTruthy();
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.queryAllByRole('article')).toHaveLength(0);
  });

  it('pressing Tìm with nothing chosen names what is missing and does not leave the page', async () => {
    render(<FlightsPage initial={null}><Shelves /></FlightsPage>);
    await flush();
    fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));
    expect(screen.getByRole('alert').textContent).toBe('Chọn sân bay đi và sân bay đến để xem chuyến bay.');

    fireEvent.focus(screen.getByLabelText('Điểm đi'));
    fireEvent.change(screen.getByLabelText('Điểm đi'), { target: { value: 'Hà Nội' } });
    fireEvent.blur(screen.getByLabelText('Điểm đi'));
    fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));
    expect(screen.getByRole('alert').textContent).toBe('Bạn chưa chọn sân bay đến.');
    expect(travel.navigate).not.toHaveBeenCalled();
    expect(api.listRoutesTo).not.toHaveBeenCalled();
    expect(window.location.pathname).toBe('/flights');
  });

  it('searching shows the flights right below on the same page and keeps the URL shareable', async () => {
    render(<FlightsPage initial={null}><Shelves /></FlightsPage>);
    await flush();
    fireEvent.change(screen.getByLabelText('Điểm đi'), { target: { value: 'Hà Nội' } });
    fireEvent.blur(screen.getByLabelText('Điểm đi'));
    fireEvent.change(screen.getByLabelText('Điểm đến'), { target: { value: 'da nang' } });
    fireEvent.blur(screen.getByLabelText('Điểm đến'));
    fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));

    await waitFor(() => expect(screen.getAllByRole('article')).toHaveLength(1));
    expect(api.listRoutesTo).toHaveBeenCalledWith('Đà Nẵng', expect.anything());
    expect(screen.queryByRole('heading', { name: 'Nhập chuyến đi để xem chuyến bay' })).toBeNull();
    expect(screen.queryByTestId('shelves')).toBeNull();
    expect(travel.navigate).not.toHaveBeenCalled();

    const url = new URL(window.location.href);
    expect(url.pathname).toBe('/flights');
    expect(url.searchParams.get('origin')).toBe('Hà Nội');
    expect(url.searchParams.get('destination')).toBe('Đà Nẵng');
    // Tấm tìm kiếm vẫn ở trên, giữ sân bay vừa chọn để sửa tiếp.
    expect((screen.getByLabelText('Điểm đi') as HTMLInputElement).value).toBe('Hà Nội (HAN)');
  });

  it('a second search replaces the results without leaving the page', async () => {
    render(<FlightsPage initial={{ origin: 'Hà Nội', destination: 'Đà Nẵng', trip: { adults: 1 } }}><Shelves /></FlightsPage>);
    await waitFor(() => expect(screen.getAllByRole('article')).toHaveLength(1));
    expect((screen.getByLabelText('Điểm đi') as HTMLInputElement).value).toBe('Hà Nội');

    fireEvent.change(screen.getByLabelText('Điểm đi'), { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));
    // Còn thiếu thông tin thì kết quả cũ ở lại kèm lời báo, không bị thay bằng lời nhắc.
    expect(screen.getAllByRole('article')).toHaveLength(1);
    expect(screen.getByRole('alert').textContent).toMatch(/Bạn chưa chọn sân bay đi\..*lần tìm trước/);
    expect(travel.navigate).not.toHaveBeenCalled();
  });
});
