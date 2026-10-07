import { describe, expect, it } from 'vitest';
import { convertItineraryCompletedToGroundedPlan, locateProduct, narrationProducts } from '../../src/features/itinerary/widget/widgetPlan';
import { itineraryCartItems } from '../../src/components/assistant/AssistantResultPanel';
import { nearestDepartureCity } from '../../src/services/flights';
import type { components } from '../../src/types/api.gen';

/** Vé máy bay của lịch trình (AC-AGT-02) và gợi ý nơi đi từ vị trí (AC-AGT-03). */
const summary = (productId: string, taxonomy: 'hotel' | 'attraction' | 'flight', destination = 'Đà Nẵng') => ({
  productId, name: `Sản phẩm ${productId}`, taxonomy, destination, unitPrice: 1_000_000, priceUnit: 'PER_PERSON',
  currency: 'VND', available: true,
}) as components['schemas']['ProductSummary'];

const response = {
  status: 'COMPLETED', conversationId: 'c1', warnings: [],
  intent: { destination: 'Đà Nẵng', origin: 'Hà Nội', days: 3, party: { type: 'COUPLE', adults: 2, children: 0 } },
  itinerary: {
    flights: [
      { product: summary('out', 'flight'), direction: 'OUTBOUND', date: '2026-10-15', passengers: 2, source: 'SEARCH' },
      { product: summary('back', 'flight', 'Hà Nội'), direction: 'RETURN', date: '2026-10-17', passengers: 2, source: 'SEARCH' },
    ],
    stay: { product: summary('h1', 'hotel'), nights: 2 },
    days: [
      { day: 1, date: '2026-10-15', slots: [] },
      { day: 2, date: '2026-10-16', slots: [{ time: 'MORNING', product: summary('t1', 'attraction'), note: null, source: 'SEARCH' }] },
      { day: 3, date: '2026-10-17', slots: [] },
    ],
    estimatedTotal: 6_000_000, currency: 'VND', budgetStatus: 'NO_BUDGET',
  },
} as unknown as components['schemas']['ItineraryCompleted'];

describe('flights in the assistant itinerary', () => {
  it('keeps both legs in the plan with direction, date and passengers', () => {
    const plan = convertItineraryCompletedToGroundedPlan(response);
    expect(plan.flights?.map((flight) => [flight.direction, flight.productId, flight.date, flight.passengers])).toEqual([
      ['OUTBOUND', 'out', '2026-10-15', 2], ['RETURN', 'back', '2026-10-17', 2],
    ]);
  });

  it('gives each flight a chat card and a book-now item on its flight date for the whole party', () => {
    expect(Object.keys(narrationProducts(response))).toEqual(expect.arrayContaining(['out', 'back']));
    const items = itineraryCartItems(response.itinerary, response.intent.party);
    expect(items.filter((item) => item.product.taxonomy === 'flight').map((item) => [item.product.productId, item.usingDate, item.party]))
      .toEqual([['out', '2026-10-15', { adults: 2, children: 0 }], ['back', '2026-10-17', { adults: 2, children: 0 }]]);
  });

  it('focuses the outbound leg on the first day and the return leg on the last day', () => {
    const plan = convertItineraryCompletedToGroundedPlan(response);
    expect(locateProduct(plan, 'out')).toEqual({ day: 1, pointId: 'flight-out', coordinate: null });
    expect(locateProduct(plan, 'back')).toEqual({ day: 3, pointId: 'flight-back', coordinate: null });
  });

  it('has no flights section when the response has none', () => {
    const without = { ...response, itinerary: { ...response.itinerary, flights: undefined } } as unknown as components['schemas']['ItineraryCompleted'];
    expect(convertItineraryCompletedToGroundedPlan(without).flights).toBeUndefined();
  });
});

describe('nearestDepartureCity', () => {
  const airports = [
    { city: 'Hà Nội', latitude: 21.2187, longitude: 105.8042 },
    { city: 'TP. Hồ Chí Minh', latitude: 10.8188, longitude: 106.652 },
    { city: 'Đà Nẵng', latitude: 16.0439, longitude: 108.1992 },
  ];

  it('picks the catalog city whose airport is closest', () => {
    expect(nearestDepartureCity({ latitude: 20.84, longitude: 106.69 }, airports)).toBe('Hà Nội'); // Hải Phòng
    expect(nearestDepartureCity({ latitude: 10.03, longitude: 105.78 }, airports)).toBe('TP. Hồ Chí Minh'); // Cần Thơ
    expect(nearestDepartureCity({ latitude: 15.88, longitude: 108.33 }, airports)).toBe('Đà Nẵng'); // Hội An
  });

  it('returns null when the catalog has no departure airport', () => {
    expect(nearestDepartureCity({ latitude: 21, longitude: 105 }, [])).toBeNull();
  });
});
