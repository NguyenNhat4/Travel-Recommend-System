// @vitest-environment jsdom
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { WidgetBudget, tripLength } from '../../src/features/itinerary/widget/WidgetBudget';
import { WidgetFlightCard } from '../../src/features/itinerary/widget/WidgetFlightCard';
import { flightDay, flightSegments, formatDuration } from '../../src/features/itinerary/widget/widgetFlight';
import { convertItineraryCompletedToGroundedPlan } from '../../src/features/itinerary/widget/widgetPlan';
import type { ItineraryFlightItem } from '../../src/types/travel';
import type { components } from '../../src/types/api.gen';

afterEach(cleanup);

const roundTrip: ItineraryFlightItem = {
  productId: 'vn-rt',
  product: {
    id: 'vn-rt', name: 'Vietnam Airlines VN1823', taxonomy: 'flight', destination: 'Phú Quốc', unitPrice: 1_730_362,
    currency: 'VND', imageUrl: '', description: '', available: true,
    attributes: {
      airline: 'Vietnam Airlines', flightNumber: 'VN1823', nonstop: true, tripType: 'roundTrip',
      originCity: 'Hồ Chí Minh', destinationCity: 'Phú Quốc', originAirport: 'SGN', destinationAirport: 'PQC',
      departureAt: '2026-10-20T08:00:00+07:00', arrivalAt: '2026-10-20T09:00:00+07:00',
      returnFlight: { flightNumber: 'VN1830', airline: 'Vietnam Airlines',
        departureAt: '2026-10-22T09:35:00+07:00', arrivalAt: '2026-10-22T10:45:00+07:00' },
    },
  } as unknown as ItineraryFlightItem['product'],
  direction: 'ROUND_TRIP',
  date: '2026-10-20',
  returnDate: '2026-10-22',
  passengers: 2,
};

describe('flight card model', () => {
  it('reads both legs of a round trip from the catalog attributes', () => {
    const [going, back] = flightSegments(roundTrip);
    expect(going).toMatchObject({
      label: 'Chiều đi', flightNumber: 'VN1823', durationMinutes: 60, nonstop: true,
      departure: { day: 'T3, 20 thg 10', time: '08:00', place: 'Hồ Chí Minh' },
      arrival: { time: '09:00', place: 'Phú Quốc' },
    });
    // Chiều về: không có cờ bay thẳng trong returnFlight thì không ghi bay thẳng.
    expect(back).toMatchObject({
      label: 'Chiều về', flightNumber: 'VN1830', durationMinutes: 70, nonstop: false,
      departure: { day: 'T5, 22 thg 10', time: '09:35', place: 'Phú Quốc' },
      arrival: { time: '10:45', place: 'Hồ Chí Minh' },
    });
  });

  it('leaves out what the catalog does not have', () => {
    const bare = { ...roundTrip, direction: 'OUTBOUND' as const,
      product: { ...roundTrip.product, attributes: { airline: 'VietJet Air' } } };
    const [segment] = flightSegments(bare);
    expect(segment.durationMinutes).toBeNull();
    expect(segment.departure.time).toBeNull();
    expect(segment.departure.day).toBe('T3, 20 thg 10');
    expect(flightDay('not a date')).toBeNull();
    expect(formatDuration(135)).toBe("2h15'");
  });
});

describe('WidgetFlightCard', () => {
  it('shows the legs, the price times the passengers and books on demand', () => {
    const onOpen = vi.fn();
    const onBookNow = vi.fn();
    render(<WidgetFlightCard flight={roundTrip} onOpen={onOpen} onBookNow={onBookNow} />);
    expect(screen.getByText('Đã chọn cho lịch')).toBeTruthy();
    expect(screen.getByText('Chiều đi')).toBeTruthy();
    expect(screen.getByText('Chiều về')).toBeTruthy();
    expect(screen.getByText("1h00'")).toBeTruthy();
    expect(screen.getByText('1.730.362 ₫')).toBeTruthy();
    expect(screen.getByText(/\/khách × 2 khách/)).toBeTruthy();
    // Giờ bay đã ở ô giờ lớn; dòng chiều chỉ ghi số hiệu, không lặp lại giờ.
    expect(screen.getByText('VN1823')).toBeTruthy();
    expect(screen.queryByText(/VN1823 · 08:00/)).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Đặt ngay' }));
    expect(onBookNow).toHaveBeenCalledOnce();
  });

  it('has no book button when the flight cannot be booked from this plan', () => {
    render(<WidgetFlightCard flight={roundTrip} onOpen={vi.fn()} />);
    expect(screen.queryByRole('button', { name: 'Đặt ngay' })).toBeNull();
  });
});

const hotel = {
  productId: 'h1', name: 'Venus Hotel', taxonomy: 'hotel', destination: 'Phú Quốc', unitPrice: 959_000,
  priceUnit: 'PER_NIGHT', currency: 'VND', available: true, attributes: {},
} as components['schemas']['ProductSummary'];

const completed = (itinerary: Record<string, unknown>, budget: number | null = null) => ({
  status: 'COMPLETED', conversationId: 'c1', warnings: [],
  intent: { destination: 'Phú Quốc', days: 3, party: { type: 'SOLO', adults: 1, children: 0 }, budget },
  itinerary: {
    stay: { product: hotel, nights: 2, fromNight: 1 }, stays: [{ product: hotel, nights: 2, fromNight: 1 }],
    days: [{ day: 1, slots: [] }], currency: 'VND', ...itinerary,
  },
}) as unknown as components['schemas']['ItineraryCompleted'];

describe('budget summary', () => {
  it('takes the split from costBreakdown and the budget from the intent', () => {
    const plan = convertItineraryCompletedToGroundedPlan(completed({
      estimatedTotal: 6_000_000, budgetStatus: 'WITHIN_BUDGET',
      costBreakdown: { flights: 3_460_724, stays: 1_918_000, activities: 621_276 },
    }, 8_000_000));
    expect(plan.budgetSummary).toEqual({ total: 6_000_000, flights: 3_460_724, stays: 1_918_000, activities: 621_276,
      budget: 8_000_000, status: 'WITHIN_BUDGET' });
  });

  it('is absent when the total is unknown', () => {
    const plan = convertItineraryCompletedToGroundedPlan(completed({ estimatedTotal: null, budgetStatus: 'UNKNOWN' }));
    expect(plan.budgetSummary).toBeNull();
  });

  it('renders the three groups, the bar and the budget status, without a food estimate', () => {
    const { container } = render(<WidgetBudget days={3} summary={{
      total: 5_378_000, flights: 3_460_000, stays: 1_918_000, activities: 0, budget: 5_000_000, status: 'OVER_BUDGET',
    }} />);
    expect(screen.getByText('Ngân sách dự tính')).toBeTruthy();
    expect(screen.getByText('3N2Đ')).toBeTruthy();
    expect(screen.getByText('5.378.000 ₫')).toBeTruthy();
    expect(screen.getByText('Vé máy bay')).toBeTruthy();
    expect(screen.queryByText('Vui chơi')).toBeNull();
    expect(screen.getByText('Vượt ngân sách')).toBeTruthy();
    expect(screen.queryByText(/Ăn uống/)).toBeNull();
    // Nhóm bằng 0 có dòng nhưng không có đoạn trên thanh.
    expect([...container.querySelectorAll('[data-budget-segment]')].map((node) => node.getAttribute('data-budget-segment')))
      .toEqual(['flights', 'stays']);
    expect(tripLength(1)).toBe('1 ngày');
  });
});
