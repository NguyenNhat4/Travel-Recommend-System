'use client';

import React, { useEffect, useId, useMemo, useRef, useState } from 'react';
import { Calendar, MapPin, PlaneTakeoff, Search, Users } from 'lucide-react';
import { useTravel } from '../../../context/TravelContext';
import { addDaysIso, serializeTripContext, todayVN, type TripContext } from '../../search/tripContext';
import { DateRangePicker, formatDisplayDate } from './DateRangePicker';
import { GuestsPopover, describeGuests, type GuestsValue } from './GuestsPopover';
import type { FlightSearchInput } from '../../flights/results/flightHref';
import type { FlightAirport } from '../../../services/flights';
import { AirportField } from '../../flights/airports/AirportField';
import { airportLabel, matchAirport } from '../../flights/airports/airportOptions';
import { useFlightAirports } from '../../flights/airports/useFlightAirports';
import { FamousHotelsPanel, famousHotelOptions, type FamousHotel } from './FamousHotelsPanel';
import { useFamousHotels } from './useFamousHotels';
import { LABEL, PILL, POPOVER, VALUE } from './fieldStyles';
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

/**
 * Tấm tìm kiếm kính mờ ở hero trang danh mục. Gửi đi là điều hướng về chính trang danh mục kèm `?q=` và ngữ cảnh chuyến đi
 * (kết quả hiện ngay dưới, `LandingResults`): số khách lọc theo sức chứa, ngày lọc theo lịch và cửa sổ mở bán (Backend, contract
 * 1.19.0); cả hai cũng điền sẵn hộp đặt ở trang chi tiết.
 * Ngoại lệ: vé máy bay ở `/flights` gọi `onFlightSearch` và tìm ngay tại chỗ (features/flights/FlightsPage).
 * Vé máy bay: ô Điểm đi và Điểm đến chỉ nhận sân bay hiện hành của catalog (`features/flights/airports`); chữ không khớp
 * thì ô tự xoá khi rời ô. Ô Địa điểm của `/hotels` và `/combos` hiện khách sạn nổi tiếng khi bấm; `/experiences` hiện điểm đến phổ biến.
 * Spec: docs/spec/ui-dia-diem-san-bay-va-khach-san-noi-tieng.md.
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

  const airportMode = sheet.location.suggest === 'airports';
  const famousMode = sheet.location.suggest === 'famous-hotels';
  const keepHistory = tab.taxonomy === 'flight';
  const recentOrigins = useRecentPlaces(RECENT_ORIGINS_KEY, keepHistory);
  const recentDestinations = useRecentPlaces(RECENT_DESTINATIONS_KEY, keepHistory);

  // Sân bay hiện hành (vé máy bay): chữ đang nhập khớp sân bay nào thì đó là sân bay đã chọn; không khớp thì null.
  const airports = useFlightAirports(airportMode);
  const originAirport = airportMode ? matchAirport(origin, airports.data) : null;
  const destinationMatch = airportMode ? matchAirport(location, airports.data) : null;
  // Cùng một sân bay không thể vừa là điểm đi vừa là điểm đến.
  const destinationAirport = destinationMatch && destinationMatch.code !== originAirport?.code ? destinationMatch : null;

  const destinations = useDestinations(!airportMode && panel === 'location');
  const famousHotels = useFamousHotels(famousMode && panel === 'location');
  const famous = famousMode
    ? famousHotelOptions(location, famousHotels.data ?? [], destinations.data ?? [])
    : null;
  const locationOptions = useMemo(
    () => buildPlaceOptions({ text: location, recent: recentDestinations.items, destinations: destinations.data, exclude: sheet.origin ? origin : undefined }),
    [location, recentDestinations.items, destinations.data, sheet.origin, origin],
  );
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

  const currentTrip = (): TripContext => ({
    checkIn,
    checkOut: dateMode === 'range' ? checkOut ?? undefined : undefined,
    adults: guests.adults,
    children: guests.children,
    rooms: sheet.rooms ? guests.rooms : undefined,
  });

  const chooseDestination = (name: string) => {
    setLocation(name);
    setDestination(name);
    setActiveOption(-1);
    setPanel('dates');
  };

  /** Mở một khách sạn nổi tiếng: sang trang chi tiết, kèm ngày và số khách đang chọn (như thẻ sản phẩm). */
  const openHotel = (hotel: FamousHotel) => {
    setPanel(null);
    const tripQuery = serializeTripContext(currentTrip());
    navigate(`/product/${encodeURIComponent(hotel.id)}${tripQuery ? `?${tripQuery}` : ''}`);
  };

  /** Chọn sân bay đi xong thì sang ô điểm đến, để gõ liền một mạch. */
  const pickOrigin = (airport: FlightAirport) => {
    setOrigin(airportLabel(airport));
    setActiveOption(-1);
    setPanel('location');
    locationInputRef.current?.focus();
  };

  const pickDestination = (airport: FlightAirport) => {
    setLocation(airportLabel(airport));
    setActiveOption(-1);
    setPanel('dates');
  };

  /**
   * Rời ô sân bay: chữ khớp sân bay hiện hành thì ghi lại đúng nhãn "Thành phố (MÃ)", không khớp thì xoá (spec §4.4).
   * Đọc chữ mới nhất qua hàm cập nhật: chọn một dòng rồi chuyển focus sang ô kia thì ô này bị rời ngay, lúc đó chữ trong
   * closure còn là chữ cũ. Khi danh sách chưa tải xong thì giữ nguyên chữ, vì chưa biết chữ có đúng không.
   */
  const settleAirport = (set: React.Dispatch<React.SetStateAction<string>>, other: FlightAirport | null) => {
    const list = airports.data;
    if (!list) return;
    set((text) => {
      const hit = matchAirport(text, list);
      return hit && hit.code !== other?.code ? airportLabel(hit) : '';
    });
  };

  /** Mũi tên và Enter trên danh sách gợi ý của một ô; Enter khi chưa tô sáng mục nào thì để form gửi đi. */
  const navigateOptions = (e: React.KeyboardEvent, name: Exclude<Panel, null>, count: number, pickAt: (index: number) => void) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setPanel(name);
      setActiveOption((i) => Math.min(i + 1, count - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveOption((i) => Math.max(i - 1, -1));
    } else if (e.key === 'Enter' && panel === name && activeOption >= 0 && activeOption < count) {
      e.preventDefault();
      pickAt(activeOption);
    }
  };

  const setTripKind = (round: boolean) => {
    setRoundTrip(round);
    setCheckOut(round ? addDaysIso(checkIn, 2) : null);
  };

  /** Vé máy bay: chỉ hai sân bay đã khớp mới đi đi; chữ không khớp bị xoá khỏi ô, và báo đúng ô nào. */
  const submitFlight = () => {
    const ready = airports.data !== null;
    const rawOrigin = origin;
    const rawDestination = location;
    if (ready) {
      setOrigin(originAirport ? airportLabel(originAirport) : '');
      setLocation(destinationAirport ? airportLabel(destinationAirport) : '');
    }
    if (keepHistory && originAirport && destinationAirport) {
      recentOrigins.remember(originAirport.city);
      recentDestinations.remember(destinationAirport.city);
    }
    const trip = currentTrip();
    const input: FlightSearchInput = {
      origin: originAirport?.city ?? '',
      originText: rawOrigin,
      location: rawDestination,
      destination: destinationAirport?.city ?? null,
      airportsReady: ready,
      trip: { checkIn: trip.checkIn, checkOut: trip.checkOut, adults: trip.adults, children: trip.children },
    };
    // Vé máy bay ở `/flights`: kết quả hiện ngay dưới tấm này, kể cả khi còn thiếu sân bay (trang nhắc người dùng chọn).
    if (onFlightSearch) {
      onFlightSearch(input);
      return;
    }
    if (input.origin && input.destination) {
      navigate(buildSearchHref({ taxonomy: tab.taxonomy, origin: input.origin, location: '', destination: input.destination, trip }));
    }
  };

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    setPanel(null);
    if (airportMode) {
      submitFlight();
      return;
    }
    const resolved = destination ?? matchDestination(location, destinations.data);
    const trip = currentTrip();
    navigate(buildSearchHref({ taxonomy: tab.taxonomy, origin, location, destination: resolved, trip }));
  };

  const togglePanel = (next: Exclude<Panel, null>) => setPanel((prev) => (prev === next ? null : next));

  // Dãy lựa chọn của ô địa điểm (không phải sân bay) theo đúng thứ tự hiển thị, để mũi tên và Enter đi đúng dòng.
  const locationRows: { pick: () => void }[] = famous
    ? [
      ...famous.hotels.map((hotel) => ({ pick: () => openHotel(hotel) })),
      ...famous.destinations.map((name) => ({ pick: () => chooseDestination(name) })),
    ]
    : locationList.map((name) => ({ pick: () => chooseDestination(name) }));

  return (
    <form
      ref={formRef}
      onSubmit={submit}
      aria-label={`Tìm ${tab.noun}`}
      className="glass-sheet w-full rounded-[28px] p-2.5 sm:rounded-[38px]"
    >
      <div className="flex flex-col gap-2 rounded-[24px] bg-[#d6dadf]/60 p-2 sm:rounded-[32px] lg:flex-row lg:items-stretch lg:p-3">
        {sheet.origin && (
          <AirportField
            listId={originListId}
            listLabel="Gợi ý điểm đi"
            label={sheet.origin.label}
            placeholder={sheet.origin.placeholder}
            icon={<PlaneTakeoff className="h-5 w-5 shrink-0 text-slate-400" aria-hidden="true" />}
            value={origin}
            open={panel === 'origin'}
            airports={airports.data}
            loading={airports.loading}
            error={Boolean(airports.error)}
            recent={recentOrigins.items}
            exclude={destinationAirport}
            onChange={setOrigin}
            onOpen={() => setPanel('origin')}
            onClose={() => setPanel((prev) => (prev === 'origin' ? null : prev))}
            onPick={pickOrigin}
            onBlur={() => {
              setPanel((prev) => (prev === 'origin' ? null : prev));
              settleAirport(setOrigin, destinationAirport);
            }}
            onClearRecent={recentOrigins.clear}
          />
        )}

        <div className="relative min-w-0 flex-1">
          {airportMode ? (
            <AirportField
              listId={listId}
              listLabel="Gợi ý điểm đến"
              label={sheet.location.label}
              placeholder={sheet.location.placeholder}
              icon={<MapPin className="h-5 w-5 shrink-0 text-slate-400" aria-hidden="true" />}
              inputRef={locationInputRef}
              value={location}
              open={panel === 'location'}
              airports={airports.data}
              loading={airports.loading}
              error={Boolean(airports.error)}
              recent={recentDestinations.items}
              exclude={originAirport}
              onChange={setLocation}
              onOpen={() => setPanel('location')}
              onClose={() => setPanel((prev) => (prev === 'location' ? null : prev))}
              onPick={pickDestination}
              onBlur={() => {
                setPanel((prev) => (prev === 'location' ? null : prev));
                settleAirport(setLocation, originAirport);
              }}
              onClearRecent={recentDestinations.clear}
            />
          ) : (
            <>
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
                    onKeyDown={(e) => navigateOptions(e, 'location', locationRows.length, (i) => locationRows[i].pick())}
                    placeholder={sheet.location.placeholder}
                    autoComplete="off"
                    className={VALUE}
                    ref={locationInputRef}
                  />
                </span>
              </label>
              {panel === 'location' && (
                <div className={`${POPOVER} left-0 w-full min-w-64`}>
                  {famous ? (
                    <FamousHotelsPanel
                      listId={listId}
                      listLabel="Gợi ý khách sạn nổi tiếng và điểm đến"
                      text={location}
                      hotels={famousHotels.data}
                      error={Boolean(famousHotels.error)}
                      options={famous}
                      activeOption={activeOption}
                      errorHint="Chưa tải được khách sạn nổi tiếng. Bạn vẫn có thể gõ tên điểm đến."
                      onPickHotel={openHotel}
                      onPickDestination={chooseDestination}
                    />
                  ) : (
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
                  )}
                </div>
              )}
            </>
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
                      className={`h-9 cursor-pointer rounded-full px-4 text-sm font-semibold transition ${roundTrip === round ? 'bg-white text-brand-600 shadow-xs' : 'text-slate-600'}`}
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
          className="flex h-[70px] w-full shrink-0 cursor-pointer items-center justify-center gap-2 rounded-full bg-gradient-to-r from-brand-600 to-brand-600 px-4 text-white shadow-lg transition hover:scale-[1.03] active:scale-95 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600 lg:w-[120px]"
        >
          <Search className="h-6 w-6" aria-hidden="true" />
          <span className="text-sm font-bold lg:sr-only">Tìm kiếm</span>
        </button>
      </div>
    </form>
  );
}
