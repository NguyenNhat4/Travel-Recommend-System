'use client';

import React from 'react';
import { Minus, Plus } from 'lucide-react';
import { MAX_PARTY_SIZE } from '../../search/tripContext';

export interface GuestsValue {
  adults: number;
  children: number;
  rooms: number;
}

interface GuestsPopoverProps {
  value: GuestsValue;
  onChange: (value: GuestsValue) => void;
  showRooms: boolean;
}

/** Văn bản ở ô "Số lượng": "1 phòng, 2 người lớn, 1 trẻ em". */
export function describeGuests(value: GuestsValue, showRooms: boolean): string {
  const parts: string[] = [];
  if (showRooms) parts.push(`${value.rooms} phòng`);
  parts.push(`${value.adults} người lớn`);
  if (value.children > 0) parts.push(`${value.children} trẻ em`);
  return parts.join(', ');
}

function Stepper({ label, hint, value, min, max, onChange }: {
  label: string; hint: string; value: number; min: number; max: number; onChange: (next: number) => void;
}) {
  const button = 'flex h-11 w-11 cursor-pointer items-center justify-center rounded-full border border-slate-200 bg-white text-slate-600 shadow-xs transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40';
  return (
    <div className="flex items-center justify-between rounded-2xl border border-slate-100 bg-slate-50/80 p-3">
      <div>
        <div className="text-sm font-bold text-slate-900">{label}</div>
        <div className="text-xs text-slate-500">{hint}</div>
      </div>
      <div className="flex items-center gap-3" role="group" aria-label={label}>
        <button type="button" className={button} onClick={() => onChange(value - 1)} disabled={value <= min} aria-label={`Giảm ${label.toLowerCase()}`}>
          <Minus className="h-4 w-4" aria-hidden="true" />
        </button>
        <span className="w-6 text-center text-sm font-bold text-slate-800" aria-live="polite">{value}</span>
        <button type="button" className={button} onClick={() => onChange(value + 1)} disabled={value >= max} aria-label={`Tăng ${label.toLowerCase()}`}>
          <Plus className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}

/**
 * Bộ đếm phòng, người lớn, trẻ em theo luật đoàn của checkout (FR-BKG-08): tối đa 9 người mỗi lần đặt, ít nhất
 * một người lớn, mỗi phòng ít nhất một người lớn. Backend vẫn là nơi quyết định cuối.
 */
export function GuestsPopover({ value, onChange, showRooms }: GuestsPopoverProps) {
  const { adults, children, rooms } = value;
  return (
    <div className="w-[min(calc(100vw-3rem),20rem)] space-y-3" role="dialog" aria-label="Số lượng khách">
      {showRooms && (
        <Stepper
          label="Phòng"
          hint="Mỗi phòng có ít nhất 1 người lớn"
          value={rooms}
          min={1}
          max={Math.min(adults, MAX_PARTY_SIZE)}
          onChange={(next) => onChange({ ...value, rooms: next })}
        />
      )}
      <Stepper
        label="Người lớn"
        hint="Từ 12 tuổi trở lên"
        value={adults}
        min={1}
        max={MAX_PARTY_SIZE - children}
        onChange={(next) => onChange({ ...value, adults: next, rooms: Math.min(rooms, next) })}
      />
      <Stepper
        label="Trẻ em"
        hint="Dưới 12 tuổi"
        value={children}
        min={0}
        max={MAX_PARTY_SIZE - adults}
        onChange={(next) => onChange({ ...value, children: next })}
      />
      <p className="text-xs text-slate-500">Tối đa {MAX_PARTY_SIZE} khách mỗi lần đặt.</p>
    </div>
  );
}
