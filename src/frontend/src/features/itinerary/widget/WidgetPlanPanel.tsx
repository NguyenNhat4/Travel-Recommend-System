import React from 'react';
import dynamic from 'next/dynamic';
import { MapPin, Calendar, Users, Loader2, ArrowRight } from 'lucide-react';
import { WidgetDays } from './WidgetDays';
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
  const { activePlan, activeDayTab, setActiveDayTab, isCheckingOut,
    handleCheckoutPlan, addToCart, hoveredCoordinate, hoveredPointId } = widget;
  if (!activePlan) return null;
  return (
<div className="grid grid-cols-1 md:grid-cols-2 w-full h-full overflow-hidden divide-x divide-slate-100">
  {/* PHẦN Ở GIỮA: DANH SÁCH LỘ TRÌNH (CÓ HEADER) */}
  <div className="flex flex-col h-full bg-white overflow-hidden">
    {/* Header của phần ở giữa */}
    <div className="p-4 bg-white border-b border-slate-100 space-y-3 shrink-0 shadow-2xs">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div>
          <h2 className="text-base font-bold text-slate-900">
            {activePlan.title}
          </h2>
          <div className="flex items-center gap-3 text-sm text-slate-500 mt-1">
            <span className="flex items-center gap-1.5">
              <MapPin className="w-3.5 h-3.5 text-slate-400" />
              {activePlan.intent.destination}
            </span>
            <span className="flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5 text-slate-400" />
              {activePlan.intent.days} ngày
            </span>
            <span className="flex items-center gap-1.5">
              <Users className="w-3.5 h-3.5 text-slate-400" />
              {activePlan.intent.party === 'family_with_kids' ? 'Gia đình' : 'Cặp đôi'}
            </span>
          </div>
        </div>
      </div>

      {/* Day Tabs Selector */}
      <div className="flex items-center gap-1.5 bg-slate-100/80 p-1 rounded-xl overflow-x-auto no-scrollbar">
        <button
          onClick={() => setActiveDayTab(0)}
          className={`px-3.5 py-1.5 rounded-lg text-sm font-bold transition-all cursor-pointer whitespace-nowrap ${
            activeDayTab === 0
              ? 'bg-blue-600 text-white shadow-xs'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          Tất cả
        </button>
        {activePlan.days.map((d) => (
          <button
            key={d.day}
            onClick={() => setActiveDayTab(d.day)}
            className={`px-3.5 py-1.5 rounded-lg text-sm font-bold transition-all cursor-pointer whitespace-nowrap ${
              activeDayTab === d.day
                ? 'bg-blue-600 text-white shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Ngày {d.day}
          </button>
        ))}
      </div>
    </div>

    <WidgetDays widget={widget} />

    {/* Footer của phần lịch trình: Tổng tiền & Nút Thanh Toán */}
    <div className="p-4 bg-white border-t border-slate-100 flex items-center justify-between gap-4 shrink-0 shadow-xs">
      <div>
        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">
          Chi phí sản phẩm
        </span>
        {activePlan.totalEstimatedPrice != null ? (
          <>
            <span className="text-lg font-black text-blue-900 font-mono">
              {new Intl.NumberFormat('vi-VN').format(activePlan.totalEstimatedPrice)} ₫
            </span>
            <span className="block text-[10px] text-slate-400 leading-tight">
              Chưa gồm ăn uống, đi lại và phát sinh
            </span>
          </>
        ) : (
          <span
            className="text-sm font-bold text-slate-500"
            title="Một số mục trong lịch trình chưa có giá nên không cộng được tổng; giá thiếu không được coi là 0."
          >
            Chưa tính được
          </span>
        )}
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={handleCheckoutPlan}
          disabled={isCheckingOut}
          aria-busy={isCheckingOut}
          className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 disabled:opacity-60 disabled:cursor-wait text-white text-sm font-bold rounded-xl shadow-xs transition flex items-center gap-2 cursor-pointer"
        >
          <span>{isCheckingOut ? 'Đang thêm vào giỏ…' : 'Thanh toán'}</span>
          {isCheckingOut ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
        </button>
      </div>
    </div>
  </div>

  {/* PHẦN MAP BÊN PHẢI (KHÔNG CÓ HEADER - FULL HEIGHT) */}
  <div className="h-full relative overflow-hidden bg-slate-100 flex flex-col">
    <ItineraryMap
      plan={activePlan}
      activeDay={activeDayTab}
      onSelectDay={setActiveDayTab}
      onAddToCart={(p) => addToCart(p, 2)}
      focusedCoordinate={hoveredCoordinate}
      focusedPointId={hoveredPointId}
      className="w-full h-full flex-1"
    />
  </div>
</div>
  );
}
