import React from 'react';
import { Hotel, ExternalLink, MapPin, Clock } from 'lucide-react';
import { getHotelVisuals, getSlotVisualUrl } from './widgetVisuals';
import type { FloatingWidgetController } from './useFloatingWidget';

export function WidgetDays({ widget }: { widget: FloatingWidgetController }) {
  const { activePlan, activeDayTab, setHoveredCoordinate, setHoveredPointId } = widget;
  if (!activePlan) return null;
  return (
<div className="flex-1 overflow-y-auto p-4 space-y-4 bg-white">
  {/* Render Days (Tất cả các ngày hoặc ngày đang chọn) */}
  {activePlan.days
    .filter((d) => activeDayTab === 0 || d.day === activeDayTab)
    .map((dayItem) => {
      const dayIndex = activePlan.days.findIndex((day) => day.day === dayItem.day);
      const dayStartOrder = activePlan.days
        .slice(0, dayIndex)
        .reduce((total, day) => total + day.slots.length, 0);
      const stayForThisDay = activePlan.stays && activePlan.stays.length >= 2
        ? (dayItem.day <= Math.ceil(activePlan.days.length / 2) ? activePlan.stays[0] : activePlan.stays[1])
        : activePlan.stay;
      const stayHotelName = stayForThisDay?.product?.name || 'Khách sạn lưu trú';
      const hotelVisuals = stayForThisDay?.product ? getHotelVisuals(stayForThisDay.product, activePlan.intent.destination) : null;

      return (
        <div key={dayItem.day} className="space-y-4 pt-1">
          {/* Day Header Badge */}
          <div className="flex items-center pt-1">
            <span className="px-3.5 py-1.5 rounded-xl bg-blue-600 text-white text-sm font-bold shadow-xs">
              Ngày {dayItem.day}
            </span>
          </div>

          {/* Vertical Timeline Track */}
          <div className="relative pl-6 sm:pl-7 border-l-2 border-dashed border-blue-200 ml-3.5 sm:ml-4 space-y-4 my-2">
            {/* Khách sạn lưu trú được tích hợp trực tiếp vào lộ trình ngày - Visual to rõ, ít nhất 2 ảnh */}
            {stayForThisDay?.product && hotelVisuals && (
              <div className="relative group">
                {/* Timeline Step Node với Icon Khách Sạn */}
                <div className="absolute -left-[31px] sm:-left-[35px] top-3.5 w-6 h-6 sm:w-7 sm:h-7 rounded-full bg-indigo-600 text-white border-2 border-white shadow-xs flex items-center justify-center z-10">
                  <Hotel className="w-3 h-3 sm:w-3.5 sm:h-3.5" />
                </div>

                {/* Hotel Card trong Lộ trình - Layout ưu tiên VISUAL TO RÕ (Ít nhất 2 ảnh: Biệt Thự & Hồ Bơi) */}
                <div
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
                  className="p-3.5 sm:p-4 rounded-2xl bg-white border border-slate-100 cursor-pointer space-y-3"
                >
                  {/* Row 1: Header / Giá phòng */}
                  <div className="flex items-center justify-between gap-2 pb-2 border-b border-slate-100">
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-indigo-50 text-indigo-700 text-xs font-bold">
                      <Hotel className="w-3.5 h-3.5 text-indigo-600" />
                      Khách sạn lưu trú {'dayRange' in stayForThisDay && stayForThisDay.dayRange ? `(${stayForThisDay.dayRange})` : ''}
                    </span>
                    <span className="text-sm font-black text-indigo-950 font-mono">
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

                  {/* Row 3: Hot Feature Tags trực quan: Điểm đến, Biệt Thự, Hồ Bơi, View Biển... */}
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {hotelVisuals.tags.map((tag, tIdx) => (
                      <span
                        key={tIdx}
                        className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-lg bg-slate-50 border border-slate-200/80 text-xs font-semibold text-slate-700"
                      >
                        <span>{tag.icon}</span>
                        <span>{tag.label}</span>
                      </span>
                    ))}
                  </div>

                  {/* Row 4: KHÔNG GIAN HÌNH ẢNH TO RÕ (LƯỚI 2 ẢNH: BIỆT THỰ + HỒ BƠI/VIEW BIỂN) - KHÓA TỶ LỆ KHUNG HÌNH CHUẨN */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-1">
                    {hotelVisuals.images.map((img, iIdx) => (
                      <div
                        key={iIdx}
                        className="relative aspect-[4/3] sm:aspect-[16/10] w-full rounded-xl overflow-hidden bg-slate-100 shadow-2xs"
                      >
                        <img
                          src={img.url}
                          alt={stayHotelName}
                          className="w-full h-full object-cover"
                        />
                      </div>
                    ))}
                  </div>

                  {/* Row 5: Ghi chú súc tích */}
                  <p className="text-xs sm:text-sm text-slate-600 leading-relaxed pt-0.5">
                    {stayForThisDay.note || 'Khách sạn lưu trú tiêu chuẩn cao cấp, điểm xuất phát và nghỉ ngơi thuận tiện cho cả ngày.'}
                  </p>
                </div>
              </div>
            )}

            {/* Các chặng hoạt động trong ngày - ƯU TIÊN VISUAL TO RÕ */}
            {dayItem.slots.map((slot, sIdx) => {
              const stepNumber = dayStartOrder + sIdx + 1;
              const formattedTimeRange = slot.timeRange || (
                slot.time === 'morning' ? '08:30 - 11:30' :
                slot.time === 'noon' ? '11:45 - 13:30' :
                slot.time === 'afternoon' ? '14:30 - 17:30' : '18:00 - 21:00'
              );

              const stopTitle = slot.activityTitle || (slot.product ? slot.product.name : 'Hoạt động trải nghiệm');
              const locationTitle = slot.locationName || (slot.product ? slot.product.name : slot.address ? slot.address.split(',')[0] : 'Khu vực trung tâm');
              const slotImgUrl = getSlotVisualUrl(slot, activePlan.intent.destination);

              return (
                <div key={sIdx} className="relative">
                  {/* Timeline Step Node */}
                  <div className="absolute -left-[31px] sm:-left-[35px] top-3.5 w-6 h-6 sm:w-7 sm:h-7 rounded-full bg-blue-600 text-white border-2 border-white shadow-xs flex items-center justify-center text-[11px] sm:text-xs font-black z-10">
                    {stepNumber}
                  </div>

                  {/* Stop Card - Layout ưu tiên VISUAL TO RÕ - KHÔNG HOVER ANIMATIONS */}
                  <div
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
                    className={`p-3.5 sm:p-4 rounded-2xl bg-white border border-slate-100 space-y-3 ${slot.product ? 'cursor-pointer' : ''}`}
                  >
                    {/* Row 1: Khung giờ + Phân loại dịch vụ + Địa điểm */}
                    <div className="flex items-center justify-between gap-2 pb-2 border-b border-slate-100 flex-wrap">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-lg bg-blue-50 text-blue-700 text-xs font-black font-mono tracking-wide">
                          <Clock className="w-3.5 h-3.5 text-blue-600" />
                          {formattedTimeRange}
                        </span>
                        {slot.product && (
                          <span className="px-2.5 py-0.5 rounded-lg bg-slate-100 text-slate-700 text-xs font-semibold">
                            {slot.product.taxonomy === 'attraction' ? '🎡 Vé vui chơi giải trí' :
                             slot.product.taxonomy === 'combo' ? '✨ Combo & Show' : '🛎️ Dịch vụ nghỉ dưỡng'}
                          </span>
                        )}
                      </div>
                      <span className="text-xs text-slate-500 font-medium truncate max-w-[55%] flex items-center gap-1 justify-end">
                        <MapPin className="w-3 h-3 text-slate-400 shrink-0" />
                        <span className="truncate">{locationTitle}</span>
                      </span>
                    </div>

                    {/* Row 2: Tên chặng hoạt động & Giá vé */}
                    <div className="flex items-start justify-between gap-2">
                      <h4 className="text-[15px] sm:text-base font-bold text-slate-900 leading-snug">
                        {stopTitle}
                      </h4>
                      <div className="flex items-center gap-2 shrink-0">
                        {slot.product && slot.product.unitPrice != null && (
                          <span className="text-sm font-black font-mono text-indigo-950">
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

                    {/* Row 3: KHÔNG GIAN ẢNH TO RÕ CỦA CHẶNG HOẠT ĐỘNG - TỶ LỆ CHUẨN 16:9 KHÔNG KÉO DÃN KHI CO DÃN CỘT */}
                    <div className="relative aspect-[16/9] w-full rounded-xl overflow-hidden shadow-2xs bg-slate-100">
                      <img
                        src={slotImgUrl}
                        alt={stopTitle}
                        className="w-full h-full object-cover"
                      />
                    </div>

                    {/* Row 4: Ghi chú súc tích */}
                    <p className="text-xs sm:text-sm text-slate-600 leading-relaxed pt-0.5">
                      {slot.note}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      );
    })}
</div>
  );
}
