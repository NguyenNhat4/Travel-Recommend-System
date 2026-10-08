import React from 'react';
import { isCartEligible } from '../../../services/booking';
import Image from 'next/image';
import { AlertCircle, Maximize2, RotateCcw, Sparkles } from 'lucide-react';
import { AssistantText, InlineBold } from '../../../components/assistant/inlineBold';
import { SuggestionChips } from '../../../components/assistant/SuggestionChips';
import { TripDetailsForm } from '../../../components/assistant/TripDetailsForm';
import { WidgetOpening } from './WidgetOpening';
import { WidgetNarration } from './WidgetNarration';
import { WidgetComposer } from './WidgetComposer';
import { WidgetProgress } from './WidgetProgress';
import type { FloatingWidgetController } from './useFloatingWidget';

function AssistantHeader() {
  return (
    <div className="flex items-center gap-2.5">
      <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-ai-50">
        <Image src="/mascot_welcome.webp" alt="" width={28} height={28} className="h-7 w-7 object-contain" />
      </span>
      <span className="text-xs font-semibold tracking-wide text-slate-500">Trợ lý du lịch V-OTA</span>
    </div>
  );
}

export function WidgetChat({ widget }: { widget: FloatingWidgetController }) {
  const { messages, assistantState, isRunning, isExpanded, setIsExpanded, chatScrollRef,
    inputVal, setInputVal, handleSendMessage, handleConfirmTripDetails, retry, abort, openProductDetail, addPlanItemToCart } = widget;
  const isInitial = messages.length === 0 && !isRunning;
  const lastMessageId = messages.length > 0 ? messages[messages.length - 1].id : null;

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-white">
      <div ref={chatScrollRef} className={`min-h-0 flex-1 overflow-y-auto overscroll-contain ${isInitial ? 'flex flex-col' : 'space-y-6 px-4 py-6 sm:px-6'}`}>
        {isInitial && <WidgetOpening value={inputVal} onChange={setInputVal} onSend={handleSendMessage} busy={isRunning} />}
        <div className="space-y-7" role="log" aria-label="Hội thoại với trợ lý du lịch" aria-live="polite">
          {messages.map((message) => (
            <div key={message.id} className={`flex min-w-0 ${message.sender === 'user' ? 'justify-end' : 'flex-col gap-3'}`}>
              {message.sender === 'assistant' && <AssistantHeader />}
              <div className={`min-w-0 whitespace-pre-wrap break-words text-sm leading-7 sm:text-base ${message.sender === 'user' ? 'message-send-in max-w-[88%] rounded-2xl rounded-tr-md bg-ai-600 px-4 py-3 text-white' : 'w-full text-slate-700'}`}>
                {message.sender === 'assistant'
                  ? (message.products
                    ? <WidgetNarration text={message.text} products={message.products}
                        onOpen={(productId) => openProductDetail(productId, message)}
                        quickAddIds={message.plan ? new Set(message.plan.cartItems.filter((item) => isCartEligible(item.product.taxonomy)).map((item) => item.product.productId)) : undefined}
                        cartAddStates={widget.cartAddStates}
                        onQuickAdd={message.plan ? (productId) => addPlanItemToCart(message.plan!, productId) : undefined} />
                    : <AssistantText text={message.text} />)
                  : message.text}
                {message.plan && !isExpanded && (
                  <button onClick={() => setIsExpanded(true)} className="mt-3 flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-white px-3 py-2 text-sm font-semibold text-ai-600 hover:bg-ai-50">
                    <Sparkles className="h-4 w-4" aria-hidden="true" />Xem lộ trình & Bản đồ song song<Maximize2 className="h-4 w-4" aria-hidden="true" />
                  </button>
                )}
                {/* Chỉ hiện form ở tin nhắn mới nhất: người dùng xác nhận thì lượt sau đã có câu trả lời khác. */}
                {message.clarificationForm && message.id === lastMessageId && (
                  <TripDetailsForm form={message.clarificationForm} onConfirm={handleConfirmTripDetails} disabled={isRunning} />
                )}
                {message.suggestions && message.id === lastMessageId && (
                  <SuggestionChips suggestions={message.suggestions} onSelect={handleSendMessage} disabled={isRunning} />
                )}
              </div>
            </div>
          ))}
        </div>
        {/* Tiến trình đứng đúng chỗ câu trả lời sắp hiện, như một tin nhắn trợ lý đang soạn. */}
        {isRunning && (
          <div className="flex flex-col gap-3">
            <AssistantHeader />
            <WidgetProgress progress={assistantState.progress} isSlow={assistantState.isSlow} />
          </div>
        )}
        {assistantState.error && (
          <div role="alert" className={`flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3.5 text-sm text-rose-800 ${isInitial ? 'mx-4 mb-4' : ''}`}>
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <div className="min-w-0"><p className="whitespace-pre-line"><InlineBold text={assistantState.error.message} /></p>
              {assistantState.error.retryable && <button onClick={retry} className="mt-2 inline-flex min-h-11 items-center gap-2 rounded-lg px-2 font-semibold underline"><RotateCcw className="h-4 w-4" aria-hidden="true" />Thử lại</button>}
            </div>
          </div>
        )}
        {assistantState.phase === 'aborted' && (
          <div role="status" className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-500">
            <span>Đã dừng. Trợ lý chưa trả lời tin nhắn này.</span>
            {assistantState.lastRequest && (
              <button type="button" onClick={retry} className="inline-flex min-h-11 items-center gap-1.5 rounded-lg px-2 font-semibold text-ai-600 hover:bg-ai-50">
                <RotateCcw className="h-4 w-4" aria-hidden="true" />Gửi lại
              </button>
            )}
          </div>
        )}
      </div>
      {!isInitial && (
        <div className="shrink-0 border-t border-slate-100 bg-slate-50/80 px-4 pb-4 pt-4 sm:px-6">
          <WidgetComposer value={inputVal} onChange={setInputVal} onSend={handleSendMessage} busy={isRunning} onStop={abort} />
          <p className="mt-2 text-xs text-slate-500">{assistantState.conversationId ? 'Đang tiếp tục cuộc trò chuyện' : 'Trợ lý AI V-OTA'}</p>
        </div>
      )}
    </div>
  );
}
