import { describe, expect, it } from 'vitest';
import { convertItineraryCompletedToGroundedPlan, locateProduct } from '../../src/features/itinerary/widget/widgetPlan';
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
