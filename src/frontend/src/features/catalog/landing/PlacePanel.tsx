'use client';

import React from 'react';
import { History, MapPin } from 'lucide-react';
import type { PlaceOptions } from './recentPlaces';

interface PlacePanelProps extends PlaceOptions {
  /** `id` của danh sách, nối với `aria-controls` của ô nhập. */
  listId: string;
  /** Tên danh sách cho trình đọc màn hình, ví dụ "Gợi ý điểm đi". */
  listLabel: string;
  /** Tiêu đề nhóm gợi ý, ví dụ "Điểm đi phổ biến". */
  title: string;
  /** Chữ đang gõ, dùng cho câu "không trùng". */
  text: string;
  loading: boolean;
  error: boolean;
  /** Vị trí của lựa chọn đang tô sáng trong dãy `recent` rồi `popular`; -1 là chưa có. */
  activeOption: number;
  /** Câu khi tải gợi ý lỗi. */
  errorHint: string;
  onPick: (name: string) => void;
  onClearRecent: () => void;
}

const CHIP = 'inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-full border px-3.5 text-sm font-semibold transition';

/**
 * Nội dung dropdown của ô địa điểm: "Tìm gần đây" (khi ô trống) rồi nhóm gợi ý theo chữ đã gõ.
 * Thứ tự lựa chọn để điều khiển bằng phím là `recent` nối `popular`; cha giữ `activeOption` theo thứ tự đó.
 */
export function PlacePanel({ listId, listLabel, title, text, recent, popular, loading, error, activeOption, errorHint, onPick, onClearRecent }: PlacePanelProps) {
  const chip = (name: string, index: number, icon: React.ReactNode) => (
    <button
      key={`${index < recent.length ? 'recent' : 'popular'}-${name}`}
      type="button"
      role="option"
      aria-selected={index === activeOption}
      onClick={() => onPick(name)}
      className={`${CHIP} ${
        index === activeOption ? 'border-blue-400 bg-blue-50 text-blue-700' : 'border-slate-200 bg-slate-50 text-slate-700 hover:border-blue-300 hover:text-blue-700'
      }`}
    >
      {icon}
      {name}
    </button>
  );

  const noneYet = !loading && popular.length === 0 && recent.length === 0;

  return (
    <div id={listId} role="listbox" aria-label={listLabel} className="flex flex-col gap-4">
      {recent.length > 0 && (
        <div role="group" aria-label="Tìm gần đây">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Tìm gần đây</p>
            <button
              type="button"
              onClick={onClearRecent}
              className="cursor-pointer rounded-md px-1.5 py-0.5 text-xs font-semibold text-slate-500 transition hover:bg-slate-100 hover:text-blue-700"
            >
              Xóa
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {recent.map((name, i) => chip(name, i, <History className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />))}
          </div>
        </div>
      )}

      <div role="group" aria-label={title}>
        <p className="mb-2 text-[11px] font-bold uppercase tracking-wider text-slate-400">{title}</p>
        {loading ? (
          <div className="flex flex-wrap gap-2" aria-busy="true">
            {[0, 1, 2, 3].map((i) => <span key={i} aria-hidden="true" className="skeleton-wave h-9 w-24 rounded-full" />)}
          </div>
        ) : error && popular.length === 0 ? (
          <p className="text-xs text-slate-500">{errorHint}</p>
        ) : noneYet ? (
          <p className="text-xs text-slate-500">Không có địa điểm trùng. Bạn vẫn có thể tìm theo &ldquo;{text}&rdquo;.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {popular.map((name, i) => chip(name, recent.length + i, <MapPin className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />))}
          </div>
        )}
      </div>
    </div>
  );
}
