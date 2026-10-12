'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { Filter, Search, X } from 'lucide-react';
import { ApiError } from '../../services/http';
import {
  GROUP_PAGE_SIZE, SEARCH_GROUPS, searchCacheKey, searchGroupApi, sortItems,
  type Guests, type PriceStarFilter, type SearchGroup, type Stay, type SearchResultItem, type SortOption,
} from '../../services/search';
import type { Taxonomy } from '../../types/travel';
import { loadSection } from '../../hooks/useLazySection';
import { ProductCard } from '../common/ProductCard';
import { SearchAssistantBanner } from './SearchAssistantBanner';
import { SortMenu } from './SortMenu';

interface GroupResultsProps {
  group: SearchGroup;
  query: string;
  destination: string | null;
  tripQuery: string;
  onClearDestination: () => void;
  onAskAssistant: () => void;
  /** Thu hẹp nhóm về một loại (tab Vé tham quan / Sân golf ở /experiences); không có thì cả nhóm. */
  taxonomy?: Taxonomy;
  /** Số khách một phòng/đơn vị của tấm tìm kiếm: lọc cứng theo sức chứa ở API. */
  guests?: Guests;
  /** Ngày của tấm tìm kiếm: lọc cứng ở API (khách sạn theo luật đặt phòng và lịch phòng; vé theo cửa sổ mở bán). */
  stay?: Stay;
  /** Nhãn ở chip "Đang lọc" thay cho nhãn nhóm. */
  label?: string;
  /** Đặt trong trang danh mục: điểm đến là bộ lọc của tấm tìm kiếm nên bỏ ghi chú "không có bộ lọc điểm đến". */
  embedded?: boolean;
}

interface Loaded {
  items: SearchResultItem[];
  total: number;
  hasMore: boolean;
}

/** Thanh trượt giá: chờ người dùng dừng kéo rồi mới gọi API (mỗi nấc là một request). */
const PRICE_DEBOUNCE_MS = 400;
const PRICE_SLIDER_MAX = 8_000_000;

/**
 * Danh sách đầy đủ của một nhóm (tab Lưu trú, Tour và trải nghiệm, Tiện ích khác; hoặc vé máy bay khi mở từ /flights).
 * Mỗi trang `GROUP_PAGE_SIZE` mục, "Xem thêm" nối trang kế; từng trang nằm trong bộ đệm nên quay lại tab không tải lại.
 * Sắp xếp là popup ở mọi nhóm (chạy trên các mục đã tải); lọc hạng sao và giá chỉ có ở Lưu trú (đơn vị giá đồng nhất)
 * và gửi lên API (`starRatingMin`, `priceMax`), nên `total` và "Xem thêm" đếm theo bộ lọc.
 * Cha đặt `key` theo (nhóm, truy vấn, điểm đến) nên state ở đây tự đặt lại khi các giá trị đó đổi.
 */
export const GroupResults: React.FC<GroupResultsProps> = ({ group, query, destination, tripQuery, onClearDestination, onAskAssistant, taxonomy, guests, stay, label, embedded }) => {
  const [pages, setPages] = useState(1);
  const [retryToken, setRetryToken] = useState(0);
  const [sort, setSort] = useState<SortOption>('relevance');
  const [filter, setFilter] = useState<PriceStarFilter>({});
  // Giá trên thanh trượt (hiện ngay); `filter.maxPrice` là giá đã gửi API.
  const [priceDraft, setPriceDraft] = useState<number | undefined>(undefined);
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const { minStarRating, maxPrice } = filter;

  // Đổi bộ lọc là một danh sách mới: về trang 1 và bỏ danh sách cũ (kết quả và số "Xem thêm" cũ không còn đúng).
  const applyFilter = (next: (current: PriceStarFilter) => PriceStarFilter) => {
    setFilter(next);
    setPages(1);
    setLoaded(null);
  };

  useEffect(() => {
    if (priceDraft === maxPrice) return undefined;
    const timer = setTimeout(() => applyFilter((current) => ({ ...current, maxPrice: priceDraft })), PRICE_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [priceDraft, maxPrice]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all(Array.from({ length: pages }, (_, index) => {
      const offset = index * GROUP_PAGE_SIZE;
      return loadSection(
        searchCacheKey('group', query, destination, group, GROUP_PAGE_SIZE, offset, taxonomy, guests, stay, filter),
        () => searchGroupApi(query, group, { destination, limit: GROUP_PAGE_SIZE, offset, taxonomy, guests, stay, ...filter }),
      );
    })).then((list) => {
      if (cancelled) return;
      const seen = new Set<string>();
      const items = list.flatMap((page) => page.items).filter((item) => !seen.has(item.product.id) && seen.add(item.product.id));
      setLoaded({ items, total: list[0].total, hasMore: list[list.length - 1].hasMore });
      setLoading(false);
    }).catch((err) => {
      if (cancelled) return;
      // Không thay bằng kết quả giả: hiện lỗi, giữ nguyên truy vấn để Thử lại (frontend §4.2).
      setError(err instanceof ApiError ? err : new ApiError('Chưa tìm được lúc này. Vui lòng thử lại.', 'INTERNAL_ERROR', 0, true));
      setLoading(false);
    });
    return () => { cancelled = true; };
  // guests và stay là object dựng lại mỗi lần render của cha: so theo giá trị từng trường để không tải lại vô ích.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, destination, group, taxonomy, guests?.adults, guests?.children, stay?.checkIn, stay?.checkOut, minStarRating, maxPrice, pages, retryToken]);

  const visible = useMemo(() => sortItems(loaded?.items ?? [], sort), [loaded, sort]);
  const isStay = group === 'stay';
  const hasFilters = minStarRating !== undefined || maxPrice !== undefined;
  const setStar = (value: number | undefined) => applyFilter((current) => ({ ...current, minStarRating: value }));
  const clearPrice = () => {
    setPriceDraft(undefined);
    applyFilter((current) => ({ ...current, maxPrice: undefined }));
  };
  const clearFilters = () => {
    setPriceDraft(undefined);
    applyFilter(() => ({}));
  };

  const sidebar = isStay && (
    <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-6">
      <div className="flex items-center justify-between pb-3 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-slate-600" />
          <span className="text-sm font-bold text-slate-900">Bộ lọc tìm kiếm</span>
        </div>
        {hasFilters && (
          <button onClick={clearFilters} className="text-xs text-rose-600 hover:underline font-medium">Xóa tất cả</button>
        )}
      </div>

      <div className="space-y-2.5">
        <h4 className="font-sans text-xs font-bold text-slate-800 uppercase tracking-wider">Hạng sao khách sạn</h4>
        <div className="space-y-1.5">
          {[
            { label: 'Tất cả hạng sao', val: undefined },
            { label: '5 sao (Luxury)', val: 5 },
            { label: '4 sao trở lên', val: 4 },
          ].map((opt) => (
            <label key={opt.label} className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer">
              <input
                type="radio"
                name="starRating"
                checked={minStarRating === opt.val}
                onChange={() => setStar(opt.val)}
                className="text-brand-600 focus:ring-brand-500 w-3.5 h-3.5"
              />
              <span>{opt.label}</span>
            </label>
          ))}
        </div>
      </div>

      <div className="space-y-2.5 pt-4 border-t border-slate-100">
        <h4 className="font-sans text-xs font-bold text-slate-800 uppercase tracking-wider">Mức giá tối đa</h4>
        <div className="space-y-2">
          <input
            type="range"
            min="500000"
            max={PRICE_SLIDER_MAX}
            step="500000"
            aria-label="Mức giá tối đa"
            value={priceDraft ?? PRICE_SLIDER_MAX}
            onChange={(e) => {
              const value = parseInt(e.target.value, 10);
              setPriceDraft(value >= PRICE_SLIDER_MAX ? undefined : value);
            }}
            className="w-full accent-brand-600"
          />
          <div className="flex justify-between text-xs text-slate-500 font-mono">
            <span>500k</span>
            <span className="font-bold text-brand-700">{priceDraft ? new Intl.NumberFormat('vi-VN').format(priceDraft) + ' ₫' : 'Tất cả'}</span>
            <span>8tr+</span>
          </div>
        </div>
      </div>

      {!embedded && (
        <p className="rounded-lg bg-slate-50 px-3 py-2 text-[11px] text-slate-500">
          Điểm đến do câu tìm kiếm quyết định, nên không có bộ lọc điểm đến.
        </p>
      )}
    </div>
  );

  let body: React.ReactNode;
  if (error) {
    body = (
      <div className="p-10 text-center bg-white rounded-2xl border border-slate-200 space-y-3">
        <h3 className="text-base font-bold text-slate-800">{error.message}</h3>
        {error.retryable && (
          <button onClick={() => setRetryToken((n) => n + 1)} className="px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white font-bold text-xs rounded-lg transition-colors">
            Thử lại
          </button>
        )}
      </div>
    );
  } else if (loading && !loaded) {
    body = (
      <div className="space-y-4" aria-busy="true">
        {[0, 1, 2].map((i) => <div key={i} className="h-36 rounded-xl bg-slate-100 animate-pulse" />)}
      </div>
    );
  } else if (visible.length > 0) {
    body = (
      <div className="space-y-4">
        {visible.map((item, index) => (
          <React.Fragment key={item.product.id}>
            <ProductCard product={item.product} variant="row" tripQuery={tripQuery} score={item.relevanceScore} rank={index + 1} />
            {index === 2 && <SearchAssistantBanner query={query} />}
          </React.Fragment>
        ))}
        {loaded?.hasMore && (
          <div className="text-center pt-2">
            <button
              onClick={() => setPages((n) => n + 1)}
              disabled={loading}
              className="px-5 py-2.5 bg-white border border-slate-300 hover:border-brand-500 hover:text-brand-700 text-slate-700 font-bold text-xs rounded-lg transition-colors disabled:opacity-60"
            >
              {loading ? 'Đang tải…' : `Xem thêm (${loaded.items.length}/${loaded.total})`}
            </button>
          </div>
        )}
      </div>
    );
  } else {
    body = (
      <div className="p-12 text-center bg-white rounded-2xl border border-slate-200 space-y-4">
        <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mx-auto text-slate-400">
          <Search className="w-6 h-6" />
        </div>
        <div>
          <h3 className="text-base font-bold text-slate-800">
            {hasFilters ? 'Không có kết quả với bộ lọc hiện tại' : `Chưa tìm thấy dịch vụ nào cho “${query}”`}
          </h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1">
            Hãy thử thay đổi từ khóa, bỏ bớt bộ lọc hoặc nhờ Trợ lý AI gợi ý lịch trình.
          </p>
        </div>
        <div className="flex justify-center gap-3">
          {hasFilters && (
            <button onClick={clearFilters} className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs rounded-lg transition-colors">
              Xóa bộ lọc
            </button>
          )}
          <button onClick={onAskAssistant} className="px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white font-bold text-xs rounded-lg transition-colors">
            Nhờ Trợ lý AI gợi ý
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={`grid grid-cols-1 gap-6 items-start ${isStay ? 'lg:grid-cols-4' : ''}`}>
      {sidebar}
      <div className={`space-y-4 ${isStay ? 'lg:col-span-3' : ''}`}>
        <div className="bg-white p-3.5 rounded-xl border border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-slate-400 font-medium">Đang lọc:</span>
            <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-brand-50 text-brand-700 font-medium border border-brand-200">
              {label ?? SEARCH_GROUPS[group].label}
            </span>
            {destination && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-brand-50 text-brand-700 font-medium border border-brand-200">
                {destination}
                <button onClick={onClearDestination} aria-label={`Bỏ lọc ${destination}`}><X className="w-3 h-3" /></button>
              </span>
            )}
            {minStarRating !== undefined && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-amber-50 text-amber-700 font-medium border border-amber-200">
                {minStarRating}★+
                <button onClick={() => setStar(undefined)} aria-label="Bỏ lọc hạng sao"><X className="w-3 h-3" /></button>
              </span>
            )}
            {maxPrice !== undefined && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-amber-50 text-amber-700 font-medium border border-amber-200">
                ≤ {new Intl.NumberFormat('vi-VN').format(maxPrice)} ₫
                <button onClick={clearPrice} aria-label="Bỏ lọc giá"><X className="w-3 h-3" /></button>
              </span>
            )}
            {/* Số trên tab là số chưa áp sao/giá; khi đang lọc thì danh sách ghi số theo bộ lọc. */}
            {hasFilters && loaded && !error && (
              <span className="text-slate-500 font-medium">· {loaded.total} kết quả theo bộ lọc</span>
            )}
          </div>
          <div className="self-end sm:self-auto">
            <SortMenu<SortOption> value={sort} onChange={setSort} />
          </div>
        </div>
        {body}
      </div>
    </div>
  );
};
