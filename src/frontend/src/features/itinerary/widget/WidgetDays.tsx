import React from 'react';
import { Hotel, ExternalLink, MapPin, Clock, Utensils, BedDouble, Footprints, Bus, Camera, Plane, type LucideIcon } from 'lucide-react';
import { hotelTags, placeholderOnError } from './widgetVisuals';
import { isFreeToVisit } from './widgetPlan';
import type { FloatingWidgetController } from './useFloatingWidget';
import type { ItineraryFlightItem, ItinerarySlot } from '../../../types/travel';
import { taxonomyLabel } from '../../../components/assistant/assistantLabels';

const SLOT_PERIOD_LABEL: Record<ItinerarySlot['time'], string> = {
  morning: 'Buổi sáng',
  noon: 'Buổi trưa',
  afternoon: 'Buổi chiều',
  evening: 'Buổi tối',
};

function ItemActions({ actions }: { actions: ReturnType<FloatingWidgetController['itemActions']> }) {
  if (!actions) return null;
  const stop = (run: () => void) => (e: React.MouseEvent) => { e.stopPropagation(); run(); };
  return (
    <div className="flex items-center justify-end gap-2 pt-1" data-testid="itinerary-item-actions">
      {actions.canAddToCart && (
        <button type="button" onClick={stop(actions.addToCart)}
          className="min-h-11 px-3 rounded-xl border border-blue-200 bg-blue-50 text-blue-700 text-xs font-bold hover:bg-blue-100 transition-colors">
          Thêm vào giỏ
        </button>
      )}
      <button type="button" onClick={stop(actions.bookNow)}
        className="min-h-11 px-4 rounded-xl bg-blue-600 text-white text-xs font-bold hover:bg-blue-700 transition-colors">
        Đặt ngay
      </button>
    </div>
  );
}

const FLIGHT_DIRECTION_LABEL: Record<ItineraryFlightItem['direction'], string> = {
  OUTBOUND: 'Chặng đi',
  RETURN: 'Chặng về',
  ROUND_TRIP: 'Vé khứ hồi',
};

function formatDay(isoDate: string): string {
  const [year, month, day] = isoDate.split('-');
  return day && month && year ? `${day}/${month}/${year}` : isoDate;
}

/**
 * Thẻ vé máy bay của lịch trình (AC-AGT-02, user-flow.md §4.2): hãng, số hiệu, giờ đi/đến, bay thẳng, giá × số khách.
 * Mọi giá trị lấy từ `product` của response, không tính lại; chỉ có nút "Đặt ngay" như khách sạn.
 */
function FlightCard({ flight, actions, focused }: {
  flight: ItineraryFlightItem;
  actions: ReturnType<FloatingWidgetController['itemActions']>;
  focused: boolean;
}) {
  const attributes = (flight.product.attributes ?? {}) as Record<string, unknown>;
  const clock = (key: 'departure' | 'arrival') =>
    (attributes[`${key}TimeLocal`] as string | undefined) ?? String(attributes[`${key}At`] ?? '').slice(11, 16);
  const departure = clock('departure');
  const arrival = clock('arrival');
  const carrier = [attributes.airline, attributes.flightNumber].filter(Boolean).join(' · ');
  const dates = flight.returnDate ? `${formatDay(flight.date)} – ${formatDay(flight.returnDate)}` : formatDay(flight.date);
  return (
    <div className="relative group">
      <div className="absolute -left-[31px] sm:-left-[35px] top-3.5 w-6 h-6 sm:w-7 sm:h-7 rounded-full bg-sky-600 text-white border-2 border-white shadow-xs flex items-center justify-center z-10">
        <Plane className="w-3 h-3 sm:w-3.5 sm:h-3.5" />
      </div>
      <div data-product-id={flight.product.id} data-testid="itinerary-flight"
        onClick={() => window.open(`/product/${flight.product.id}`, '_blank', 'noopener,noreferrer')}
        className={`p-3.5 sm:p-4 rounded-2xl bg-white border border-slate-100 cursor-pointer space-y-2${focused ? ' ring-2 ring-blue-500' : ''}`}>
        <div className="flex items-center justify-between gap-2 pb-2 border-b border-slate-100">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-sky-50 text-sky-700 text-xs font-semibold">
            {FLIGHT_DIRECTION_LABEL[flight.direction]} · {dates}
          </span>
          <span className="text-xs font-bold text-slate-800">
            {flight.product.unitPrice != null
              ? `${flight.product.unitPrice.toLocaleString('vi-VN')} ₫/khách × ${flight.passengers}`
              : 'Chưa có giá'}
          </span>
        </div>
        <p className="text-sm font-semibold text-slate-900">{flight.product.name}</p>
        <p className="flex flex-wrap items-center gap-x-2 text-xs text-slate-600">
          {carrier && <span>{carrier}</span>}
          {departure && <span>{arrival ? `${departure} → ${arrival}` : departure}</span>}
          {attributes.nonstop === true && <span className="font-semibold text-emerald-700">Bay thẳng</span>}
        </p>
        <ItemActions actions={actions} />
      </div>
    </div>
  );
}

/** Slot không có sản phẩm (`ActivityNote`) không có ảnh và giá (hop-dong-tich-hop-frontend.md §5); chỉ hiện icon theo loại. */
const ACTIVITY_ICON: Record<string, LucideIcon> = {
  MEAL: Utensils,
  REST: BedDouble,
  FREE_TIME: Footprints,
  TRANSFER: Bus,
  SIGHTSEEING: Camera,
};

export function WidgetDays({ widget }: { widget: FloatingWidgetController }) {
  const { activePlan, activeDayTab, setHoveredCoordinate, setHoveredPointId, focusedProductId, itemActions } = widget;
  const listRef = React.useRef<HTMLDivElement>(null);
  // Bấm tên sản phẩm trong chat: sau khi tab ngày đã đổi, cuộn thẻ vào giữa khung.
  React.useEffect(() => {
    if (!focusedProductId) return;
    const card = Array.from(listRef.current?.querySelectorAll<HTMLElement>('[data-product-id]') ?? [])
      .find((element) => element.dataset.productId === focusedProductId);
    card?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [focusedProductId, activeDayTab, activePlan]);
  if (!activePlan) return null;
  const focusRing = (productId?: string) => (productId && productId === focusedProductId ? ' ring-2 ring-blue-500' : '');
  return (
<div ref={listRef} className="stay-swap-in min-h-0 flex-1 space-y-6 overflow-y-auto overscroll-contain bg-slate-50/70 p-5">
  {/* Render Days (Tất cả các ngày hoặc ngày đang chọn) */}
  {activePlan.days
    .filter((d) => activeDayTab === 0 || d.day === activeDayTab)
    .map((dayItem) => {
      const dayIndex = activePlan.days.findIndex((day) => day.day === dayItem.day);
      const dayStartOrder = activePlan.days
        .slice(0, dayIndex)
        .reduce((total, day) => total + day.slots.length, 0);
      // Khách sạn của đêm ngày này (contract 1.19.0, AC-AGT-04); ngày cuối không có đêm nên lấy khách sạn đêm trước.
      const nightOfDay = Math.min(dayItem.day, Math.max(1, activePlan.days.length - 1));
      const stayForThisDay = activePlan.stays?.find((stay) => {
        const first = stay.fromNight ?? 1;
        return nightOfDay >= first && nightOfDay < first + stay.nights;
      }) ?? activePlan.stay;
      const stayHotelName = stayForThisDay?.product?.name || 'Khách sạn lưu trú';
      // Chặng đi và vé khứ hồi mở đầu ngày đầu tiên; chặng về khép lại ngày cuối.
      const isFirstDay = dayIndex === 0;
      const isLastDay = dayIndex === activePlan.days.length - 1;
      const flightsBefore = isFirstDay ? (activePlan.flights ?? []).filter((flight) => flight.direction !== 'RETURN') : [];
      const flightsAfter = isLastDay ? (activePlan.flights ?? []).filter((flight) => flight.direction === 'RETURN') : [];
      const renderFlight = (flight: ItineraryFlightItem) => (
        <FlightCard key={`${flight.direction}-${flight.productId}`} flight={flight}
          actions={itemActions(flight.product.id)} focused={flight.product.id === focusedProductId} />
      );
      const stayTags = stayForThisDay?.product ? hotelTags(stayForThisDay.product) : [];

      return (
        <div key={dayItem.day} className="space-y-4 pt-1">
          {/* Day Header Badge */}
          <div className="flex items-center pt-1">
            <span className="rounded-lg border border-blue-100 bg-blue-50 px-3 py-1.5 text-sm font-semibold text-blue-800">
              Ngày {dayItem.day}
            </span>
          </div>

          {/* Vertical Timeline Track */}
          <div className="relative pl-6 sm:pl-7 border-l-2 border-dashed border-blue-200 ml-3.5 sm:ml-4 space-y-4 my-2">
            {flightsBefore.map(renderFlight)}
            {/* Khách sạn lưu trú trong lộ trình ngày: ảnh, tag và ghi chú chỉ lấy từ dữ liệu sản phẩm thật */}
            {stayForThisDay?.product && (
              <div className="relative group">
                {/* Timeline Step Node với Icon Khách Sạn */}
                <div className="absolute -left-[31px] sm:-left-[35px] top-3.5 w-6 h-6 sm:w-7 sm:h-7 rounded-full bg-blue-600 text-white border-2 border-white shadow-xs flex items-center justify-center z-10">
                  <Hotel className="w-3 h-3 sm:w-3.5 sm:h-3.5" />
                </div>

                <div
                  data-product-id={stayForThisDay.product.id}
                  onClick={() => {
                    if (stayForThisDay.product) {
                      window.open(`/product/${stayForThisDay.product.id}`, '_blank', 'noopener,noreferrer');
                    }
                  }}
                  onMouseEnter={() => {
                    if (stayForThisDay.product?.coordinates) {
                      setHoveredCoordinate(stayForThisDay.product.coordinates);
                      setHoveredPointId('stay-' + (stayForThisDay.productId || 'default'));
                    }
                  }}
                  onMouseLeave={() => {
                    setHoveredCoordinate(null);
                    setHoveredPointId(null);
                  }}
                  className={`p-3.5 sm:p-4 rounded-2xl bg-white border border-slate-100 cursor-pointer space-y-3${focusRing(stayForThisDay.product.id)}`}
                >
                  {/* Row 1: Header / Giá phòng */}
                  <div className="flex items-center justify-between gap-2 pb-2 border-b border-slate-100">
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-blue-50 text-blue-700 text-xs font-semibold">
                      <Hotel className="w-3.5 h-3.5 text-blue-600" />
                      Khách sạn lưu trú {'dayRange' in stayForThisDay && stayForThisDay.dayRange ? `(${stayForThisDay.dayRange})` : ''}
                    </span>
                    <span className="text-sm font-semibold text-slate-900 tabular-nums">
                      {stayForThisDay.product.unitPrice != null ? `${stayForThisDay.product.unitPrice.toLocaleString('vi-VN')} ₫/đêm` : 'Chưa có giá'}
                    </span>
                  </div>

                  {/* Row 2: Tên khách sạn & Icon link */}
                  <div className="flex items-start justify-between gap-2">
                    <h4 className="text-[15px] sm:text-base font-bold text-slate-900 leading-snug">
                      {stayHotelName}
                    </h4>
                    <div className="p-1 text-slate-400 shrink-0">
                      <ExternalLink className="w-4 h-4" />
                    </div>
                  </div>

                  {/* Row 3: Tag từ attributes thật (hạng sao, hướng biển, bãi biển riêng, hồ bơi); không có thì ẩn */}
                  {stayTags.length > 0 && (
                    <div className="flex items-center gap-1.5 flex-wrap">
                      {stayTags.map((tag) => (
                        <span
                          key={tag}
                          className="inline-flex items-center px-2.5 py-0.5 rounded-lg bg-slate-50 border border-slate-200/80 text-xs font-semibold text-slate-700"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Row 4: Ảnh của chính sản phẩm (imageUrl catalog, thiếu/lỗi thì placeholder theo loại) */}
                  <div className="relative aspect-[16/9] w-full rounded-xl overflow-hidden bg-slate-100 shadow-2xs">
                    <img
                      src={stayForThisDay.product.imageUrl}
                      alt={stayHotelName}
                      onError={placeholderOnError(stayForThisDay.product.taxonomy)}
                      className="w-full h-full object-cover"
                    />
                  </div>

                  {/* Row 5: Ghi chú của lịch trình, chỉ khi backend có */}
                  {stayForThisDay.note && (
                    <p className="text-xs sm:text-sm text-slate-600 leading-relaxed pt-0.5">
                      {stayForThisDay.note}
                    </p>
                  )}
                  {stayForThisDay.product && <ItemActions actions={itemActions(stayForThisDay.product.id)} />}
                </div>
              </div>
            )}

            {/* Các chặng hoạt động trong ngày - ƯU TIÊN VISUAL TO RÕ */}
            {dayItem.slots.map((slot, sIdx) => {
              const stepNumber = dayStartOrder + sIdx + 1;
              const slotPeriod = SLOT_PERIOD_LABEL[slot.time];

              const stopTitle = slot.activityTitle || slot.product?.name || 'Hoạt động tự do';
              const locationTitle = slot.locationName || slot.address || '';
              const ActivityIcon = !slot.product && slot.activityType ? ACTIVITY_ICON[slot.activityType] : undefined;

              return (
                <div key={sIdx} className="relative">
                  {/* Timeline Step Node */}
                  <div className="absolute -left-[31px] sm:-left-[35px] top-3.5 w-6 h-6 sm:w-7 sm:h-7 rounded-full bg-blue-600 text-white border-2 border-white shadow-xs flex items-center justify-center text-[11px] sm:text-xs font-black z-10">
                    {stepNumber}
                  </div>

                  {/* Stop Card - Layout ưu tiên VISUAL TO RÕ - KHÔNG HOVER ANIMATIONS */}
                  <div
                    data-product-id={slot.product?.id}
                    onClick={() => {
                      if (slot.product) {
                        window.open(`/product/${slot.product.id}`, '_blank', 'noopener,noreferrer');
                      }
                    }}
                    onMouseEnter={() => {
                      const coord = slot.coordinates || slot.product?.coordinates;
                      if (coord) {
                        setHoveredCoordinate(coord);
                        setHoveredPointId(`day-${dayItem.day}-slot-${slot.time}-${stepNumber}`);
                      }
                    }}
                    onMouseLeave={() => {
                      setHoveredCoordinate(null);
                      setHoveredPointId(null);
                    }}
                    className={`p-3.5 sm:p-4 rounded-2xl bg-white border border-slate-100 space-y-3 ${slot.product ? 'cursor-pointer' : ''}${focusRing(slot.product?.id)}`}
                  >
                    {/* Row 1: Buổi + Phân loại dịch vụ + Địa điểm */}
                    <div className="flex items-center justify-between gap-2 pb-2 border-b border-slate-100 flex-wrap">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-lg bg-blue-50 text-blue-700 text-xs font-bold">
                          <Clock className="w-3.5 h-3.5 text-blue-600" />
                          {slotPeriod}
                        </span>
                        {slot.product && (
                          <span className="px-2.5 py-0.5 rounded-lg bg-slate-100 text-slate-700 text-xs font-semibold">
                            {taxonomyLabel(slot.product.taxonomy)}
                          </span>
                        )}
                        {ActivityIcon && (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-lg bg-slate-100 text-slate-700 text-xs font-semibold">
                            <ActivityIcon className="w-3.5 h-3.5" aria-hidden="true" />
                            {stopTitle}
                          </span>
                        )}
                      </div>
                      {locationTitle && (
                        <span className="text-xs text-slate-500 font-medium truncate max-w-[55%] flex items-center gap-1 justify-end">
                          <MapPin className="w-3 h-3 text-slate-400 shrink-0" />
                          <span className="truncate">{locationTitle}</span>
                        </span>
                      )}
                    </div>

                    {/* Row 2: Tên chặng hoạt động & Giá vé */}
                    <div className="flex items-start justify-between gap-2">
                      <h4 className="text-[15px] sm:text-base font-bold text-slate-900 leading-snug">
                        {stopTitle}
                      </h4>
                      <div className="flex items-center gap-2 shrink-0">
                        {slot.product && isFreeToVisit(slot.product) ? (
                          <span className="text-xs font-bold text-emerald-700">Tham quan tự do</span>
                        ) : slot.product && slot.product.unitPrice != null && (
                          <span className="text-sm font-semibold text-slate-900 tabular-nums">
                            {slot.product.unitPrice.toLocaleString('vi-VN')} ₫
                          </span>
                        )}
                        {slot.product && (
                          <div className="p-1 text-slate-400">
                            <ExternalLink className="w-4 h-4" />
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Row 3: Ảnh của chính sản phẩm (imageUrl catalog, lỗi thì placeholder); slot không có sản phẩm thì không có ảnh */}
                    {slot.product && (
                      <div className="relative aspect-[16/9] w-full rounded-xl overflow-hidden shadow-2xs bg-slate-100">
                        <img
                          src={slot.product.imageUrl}
                          alt={stopTitle}
                          onError={placeholderOnError(slot.product.taxonomy)}
                          className="w-full h-full object-cover"
                        />
                      </div>
                    )}

                    {/* Row 4: Ghi chú súc tích */}
                    <p className="text-xs sm:text-sm text-slate-600 leading-relaxed pt-0.5">
                      {slot.note}
                    </p>
                    {slot.product && <ItemActions actions={itemActions(slot.product.id)} />}
                  </div>
                </div>
              );
            })}
            {flightsAfter.map(renderFlight)}
          </div>
        </div>
      );
    })}
</div>
  );
}
