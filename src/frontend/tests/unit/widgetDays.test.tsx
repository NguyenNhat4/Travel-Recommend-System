// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { WidgetDays } from '../../src/features/itinerary/widget/WidgetDays';
import { convertItineraryCompletedToGroundedPlan } from '../../src/features/itinerary/widget/widgetPlan';
import type { FloatingWidgetController } from '../../src/features/itinerary/widget/useFloatingWidget';
import type { components } from '../../src/types/api.gen';

const summary = (productId: string, name: string, taxonomy: 'hotel' | 'attraction', extra: object = {}) => ({
  productId, name, taxonomy, destination: 'Nha Trang', unitPrice: 200000, priceUnit: 'PER_PERSON', currency: 'VND',
  available: true, ...extra,
});

// Chữ "phố", "show" trong tên và ghi chú từng làm widget chọn ảnh stock theo từ khoá (sân golf, sân khấu) thay cho ảnh thật.
const response = {
  status: 'COMPLETED', conversationId: 'c1', warnings: [],
  intent: { destination: 'Nha Trang', days: 1, party: { type: null, adults: 2, children: 0 } },
  itinerary: {
    stay: {
      product: summary('h1', 'Khách sạn phố biển', 'hotel', { imageUrl: 'https://cdn.example.vn/h1.jpg', attributes: { starRating: 3 } }),
      nights: 1, note: null,
    },
    days: [{ day: 1, slots: [
      { time: 'MORNING', note: 'Dạo phố cổ rồi xem show.', source: 'SEARCH',
        product: summary('a1', 'Tata Show', 'attraction', { imageUrl: 'https://cdn.example.vn/a1.jpg' }) },
      { time: 'EVENING', product: null, activityType: 'MEAL', note: 'Ăn tối ở thành phố biển.', source: null },
    ] }],
    estimatedTotal: null, currency: 'VND', budgetStatus: 'UNKNOWN',
  },
} as unknown as components['schemas']['ItineraryCompleted'];

function renderDays() {
  const widget = {
    activePlan: convertItineraryCompletedToGroundedPlan(response), activeDayTab: 0,
    setHoveredCoordinate: vi.fn(), setHoveredPointId: vi.fn(), focusedProductId: null,
  } as unknown as FloatingWidgetController;
  return render(<WidgetDays widget={widget} />);
}

describe('WidgetDays', () => {
  afterEach(cleanup);

  it('shows only the catalog image of each product, never a keyword stock photo', () => {
    const { container } = renderDays();
    const sources = Array.from(container.querySelectorAll('img')).map((image) => image.getAttribute('src'));
    expect(sources).toEqual(['https://cdn.example.vn/h1.jpg', 'https://cdn.example.vn/a1.jpg']);
  });

  it('tags the hotel from its real attributes and invents no star class or note', () => {
    renderDays();
    expect(screen.getByText('3 sao')).toBeTruthy();
    expect(screen.queryByText(/5★|5 sao|cao cấp/)).toBeNull();
  });

  it('labels an activity note by its type, without an image', () => {
    renderDays();
    expect(screen.getAllByText('Ăn uống').length).toBeGreaterThan(0);
    expect(screen.queryByAltText('Ăn uống')).toBeNull();
  });
});
