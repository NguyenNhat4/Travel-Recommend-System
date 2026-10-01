import { describe, expect, it } from 'vitest';
import {
  applyFilters, canFollow, countFacets, flightOptionsFromVariants, formatDuration, matchRoute, minPrice, noFilters,
  originChoices, pickDate, pruneFilters, slotOf, sortFlights, summarizeDays, type FlightOption,
} from '../../src/features/flights/results/flightModel';
import { buildFlightResultsHref, parseFlightSearch } from '../../src/features/flights/results/flightHref';

let seq = 0;
/** Một sản phẩm tầng con của tuyến, đúng hình `GET /products?parentProductId=`. */
function variant(over: Record<string, unknown> = {}, attrs: Record<string, unknown> = {}, extra: Record<string, unknown> = {}) {
  seq += 1;
  return {
    productId: `p${seq}`, name: 'VietJet Air VJ157: Hà Nội - TP. Hồ Chí Minh (21:45)', taxonomy: 'flight', destination: 'TP. Hồ Chí Minh',
    unitPrice: 656000, currency: 'VND', priceUnit: 'PER_PERSON', available: true, availableFrom: '2026-10-27', availableTo: '2026-10-27',
    attributes: {
      level: 'flight', airline: 'VietJet Air', airlineCode: 'VJ', flightNumber: 'VJ157', originAirport: 'HAN', destinationAirport: 'SGN',
      originCity: 'Hà Nội', destinationCity: 'TP. Hồ Chí Minh', destinationAirportName: 'Sân bay quốc tế Tân Sơn Nhất',
      departureAt: '2026-10-27T21:45:00+07:00', arrivalAt: '2026-10-27T23:55:00+07:00', durationMinutes: 130, nonstop: true, tripType: 'oneWay',
      ...attrs,
    },
    ...extra, ...over,
  } as any;
}

const fare = (productId: string, code: string | null, name: string, price: number, status = 'AVAILABLE') =>
  ({ productId, code, name, price, currency: 'VND', availabilityStatus: status, carryOnKg: null, checkedKg: null });

describe('flightOptionsFromVariants', () => {
  it('maps one bookable one-way flight and keeps unknown fields unknown', () => {
    const [option] = flightOptionsFromVariants([variant({}, { nonstop: undefined, durationMinutes: undefined })]);
    expect(option).toMatchObject({
      date: '2026-10-27', depClock: '21:45', arrClock: '23:55', depMinutes: 21 * 60 + 45, arrDayOffset: 0, from: 'HAN', to: 'SGN',
      airline: 'VietJet Air', airlineCode: 'VJ', flightNumber: 'VJ157', toAirportName: 'Sân bay quốc tế Tân Sơn Nhất',
    });
    expect(option.nonstop).toBeNull();
    expect(option.durationMinutes).toBe(130); // suy từ giờ đi và giờ đến khi nguồn không có
    expect(option.fares).toHaveLength(1);
    expect(option.fares[0]).toMatchObject({ price: 656000, name: '', code: null, simulated: false, expired: false, carryOnKg: null, checkedKg: null });
  });

  it('drops round trips, sold-out, unpriced, not ticketed and undated flights', () => {
    const options = flightOptionsFromVariants([
      variant({}, { tripType: 'roundTrip' }),
      variant({ available: false }),
      variant({ unitPrice: null }),
      variant({}, { ticketed: false }),
      variant({}, { departureAt: undefined }),
      variant({}, { level: 'route' }),
      variant({}, { tripType: undefined }), // vé cũ không ghi loại vẫn là một chiều
    ]);
    expect(options).toHaveLength(1);
  });

  it('shows an overnight arrival as +1 day and reads nonstop as a tri-state', () => {
    const [late, direct, unknown, connecting] = flightOptionsFromVariants([
      variant({}, { flightNumber: 'VJ169', departureAt: '2026-10-03T22:25:00+07:00', arrivalAt: '2026-10-04T00:35:00+07:00' }),
      variant({}, { flightNumber: 'VJ1', nonstop: true }),
      variant({}, { flightNumber: 'VJ2', nonstop: undefined }),
      variant({}, { flightNumber: 'VJ3', nonstop: false }),
    ]);
    const by = (n: string) => [late, direct, unknown, connecting].find((o) => o.flightNumber === n)!;
    expect(by('VJ169').arrDayOffset).toBe(1);
    expect(by('VJ1').nonstop).toBe(true);
    expect(by('VJ2').nonstop).toBeNull();
    expect(by('VJ3').nonstop).toBe(false);
  });

  it('derives the airline code from the flight number when the source has none', () => {
    const [option] = flightOptionsFromVariants([variant({}, { airlineCode: undefined, flightNumber: 'VN6023' })]);
    expect(option.airlineCode).toBe('VN');
  });

  it('groups the fare classes of one itinerary into one card, in the order the backend sends', () => {
    const classes = (ids: string[]) => [
      fare(ids[0], 'ECO', 'Phổ thông', 656000), fare(ids[1], 'BUS', 'Thương gia', 1738000),
    ];
    const economy = variant({ productId: 'eco', fareClasses: classes(['eco', 'biz']) });
    const business = variant({ productId: 'biz', unitPrice: 1738000, name: 'VJ157 — Thương gia (giá minh hoạ)', fareClasses: classes(['eco', 'biz']) }, { simulated: true });
    const other = variant({ productId: 'solo', fareClasses: [fare('solo', null, 'Giá rẻ nhất', 700000)] }, { flightNumber: 'VJ999' });

    // Thứ tự vào đảo ngược: thẻ vẫn theo thứ tự hạng của backend, không theo thứ tự danh sách.
    const options = flightOptionsFromVariants([business, other, economy]);
    expect(options).toHaveLength(2);
    const grouped = options.find((o) => o.flightNumber === 'VJ157')!;
    expect(grouped.fares.map((f) => [f.productId, f.code, f.simulated])).toEqual([['eco', 'ECO', false], ['biz', 'BUS', true]]);
    expect(minPrice(grouped)).toBe(656000);
    expect(options.find((o) => o.flightNumber === 'VJ999')!.fares[0].name).toBe('Giá rẻ nhất');
  });

  it('marks an expired quote without hiding the flight', () => {
    const [option] = flightOptionsFromVariants([variant({ productId: 'x', fareClasses: [fare('x', null, 'Giá rẻ nhất', 656000, 'EXPIRED')] })]);
    expect(option.fares[0].expired).toBe(true);
  });

  it('recognises a simulated fare by the name suffix too', () => {
    const [option] = flightOptionsFromVariants([variant({ name: 'VJ157 — Thương gia (giá minh hoạ)' })]);
    expect(option.fares[0].simulated).toBe(true);
  });
});

describe('formatDuration', () => {
  it('formats hours and zero-padded minutes', () => {
    expect(formatDuration(130)).toBe("2h10'");
    expect(formatDuration(125)).toBe("2h05'");
    expect(formatDuration(60)).toBe("1h00'");
  });
});

describe('slotOf', () => {
  it('splits the day into five slots with the start included and the end excluded', () => {
    const at = (h: number, m = 0) => slotOf(h * 60 + m);
    expect([at(5), at(10, 59), at(11), at(13, 59), at(14), at(17, 59), at(18), at(21, 59)])
      .toEqual(['morning', 'morning', 'noon', 'noon', 'afternoon', 'afternoon', 'evening', 'evening']);
    expect([at(22), at(23, 59), at(0), at(4, 59)]).toEqual(['late', 'late', 'late', 'late']);
  });
});

function options(): FlightOption[] {
  return flightOptionsFromVariants([
    variant({ unitPrice: 900000, availableFrom: '2026-10-05' }, { flightNumber: 'VN1', airline: 'Vietnam Airlines', airlineCode: 'VN', departureAt: '2026-10-05T06:00:00+07:00', arrivalAt: '2026-10-05T08:10:00+07:00', durationMinutes: 130 }),
    variant({ unitPrice: 700000, availableFrom: '2026-10-05' }, { flightNumber: 'VJ1', departureAt: '2026-10-05T12:30:00+07:00', arrivalAt: '2026-10-05T14:40:00+07:00', durationMinutes: undefined, nonstop: undefined }),
    variant({ unitPrice: 800000, availableFrom: '2026-10-05' }, { flightNumber: 'VJ2', departureAt: '2026-10-05T19:00:00+07:00', arrivalAt: '2026-10-05T21:05:00+07:00', durationMinutes: 125, nonstop: false }),
    variant({ unitPrice: 650000, availableFrom: '2026-10-06' }, { flightNumber: 'VJ3', departureAt: '2026-10-06T23:00:00+07:00', arrivalAt: '2026-10-07T01:10:00+07:00', durationMinutes: 130 }),
  ]);
}
const numbers = (list: FlightOption[]) => list.map((o) => o.flightNumber);

describe('filters and sorting', () => {
  it('filters by time slot, airline and stops; an empty filter keeps everything', () => {
    const all = options();
    expect(applyFilters(all, noFilters())).toHaveLength(4);
    expect(numbers(applyFilters(all, { ...noFilters(), slots: new Set(['morning', 'evening']) }))).toEqual(['VN1', 'VJ2']);
    expect(numbers(applyFilters(all, { ...noFilters(), hiddenAirlines: new Set(['VietJet Air']) }))).toEqual(['VN1']);
    // "Bay thẳng" giữ chuyến nonstop = true; chuyến chưa rõ không được coi là bay thẳng.
    expect(numbers(applyFilters(all, { ...noFilters(), stops: new Set(['nonstop']) }))).toEqual(['VN1', 'VJ3']);
    expect(numbers(applyFilters(all, { ...noFilters(), stops: new Set(['connecting']) }))).toEqual(['VJ2']);
  });

  it('sorts by price, departure time and duration', () => {
    const all = options();
    expect(numbers(sortFlights(all, 'price'))).toEqual(['VJ3', 'VJ1', 'VJ2', 'VN1']);
    expect(numbers(sortFlights(all, 'early'))).toEqual(['VN1', 'VJ1', 'VJ2', 'VJ3']);
    expect(numbers(sortFlights(all, 'late'))).toEqual(['VJ3', 'VJ2', 'VJ1', 'VN1']);
    // Ngắn nhất trước; bằng nhau thì rẻ hơn trước.
    expect(numbers(sortFlights(all, 'fast'))).toEqual(['VJ2', 'VJ3', 'VJ1', 'VN1']);
  });

  it('counts facets and prunes filters that no longer match anything', () => {
    const all = options().filter((o) => o.date === '2026-10-05');
    const facets = countFacets(all);
    expect(facets.slots.get('morning')).toBe(1);
    expect(facets.slots.get('late')).toBeUndefined();
    expect(facets.airlines.get('VietJet Air')).toBe(2);
    expect([facets.nonstop, facets.connecting]).toEqual([1, 1]);

    const pruned = pruneFilters({ slots: new Set(['morning', 'late']), hiddenAirlines: new Set(['X']), stops: new Set(['nonstop', 'connecting']) }, countFacets([all[0]]));
    expect([...pruned.slots]).toEqual(['morning']);
    expect([...pruned.stops]).toEqual(['nonstop']);
    expect([...pruned.hiddenAirlines]).toEqual(['X']);
  });
});

describe('days', () => {
  it('lists only days that have flights, from a start date, with the cheapest price and the count', () => {
    const all = options();
    expect(summarizeDays(all)).toEqual([
      { date: '2026-10-05', minPrice: 700000, count: 3 },
      { date: '2026-10-06', minPrice: 650000, count: 1 },
    ]);
    expect(summarizeDays(all, '2026-10-06').map((d) => d.date)).toEqual(['2026-10-06']);
  });

  it('opens on the wanted day, else the next day with flights, else the last one', () => {
    const days = summarizeDays(options());
    expect(pickDate(days, '2026-10-06')).toEqual({ date: '2026-10-06', exact: true });
    expect(pickDate(days, '2026-10-02')).toEqual({ date: '2026-10-05', exact: false });
    expect(pickDate(days, '2026-11-01')).toEqual({ date: '2026-10-06', exact: false });
    expect(pickDate(days, undefined)).toEqual({ date: '2026-10-05', exact: true });
    expect(pickDate([], '2026-10-05')).toBeNull();
  });
});

describe('canFollow', () => {
  it('needs the return flight to take off after the outbound lands, even across midnight', () => {
    const [outbound] = flightOptionsFromVariants([variant({}, { departureAt: '2026-10-03T22:25:00+07:00', arrivalAt: '2026-10-04T00:35:00+07:00' })]);
    const [before, after] = flightOptionsFromVariants([
      variant({}, { flightNumber: 'R1', departureAt: '2026-10-04T00:10:00+07:00', arrivalAt: '2026-10-04T02:10:00+07:00' }),
      variant({}, { flightNumber: 'R2', departureAt: '2026-10-04T05:00:00+07:00', arrivalAt: '2026-10-04T07:00:00+07:00' }),
    ]);
    expect(canFollow(outbound, before)).toBe(false);
    expect(canFollow(outbound, after)).toBe(true);
  });
});

describe('matchRoute / originChoices', () => {
  const route = (originCity: string, airport: string) => ({ productId: airport, destination: 'TP. Hồ Chí Minh', attributes: { level: 'route', originCity, originAirports: [airport] } }) as any;
  const routes = [route('Hà Nội', 'HAN'), route('Thanh Hóa', 'THD'), route('TP. Hồ Chí Minh', 'SGN'), route('Đà Nẵng', 'DAD')];

  it('matches by city or airport code ignoring case and accents', () => {
    expect(matchRoute(routes, 'ha noi')?.productId).toBe('HAN');
    expect(matchRoute(routes, ' ĐÀ NẴNG ')?.productId).toBe('DAD');
    expect(matchRoute(routes, 'sgn')?.productId).toBe('SGN');
  });

  it('accepts a name contained in the city name but never matches inside another word or a code', () => {
    expect(matchRoute(routes, 'Hồ Chí Minh')?.productId).toBe('SGN');
    // "thanh hoa" chứa "han": không được nhận nhầm sân bay HAN.
    expect(matchRoute(routes, 'Thanh Hóa')?.productId).toBe('THD');
    expect(matchRoute(routes, 'Huế')).toBeNull();
    expect(matchRoute(routes, '')).toBeNull();
    expect(matchRoute(routes.filter((r) => r.productId !== 'THD'), 'Thanh Hóa')).toBeNull();
  });

  it('lists each origin city once, in Vietnamese order', () => {
    const cities = originChoices([...routes, route('Hà Nội', 'HAN')]).map((c) => c.city);
    expect(cities).toHaveLength(4);
    expect(cities).toEqual([...cities].sort((a, b) => a.localeCompare(b, 'vi')));
  });
});

describe('flight search URL', () => {
  it('round-trips through build and parse and keeps trip context valid', () => {
    const href = buildFlightResultsHref({ origin: ' Hà Nội ', destination: 'TP. Hồ Chí Minh', trip: { checkIn: '2999-10-02', checkOut: '2999-10-08', adults: 2, children: 1, rooms: 3 } });
    const url = new URL(href, 'http://x');
    expect(url.pathname).toBe('/flights');
    expect(url.searchParams.get('origin')).toBe('Hà Nội');
    expect(url.searchParams.get('rooms')).toBeNull();
    expect(parseFlightSearch(url.searchParams)).toEqual({
      origin: 'Hà Nội', destination: 'TP. Hồ Chí Minh', trip: { checkIn: '2999-10-02', checkOut: '2999-10-08', adults: 2, children: 1 },
    });
  });

  it('is a search only when both the origin and the destination are present', () => {
    expect(parseFlightSearch(new URLSearchParams('destination=Nha+Trang'))).toBeNull();
    expect(parseFlightSearch(new URLSearchParams('origin=H%C3%A0+N%E1%BB%99i'))).toBeNull();
    expect(parseFlightSearch(new URLSearchParams('origin=+&destination=X'))).toBeNull();
  });
});
