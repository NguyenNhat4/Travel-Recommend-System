'use client';

import React, { useEffect, useId, useMemo, useRef, useState } from 'react';
import { Calendar, MapPin, Search, Users } from 'lucide-react';
import type { CartState } from '../checkout/allocation';
import { DateRangePicker, formatDisplayDate } from '../../features/catalog/landing/DateRangePicker';
import { GuestsPopover, describeGuests } from '../../features/catalog/landing/GuestsPopover';
import { PlacePanel } from '../../features/catalog/landing/PlacePanel';
import { buildPlaceOptions } from '../../features/catalog/landing/recentPlaces';
import { buildSearchHref, matchDestination } from '../../features/catalog/landing/searchHref';
import { useDestinations } from '../../features/catalog/landing/useDestinations';
import { useTravel } from '../../context/TravelContext';
import { addDaysIso, todayVN } from '../../features/search/tripContext';

interface HotelTripBarProps {
  hotelName: string;
  checkIn: string;
  checkOut: string;
  counts: CartState;
  onDates: (checkIn: string, checkOut: string) => void;
  onCounts: (next: CartState) => void;
  /** Bấm nút tìm: ghi ngày và đoàn khách vào URL rồi cuộn tới danh sách hạng phòng. */
  onSearch: () => void;
  /** Lỗi ngày đang nhập (nếu có); các nút Đặt ngay của hạng phòng bị khoá cho tới khi sửa. */
  dateError: string | null;
}

type Panel = 'location' | 'dates' | 'guests' | null;

const SEGMENT = 'flex h-12 w-full min-w-0 items-center gap-3 rounded-full border border-slate-200 bg-slate-50 px-5 text-left text-sm font-semibold text-slate-800 transition-colors motion-reduce:transition-none';
const CLICKABLE = `${SEGMENT} cursor-pointer hover:border-brand-300 hover:bg-white focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand-600`;
const POPOVER = 'absolute top-full z-40 mt-2 rounded-3xl bg-white p-4 text-slate-800 shadow-2xl ring-1 ring-slate-900/5';

const nightsBetween = (from: string, to: string) => Math.max(1, Math.round((new Date(`${to}T12:00:00Z`).getTime() - new Date(`${from}T12:00:00Z`).getTime()) / 86400000));

/**
 * Thanh tìm kiếm của trang chi tiết khách sạn, cùng kiểu với tấm tìm kiếm ở trang danh mục: ô địa điểm (điền sẵn tên khách sạn, gõ được và
 * có gợi ý điểm đến), ngày ở, số phòng và khách, nút tìm. Giữ nguyên ô địa điểm thì nút tìm chỉ áp ngày/khách và cuộn tới hạng phòng; đổi
 * địa điểm thì sang `/hotels` với kết quả theo địa điểm, ngày và khách đó, như tấm tìm kiếm ở trang danh mục. Điền sẵn từ URL của lần tìm; nút Đặt ngay nằm trên từng thẻ hạng phòng và dùng đúng các giá trị này.
 */
export const HotelTripBar: React.FC<HotelTripBarProps> = ({ hotelName, checkIn, checkOut, counts, onDates, onCounts, onSearch, dateError }) => {
  const formRef = useRef<HTMLFormElement>(null);
  const { navigate } = useTravel();
  const listId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [panel, setPanel] = useState<Panel>(null);
  const [location, setLocation] = useState(hotelName);
  const [destination, setDestination] = useState<string | null>(null);
  const [activeOption, setActiveOption] = useState(-1);
  const destinations = useDestinations(panel === 'location');
  const options = useMemo(() => buildPlaceOptions({ text: location === hotelName ? '' : location, recent: [], destinations: destinations.data }), [location, hotelName, destinations.data]);
  const optionList = [...options.recent, ...options.popular];
  useEffect(() => { setLocation(hotelName); setDestination(null); }, [hotelName]);

  useEffect(() => {
    if (!panel) return;
    const onPointerDown = (event: MouseEvent) => { if (!formRef.current?.contains(event.target as Node)) setPanel(null); };
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') setPanel(null); };
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [panel]);

  // Chọn một điểm đến gợi ý: giữ ô chữ, mở tiếp lịch để chọn ngày cho nơi mới.
  const choose = (name: string) => { setLocation(name); setDestination(name); setActiveOption(-1); setPanel('dates'); };
  const toggle = (next: Exclude<Panel, null>) => setPanel((prev) => (prev === next ? null : next));
  const guests = { adults: counts.guests.adults, children: counts.guests.children, rooms: counts.quantity };
  const dayMonth = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;

  return (
    <div className="space-y-2 mb-8" data-testid="hotel-trip-bar">
      <form
        ref={formRef}
        aria-label="Tìm phòng"
        onSubmit={(event) => {
          event.preventDefault();
          setPanel(null);
          const text = location.trim();
          if (!text || text === hotelName) { onSearch(); return; }
          if (dateError) return;
          navigate(buildSearchHref({
            taxonomy: 'hotel', origin: '', location: text, destination: destination ?? matchDestination(text, destinations.data),
            trip: { checkIn, checkOut, adults: counts.guests.adults, children: counts.guests.children, rooms: counts.quantity },
          }));
        }}
        className="grid grid-cols-1 gap-2 rounded-[32px] border border-slate-200 bg-white p-2 shadow-md shadow-slate-900/5 sm:grid-cols-[repeat(3,minmax(0,1fr))_auto] sm:rounded-full"
      >
        <div className="relative min-w-0">
          <label className={`${SEGMENT} focus-within:border-brand-600 focus-within:bg-white focus-within:outline-2 focus-within:outline-offset-1 focus-within:outline-brand-600`}>
            <MapPin className="h-5 w-5 shrink-0 text-brand-700" aria-hidden="true" />
            <input
              ref={inputRef}
              type="text"
              role="combobox"
              aria-label="Địa điểm hoặc tên khách sạn"
              aria-expanded={panel === 'location'}
              aria-controls={listId}
              aria-autocomplete="list"
              autoComplete="off"
              value={location}
              title={location}
              onChange={(e) => { setLocation(e.target.value); setDestination(matchDestination(e.target.value, destinations.data)); setActiveOption(-1); setPanel('location'); }}
              onFocus={(e) => { e.currentTarget.select(); setActiveOption(-1); setPanel('location'); }}
              onKeyDown={(e) => {
                if (e.key === 'ArrowDown') { e.preventDefault(); setActiveOption((i) => Math.min(i + 1, optionList.length - 1)); }
                else if (e.key === 'ArrowUp') { e.preventDefault(); setActiveOption((i) => Math.max(i - 1, -1)); }
                else if (e.key === 'Enter' && panel === 'location' && activeOption >= 0 && optionList[activeOption]) { e.preventDefault(); choose(optionList[activeOption]); }
              }}
              className="w-full min-w-0 truncate bg-transparent font-bold text-slate-900 outline-none placeholder:font-normal placeholder:text-slate-400"
              placeholder="Điểm đến hoặc tên khách sạn"
            />
          </label>
          {panel === 'location' && (
            <div className={`${POPOVER} left-0 w-full min-w-64`}>
              <PlacePanel listId={listId} listLabel="Gợi ý điểm đến" title="Điểm đến phổ biến" text={location === hotelName ? '' : location} {...options}
                loading={destinations.loading} error={Boolean(destinations.error)} activeOption={activeOption}
                errorHint="Chưa tải được gợi ý điểm đến. Bạn vẫn có thể gõ tên điểm đến." onPick={choose} onClearRecent={() => undefined} />
            </div>
          )}
        </div>

        <div className="relative min-w-0">
          <button type="button" aria-haspopup="dialog" aria-expanded={panel === 'dates'} aria-label={`Ngày ở: ${checkIn && checkOut ? `${dayMonth(checkIn)} - ${dayMonth(checkOut)}` : 'chưa chọn'}`} onClick={() => toggle('dates')} className={CLICKABLE}>
            <Calendar className="h-5 w-5 shrink-0 text-brand-700" aria-hidden="true" />
            <span className="truncate">
              {checkIn && checkOut ? `${dayMonth(checkIn)} - ${dayMonth(checkOut)}, ${checkOut > checkIn ? nightsBetween(checkIn, checkOut) : 0} đêm` : 'Chọn ngày'}
            </span>
          </button>
          {panel === 'dates' && (
            <div className={`${POPOVER} left-0`}>
              <DateRangePicker mode="range" start={checkIn || addDaysIso(todayVN(), 1)} end={checkOut || null} min={todayVN()}
                startLabel="Nhận phòng" endLabel="Trả phòng" hint="Nhận phòng trong 3 tháng tới, tối đa 30 đêm."
                onChange={(start, end) => onDates(start, end ?? addDaysIso(start, 1))} onDone={() => setPanel(null)} />
            </div>
          )}
        </div>

        <div className="relative min-w-0">
          <button type="button" aria-haspopup="dialog" aria-expanded={panel === 'guests'} aria-label={`Số phòng và khách: ${describeGuests(guests, true)}`} onClick={() => toggle('guests')} className={CLICKABLE}>
            <Users className="h-5 w-5 shrink-0 text-brand-700" aria-hidden="true" />
            <span className="truncate">{describeGuests(guests, true)}</span>
          </button>
          {panel === 'guests' && (
            <div className={`${POPOVER} right-0`}>
              <GuestsPopover showRooms value={guests}
                onChange={(next) => onCounts({ quantity: next.rooms, guests: { adults: next.adults, children: next.children } })} />
            </div>
          )}
        </div>

        <button type="submit" aria-label="Tìm phòng"
          className="flex h-12 w-full cursor-pointer items-center justify-center gap-2 rounded-full bg-brand-600 px-6 text-white shadow-md transition-colors hover:bg-brand-700 active:scale-95 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600 motion-reduce:transform-none motion-reduce:transition-none sm:w-[84px]">
          <Search className="h-5 w-5" aria-hidden="true" />
          <span className="text-sm font-bold sm:sr-only">Tìm phòng</span>
        </button>
      </form>
      {dateError && (
        <p role="alert" data-testid="date-error" className="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg p-2.5">{dateError}</p>
      )}
    </div>
  );
};
