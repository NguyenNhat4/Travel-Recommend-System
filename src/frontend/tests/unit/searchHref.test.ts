import { describe, expect, it } from 'vitest';
import { buildSearchHref, filterDestinations, fold, matchDestination, pickParam } from '../../src/features/catalog/landing/searchHref';

const DESTS = [{ destination: 'Đà Nẵng' }, { destination: 'Nha Trang' }, { destination: 'Phú Quốc' }];

describe('fold / matchDestination', () => {
  it('ignores diacritics and case', () => {
    expect(fold('Đà Nẵng')).toBe('da nang');
    expect(matchDestination('da nang', DESTS)).toBe('Đà Nẵng');
    expect(matchDestination('  NHA TRANG ', DESTS)).toBe('Nha Trang');
  });

  it('returns null for partial, empty or unknown text and when the list has not loaded', () => {
    expect(matchDestination('Nha', DESTS)).toBeNull();
    expect(matchDestination('', DESTS)).toBeNull();
    expect(matchDestination('Nha Trang', null)).toBeNull();
  });
});

describe('filterDestinations', () => {
  it('keeps order for empty text and filters by substring otherwise', () => {
    expect(filterDestinations('', DESTS).map((d) => d.destination)).toEqual(['Đà Nẵng', 'Nha Trang', 'Phú Quốc']);
    expect(filterDestinations('nha', DESTS).map((d) => d.destination)).toEqual(['Nha Trang']);
    expect(filterDestinations('quoc', DESTS).map((d) => d.destination)).toEqual(['Phú Quốc']);
    expect(filterDestinations('x', DESTS)).toEqual([]);
    expect(filterDestinations('', DESTS, 2)).toHaveLength(2);
  });
});

describe('buildSearchHref', () => {
  const trip = { checkIn: '2026-10-15', checkOut: '2026-10-17', adults: 2, children: 1, rooms: 1 };

  it('uses the category default query when nothing is typed and adds trip context', () => {
    const href = buildSearchHref({ taxonomy: 'hotel', origin: '', location: '', destination: null, trip });
    const url = new URL(href, 'http://x');
    expect(url.pathname).toBe('/search');
    expect(url.searchParams.get('q')).toBe('khách sạn');
    expect(url.searchParams.get('type')).toBe('hotel');
    expect(url.searchParams.get('destination')).toBeNull();
    expect(url.searchParams.get('checkIn')).toBe('2026-10-15');
    expect(url.searchParams.get('checkOut')).toBe('2026-10-17');
    expect(url.searchParams.get('rooms')).toBe('1');
    expect(url.searchParams.get('adults')).toBe('2');
    expect(url.searchParams.get('children')).toBe('1');
  });

  it('sends a matched destination as a filter and free text as the query', () => {
    const chosen = new URL(buildSearchHref({ taxonomy: 'hotel', origin: '', location: 'Nha Trang', destination: 'Nha Trang', trip: {} }), 'http://x');
    expect(chosen.searchParams.get('destination')).toBe('Nha Trang');
    expect(chosen.searchParams.get('q')).toBe('khách sạn');

    const free = new URL(buildSearchHref({ taxonomy: 'hotel', origin: '', location: 'resort yên tĩnh có hồ bơi', destination: null, trip: {} }), 'http://x');
    expect(free.searchParams.get('q')).toBe('resort yên tĩnh có hồ bơi');
    expect(free.searchParams.get('destination')).toBeNull();
  });

  it('puts the flight origin in the query and searches "vé máy bay" without one', () => {
    const from = new URL(buildSearchHref({ taxonomy: 'flight', origin: ' Hà Nội ', location: 'Đà Nẵng', destination: 'Đà Nẵng', trip: {} }), 'http://x');
    expect(from.searchParams.get('q')).toBe('Hà Nội');
    expect(from.searchParams.get('type')).toBe('flight');
    const bare = new URL(buildSearchHref({ taxonomy: 'flight', origin: '', location: '', destination: null, trip: {} }), 'http://x');
    expect(bare.searchParams.get('q')).toBe('vé máy bay');
  });

  it('ends without a dangling & when there is no trip context', () => {
    expect(buildSearchHref({ taxonomy: 'golf', origin: '', location: '', destination: null, trip: {} })).toBe('/search?q=s%C3%A2n+golf&type=golf');
  });
});

describe('pickParam', () => {
  it('takes the first value and trims; empty is undefined', () => {
    expect(pickParam(['Nha Trang', 'x'])).toBe('Nha Trang');
    expect(pickParam('  golf ')).toBe('golf');
    expect(pickParam('   ')).toBeUndefined();
    expect(pickParam(undefined)).toBeUndefined();
  });
});
