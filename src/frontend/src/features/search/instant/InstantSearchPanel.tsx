'use client';

import React from 'react';
import { Building2, Flag, History, MapPin, Plane, Sparkles, Ticket, TrendingUp, type LucideIcon } from 'lucide-react';
import type { Taxonomy } from '../../../types/travel';
import { highlightParts } from './highlight';
import type { InstantOption, InstantSearchPanelState } from './useInstantSearchBox';

// Cùng bộ icon và nhãn với `components/common/TaxonomyBadge.tsx`.
const TAXONOMY: Record<Taxonomy, { label: string; icon: LucideIcon }> = {
  hotel: { label: 'Khách sạn', icon: Building2 },
  flight: { label: 'Vé máy bay', icon: Plane },
  attraction: { label: 'Vé tham quan', icon: Ticket },
  golf: { label: 'Sân golf', icon: Flag },
  combo: { label: 'Combo', icon: Sparkles },
};

function describe(option: InstantOption): { icon: LucideIcon; kindLabel: string | null } {
  if (option.kind !== 'suggestion') return { icon: option.kind === 'recent' ? History : TrendingUp, kindLabel: null };
  const { suggestion } = option;
  if (suggestion.type === 'destination') return { icon: MapPin, kindLabel: 'Địa điểm' };
  const taxonomy = TAXONOMY[suggestion.taxonomy as Taxonomy];
  const kind = taxonomy?.label ?? 'Dịch vụ';
  return { icon: taxonomy?.icon ?? Sparkles, kindLabel: suggestion.destination ? `${kind} · ${suggestion.destination}` : kind };
}

const GROUP_TITLE = 'text-[11px] font-bold uppercase tracking-wider text-slate-400';

interface InstantSearchPanelProps extends InstantSearchPanelState {
  className?: string;
}

/**
 * Panel dưới ô tìm kiếm (FR-SRC-05). Ô trống: "Tìm kiếm gần đây" và "Từ khoá phổ biến". Đang gõ: gợi ý theo loại,
 * mỗi dòng có icon, phần khớp in đậm, tên loại; cuối panel là nút sang trang kết quả đầy đủ.
 * Bấm chuột trong panel không làm ô nhập mất focus (chặn `mousedown`), nên bàn phím vẫn dùng tiếp được.
 */
export function InstantSearchPanel({
  listId, query, typing, status, options, activeIndex, optionId, onPick, onSeeAll, onClearRecent, className = '',
}: InstantSearchPanelProps) {
  const row = (option: InstantOption, index: number) => {
    const { icon: Icon, kindLabel } = describe(option);
    const selected = index === activeIndex;
    return (
      <button
        key={`${option.kind}-${index}-${option.label}`}
        id={optionId(index)}
        type="button"
        role="option"
        aria-selected={selected}
        tabIndex={-1}
        onClick={() => onPick(option)}
        className={`flex w-full cursor-pointer items-center gap-3 rounded-xl px-2.5 py-2 text-left transition-colors ${
          selected ? 'bg-blue-50' : 'hover:bg-slate-50'
        }`}
      >
        <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl ${selected ? 'bg-white text-blue-600' : 'bg-slate-100 text-slate-500'}`}>
          <Icon className="h-[18px] w-[18px]" aria-hidden="true" />
        </span>
        <span className="flex min-w-0 flex-col">
          <span className="truncate text-[15px] text-slate-900">
            {option.kind === 'suggestion'
              ? highlightParts(option.label, query).map((part, i) => (part.match ? <strong key={i} className="font-bold">{part.text}</strong> : <React.Fragment key={i}>{part.text}</React.Fragment>))
              : option.label}
          </span>
          {kindLabel && <span className="truncate text-xs text-slate-500">{kindLabel}</span>}
        </span>
      </button>
    );
  };

  const recentCount = options.filter((option) => option.kind === 'recent').length;

  return (
    <div
      onMouseDown={(event) => event.preventDefault()}
      className={`absolute inset-x-0 top-full z-30 mt-2 rounded-3xl border border-slate-200 bg-white/95 p-2.5 text-left shadow-2xl backdrop-blur-md ${className}`}
    >
      <div id={listId} role="listbox" aria-label="Gợi ý tìm kiếm" aria-busy={typing && status === 'loading'}>
        {!typing ? (
          <>
            {recentCount > 0 && (
              <div role="group" aria-label="Tìm kiếm gần đây">
                <div className="flex items-center justify-between px-2.5 pb-1 pt-1.5">
                  <p className={GROUP_TITLE}>Tìm kiếm gần đây</p>
                  <button
                    type="button"
                    tabIndex={-1}
                    onClick={onClearRecent}
                    className="cursor-pointer rounded-md px-1.5 py-0.5 text-xs font-semibold text-slate-500 transition hover:bg-slate-100 hover:text-blue-700"
                  >
                    Xóa
                  </button>
                </div>
                {options.slice(0, recentCount).map((option, i) => row(option, i))}
              </div>
            )}
            <div role="group" aria-label="Từ khoá phổ biến">
              <p className={`${GROUP_TITLE} px-2.5 pb-1 pt-1.5`}>Từ khoá phổ biến</p>
              {options.slice(recentCount).map((option, i) => row(option, recentCount + i))}
            </div>
          </>
        ) : status === 'loading' ? (
          <div aria-hidden="true" data-testid="instant-search-loading">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="flex items-center gap-3 px-2.5 py-2">
                <span className="skeleton-wave h-9 w-9 shrink-0 rounded-xl" />
                <span className="skeleton-wave h-3.5 w-3/5 rounded-full" />
              </div>
            ))}
          </div>
        ) : status === 'error' ? (
          <p className="px-2.5 py-3 text-sm text-slate-500">Chưa tải được gợi ý. Bạn vẫn có thể nhấn Enter để tìm.</p>
        ) : options.length === 0 ? (
          <p className="px-2.5 py-3 text-sm text-slate-500">
            Không có gợi ý trùng với &ldquo;{query}&rdquo;. Nhấn Enter để tìm theo nghĩa của cả câu.
          </p>
        ) : (
          options.map((option, i) => row(option, i))
        )}
      </div>

      {typing && (
        <button
          type="button"
          tabIndex={-1}
          onClick={onSeeAll}
          className="mt-2 w-full cursor-pointer truncate rounded-2xl bg-slate-100 px-3 py-3 text-center text-[15px] font-medium text-slate-800 transition-colors hover:bg-blue-50 hover:text-blue-700"
        >
          Xem tất cả kết quả cho &ldquo;{query}&rdquo;
        </button>
      )}
    </div>
  );
}
