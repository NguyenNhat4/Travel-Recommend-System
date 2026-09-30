'use client';

import React, { useEffect, useId, useMemo, useRef, useState } from 'react';
import { Calendar, MapPin, PlaneTakeoff, Search, Users } from 'lucide-react';
import { useTravel } from '../../../context/TravelContext';
import { addDaysIso, todayVN } from '../../search/tripContext';
import { DateRangePicker, formatDisplayDate } from './DateRangePicker';
import { GuestsPopover, describeGuests, type GuestsValue } from './GuestsPopover';
import { buildSearchHref, filterDestinations, matchDestination } from './searchHref';
import { topDestinations, useDestinations } from './useDestinations';
import type { VerticalConfig, VerticalTab } from './verticals';

type Panel = 'location' | 'dates' | 'guests' | null;

interface LandingSearchSheetProps {
  config: VerticalConfig;
  tab: VerticalTab;
  /** Điểm đến đang lọc ở URL (`?destination=`), điền sẵn vào ô địa điểm. */
  initialDestination?: string;
}

const PILL = 'flex h-[70px] w-full min-w-0 items-center gap-3 rounded-[22px] bg-white px-5 text-left transition hover:bg-white/90 focus-within:ring-2 focus-within:ring-blue-500/60 lg:px-6';
const LABEL = 'text-xs font-medium text-slate-500';
const VALUE = 'w-full min-w-0 truncate bg-transparent text-base font-semibold text-slate-900 outline-none placeholder:font-normal placeholder:text-slate-400';
const POPOVER = 'absolute top-full z-40 mt-2 rounded-3xl bg-white p-4 text-slate-800 shadow-2xl ring-1 ring-slate-900/5';

/**
 * Tấm tìm kiếm kính mờ ở hero trang danh mục. Gửi đi là điều hướng sang `/search` kèm ngữ cảnh chuyến đi:
 * ngày và số khách điền sẵn hộp đặt ở trang chi tiết, không lọc phòng trống (Backend chưa lọc theo ngày).
 */
export function LandingSearchSheet({ config, tab, initialDestination }: LandingSearchSheetProps) {
  const { navigate } = useTravel();
  const { sheet } = config;
  const tomorrow = addDaysIso(todayVN(), 1);
  const listId = useId();
  const formRef = useRef<HTMLFormElement>(null);

  const [origin, setOrigin] = useState('');
  const [location, setLocation] = useState(initialDestination ?? '');
  const [destination, setDestination] = useState<string | null>(initialDestination ?? null);
  const [checkIn, setCheckIn] = useState(tomorrow);
  const [checkOut, setCheckOut] = useState<string | null>(sheet.dates.mode === 'range' ? addDaysIso(tomorrow, 1) : null);
  const [roundTrip, setRoundTrip] = useState(false);
  const [guests, setGuests] = useState<GuestsValue>({ adults: 2, children: 0, rooms: 1 });
  const [panel, setPanel] = useState<Panel>(null);
  const [activeOption, setActiveOption] = useState(-1);

  const destinations = useDestinations(panel === 'location');
  const suggestions = useMemo(
    () => filterDestinations(location, topDestinations(destinations.data, 50)),
    [location, destinations.data],
  );

  // Đổi `?destination=` trên cùng trang thì ô địa điểm theo URL.
  useEffect(() => {
    setLocation(initialDestination ?? '');
    setDestination(initialDestination ?? null);
  }, [initialDestination]);

  useEffect(() => {
    if (!panel) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!formRef.current?.contains(event.target as Node)) setPanel(null);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setPanel(null);
    };
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [panel]);

  const dateMode: 'range' | 'single' = sheet.dates.mode === 'range' || (sheet.dates.mode === 'single-or-return' && roundTrip) ? 'range' : 'single';

  const chooseDestination = (name: string) => {
    setLocation(name);
    setDestination(name);
    setActiveOption(-1);
    setPanel('dates');
  };

  const setTripKind = (round: boolean) => {
    setRoundTrip(round);
    setCheckOut(round ? addDaysIso(checkIn, 2) : null);
  };

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    setPanel(null);
    navigate(buildSearchHref({
      taxonomy: tab.taxonomy,
      origin,
      location,
      destination: destination ?? matchDestination(location, destinations.data),
      trip: {
        checkIn,
        checkOut: dateMode === 'range' ? checkOut ?? undefined : undefined,
        adults: guests.adults,
        children: guests.children,
        rooms: sheet.rooms ? guests.rooms : undefined,
      },
    }));
  };

  const togglePanel = (next: Exclude<Panel, null>) => setPanel((prev) => (prev === next ? null : next));

  return (
    <form
      ref={formRef}
      onSubmit={submit}
      aria-label={`Tìm ${tab.noun}`}
      className="glass-sheet w-full rounded-[28px] p-2.5 sm:rounded-[38px]"
    >
      <div className="flex flex-col gap-2 rounded-[24px] bg-[#d6dadf]/60 p-2 sm:rounded-[32px] lg:flex-row lg:items-stretch lg:p-3">
        {sheet.origin && (
          <div className="relative min-w-0 flex-1">
            <label className={PILL}>
              <PlaneTakeoff className="h-5 w-5 shrink-0 text-slate-400" aria-hidden="true" />
              <span className="flex min-w-0 flex-1 flex-col">
                <span className={LABEL}>{sheet.origin.label}</span>
                <input
                  type="text"
                  value={origin}
                  onChange={(e) => setOrigin(e.target.value)}
                  placeholder={sheet.origin.placeholder}
                  autoComplete="off"
                  className={VALUE}
                />
              </span>
            </label>
          </div>
        )}

        <div className="relative min-w-0 flex-1">
          <label className={PILL}>
            <MapPin className="h-5 w-5 shrink-0 text-slate-400" aria-hidden="true" />
            <span className="flex min-w-0 flex-1 flex-col">
              <span className={LABEL}>{sheet.location.label}</span>
              <input
                type="text"
                role="combobox"
                aria-expanded={panel === 'location'}
                aria-controls={listId}
                aria-autocomplete="list"
                value={location}
                onChange={(e) => {
                  setLocation(e.target.value);
                  setDestination(matchDestination(e.target.value, destinations.data));
                  setActiveOption(-1);
                  setPanel('location');
                }}
                onFocus={() => setPanel('location')}
                onKeyDown={(e) => {
                  if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    setPanel('location');
                    setActiveOption((i) => Math.min(i + 1, suggestions.length - 1));
                  } else if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    setActiveOption((i) => Math.max(i - 1, -1));
                  } else if (e.key === 'Enter' && panel === 'location' && activeOption >= 0 && suggestions[activeOption]) {
                    e.preventDefault();
                    chooseDestination(suggestions[activeOption].destination);
                  }
                }}
                placeholder={sheet.location.placeholder}
                autoComplete="off"
                className={VALUE}
              />
            </span>
          </label>
          {panel === 'location' && (
            <div className={`${POPOVER} left-0 w-full min-w-64`}>
              <p className="mb-2 text-[11px] font-bold uppercase tracking-wider text-slate-400">Điểm đến phổ biến</p>
              {destinations.loading ? (
                <div className="flex flex-wrap gap-2" aria-busy="true">
                  {[0, 1, 2, 3].map((i) => <span key={i} aria-hidden="true" className="skeleton-wave h-9 w-24 rounded-full" />)}
                </div>
              ) : destinations.error ? (
                <p className="text-xs text-slate-500">Chưa tải được gợi ý điểm đến. Bạn vẫn có thể gõ tên điểm đến.</p>
              ) : suggestions.length === 0 ? (
                <p className="text-xs text-slate-500">Không có điểm đến trùng. Bạn vẫn có thể tìm theo &ldquo;{location}&rdquo;.</p>
              ) : (
                <div id={listId} role="listbox" aria-label="Gợi ý điểm đến" className="flex flex-wrap gap-2">
                  {suggestions.map((d, index) => (
                    <button
                      key={d.destination}
                      type="button"
                      role="option"
                      aria-selected={index === activeOption}
                      onClick={() => chooseDestination(d.destination)}
                      className={`inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-full border px-3.5 text-sm font-semibold transition ${
                        index === activeOption ? 'border-blue-400 bg-blue-50 text-blue-700' : 'border-slate-200 bg-slate-50 text-slate-700 hover:border-blue-300 hover:text-blue-700'
                      }`}
                    >
                      <MapPin className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
                      {d.destination}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="relative min-w-0 flex-1">
          <button
            type="button"
            aria-haspopup="dialog"
            aria-expanded={panel === 'dates'}
            onClick={() => togglePanel('dates')}
            className={`${PILL} cursor-pointer`}
          >
            <Calendar className="h-5 w-5 shrink-0 text-slate-400" aria-hidden="true" />
            <span className="flex min-w-0 flex-1 items-center gap-4">
              <span className="flex min-w-0 flex-1 flex-col">
                <span className={LABEL}>{sheet.dates.startLabel}</span>
                <span className="truncate text-base font-semibold text-slate-900">{formatDisplayDate(checkIn)}</span>
              </span>
              {dateMode === 'range' && (
                <>
                  <span className="h-9 w-px shrink-0 bg-slate-200" aria-hidden="true" />
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className={LABEL}>{sheet.dates.endLabel ?? 'Ngày về'}</span>
                    <span className="truncate text-base font-semibold text-slate-900">{checkOut ? formatDisplayDate(checkOut) : '—'}</span>
                  </span>
                </>
              )}
            </span>
          </button>
          {panel === 'dates' && (
            <div className={`${POPOVER} left-0`}>
              {sheet.dates.mode === 'single-or-return' && (
                <div role="radiogroup" aria-label="Loại hành trình" className="mb-3 inline-flex rounded-full bg-slate-100 p-1">
                  {([['Một chiều', false], ['Khứ hồi', true]] as const).map(([label, round]) => (
                    <button
                      key={label}
                      type="button"
                      role="radio"
                      aria-checked={roundTrip === round}
                      onClick={() => setTripKind(round)}
                      className={`h-9 cursor-pointer rounded-full px-4 text-sm font-semibold transition ${roundTrip === round ? 'bg-white text-blue-600 shadow-xs' : 'text-slate-600'}`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              )}
              <DateRangePicker
                mode={dateMode}
                start={checkIn}
                end={checkOut}
                min={todayVN()}
                startLabel={sheet.dates.startLabel}
                endLabel={sheet.dates.endLabel}
                hint="Ngày còn chỗ được kiểm ở bước chọn dịch vụ."
                onChange={(start, end) => {
                  setCheckIn(start);
                  setCheckOut(end);
                }}
                onDone={() => setPanel(null)}
              />
            </div>
          )}
        </div>

        <div className="relative min-w-0 flex-1">
          <button
            type="button"
            aria-haspopup="dialog"
            aria-expanded={panel === 'guests'}
            onClick={() => togglePanel('guests')}
            className={`${PILL} cursor-pointer`}
          >
            <Users className="h-5 w-5 shrink-0 text-slate-400" aria-hidden="true" />
            <span className="flex min-w-0 flex-1 flex-col">
              <span className={LABEL}>{sheet.guestsLabel}</span>
              <span className="truncate text-base font-semibold text-slate-900">{describeGuests(guests, sheet.rooms)}</span>
            </span>
          </button>
          {panel === 'guests' && (
            <div className={`${POPOVER} right-0`}>
              <GuestsPopover value={guests} onChange={setGuests} showRooms={sheet.rooms} />
            </div>
          )}
        </div>

        <button
          type="submit"
          aria-label="Tìm kiếm"
          className="flex h-[70px] w-full shrink-0 cursor-pointer items-center justify-center gap-2 rounded-full bg-gradient-to-r from-blue-600 to-indigo-600 px-4 text-white shadow-lg transition hover:scale-[1.03] active:scale-95 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 lg:w-[120px]"
        >
          <Search className="h-6 w-6" aria-hidden="true" />
          <span className="text-sm font-bold lg:sr-only">Tìm kiếm</span>
        </button>
      </div>
    </form>
  );
}
