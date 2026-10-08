'use client';

import React from 'react';
import { Baby, Ban, Bed, BedDouble, CheckCircle2, ChevronDown, Images, Maximize2, ShieldCheck, Tag, Users, Waves } from 'lucide-react';
import { placeholderImage } from '../../services/catalog';
import type { Product } from '../../types/travel';
import { formatVnd } from '../confirmation/bookingLabels';
import { AmenityList, amenityList } from './AmenityList';
import { amenityIcon, pickHighlights } from './amenityIcons';
import { imagesOf } from './ProductGallery';

interface RoomCardProps {
  room: Product;
  /** Tên hạng phòng (`roomName`, không kèm tên khách sạn). */
  title: string;
  selected: boolean;
  /** Đang bán và có giá (cùng điều kiện đặt được ở hộp đặt). */
  selectable: boolean;
  /** Giá thấp nhất trong các hạng phòng bán được (chỉ gắn nhãn khi có ít nhất hai hạng). */
  cheapest?: boolean;
  onSelect: () => void;
  onPhotos: (images: string[]) => void;
  amenitiesOpen: boolean;
  onToggleAmenities: () => void;
}

interface Fact {
  icon: React.ComponentType<{ className?: string; 'aria-hidden'?: boolean | 'true' }>;
  text: string;
}

/** Thông số của hạng phòng, mỗi thông số một icon: sức chứa, diện tích, giường, phòng ngủ, hướng biển, hợp gia đình. */
function roomFacts(room: Product): Fact[] {
  const a = (room.attributes ?? {}) as Record<string, unknown>;
  const facts: Fact[] = [];
  if (typeof a.maxOccupancy === 'number' && a.maxOccupancy > 0) facts.push({ icon: Users, text: `Tối đa ${a.maxOccupancy} khách` });
  if (a.roomSizeM2) facts.push({ icon: Maximize2, text: `${a.roomSizeM2} m²` });
  if (typeof a.bed === 'string' && a.bed.trim()) facts.push({ icon: BedDouble, text: a.bed.trim() });
  if (typeof a.bedrooms === 'number' && a.bedrooms > 0) facts.push({ icon: Bed, text: `${a.bedrooms} phòng ngủ` });
  if (a.oceanView === true) facts.push({ icon: Waves, text: 'Hướng biển' });
  if (a.familyFriendly === true) facts.push({ icon: Baby, text: 'Phù hợp gia đình' });
  return facts;
}

/**
 * Thẻ một hạng phòng ở bước "Chọn hạng phòng": ảnh lớn, thông số có icon, tiện ích nổi bật có icon, giá nổi bật và trạng thái chọn rõ.
 * Cả thẻ là một ô chọn (`role="radio"` phủ kín thẻ, nằm dưới nội dung); nút xem ảnh và tiện ích nằm trên nó nên bấm vào đó không đổi
 * lựa chọn. Nội dung `pointer-events-none` để mọi chỗ khác của thẻ đều chọn được.
 */
export const RoomCard: React.FC<RoomCardProps> = ({
  room, title, selected, selectable, cheapest, onSelect, onPhotos, amenitiesOpen, onToggleAmenities,
}) => {
  const photos = imagesOf(room);
  const amenities = amenityList(room.attributes?.amenities);
  const highlights = pickHighlights(amenities, 5);
  const facts = roomFacts(room);
  const price = room.unitPrice;
  const panelId = `amenities-${room.id}`;

  const frame = selected
    ? 'border-blue-600 bg-blue-50/40 shadow-lg shadow-blue-900/10 ring-2 ring-blue-600/30'
    : selectable
      ? 'border-slate-200 bg-white hover:border-blue-300 hover:shadow-md'
      : 'border-slate-200 bg-slate-50';

  return (
    <div className={`relative overflow-hidden rounded-2xl border transition-all duration-200 motion-reduce:transition-none ${frame} ${selectable ? '' : 'opacity-75'}`}>
      <button
        type="button"
        role="radio"
        aria-checked={selected}
        aria-label={`${title}${price != null ? `, ${formatVnd(price)} mỗi đêm` : ''}`}
        disabled={!selectable}
        onClick={onSelect}
        className="absolute inset-0 z-0 h-full w-full cursor-pointer rounded-2xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed"
      />

      <div className="pointer-events-none relative z-10 flex flex-col md:flex-row">
        <div className="relative aspect-16/10 shrink-0 overflow-hidden bg-slate-100 md:aspect-auto md:min-h-[230px] md:w-64">
          <img
            src={photos[0] ?? room.imageUrl}
            alt=""
            loading="lazy"
            fetchPriority="low"
            decoding="async"
            referrerPolicy="no-referrer"
            onError={(event) => {
              const fallback = placeholderImage(room.taxonomy);
              if (!event.currentTarget.src.endsWith(fallback)) event.currentTarget.src = fallback;
            }}
            className={`absolute inset-0 h-full w-full object-cover transition-transform duration-500 motion-reduce:transition-none ${selectable ? '' : 'grayscale'}`}
          />
          {photos.length > 0 && (
            <button
              type="button"
              onClick={() => onPhotos(photos)}
              aria-label={`Xem ảnh phòng (${photos.length})`}
              className="pointer-events-auto absolute bottom-3 left-3 inline-flex cursor-pointer items-center gap-1.5 rounded-lg bg-white/90 px-2.5 py-1.5 text-xs font-semibold text-slate-800 shadow backdrop-blur transition hover:bg-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
            >
              <Images className="h-3.5 w-3.5" aria-hidden="true" />{photos.length}
            </button>
          )}
          {!selectable && (
            <span className="absolute left-3 top-3 inline-flex items-center gap-1.5 rounded-lg bg-slate-900/80 px-2.5 py-1 text-xs font-bold text-white">
              <Ban className="h-3.5 w-3.5" aria-hidden="true" />Hết chỗ
            </span>
          )}
        </div>

        <div className="flex min-w-0 flex-1 flex-col gap-3.5 p-4 md:p-5">
          <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1.5">
            <h4 className="min-w-0 font-display text-lg font-semibold leading-snug text-slate-900">{title}</h4>
            {cheapest && selectable && (
              <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-amber-50 px-2.5 py-1 text-[11px] font-bold text-amber-800 ring-1 ring-amber-200">
                <Tag className="h-3 w-3" aria-hidden="true" />Giá tốt nhất
              </span>
            )}
          </div>

          {facts.length > 0 && (
            <ul className="flex flex-wrap gap-x-4 gap-y-2 text-[13px] font-medium text-slate-700" aria-label="Thông số phòng">
              {facts.map(({ icon: Icon, text }) => (
                <li key={text} className="inline-flex items-center gap-1.5">
                  <Icon className="h-4 w-4 shrink-0 text-blue-700" aria-hidden="true" />{text}
                </li>
              ))}
            </ul>
          )}

          {highlights.length > 0 && (
            <ul className="flex flex-wrap gap-2" aria-label="Tiện ích nổi bật">
              {highlights.map((item) => {
                const Icon = amenityIcon(item);
                return (
                  <li key={item} className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white/80 px-2.5 py-1 text-xs text-slate-700">
                    <Icon className="h-3.5 w-3.5 shrink-0 text-blue-700" aria-hidden="true" />{item}
                  </li>
                );
              })}
            </ul>
          )}

          <div className="mt-auto flex flex-wrap items-end justify-between gap-x-4 gap-y-3 border-t border-slate-100 pt-3.5">
            {amenities.length > 0 ? (
              <button
                type="button"
                aria-expanded={amenitiesOpen}
                aria-controls={panelId}
                onClick={onToggleAmenities}
                className="pointer-events-auto inline-flex cursor-pointer items-center gap-1 text-xs font-semibold text-blue-700 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
              >
                {amenitiesOpen ? 'Ẩn tiện ích phòng' : `Tiện ích phòng (${amenities.length})`}
                <ChevronDown className={`h-3.5 w-3.5 transition-transform motion-reduce:transition-none ${amenitiesOpen ? 'rotate-180' : ''}`} aria-hidden="true" />
              </button>
            ) : <span />}

            <div className="ml-auto flex items-end gap-4">
              <div className="text-right">
                {price != null ? (
                  <>
                    <p className="text-2xl font-bold leading-none text-blue-900 tabular-nums">
                      {formatVnd(price)}<span className="ml-1 text-xs font-medium text-slate-500">/ đêm</span>
                    </p>
                    <p className="mt-1.5 inline-flex items-center gap-1 text-[11px] text-slate-500">
                      <ShieldCheck className="h-3 w-3 text-emerald-600" aria-hidden="true" />Đã gồm thuế &amp; phí
                    </p>
                  </>
                ) : (
                  <p className="text-sm font-medium text-slate-500">Chưa có giá</p>
                )}
              </div>
              <span
                className={`inline-flex h-10 min-w-[7.5rem] items-center justify-center gap-1.5 rounded-xl px-4 text-sm font-bold transition-colors motion-reduce:transition-none ${
                  !selectable ? 'bg-slate-200 text-slate-500'
                    : selected ? 'bg-blue-700 text-white shadow-sm'
                      : 'border border-blue-200 bg-white text-blue-700'}`}
                aria-hidden="true"
              >
                {selected && <CheckCircle2 className="h-4 w-4" />}
                {!selectable ? 'Hết chỗ' : selected ? 'Đã chọn' : 'Chọn phòng'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {amenitiesOpen && amenities.length > 0 && (
        <div id={panelId} className="pointer-events-auto relative z-10 border-t border-slate-100 bg-slate-50/80 px-4 py-4 md:px-5">
          <AmenityList items={amenities} limit={60} label="Tiện ích phòng" compact columns />
        </div>
      )}
    </div>
  );
};
