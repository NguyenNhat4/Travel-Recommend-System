import React from 'react';
import Link from 'next/link';
import { ChevronRight, Home } from 'lucide-react';
import { buildSearchHref } from '../../features/catalog/landing/searchHref';
import { verticalForTaxonomy, resolveTab } from '../../features/catalog/landing/verticals';
import { parseTripContext } from '../../features/search/tripContext';
import type { Product } from '../../types/travel';

export interface Crumb {
  label: string;
  /** Không có `href` là mục hiện tại (trang đang xem). */
  href?: string;
}

/**
 * Thanh phân cấp của trang chi tiết: Trang chủ › {Loại} tại {điểm đến} › {tên sản phẩm}.
 * Mục giữa quay về đúng trang danh mục của loại này (`/hotels`, `/experiences`, `/combos`) với kết quả của điểm đến đó, giữ ngày và
 * số khách đã chọn ở tấm tìm kiếm (`tripQuery`); không sang `/search`, trang gộp dành cho câu tìm tự do. Vé máy bay không có
 * trang kết quả riêng nên về `/flights?destination=`.
 */
export function breadcrumbOf(product: Product, tripQuery = ''): Crumb[] {
  const home: Crumb = { label: 'Trang chủ', href: '/' };
  const current: Crumb = { label: product.name };
  if (!product.destination) return [home, current];
  const vertical = verticalForTaxonomy(product.taxonomy);
  const tab = resolveTab(vertical, product.taxonomy);
  const label = `${tab.label} ${tab.atWord} ${product.destination}`;
  const href = product.taxonomy === 'flight'
    ? `${vertical.route}?${new URLSearchParams({ destination: product.destination }).toString()}`
    : buildSearchHref({
      taxonomy: product.taxonomy, origin: '', location: '', destination: product.destination,
      trip: parseTripContext(new URLSearchParams(tripQuery)),
    });
  return [home, { label, href }, current];
}

export const ProductBreadcrumb: React.FC<{ product: Product; tripQuery?: string }> = ({ product, tripQuery }) => {
  const crumbs = breadcrumbOf(product, tripQuery);
  return (
    <nav aria-label="Thanh phân cấp" className="-ml-2">
      <ol className="no-scrollbar flex flex-nowrap items-center gap-0.5 overflow-x-auto text-sm text-slate-600 sm:flex-wrap sm:overflow-visible">
        {crumbs.map((crumb, index) => (
          <li key={`${index}-${crumb.label}`} className="flex shrink-0 items-center gap-0.5 sm:min-w-0">
            {index > 0 && <ChevronRight className="h-3.5 w-3.5 shrink-0 text-slate-400" aria-hidden="true" />}
            {crumb.href ? (
              <Link href={crumb.href}
                className="inline-flex min-h-8 items-center gap-1.5 rounded-lg px-2 font-medium transition-colors hover:bg-brand-50 hover:text-brand-700 focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand-500 motion-reduce:transition-none">
                {index === 0 && <Home className="h-3.5 w-3.5" aria-hidden="true" />}
                {crumb.label}
              </Link>
            ) : (
              <span aria-current="page" className="inline-flex min-h-8 max-w-[16rem] items-center truncate rounded-lg bg-slate-100 px-2.5 font-semibold text-slate-900 sm:max-w-none">{crumb.label}</span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
};
