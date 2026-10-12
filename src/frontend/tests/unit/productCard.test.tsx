// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import diversifiedFixture from '../../../shared/mocks/catalog/listProducts.200-diversified.json';

vi.mock('../../src/context/TravelContext', () => ({
  useTravel: () => ({ navigate: vi.fn(), debugMode: false, recordEvent: vi.fn() }),
}));

import { ProductCard } from '../../src/components/common/ProductCard';
import { productFromApi } from '../../src/services/catalog';

const golf = productFromApi(diversifiedFixture.results.find((r) => r.taxonomy === 'golf') as any);
const combo = productFromApi(diversifiedFixture.results.find((r) => r.taxonomy === 'combo') as any);

/** Nhãn loại trên thẻ tile chỉ bật ở kệ trộn nhiều loại (product.md §4.0; kệ Phổ biến tab Tất cả ở Home). */
describe('ProductCard tile taxonomy label', () => {
  afterEach(cleanup);

  it('has no type label by default (decision of 2026-10-01)', () => {
    render(<ProductCard product={golf} variant="tile" />);
    expect(screen.queryByText('Golf')).toBeNull();
  });

  it('shows the type label inside the link when the shelf mixes types', () => {
    render(<ProductCard product={golf} variant="tile" showTaxonomy />);
    expect(screen.getByRole('link', { name: /Golf/ })).toBeTruthy();
  });

  it('tells a combo apart from a flight even when its name starts with "Vé máy bay"', () => {
    render(<ProductCard product={combo} variant="tile" showTaxonomy />);
    expect(screen.getByText('Combo')).toBeTruthy();
    expect(screen.queryByText('Vé máy bay')).toBeNull();
  });
});
