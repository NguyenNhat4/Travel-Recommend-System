import { describe, expect, it } from 'vitest';
import { convertItineraryResponseToGroundedPlan, mapProductSummaryToProduct, planLocationCoverage } from '../../src/services/assistant';
import type { components } from '../../src/types/api.gen';

const unknownProduct: components['schemas']['ProductSummary'] = {
  productId: 'not-in-local-catalog',
  name: 'Sản phẩm từ API',
  taxonomy: 'attraction',
  destination: 'Nha Trang',
  status: 'ACTIVE',
  unitPrice: 500_000,
  currency: 'VND',
  priceUnit: 'PER_PERSON',
  available: true,
};

describe('convertItineraryResponseToGroundedPlan', () => {
  const response: components['schemas']['ItineraryResponse'] = {
    status: 'COMPLETED',
    conversationId: 'conv-1',
    itinerary: {
      days: [{
        day: 1,
        slots: [
          { time: 'MORNING', product: unknownProduct, note: null },
          { time: 'EVENING', product: null, activityType: 'MEAL', note: 'Ăn tối' },
        ],
      }],
      estimatedTotal: null,
      currency: 'VND',
      budgetStatus: 'UNKNOWN',
    },
    warnings: [],
  };

  it('maps contract slot times instead of defaulting every slot to morning', () => {
    const plan = convertItineraryResponseToGroundedPlan(response);
    expect(plan?.days[0].slots.map((slot) => slot.time)).toEqual(['morning', 'evening']);
  });

  it('does not invent coordinates for products without a known location', () => {
    const plan = convertItineraryResponseToGroundedPlan(response)!;
    expect(plan.days[0].slots[0].coordinates).toBeUndefined();
    expect(planLocationCoverage(plan)).toEqual({ located: 0, missing: 1 });
  });

  it('keeps an unknown total as null instead of showing it as free', () => {
    // estimatedTotal null means "chưa tính được", never 0 đ.
    const plan = convertItineraryResponseToGroundedPlan(response)!;
    expect(plan.totalEstimatedPrice).toBeNull();
  });

  it('carries a known total through unchanged', () => {
    const priced = { ...response, itinerary: { ...response.itinerary!, estimatedTotal: 358_808, budgetStatus: 'WITHIN_BUDGET' as const } };
    expect(convertItineraryResponseToGroundedPlan(priced)!.totalEstimatedPrice).toBe(358_808);
  });
});

describe('mapProductSummaryToProduct', () => {
  it('keeps the API name and price', () => {
    const product = mapProductSummaryToProduct(unknownProduct);
    expect(product).toMatchObject({ id: 'not-in-local-catalog', name: 'Sản phẩm từ API', unitPrice: 500_000, available: true });
  });
});
