'use client';

import React from 'react';
import { X, List, Compass, Maximize2, Minimize2, ChevronLeft, ChevronRight } from 'lucide-react';
import { useWidgetFocus } from './useWidgetFocus';
import { useFloatingWidget } from './useFloatingWidget';
import { WidgetLauncher } from './WidgetLauncher';
import { WidgetHistory } from './WidgetHistory';
import { WidgetChat } from './WidgetChat';
import { WidgetPlanPanel } from './WidgetPlanPanel';
import { WidgetPlanEmpty } from './WidgetPlanEmpty';
import { WidgetProductDetail } from './WidgetProductDetail';

export function FloatingWidget() {
  const widget = useFloatingWidget();
  const { isOpen, setIsOpen, isExpanded, setIsExpanded, isHistoryOpen, setIsHistoryOpen,
    activePlan, isChatCollapsed, setIsChatCollapsed, handleQuickPrompt,
    selectedProduct, closeProductDetail, addSelectedToCart, selectedCanAddToCart, bookSelectedNow } = widget;
  const dialogRef = useWidgetFocus(isOpen, isExpanded, isHistoryOpen);
  return (
    <>
      {!isOpen && <WidgetLauncher onOpen={() => setIsOpen(true)} />}

      {/* ========================================================================= */}
      {/* 2. CHẾ ĐỘ SIDEBAR (Mở trượt từ MÉP TRÁI)                                   */}
      {/* ========================================================================= */}
      {isOpen && !isExpanded && (
        <div ref={dialogRef} role="dialog" aria-modal="true" aria-label="Trợ lý du lịch AI" className="fixed inset-0 z-50 overflow-hidden">
          {/* Backdrop mờ phía sau - bấm vào để đóng */}
          <div
            onClick={() => setIsOpen(false)}
            className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs transition-opacity duration-300"
          />

          {/* Slide-over Drawer từ mép trái màn hình - Chiếm 4 phần (4/12) trên desktop */}
          <div className="fixed inset-y-0 left-0 w-full sm:w-[420px] lg:w-4/12 min-w-0 lg:min-w-[380px] max-w-[640px] bg-white shadow-2xl flex flex-col border-r border-slate-100 z-10 animate-in slide-in-from-left duration-300 ease-out">
            {/* Top Bar tối giản khi chưa mở rộng: Không Header xanh, giữ icon List + mock title bên trái, icon Mở rộng & icon Tắt bên phải */}
            <div className="flex min-h-20 items-center justify-between border-b border-slate-200/70 bg-white px-4 py-3">
              {/* Bên trái: Icon List + Mock Title */}
              <div className="flex items-center space-x-2 text-slate-700 min-w-0 flex-1 mr-2">
                <button
                  type="button"
                  onClick={() => setIsHistoryOpen(prev => !prev)}
                  className="min-h-11 min-w-11 p-1.5 text-slate-600 hover:text-slate-900 rounded-lg hover:bg-slate-100 transition cursor-pointer shrink-0"
                  title="Danh sách hội thoại & Tạo chat mới"
                  aria-label="Danh sách hội thoại & Tạo chat mới"
                >
                  <List className="w-4 h-4" />
                </button>
                <WidgetTitle title={activePlan?.title} />
              </div>

              {/* Bên phải: 2 icon Mở rộng (Maximize2) và icon Tắt (X) */}
              <div className="flex items-center space-x-1 shrink-0">
                <button
                  type="button"
                  onClick={() => setIsExpanded(true)}
                  className="min-h-11 min-w-11 p-1.5 text-slate-600 hover:text-slate-900 rounded-lg hover:bg-slate-100 transition cursor-pointer"
                  title="Mở rộng toàn màn hình"
                  aria-label="Mở rộng toàn màn hình"
                >
                  <Maximize2 className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={() => setIsOpen(false)}
                  className="min-h-11 min-w-11 p-1.5 text-slate-600 hover:text-rose-600 rounded-lg hover:bg-rose-50 transition cursor-pointer"
                  title="Đóng"
                  aria-label="Đóng"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Sub-sidebar trượt ra hiển thị History Conversation & New Chat trong chế độ Sidebar */}
            {isHistoryOpen && <WidgetHistory widget={widget} />}


            {/* Khung chat */}
            <div className="flex-1 overflow-hidden">
              <WidgetChat widget={widget} />
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 3. CHẾ ĐỘ TOÀN MÀN HÌNH (Full Width, Full Height - 4 phần Trái / 8 phần Phải) */}
      {/* ========================================================================= */}
      {isOpen && isExpanded && (
        <div ref={dialogRef} role="dialog" aria-modal="true" aria-label="Trợ lý du lịch AI" className="fixed inset-0 z-50 bg-slate-100 flex flex-col overflow-hidden animate-in fade-in duration-200">
          {/* Floating Control Buttons: Thu nhỏ về sidebar & Đóng hoàn toàn (Top-Right) */}
          <div className="absolute right-3 top-3 z-[1100] flex items-center gap-1 rounded-xl border border-slate-200/80 bg-white/95 p-1 shadow-sm backdrop-blur-md">
            <button
              onClick={() => setIsExpanded(false)}
              className="min-h-11 min-w-11 p-2 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-xl transition cursor-pointer"
              title="Thu nhỏ về sidebar"
              aria-label="Thu nhỏ về sidebar"
            >
              <Minimize2 className="w-4 h-4" />
            </button>
            <button
              onClick={() => {
                setIsExpanded(false);
                setIsOpen(false);
              }}
              className="min-h-11 min-w-11 p-2 text-slate-600 hover:text-rose-600 hover:bg-rose-50 rounded-xl transition cursor-pointer"
              title="Đóng"
              aria-label="Đóng"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Sub-sidebar trượt ra hiển thị History Conversation & New Chat - Overlay toàn bộ 12/12 */}
          {isHistoryOpen && <WidgetHistory widget={widget} />}

          {/* Main Container: Flex layout với hiệu ứng trượt vào/ra (slide in/out) mượt mà */}
          <div className="flex flex-1 h-full overflow-hidden relative">
            {/* =================================================================== */}
            {/* CỘT TRÁI (KHUNG CHAT AI): HIỆU ỨNG TRƯỢT VÀO VÀ TRƯỢT RA (SLIDE IN/OUT) */}
            {/* =================================================================== */}
            <div
              className={`h-full shrink-0 flex flex-col bg-white border-r border-slate-200/70 transition-all duration-300 ease-in-out motion-reduce:transition-none overflow-hidden z-20 ${
                isChatCollapsed
                  ? 'w-0 opacity-0 -translate-x-4 pointer-events-none hidden lg:flex'
                  : 'w-full lg:w-[36%] xl:w-[34%] opacity-100 translate-x-0 flex'
              }`}
            >
              <div className="w-full min-w-0 h-full flex flex-col">
                {/* Top chat bar: Icon List + Mock Title (không border, không khác màu) */}
                <div className="flex min-h-20 shrink-0 items-center justify-between border-b border-slate-200/70 bg-white px-4 py-3 pr-28 lg:pr-4">
                  <div className="flex min-w-0 items-center space-x-2 text-slate-700">
                    <button
                      type="button"
                      onClick={() => setIsHistoryOpen(prev => !prev)}
                      className="min-h-11 min-w-11 p-1.5 text-slate-600 hover:text-slate-900 rounded-lg hover:bg-slate-100 transition cursor-pointer"
                      title="Danh sách hội thoại & Tạo chat mới"
                      aria-label="Danh sách hội thoại & Tạo chat mới"
                    >
                      <List className="w-4 h-4" />
                    </button>
                    <WidgetTitle title={activePlan?.title} />
                  </div>
                </div>

                <div className="flex-1 overflow-hidden">
                  <WidgetChat widget={widget} />
                </div>
              </div>
            </div>

            {/* =================================================================== */}
            {/* CỘT PHẢI: TÁCH 2 PHẦN (LỘ TRÌNH CÓ HEADER & MAP KHÔNG CÓ HEADER)  */}
            {/* Khi thu nhỏ chat, cột phải mở rộng trọn vẹn toàn bộ không gian    */}
            {/* =================================================================== */}
            <div className={`relative ${isChatCollapsed ? 'flex' : 'hidden lg:flex'} flex-1 h-full min-w-0 bg-slate-50/50`}>
              {/* Nút thu nhỏ / mở rộng nằm ngay tại ranh giới giữa cột 1 và cột 2 */}
              <button
                type="button"
                onClick={() => setIsChatCollapsed(prev => !prev)}
                className={`hidden lg:flex absolute top-1/2 -translate-y-1/2 z-30 transition-all duration-200 cursor-pointer items-center justify-center ${
                  isChatCollapsed
                    ? 'left-0 w-6 h-12 bg-white hover:bg-ai-50 text-slate-500 hover:text-ai-600 border border-l-0 border-slate-300/80 rounded-r-xl shadow-md hover:w-7'
                    : '-left-3.5 w-7 h-7 bg-white hover:bg-slate-50 text-slate-500 hover:text-ai-600 border border-slate-200 rounded-full shadow-md hover:scale-110'
                }`}
                title={isChatCollapsed ? "Mở rộng Khung Chat AI Assistant" : "Thu nhỏ Khung Chat AI Assistant"}
                aria-label={isChatCollapsed ? "Mở rộng Khung Chat AI Assistant" : "Thu nhỏ Khung Chat AI Assistant"}
              >
                {isChatCollapsed ? (
                  <ChevronRight className="w-4 h-4" />
                ) : (
                  <ChevronLeft className="w-4 h-4" />
                )}
              </button>
              {selectedProduct && !activePlan
                ? <WidgetProductDetail key={selectedProduct.productId} productId={selectedProduct.productId}
                    summary={selectedProduct.summary} onClose={closeProductDetail} onAddToCart={selectedCanAddToCart ? addSelectedToCart : undefined} onBookNow={bookSelectedNow}
                    cartAddState={widget.cartAddStates[selectedProduct.productId]} />
                : activePlan ? <WidgetPlanPanel widget={widget} /> : <WidgetPlanEmpty onPrompt={handleQuickPrompt} />}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function WidgetTitle({ title }: { title?: string }) {
  return (
    <div className="flex min-w-0 items-center gap-3">
      <span className="hidden h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-ai-50 text-ai-600 sm:flex">
        <Compass className="h-5 w-5" aria-hidden="true" />
      </span>
      <div className="min-w-0">
        <h2 className="font-sans truncate text-sm font-semibold text-slate-900">Trợ lý du lịch AI</h2>
        <p className="mt-0.5 truncate text-xs text-slate-500">{title || 'Lên kế hoạch cùng X-OTA'}</p>
      </div>
    </div>
  );
}
