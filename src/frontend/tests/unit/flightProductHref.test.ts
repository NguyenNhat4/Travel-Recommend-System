import { describe, expect, it } from 'vitest';
import { flightProductHref } from '../../src/features/flights/results/flightHref';

const flight = { destination: 'Phú Quốc', attributes: { originCity: 'Hà Nội', destinationCity: 'Phú Quốc', departureAt: '2099-01-05T08:00:00+07:00' } };

describe('flightProductHref', () => {
  it('đưa về /flights với điểm đi, điểm đến và ngày bay của vé', () => {
    const url = new URL(flightProductHref(flight)!, 'http://x');
    expect(url.pathname).toBe('/flights');
    expect(url.searchParams.get('origin')).toBe('Hà Nội');
    expect(url.searchParams.get('destination')).toBe('Phú Quốc');
    expect(url.searchParams.get('checkIn')).toBe('2099-01-05');
  });

  it('giữ ngày và số khách đang tìm', () => {
    const url = new URL(flightProductHref(flight, 'checkIn=2099-02-01&adults=2')!, 'http://x');
    expect(url.searchParams.get('checkIn')).toBe('2099-02-01');
    expect(url.searchParams.get('adults')).toBe('2');
  });

  it('thiếu điểm đi thì trả null', () => {
    expect(flightProductHref({ destination: 'Phú Quốc', attributes: {} })).toBeNull();
  });
});


it('carries the exact fare id so the landing page can select the quoted price', () => {
  const href = flightProductHref({ productId: 'fare-cheap', destination: 'Hà Nội',
    attributes: { originCity: 'Đà Nẵng', destinationCity: 'Hà Nội', departureAt: '2999-10-10T08:00:00+07:00' } });
  expect(href).toContain('fare=fare-cheap');
});
