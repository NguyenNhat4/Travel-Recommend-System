// @vitest-environment jsdom
import { useState } from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { GuestsPopover, type GuestsValue } from '../../src/features/catalog/landing/GuestsPopover';

afterEach(cleanup);

function Harness({ initial, showRooms }: { initial: GuestsValue; showRooms: boolean }) {
  const [value, setValue] = useState(initial);
  return <GuestsPopover value={value} onChange={setValue} showRooms={showRooms} />;
}

const group = (name: string) => screen.getByRole('group', { name });
const count = (name: string) => group(name).querySelector('span')!.textContent;
const plus = (name: string) => screen.getByRole('button', { name: `Tăng ${name.toLowerCase()}` });
const minus = (name: string) => screen.getByRole('button', { name: `Giảm ${name.toLowerCase()}` });

describe('GuestsPopover (FR-BKG-08)', () => {
  it('hotel: 1 room stops at 9 guests, 2 rooms allow 18', () => {
    render(<Harness initial={{ adults: 9, children: 0, rooms: 1 }} showRooms />);
    expect(plus('Người lớn')).toHaveProperty('disabled', true);
    expect(plus('Trẻ em')).toHaveProperty('disabled', true);
    expect(screen.getByText('Tối đa 9 khách mỗi phòng, 9 phòng mỗi lần đặt.')).toBeTruthy();

    fireEvent.click(plus('Phòng'));
    expect(count('Phòng')).toBe('2');
    expect(plus('Người lớn')).toHaveProperty('disabled', false);
    for (let i = 0; i < 9; i += 1) fireEvent.click(plus('Trẻ em'));
    expect(count('Trẻ em')).toBe('9');
    expect(plus('Trẻ em')).toHaveProperty('disabled', true);                       // 9 + 9 = 18
    expect(plus('Người lớn')).toHaveProperty('disabled', true);
  });

  it('hotel: rooms cannot drop while the party no longer fits, and stop at 9 rooms', () => {
    render(<Harness initial={{ adults: 10, children: 8, rooms: 2 }} showRooms />);
    expect(minus('Phòng')).toHaveProperty('disabled', true);                       // 18 khách không vừa 1 phòng
    cleanup();
    render(<Harness initial={{ adults: 9, children: 0, rooms: 9 }} showRooms />);
    expect(plus('Phòng')).toHaveProperty('disabled', true);
  });

  it('without rooms (tickets, golf, combo) the cap stays 9 guests per booking', () => {
    render(<Harness initial={{ adults: 8, children: 1, rooms: 3 }} showRooms={false} />);
    expect(plus('Người lớn')).toHaveProperty('disabled', true);
    expect(screen.getByText('Tối đa 9 khách mỗi lần đặt.')).toBeTruthy();
  });
});
