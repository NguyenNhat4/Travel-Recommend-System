import React from 'react';
import Image from 'next/image';
import { AlertCircle, Loader2, Maximize2, RotateCcw, Sparkles } from 'lucide-react';
import { nodeLabel } from '../../../components/assistant/assistantLabels';
import { AssistantText, InlineBold } from '../../../components/assistant/inlineBold';
import { SuggestionChips } from '../../../components/assistant/SuggestionChips';
import { TripDetailsForm } from '../../../components/assistant/TripDetailsForm';
import { WidgetOpening } from './WidgetOpening';
import { WidgetNarration } from './WidgetNarration';
import { WidgetComposer } from './WidgetComposer';
import type { FloatingWidgetController } from './useFloatingWidget';

export function WidgetChat({ widget }: { widget: FloatingWidgetController }) {
  const { messages, assistantState, isRunning, isExpanded, setIsExpanded, chatScrollRef,
    inputVal, setInputVal, handleSendMessage, handleConfirmTripDetails, retry, abort, openProductDetail, addPlanItemToCart } = widget;
  const isInitial = messages.length === 0 && !isRunning;
  const lastMessageId = messages.length > 0 ? messages[messages.length - 1].id : null;

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-white">
      <div ref={chatScrollRef} className={`min-h-0 flex-1 overflow-y-auto ${isInitial ? 'flex flex-col' : 'space-y-4 p-4'}`}>
        {isInitial && <WidgetOpening value={inputVal} onChange={setInputVal} onSend={handleSendMessage} busy={isRunning} />}
        <div className="space-y-4" role="log" aria-label="Hội thoại với trợ lý du lịch" aria-live="polite">
          {messages.map((message) => (
            <div key={message.id} className={`flex items-start gap-3 ${message.sender === 'user' ? 'justify-end' : ''}`}>
              {message.sender === 'assistant' && <Image src="/mascot_welcome.webp" alt="" width={36} height={36} className="mt-1 h-9 w-9 shrink-0 object-contain" />}
              <div className={`min-w-0 max-w-[88%] whitespace-pre-wrap break-words rounded-2xl p-4 text-base leading-relaxed ${message.sender === 'user' ? 'rounded-tr-none bg-blue-600 text-white' : 'rounded-tl-none bg-slate-100 text-slate-800'}`}>
                {message.sender === 'assistant'
                  ? (message.products
                    ? <WidgetNarration text={message.text} products={message.products}
                        onOpen={(productId) => openProductDetail(productId, message)}
                        quickAddIds={message.plan ? new Set(message.plan.cartItems.map((item) => item.product.productId)) : undefined}
                        onQuickAdd={message.plan ? (productId) => addPlanItemToCart(message.plan!, productId) : undefined} />
                    : <AssistantText text={message.text} />)
                  : message.text}
                {message.plan && !isExpanded && (
                  <button onClick={() => setIsExpanded(true)} className="mt-3 flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-white px-3 py-2 text-sm font-semibold text-blue-600 hover:bg-blue-50">
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
        {isRunning && (
          <div role="status" className="w-fit max-w-full space-y-2 rounded-2xl border border-blue-100 bg-blue-50 p-3.5 text-sm text-blue-900">
            <div className="flex items-center gap-2 font-semibold"><Loader2 className="h-4 w-4 shrink-0 animate-spin" aria-hidden="true" />{assistantState.isSlow ? 'Yêu cầu đang mất nhiều thời gian hơn dự kiến…' : 'AI đang lập kế hoạch và tính toán lộ trình...'}</div>
            {assistantState.progress.length > 0 && <ol className="space-y-1 pl-5 text-xs">
              {assistantState.progress.map((step, index) => <li key={`${step.sequence ?? index}-${step.nodeId ?? 'node'}`}>{nodeLabel(step.nodeId)}{step.message ? ` · ${step.message}` : ''}</li>)}
            </ol>}
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
        {assistantState.phase === 'aborted' && <p role="status" className="text-sm text-slate-500">Đã dừng yêu cầu.</p>}
      </div>
      {!isInitial && (
        <div className="shrink-0 border-t border-slate-100 bg-white px-4 pb-5 pt-3">
          <WidgetComposer value={inputVal} onChange={setInputVal} onSend={handleSendMessage} busy={isRunning} />
          <div className="mt-2 flex items-center justify-between gap-2 text-xs text-slate-500">
            <span>{assistantState.conversationId ? 'Đang tiếp tục cuộc trò chuyện' : 'Trợ lý AI V-OTA'}</span>
            {isRunning && <button type="button" onClick={abort} className="min-h-11 rounded-lg px-2 font-semibold text-rose-700 hover:bg-rose-50">Dừng xử lý</button>}
          </div>
        </div>
      )}
    </div>
  );
}
