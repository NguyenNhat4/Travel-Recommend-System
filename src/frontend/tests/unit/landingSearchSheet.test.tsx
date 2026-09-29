// @vitest-environment jsdom
import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({ listDestinations: vi.fn() }));
const travel = vi.hoisted(() => ({ navigate: vi.fn() }));
vi.mock('../../src/services/destinations', () => api);
vi.mock('../../src/context/TravelContext', () => ({ useTravel: () => travel }));

import { LandingSearchSheet } from '../../src/features/catalog/landing/LandingSearchSheet';
import { VERTICALS, resolveTab } from '../../src/features/catalog/landing/verticals';
import { clearSectionCache } from '../../src/hooks/useLazySection';
import { addDaysIso, todayVN } from '../../src/features/search/tripContext';

const tomorrow = () => addDaysIso(todayVN(), 1);
const lastHref = () => new URL(travel.navigate.mock.calls.at(-1)![0], 'http://x');

function renderSheet(id: keyof typeof VERTICALS, extra: Partial<React.ComponentProps<typeof LandingSearchSheet>> = {}) {
  const config = VERTICALS[id];
  return render(<LandingSearchSheet config={config} tab={resolveTab(config, undefined)} {...extra} />);
}

describe('LandingSearchSheet', () => {
  beforeEach(() => {
    clearSectionCache();
    travel.navigate.mockReset();
    api.listDestinations.mockReset();
    api.listDestinations.mockResolvedValue([
      { destination: 'Nha Trang', productCount: 120 }, { destination: 'Đà Nẵng', productCount: 75 },
    ]);
  });
  afterEach(() => cleanup());

  it('hotels: defaults to tomorrow + 1 night, 1 room, 2 adults and searches hotels with trip context', () => {
    renderSheet('hotels');
    expect(screen.getByText('1 phòng, 2 người lớn')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));

    const url = lastHref();
    expect(url.pathname).toBe('/search');
    expect(url.searchParams.get('type')).toBe('hotel');
    expect(url.searchParams.get('q')).toBe('khách sạn');
    expect(url.searchParams.get('checkIn')).toBe(tomorrow());
    expect(url.searchParams.get('checkOut')).toBe(addDaysIso(tomorrow(), 1));
    expect(url.searchParams.get('rooms')).toBe('1');
    expect(url.searchParams.get('adults')).toBe('2');
    expect(url.searchParams.get('children')).toBeNull();
  });

  it('picking a suggested destination sends it as an exact filter', async () => {
    renderSheet('hotels');
    fireEvent.focus(screen.getByRole('combobox'));
    fireEvent.click(await screen.findByRole('option', { name: 'Nha Trang' }));
    expect((screen.getByRole('combobox') as HTMLInputElement).value).toBe('Nha Trang');

    fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));
    expect(lastHref().searchParams.get('destination')).toBe('Nha Trang');
  });

  it('typing free text without picking sends it as the query, typing an exact label still filters', async () => {
    renderSheet('hotels');
    const input = screen.getByRole('combobox');
    fireEvent.change(input, { target: { value: 'resort yên tĩnh' } });
    fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));
    expect(lastHref().searchParams.get('q')).toBe('resort yên tĩnh');
    expect(lastHref().searchParams.get('destination')).toBeNull();

    await waitFor(() => expect(api.listDestinations).toHaveBeenCalled());
    await screen.findByText('Điểm đến phổ biến').catch(() => undefined);
    await waitFor(() => expect(screen.queryByRole('listbox')).toBeNull());
    fireEvent.change(input, { target: { value: 'da nang' } });
    fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));
    expect(lastHref().searchParams.get('destination')).toBe('Đà Nẵng');
  });

  it('prefills the location from ?destination= and sends it', () => {
    renderSheet('experiences', { initialDestination: 'Phú Quốc' });
    expect((screen.getByRole('combobox') as HTMLInputElement).value).toBe('Phú Quốc');
    fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));
    expect(lastHref().searchParams.get('destination')).toBe('Phú Quốc');
    expect(lastHref().searchParams.get('q')).toBe('vé tham quan');
  });

  it('guests: never exceeds 9 people or more rooms than adults (FR-BKG-08)', () => {
    renderSheet('hotels');
    fireEvent.click(screen.getByRole('button', { name: /Số lượng/ }));
    const dialog = screen.getByRole('dialog', { name: 'Số lượng khách' });
    const plusAdult = within(dialog).getByRole('button', { name: 'Tăng người lớn' });
    for (let i = 0; i < 10; i++) fireEvent.click(plusAdult);
    expect(screen.getByText('9 người lớn', { exact: false })).toBeTruthy();
    expect((plusAdult as HTMLButtonElement).disabled).toBe(true);
    expect((within(dialog).getByRole('button', { name: 'Tăng trẻ em' }) as HTMLButtonElement).disabled).toBe(true);

    fireEvent.click(within(dialog).getByRole('button', { name: 'Tăng phòng' }));
    fireEvent.click(within(dialog).getByRole('button', { name: 'Tăng phòng' }));
    for (let i = 0; i < 9; i++) fireEvent.click(within(dialog).getByRole('button', { name: 'Giảm người lớn' }));
    // Còn 1 người lớn thì số phòng bị kéo xuống 1.
    expect(screen.getByText('1 phòng, 1 người lớn')).toBeTruthy();
  });

  it('dates: past days are disabled and a range needs the end after the start', () => {
    renderSheet('hotels');
    fireEvent.click(screen.getByRole('button', { name: /Ngày đi/ }));
    const dialog = screen.getByRole('dialog', { name: 'Chọn ngày' });
    const today = Number(todayVN().slice(8, 10));
    if (today > 1) {
      expect((within(dialog).getByRole('button', { name: new RegExp(`^${today - 1} tháng`) }) as HTMLButtonElement).disabled).toBe(true);
    }
    expect((within(dialog).getByRole('button', { name: 'Tháng trước' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('flights: has an origin field, one-way by default, and adds a return date only for round trips', () => {
    renderSheet('flights');
    fireEvent.change(screen.getByLabelText('Điểm đi'), { target: { value: 'Hà Nội' } });
    fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));
    let url = lastHref();
    expect(url.searchParams.get('type')).toBe('flight');
    expect(url.searchParams.get('q')).toBe('Hà Nội');
    expect(url.searchParams.get('checkOut')).toBeNull();
    expect(url.searchParams.get('rooms')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: /Ngày đi/ }));
    fireEvent.click(screen.getByRole('radio', { name: 'Khứ hồi' }));
    fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));
    url = lastHref();
    expect(url.searchParams.get('checkOut')).toBe(addDaysIso(tomorrow(), 2));
  });

  it('closes an open panel on Escape', () => {
    renderSheet('hotels');
    fireEvent.click(screen.getByRole('button', { name: /Số lượng/ }));
    expect(screen.getByRole('dialog', { name: 'Số lượng khách' })).toBeTruthy();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog', { name: 'Số lượng khách' })).toBeNull();
  });
});
