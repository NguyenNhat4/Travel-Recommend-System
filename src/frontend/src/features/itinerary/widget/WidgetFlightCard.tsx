import React from 'react';
import { BadgeCheck, Plane } from 'lucide-react';
import type { ItineraryFlightItem } from '../../../types/travel';
import { flightSegments, formatDuration, type FlightEnd, type FlightSegment } from './widgetFlight';

const vnd = new Intl.NumberFormat('vi-VN');

function End({ end }: { end: FlightEnd }) {
  return (
    <div className="flex min-w-0 flex-1 flex-col items-center rounded-xl border border-sky-200 bg-white px-2 py-2.5 text-center">
      {end.day && <span className="text-xs text-slate-600">{end.day}</span>}
      <span className="text-lg font-bold tabular-nums text-blue-600">{end.time ?? '--:--'}</span>
      <span className="line-clamp-1 text-xs text-slate-700">{end.place}</span>
    </div>
  );
}

function Segment({ segment }: { segment: FlightSegment }) {
  return (
    <div className="space-y-2">
      <div className="flex items-stretch gap-2">
        <End end={segment.departure} />
        <div className="flex w-24 shrink-0 flex-col items-center justify-center gap-0.5 text-center">
          {segment.airline && <span className="line-clamp-2 text-xs font-semibold leading-tight text-slate-800">{segment.airline}</span>}
          <span className="flex w-full items-center gap-1 text-slate-400" aria-hidden="true">
            <span className="h-px flex-1 bg-slate-300" /><Plane className="h-3.5 w-3.5" /><span className="h-px flex-1 bg-slate-300" />
          </span>
          {segment.durationMinutes != null && <span className="text-xs tabular-nums text-slate-600">{formatDuration(segment.durationMinutes)}</span>}
          {segment.nonstop && <span className="text-xs text-slate-600">Bay thẳng</span>}
        </div>
        <End end={segment.arrival} />
      </div>
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-600">
        <span className="rounded-md bg-emerald-50 px-1.5 py-0.5 font-semibold text-emerald-700">{segment.label}</span>
        {[segment.flightNumber, segment.departure.time].filter(Boolean).join(' · ')}
      </p>
    </div>
  );
}

/**
 * Thẻ vé máy bay trong câu trả lời (AC-AGT-02, user-flow §4.2): hãng, số hiệu, giờ và nơi đi/đến, thời gian bay, bay thẳng,
 * giá × số khách và nút "Đặt ngay". Vé do luật chọn (bay thẳng, rẻ, giờ hợp lý) nên nhãn là "Đã chọn cho lịch", không phải
 * "tốt nhất". Catalog không có hạng vé và hành lý nên thẻ không hiện hai thông tin này.
 */
export function WidgetFlightCard({ flight, onOpen, onBookNow }: {
  flight: ItineraryFlightItem;
  onOpen: () => void;
  /** Không có khi vé chưa đặt được trong lịch này. */
  onBookNow?: () => void;
}) {
  const price = flight.product.unitPrice;
  return (
    <article data-product-id={flight.product.id} aria-label={`Vé máy bay ${flight.product.name}`}
      className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xs">
      <p className="flex items-center justify-center gap-1.5 bg-gradient-to-r from-cyan-100 to-sky-50 py-1 text-xs font-semibold text-slate-700">
        <BadgeCheck className="h-3.5 w-3.5 text-blue-600" aria-hidden="true" />Đã chọn cho lịch
      </p>
      <button type="button" onClick={onOpen}
        className="block w-full space-y-3 p-3 text-left focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-blue-600">
        {flightSegments(flight).map((segment) => <Segment key={segment.label} segment={segment} />)}
      </button>
      <div className="flex items-center justify-between gap-3 border-t border-slate-100 px-3 py-2.5">
        <p className="text-xs text-slate-500 tabular-nums">
          {price != null
            ? <><span className="text-base font-bold text-slate-900">{vnd.format(price)} ₫</span>/khách × {flight.passengers}</>
            : 'Chưa có giá'}
        </p>
        {onBookNow && (
          <button type="button" onClick={onBookNow}
            className="min-h-11 shrink-0 rounded-xl bg-blue-600 px-4 text-xs font-bold text-white transition-colors hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600">
            Đặt ngay
          </button>
        )}
      </div>
    </article>
  );
}
