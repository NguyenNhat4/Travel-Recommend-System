import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { expect, it } from 'vitest';
import { FlightSummary } from '../../src/components/common/FlightSummary';

it('shows the selected cabin and both dated legs for a round trip', () => {
  const html = renderToStaticMarkup(<FlightSummary product={{ taxonomy: 'flight', attributes: {
    level: 'flight', tripType: 'roundTrip', cabinClass: 'BUSINESS', flightNumber: 'VN100',
    originAirport: 'SGN', destinationAirport: 'HAN', departureAt: '2026-10-10T08:00:00+07:00',
    returnFlight: { flightNumber: 'VN101', originAirport: 'HAN', destinationAirport: 'SGN',
      departureAt: '2026-10-13T09:00:00+07:00' },
  } }} />);
  for (const expected of ['Khứ hồi', 'Thương gia', 'VN100', 'VN101', '10/10/2026', '13/10/2026', 'Giá gồm hai chặng / khách']) {
    expect(html).toContain(expected);
  }
});

it('does not invent a cabin on legacy flights or show flight details on hotels', () => {
  expect(renderToStaticMarkup(<FlightSummary product={{ taxonomy: 'flight', attributes: { level: 'flight' } }} />))
    .toContain('Chưa rõ hạng vé');
  expect(renderToStaticMarkup(<FlightSummary product={{ taxonomy: 'hotel', attributes: { level: 'room' } }} />)).toBe('');
});
