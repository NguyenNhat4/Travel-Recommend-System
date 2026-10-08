'use client';

import React, { useId, useState } from 'react';
import { ChevronDown, Moon, MoonStar, RotateCcw, Sun, Sunrise, Sunset } from 'lucide-react';
import { TIME_SLOTS, countFacets, type FlightFilters as Filters, type SlotId, type StopKind } from './flightModel';
import { AirlineBadge } from './AirlineBadge';

const SLOT_ICONS: Record<SlotId, typeof Sun> = { morning: Sunrise, noon: Sun, afternoon: Sunset, evening: Moon, late: MoonStar };

function toggled<T>(set: ReadonlySet<T>, value: T): Set<T> {
  const next = new Set(set);
  if (!next.delete(value)) next.add(value);
  return next;
}

interface FlightFiltersProps {
  /** Danh sách chưa lọc của ngày đang xem: từ đó tính số chuyến theo từng giá trị. */
  facets: ReturnType<typeof countFacets>;
  /** Hãng của ngày đang xem, kèm mã và tên. */
  airlines: Array<{ name: string; code: string }>;
  filters: Filters;
  onChange: (next: Filters) => void;
  onReset: () => void;
  activeCount: number;
  className?: string;
}

const SECTION = 'border-b border-slate-200 py-[18px] last:border-b-0 last:pb-0';
const HEADING = 'mb-3.5 font-display text-base text-slate-900';

/**
 * Bộ lọc của trang kết quả vé máy bay: khung giờ theo buổi, hãng, điểm dừng. Giá trị không có chuyến nào ở ngày đang xem thì
 * mờ và không bấm được. Dưới `md` cả khối gập lại sau nút mũi tên để danh sách chuyến lên trước.
 */
export const FlightFilters: React.FC<FlightFiltersProps> = ({ facets, airlines, filters, onChange, onReset, activeCount, className = '' }) => {
  const [open, setOpen] = useState(false);
  const bodyId = useId();

  const stopChips: Array<{ kind: StopKind; label: string; count: number }> = [
    { kind: 'nonstop', label: 'Bay thẳng', count: facets.nonstop },
    { kind: 'connecting', label: 'Có điểm dừng', count: facets.connecting },
  ];

  return (
    <aside aria-label="Bộ lọc chuyến bay" className={`rounded-[20px] border border-slate-100 bg-white px-5 pb-6 pt-2.5 shadow-[0_8px_40px_rgba(15,28,58,0.05)] ${className}`}>
      <div className="flex items-center gap-2 border-b border-slate-200 py-2 pb-3.5 md:border-b">
        <h2 className="mr-auto font-display text-xl text-slate-900">Bộ lọc{activeCount > 0 && <span className="ml-2 align-middle text-sm text-brand-600">({activeCount})</span>}</h2>
        <button type="button" onClick={onReset} disabled={activeCount === 0}
          className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg px-1.5 py-1 text-[15px] font-medium text-brand-700 hover:bg-brand-50 disabled:cursor-default disabled:text-slate-400 disabled:hover:bg-transparent">
          <RotateCcw className="h-4 w-4" aria-hidden="true" />Đặt lại
        </button>
        <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open} aria-controls={bodyId} aria-label="Mở hoặc đóng bộ lọc"
          className="grid h-8 w-8 cursor-pointer place-items-center rounded-full border border-slate-200 text-slate-600 md:hidden">
          <ChevronDown className={`h-[18px] w-[18px] transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden="true" />
        </button>
      </div>

      <div id={bodyId} className={`${open ? 'block' : 'hidden'} md:block`}>
        <section className={SECTION}>
          <h3 className={HEADING}>Thời gian khởi hành</h3>
          <div className="grid grid-cols-2 gap-2">
            {TIME_SLOTS.map((slot) => {
              const count = facets.slots.get(slot.id) ?? 0;
              const pressed = filters.slots.has(slot.id);
              const Icon = SLOT_ICONS[slot.id];
              return (
                <button key={slot.id} type="button" aria-pressed={pressed} disabled={count === 0}
                  onClick={() => onChange({ ...filters, slots: toggled(filters.slots, slot.id) })}
                  className={`flex cursor-pointer flex-col gap-0.5 rounded-[14px] border px-2.5 py-2.5 text-left transition-colors last:col-span-2 disabled:cursor-not-allowed disabled:text-slate-400 ${
                    pressed ? 'border-brand-600 bg-brand-50 text-brand-700' : 'border-slate-200 bg-white text-slate-900 enabled:hover:border-brand-300'}`}>
                  <span className="flex items-center gap-1.5">
                    <Icon className={`h-5 w-5 ${pressed ? 'text-brand-600' : 'text-slate-500'} ${count === 0 ? 'opacity-50' : ''}`} aria-hidden="true" />
                    <b className="text-sm font-semibold">{slot.label}</b>
                    <em className="ml-auto text-xs font-normal not-italic text-slate-500 tabular-nums" aria-label={`${count} chuyến`}>{count}</em>
                  </span>
                  <span className="whitespace-nowrap text-xs tabular-nums text-slate-500">{slot.hours}</span>
                </button>
              );
            })}
          </div>
        </section>

        <section className={SECTION}>
          <h3 className={HEADING}>Hãng hàng không</h3>
          <div className="flex flex-col gap-3.5">
            {airlines.map((airline) => {
              const count = facets.airlines.get(airline.name) ?? 0;
              return (
                <label key={airline.name} className={`flex items-center justify-between gap-3 ${count === 0 ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}`}>
                  <span className="flex min-w-0 items-center gap-2.5 text-sm text-slate-800">
                    <AirlineBadge name={airline.name} code={airline.code} />
                    <span className="truncate">{airline.name}</span>
                    <span className="text-xs text-slate-500 tabular-nums">({count})</span>
                  </span>
                  <input type="checkbox" disabled={count === 0} checked={!filters.hiddenAirlines.has(airline.name)}
                    onChange={() => onChange({ ...filters, hiddenAirlines: toggled(filters.hiddenAirlines, airline.name) })}
                    className="h-[22px] w-[22px] shrink-0 cursor-[inherit] accent-brand-600" />
                </label>
              );
            })}
          </div>
        </section>

        <section className={SECTION}>
          <h3 className={HEADING}>Điểm dừng</h3>
          <div className="grid grid-cols-2 gap-2">
            {stopChips.map((chip) => {
              const pressed = filters.stops.has(chip.kind);
              return (
                <button key={chip.kind} type="button" aria-pressed={pressed} disabled={chip.count === 0}
                  onClick={() => onChange({ ...filters, stops: toggled(filters.stops, chip.kind) })}
                  className={`h-9 cursor-pointer truncate rounded-full border px-2 text-[13px] transition-colors disabled:cursor-not-allowed disabled:text-slate-400 ${
                    pressed ? 'border-brand-600 bg-brand-50 font-semibold text-brand-700' : 'border-slate-200 bg-white text-slate-800 enabled:hover:border-brand-300'}`}>
                  {chip.label}
                </button>
              );
            })}
          </div>
        </section>
      </div>
    </aside>
  );
};
