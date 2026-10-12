'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { useTravel } from '../../context/TravelContext';
import { useAssistant } from '../../context/AssistantProvider';
import {
  DEFAULT_QUERY, SEARCH_GROUPS, TAB_GROUPS, parseGroupParam, searchCacheKey, searchOverviewApi,
  type SearchGroup, type TabGroup,
} from '../../services/search';
import { loadSection, useLazySection } from '../../hooks/useLazySection';
import { parseTripContext, serializeTripContext } from '../../features/search/tripContext';
import { SearchBox } from '../common/SearchBox';
import { Search, Loader2 } from 'lucide-react';
import { GroupResults } from './GroupResults';
import { GroupShelf } from './GroupShelf';
import { SearchAssistantBanner } from './SearchAssistantBanner';

const GROUP_TITLES: Record<SearchGroup | 'all', string> = {
  all: 'Tất cả dịch vụ du lịch',
  stay: 'Khách sạn & Khu nghỉ dưỡng V-OTA',
  exp: 'Tour và trải nghiệm',
  more: 'Gói Combo Du lịch Tiết Kiệm',
  flight: 'Vé máy bay & Chặng bay phổ biến',
};

export const SearchView: React.FC = () => {
  const { navigate } = useTravel();
  const { openFloatingWidget } = useAssistant();
  const searchParams = useSearchParams();

  // URL: ?q=..., ?type=stay|exp|more (hoặc taxonomy cũ hotel|attraction|golf|combo), ?destination=...
  // `type=flight` chỉ có khi mở từ /flights: một danh sách phẳng, không có tab. Không `type` là tab "Tất cả".
  const queryParam = searchParams.get('q') || '';
  const group = parseGroupParam(searchParams.get('type') || searchParams.get('taxonomy'));
  const destination = searchParams.get('destination') || searchParams.get('dest');
  const isFlightMode = group === 'flight';

  // Ô nhập giữ giá trị đang gõ; URL đổi (từ header, trang chủ) thì đồng bộ lại.
  const [searchInput, setSearchInput] = useState(queryParam);
  useEffect(() => setSearchInput(queryParam), [queryParam]);

  // Ngữ cảnh chuyến đi từ tấm tìm kiếm ở trang danh mục: chỉ đi tiếp tới trang chi tiết để điền sẵn hộp đặt; /search không hiển thị và không lọc theo nó.
  const tripQuery = useMemo(() => serializeTripContext(parseTripContext(searchParams)), [searchParams]);

  const buildUrl = (opts: { type?: SearchGroup; query?: string; destination?: string | null }) => {
    const url = new URL('/search', window.location.origin);
    const q = opts.query ?? queryParam;
    if (q) url.searchParams.set('q', q);
    const dest = opts.destination === undefined ? destination : opts.destination;
    if (dest) url.searchParams.set('destination', dest);
    if (opts.type) url.searchParams.set('type', opts.type);
    new URLSearchParams(tripQuery).forEach((value, key) => url.searchParams.set(key, value));
    return url.pathname + url.search;
  };

  // Số kết quả của các tab = `total` của chính các request hàng ở "Tất cả" (cùng khóa bộ đệm, nên hàng không gọi lại),
  // để tab, hàng và "Xem thêm" cùng một số. Không dùng ở chế độ vé máy bay (không có tab).
  const overview = useLazySection(
    searchCacheKey('overview', queryParam, destination),
    () => searchOverviewApi(queryParam, destination, loadSection),
    { enabled: !isFlightMode },
  );
  const counts = overview.data?.counts;

  const headerTitle = useMemo(() => {
    const isDefaultQuery = Object.values(DEFAULT_QUERY).includes(queryParam.trim().toLowerCase());
    if (queryParam && !(isDefaultQuery && group)) return `Kết quả cho “${queryParam}”`;
    return GROUP_TITLES[group ?? 'all'];
  }, [queryParam, group]);

  const goTab = (next: SearchGroup | undefined) => navigate(buildUrl({ type: next }));
  const clearDestination = () => navigate(buildUrl({ type: group, destination: null }));
  const askAssistant = () => openFloatingWidget(queryParam || undefined);

  const noResults = !isFlightMode && !group && overview.data !== null && overview.data.total === 0;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <SearchBox
        value={searchInput}
        onChange={setSearchInput}
        onSearch={(query) => navigate(buildUrl({ query: query.trim(), type: group }))}
        placeholder="Nhập truy vấn tự do: nghỉ dưỡng 5 sao, vé vui chơi, sân golf..."
        variant="page"
        suggestions={['Vinpearl Nha Trang', 'VinWonders Phú Quốc', 'Combo 3N2Đ tiết kiệm', 'Villa ven biển', 'Sân golf nghỉ dưỡng']}
      />

      <div className="space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-2">
          <h1 className="text-xl sm:text-2xl font-black text-slate-900">{headerTitle}</h1>
          {!isFlightMode && (
            <span className="text-xs font-semibold text-slate-500 flex items-center gap-1.5">
              {overview.loading && <Loader2 className="w-3.5 h-3.5 animate-spin text-brand-600" />}
              {overview.data && (
                <span>Tìm thấy {overview.data.total} dịch vụ phù hợp</span>
              )}
            </span>
          )}
        </div>

        {!isFlightMode && (
          <div role="tablist" aria-label="Nhóm dịch vụ" className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none border-b border-slate-200">
            {([undefined, ...TAB_GROUPS] as Array<TabGroup | undefined>).map((tab) => {
              const label = tab ? SEARCH_GROUPS[tab].label : 'Tất cả';
              const count = tab ? counts?.[tab] : overview.data?.total;
              const selected = group === tab;
              return (
                <button
                  key={tab ?? 'all'}
                  role="tab"
                  aria-selected={selected}
                  onClick={() => goTab(tab)}
                  className={`px-3 py-2 text-xs font-bold whitespace-nowrap border-b-2 transition-all ${selected ? 'border-brand-600 text-brand-600' : 'border-transparent text-slate-600 hover:text-slate-900'}`}
                >
                  {label}{count !== undefined ? ` (${count})` : ''}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {overview.data?.isWeakMatch && (
        <div className="p-3 bg-amber-50 text-amber-900 border border-amber-200 rounded-xl text-xs flex items-center justify-between">
          <span>Chưa tìm thấy kết quả khớp tuyệt đối với &ldquo;{queryParam}&rdquo;. Đây là những lựa chọn gần nghĩa nhất.</span>
          <button onClick={askAssistant} className="font-bold underline text-amber-950 ml-2 shrink-0">Hỏi Trợ lý AI →</button>
        </div>
      )}

      {group ? (
        <GroupResults
          key={`${group}|${queryParam}|${destination ?? ''}`}
          group={group}
          query={queryParam}
          destination={destination}
          tripQuery={tripQuery}
          onClearDestination={clearDestination}
          onAskAssistant={askAssistant}
        />
      ) : noResults ? (
        <div className="p-12 text-center bg-white rounded-2xl border border-slate-200 space-y-4">
          <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mx-auto text-slate-400">
            <Search className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-800">Chưa tìm thấy dịch vụ nào cho &ldquo;{queryParam}&rdquo;</h3>
            <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1">Hãy thử thay đổi từ khóa hoặc nhờ Trợ lý AI gợi ý lịch trình.</p>
          </div>
          <button onClick={askAssistant} className="px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white font-bold text-xs rounded-lg transition-colors">
            Nhờ Trợ lý AI gợi ý
          </button>
        </div>
      ) : (
        <div className="space-y-8">
          {destination && (
            <div className="flex items-center gap-1.5 text-xs">
              <span className="text-slate-400 font-medium">Đang lọc:</span>
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-brand-50 text-brand-700 font-medium border border-brand-200">
                {destination}
                <button onClick={clearDestination} aria-label={`Bỏ lọc ${destination}`}>×</button>
              </span>
            </div>
          )}
          {TAB_GROUPS.map((tab) => (
            <GroupShelf
              key={`${tab}|${queryParam}|${destination ?? ''}`}
              group={tab}
              query={queryParam}
              destination={destination}
              tripQuery={tripQuery}
              onSeeAll={goTab}
            />
          ))}
          <SearchAssistantBanner query={queryParam} />
        </div>
      )}
    </div>
  );
};
