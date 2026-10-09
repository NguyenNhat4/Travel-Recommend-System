'use client';

import React, { useState } from 'react';
import { Check } from 'lucide-react';
import type { Product } from '../../types/travel';
import { amenityList } from './AmenityList';
import { amenityIcon } from './amenityIcons';

const fold = (text: string) => text.normalize('NFC').trim().toLowerCase();
const roomAmenities = (room: Product) => amenityList(room.attributes?.amenities).map(fold);

/** Nguồn đôi khi để diện tích ("20 m²") trong danh sách tiện ích: đã có ở thông số phòng, không đưa vào bộ lọc. */
const isAreaLabel = (label: string) => /^\d+([.,]\d+)?\s*m(2|²)$/i.test(label.trim());

export interface AmenityOption {
  label: string;
  count: number;
}

/** Tiện ích có ở ít nhất một hạng phòng, nhiều phòng nhất lên trước (cùng số thì theo thứ tự xuất hiện ở nguồn). */
export function amenityOptions(rooms: readonly Product[]): AmenityOption[] {
  const tally = new Map<string, AmenityOption>();
  for (const room of rooms) {
    const labels = amenityList(room.attributes?.amenities);
    for (const label of labels) {
      if (isAreaLabel(label)) continue;
      const key = fold(label);
      const entry = tally.get(key);
      if (entry) entry.count += 1;
      else tally.set(key, { label, count: 1 });
    }
  }
  return [...tally.values()].sort((a, b) => b.count - a.count);
}

/** Phòng có đủ mọi tiện ích đã chọn (không chọn gì thì mọi phòng đều hợp). */
export function matchesAmenities(room: Product, selected: readonly string[]): boolean {
  if (selected.length === 0) return true;
  const has = new Set(roomAmenities(room));
  return selected.every((label) => has.has(fold(label)));
}

interface RoomAmenityFilterProps {
  options: AmenityOption[];
  selected: string[];
  onChange: (next: string[]) => void;
  total: number;
  shown: number;
  /** Số chip hiện khi thu gọn. */
  limit?: number;
}

/**
 * Bộ lọc tiện ích của danh sách hạng phòng: chọn nhiều tiện ích, phòng phải có đủ mọi tiện ích đã chọn. Dữ liệu là
 * `attributes.amenities` của từng hạng phòng, lọc ngay trên trình duyệt (không gọi API).
 */
export const RoomAmenityFilter: React.FC<RoomAmenityFilterProps> = ({ options, selected, onChange, total, shown, limit = 10 }) => {
  const [expanded, setExpanded] = useState(false);
  if (options.length === 0) return null;
  const chosen = new Set(selected.map(fold));
  // Tiện ích đã chọn luôn hiện, kể cả khi nằm ngoài `limit` lúc thu gọn.
  const visible = expanded ? options : options.filter((o, i) => i < limit || chosen.has(fold(o.label)));
  const toggle = (label: string) => onChange(chosen.has(fold(label)) ? selected.filter((s) => fold(s) !== fold(label)) : [...selected, label]);

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 space-y-3" data-testid="room-amenity-filter">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-sm font-bold text-slate-900">Lọc theo tiện ích phòng</h4>
        <div className="flex items-center gap-3 text-xs">
          <span className="text-slate-600" role="status" aria-live="polite">
            {selected.length > 0 ? `${shown}/${total} hạng phòng phù hợp` : `${total} hạng phòng`}
          </span>
          {selected.length > 0 && (
            <button type="button" onClick={() => onChange([])}
              className="min-h-9 cursor-pointer font-semibold text-brand-700 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600">
              Xoá bộ lọc
            </button>
          )}
        </div>
      </div>
      <ul className="flex flex-wrap gap-2" aria-label="Tiện ích phòng để lọc">
        {visible.map((option) => {
          const on = chosen.has(fold(option.label));
          const Icon = amenityIcon(option.label);
          return (
            <li key={option.label}>
              <button type="button" aria-pressed={on} onClick={() => toggle(option.label)}
                className={`inline-flex min-h-9 cursor-pointer items-center gap-1.5 rounded-full border px-3 text-xs font-semibold transition-colors motion-reduce:transition-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600 ${
                  on ? 'border-brand-600 bg-brand-600 text-white' : 'border-slate-200 bg-white text-slate-700 hover:border-brand-300 hover:text-brand-700'}`}>
                {on ? <Check className="h-3.5 w-3.5" aria-hidden="true" /> : <Icon className="h-3.5 w-3.5 text-brand-700" aria-hidden="true" />}
                {option.label}
                <span className={on ? 'text-brand-100' : 'text-slate-400'}>{option.count}</span>
              </button>
            </li>
          );
        })}
      </ul>
      {options.length > limit && (
        <button type="button" onClick={() => setExpanded((v) => !v)} aria-expanded={expanded}
          className="min-h-9 cursor-pointer text-xs font-semibold text-brand-700 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600">
          {expanded ? 'Thu gọn' : `Xem tất cả (${options.length})`}
        </button>
      )}
    </div>
  );
};
