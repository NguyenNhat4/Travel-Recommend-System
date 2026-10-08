import React from 'react';
import { resolveActiveGroup } from '../../../components/layout/nav/navConfig';
import { CatalogShelf } from './ProductShelf';
import { DestinationTiles } from './DestinationTiles';
import { LandingHero } from './LandingHero';
import { LandingResults } from './LandingResults';
import { PromoBanner } from './PromoBanner';
import { buildSearchHref, isDefaultQuery } from './searchHref';
import type { TripContext } from '../../search/tripContext';
import { VERTICALS, resolveTab, titleWithDestination, type VerticalId } from './verticals';
import type { ListProductsParams } from '../../../services/catalog';

interface VerticalLandingProps {
  vertical: VerticalId;
  /** `?destination=` của URL. */
  destination?: string;
  /** `?type=` của URL; chỉ có nghĩa với danh mục nhiều tab. */
  type?: string;
  /** `?q=` của URL: có mặt thì trang đang ở chế độ tìm và hiện kết quả dưới tấm tìm kiếm. */
  query?: string;
  /** Ngày và số khách của lần tìm (`checkIn`, `checkOut`, `adults`, `children`, `rooms`). */
  trip?: TripContext;
}

/**
 * Trang danh mục dịch vụ (`/hotels`, `/flights`, `/experiences`, `/combos`): một template, cấu hình ở `verticals.ts`.
 * Khối 1 tải ngay; khối 2 và điểm đến chỉ tải khi cuộn tới (docs/plan/2026-09-29-ui-trang-danh-muc-va-header.md §5).
 * Có `?q=` thì là đang tìm: hero thu gọn, kết quả của tab hiện thay các khối trên (như `/flights`).
 */
export function VerticalLanding({ vertical, destination, type, query, trip = {} }: VerticalLandingProps) {
  const config = VERTICALS[vertical];
  const tab = resolveTab(config, type);
  const base: ListProductsParams = {
    taxonomy: tab.taxonomy,
    availableOnly: true,
    limit: 8,
    ...(destination ? { destination } : {}),
  };
  const everywhereHref = buildSearchHref({ taxonomy: tab.taxonomy, origin: '', location: '', destination: null, trip: {} });
  const searching = query !== undefined;
  const hero = (
    <LandingHero
      config={config}
      tab={tab}
      activeGroup={resolveActiveGroup(config.route)}
      destination={destination}
      search={searching ? { origin: '', trip } : undefined}
      initialText={searching && !isDefaultQuery(query) ? query : undefined}
      compact={searching}
    />
  );

  if (searching) {
    return (
      <div className="flex flex-col bg-white">
        {hero}
        <LandingResults tab={tab} query={query} destination={destination} trip={trip} />
      </div>
    );
  }

  return (
    <div className="flex flex-col bg-white">
      {hero}

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
