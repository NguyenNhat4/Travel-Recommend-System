'use client';

import React from 'react';
import { MapPin } from 'lucide-react';
import { placeholderImage } from '../../../services/catalog';
import { filterDestinations, startsAWord } from './searchHref';

/** Khách sạn hiển thị trong dropdown ô Địa điểm của `/hotels` và `/combos` (spec §5). */
export interface FamousHotel {
  id: string;
  name: string;
  destination: string;
  /** Ảnh của catalog; khi thiếu thì dùng ảnh thay thế của loại khách sạn. */
  imageUrl: string;
}

export const FAMOUS_HOTEL_SHOWN = 5;
export const FAMOUS_DESTINATION_SHOWN = 5;

/** Cách đọc thứ tự chọn: khách sạn trước, điểm đến sau. Hai danh sách nối lại thành một dãy để điều khiển bằng phím. */
export interface FamousHotelOptions {
  hotels: FamousHotel[];
  destinations: string[];
}

/**
 * Khi ô trống: 5 khách sạn đầu của danh sách nổi tiếng, không có điểm đến. Khi đang gõ: khách sạn có tên hoặc thành phố
 * bắt đầu một từ bằng chữ gõ (không phân biệt dấu), và điểm đến khớp chữ gõ để vẫn tìm được theo thành phố.
 */
export function famousHotelOptions(text: string, hotels: readonly FamousHotel[], destinations: readonly { destination: string }[]): FamousHotelOptions {
  if (!text.trim()) return { hotels: hotels.slice(0, FAMOUS_HOTEL_SHOWN), destinations: [] };
  const matchedHotels = hotels.filter((hotel) => startsAWord(hotel.name, text) || startsAWord(hotel.destination, text));
  const matchedDestinations = filterDestinations(text, destinations, FAMOUS_DESTINATION_SHOWN).map((d) => d.destination);
  return { hotels: matchedHotels.slice(0, FAMOUS_HOTEL_SHOWN), destinations: matchedDestinations };
}

interface FamousHotelsPanelProps {
  listId: string;
  listLabel: string;
  /** Chữ đang gõ, dùng cho câu "không khớp". */
  text: string;
  /** null khi chưa tải xong (và chưa lỗi). */
  hotels: readonly FamousHotel[] | null;
  error: boolean;
  options: FamousHotelOptions;
  /** Vị trí dòng đang tô sáng trong dãy `hotels` rồi `destinations`; -1 là chưa có. */
  activeOption: number;
  errorHint: string;
  onPickHotel: (hotel: FamousHotel) => void;
  onPickDestination: (name: string) => void;
}

/**
 * Nội dung dropdown ô Địa điểm của `/hotels` và `/combos`: "Khách sạn nổi tiếng" thay cho "Điểm đến phổ biến".
 * Chữ `option` ghi tên đủ của khách sạn để trình đọc màn hình đọc được.
 */
export function FamousHotelsPanel({ listId, listLabel, text, hotels, error, options, activeOption, errorHint, onPickHotel, onPickDestination }: FamousHotelsPanelProps) {
  const hasRows = options.hotels.length + options.destinations.length > 0;

  return (
    <div id={listId} role="listbox" aria-label={listLabel} className="flex max-h-[360px] flex-col gap-4 overflow-y-auto pr-1">
      {hotels === null && !error ? (
        <div role="group" aria-label="Khách sạn nổi tiếng" aria-busy="true" className="flex flex-col gap-2">
          <p className="mb-1 text-[11px] font-bold uppercase tracking-wider text-slate-400">Khách sạn nổi tiếng</p>
          {[0, 1, 2].map((i) => <span key={i} aria-hidden="true" className="skeleton-wave h-12 w-full rounded-xl" />)}
        </div>
      ) : hotels === null ? (
        <p className="text-xs text-slate-500">{errorHint}</p>
      ) : (
        <>
          {options.hotels.length > 0 && (
            <div role="group" aria-label="Khách sạn nổi tiếng" className="flex flex-col gap-1">
              <p className="mb-1 text-[11px] font-bold uppercase tracking-wider text-slate-400">Khách sạn nổi tiếng</p>
              {options.hotels.map((hotel, index) => {
                const position = index;
                const isActive = position === activeOption;
                return (
                  <button
                    key={`hotel-${hotel.id}`}
                    id={`${listId}-${position}`}
                    type="button"
                    role="option"
                    aria-selected={isActive}
                    aria-label={`${hotel.name}, ${hotel.destination}`}
                    onClick={() => onPickHotel(hotel)}
                    className={`flex w-full cursor-pointer items-center gap-3 rounded-xl border p-2 text-left transition ${
                      isActive ? 'border-brand-400 bg-brand-50' : 'border-transparent hover:bg-slate-50'
                    }`}
                  >
                    {/* Ảnh tải lỗi thì về ảnh thay thế của loại khách sạn; không dùng ảnh giả. */}
                    <img
                      src={hotel.imageUrl || placeholderImage('hotel')}
                      alt=""
                      loading="lazy"
                      decoding="async"
                      referrerPolicy="no-referrer"
                      onError={(event) => {
                        const img = event.currentTarget;
                        if (!img.src.endsWith(placeholderImage('hotel'))) img.src = placeholderImage('hotel');
                      }}
                      className="h-12 w-12 shrink-0 rounded-xl object-cover"
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-semibold text-slate-900">{hotel.name}</span>
                      <span className="flex items-center gap-1 truncate text-xs text-slate-500">
                        <MapPin className="h-3 w-3 shrink-0" aria-hidden="true" />
                        <span className="truncate">{hotel.destination}</span>
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          )}

          {options.destinations.length > 0 && (
            <div role="group" aria-label="Điểm đến" className="flex flex-col gap-2">
              <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Điểm đến</p>
              <div className="flex flex-wrap gap-2">
                {options.destinations.map((name, index) => {
                  const position = options.hotels.length + index;
                  const isActive = position === activeOption;
                  return (
                    <button
                      key={`destination-${name}`}
                      id={`${listId}-${position}`}
                      type="button"
                      role="option"
                      aria-selected={isActive}
                      onClick={() => onPickDestination(name)}
                      className={`inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-full border px-3.5 text-sm font-semibold transition ${
                        isActive ? 'border-brand-400 bg-brand-50 text-brand-700' : 'border-slate-200 bg-slate-50 text-slate-700 hover:border-brand-300 hover:text-brand-700'
                      }`}
                    >
                      <MapPin className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
                      {name}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {!hasRows && (
            hotels === null || hotels.length === 0 ? (
              <p className="text-xs text-slate-500">Chưa có khách sạn nổi tiếng để hiển thị lúc này.</p>
            ) : (
              <p className="text-xs text-slate-500">
                {text.trim()
                  ? <>Không có khách sạn hay điểm đến nào khớp &ldquo;{text.trim()}&rdquo;. Bạn vẫn có thể tìm theo &ldquo;{text.trim()}&rdquo;.</>
                  : 'Chưa có khách sạn nổi tiếng để hiển thị lúc này.'}
              </p>
            )
          )}
        </>
      )}
    </div>
  );
}
