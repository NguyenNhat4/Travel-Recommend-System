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
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2026-09-15T10:00:00+07:00'));
    clearSectionCache();
    travel.navigate.mockReset();
    api.listDestinations.mockReset();
    api.listDestinations.mockResolvedValue([
      { destination: 'Nha Trang', productCount: 120 }, { destination: 'Đà Nẵng', productCount: 75 },
    ]);
    window.localStorage.clear();
  });
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it('hotels: defaults to tomorrow + 1 night, 1 room, 2 adults and searches hotels with trip context', () => {
    renderSheet('hotels');
    expect(screen.getByText('1 phòng, 2 người lớn')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));

    const url = lastHref();
    expect(url.pathname).toBe('/hotels');
    expect(url.searchParams.get('type')).toBeNull();
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

  it('experiences: the golf tab searches /experiences with type=golf; combos go to /combos', () => {
    const config = VERTICALS.experiences;
    const { unmount } = render(<LandingSearchSheet config={config} tab={resolveTab(config, 'golf')} />);
    fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));
    expect(lastHref().pathname).toBe('/experiences');
    expect(lastHref().searchParams.get('type')).toBe('golf');
    expect(lastHref().searchParams.get('q')).toBe('sân golf');
    unmount();

    renderSheet('combos');
    fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));
    expect(lastHref().pathname).toBe('/combos');
    expect(lastHref().searchParams.get('type')).toBeNull();
  });

  it('prefills dates, party, rooms and free text from the search in the URL', () => {
    renderSheet('hotels', {
      initialText: 'resort yên tĩnh',
      initialSearch: { origin: '', trip: { checkIn: '2026-10-20', checkOut: '2026-10-23', adults: 3, children: 1, rooms: 2 } },
    });
    expect((screen.getByRole('combobox') as HTMLInputElement).value).toBe('resort yên tĩnh');
    expect(screen.getByText('2 phòng, 3 người lớn, 1 trẻ em')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));
    const url = lastHref();
    expect(url.searchParams.get('q')).toBe('resort yên tĩnh');
    expect(url.searchParams.get('checkIn')).toBe('2026-10-20');
    expect(url.searchParams.get('checkOut')).toBe('2026-10-23');
    expect(url.searchParams.get('rooms')).toBe('2');
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

  it('flights: with a page handler, Tìm hands the values over instead of navigating', async () => {
    const onFlightSearch = vi.fn();
    renderSheet('flights', { onFlightSearch });
    fireEvent.change(screen.getByLabelText('Điểm đi'), { target: { value: ' Hà Nội ' } });
    fireEvent.focus(screen.getByRole('combobox', { name: /Điểm đến/ }));
    fireEvent.click(await screen.findByRole('option', { name: 'Đà Nẵng' }));
    fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));
    expect(travel.navigate).not.toHaveBeenCalled();
    expect(onFlightSearch).toHaveBeenCalledWith({
      origin: ' Hà Nội ', location: 'Đà Nẵng', destination: 'Đà Nẵng',
      trip: { checkIn: tomorrow(), checkOut: undefined, adults: 2, children: 0 },
    });
  });

  it('flights: hands over incomplete input too, so the page can say what is missing', () => {
    const onFlightSearch = vi.fn();
    renderSheet('flights', { onFlightSearch });
    fireEvent.change(screen.getByRole('combobox', { name: /Điểm đến/ }), { target: { value: 'xứ sở thần tiên' } });
    fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));
    expect(travel.navigate).not.toHaveBeenCalled();
    expect(onFlightSearch).toHaveBeenCalledWith(expect.objectContaining({ origin: '', location: 'xứ sở thần tiên', destination: null }));
  });

  it('flights: shows the search in the URL (origin, dates, round trip, party) so it can be edited in place', () => {
    const onFlightSearch = vi.fn();
    renderSheet('flights', {
      onFlightSearch,
      initialDestination: 'Đà Nẵng',
      initialSearch: { origin: 'Hà Nội', trip: { checkIn: '2026-10-20', checkOut: '2026-10-25', adults: 3, children: 1 } },
    });
    expect((screen.getByLabelText('Điểm đi') as HTMLInputElement).value).toBe('Hà Nội');
    expect((screen.getByRole('combobox', { name: /Điểm đến/ }) as HTMLInputElement).value).toBe('Đà Nẵng');
    expect(screen.getByText('3 người lớn, 1 trẻ em')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));
    expect(onFlightSearch).toHaveBeenCalledWith({
      origin: 'Hà Nội', location: 'Đà Nẵng', destination: 'Đà Nẵng',
      trip: { checkIn: '2026-10-20', checkOut: '2026-10-25', adults: 3, children: 1 },
    });
  });

  describe('flights: origin and history', () => {
    const originBox = () => screen.getByRole('combobox', { name: /Điểm đi/ }) as HTMLInputElement;
    const destinationBox = () => screen.getByRole('combobox', { name: /Điểm đến/ }) as HTMLInputElement;

    it('the origin field suggests places as you type and moves on to the destination after a pick', async () => {
      renderSheet('flights');
      fireEvent.focus(originBox());
      const list = await screen.findByRole('listbox', { name: 'Gợi ý điểm đi' });
      expect(within(list).getAllByRole('option').map((o) => o.textContent)).toEqual(['Nha Trang', 'Đà Nẵng']);

      fireEvent.change(originBox(), { target: { value: 'da n' } });
      expect(within(screen.getByRole('listbox', { name: 'Gợi ý điểm đi' })).getAllByRole('option').map((o) => o.textContent)).toEqual(['Đà Nẵng']);

      fireEvent.click(screen.getByRole('option', { name: 'Đà Nẵng' }));
      expect(originBox().value).toBe('Đà Nẵng');
      expect(document.activeElement).toBe(destinationBox());
      expect(screen.getByRole('listbox', { name: 'Gợi ý điểm đến' })).toBeTruthy();
      // Điểm đi đã chọn không được gợi ý lại làm điểm đến.
      expect(screen.queryByRole('option', { name: 'Đà Nẵng' })).toBeNull();
    });

    it('arrow keys and Enter pick an origin suggestion; a free-typed origin still goes through', async () => {
      const onFlightSearch = vi.fn();
      renderSheet('flights', { onFlightSearch });
      fireEvent.focus(originBox());
      await screen.findByRole('option', { name: 'Nha Trang' });
      fireEvent.keyDown(originBox(), { key: 'ArrowDown' });
      fireEvent.keyDown(originBox(), { key: 'ArrowDown' });
      fireEvent.keyDown(originBox(), { key: 'Enter' });
      expect(originBox().value).toBe('Đà Nẵng');

      fireEvent.change(originBox(), { target: { value: 'Cần Thơ' } });
      fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));
      expect(onFlightSearch).toHaveBeenCalledWith(expect.objectContaining({ origin: 'Cần Thơ' }));
    });

    it('a finished search is remembered for both fields, newest first, and offered again when the field is empty', async () => {
      const { unmount } = renderSheet('flights', { onFlightSearch: vi.fn() });
      fireEvent.change(originBox(), { target: { value: 'nha trang' } });
      fireEvent.focus(destinationBox());
      fireEvent.click(await screen.findByRole('option', { name: 'Đà Nẵng' }));
      fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));
      // Chuẩn hóa về nhãn của /destinations.
      expect(JSON.parse(window.localStorage.getItem('vota_flight_recent_origins')!)).toEqual(['Nha Trang']);
      expect(JSON.parse(window.localStorage.getItem('vota_flight_recent_destinations')!)).toEqual(['Đà Nẵng']);
      unmount();

      renderSheet('flights', { onFlightSearch: vi.fn() });
      fireEvent.focus(originBox());
      const recent = await screen.findByRole('group', { name: 'Tìm gần đây' });
      expect(within(recent).getAllByRole('option').map((o) => o.textContent)).toEqual(['Nha Trang']);
      // Mục đã có ở "Tìm gần đây" không lặp ở nhóm phổ biến.
      expect(screen.getAllByRole('option', { name: 'Nha Trang' })).toHaveLength(1);

      fireEvent.click(within(recent).getByRole('option', { name: 'Nha Trang' }));
      expect(originBox().value).toBe('Nha Trang');
      expect(within(await screen.findByRole('group', { name: 'Tìm gần đây' })).getAllByRole('option').map((o) => o.textContent)).toEqual(['Đà Nẵng']);
    });

    it('history is hidden while typing, capped at five, and can be cleared', async () => {
      window.localStorage.setItem('vota_flight_recent_origins', JSON.stringify(['Đà Nẵng', 'Nha Trang']));
      renderSheet('flights');
      fireEvent.focus(originBox());
      expect(await screen.findByRole('group', { name: 'Tìm gần đây' })).toBeTruthy();

      fireEvent.change(originBox(), { target: { value: 'nha' } });
      expect(screen.queryByRole('group', { name: 'Tìm gần đây' })).toBeNull();

      fireEvent.change(originBox(), { target: { value: '' } });
      fireEvent.click(within(screen.getByRole('group', { name: 'Tìm gần đây' })).getByRole('button', { name: 'Xóa' }));
      expect(screen.queryByRole('group', { name: 'Tìm gần đây' })).toBeNull();
      expect(window.localStorage.getItem('vota_flight_recent_origins')).toBeNull();
    });

    it('history entries that are no longer in /destinations are not offered', async () => {
      window.localStorage.setItem('vota_flight_recent_destinations', JSON.stringify(['Atlantis', 'Nha Trang']));
      renderSheet('flights');
      fireEvent.focus(destinationBox());
      const recent = await screen.findByRole('group', { name: 'Tìm gần đây' });
      expect(within(recent).getAllByRole('option').map((o) => o.textContent)).toEqual(['Nha Trang']);
    });

    it('other categories keep no history', async () => {
      renderSheet('hotels');
      fireEvent.focus(screen.getByRole('combobox'));
      await screen.findByRole('option', { name: 'Nha Trang' });
      fireEvent.click(screen.getByRole('option', { name: 'Nha Trang' }));
      fireEvent.click(screen.getByRole('button', { name: 'Tìm kiếm' }));
      expect(window.localStorage.length).toBe(0);
    });
  });

  it('closes an open panel on Escape', () => {
    renderSheet('hotels');
    fireEvent.click(screen.getByRole('button', { name: /Số lượng/ }));
    expect(screen.getByRole('dialog', { name: 'Số lượng khách' })).toBeTruthy();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog', { name: 'Số lượng khách' })).toBeNull();
  });
});
