import { describe, expect, it } from 'vitest';
import { collectFlightAirports } from '../../src/services/flights';
import { famousHotelOptions, FAMOUS_HOTEL_SHOWN, type FamousHotel } from '../../src/features/catalog/landing/FamousHotelsPanel';

// Tuyến tối giản đúng hình dạng `attributes` của catalog (spec §2.1).
const route = (productId: string, attributes: Record<string, unknown>) => ({
  productId, name: productId, taxonomy: 'flight', destination: String(attributes.destinationCity), unitPrice: 500000,
  currency: 'VND', priceUnit: 'PER_PERSON', available: true, attributes: { level: 'route', ...attributes },
}) as never;

describe('collectFlightAirports (spec ui-dia-diem-san-bay-va-khach-san-noi-tieng §2.1)', () => {
  it('collects origin and destination airports, counts the routes touching each once, and takes the name from the destination', () => {
    const routes = [
      route('r1', { originCity: 'Nha Trang', originAirports: ['CXR'], destinationCity: 'TP. Hồ Chí Minh', destinationAirports: ['SGN'], destinationAirportName: 'Sân bay quốc tế Tân Sơn Nhất' }),
      route('r2', { originCity: 'TP. Hồ Chí Minh', originAirports: ['SGN'], destinationCity: 'Nha Trang', destinationAirports: ['CXR'], destinationAirportName: 'Sân bay quốc tế Cam Ranh' }),
      route('r3', { originCity: 'TP. Hồ Chí Minh', originAirports: ['SGN'], destinationCity: 'Hà Nội', destinationAirports: ['HAN'], destinationAirportName: 'Sân bay quốc tế Nội Bài' }),
    ];
    expect(collectFlightAirports(routes)).toEqual([
      { code: 'SGN', city: 'TP. Hồ Chí Minh', name: 'Sân bay quốc tế Tân Sơn Nhất', routeCount: 3 },
      { code: 'HAN', city: 'Hà Nội', name: 'Sân bay quốc tế Nội Bài', routeCount: 1 },
      { code: 'CXR', city: 'Nha Trang', name: 'Sân bay quốc tế Cam Ranh', routeCount: 2 },
    ].sort((a, b) => a.city.localeCompare(b.city, 'vi')));
  });

  it('a route with one destination airport names only that airport; a multi-airport route names none; nothing is invented', () => {
    const routes = [
      route('r1', { originCity: 'Pleiku', originAirports: ['PXU'], destinationCity: 'Hà Nội', destinationAirports: ['HAN'] }),
      route('r2', { originCity: 'Hà Nội', originAirports: ['HAN'], destinationCity: 'Pleiku', destinationAirports: ['PXU', 'XXX'], destinationAirportName: 'Sân bay A' }),
    ];
    const byCode = Object.fromEntries(collectFlightAirports(routes).map((a) => [a.code, a]));
    expect(byCode.PXU.name).toBeNull();
    expect(byCode.HAN.name).toBeNull();
    // Tuyến có hai sân bay đến: cả hai là sân bay hiện hành của tuyến, nhưng tên không suy ra được cho sân bay nào.
    expect(byCode.XXX).toEqual({ code: 'XXX', city: 'Pleiku', name: null, routeCount: 1 });
    expect(byCode.PXU.routeCount).toBe(2);
  });

  it('ignores rows that are not route-level, and blank or missing codes', () => {
    const routes = [
      route('f1', { level: 'flight', originCity: 'Huế', originAirports: ['HUI'], destinationCity: 'Hà Nội', destinationAirports: ['HAN'] }),
      route('r1', { originCity: 'Huế', originAirports: ['', 'HUI'], destinationCity: 'Hà Nội' }),
    ];
    const codes = collectFlightAirports(routes).map((a) => a.code);
    expect(codes).toEqual(['HUI']);
  });
});

describe('famousHotelOptions', () => {
  const hotels: FamousHotel[] = [
    { id: 'h1', name: 'Vinpearl Resort Nha Trang', destination: 'Nha Trang', imageUrl: '' },
    { id: 'h2', name: '1 House', destination: 'Đà Lạt', imageUrl: '' },
    { id: 'h3', name: 'Homestay Đà Nẵng', destination: 'Đà Nẵng', imageUrl: '' },
    { id: 'h4', name: 'Hotel A', destination: 'Hà Nội', imageUrl: '' },
    { id: 'h5', name: 'Hotel B', destination: 'Hà Nội', imageUrl: '' },
    { id: 'h6', name: 'Hotel C', destination: 'Hà Nội', imageUrl: '' },
  ];
  const destinations = [{ destination: 'Đà Lạt' }, { destination: 'Đà Nẵng' }, { destination: 'Nha Trang' }];

  it('empty text: the first famous hotels, and no destinations', () => {
    const options = famousHotelOptions('', hotels, destinations);
    expect(options.hotels.map((h) => h.id)).toEqual(['h1', 'h2', 'h3', 'h4', 'h5']);
    expect(options.hotels).toHaveLength(FAMOUS_HOTEL_SHOWN);
    expect(options.destinations).toEqual([]);
  });

  it('typing: hotels whose name or city starts a word with the text, plus matching destinations', () => {
    const options = famousHotelOptions('da', hotels, destinations);
    expect(options.hotels.map((h) => h.id)).toEqual(['h2', 'h3']);
    expect(options.destinations).toEqual(['Đà Lạt', 'Đà Nẵng']);
  });

  it('typing that matches nothing gives empty lists', () => {
    expect(famousHotelOptions('xứ sở', hotels, destinations)).toEqual({ hotels: [], destinations: [] });
  });
});
