import React from 'react';
import { resolveActiveGroup } from '../../../components/layout/nav/navConfig';
import { CatalogShelf } from './ProductShelf';
import { DestinationTiles } from './DestinationTiles';
import { LandingHero } from './LandingHero';
import { PromoBanner } from './PromoBanner';
import { buildSearchHref } from './searchHref';
import { VERTICALS, resolveTab, titleWithDestination, type VerticalId } from './verticals';
import type { ListProductsParams } from '../../../services/catalog';

interface VerticalLandingProps {
  vertical: VerticalId;
  /** `?destination=` của URL. */
  destination?: string;
  /** `?type=` của URL; chỉ có nghĩa với danh mục nhiều tab. */
  type?: string;
}

/**
 * Trang danh mục dịch vụ (`/hotels`, `/flights`, `/experiences`, `/combos`): một template, cấu hình ở `verticals.ts`.
 * Khối 1 tải ngay; khối 2 và điểm đến chỉ tải khi cuộn tới (docs/plan/2026-09-29-ui-trang-danh-muc-va-header.md §5).
 */
export function VerticalLanding({ vertical, destination, type }: VerticalLandingProps) {
  const config = VERTICALS[vertical];
  const tab = resolveTab(config, type);
  const base: ListProductsParams = {
    taxonomy: tab.taxonomy,
    availableOnly: true,
    limit: 8,
    ...(destination ? { destination } : {}),
  };
  const everywhereHref = buildSearchHref({ taxonomy: tab.taxonomy, origin: '', location: '', destination: null, trip: {} });

  return (
    <div className="flex flex-col bg-white">
      <LandingHero config={config} tab={tab} activeGroup={resolveActiveGroup(config.route)} destination={destination} />

      {/* Tờ nền trắng bo góc trên đè lên hero 32 px; z-10 để dưới popover của tấm tìm kiếm (z-30). */}
      <div className="relative z-10 -mt-8 rounded-t-4xl bg-white pt-4">
        <CatalogShelf
          lazy={false}
          title={titleWithDestination(tab.popularTitle, tab, destination)}
          params={{ ...base, sort: 'popular' }}
          empty={destination
            ? { text: `Chưa có ${tab.noun} ${tab.atWord} ${destination}.`, href: everywhereHref, hrefLabel: `Xem tất cả ${tab.noun}` }
            : { text: `Chưa có ${tab.noun} để hiển thị lúc này.` }}
        />
        <CatalogShelf
          title={titleWithDestination(tab.cheapTitle, tab, destination)}
          params={{ ...base, sort: 'price_asc' }}
          hideBelow={3}
        />
        <DestinationTiles route={config.route} query={tab.taxonomy === config.tabs[0].taxonomy ? undefined : { type: tab.taxonomy }} />
        <PromoBanner promo={config.promo} destination={destination} />
      </div>
    </div>
  );
}
