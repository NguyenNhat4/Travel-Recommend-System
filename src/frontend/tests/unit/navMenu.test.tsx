// @vitest-environment jsdom
import React, { useState } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({ listDestinations: vi.fn() }));
vi.mock('../../src/services/destinations', () => api);

import { AllServicesMenu, NavMenu } from '../../src/components/layout/nav/NavMenu';
import { VerticalChips } from '../../src/components/layout/nav/VerticalChips';
import { NAV_GROUPS, NAV_ITEMS } from '../../src/components/layout/nav/navConfig';
import { clearSectionCache } from '../../src/hooks/useLazySection';

const stay = NAV_GROUPS.find((g) => g.id === 'stay')!;
const experience = NAV_GROUPS.find((g) => g.id === 'experience')!;

function Harness({ group = stay, pathname = '/', query = '' }: { group?: typeof stay; pathname?: string; query?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <NavMenu group={group} active={false} tone="solid" open={open} onOpenChange={setOpen} pathname={pathname} params={new URLSearchParams(query)} />
      <button>outside</button>
    </div>
  );
}

describe('NavMenu', () => {
  beforeEach(() => {
    clearSectionCache();
    api.listDestinations.mockReset();
    api.listDestinations.mockResolvedValue([{ destination: 'Nha Trang', productCount: 120 }]);
    vi.stubGlobal('matchMedia', () => ({ matches: false }));
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('starts closed and does not fetch destinations', () => {
    render(<Harness />);
    const button = screen.getByRole('button', { name: /Lưu trú/ });
    expect(button.getAttribute('aria-expanded')).toBe('false');
    expect(screen.queryByRole('group', { name: 'Lưu trú' })).toBeNull();
    expect(api.listDestinations).not.toHaveBeenCalled();
  });

  it('opens on click with the group items as links and nothing else', () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole('button', { name: /Lưu trú/ }));

    const panel = screen.getByRole('group', { name: 'Lưu trú' });
    expect(screen.getByRole('button', { name: /Lưu trú/ }).getAttribute('aria-expanded')).toBe('true');
    const links = within(panel).getAllByRole('link');
    expect(links.map((l) => l.getAttribute('href'))).toEqual(['/hotels']);
    expect(within(panel).getByRole('link', { name: /Khách sạn & resort/ })).toBeTruthy();
  });

  it('lists services only: no popular-destinations column and no destinations request, however often it opens', async () => {
    render(<Harness />);
    const button = screen.getByRole('button', { name: /Lưu trú/ });
    for (let i = 0; i < 3; i += 1) fireEvent.click(button); // mở, đóng, mở lại
    const panel = screen.getByRole('group', { name: 'Lưu trú' });
    await act(async () => { await Promise.resolve(); });

    expect(within(panel).queryByText('Điểm đến phổ biến')).toBeNull();
    expect(within(panel).queryByRole('link', { name: 'Nha Trang' })).toBeNull();
    expect(api.listDestinations).not.toHaveBeenCalled();
  });

  it('shows every service of a group with its description', () => {
    render(<Harness group={experience} pathname="/" />);
    fireEvent.click(screen.getByRole('button', { name: /Tour và trải nghiệm/ }));
    const panel = screen.getByRole('group', { name: 'Tour và trải nghiệm' });
    expect(within(panel).getAllByRole('link').map((l) => l.getAttribute('href'))).toEqual(['/experiences', '/experiences?type=golf']);
    expect(within(panel).getByText('Khu vui chơi, điểm tham quan')).toBeTruthy();
    expect(within(panel).getByText('Sân golf nghỉ dưỡng')).toBeTruthy();
  });

  it('closes on Escape and returns focus to the button', () => {
    render(<Harness />);
    const button = screen.getByRole('button', { name: /Lưu trú/ });
    fireEvent.click(button);
    const link = within(screen.getByRole('group', { name: 'Lưu trú' })).getAllByRole('link')[0];
    link.focus();

    fireEvent.keyDown(link, { key: 'Escape' });
    expect(screen.queryByRole('group', { name: 'Lưu trú' })).toBeNull();
    expect(document.activeElement).toBe(button);
  });

  it('closes when a menu link is followed', () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole('button', { name: /Lưu trú/ }));
    fireEvent.click(within(screen.getByRole('group', { name: 'Lưu trú' })).getByRole('link', { name: /Khách sạn & resort/ }));
    expect(screen.queryByRole('group', { name: 'Lưu trú' })).toBeNull();
  });

  it('marks the current item with aria-current, telling golf from attractions by ?type', () => {
    render(<Harness group={experience} pathname="/experiences" query="type=golf" />);
    fireEvent.click(screen.getByRole('button', { name: /Tour và trải nghiệm/ }));
    let panel = screen.getByRole('group', { name: 'Tour và trải nghiệm' });
    expect(within(panel).getByRole('link', { name: /Sân golf/ }).getAttribute('aria-current')).toBe('page');
    expect(within(panel).getByRole('link', { name: /Vé tham quan/ }).getAttribute('aria-current')).toBeNull();

    cleanup();
    render(<Harness group={experience} pathname="/experiences" />);
    fireEvent.click(screen.getByRole('button', { name: /Tour và trải nghiệm/ }));
    panel = screen.getByRole('group', { name: 'Tour và trải nghiệm' });
    expect(within(panel).getByRole('link', { name: /Vé tham quan/ }).getAttribute('aria-current')).toBe('page');
  });
});

describe('AllServicesMenu', () => {
  afterEach(() => cleanup());

  function Wrapper({ pathname = '/', query = '' }: { pathname?: string; query?: string }) {
    const [open, setOpen] = useState(false);
    return <AllServicesMenu tone="solid" open={open} onOpenChange={setOpen} pathname={pathname} params={new URLSearchParams(query)} />;
  }

  it('lists every service, grouped under the four header groups, and nothing else', () => {
    render(<Wrapper />);
    fireEvent.click(screen.getByRole('button', { name: 'Tất cả dịch vụ' }));
    const panel = screen.getByRole('group', { name: 'Tất cả dịch vụ' });
    expect(within(panel).getAllByRole('link')).toHaveLength(NAV_ITEMS.length);
    expect(within(panel).queryByRole('link', { name: /Trợ lý/ })).toBeNull();
    for (const group of NAV_GROUPS) {
      const list = within(panel).getByRole('list', { name: group.label });
      expect(within(list).getAllByRole('link')).toHaveLength(group.itemIds.length);
    }
  });

  it('marks the current service with aria-current', () => {
    render(<Wrapper pathname="/experiences" query="type=golf" />);
    fireEvent.click(screen.getByRole('button', { name: 'Tất cả dịch vụ' }));
    const panel = screen.getByRole('group', { name: 'Tất cả dịch vụ' });
    expect(within(panel).getByRole('link', { name: /Sân golf/ }).getAttribute('aria-current')).toBe('page');
    expect(within(panel).getByRole('link', { name: /Vé máy bay/ }).getAttribute('aria-current')).toBeNull();
  });
});

describe('VerticalChips', () => {
  afterEach(() => cleanup());

  it('shows one chip per group and marks the active one', () => {
    render(<VerticalChips activeGroup="stay" />);
    const nav = screen.getByRole('navigation', { name: 'Danh mục dịch vụ' });
    const links = within(nav).getAllByRole('link');
    expect(links.map((l) => l.getAttribute('href'))).toEqual(['/flights', '/hotels', '/experiences', '/combos']);
    expect(within(nav).getByRole('link', { name: 'Lưu trú' }).getAttribute('aria-current')).toBe('page');
    expect(within(nav).getByRole('link', { name: 'Di chuyển' }).getAttribute('aria-current')).toBeNull();
  });

  it('marks nothing on Home', () => {
    render(<VerticalChips activeGroup={null} tone="solid" />);
    for (const link of screen.getAllByRole('link')) expect(link.getAttribute('aria-current')).toBeNull();
  });
});

// Chặn cảnh báo act khi timer của MenuShell còn treo sau test.
afterEach(async () => { await act(async () => { await Promise.resolve(); }); });
