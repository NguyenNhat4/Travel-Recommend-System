import { describe, expect, it } from 'vitest';
import { convertItineraryCompletedToGroundedPlan, isFreeToVisit, locateProduct, partyLabel } from '../../src/features/itinerary/widget/widgetPlan';
import { hotelTags } from '../../src/features/itinerary/widget/widgetVisuals';
import type { components } from '../../src/types/api.gen';

const product = (productId: string, name: string, taxonomy: 'hotel' | 'attraction') => ({
  productId, name, taxonomy, destination: 'Hà Nội', unitPrice: 100000, priceUnit: 'PER_PERSON', currency: 'VND', available: true,
}) as components['schemas']['ProductSummary'];

const response = {
  status: 'COMPLETED', conversationId: 'c1', warnings: [],
  intent: { destination: 'Hà Nội', days: 2, party: { type: 'COUPLE', adults: 2, children: 0 } },
  itinerary: {
    stay: { product: product('h1', 'Old Quarter Hotel', 'hotel'), nights: 1 },
    days: [
      { day: 1, slots: [{ time: 'MORNING', product: product('t1', 'Tour 1', 'attraction'), note: null }] },
      { day: 2, slots: [
        { time: 'MORNING', product: product('t2', 'Tour 2', 'attraction'), note: null },
        { time: 'AFTERNOON', product: product('t3', 'Tour 3', 'attraction'), note: null },
      ] },
    ],
    estimatedTotal: null, currency: 'VND', budgetStatus: 'UNKNOWN',
  },
} as unknown as components['schemas']['ItineraryCompleted'];

describe('convertItineraryCompletedToGroundedPlan', () => {
  it('maps the API slot time to the lowercase buổi used by the widget and the map', () => {
    const plan = convertItineraryCompletedToGroundedPlan(response);
    expect(plan.days[1].slots.map((slot) => slot.time)).toEqual(['morning', 'afternoon']);
  });

  it('places map points only from catalog coordinates, never at a guessed city centre', () => {
    const located = {
      ...response,
      itinerary: {
        ...response.itinerary,
        days: [{ day: 1, slots: [
          { time: 'MORNING', note: null, source: 'SEARCH',
            product: { ...product('t1', 'Tháp Bà', 'attraction'), attributes: { latitude: 12.2655, longitude: 109.1953, address: '2 Tháng 4, Nha Trang' } } },
          { time: 'AFTERNOON', note: null, source: 'SEARCH', product: product('t2', 'Tour 2', 'attraction') },
          { time: 'EVENING', product: null, activityType: 'MEAL', note: 'Ăn tối gần biển.', source: null },
        ] }],
      },
    } as unknown as components['schemas']['ItineraryCompleted'];
    const [withCoords, withoutCoords, meal] = convertItineraryCompletedToGroundedPlan(located).days[0].slots;
    expect(withCoords.coordinates).toEqual({ lat: 12.2655, lng: 109.1953 });
    expect(withCoords.locationName).toBe('2 Tháng 4, Nha Trang');
    expect(withoutCoords.coordinates).toBeUndefined();
    expect(meal).toMatchObject({ coordinates: undefined, activityTitle: 'Ăn uống', activityType: 'MEAL', isActivityNote: true });
  });

  it('labels the party from intent.party and invents neither a party nor a stay note', () => {
    const plan = convertItineraryCompletedToGroundedPlan(response);
    expect(plan.partyLabel).toBe('2 người lớn');
    expect(plan.stay?.note).toBe('');
    const unknownParty = convertItineraryCompletedToGroundedPlan({
      ...response, intent: { ...response.intent!, party: null },
    } as components['schemas']['ItineraryCompleted']);
    expect(unknownParty.partyLabel).toBeNull();
  });
});

describe('partyLabel', () => {
  it('counts adults and children, else falls back to the party type', () => {
    expect(partyLabel({ type: 'FAMILY_WITH_KIDS', adults: 2, children: 1 })).toBe('2 người lớn, 1 trẻ em');
    expect(partyLabel({ type: 'COUPLE', adults: 0, children: 0 })).toBe('Cặp đôi');
    expect(partyLabel(null)).toBeNull();
  });
});

describe('hotelTags', () => {
  it('builds tags only from real attributes, with no default tag', () => {
    expect(hotelTags({ attributes: { starRating: 4, oceanView: true, pool: true } })).toEqual(['4 sao', 'Hướng biển', 'Hồ bơi']);
    expect(hotelTags({ attributes: {} })).toEqual([]);
  });
});

describe('locateProduct', () => {
  const plan = convertItineraryCompletedToGroundedPlan(response);

  it('finds the day and the map point of a scheduled product, numbering stops across days', () => {
    expect(locateProduct(plan, 't1')).toMatchObject({ day: 1, pointId: 'day-1-slot-morning-1' });
    expect(locateProduct(plan, 't3')).toMatchObject({ day: 2, pointId: 'day-2-slot-afternoon-3' });
  });

  it('puts the stay on the first day with the stay point id', () => {
    expect(locateProduct(plan, 'h1')).toMatchObject({ day: 1, pointId: 'stay-h1' });
  });

  it('returns null for a product that is not in the plan', () => {
    expect(locateProduct(plan, 'unknown')).toBeNull();
  });
});

describe('isFreeToVisit', () => {
  it('treats unpriced attractions/golf and ticketed=false as free, never an unpriced hotel', () => {
    expect(isFreeToVisit({ taxonomy: 'attraction', unitPrice: null, attributes: {} })).toBe(true);
    expect(isFreeToVisit({ taxonomy: 'golf', unitPrice: null, attributes: {} })).toBe(true);
    expect(isFreeToVisit({ taxonomy: 'attraction', unitPrice: 50000, attributes: { ticketed: false } })).toBe(true);
    expect(isFreeToVisit({ taxonomy: 'attraction', unitPrice: 50000, attributes: {} })).toBe(false);
    expect(isFreeToVisit({ taxonomy: 'hotel', unitPrice: null, attributes: {} })).toBe(false);
  });
});
