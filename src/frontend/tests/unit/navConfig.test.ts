import { describe, expect, it } from 'vitest';
import {
  NAV_GROUPS, NAV_ITEMS, activeTaxonomy, categoryShortcuts, isItemActive, isOverlayRoute, itemsOf, resolveActiveGroup,
} from '../../src/components/layout/nav/navConfig';

const params = (query: string) => new URLSearchParams(query);
const item = (id: string) => NAV_ITEMS.find((i) => i.id === id)!;

describe('resolveActiveGroup', () => {
  it('highlights no group on Home, cart, product detail or assistant', () => {
    for (const path of ['/', '/cart', '/product/nt-h-01', '/assistant', '/checkout']) {
      expect(resolveActiveGroup(path, params(''))).toBeNull();
    }
  });

  it('maps each landing route to its group', () => {
    expect(resolveActiveGroup('/flights')).toBe('travel');
    expect(resolveActiveGroup('/hotels')).toBe('stay');
    expect(resolveActiveGroup('/experiences')).toBe('experience');
    expect(resolveActiveGroup('/combos')).toBe('more');
    expect(resolveActiveGroup('/hotels/')).toBe('stay');
  });

  it('follows the type/taxonomy param on /search', () => {
    expect(resolveActiveGroup('/search', params('type=hotel'))).toBe('stay');
    expect(resolveActiveGroup('/search', params('type=flight'))).toBe('travel');
    expect(resolveActiveGroup('/search', params('type=golf'))).toBe('experience');
    expect(resolveActiveGroup('/search', params('taxonomy=combo'))).toBe('more');
    expect(resolveActiveGroup('/search', params('type=unknown'))).toBeNull();
    expect(resolveActiveGroup('/search', params('q=biển'))).toBeNull();
  });
});

describe('isItemActive', () => {
  it('tells attraction from golf on /experiences by ?type', () => {
    expect(activeTaxonomy('/experiences', params(''))).toBe('attraction');
    expect(isItemActive(item('attractions'), '/experiences', params(''))).toBe(true);
    expect(isItemActive(item('golf'), '/experiences', params(''))).toBe(false);
    expect(isItemActive(item('golf'), '/experiences', params('type=golf'))).toBe(true);
    expect(isItemActive(item('attractions'), '/experiences', params('type=golf'))).toBe(false);
  });

  it('marks the assistant item only on /assistant', () => {
    expect(isItemActive(item('assistant'), '/assistant', params(''))).toBe(true);
    expect(isItemActive(item('assistant'), '/hotels', params(''))).toBe(false);
  });
});

describe('overlay routes', () => {
  it('has a hero on Home and the four landing pages only', () => {
    for (const path of ['/', '/hotels', '/flights', '/experiences', '/combos']) expect(isOverlayRoute(path)).toBe(true);
    for (const path of ['/search', '/cart', '/checkout', '/product/x', '/assistant', '/login']) expect(isOverlayRoute(path)).toBe(false);
  });
});

describe('nav data', () => {
  it('lists the four header groups in the reference order', () => {
    expect(NAV_GROUPS.map((g) => g.label)).toEqual(['Di chuyển', 'Lưu trú', 'Tour và trải nghiệm', 'Tiện ích khác']);
  });

  it('resolves every group item and gives every group at least one', () => {
    for (const group of NAV_GROUPS) {
      const items = itemsOf(group);
      expect(items.length).toBe(group.itemIds.length);
      expect(items.length).toBeGreaterThan(0);
    }
    expect(itemsOf(NAV_GROUPS[3]).map((i) => i.id)).toEqual(['combos', 'assistant']);
  });

  it('builds one shortcut per group pointing at its first item', () => {
    const shortcuts = categoryShortcuts();
    expect(shortcuts.map((s) => s.href)).toEqual(['/flights', '/hotels', '/experiences', '/combos']);
  });

  it('never puts numbers or promotions in static descriptions', () => {
    for (const i of NAV_ITEMS) expect(i.description).not.toMatch(/\d|%|giảm|ưu đãi/i);
  });
});
