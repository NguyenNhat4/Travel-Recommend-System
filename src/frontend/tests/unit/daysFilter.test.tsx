// @vitest-environment jsdom
import React, { useState } from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { DaysFilter } from '../../src/features/bookings/DaysFilter';
import type { DaysFilter as DaysValue } from '../../src/features/bookings/historyModel';

const onChange = vi.fn();
function Harness({ initial = 0 as DaysValue }) {
  const [value, setValue] = useState<DaysValue>(initial);
  return <><DaysFilter value={value} onChange={(v) => { onChange(v); setValue(v); }} /><button type="button">bên ngoài</button></>;
}
const trigger = () => screen.getByRole('button', { name: /^Ngày đặt/ });

describe('DaysFilter — bộ lọc Ngày đặt', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });

  it('đóng thì chỉ hiện giá trị đang chọn; mở ra có đủ năm lựa chọn, dòng đang chọn được đánh dấu', () => {
    render(<Harness initial={7} />);
    expect(trigger().textContent).toBe('7 ngày qua');
    expect(trigger().getAttribute('aria-expanded')).toBe('false');
    expect(screen.queryByRole('listbox')).toBeNull();
    fireEvent.click(trigger());
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(['Tất cả', '1 ngày qua', '7 ngày qua', '30 ngày qua', '60 ngày qua']);
    expect(screen.getByRole('option', { name: '7 ngày qua' }).getAttribute('aria-selected')).toBe('true');
    expect(screen.getByRole('option', { name: 'Tất cả' }).getAttribute('aria-selected')).toBe('false');
    expect(trigger().getAttribute('aria-expanded')).toBe('true');
  });

  it('chọn một dòng gọi onChange với đúng giá trị, đóng danh sách và cập nhật nút', () => {
    render(<Harness />);
    fireEvent.click(trigger());
    fireEvent.click(screen.getByRole('option', { name: '30 ngày qua' }));
    expect(onChange).toHaveBeenCalledWith(30);
    expect(screen.queryByRole('listbox')).toBeNull();
    expect(trigger().textContent).toBe('30 ngày qua');
  });

  it('bàn phím: mũi tên mở, mũi tên đổi dòng, Enter chọn, Esc đóng không đổi giá trị và trả focus về nút', () => {
    render(<Harness />);
    trigger().focus();
    fireEvent.keyDown(trigger(), { key: 'ArrowDown' });
    const list = screen.getByRole('listbox');
    expect(document.activeElement).toBe(list);
    fireEvent.keyDown(list, { key: 'ArrowDown' });
    fireEvent.keyDown(list, { key: 'ArrowDown' });
    expect(list.getAttribute('aria-activedescendant')).toBe(screen.getByRole('option', { name: '7 ngày qua' }).id);
    fireEvent.keyDown(list, { key: 'End' });
    expect(list.getAttribute('aria-activedescendant')).toBe(screen.getByRole('option', { name: '60 ngày qua' }).id);
    fireEvent.keyDown(list, { key: 'Home' });
    fireEvent.keyDown(list, { key: 'Escape' });
    expect(screen.queryByRole('listbox')).toBeNull();
    expect(document.activeElement).toBe(trigger());
    expect(onChange).not.toHaveBeenCalled();

    fireEvent.keyDown(trigger(), { key: 'ArrowDown' });
    fireEvent.keyDown(screen.getByRole('listbox'), { key: 'ArrowDown' });
    fireEvent.keyDown(screen.getByRole('listbox'), { key: 'Enter' });
    expect(onChange).toHaveBeenCalledWith(1);
  });

  it('bấm ra ngoài thì đóng và không đổi giá trị', () => {
    render(<Harness />);
    fireEvent.click(trigger());
    fireEvent.pointerDown(screen.getByRole('button', { name: 'bên ngoài' }));
    expect(screen.queryByRole('listbox')).toBeNull();
    expect(onChange).not.toHaveBeenCalled();
  });

  it('bấm nút lần nữa thì đóng', () => {
    render(<Harness />);
    fireEvent.click(trigger());
    fireEvent.click(trigger());
    expect(screen.queryByRole('listbox')).toBeNull();
  });
});
