'use client';

import React, { useEffect, useRef } from 'react';
import { HScroller } from '../../../components/search/HScroller';
import type { DaySummary } from './flightModel';
import { shortDate, thousands, weekdayLong } from './flightFormat';

interface FlightDateStripProps {
  days: DaySummary[];
  selected: string | null;
  onSelect: (date: string) => void;
}

/**
 * Dải ngày có chuyến kèm giá thấp nhất mỗi ngày ("Từ 1.493k"). Chỉ có ngày còn chuyến: dữ liệu catalog thưa nên ngày trống
 * không có gì để chọn và không được hiện như đã có giá.
 */
export const FlightDateStrip: React.FC<FlightDateStripProps> = ({ days, selected, onSelect }) => {
  const rootRef = useRef<HTMLDivElement>(null);

  // Đưa ngày đang chọn vào giữa hàng (mở trang ở ngày gần nhất có thể nằm ngoài vùng nhìn).
  useEffect(() => {
    const button = rootRef.current?.querySelector<HTMLElement>('[aria-pressed="true"]');
    button?.scrollIntoView?.({ inline: 'center', block: 'nearest' });
  }, [selected, days.length]);

  return (
    <div ref={rootRef} className="rounded-[20px] border border-slate-100 bg-white px-3 py-4 shadow-[0_8px_40px_rgba(15,28,58,0.05)] sm:px-5">
      <HScroller count={days.length} label="Ngày bay và giá thấp nhất trong ngày">
        {days.map((day) => {
          const active = day.date === selected;
          return (
            <button key={day.date} type="button" aria-pressed={active} onClick={() => onSelect(day.date)}
              aria-label={`${weekdayLong(day.date)}, ${shortDate(day.date)}, ${day.count} chuyến, giá từ ${new Intl.NumberFormat('vi-VN').format(day.minPrice)} đồng`}
              className={`flex min-w-[74px] shrink-0 cursor-pointer snap-start flex-col gap-1.5 rounded-[13px] border-2 bg-white pb-2 transition-colors ${
                active ? 'border-brand-600' : 'border-slate-200 hover:border-brand-300'}`}>
              <span className={`-mx-0.5 -mt-0.5 flex flex-col items-center rounded-xl px-3 py-2 ${
                active ? 'bg-gradient-to-br from-brand-600 to-brand-800 text-white' : 'bg-slate-100 text-slate-900'}`}>
                <span className="text-base font-semibold tabular-nums">{shortDate(day.date)}</span>
                <span className={`whitespace-nowrap text-xs ${active ? 'text-white/90' : 'text-slate-500'}`}>{weekdayLong(day.date)}</span>
              </span>
              <span className="text-center text-xs tabular-nums text-brand-700">Từ {thousands(day.minPrice)}</span>
            </button>
          );
        })}
      </HScroller>
    </div>
  );
};
