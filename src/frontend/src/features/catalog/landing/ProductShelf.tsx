'use client';

import React, { useId, useMemo, useRef } from 'react';
import Link from 'next/link';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import type { Product } from '../../../types/travel';
import { listProducts, productFromApi, type ListProductsParams } from '../../../services/catalog';
import { useInView } from '../../../hooks/useInView';
import { useLazySection } from '../../../hooks/useLazySection';
import { ProductCard } from '../../../components/common/ProductCard';

/** Dưới ngưỡng này thì carousel không còn ý nghĩa (frontend §6.4). */
export const MIN_CARDS_FOR_CAROUSEL = 3;

const CARD_WIDTH = 'w-[72%] shrink-0 sm:w-[calc((100%-24px)/2)] md:w-[calc((100%-48px)/3)] lg:w-[calc((100%-72px)/4)]';

export interface ShelfState {
  items: Product[] | null;
  loading: boolean;
  error: boolean;
}

export interface ProductShelfProps {
  title: string;
  state: ShelfState;
  onRetry: () => void;
  /** Khi không có sản phẩm nào: câu thay thế và lối đi tiếp. Không khai thì khối rỗng bị ẩn. */
  empty?: { text: string; href?: string; hrefLabel?: string };
  /** Ít thẻ hơn ngưỡng này thì ẩn cả khối (dành cho khối phụ). */
  hideBelow?: number;
  /** Query string ngữ cảnh chuyến đi nối vào liên kết sản phẩm. */
  tripQuery?: string;
}

function SkeletonCard() {
  return (
    <div className={`${CARD_WIDTH} flex flex-col gap-3`} aria-hidden="true">
      <div className="skeleton-wave aspect-square w-full rounded-3xl" />
      <div className="flex flex-col gap-2 px-1">
        <div className="skeleton-wave h-5 w-3/4 rounded-md" />
        <div className="skeleton-wave h-4 w-1/2 rounded-md" />
        <div className="skeleton-wave h-6 w-32 rounded-md" />
      </div>
    </div>
  );
}

export function ProductShelf({
  title, state, onRetry, empty, hideBelow = 0, tripQuery,
}: ProductShelfProps) {
  const headingId = useId();
  const trackRef = useRef<HTMLDivElement>(null);
  const items = state.items ?? [];
  const settled = !state.loading && !state.error;

  if (settled && items.length < Math.max(hideBelow, empty ? 0 : 1)) return null;

  const scrollTrack = (direction: -1 | 1) => {
    const track = trackRef.current;
    if (!track) return;
    track.scrollBy({ left: direction * track.clientWidth * 0.9, behavior: 'smooth' });
  };

  return (
    <section aria-labelledby={headingId} className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-6 flex items-center justify-between gap-4">
        <h2 id={headingId} className="type-title text-slate-900">{title}</h2>
        <div className="flex items-center gap-3">
          {items.length > 0 && (
            <div className="hidden items-center gap-2 md:flex">
              <button type="button" onClick={() => scrollTrack(-1)} aria-label="Cuộn sang trái" className="flex h-10 w-10 cursor-pointer items-center justify-center rounded-full border border-slate-200 text-slate-600 shadow-sm transition hover:bg-slate-100 active:scale-95">
                <ChevronLeft className="h-5 w-5" aria-hidden="true" />
              </button>
              <button type="button" onClick={() => scrollTrack(1)} aria-label="Cuộn sang phải" className="flex h-10 w-10 cursor-pointer items-center justify-center rounded-full border border-slate-200 text-slate-600 shadow-sm transition hover:bg-slate-100 active:scale-95">
                <ChevronRight className="h-5 w-5" aria-hidden="true" />
              </button>
            </div>
          )}
        </div>
      </div>

      {state.error ? (
        <div role="alert" className="rounded-2xl border border-slate-200 bg-slate-50 p-6 text-center text-sm text-slate-600">
          Chưa tải được danh sách ·{' '}
          <button type="button" onClick={onRetry} className="cursor-pointer font-semibold text-brand-600 hover:underline">Thử lại</button>
        </div>
      ) : state.loading && items.length === 0 ? (
        <div className="flex gap-6 overflow-hidden" aria-busy="true">
          {[0, 1, 2, 3].map((i) => <SkeletonCard key={i} />)}
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-8 text-center text-sm text-slate-600">
          <p>{empty?.text}</p>
          {empty?.href && (
            <Link href={empty.href} className="mt-2 inline-block font-semibold text-brand-600 hover:underline">{empty.hrefLabel ?? 'Xem tất cả'}</Link>
          )}
        </div>
      ) : (
        <div ref={trackRef} className="no-scrollbar snap-row -mx-4 flex gap-6 overflow-x-auto scroll-smooth px-4 pb-4 sm:mx-0 sm:px-0">
          {items.map((product) => (
            <div key={product.id} className={CARD_WIDTH}>
              <ProductCard product={product} variant="tile" tripQuery={tripQuery} />
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

interface CatalogShelfProps extends Omit<ProductShelfProps, 'state' | 'onRetry'> {
  params: ListProductsParams;
  /** true (mặc định): chỉ tải khi khối vào vùng nhìn. false: tải ngay khi mount (khối đầu trang). */
  lazy?: boolean;
}

/** `ProductShelf` + `GET /products`: một request cho mỗi bộ tham số, tải khi cần, có bộ đệm ngắn. */
export function CatalogShelf({ params, lazy = true, ...shelf }: CatalogShelfProps) {
  const [ref, inView] = useInView<HTMLDivElement>();
  const key = `products:${JSON.stringify(params)}`;
  const section = useLazySection(key, (signal) => listProducts(params, signal), { enabled: !lazy || inView });
  const items = useMemo(() => (section.data ? section.data.results.map(productFromApi) : null), [section.data]);
  // Chưa vào vùng nhìn thì giữ khung skeleton (không nháy "rỗng" rồi mới có thẻ, không nhảy layout khi dữ liệu về).
  const waiting = lazy && !inView;

  return (
    <div ref={ref}>
      <ProductShelf {...shelf} state={{ items, loading: section.loading || waiting, error: section.error !== null }} onRetry={section.retry} />
    </div>
  );
}
