// @vitest-environment jsdom
import React from 'react';
import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { ProductBreadcrumb, breadcrumbOf } from '../../src/components/detail/ProductBreadcrumb';
import type { Product } from '../../src/types/travel';

const product = (taxonomy: Product['taxonomy'], extra: Partial<Product> = {}) =>
  ({ id: 'p1', name: 'Vinpearl Empire Nha Trang', taxonomy, destination: 'Nha Trang', attributes: {}, ...extra }) as Product;

describe('breadcrumbOf', () => {
  it('hotel: Trang chủ › Khách sạn tại {điểm đến} › tên, và mục giữa về /hotels (không phải /search)', () => {
    const crumbs = breadcrumbOf(product('hotel'));
    expect(crumbs.map((c) => c.label)).toEqual(['Trang chủ', 'Khách sạn tại Nha Trang', 'Vinpearl Empire Nha Trang']);
    expect(crumbs[0].href).toBe('/');
    const href = new URL(crumbs[1].href!, 'http://x');
    expect(href.pathname).toBe('/hotels');
    expect(href.searchParams.get('destination')).toBe('Nha Trang');
    expect(href.searchParams.get('q')).toBe('khách sạn');
    expect(crumbs[2].href).toBeUndefined();   // mục hiện tại không phải liên kết
  });

  it('giữ ngày và số khách của tấm tìm kiếm để quay về đúng kết quả', () => {
    const href = new URL(breadcrumbOf(product('hotel'), 'checkIn=2099-10-20&checkOut=2099-10-22&adults=3&children=1&rooms=2')[1].href!, 'http://x');
    expect(href.searchParams.get('checkIn')).toBe('2099-10-20');
    expect(href.searchParams.get('checkOut')).toBe('2099-10-22');
    expect(href.searchParams.get('adults')).toBe('3');
    expect(href.searchParams.get('rooms')).toBe('2');
  });

  it('mỗi loại về trang của loại đó', () => {
    const at = (taxonomy: Product['taxonomy']) => {
      const crumb = breadcrumbOf(product(taxonomy))[1];
      return { label: crumb.label, url: new URL(crumb.href!, 'http://x') };
    };
    expect(at('attraction').label).toBe('Vé tham quan tại Nha Trang');
    expect(at('attraction').url.pathname).toBe('/experiences');
    expect(at('golf').label).toBe('Sân golf tại Nha Trang');
    expect(at('golf').url.pathname + at('golf').url.searchParams.get('type')).toBe('/experiencesgolf');
    expect(at('combo').label).toBe('Combo tại Nha Trang');
    expect(at('combo').url.pathname).toBe('/combos');
    expect(at('flight').label).toBe('Vé máy bay đến Nha Trang');
    expect(at('flight').url.pathname + at('flight').url.search).toBe('/flights?destination=Nha+Trang');
  });

  it('không có điểm đến thì bỏ mục giữa thay vì dẫn tới trang rỗng', () => {
    expect(breadcrumbOf(product('hotel', { destination: '' as never })).map((c) => c.label)).toEqual(['Trang chủ', 'Vinpearl Empire Nha Trang']);
  });
});

describe('ProductBreadcrumb', () => {
  afterEach(cleanup);

  it('là thanh điều hướng có liên kết thật và đánh dấu trang hiện tại', () => {
    render(<ProductBreadcrumb product={product('hotel')} tripQuery="adults=2" />);
    const nav = screen.getByRole('navigation', { name: 'Thanh phân cấp' });
    const links = within(nav).getAllByRole('link');
    expect(links.map((l) => l.textContent)).toEqual(['Trang chủ', 'Khách sạn tại Nha Trang']);
    expect(links[1].getAttribute('href')).toContain('/hotels?');
    expect(links[1].getAttribute('href')).not.toContain('/search');
    expect(within(nav).getByText('Vinpearl Empire Nha Trang').getAttribute('aria-current')).toBe('page');
  });
});
