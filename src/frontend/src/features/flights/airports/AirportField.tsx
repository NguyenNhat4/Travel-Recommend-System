'use client';

import React, { useId, useState } from 'react';
import { History, MapPin } from 'lucide-react';
import type { FlightAirport } from '../../../services/flights';
import { LABEL, PILL, POPOVER, VALUE } from '../../catalog/landing/fieldStyles';
import { RECENT_TITLE, airportSections, flattenSections, matchAirport, type AirportSection } from './airportOptions';

interface AirportFieldProps {
  /** `id` của danh sách gợi ý, nối với `aria-controls` của ô. */
  listId: string;
  /** Tên danh sách cho trình đọc màn hình, ví dụ "Gợi ý điểm đi". */
  listLabel: string;
  label: string;
  placeholder: string;
  icon: React.ReactNode;
  inputRef?: React.Ref<HTMLInputElement>;
  /** Chữ trong ô: nhãn "Thành phố (MÃ)" khi đã chọn, hoặc chữ đang gõ. */
  value: string;
  /** Dropdown đang mở (điều khiển từ tấm tìm kiếm cha, để chỉ một ô mở cùng lúc). */
  open: boolean;
  /** Sân bay hiện hành đã tải; null khi chưa tải xong. */
  airports: readonly FlightAirport[] | null;
  loading: boolean;
  error: boolean;
  /** Thành phố tìm gần đây, đã lọc theo sân bay hiện hành ở ô cha. */
  recent: readonly string[];
  /** Sân bay đã chọn ở ô kia: không đề xuất cùng một sân bay. */
  exclude?: FlightAirport | null;
  onChange: (text: string) => void;
  onOpen: () => void;
  onClose: () => void;
  onPick: (airport: FlightAirport) => void;
  /** Rời ô: cha xoá chữ nếu chữ không khớp sân bay nào (spec §4.4). */
  onBlur: () => void;
  onClearRecent: () => void;
}

/**
 * Ô sân bay của `/flights`: chỉ nhận sân bay hiện hành của catalog. Dropdown không lấy focus khi bấm (mousedown bị chặn),
 * nên bấm một dòng không làm ô mất chữ trước khi chọn xong.
 */
export function AirportField({
  listId, listLabel, label, placeholder, icon, inputRef, value, open, airports, loading, error, recent, exclude,
  onChange, onOpen, onClose, onPick, onBlur, onClearRecent,
}: AirportFieldProps) {
  const [active, setActive] = useState(-1);
  // Chữ đã khớp một sân bay hiện hành thì gợi ý các mục mặc định, không lọc theo chính chữ đó.
  const query = matchAirport(value, airports) ? '' : value;
  const sections = airports ? airportSections({ text: query, airports, recent, exclude }) : [];
  const rows = flattenSections(sections);

  const pick = (airport: FlightAirport) => {
    setActive(-1);
    onPick(airport);
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      onOpen();
      setActive((i) => Math.min(i + 1, rows.length - 1));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActive((i) => Math.max(i - 1, -1));
    } else if (event.key === 'Enter' && open && active >= 0 && rows[active]) {
      event.preventDefault();
      pick(rows[active]);
    } else if (event.key === 'Escape' && open) {
      onClose();
    }
  };

  return (
    <div className="relative min-w-0 flex-1">
      <label className={PILL}>
        {icon}
        <span className="flex min-w-0 flex-1 flex-col">
          <span className={LABEL}>{label}</span>
          <input
            ref={inputRef}
            type="text"
            role="combobox"
            aria-expanded={open}
            aria-controls={listId}
            aria-autocomplete="list"
            aria-activedescendant={open && active >= 0 && rows[active] ? `${listId}-${active}` : undefined}
            value={value}
            onChange={(event) => {
              setActive(-1);
              onChange(event.target.value);
              onOpen();
            }}
            onFocus={() => {
              setActive(-1);
              onOpen();
            }}
            onBlur={() => {
              setActive(-1);
              onBlur();
            }}
            onKeyDown={onKeyDown}
            placeholder={placeholder}
            autoComplete="off"
            className={VALUE}
          />
        </span>
      </label>
      {open && (
        <div className={`${POPOVER} left-0 w-full min-w-80`} onMouseDown={(event) => event.preventDefault()}>
          <div id={listId} role="listbox" aria-label={listLabel} className="flex max-h-[360px] flex-col gap-4 overflow-y-auto pr-1">
            {airports === null ? (
              loading ? (
                <div className="flex flex-col gap-2" aria-busy="true">
                  {[0, 1, 2].map((i) => <span key={i} aria-hidden="true" className="skeleton-wave h-12 w-full rounded-xl" />)}
                </div>
              ) : (
                <p className="text-xs text-slate-500">{error ? 'Chưa tải được danh sách sân bay. Thử lại sau giây lát.' : 'Đang tải danh sách sân bay…'}</p>
              )
            ) : sections.length === 0 ? (
              <p className="text-xs text-slate-500">
                {query.trim()
                  ? <>Chưa có sân bay nào khớp &ldquo;{query.trim()}&rdquo;. Chọn một sân bay trong danh sách.</>
                  : 'Chưa có sân bay để chọn lúc này.'}
              </p>
            ) : (
              sections.map((section) => (
                <AirportGroup
                  key={section.title}
                  section={section}
                  listId={listId}
                  offset={rows.findIndex((row) => row === section.airports[0])}
                  active={active}
                  showClear={section.title === RECENT_TITLE}
                  onPick={pick}
                  onClearRecent={onClearRecent}
                />
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function AirportGroup({ section, listId, offset, active, showClear, onPick, onClearRecent }: {
  section: AirportSection;
  listId: string;
  /** Vị trí của dòng đầu tiên của nhóm trong dãy đã nối; dùng để tô sáng đúng dòng bằng phím. */
  offset: number;
  active: number;
  showClear: boolean;
  onPick: (airport: FlightAirport) => void;
  onClearRecent: () => void;
}) {
  const titleId = useId();
  return (
    <div role="group" aria-labelledby={titleId} className="flex flex-col gap-1">
      <div className="mb-1 flex items-center justify-between">
        <p id={titleId} className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{section.title}</p>
        {showClear && (
          <button
            type="button"
            onClick={onClearRecent}
            className="cursor-pointer rounded-md px-1.5 py-0.5 text-xs font-semibold text-slate-500 transition hover:bg-slate-100 hover:text-brand-700"
          >
            Xóa
          </button>
        )}
      </div>
      {section.airports.map((airport, index) => {
        const position = offset + index;
        const isActive = position === active;
        return (
          <button
            key={`${section.title}-${airport.code}`}
            id={`${listId}-${position}`}
            type="button"
            role="option"
            aria-selected={isActive}
            onClick={() => onPick(airport)}
            className={`flex w-full cursor-pointer items-center gap-3 rounded-xl border px-3 py-2 text-left transition ${
              isActive ? 'border-brand-400 bg-brand-50' : 'border-transparent hover:bg-slate-50'
            }`}
          >
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-slate-100 text-slate-500">
              {section.title === RECENT_TITLE
                ? <History className="h-4 w-4" aria-hidden="true" />
                : <MapPin className="h-4 w-4" aria-hidden="true" />}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-semibold text-slate-900">{airport.city}</span>
              <span className="block truncate text-xs text-slate-500">
                {airport.code}{airport.name ? ` - ${airport.name}` : ''}
              </span>
            </span>
          </button>
        );
      })}
    </div>
  );
}
