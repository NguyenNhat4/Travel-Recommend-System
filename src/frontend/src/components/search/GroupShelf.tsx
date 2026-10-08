'use client';

import React, { useId } from 'react';
import { ArrowRight } from 'lucide-react';
import { PREVIEW_LIMIT, SEARCH_GROUPS, searchCacheKey, searchGroupApi, type TabGroup } from '../../services/search';
import { useInView } from '../../hooks/useInView';
import { useLazySection } from '../../hooks/useLazySection';
import { ProductCard } from '../common/ProductCard';
import { HScroller } from './HScroller';

const CARD_WIDTH = 'w-[72%] shrink-0 snap-start sm:w-[calc((100%-16px)/2)] md:w-[calc((100%-32px)/3)] lg:w-[calc((100%-48px)/4)]';

interface GroupShelfProps {
  group: TabGroup;
  query: string;
  destination: string | null;
  tripQuery: string;
  /** Tổng của nhóm từ `searchOverviewApi`, dùng khi hàng chưa tải xong. */
  total?: number;
  /** true: chỉ tải khi hàng gần vào vùng nhìn (các hàng dưới màn hình đầu). */
  lazy: boolean;
  onSeeAll: (group: TabGroup) => void;
}

/**
 * Một hàng của tab "Tất cả": chỉ `PREVIEW_LIMIT` mục đầu của nhóm, cuộn ngang. Kết quả nằm trong bộ đệm của
 * `useLazySection`; danh sách đầy đủ chỉ tải khi người dùng bấm "Xem tất cả" (tab của nhóm).
 */
export const GroupShelf: React.FC<GroupShelfProps> = ({ group, query, destination, tripQuery, total, lazy, onSeeAll }) => {
  const headingId = useId();
  const [ref, inView] = useInView<HTMLDivElement>();
  const key = searchCacheKey('group', query, destination, group, PREVIEW_LIMIT, 0);
  const section = useLazySection(
    key,
    () => searchGroupApi(query, group, { destination, limit: PREVIEW_LIMIT, offset: 0 }),
    { enabled: !lazy || inView },
  );
  const items = section.data?.items ?? [];
  const count = section.data?.total ?? total ?? items.length;
  const settled = !section.loading && !section.error;

  // Nhóm không có kết quả thì không chiếm chỗ ở "Tất cả".
  if (settled && section.data && items.length === 0) return null;

  return (
    <section ref={ref} aria-labelledby={headingId} className="space-y-3">
      <div className="flex items-baseline justify-between gap-4">
        <h2 id={headingId} className="text-lg font-black text-slate-900">
          {SEARCH_GROUPS[group].label}
          <span className="ml-2 text-xs font-medium text-slate-500">{count} kết quả</span>
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
        <div className="flex gap-4 overflow-hidden" aria-busy="true">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className={`${CARD_WIDTH} flex flex-col gap-3`} aria-hidden="true">
              <div className="skeleton-wave aspect-square w-full rounded-3xl" />
              <div className="skeleton-wave h-5 w-3/4 rounded-md" />
              <div className="skeleton-wave h-4 w-1/2 rounded-md" />
            </div>
          ))}
        </div>
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
