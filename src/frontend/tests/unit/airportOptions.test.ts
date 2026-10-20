import { describe, expect, it } from 'vitest';
import {
  DOMESTIC_TITLE, POPULAR_TITLE, RECENT_TITLE, airportLabel, airportSections, flattenSections, matchAirport,
} from '../../src/features/flights/airports/airportOptions';
import { startsAWord } from '../../src/features/catalog/landing/searchHref';
import type { FlightAirport } from '../../src/services/flights';

const air = (code: string, city: string, routeCount: number, name: string | null = null): FlightAirport => ({ code, city, name, routeCount });

// Số tuyến khác nhau để kiểm thứ tự "phổ biến": SGN, HAN, DAD nhiều nhất; DLI và CXR cùng 20 (xếp theo tên thành phố).
const AIRPORTS: FlightAirport[] = [
  air('VCS', 'Côn Đảo', 2, 'Sân bay Côn Đảo'),
  air('SGN', 'TP. Hồ Chí Minh', 36, 'Sân bay quốc tế Tân Sơn Nhất'),
  air('HAN', 'Hà Nội', 31, 'Sân bay quốc tế Nội Bài'),
  air('DAD', 'Đà Nẵng', 26, 'Sân bay quốc tế Đà Nẵng'),
  air('CXR', 'Nha Trang', 20, 'Sân bay quốc tế Cam Ranh'),
  air('PQC', 'Phú Quốc', 20, 'Sân bay quốc tế Phú Quốc'),
  air('DLI', 'Đà Lạt', 20, 'Sân bay Liên Khương'),
];

const texts = (sections: ReturnType<typeof airportSections>) => sections.map((s) => [s.title, s.airports.map((a) => a.city)]);

describe('startsAWord', () => {
  it('matches the start of a word, ignoring diacritics and case (FR-SRC-05)', () => {
    expect(startsAWord('Hà Nội', 'ha')).toBe(true);
    expect(startsAWord('Hạ Long', 'ha')).toBe(true);
    expect(startsAWord('Đà Nẵng', 'DA')).toBe(true);
    expect(startsAWord('Nha Trang', 'trang')).toBe(true);
    expect(startsAWord('Đà Nẵng', 'nang')).toBe(true);
  });

  it('does not match inside a word, and matches a phrase from a word start', () => {
    expect(startsAWord('Nha Trang', 'ang')).toBe(false);
    expect(startsAWord('Sân bay quốc tế Cam Ranh', 'cam ranh')).toBe(true);
    expect(startsAWord('Sân bay quốc tế Cam Ranh', 'quoc te cam')).toBe(true);
    expect(startsAWord('Sân bay quốc tế Cam Ranh', 'bay cam')).toBe(false);
  });

  it('empty query matches everything', () => {
    expect(startsAWord('Hà Nội', '   ')).toBe(true);
  });
});

describe('matchAirport', () => {
  it('accepts an airport code, its "Thành phố (MÃ)" label, or a city that has one airport', () => {
    expect(matchAirport('sgn', AIRPORTS)?.code).toBe('SGN');
    expect(matchAirport('TP. Hồ Chí Minh (SGN)', AIRPORTS)?.code).toBe('SGN');
    expect(matchAirport('ha noi', AIRPORTS)?.code).toBe('HAN');
    expect(matchAirport('Đà Nẵng', AIRPORTS)?.code).toBe('DAD');
  });

  it('rejects any other text, so the field can be cleared (spec §4.4)', () => {
    expect(matchAirport('xứ sở thần tiên', AIRPORTS)).toBeNull();
    expect(matchAirport('Đà', AIRPORTS)).toBeNull();
    expect(matchAirport('Hà', AIRPORTS)).toBeNull();
    expect(matchAirport('', AIRPORTS)).toBeNull();
    expect(matchAirport('Hà Nội', null)).toBeNull();
  });

  it('a city with more than one airport must be picked by code or label', () => {
    const two = [air('SGN', 'TP. Hồ Chí Minh', 36), air('XXX', 'TP. Hồ Chí Minh', 1)];
    expect(matchAirport('TP. Hồ Chí Minh', two)).toBeNull();
    expect(matchAirport('XXX', two)?.code).toBe('XXX');
  });
});

describe('airportSections', () => {
  it('empty text: recent first, then the five busiest airports, then the rest of the domestic list by city', () => {
    const sections = airportSections({ text: '', airports: AIRPORTS, recent: ['Nha Trang'] });
    expect(texts(sections)).toEqual([
      [RECENT_TITLE, ['Nha Trang']],
      [POPULAR_TITLE, ['TP. Hồ Chí Minh', 'Hà Nội', 'Đà Nẵng', 'Đà Lạt', 'Phú Quốc']],
      [DOMESTIC_TITLE, ['Côn Đảo']],
    ]);
  });

  it('without history the popular group starts at the busiest airport and nothing repeats', () => {
    const sections = airportSections({ text: '', airports: AIRPORTS, recent: [] });
    expect(sections[0].title).toBe(POPULAR_TITLE);
    const all = flattenSections(sections).map((a) => a.code);
    expect(new Set(all).size).toBe(all.length);
    expect(all).toHaveLength(AIRPORTS.length);
  });

  it('recent entries that are no longer current airports are dropped', () => {
    const sections = airportSections({ text: '', airports: AIRPORTS, recent: ['Atlantis', 'Hà Nội'] });
    expect(sections[0]).toEqual({ title: RECENT_TITLE, airports: [AIRPORTS[2]] });
  });

  it('typing: one group of matches, starts-with first, at most eight', () => {
    const sections = airportSections({ text: 'da', airports: AIRPORTS, recent: [] });
    expect(sections.map((s) => s.title)).toEqual([POPULAR_TITLE]);
    // "Đà" bắt đầu thành phố nên xếp trước; "Côn Đảo" chỉ khớp ở từ "Đảo" (bỏ dấu là "dao").
    expect(sections[0].airports.map((a) => a.city)).toEqual(['Đà Lạt', 'Đà Nẵng', 'Côn Đảo']);
  });

  it('typing matches the airport name too', () => {
    const sections = airportSections({ text: 'cam ranh', airports: AIRPORTS, recent: [] });
    expect(sections[0].airports.map((a) => a.code)).toEqual(['CXR']);
  });

  it('typing nothing that matches gives no groups', () => {
    expect(airportSections({ text: 'xứ sở', airports: AIRPORTS, recent: [] })).toEqual([]);
  });

  it('excludes the airport chosen at the other field', () => {
    const sections = airportSections({ text: '', airports: AIRPORTS, recent: [], exclude: AIRPORTS[1] });
    expect(flattenSections(sections).map((a) => a.code)).not.toContain('SGN');
    expect(airportLabel(AIRPORTS[1])).toBe('TP. Hồ Chí Minh (SGN)');
  });
});
