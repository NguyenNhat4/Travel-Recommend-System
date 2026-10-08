'use client';

import React, { useEffect, useId, useMemo, useRef, useState } from 'react';
import { Calendar, MapPin, PlaneTakeoff, Search, Users } from 'lucide-react';
import { useTravel } from '../../../context/TravelContext';
import { addDaysIso, todayVN, type TripContext } from '../../search/tripContext';
import { DateRangePicker, formatDisplayDate } from './DateRangePicker';
import { GuestsPopover, describeGuests, type GuestsValue } from './GuestsPopover';
import type { FlightSearchInput } from '../../flights/results/flightHref';
import { PlacePanel } from './PlacePanel';
import { RECENT_DESTINATIONS_KEY, RECENT_ORIGINS_KEY, buildPlaceOptions, useRecentPlaces } from './recentPlaces';
import { buildSearchHref, matchDestination } from './searchHref';
import { useDestinations } from './useDestinations';
import type { VerticalConfig, VerticalTab } from './verticals';

type Panel = 'origin' | 'location' | 'dates' | 'guests' | null;

interface LandingSearchSheetProps {
  config: VerticalConfig;
  tab: VerticalTab;
  /** Điểm đến đang lọc ở URL (`?destination=`), điền sẵn vào ô địa điểm. */
  initialDestination?: string;
  /** Chữ tự do của lần tìm đang xem (`?q=` không phải điểm đến chuẩn): điền sẵn ô địa điểm khi chưa có `initialDestination`. */
  initialText?: string;
  /** Lần tìm đang xem ở URL (`/flights?origin&destination…`, `/hotels?q…`): điền sẵn điểm đi, ngày, khứ hồi, số khách và số phòng. */
  initialSearch?: { origin: string; trip: TripContext };
  /** Vé máy bay: nhận giá trị tấm tìm kiếm và tìm ngay tại chỗ (trang `/flights`); không có thì điều hướng về trang danh mục kèm `?q=`. */
  onFlightSearch?: (input: FlightSearchInput) => void;
}

const PILL = 'flex h-[70px] w-full min-w-0 items-center gap-3 rounded-[22px] bg-white px-5 text-left transition hover:bg-white/90 focus-within:ring-2 focus-within:ring-blue-500/60 lg:px-6';
const LABEL = 'text-xs font-medium text-slate-500';
const VALUE = 'w-full min-w-0 truncate bg-transparent text-base font-semibold text-slate-900 outline-none placeholder:font-normal placeholder:text-slate-400';
const POPOVER = 'absolute top-full z-40 mt-2 rounded-3xl bg-white p-4 text-slate-800 shadow-2xl ring-1 ring-slate-900/5';

/**
 * Tấm tìm kiếm kính mờ ở hero trang danh mục. Gửi đi là điều hướng về chính trang danh mục kèm `?q=` và ngữ cảnh chuyến đi
 * (kết quả hiện ngay dưới, `LandingResults`): số khách lọc theo sức chứa, ngày lọc theo lịch và cửa sổ mở bán (Backend, contract
 * 1.19.0); cả hai cũng điền sẵn hộp đặt ở trang chi tiết.
 * Ngoại lệ: vé máy bay ở `/flights` gọi `onFlightSearch` và tìm ngay tại chỗ (features/flights/FlightsPage).
 * Vé máy bay: ô Điểm đi và Điểm đến cùng gợi ý theo chữ gõ và nhớ vài lần tìm gần nhất ở trình duyệt (`recentPlaces.ts`).
 */
export function LandingSearchSheet({ config, tab, initialDestination, initialText, initialSearch, onFlightSearch }: LandingSearchSheetProps) {
  const { navigate } = useTravel();
  const { sheet } = config;
  const tomorrow = addDaysIso(todayVN(), 1);
  const originListId = useId();
  const listId = useId();
  const formRef = useRef<HTMLFormElement>(null);
  const locationInputRef = useRef<HTMLInputElement>(null);

  const seed = initialSearch?.trip;
  const [origin, setOrigin] = useState(initialSearch?.origin ?? '');
  const [location, setLocation] = useState(initialDestination ?? initialText ?? '');
  const [destination, setDestination] = useState<string | null>(initialDestination ?? null);
  const [checkIn, setCheckIn] = useState(seed?.checkIn ?? tomorrow);
  const [checkOut, setCheckOut] = useState<string | null>(
    sheet.dates.mode === 'range' ? seed?.checkOut ?? addDaysIso(seed?.checkIn ?? tomorrow, 1)
      : sheet.dates.mode === 'single-or-return' ? seed?.checkOut ?? null : null,
  );
  const [roundTrip, setRoundTrip] = useState(sheet.dates.mode === 'single-or-return' && Boolean(seed?.checkOut));
  const [guests, setGuests] = useState<GuestsValue>({ adults: seed?.adults ?? 2, children: seed?.children ?? 0, rooms: seed?.rooms ?? 1 });
  const [panel, setPanel] = useState<Panel>(null);
  const [activeOption, setActiveOption] = useState(-1);

  const keepHistory = tab.taxonomy === 'flight';
  const recentOrigins = useRecentPlaces(RECENT_ORIGINS_KEY, keepHistory);
  const recentDestinations = useRecentPlaces(RECENT_DESTINATIONS_KEY, keepHistory);

  const destinations = useDestinations(panel === 'location' || panel === 'origin');
  const originOptions = useMemo(
    () => buildPlaceOptions({ text: origin, recent: recentOrigins.items, destinations: destinations.data, exclude: destination ?? undefined }),
    [origin, recentOrigins.items, destinations.data, destination],
  );
  const locationOptions = useMemo(
    () => buildPlaceOptions({ text: location, recent: recentDestinations.items, destinations: destinations.data, exclude: sheet.origin ? origin : undefined }),
    [location, recentDestinations.items, destinations.data, sheet.origin, origin],
  );
  const originList = [...originOptions.recent, ...originOptions.popular];
  const locationList = [...locationOptions.recent, ...locationOptions.popular];

  // Đổi `?destination=` hay `?q=` trên cùng trang thì ô địa điểm theo URL.
  useEffect(() => {
    setLocation(initialDestination ?? initialText ?? '');
    setDestination(initialDestination ?? null);
  }, [initialDestination, initialText]);

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

  // Chọn điểm đi xong thì sang ô điểm đến, để gõ liền một mạch.
  const chooseOrigin = (name: string) => {
    setOrigin(name);
    setActiveOption(-1);
    setPanel('location');
    locationInputRef.current?.focus();
  };

  /** Mũi tên và Enter trên danh sách gợi ý của một ô; Enter khi chưa tô sáng mục nào thì để form gửi đi. */
  const navigateOptions = (e: React.KeyboardEvent, name: Exclude<Panel, null>, list: string[], pick: (name: string) => void) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setPanel(name);
      setActiveOption((i) => Math.min(i + 1, list.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveOption((i) => Math.max(i - 1, -1));
    } else if (e.key === 'Enter' && panel === name && activeOption >= 0 && list[activeOption]) {
      e.preventDefault();
      pick(list[activeOption]);
    }
  };

  const setTripKind = (round: boolean) => {
    setRoundTrip(round);
    setCheckOut(round ? addDaysIso(checkIn, 2) : null);
  };

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    setPanel(null);
    const resolved = destination ?? matchDestination(location, destinations.data);
    const trip = {
      checkIn,
      checkOut: dateMode === 'range' ? checkOut ?? undefined : undefined,
      adults: guests.adults,
      children: guests.children,
      rooms: sheet.rooms ? guests.rooms : undefined,
    };
    if (keepHistory && origin.trim() && resolved) {
      recentOrigins.remember(matchDestination(origin, destinations.data) ?? origin);
      recentDestinations.remember(resolved);
    }
    // Vé máy bay ở `/flights`: kết quả hiện ngay dưới tấm này, kể cả khi còn thiếu điểm đi hay điểm đến (trang nhắc người dùng nhập).
    if (tab.taxonomy === 'flight' && onFlightSearch) {
      onFlightSearch({ origin, location, destination: resolved, trip: { checkIn: trip.checkIn, checkOut: trip.checkOut, adults: trip.adults, children: trip.children } });
      return;
    }
    navigate(buildSearchHref({ taxonomy: tab.taxonomy, origin, location, destination: resolved, trip }));
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
                  role="combobox"
                  aria-expanded={panel === 'origin'}
                  aria-controls={originListId}
                  aria-autocomplete="list"
                  value={origin}
                  onChange={(e) => {
                    setOrigin(e.target.value);
                    setActiveOption(-1);
                    setPanel('origin');
                  }}
                  onFocus={() => {
                    setActiveOption(-1);
                    setPanel('origin');
                  }}
                  onKeyDown={(e) => navigateOptions(e, 'origin', originList, chooseOrigin)}
                  placeholder={sheet.origin.placeholder}
                  autoComplete="off"
                  className={VALUE}
                />
              </span>
            </label>
            {panel === 'origin' && (
              <div className={`${POPOVER} left-0 w-full min-w-64`}>
                <PlacePanel
                  listId={originListId}
                  listLabel="Gợi ý điểm đi"
                  title="Điểm đi phổ biến"
                  text={origin}
                  {...originOptions}
                  loading={destinations.loading}
                  error={Boolean(destinations.error)}
                  activeOption={activeOption}
                  errorHint="Chưa tải được gợi ý điểm đi. Bạn vẫn có thể gõ tên nơi khởi hành."
                  onPick={chooseOrigin}
                  onClearRecent={recentOrigins.clear}
                />
              </div>
            )}
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
                onFocus={() => {
                  setActiveOption(-1);
                  setPanel('location');
                }}
                onKeyDown={(e) => navigateOptions(e, 'location', locationList, chooseDestination)}
                placeholder={sheet.location.placeholder}
                autoComplete="off"
                className={VALUE}
                ref={locationInputRef}
              />
            </span>
          </label>
          {panel === 'location' && (
            <div className={`${POPOVER} left-0 w-full min-w-64`}>
              <PlacePanel
                listId={listId}
                listLabel="Gợi ý điểm đến"
                title="Điểm đến phổ biến"
                text={location}
                {...locationOptions}
                loading={destinations.loading}
                error={Boolean(destinations.error)}
                activeOption={activeOption}
                errorHint="Chưa tải được gợi ý điểm đến. Bạn vẫn có thể gõ tên điểm đến."
                onPick={chooseDestination}
                onClearRecent={recentDestinations.clear}
              />
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
