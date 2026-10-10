import React from 'react';
import dynamic from 'next/dynamic';
import { MapPin, Calendar, Users } from 'lucide-react';
import { WidgetDays } from './WidgetDays';
import { WidgetProductDetail } from './WidgetProductDetail';
import { stayCardKey } from './widgetPlan';
import type { FloatingWidgetController } from './useFloatingWidget';


// Dynamically load the Leaflet + OSM/OSRM itinerary map to avoid SSR issues.
const ItineraryMap = dynamic(
  () => import('../../../components/assistant/ItineraryMap').then((module) => module.ItineraryMap),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full min-h-[350px] items-center justify-center bg-slate-50 text-sm text-slate-500">
        Đang tải bản đồ lộ trình…
      </div>
    ),
  }
);

export function WidgetPlanPanel({ widget }: { widget: FloatingWidgetController }) {
  const { activePlan, activeDayTab, setActiveDayTab, itemActions, hoveredCoordinate, hoveredPointId,
    selectedProduct, closeProductDetail, addSelectedToCart, selectedCanAddToCart, bookSelectedNow,
    previewedStay, cancelStayPreview, chooseStayOption } = widget;
  if (!activePlan) return null;
  const stayKey = stayCardKey({ plan: activePlan });
  return (
<div className="grid grid-cols-1 md:grid-cols-2 w-full h-full min-w-0 overflow-hidden divide-x divide-slate-200/70">
  {/* PHẦN Ở GIỮA: DANH SÁCH LỘ TRÌNH (CÓ HEADER) */}
  {/* Bấm thẻ trong lời diễn giải: panel chi tiết thay chỗ danh sách ngày, bản đồ vẫn hiện và focus đúng điểm */}
  {selectedProduct ? (
    <div className="h-full overflow-hidden">
      <WidgetProductDetail key={selectedProduct.productId} productId={selectedProduct.productId}
        summary={selectedProduct.summary} onClose={closeProductDetail} onAddToCart={selectedCanAddToCart ? addSelectedToCart : undefined} onBookNow={bookSelectedNow}
        cartAddState={widget.cartAddStates[selectedProduct.productId]} />
    </div>
  ) : (
  <section aria-label="Lịch trình theo ngày" className="flex flex-col h-full bg-white overflow-hidden">
    {/* Header của phần ở giữa */}
    <div className="space-y-4 border-b border-slate-200/70 bg-white p-5 shrink-0">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div>
          <h2 className="font-sans text-lg font-semibold leading-snug tracking-tight text-slate-900">
            {activePlan.title}
          </h2>
          <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2 text-xs text-slate-500">
            <span className="flex items-center gap-1.5">
              <MapPin className="w-3.5 h-3.5 text-slate-400" />
              {activePlan.intent.destination}
            </span>
            <span className="flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5 text-slate-400" />
              {activePlan.intent.days} ngày
            </span>
            {activePlan.partyLabel && (
              <span className="flex items-center gap-1.5">
                <Users className="w-3.5 h-3.5 text-slate-400" />
                {activePlan.partyLabel}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Day Tabs Selector */}
      <div className="flex items-center gap-1.5 bg-slate-100/80 p-1 rounded-xl overflow-x-auto no-scrollbar">
        <button
          onClick={() => setActiveDayTab(0)}
          aria-pressed={activeDayTab === 0}
          className={`min-h-11 px-3.5 py-1.5 rounded-lg text-sm font-semibold transition-colors cursor-pointer whitespace-nowrap focus-visible:outline-2 focus-visible:outline-brand-600 ${
            activeDayTab === 0
              ? 'bg-brand-600 text-white shadow-xs'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          Tất cả
        </button>
        {activePlan.days.map((d) => (
          <button
            key={d.day}
            onClick={() => setActiveDayTab(d.day)}
            aria-pressed={activeDayTab === d.day}
            className={`min-h-11 px-3.5 py-1.5 rounded-lg text-sm font-semibold transition-colors cursor-pointer whitespace-nowrap focus-visible:outline-2 focus-visible:outline-brand-600 ${
              activeDayTab === d.day
                ? 'bg-brand-600 text-white shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Ngày {d.day}
          </button>
        ))}
      </div>
    </div>

    {/* Xem trước một thẻ khách sạn (AC-AGT-04): chưa đổi lịch đã lưu, nên ghi rõ và cho đổi hoặc quay lại ngay tại đây. */}
    {previewedStay && (
      <div role="status" className="stay-swap-in flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-blue-100 bg-blue-50 px-5 py-2.5">
        <p className="min-w-0 text-sm text-blue-900">
          <span className="font-semibold">Đang xem trước</span> {previewedStay.card.hotels[0]?.name}
          <span className="text-blue-700"> · chưa đổi</span>
        </p>
        <div className="flex gap-2">
          <button type="button" onClick={cancelStayPreview}
            className="min-h-9 rounded-lg px-3 text-sm font-semibold text-blue-700 hover:bg-blue-100 focus-visible:outline-2 focus-visible:outline-blue-600">
            Quay lại
          </button>
          <button type="button" onClick={() => { void chooseStayOption(previewedStay.message, previewedStay.card); }}
            className="min-h-9 rounded-lg bg-blue-600 px-3 text-sm font-semibold text-white hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600">
            Đổi sang khách sạn này
          </button>
        </div>
      </div>
    )}
    {/* Đổi khách sạn (hàng thẻ "Phương án khác"): lịch mới trượt vào thay vì thay chữ tại chỗ. */}
    <WidgetDays key={stayKey} widget={widget} />

    {/* Footer của phần lịch trình: tổng tiền. Không có thanh toán gộp: mỗi mục đặt bằng nút riêng của nó. */}
    <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-t border-slate-200/70 bg-white p-5">
      <div>
        <span className="block text-xs font-medium text-slate-500">
          Chi phí sản phẩm
        </span>
        {activePlan.totalEstimatedPrice != null ? (
          <>
            <span key={stayKey} className="stay-swap-in mt-1 block text-xl font-semibold tracking-tight text-slate-900 tabular-nums">
              {new Intl.NumberFormat('vi-VN').format(activePlan.totalEstimatedPrice)} ₫
            </span>
            <span className="mt-1 block text-xs leading-relaxed text-slate-500">
              Chưa gồm ăn uống, đi lại và phát sinh
            </span>
          </>
        ) : (
          <span
            className="text-sm font-bold text-slate-500"
            title="Một số mục có vé trong lịch trình chưa có giá nên không cộng được tổng; giá thiếu không được coi là 0."
          >
            Chưa tính được
          </span>
        )}
      </div>
    </div>
  </section>

  )}

  {/* Bản đồ giữ nguyên bên cạnh lịch trình/chi tiết; header chừa chỗ cho nút đóng và thu nhỏ widget. */}
  <div className="relative flex h-full min-w-0 flex-col overflow-hidden bg-slate-100">
    <div className="flex min-h-20 shrink-0 items-center border-b border-slate-200/70 bg-white px-5 py-3 pr-28">
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold text-slate-900">Bản đồ lộ trình</p>
        <p className="mt-0.5 truncate text-xs text-slate-500">{activePlan.intent.destination}</p>
      </div>
    </div>
    <div className="min-h-0 flex-1">
    <ItineraryMap
      plan={activePlan}
      activeDay={activeDayTab}
      onSelectDay={setActiveDayTab}
      itemActions={(p) => itemActions(p.id)}
      focusedCoordinate={hoveredCoordinate}
      focusedPointId={hoveredPointId}
      overview={Boolean(previewedStay)}
      className="w-full h-full flex-1"
    />
    </div>
  </div>
</div>
  );
}
