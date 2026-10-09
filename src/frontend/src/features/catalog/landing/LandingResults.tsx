'use client';

import React from 'react';
import { GroupResults } from '../../../components/search/GroupResults';
import { useAssistant } from '../../../context/AssistantProvider';
import { useTravel } from '../../../context/TravelContext';
import { parseGroupParam, type Guests, type Stay } from '../../../services/search';
import { describeTripContext, serializeTripContext, type TripContext } from '../../search/tripContext';
import { buildSearchHref, isDefaultQuery } from './searchHref';
import type { VerticalTab } from './verticals';

interface LandingResultsProps {
  tab: VerticalTab;
  /** `?q=` của URL; có mặt nghĩa là đang tìm. */
  query: string;
  destination?: string;
  trip: TripContext;
}

/**
 * Số khách của tấm tìm kiếm thành `travelContext.guests`. Backend so tổng `adults + children` với sức chứa của MỘT hạng phòng
 * (hay một đơn vị), nên nhiều phòng thì chia đều (làm tròn lên) thay vì gửi cả đoàn: 4 người ở 2 phòng cần phòng chứa được 2.
 * Không có số người lớn trên URL thì không lọc.
 */
export function guestsOf(trip: TripContext): Guests | undefined {
  if (!trip.adults) return undefined;
  const rooms = trip.rooms && trip.rooms > 1 ? trip.rooms : 1;
  if (rooms === 1) return { adults: trip.adults, children: trip.children ?? 0 };
  return { adults: Math.ceil((trip.adults + (trip.children ?? 0)) / rooms), children: 0 };
}

/**
 * Ngày của tấm tìm kiếm thành `travelContext.checkIn` / `checkOut`. Chỉ ngày nhận / ngày dùng thì không có `checkOut`
 * (vé, combo một ngày; khách sạn một đêm). Không có ngày hợp lệ trên URL thì không lọc.
 */
export function stayOf(trip: TripContext): Stay | undefined {
  if (!trip.checkIn) return undefined;
  return trip.checkOut ? { checkIn: trip.checkIn, checkOut: trip.checkOut } : { checkIn: trip.checkIn };
}

/**
 * Kết quả tìm kiếm ngay dưới tấm tìm kiếm của trang danh mục (`/hotels`, `/experiences`, `/combos`), chỉ trong loại
 * dịch vụ của tab đang chọn. Dùng lại danh sách của `/search` (`GroupResults`): sắp xếp, lọc sao và giá (khách sạn),
 * "Xem thêm". Số khách (sức chứa) và ngày (luật đặt phòng, lịch phòng, cửa sổ mở bán) là bộ lọc cứng ở API; cả hai cũng
 * điền sẵn hộp đặt ở trang chi tiết.
 */
export function LandingResults({ tab, query, destination, trip }: LandingResultsProps) {
  const { navigate } = useTravel();
  const { openFloatingWidget } = useAssistant();
  const group = parseGroupParam(tab.taxonomy);
  if (!group) return null;

  const typed = !isDefaultQuery(query);
  const title = typed ? `Kết quả cho “${query}”` : `${tab.label}${destination ? ` ${tab.atWord} ${destination}` : ''}`;
  const context = describeTripContext(trip);

  const clearDestination = () => navigate(buildSearchHref({
    taxonomy: tab.taxonomy, origin: '', location: typed ? query : '', destination: null, trip,
  }));

  return (
    <section aria-label={`Kết quả ${tab.noun}`} className="relative z-10 -mt-8 rounded-t-4xl bg-white pb-10 pt-8">
      <div className="mx-auto max-w-7xl space-y-5 px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col justify-between gap-1 sm:flex-row sm:items-baseline">
          <h2 className="text-xl font-black text-slate-900 sm:text-2xl">{title}</h2>
          {context && <span className="text-xs font-semibold text-slate-500">{context}</span>}
        </div>
        <GroupResults
          key={`${tab.taxonomy}|${query}|${destination ?? ''}`}
          group={group}
          taxonomy={tab.taxonomy}
          guests={guestsOf(trip)}
          stay={stayOf(trip)}
          label={tab.label}
          embedded
          query={query}
          destination={destination ?? null}
          tripQuery={serializeTripContext(trip)}
          onClearDestination={clearDestination}
          onAskAssistant={() => openFloatingWidget(typed ? query : undefined)}
        />
      </div>
    </section>
  );
}
