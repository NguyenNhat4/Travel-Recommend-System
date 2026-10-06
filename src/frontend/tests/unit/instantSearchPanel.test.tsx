// @vitest-environment jsdom
import React, { useState } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from '../../../shared/mocks/search/suggestSearch.200-default.json';

const api = vi.hoisted(() => ({ fetchSuggestions: vi.fn() }));
vi.mock('../../src/services/suggest', () => ({ fetchSuggestions: api.fetchSuggestions, SUGGESTION_LIMIT: 8 }));

import { InstantSearchPanel } from '../../src/features/search/instant/InstantSearchPanel';
import { POPULAR_KEYWORDS, RECENT_SEARCHES_KEY } from '../../src/features/search/instant/recentSearches';
import { clearSuggestionCache, DEBOUNCE_MS } from '../../src/features/search/instant/useInstantSearch';
import { useInstantSearchBox } from '../../src/features/search/instant/useInstantSearchBox';

const onSearch = vi.fn();
const onOpenProduct = vi.fn();

function Harness() {
  const [value, setValue] = useState('');
  const { containerRef, ...instant } = useInstantSearchBox({ value, onSearch, onOpenProduct });
  return (
    <>
      <div ref={containerRef}>
        <form role="search" onSubmit={(e) => { e.preventDefault(); instant.search(value); }}>
          <input aria-label="Ô tìm kiếm" value={value} onChange={(e) => { setValue(e.target.value); instant.onType(); }} {...instant.inputProps} />
        </form>
        {instant.open && <InstantSearchPanel {...instant.panel} />}
      </div>
      <button type="button">ngoài</button>
    </>
  );
}

const input = () => screen.getByLabelText('Ô tìm kiếm') as HTMLInputElement;
const type = (value: string) => fireEvent.change(input(), { target: { value } });
const labels = () => screen.queryAllByRole('option').map((o) => o.textContent);
const settle = (ms = DEBOUNCE_MS + 60) => act(async () => { await new Promise((r) => setTimeout(r, ms)); });

describe('instant search box', () => {
  beforeEach(() => {
    clearSuggestionCache();
    window.localStorage.clear();
    api.fetchSuggestions.mockReset();
    api.fetchSuggestions.mockResolvedValue(fixture.suggestions);
    onSearch.mockReset();
    onOpenProduct.mockReset();
  });
  afterEach(cleanup);

  it('empty box on focus: popular keywords, recent searches when there are any, and no request', async () => {
    render(<Harness />);
    expect(screen.queryByRole('listbox')).toBeNull();
    fireEvent.focus(input());
    expect(input().getAttribute('aria-expanded')).toBe('true');
    expect(screen.queryByText('Tìm kiếm gần đây')).toBeNull();
    expect(within(screen.getByRole('group', { name: 'Từ khoá phổ biến' })).getAllByRole('option').map((o) => o.textContent)).toEqual([...POPULAR_KEYWORDS]);

    type('H');                                   // một ký tự: vẫn là hai nhóm này
    type('   ');
    await settle();
    expect(labels()).toEqual([...POPULAR_KEYWORDS]);
    expect(screen.queryByText(/Xem tất cả kết quả/)).toBeNull();
    expect(api.fetchSuggestions).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('option', { name: POPULAR_KEYWORDS[1] }));
    expect(onSearch).toHaveBeenCalledWith(POPULAR_KEYWORDS[1]);
    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('typing shows grouped suggestions with an icon, the matching part in bold, the kind and a see-all button', async () => {
    render(<Harness />);
    type('Ha');
    expect(screen.getByTestId('instant-search-loading')).toBeTruthy();
    await waitFor(() => expect(screen.getAllByRole('option')).toHaveLength(fixture.suggestions.length));
    expect(api.fetchSuggestions).toHaveBeenCalledTimes(1);
    expect(api.fetchSuggestions.mock.calls[0][0]).toBe('ha');

    const options = screen.getAllByRole('option');
    expect(options.every((o) => o.querySelector('svg'))).toBe(true);
    expect(options[0].textContent).toBe('Hà NộiĐịa điểm');
    expect(Array.from(options[0].querySelectorAll('strong')).map((b) => b.textContent)).toEqual(['Hà']);
    expect(options[3].textContent).toBe('Vinpearl Resort & Spa Hạ LongKhách sạn · Hạ Long');
    expect(Array.from(options[3].querySelectorAll('strong')).map((b) => b.textContent)).toEqual(['Hạ']);
    expect(options[6].textContent).toContain('Sân golf · Hải Phòng');
    expect(options[7].textContent).toContain('Combo · Hà Nội');

    fireEvent.click(screen.getByRole('button', { name: 'Xem tất cả kết quả cho “Ha”' }));
    expect(onSearch).toHaveBeenCalledWith('Ha');
  });

  it('a search is remembered: newest first, shown when the box is empty, removable', async () => {
    render(<Harness />);
    type('Ha');
    fireEvent.submit(screen.getByRole('search'));
    type('Phú Quốc');
    fireEvent.submit(screen.getByRole('search'));
    expect(onSearch.mock.calls.map((c) => c[0])).toEqual(['Ha', 'Phú Quốc']);
    expect(JSON.parse(window.localStorage.getItem(RECENT_SEARCHES_KEY) ?? '[]')).toEqual(['Phú Quốc', 'Ha']);

    type('');
    const recent = screen.getByRole('group', { name: 'Tìm kiếm gần đây' });
    expect(within(recent).getAllByRole('option').map((o) => o.textContent)).toEqual(['Phú Quốc', 'Ha']);
    fireEvent.click(within(recent).getByRole('button', { name: 'Xóa' }));
    expect(screen.queryByText('Tìm kiếm gần đây')).toBeNull();
    expect(window.localStorage.getItem(RECENT_SEARCHES_KEY)).toBeNull();
    expect(labels()).toEqual([...POPULAR_KEYWORDS]);
  });

  it('keyboard: arrows move, Enter opens the highlighted row, Escape closes', async () => {
    render(<Harness />);
    type('Ha');
    await waitFor(() => expect(screen.getAllByRole('option')).toHaveLength(fixture.suggestions.length));

    fireEvent.keyDown(input(), { key: 'ArrowDown' });
    expect(screen.getAllByRole('option')[0].getAttribute('aria-selected')).toBe('true');
    expect(input().getAttribute('aria-activedescendant')).toBe(screen.getAllByRole('option')[0].id);
    fireEvent.keyDown(input(), { key: 'ArrowDown' });
    fireEvent.keyDown(input(), { key: 'ArrowDown' });
    fireEvent.keyDown(input(), { key: 'Enter' });
    expect(onOpenProduct).toHaveBeenCalledWith('hl-h-12');             // dòng thứ ba là một khách sạn
    expect(onSearch).not.toHaveBeenCalled();
    expect(window.localStorage.getItem(RECENT_SEARCHES_KEY)).toBeNull(); // mở sản phẩm không tính là một lượt tìm

    fireEvent.focus(input());
    fireEvent.keyDown(input(), { key: 'ArrowDown' });
    fireEvent.keyDown(input(), { key: 'Enter' });
    expect(onSearch).toHaveBeenCalledWith('Hà Nội');                   // điểm đến: tìm theo tên điểm đến

    fireEvent.focus(input());
    fireEvent.keyDown(input(), { key: 'ArrowDown' });
    fireEvent.keyDown(input(), { key: 'ArrowUp' });
    expect(screen.queryByRole('option', { selected: true })).toBeNull();
    fireEvent.keyDown(input(), { key: 'Escape' });
    expect(screen.queryByRole('listbox')).toBeNull();
    expect(input().getAttribute('aria-expanded')).toBe('false');
  });

  it('closes on a click outside, not on a click inside', async () => {
    render(<Harness />);
    fireEvent.focus(input());
    fireEvent.mouseDown(screen.getByRole('listbox'));
    expect(screen.getByRole('listbox')).toBeTruthy();
    fireEvent.mouseDown(screen.getByRole('button', { name: 'ngoài' }));
    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('no match and a failed request both keep the see-all button', async () => {
    api.fetchSuggestions.mockResolvedValueOnce([]);
    render(<Harness />);
    type('zz');
    expect(await screen.findByText(/Không có gợi ý trùng với “zz”/)).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Xem tất cả kết quả cho “zz”' })).toBeTruthy();

    api.fetchSuggestions.mockRejectedValueOnce(new Error('500'));
    type('yy');
    expect(await screen.findByText(/Chưa tải được gợi ý/)).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Xem tất cả kết quả cho “yy”' })).toBeTruthy();
    expect(screen.queryAllByRole('option')).toHaveLength(0);
  });
});
