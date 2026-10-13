'use client';

import React, { useId } from 'react';
import { ArrowRight } from 'lucide-react';
import { SEARCH_GROUPS, searchShelfApi, shelfCacheKey, type TabGroup } from '../../services/search';
import { useLazySection } from '../../hooks/useLazySection';
import { ProductCard } from '../common/ProductCard';
import { SkeletonBlock, SkeletonStatus } from '../common/Skeleton';
import { HScroller } from './HScroller';

const CARD_WIDTH = 'w-[72%] shrink-0 snap-start sm:w-[calc((100%-16px)/2)] md:w-[calc((100%-32px)/3)] lg:w-[calc((100%-48px)/4)]';

/** Bốn ô khung của một hàng (ảnh vuông, tên, dòng phụ), cùng bề rộng ô thật; đặt trong một hàng `flex gap-4 overflow-hidden`. */
export const ShelfTilesSkeleton: React.FC = () => (
  <>
    {[0, 1, 2, 3].map((i) => (
      <div key={i} className={`${CARD_WIDTH} flex flex-col gap-3`} aria-hidden="true">
        <SkeletonBlock className="aspect-square w-full rounded-3xl" />
        <SkeletonBlock className="h-5 w-3/4 rounded-md" />
        <SkeletonBlock className="h-4 w-1/2 rounded-md" />
      </div>
    ))}
  </>
);

interface GroupShelfProps {
  group: TabGroup;
  query: string;
  destination: string | null;
  tripQuery: string;
  onSeeAll: (group: TabGroup) => void;
}

/**
 * Một hàng của tab "Tất cả": chỉ `PREVIEW_LIMIT` mục đầu của nhóm, cuộn ngang. Cùng request và khóa bộ đệm với số
 * trên tab (`searchOverviewApi`), nên ba hàng tải cùng lúc với số tab và số ở hàng luôn bằng số trên tab. Danh sách
 * đầy đủ chỉ tải khi người dùng bấm "Xem tất cả" (tab của nhóm).
 */
export const GroupShelf: React.FC<GroupShelfProps> = ({ group, query, destination, tripQuery, onSeeAll }) => {
  const headingId = useId();
  const section = useLazySection(shelfCacheKey(query, destination, group), () => searchShelfApi(query, group, destination));
  const items = section.data?.items ?? [];
  const count = section.data?.total ?? 0;
  const settled = !section.loading && !section.error;

  // Nhóm không có kết quả thì không chiếm chỗ ở "Tất cả".
  if (settled && section.data && items.length === 0) return null;

  return (
    <section aria-labelledby={headingId} className="space-y-3">
      <div className="flex items-baseline justify-between gap-4">
        <h2 id={headingId} className="text-lg font-black text-slate-900">
          {SEARCH_GROUPS[group].label}
          {section.data && <span className="ml-2 text-xs font-medium text-slate-500">{count} kết quả</span>}
        </h2>
        <button type="button" onClick={() => onSeeAll(group)} className="inline-flex cursor-pointer items-center gap-1 text-sm font-semibold text-brand-600 hover:text-brand-700">
          Xem tất cả <ArrowRight className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>

      {section.error ? (
        <div role="alert" className="rounded-2xl border border-slate-200 bg-slate-50 p-6 text-center text-sm text-slate-600">
          Chưa tải được nhóm này ·{' '}
          <button type="button" onClick={section.retry} className="cursor-pointer font-semibold text-brand-600 hover:underline">Thử lại</button>
        </div>
      ) : section.loading && items.length === 0 ? (
        <SkeletonStatus label={`Đang tải ${SEARCH_GROUPS[group].label}`} className="flex gap-4 overflow-hidden">
          <ShelfTilesSkeleton />
        </SkeletonStatus>
      ) : (
        <HScroller count={items.length + 1} label={`Kết quả nhóm ${SEARCH_GROUPS[group].label}`}>
          {items.map((item) => (
            <div key={item.product.id} className={CARD_WIDTH}>
              <ProductCard product={item.product} variant="tile" tripQuery={tripQuery} />
            </div>
          ))}
          {count > items.length && (
            <div className={CARD_WIDTH}>
              <button
                type="button"
                onClick={() => onSeeAll(group)}
                className="flex aspect-square w-full cursor-pointer flex-col items-center justify-center gap-2 rounded-3xl border border-dashed border-brand-300 bg-brand-50 p-4 text-center text-brand-700 hover:bg-brand-100"
              >
                <span className="text-base font-bold">Còn {count - items.length} kết quả</span>
                <span className="inline-flex items-center gap-1 text-sm font-semibold">Xem tất cả {count} <ArrowRight className="h-4 w-4" aria-hidden="true" /></span>
              </button>
            </div>
          )}
        </HScroller>
      )}
    </section>
  );
};
