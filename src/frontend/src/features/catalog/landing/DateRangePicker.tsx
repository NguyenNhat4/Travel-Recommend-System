'use client';

import React, { useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { addDaysIso } from '../../search/tripContext';

interface DateRangePickerProps {
  /** range: chọn ngày đi rồi ngày về. single: chỉ một ngày, chọn xong là đóng. */
  mode: 'range' | 'single';
  start: string;
  end: string | null;
  /** Ngày sớm nhất chọn được (YYYY-MM-DD), thường là hôm nay theo giờ Việt Nam. */
  min: string;
  startLabel: string;
  endLabel?: string;
  hint?: string;
  onChange: (start: string, end: string | null) => void;
  onDone: () => void;
}

const WEEKDAYS = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'];
const pad = (n: number) => String(n).padStart(2, '0');
const isoOf = (year: number, month: number, day: number) => `${year}-${pad(month + 1)}-${pad(day)}`;

/** dd/MM/yyyy */
export function formatDisplayDate(iso: string): string {
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}`;
}

function monthOf(iso: string) {
  return { year: Number(iso.slice(0, 4)), month: Number(iso.slice(5, 7)) - 1 };
}

/** Lưới một tháng, tuần bắt đầu từ thứ Hai. Tính bằng UTC để không lệch ngày theo múi giờ trình duyệt. */
function buildMonth(year: number, month: number) {
  const leading = (new Date(Date.UTC(year, month, 1)).getUTCDay() + 6) % 7;
  const days = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
  return { leading, days };
}

export function DateRangePicker({ mode, start, end, min, startLabel, endLabel, hint, onChange, onDone }: DateRangePickerProps) {
  const [view, setView] = useState(() => monthOf(start >= min ? start : min));
  const [selecting, setSelecting] = useState<'start' | 'end'>('start');
  const [hovered, setHovered] = useState<string | null>(null);
  const { leading, days } = buildMonth(view.year, view.month);
  const minMonth = monthOf(min);
  const canGoBack = view.year > minMonth.year || (view.year === minMonth.year && view.month > minMonth.month);

  const shiftMonth = (delta: number) => {
    setView((prev) => {
      const date = new Date(Date.UTC(prev.year, prev.month + delta, 1));
      return { year: date.getUTCFullYear(), month: date.getUTCMonth() };
    });
  };

  const pick = (day: string) => {
    if (mode === 'single') {
      onChange(day, null);
      onDone();
      return;
    }
    if (selecting === 'start') {
      onChange(day, end && end > day ? end : addDaysIso(day, 1));
      setSelecting('end');
      return;
    }
    if (day <= start) {
      onChange(day, addDaysIso(day, 1));
      return;
    }
    onChange(start, day);
    setSelecting('start');
    onDone();
  };

  const rangeEnd = mode === 'range' ? (selecting === 'end' && hovered && hovered > start ? hovered : end) : null;

  return (
    <div className="w-[min(calc(100vw-3rem),22rem)] space-y-3" role="dialog" aria-label="Chọn ngày">
      {mode === 'range' ? (
        <div className="flex items-center gap-1.5 rounded-xl bg-slate-100 p-1">
          {([['start', startLabel, start], ['end', endLabel ?? 'Ngày về', end]] as const).map(([which, label, value]) => (
            <button
              key={which}
              type="button"
              onClick={() => setSelecting(which)}
              aria-pressed={selecting === which}
              className={`flex-1 cursor-pointer rounded-lg px-2.5 py-1.5 text-left transition ${selecting === which ? 'bg-white text-blue-600 shadow-xs ring-1 ring-blue-500/20' : 'text-slate-600 hover:text-slate-900'}`}
            >
              <span className="block text-[10px] font-extrabold uppercase tracking-wider text-slate-400">{label}</span>
              <span className="block text-sm font-bold">{value ? formatDisplayDate(value) : '—'}</span>
            </button>
          ))}
        </div>
      ) : (
        <p className="text-sm font-bold text-slate-800">
          {startLabel}: <span className="text-blue-600">{formatDisplayDate(start)}</span>
        </p>
      )}

      <div className="flex items-center justify-between px-1">
        <button type="button" onClick={() => shiftMonth(-1)} disabled={!canGoBack} aria-label="Tháng trước" className="flex h-9 w-9 cursor-pointer items-center justify-center rounded-lg text-slate-600 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-30">
          <ChevronLeft className="h-4 w-4" aria-hidden="true" />
        </button>
        <span className="select-none text-sm font-bold text-slate-800" aria-live="polite">Tháng {view.month + 1}, {view.year}</span>
        <button type="button" onClick={() => shiftMonth(1)} aria-label="Tháng sau" className="flex h-9 w-9 cursor-pointer items-center justify-center rounded-lg text-slate-600 transition hover:bg-slate-100">
          <ChevronRight className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>

      <div className="grid grid-cols-7 border-b border-slate-100 py-1 text-center text-[11px] font-bold text-slate-400" aria-hidden="true">
        {WEEKDAYS.map((d) => <div key={d}>{d}</div>)}
      </div>

      <div className="grid grid-cols-7 gap-y-1 text-center" onMouseLeave={() => setHovered(null)}>
        {Array.from({ length: leading }).map((_, i) => <div key={`blank-${i}`} className="h-9" />)}
        {Array.from({ length: days }).map((_, i) => {
          const day = isoOf(view.year, view.month, i + 1);
          const disabled = day < min;
          const isStart = day === start;
          const isEnd = rangeEnd !== null && day === rangeEnd;
          const inRange = rangeEnd !== null && day > start && day < rangeEnd;
          return (
            <div key={day} className={`flex h-9 items-center justify-center ${inRange ? 'bg-blue-50' : ''} ${isStart && rangeEnd ? 'rounded-l-full bg-blue-50' : ''} ${isEnd ? 'rounded-r-full bg-blue-50' : ''}`}>
              <button
                type="button"
                disabled={disabled}
                onClick={() => pick(day)}
                onMouseEnter={() => setHovered(day)}
                aria-label={`${i + 1} tháng ${view.month + 1}, ${view.year}`}
                aria-pressed={isStart || isEnd}
                className={`flex h-9 w-9 cursor-pointer items-center justify-center rounded-full text-sm font-semibold transition disabled:cursor-not-allowed disabled:text-slate-300 ${
                  isStart || isEnd ? 'bg-blue-600 font-bold text-white' : inRange ? 'text-blue-700 hover:bg-blue-100' : 'text-slate-700 hover:bg-slate-100 disabled:hover:bg-transparent'
                }`}
              >
                {i + 1}
              </button>
            </div>
          );
        })}
      </div>

      {hint && <p className="border-t border-slate-100 pt-2 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}
