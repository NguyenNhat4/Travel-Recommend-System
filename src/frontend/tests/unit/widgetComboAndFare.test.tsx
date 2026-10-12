// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { WidgetComboCard, comboBadge } from '../../src/features/itinerary/widget/WidgetComboCard';
import { FlightCard } from '../../src/features/flights/results/FlightCard';
import type { Product } from '../../src/types/travel';
import type { FlightOption } from '../../src/features/flights/results/flightModel';

afterEach(cleanup);
const combo = { id: 'c', name: 'Gói kết hợp', taxonomy: 'combo', destination: 'Hà Nội', unitPrice: 1000000, imageUrl: '/combo.jpg', attributes: {} } as Product;
it('only uses supported evidence for the special combo badge and preserves booking actions', () => {
  expect(comboBadge(combo, [combo])).toBe('Combo trọn gói');
  expect(comboBadge({ ...combo, attributes: { originalPrice: 2000000 } }, [combo])).toBe('Giảm 50%');
  const reviewed = { ...combo, aggregateRating: { score: 4.7, count: 100 } };
  expect(comboBadge(reviewed, [reviewed])).toBe('Được yêu thích nhất');
  const onBook = vi.fn();
  render(<WidgetComboCard product={reviewed} peers={[reviewed]} onOpen={vi.fn()} onBook={onBook} />);
  fireEvent.click(screen.getByRole('button', { name: 'Đặt ngay' }));
  expect(onBook).toHaveBeenCalledOnce();
});

it('defaults to the cheapest fare despite backend order and honors a specific fare id', () => {
  const business = { productId: 'b', name: 'Thương gia', price: 2000000, summary: {}, carryOnKg: null, checkedKg: null };
  const economy = { ...business, productId: 'e', name: 'Giá rẻ nhất', price: 500000 };
  const option = { key: 'flight', fares: [business, economy], from: 'HAN', to: 'DAD', date: '2999-10-10', airline: 'Hãng bay', depClock: '08:00', arrClock: '09:30', durationMinutes: 90 } as unknown as FlightOption;
  const pick = vi.fn();
  const props = { option, chosen: null, expanded: false, onPick: pick, onClear: vi.fn(), onToggleExpanded: vi.fn() };
  const { unmount } = render(<FlightCard {...props} />);
  fireEvent.click(screen.getByRole('button', { name: /Chọn/ }));
  expect(pick.mock.calls[0][1].productId).toBe('e');
  unmount(); pick.mockClear();
  render(<FlightCard {...props} preferredFareId="b" />);
  fireEvent.click(screen.getByRole('button', { name: /Chọn/ }));
  expect(pick.mock.calls[0][1].productId).toBe('b');
});
