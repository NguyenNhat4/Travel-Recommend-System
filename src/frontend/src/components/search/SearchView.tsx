'use client';

import React, { useState, useMemo, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { useTravel } from '../../context/TravelContext';
import { DEFAULT_QUERY, EMPTY_SEARCH_RESPONSE, searchProductsApi, SortOption, SearchResponse } from '../../services/search';
import { ApiError } from '../../services/http';
import { Destination, Taxonomy } from '../../types/travel';
import { ProductCard } from '../common/ProductCard';
import { describeTripContext, parseTripContext, serializeTripContext } from '../../features/search/tripContext';
import { SearchBox } from '../common/SearchBox';
import { Search, Filter, Sparkles, HelpCircle, X, ArrowUpDown, ChevronDown, Loader2 } from 'lucide-react';

export const SearchView: React.FC = () => {
  const { navigate } = useTravel();
  const searchParams = useSearchParams();

  // Extract parameters from URL (?q=..., ?type=... / ?taxonomy=..., ?destination=...)
  const { queryParam, taxonomyParam, destinationParam } = useMemo(() => {
    const q = searchParams.get('q') || '';
    const rawType = searchParams.get('type') || searchParams.get('taxonomy');
    const validTaxonomies: Taxonomy[] = ['hotel', 'flight', 'attraction', 'combo', 'golf'];
    const taxonomy = validTaxonomies.includes(rawType as Taxonomy) ? (rawType as Taxonomy) : undefined;
    const dest = searchParams.get('destination') || searchParams.get('dest');
    return {
      queryParam: q,
      taxonomyParam: taxonomy,
      destinationParam: dest,
    };
  }, [searchParams]);

  // Ngữ cảnh chuyến đi từ tấm tìm kiếm ở trang danh mục: đi tiếp tới trang chi tiết để điền sẵn hộp đặt, không lọc kết quả.
  const tripQuery = useMemo(() => serializeTripContext(parseTripContext(searchParams)), [searchParams]);
  const tripSummary = useMemo(() => describeTripContext(parseTripContext(searchParams)), [searchParams]);
  const withTrip = (url: URL) => {
    new URLSearchParams(tripQuery).forEach((value, key) => url.searchParams.set(key, value));
    return url;
  };

  const [searchInput, setSearchInput] = useState(queryParam);
  const [selectedDestinations, setSelectedDestinations] = useState<Destination[]>(() => {
    return destinationParam ? [destinationParam as Destination] : [];
  });
  const [selectedTaxonomy, setSelectedTaxonomy] = useState<Taxonomy | undefined>(taxonomyParam);
  const [minStarRating, setMinStarRating] = useState<number | undefined>(undefined);
  const [maxPrice, setMaxPrice] = useState<number | undefined>(undefined);
  const [sortOption, setSortOption] = useState<SortOption>('relevance');
  const [showRelevanceInfo, setShowRelevanceInfo] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [searchError, setSearchError] = useState<ApiError | null>(null);
  const [retryToken, setRetryToken] = useState(0);
  const [searchResponse, setSearchResponse] = useState<SearchResponse>(EMPTY_SEARCH_RESPONSE);

  // Sync state whenever URL parameters change (e.g. from header or home submission)
  useEffect(() => {
    setSearchInput(queryParam);
    setSelectedTaxonomy(taxonomyParam);
    if (destinationParam) {
      setSelectedDestinations([destinationParam as Destination]);
    }
  }, [queryParam, taxonomyParam, destinationParam]);

  // Perform search by calling backend endpoint /search (via searchProductsApi)
  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setSearchError(null);

    searchProductsApi(
      queryParam,
      {
        destination: selectedDestinations.length > 0 ? selectedDestinations : undefined,
        taxonomy: selectedTaxonomy,
        minStarRating,
        maxPrice,
      },
      sortOption
    )
      .then((res) => {
        if (!cancelled) {
          setSearchResponse(res);
          setSearchError(null);
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          // Không thay bằng kết quả giả: hiện lỗi, giữ nguyên truy vấn để Thử lại (frontend §4.2).
          setSearchError(err instanceof ApiError ? err : new ApiError('Chưa tìm được lúc này. Vui lòng thử lại.', 'INTERNAL_ERROR', 0, true));
          setSearchResponse(EMPTY_SEARCH_RESPONSE);
          setIsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [queryParam, selectedDestinations, selectedTaxonomy, minStarRating, maxPrice, sortOption, retryToken]);

  const handleTabChange = (taxId: Taxonomy | undefined) => {
    setSelectedTaxonomy(taxId);
    const url = new URL('/search', window.location.origin);
    if (queryParam) url.searchParams.set('q', queryParam);
    if (destinationParam) url.searchParams.set('destination', destinationParam);
    if (taxId) {
      url.searchParams.set('type', taxId);
    } else {
      url.searchParams.delete('type');
      url.searchParams.delete('taxonomy');
    }
    withTrip(url);
    navigate(url.pathname + url.search);
  };

  const handleSearchSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const trimmed = searchInput.trim();
    try {
      const url = new URL(window.location.origin + '/search');
      if (trimmed) {
        url.searchParams.set('q', trimmed);
      }
      if (selectedTaxonomy) {
        url.searchParams.set('type', selectedTaxonomy);
      }
      withTrip(url);
      navigate(url.pathname + url.search);
    } catch {
      // fallback
    }
  };

  const toggleDestination = (dest: Destination) => {
    setSelectedDestinations(prev => 
      prev.includes(dest) ? prev.filter(d => d !== dest) : [...prev, dest]
    );
  };

  const clearAllFilters = () => {
    setSelectedDestinations([]);
    setSelectedTaxonomy(undefined);
    setMinStarRating(undefined);
    setMaxPrice(undefined);
    const url = new URL('/search', window.location.origin);
    if (queryParam) url.searchParams.set('q', queryParam);
    navigate(url.pathname + url.search);
  };

  const hasActiveFilters = selectedDestinations.length > 0 || selectedTaxonomy || minStarRating || maxPrice;

  // Compute readable heading based on search query or active category
  const headerTitle = useMemo(() => {
    const isDefaultQuery = Object.values(DEFAULT_QUERY).includes(queryParam.trim().toLowerCase());
    if (queryParam && !(isDefaultQuery && selectedTaxonomy)) {
      return `Kết quả cho “${queryParam}”`;
    }
    switch (selectedTaxonomy) {
      case 'hotel':
        return 'Khách sạn & Khu nghỉ dưỡng V-OTA';
      case 'flight':
        return 'Vé máy bay & Chặng bay phổ biến';
      case 'combo':
        return 'Gói Combo Du lịch Tiết Kiệm';
      case 'attraction':
        return 'Vé Vui chơi & Tham quan VinWonders';
      case 'golf':
        return 'Dịch vụ Sân Golf Nghỉ Dưỡng';
      default:
        return 'Tất cả dịch vụ du lịch';
    }
  }, [queryParam, selectedTaxonomy]);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Top Search Input Bar (Redesigned for Elder & Youth, Traditional Flow) */}
      <SearchBox
        value={searchInput}
        onChange={setSearchInput}
        onSearch={(query) => {
          const trimmed = query.trim();
          const url = new URL(window.location.origin + '/search');
          if (trimmed) {
            url.searchParams.set('q', trimmed);
          }
          if (selectedTaxonomy) {
            url.searchParams.set('type', selectedTaxonomy);
          }
          withTrip(url);
          navigate(url.pathname + url.search);
        }}
        placeholder="Nhập truy vấn tự do: nghỉ dưỡng 5 sao, vé vui chơi, vé máy bay..."
        variant="page"
        suggestions={[
          'Vinpearl Nha Trang',
          'VinWonders Phú Quốc',
          'Combo 3N2Đ tiết kiệm',
          'Villa ven biển',
          'Vé máy bay Hà Nội - Đà Nẵng'
        ]}
      />

      {/* Query Header & Category Tabs */}
      <div className="space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-2">
          <h1 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight">
            {headerTitle}
          </h1>
          {tripSummary && (
            <span className="text-xs font-semibold text-blue-700 bg-blue-50 border border-blue-100 rounded-full px-3 py-1" title="Ngày và số khách sẽ được điền sẵn khi bạn chọn dịch vụ">
              Chuyến đi: {tripSummary}
            </span>
          )}
          <span className="text-xs font-semibold text-slate-500 flex items-center gap-1.5">
            {isLoading && <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-600" />}
            <span>Tìm thấy {searchResponse.total}{searchResponse.totalExact === false ? '+' : ''} dịch vụ phù hợp</span>
          </span>
        </div>

        {/* Taxonomy Tabs */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none border-b border-slate-200">
          {[
            { id: undefined, label: `Tất cả (${searchResponse.categoryCounts.all || 0})` },
            { id: 'hotel' as Taxonomy, label: `Khách sạn (${searchResponse.categoryCounts.hotel || 0})` },
            { id: 'flight' as Taxonomy, label: `Vé máy bay (${searchResponse.categoryCounts.flight || 0})` },
            { id: 'attraction' as Taxonomy, label: `Vé tham quan (${searchResponse.categoryCounts.attraction || 0})` },
            { id: 'combo' as Taxonomy, label: `Combo (${searchResponse.categoryCounts.combo || 0})` },
            { id: 'golf' as Taxonomy, label: `Golf (${searchResponse.categoryCounts.golf || 0})` }
          ].map((tab, idx) => (
            <button
              key={idx}
              onClick={() => handleTabChange(tab.id)}
              className={`px-3 py-2 text-xs font-bold whitespace-nowrap border-b-2 transition-all ${selectedTaxonomy === tab.id ? 'border-blue-600 text-blue-600' : 'border-transparent text-slate-600 hover:text-slate-900'}`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main Grid: Filters Sidebar (1/4) + Results List (3/4) */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-start">
        {/* Sidebar Filters */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs space-y-6">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-slate-600" />
              <span className="text-sm font-bold text-slate-900">Bộ lọc tìm kiếm</span>
            </div>
            {hasActiveFilters && (
              <button
                onClick={clearAllFilters}
                className="text-xs text-rose-600 hover:underline font-medium"
              >
                Xóa tất cả
              </button>
            )}
          </div>

          {/* Destination Filter */}
          <div className="space-y-2.5">
            <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
              Điểm đến
            </h4>
            {(['Nha Trang', 'Phú Quốc', 'Đà Nẵng', 'Hội An', 'Hạ Long'] as Destination[]).map(dest => (
              <label key={dest} className="flex items-center gap-2.5 text-xs text-slate-700 cursor-pointer hover:text-slate-900">
                <input
                  type="checkbox"
                  checked={selectedDestinations.includes(dest)}
                  onChange={() => toggleDestination(dest)}
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 w-4 h-4"
                />
                <span>{dest}</span>
              </label>
            ))}
          </div>

          {/* Star Rating Filter */}
          <div className="space-y-2.5 pt-4 border-t border-slate-100">
            <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
              Hạng sao khách sạn
            </h4>
            <div className="space-y-1.5">
              {[
                { label: 'Tất cả hạng sao', val: undefined },
                { label: '5 sao (Luxury)', val: 5 },
                { label: '4 sao trở lên', val: 4 }
              ].map(opt => (
                <label key={opt.label} className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer">
                  <input
                    type="radio"
                    name="starRating"
                    checked={minStarRating === opt.val}
                    onChange={() => setMinStarRating(opt.val)}
                    className="text-blue-600 focus:ring-blue-500 w-3.5 h-3.5"
                  />
                  <span>{opt.label}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Price Range Filter */}
          <div className="space-y-2.5 pt-4 border-t border-slate-100">
            <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
              Mức giá tối đa
            </h4>
            <div className="space-y-2">
              <input
                type="range"
                min="500000"
                max="8000000"
                step="500000"
                value={maxPrice || 8000000}
                onChange={(e) => setMaxPrice(parseInt(e.target.value, 10))}
                className="w-full accent-blue-600"
              />
              <div className="flex justify-between text-xs text-slate-500 font-mono">
                <span>500k</span>
                <span className="font-bold text-blue-700">
                  {maxPrice ? new Intl.NumberFormat('vi-VN').format(maxPrice) + ' ₫' : 'Tất cả'}
                </span>
                <span>8tr+</span>
              </div>
            </div>
          </div>
        </div>

        {/* Results List Column */}
        <div className="lg:col-span-3 space-y-4">
          {/* Controls Bar: Active Filters Chips + Sort */}
          <div className="bg-white p-3.5 rounded-xl border border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
            {/* Active Filter Chips */}
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-slate-400 font-medium">Đang lọc:</span>
              {selectedDestinations.map(d => (
                <span key={d} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 font-medium border border-blue-200">
                  {d}
                  <button onClick={() => toggleDestination(d)}><X className="w-3 h-3" /></button>
                </span>
              ))}
              {selectedTaxonomy && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-indigo-50 text-indigo-700 font-medium border border-indigo-200">
                  {selectedTaxonomy === 'hotel' ? 'Khách sạn' : selectedTaxonomy === 'flight' ? 'Vé máy bay' : selectedTaxonomy === 'combo' ? 'Combo' : selectedTaxonomy === 'attraction' ? 'Vé tham quan' : 'Golf'}
                  <button onClick={() => handleTabChange(undefined)}><X className="w-3 h-3" /></button>
                </span>
              )}
              {minStarRating && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-amber-50 text-amber-700 font-medium border border-amber-200">
                  {minStarRating}★+
                  <button onClick={() => setMinStarRating(undefined)}><X className="w-3 h-3" /></button>
                </span>
              )}
              {!hasActiveFilters && (
                <span className="text-slate-500 italic">Mặc định</span>
              )}
            </div>

            {/* Sort Options with Relevance Info Tooltip */}
            <div className="flex items-center gap-2 self-end sm:self-auto relative">
              <span className="text-slate-500 font-medium">Sắp xếp:</span>
              <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-lg">
                <button
                  onClick={() => setSortOption('relevance')}
                  className={`px-2.5 py-1 rounded-md font-semibold transition-colors flex items-center gap-1 ${sortOption === 'relevance' ? 'bg-white text-blue-700 shadow-2xs' : 'text-slate-600 hover:text-slate-900'}`}
                >
                  <span>Phù hợp nhất</span>
                  <HelpCircle 
                    className="w-3.5 h-3.5 text-slate-400 hover:text-blue-600 cursor-pointer" 
                    onClick={(e) => {
                      e.stopPropagation();
                      setShowRelevanceInfo(!showRelevanceInfo);
                    }}
                  />
                </button>
                <button
                  onClick={() => setSortOption('price_asc')}
                  className={`px-2.5 py-1 rounded-md font-semibold transition-colors ${sortOption === 'price_asc' ? 'bg-white text-blue-700 shadow-2xs' : 'text-slate-600 hover:text-slate-900'}`}
                >
                  Giá thấp → cao
                </button>
                <button
                  onClick={() => setSortOption('price_desc')}
                  className={`px-2.5 py-1 rounded-md font-semibold transition-colors ${sortOption === 'price_desc' ? 'bg-white text-blue-700 shadow-2xs' : 'text-slate-600 hover:text-slate-900'}`}
                >
                  Giá cao → thấp
                </button>
              </div>

              {/* Relevance Info Popover (§4.2.3) */}
              {showRelevanceInfo && (
                <div className="absolute right-0 top-10 w-72 p-3.5 bg-slate-900 text-white rounded-xl shadow-xl z-30 border border-slate-700 text-xs space-y-1.5 animate-in fade-in duration-150">
                  <div className="font-bold text-amber-300">Cơ chế &ldquo;Phù hợp nhất&rdquo;</div>
                  <p className="text-slate-300 leading-relaxed text-[11px]">
                    Kết quả được xếp theo mức độ <strong>gần nghĩa ngữ nghĩa</strong> với câu bạn gõ, 
                    không chỉ trùng từ khóa đơn thuần. Bạn có thể thoải mái mô tả mong muốn chuyến đi bằng ngôn ngữ tự nhiên.
                  </p>
                  <div className="text-right">
                    <button 
                      onClick={() => setShowRelevanceInfo(false)}
                      className="text-[10px] text-blue-400 hover:underline"
                    >
                      Đã hiểu
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Weak Match Banner if applicable (§4.2.4) */}
          {searchResponse.isWeakMatch && (
            <div className="p-3 bg-amber-50 text-amber-900 border border-amber-200 rounded-xl text-xs flex items-center justify-between">
              <span>Chưa tìm thấy kết quả khớp tuyệt đối với &ldquo;{queryParam}&rdquo;. Đây là những lựa chọn gần nghĩa nhất.</span>
              <button 
                onClick={() => navigate('/assistant')}
                className="font-bold underline text-amber-950 ml-2 shrink-0"
              >
                Hỏi Trợ lý AI →
              </button>
            </div>
          )}

          {/* Results List */}
          {searchError ? (
            <div className="p-10 text-center bg-white rounded-2xl border border-slate-200 space-y-3">
              <h3 className="text-base font-bold text-slate-800">{searchError.message}</h3>
              {searchError.retryable && (
                <button
                  onClick={() => setRetryToken((n) => n + 1)}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs rounded-lg transition-colors"
                >
                  Thử lại
                </button>
              )}
            </div>
          ) : isLoading && searchResponse.results.length === 0 ? (
            <div className="space-y-4" aria-busy="true">
              {[0, 1, 2].map((i) => (
                <div key={i} className="h-36 rounded-xl bg-slate-100 animate-pulse" />
              ))}
            </div>
          ) : searchResponse.results.length > 0 ? (
            <div className="space-y-4">
              {searchResponse.results.map((item, index) => (
                <React.Fragment key={item.product.id}>
                  <ProductCard
                    product={item.product}
                    variant="row"
                    tripQuery={tripQuery}
                    score={item.relevanceScore}
                    rank={index + 1}
                  />

                  {/* Inline Assistant Banner inserted at 3rd item (§4.2.3) */}
                  {index === 2 && (
                    <div className="p-4 rounded-xl bg-gradient-to-r from-blue-900 to-indigo-900 text-white flex flex-col sm:flex-row items-center justify-between gap-3 shadow-sm my-2">
                      <div className="flex items-center gap-2.5">
                        <div className="p-2 rounded-lg bg-blue-500/30 text-indigo-300">
                          <Sparkles className="w-5 h-5" />
                        </div>
                        <div>
                          <h4 className="text-xs font-bold text-white">
                            Muốn ghép các dịch vụ này thành lịch trình trọn gói?
                          </h4>
                          <p className="text-[11px] text-slate-300">
                            Trợ lý AI sẽ tự động phân bổ khách sạn, vé tham quan và ăn uống theo ngày.
                          </p>
                        </div>
                      </div>
                      <button
                        onClick={() => navigate('/assistant')}
                        className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs rounded-lg shadow-xs transition-colors shrink-0 whitespace-nowrap"
                      >
                        Hỏi trợ lý với truy vấn này →
                      </button>
                    </div>
                  )}
                </React.Fragment>
              ))}
            </div>
          ) : (
            /* Empty State */
            <div className="p-12 text-center bg-white rounded-2xl border border-slate-200 space-y-4">
              <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mx-auto text-slate-400">
                <Search className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-800">
                  Chưa tìm thấy dịch vụ nào cho &ldquo;{queryParam}&rdquo;
                </h3>
                <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1">
                  Hãy thử thay đổi từ khóa, bỏ bớt bộ lọc hoặc nhờ Trợ lý AI gợi ý lịch trình.
                </p>
              </div>
              <div className="flex justify-center gap-3">
                <button
                  onClick={clearAllFilters}
                  className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs rounded-lg transition-colors"
                >
                  Xóa bộ lọc
                </button>
                <button
                  onClick={() => navigate('/assistant')}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs rounded-lg transition-colors"
                >
                  Nhờ Trợ lý AI gợi ý
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
