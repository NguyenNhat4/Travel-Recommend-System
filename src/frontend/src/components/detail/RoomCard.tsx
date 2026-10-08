'use client';

import React from 'react';
import { Baby, Ban, Bed, BedDouble, ChevronDown, Loader2, Images, Maximize2, ShieldCheck, Tag, Users, Waves } from 'lucide-react';
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
  /** Đang bán và có giá. */
  bookable: boolean;
  /** Ngày và đoàn khách đang nhập hợp lệ với phòng này; sai thì nút Đặt ngay khoá. */
  canBook: boolean;
  /** Lý do riêng của phòng này khi đoàn khách không hợp lệ (ví dụ vượt sức chứa). */
  bookNote?: string | null;
  /** Giá thấp nhất trong các hạng phòng bán được (chỉ gắn nhãn khi có ít nhất hai hạng). */
  cheapest?: boolean;
  onBook: () => void;
  /** Đang tạo đơn nháp: khoá nút và hiện vòng xoay để khách không bấm hai lần. */
  busy?: boolean;
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
 * Thẻ một hạng phòng: ảnh lớn, thông số có icon, tiện ích nổi bật có icon, giá nổi bật và nút Đặt ngay ngay trên thẻ. Ngày và đoàn
 * khách lấy từ thanh ngày/số khách phía trên danh sách (điền sẵn từ tấm tìm kiếm), nên khách đi từ kết quả tìm kiếm bấm đặt luôn.
 */
export const RoomCard: React.FC<RoomCardProps> = ({
  room, title, bookable, canBook, bookNote, busy, cheapest, onBook, onPhotos, amenitiesOpen, onToggleAmenities,
}) => {
  const photos = imagesOf(room);
  const amenities = amenityList(room.attributes?.amenities);
  const highlights = pickHighlights(amenities, 5);
  const facts = roomFacts(room);
  const price = room.unitPrice;
  const panelId = `amenities-${room.id}`;

  const frame = bookable ? 'border-slate-200 bg-white hover:border-brand-300 hover:shadow-md' : 'border-slate-200 bg-slate-50';

  return (
    <div className={`relative overflow-hidden rounded-2xl border transition-all duration-200 motion-reduce:transition-none ${frame} ${bookable ? '' : 'opacity-75'}`}>
      <div className="flex flex-col md:flex-row">
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
            className={`absolute inset-0 h-full w-full object-cover transition-transform duration-500 motion-reduce:transition-none ${bookable ? '' : 'grayscale'}`}
          />
          {photos.length > 0 && (
            <button
              type="button"
              onClick={() => onPhotos(photos)}
              aria-label={`Xem ảnh phòng (${photos.length})`}
              className="absolute bottom-3 left-3 inline-flex cursor-pointer items-center gap-1.5 rounded-lg bg-white/90 px-2.5 py-1.5 text-xs font-semibold text-slate-800 shadow backdrop-blur transition hover:bg-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600"
            >
              <Images className="h-3.5 w-3.5" aria-hidden="true" />{photos.length}
            </button>
          )}
          {!bookable && (
            <span className="absolute left-3 top-3 inline-flex items-center gap-1.5 rounded-lg bg-slate-900/80 px-2.5 py-1 text-xs font-bold text-white">
              <Ban className="h-3.5 w-3.5" aria-hidden="true" />Hết chỗ
            </span>
          )}
        </div>

        <div className="flex min-w-0 flex-1 flex-col gap-3.5 p-4 md:p-5">
          <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1.5">
            <h4 className="min-w-0 font-display text-lg font-semibold leading-snug text-slate-900">{title}</h4>
            {cheapest && bookable && (
              <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-amber-50 px-2.5 py-1 text-[11px] font-bold text-amber-800 ring-1 ring-amber-200">
                <Tag className="h-3 w-3" aria-hidden="true" />Giá tốt nhất
              </span>
            )}
          </div>

          {facts.length > 0 && (
            <ul className="flex flex-wrap gap-x-4 gap-y-2 text-[13px] font-medium text-slate-700" aria-label="Thông số phòng">
              {facts.map(({ icon: Icon, text }) => (
                <li key={text} className="inline-flex items-center gap-1.5">
                  <Icon className="h-4 w-4 shrink-0 text-brand-700" aria-hidden="true" />{text}
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
                    <Icon className="h-3.5 w-3.5 shrink-0 text-brand-700" aria-hidden="true" />{item}
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
                className="inline-flex min-h-11 cursor-pointer items-center gap-1 text-xs font-semibold text-brand-700 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600"
              >
                {amenitiesOpen ? 'Ẩn tiện ích phòng' : `Tiện ích phòng (${amenities.length})`}
                <ChevronDown className={`h-3.5 w-3.5 transition-transform motion-reduce:transition-none ${amenitiesOpen ? 'rotate-180' : ''}`} aria-hidden="true" />
              </button>
            ) : <span />}

            <div className="ml-auto flex items-end gap-4">
              <div className="text-right">
                {price != null ? (
                  <>
                    <p className="text-2xl font-bold leading-none text-brand-900 tabular-nums">
                      {formatVnd(price)}<span className="ml-1 text-xs font-medium text-slate-500">/ đêm</span>
                    </p>
                    <p className="mt-1.5 inline-flex items-center gap-1 text-[11px] text-slate-500">
                      <ShieldCheck className="h-3 w-3 text-emerald-600" aria-hidden="true" />Đã gồm thuế &amp; phí
                    </p>
                  </>
                ) : (
                  <p className="text-sm font-medium text-slate-500">Chưa có giá</p>
                )}
                {bookNote && <p role="alert" className="mt-1.5 max-w-64 text-[11px] font-medium text-amber-800" data-testid="room-book-note">{bookNote}</p>}
              </div>
              <button
                type="button"
                onClick={onBook}
                disabled={!bookable || !canBook || busy}
                aria-busy={busy}
                aria-label={`Đặt ngay ${title}`}
                className="inline-flex h-11 min-w-[8rem] cursor-pointer items-center justify-center gap-2 rounded-xl bg-brand-600 px-5 text-sm font-bold text-white shadow-xs transition-colors hover:bg-brand-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-500 motion-reduce:transition-none"
              >
                {busy && <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />}
                {!bookable ? 'Hết chỗ' : busy ? 'Đang xử lý' : 'Đặt ngay'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {amenitiesOpen && amenities.length > 0 && (
        <div id={panelId} className="border-t border-slate-100 bg-slate-50/80 px-4 py-4 md:px-5">
          <AmenityList items={amenities} limit={60} label="Tiện ích phòng" compact columns />
        </div>
      )}
    </div>
  );
};
