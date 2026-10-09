// @vitest-environment jsdom
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { stayCardKey, stayOptionCards } from '../../src/features/itinerary/widget/widgetPlan';
import { WidgetStayOptions } from '../../src/features/itinerary/widget/WidgetStayOptions';
import type { components } from '../../src/types/api.gen';

const hotel = (productId: string, name: string, unitPrice: number) => ({
  productId, name, taxonomy: 'hotel', destination: 'TP. Hồ Chí Minh', unitPrice, priceUnit: 'PER_NIGHT',
  currency: 'VND', available: true, attributes: { starRating: 4 },
}) as components['schemas']['ProductSummary'];

const itinerary = (stay: components['schemas']['ProductSummary'], estimatedTotal: number) => ({
  stay: { product: stay, nights: 2, fromNight: 1 }, stays: [{ product: stay, nights: 2, fromNight: 1 }],
  days: [{ day: 1, slots: [] }], estimatedTotal, currency: 'VND', budgetStatus: 'NO_BUDGET',
}) as unknown as components['schemas']['ItineraryPlan'];

const response = {
  status: 'COMPLETED', conversationId: 'c1', warnings: [],
  intent: { destination: 'TP. Hồ Chí Minh', days: 1, party: { type: 'COUPLE', adults: 2, children: 0 } },
  itinerary: itinerary(hotel('h-close', 'Khách sạn gần', 3_000_000), 6_400_000),
  stayOptions: {
    distanceKm: 33.1,
    options: [{ index: 1, kmDelta: 9.2, moneyDelta: -5_000_000, overBudget: null,
      itinerary: itinerary(hotel('h-far', 'Khách sạn rẻ', 500_000), 1_400_000) }],
  },
} as unknown as components['schemas']['ItineraryCompleted'];

describe('stayOptionCards', () => {
  it('puts the current plan first and gives every option its own full plan for the preview', () => {
    const [current, option] = stayOptionCards(response)!;
    expect(current).toMatchObject({ index: null, distanceKm: 33.1, kmDelta: 0, moneyDelta: 0 });
    expect(current.hotels.map((h) => h.id)).toEqual(['h-close']);
    expect(option).toMatchObject({ index: 1, distanceKm: 42.3, kmDelta: 9.2, moneyDelta: -5_000_000, overBudget: null });
    expect(option.plan.stay?.productId).toBe('h-far');
    expect(option.plan.totalEstimatedPrice).toBe(1_400_000);
  });

  it('is undefined when the response has no other option', () => {
    expect(stayOptionCards({ ...response, stayOptions: undefined })).toBeUndefined();
  });
});

describe('WidgetStayOptions', () => {
  afterEach(cleanup);
  const cards = stayOptionCards(response)!;
  const row = (props: Partial<React.ComponentProps<typeof WidgetStayOptions>> = {}) => (
    <WidgetStayOptions cards={cards} interactive selectingKey={null} previewKey={null}
      onPreview={vi.fn()} onSelect={vi.fn()} {...props} />
  );

  it('shows the trade-off of each option', () => {
    render(row());
    expect(screen.getByText('Đang chọn')).toBeTruthy();
    expect(screen.getByText(/Đi lại ≈33,1 km/)).toBeTruthy();
    expect(screen.getByText('−5.000.000 ₫')).toBeTruthy();
    expect(screen.getByText('≈+9,2 km')).toBeTruthy();
  });

  it('notes that the km is an estimate, including the airport legs only when the plan has a flight', () => {
    render(row());
    expect(screen.getByText('Số km là ước tính quãng đường di chuyển cả hành trình.')).toBeTruthy();
    cleanup();
    const flight = {
      product: { productId: 'vn-rt', name: 'VN1823', taxonomy: 'flight', destination: 'Phú Quốc', unitPrice: 1_730_362,
        priceUnit: 'PER_PERSON', currency: 'VND', available: true,
        attributes: { latitude: 10.169783, longitude: 103.99353, destinationAirport: 'PQC' } },
      direction: 'ROUND_TRIP', date: '2026-10-20', returnDate: '2026-10-22', passengers: 2, source: 'SEARCH',
    };
    const withFlight = { ...response, itinerary: { ...response.itinerary, flights: [flight] } } as unknown as
      components['schemas']['ItineraryCompleted'];
    render(row({ cards: stayOptionCards(withFlight)! }));
    expect(screen.getByText('Số km là ước tính quãng đường di chuyển cả hành trình, gồm cả đường sân bay.')).toBeTruthy();
  });

  it('only previews on a tap of the card; the switch button is what changes the hotel', () => {
    const onPreview = vi.fn();
    const onSelect = vi.fn();
    render(row({ onPreview, onSelect }));
    fireEvent.click(screen.getByRole('button', { name: /Xem trước phương án 1/ }));
    expect(onPreview).toHaveBeenCalledWith(cards[1]);
    expect(onSelect).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: /Đổi sang phương án 1/ }));
    expect(onSelect).toHaveBeenCalledWith(cards[1]);
  });

  it('lifts the previewed card without making it the chosen one', () => {
    render(row({ previewKey: stayCardKey(cards[1]) }));
    expect(screen.getByText('Đang xem trước')).toBeTruthy();
    expect(screen.getByText('Đang chọn')).toBeTruthy();
    expect(screen.getByRole('button', { name: /Xem trước phương án 1/ }).getAttribute('aria-pressed')).toBe('true');
  });

  it('marks the switched card as chosen right away and locks the rest while saving', () => {
    const onSelect = vi.fn();
    render(row({ selectingKey: stayCardKey(cards[1]), onSelect }));
    expect(screen.getByRole('button', { name: 'Đang chọn: Khách sạn rẻ' })).toBeTruthy();
    expect(screen.getByText('Đang lưu…')).toBeTruthy();
    const previous = screen.getByRole('button', { name: /Khách sạn gần/ }) as HTMLButtonElement;
    expect(previous.disabled).toBe(true);
  });

  it('locks the row on an old answer', () => {
    render(row({ interactive: false }));
    expect((screen.getByRole('button', { name: /Đổi sang phương án 1/ }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole('button', { name: /Xem trước phương án 1/ }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('keeps the card order when the server puts the chosen plan first', () => {
    const swapped = {
      ...response,
      itinerary: response.stayOptions!.options[0].itinerary,
      stayOptions: { distanceKm: 42.3, options: [{ index: 1, kmDelta: -9.2, moneyDelta: 5_000_000, overBudget: null,
        itinerary: response.itinerary }] },
    } as typeof response;
    const names = () => screen.getAllByRole('button', { name: /^(Đang chọn|Xem trước)/ })
      .map((button) => button.getAttribute('aria-label'));
    const { rerender } = render(row());
    expect(names()).toEqual(['Đang chọn: Khách sạn gần', 'Xem trước phương án 1: Khách sạn rẻ']);
    rerender(row({ cards: stayOptionCards(swapped)! }));
    expect(names()).toEqual(['Xem trước phương án 1: Khách sạn gần', 'Đang chọn: Khách sạn rẻ']);
  });
});

describe('two-hotel options that split the nights differently', () => {
  afterEach(cleanup);
  const a = hotel('h-a', 'Khách sạn A', 500_000);
  const b = hotel('h-b', 'Khách sạn B', 700_000);
  const split = (aNights: number, total: number) => ({
    stay: { product: a, nights: aNights, fromNight: 1 },
    stays: [{ product: a, nights: aNights, fromNight: 1 }, { product: b, nights: 4 - aNights, fromNight: aNights + 1 }],
    days: [{ day: 1, slots: [] }], estimatedTotal: total, currency: 'VND', budgetStatus: 'NO_BUDGET',
  }) as unknown as components['schemas']['ItineraryPlan'];
  const twoSplits = {
    ...response,
    intent: { ...response.intent, days: 5 },
    itinerary: itinerary(hotel('h-close', 'Khách sạn gần', 3_000_000), 6_400_000),
    stayOptions: { distanceKm: 30, options: [
      { index: 1, kmDelta: 3, moneyDelta: -1_000_000, overBudget: null, itinerary: split(2, 5_400_000) },
      { index: 2, kmDelta: 5, moneyDelta: -1_200_000, overBudget: null, itinerary: split(3, 5_200_000) },
    ] },
  } as unknown as components['schemas']['ItineraryCompleted'];

  it('gives each its own key and shows the nights of every hotel', () => {
    const cards = stayOptionCards(twoSplits)!;
    expect(new Set(cards.map(stayCardKey)).size).toBe(3);
    render(<WidgetStayOptions cards={cards} interactive selectingKey={null} previewKey={null} onPreview={vi.fn()} onSelect={vi.fn()} />);
    expect(screen.getByText('Đêm 1–2 · Khách sạn A')).toBeTruthy();
    expect(screen.getByText('Đêm 1–3 · Khách sạn A')).toBeTruthy();
    expect(screen.getByText('Đêm 4 · Khách sạn B')).toBeTruthy();
  });
});
