import { describe, expect, it } from 'vitest';
import { NAV_ITEMS, TAXONOMIES } from '../../src/components/layout/nav/navConfig';
import {
  DEFAULT_QUERY, VERTICALS, VERTICAL_LIST, resolveTab, titleWithDestination, verticalForTaxonomy,
} from '../../src/features/catalog/landing/verticals';
import { coverFor } from '../../src/features/catalog/landing/destinationCovers';

describe('verticals', () => {
  it('has a default query for every taxonomy', () => {
    for (const taxonomy of TAXONOMIES) expect(DEFAULT_QUERY[taxonomy].length).toBeGreaterThan(0);
  });

  it('keeps routes in step with navConfig: every nav item with a taxonomy lands on a vertical route', () => {
    const routes = VERTICAL_LIST.map((v) => v.route);
    for (const item of NAV_ITEMS.filter((i) => i.taxonomy)) {
      expect(routes).toContain(item.href.split('?')[0]);
    }
  });

  it('covers every taxonomy exactly once across the tabs', () => {
    const taxonomies = VERTICAL_LIST.flatMap((v) => v.tabs.map((t) => t.taxonomy)).sort();
    expect(taxonomies).toEqual([...TAXONOMIES].sort());
  });

  it('lets only /experiences carry two tabs, attraction first', () => {
    expect(VERTICALS.experiences.tabs.map((t) => t.taxonomy)).toEqual(['attraction', 'golf']);
    for (const id of ['hotels', 'flights', 'combos'] as const) expect(VERTICALS[id].tabs).toHaveLength(1);
  });

  it('resolves the tab from ?type and falls back to the first', () => {
    expect(resolveTab(VERTICALS.experiences, 'golf').taxonomy).toBe('golf');
    expect(resolveTab(VERTICALS.experiences, 'hotel').taxonomy).toBe('attraction');
    expect(resolveTab(VERTICALS.experiences, null).taxonomy).toBe('attraction');
    expect(resolveTab(VERTICALS.hotels, 'golf').taxonomy).toBe('hotel');
  });

  it('finds the vertical that owns a taxonomy', () => {
    expect(verticalForTaxonomy('golf').id).toBe('experiences');
    expect(verticalForTaxonomy('flight').id).toBe('flights');
  });

  it('adds the destination to a shelf title with the right preposition', () => {
    expect(titleWithDestination('Chặng bay phổ biến', VERTICALS.flights.tabs[0], 'Nha Trang')).toBe('Chặng bay phổ biến đến Nha Trang');
    expect(titleWithDestination('Khách sạn và resort phổ biến', VERTICALS.hotels.tabs[0], 'Phú Quốc')).toBe('Khách sạn và resort phổ biến tại Phú Quốc');
    expect(titleWithDestination('Khách sạn và resort phổ biến', VERTICALS.hotels.tabs[0], null)).toBe('Khách sạn và resort phổ biến');
  });

  it('only flights ask for an origin, and only hotels for rooms', () => {
    expect(VERTICALS.flights.sheet.origin).toBeDefined();
    expect(VERTICALS.flights.sheet.dates.mode).toBe('single-or-return');
    for (const id of ['hotels', 'experiences', 'combos'] as const) expect(VERTICALS[id].sheet.origin).toBeUndefined();
    expect(VERTICAL_LIST.filter((v) => v.sheet.rooms).map((v) => v.id)).toEqual(['hotels']);
  });

  it('keeps hard-coded copy free of prices, counts and promotions', () => {
    for (const v of VERTICAL_LIST) {
      const copy = [v.title, v.subtitle, v.promo.title, v.promo.body, v.promo.cta, ...v.tabs.flatMap((t) => [t.popularTitle, t.cheapTitle])].join(' ');
      expect(copy).not.toMatch(/\d|%|giảm giá|khuyến mãi|ưu đãi/i);
    }
  });

  it('returns a cover only for known destination labels', () => {
    expect(coverFor('Nha Trang')).toMatch(/^https:\/\//);
    expect(coverFor('Điểm đến lạ')).toBeNull();
  });
});
