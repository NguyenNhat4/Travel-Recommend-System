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
    setHoveredCoordinate: vi.fn(), setHoveredPointId: vi.fn(), focusedProductId: null, itemActions: () => null,
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

  it('shows the room count next to the nightly price when the group needs several rooms', () => {
    const rooms = { ...response, itinerary: { ...response.itinerary,
      stay: { ...response.itinerary.stay!, product: { ...response.itinerary.stay!.product, priceUnit: 'PER_NIGHT' }, rooms: 5 } } };
    const widget = {
      activePlan: convertItineraryCompletedToGroundedPlan(rooms as typeof response), activeDayTab: 0,
      setHoveredCoordinate: vi.fn(), setHoveredPointId: vi.fn(), focusedProductId: null, itemActions: () => null,
    } as unknown as FloatingWidgetController;
    render(<WidgetDays widget={widget} />);
    expect(screen.getByText('200.000 ₫/đêm × 5 phòng')).toBeTruthy();
  });

  it('does not mention rooms for one room', () => {
    renderDays();
    expect(screen.getByText('200.000 ₫/đêm')).toBeTruthy();
  });

  it('labels an activity note by its type, without an image', () => {
    renderDays();
    expect(screen.getAllByText('Ăn uống').length).toBeGreaterThan(0);
    expect(screen.queryByAltText('Ăn uống')).toBeNull();
  });
});

describe('WidgetDays flights (AC-AGT-02)', () => {
  afterEach(cleanup);

  const flight = (productId: string, destination: string, direction: string, date: string, extra: object) => ({
    product: { ...summary(productId, `Vé ${productId}`, 'attraction'), taxonomy: 'flight', destination, unitPrice: 1_000_000, ...extra },
    direction, date, passengers: 2, source: 'SEARCH',
  });

  it('opens the first day with the outbound leg and closes the last day with the return leg', () => {
    const withFlights = {
      ...response,
      intent: { ...response.intent, days: 2 },
      itinerary: {
        ...response.itinerary,
        flights: [
          flight('out', 'Nha Trang', 'OUTBOUND', '2026-10-15',
            { attributes: { airline: 'VietJet Air', flightNumber: 'VJ601', departureTimeLocal: '06:45', arrivalTimeLocal: '07:55', nonstop: true } }),
          flight('back', 'Hà Nội', 'RETURN', '2026-10-16', { attributes: { airline: 'Vietnam Airlines', departureTimeLocal: '19:00' } }),
        ],
        days: [response.itinerary.days[0], { day: 2, slots: [] }],
      },
    } as unknown as components['schemas']['ItineraryCompleted'];
    const widget = {
      activePlan: convertItineraryCompletedToGroundedPlan(withFlights), activeDayTab: 0,
      setHoveredCoordinate: vi.fn(), setHoveredPointId: vi.fn(), focusedProductId: null, itemActions: () => null,
    } as unknown as FloatingWidgetController;
    render(<WidgetDays widget={widget} />);

    const cards = screen.getAllByTestId('itinerary-flight');
    expect(cards.map((card) => card.getAttribute('data-product-id'))).toEqual(['out', 'back']);
    expect(cards[0].textContent).toContain('Chặng đi · 15/10/2026');
    expect(cards[0].textContent).toContain('VietJet Air · VJ601');
    expect(cards[0].textContent).toContain('06:45 → 07:55');
    expect(cards[0].textContent).toContain('Bay thẳng');
    expect(cards[0].textContent).toContain('1.000.000 ₫/khách × 2');
    expect(cards[1].textContent).toContain('Chặng về · 16/10/2026');
    expect(cards[1].textContent).not.toContain('Bay thẳng');
  });

  it('shows the airport transfer line of a late-landing day without an image (chốt 2026-10-07)', () => {
    const lateLanding = {
      ...response,
      itinerary: {
        ...response.itinerary,
        days: [{ day: 1, slots: [
          { time: 'EVENING', product: null, activityType: 'TRANSFER', note: 'Di chuyển từ sân bay, nhận phòng.', source: null },
        ] }],
      },
    } as unknown as components['schemas']['ItineraryCompleted'];
    const widget = {
      activePlan: convertItineraryCompletedToGroundedPlan(lateLanding), activeDayTab: 0,
      setHoveredCoordinate: vi.fn(), setHoveredPointId: vi.fn(), focusedProductId: null, itemActions: () => null,
    } as unknown as FloatingWidgetController;
    render(<WidgetDays widget={widget} />);
    expect(screen.getAllByText('Di chuyển').length).toBeGreaterThan(0);
    expect(screen.getByText('Di chuyển từ sân bay, nhận phòng.')).toBeTruthy();
    expect(screen.queryByAltText('Di chuyển')).toBeNull();
  });
});

describe('WidgetDays hotel change (AC-AGT-04, contract 1.19.0)', () => {
  afterEach(cleanup);

  it('shows on each day the hotel of that night, and the last day keeps the hotel of the night before', () => {
    const north = { product: summary('h1', 'Khách sạn Bắc đảo', 'hotel'), nights: 2, fromNight: 1, note: null };
    const south = { product: summary('h2', 'Khách sạn Nam đảo', 'hotel'), nights: 2, fromNight: 3, note: null };
    const fiveDays = {
      ...response,
      intent: { ...response.intent, days: 5 },
      itinerary: {
        ...response.itinerary, stay: north, stays: [north, south],
        days: [1, 2, 3, 4, 5].map((day) => ({ day, slots: [] })),
      },
    } as unknown as components['schemas']['ItineraryCompleted'];
    const widget = {
      activePlan: convertItineraryCompletedToGroundedPlan(fiveDays), activeDayTab: 0,
      setHoveredCoordinate: vi.fn(), setHoveredPointId: vi.fn(), focusedProductId: null, itemActions: () => null,
    } as unknown as FloatingWidgetController;
    const { container } = render(<WidgetDays widget={widget} />);
    const hotels = Array.from(container.querySelectorAll('[data-product-id="h1"], [data-product-id="h2"]'))
      .map((card) => card.getAttribute('data-product-id'));
    expect(hotels).toEqual(['h1', 'h1', 'h2', 'h2', 'h2']);
    expect(container.textContent).toContain('(Đêm 3–4)');
  });
});
