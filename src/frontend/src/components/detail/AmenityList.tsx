'use client';

import React, { useMemo, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { amenityIcon } from './amenityIcons';

const fold = (text: string) => text.normalize('NFC').trim().toLowerCase();

/** Danh sách tiện ích từ dữ liệu: chỉ lấy chuỗi, bỏ rỗng và trùng (không phân biệt hoa thường), giữ thứ tự của nguồn. */
export function amenityList(raw: unknown): string[] {
  if (!Array.isArray(raw)) return [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const item of raw) {
    if (typeof item !== 'string' || !item.trim()) continue;
    const key = fold(item);
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(item.trim());
  }
  return out;
}

interface AmenityListProps {
  items: string[];
  /** Số tiện ích hiện khi thu gọn. */
  limit?: number;
  /** Nhãn cho đọc màn hình, ví dụ "Tiện ích khách sạn". */
  label: string;
  compact?: boolean;
  /** Hai cột trên màn hình rộng (danh sách dài). */
  columns?: boolean;
}

/** Chip tiện ích: thu gọn còn `limit` mục, nút "Xem tất cả (N)" mở hết, "Thu gọn" đóng lại. */
export const AmenityList: React.FC<AmenityListProps> = ({ items, limit = 12, label, compact, columns }) => {
  const [expanded, setExpanded] = useState(false);
  const visible = useMemo(() => (expanded ? items : items.slice(0, limit)), [items, expanded, limit]);
  if (items.length === 0) return null;
  const hidden = items.length - limit;
  return (
    <div>
      <ul aria-label={label}
        className={`${columns ? 'grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2' : 'flex flex-wrap gap-x-5 gap-y-2'} ${compact ? 'text-xs' : 'text-sm'} text-slate-700`}>
        {visible.map((item) => {
          const Icon = amenityIcon(item);
          return (
            <li key={item} className="flex min-w-0 items-center gap-2">
              <Icon className={`${compact ? 'h-4 w-4' : 'h-[18px] w-[18px]'} shrink-0 text-blue-700`} aria-hidden="true" />
              <span className="min-w-0">{item}</span>
            </li>
          );
        })}
      </ul>
      {hidden > 0 && (
        <button type="button" onClick={() => setExpanded((v) => !v)} aria-expanded={expanded}
          className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-blue-700 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600">
          {expanded ? 'Thu gọn' : `Xem tất cả (${items.length})`}
          <ChevronDown className={`h-3.5 w-3.5 transition-transform motion-reduce:transition-none ${expanded ? 'rotate-180' : ''}`} aria-hidden="true" />
        </button>
      )}
    </div>
  );
};
