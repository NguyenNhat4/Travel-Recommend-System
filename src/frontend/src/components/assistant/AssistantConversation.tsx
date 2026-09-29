'use client';

import React, { useEffect, useRef, useState } from 'react';
import Image from 'next/image';
import { Check, Loader2, Mic, MicOff, RotateCcw, Send, Square } from 'lucide-react';
import { useAssistant } from '../../context/AssistantProvider';
import { useTravel } from '../../context/TravelContext';
import { useSpeechRecognition } from '../../hooks/useSpeechRecognition';
import { useAssistantCart } from '../../hooks/useAssistantCart';
import { AssistantResultPanel } from './AssistantResultPanel';
import { AssistantTripStarter, tripStarterMessage } from './AssistantTripStarter';
import { TripDetailsForm } from './TripDetailsForm';
import { SuggestionChips } from './SuggestionChips';
import { nodeLabel } from './assistantLabels';

export function AssistantConversation({
  inputId,
  consumeInitialMessage = false,
  showResponseInline = true,
  className = '',
}: {
  inputId: string;
  consumeInitialMessage?: boolean;
  showResponseInline?: boolean;
  className?: string;
}) {
  const { state, sendMessage, submitIntentOverride, retry, abort, resetConversation, consumeFloatingInitialMessage } = useAssistant();
  const { currentLocale, showToast } = useTravel();
  const addItineraryToCart = useAssistantCart();
  const [input, setInput] = useState('');
  const endRef = useRef<HTMLDivElement>(null);
  const isRunning = state.phase === 'connecting' || state.phase === 'streaming';
  const {
    isSupported: isSpeechSupported,
    isListening,
    interimTranscript,
    currentLang,
    setCurrentLang,
    toggleListening,
  } = useSpeechRecognition({
    lang: currentLocale === 'en' ? 'en-US' : 'vi-VN',
    continuous: true,
    interimResults: true,
    onFinalResult: (text) => setInput((current) => current ? `${current} ${text}` : text),
    onError: showToast,
  });

  useEffect(() => {
    setCurrentLang(currentLocale === 'en' ? 'en-US' : 'vi-VN');
  }, [currentLocale, setCurrentLang]);

  useEffect(() => {
    if (!consumeInitialMessage || !state.floatingInitialMessage) return;
    setInput(state.floatingInitialMessage);
    consumeFloatingInitialMessage();
  }, [consumeInitialMessage, consumeFloatingInitialMessage, state.floatingInitialMessage]);

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'end' });
  }, [state.transcript.length, state.progress.length, state.phase]);

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const message = input.trim();
    if (!message || isRunning) return;
    sendMessage(message);
    setInput('');
  };

  return (
    <div className={`flex h-full min-h-0 flex-col bg-white ${className}`}>
      <div className="flex-1 space-y-5 overflow-y-auto bg-gradient-to-b from-slate-50/80 to-white px-4 py-5 sm:px-5" aria-live="polite">
        {state.transcript.length === 0 && (
          <div className="flex items-start gap-3">
            <Image src="/mascot_welcome.webp" alt="" width={38} height={38} className="mt-0.5 h-9 w-9 shrink-0 object-contain" />
            <div className="max-w-[90%] rounded-2xl rounded-tl-sm border border-slate-100 bg-white p-4 shadow-sm">
              <p className="text-sm font-bold text-slate-800">Xin chào! Mình có thể giúp bạn lên lịch trình.</p>
              <p className="mt-1.5 text-xs leading-relaxed text-slate-500">Hãy cung cấp thông tin đầy đủ nhất có thể về điểm đến, số ngày, nhóm đồng hành, ngân sách và sở thích để đề xuất chính xác và sát nhu cầu của bạn hơn. Bạn có thể chọn nhanh bên dưới hoặc nhập yêu cầu chi tiết ở ô chat.</p>
              <AssistantTripStarter
                disabled={isRunning}
                onSubmit={(selection) => sendMessage(tripStarterMessage(selection))}
              />
            </div>
          </div>
        )}

        {state.transcript.map((message, index) => {
          const showStructuredResponse = message.response
            && message.response.status !== 'NEEDS_CLARIFICATION'
            && message.response.status !== 'NO_RESULTS';
          const isLast = index === state.transcript.length - 1;
          const clarificationForm = message.response?.status === 'NEEDS_CLARIFICATION'
            ? message.response.clarificationForm : undefined;
          const noResultsSuggestions = message.response?.status === 'NO_RESULTS' ? message.response.suggestions : undefined;

          return <div key={message.id} className={`flex items-start gap-2.5 ${message.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
            {message.sender === 'assistant' && <Image src="/mascot_welcome.webp" alt="" width={34} height={34} className="mt-1 h-8 w-8 shrink-0 object-contain" />}
            <div className={`min-w-0 max-w-[92%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${message.sender === 'user' ? 'rounded-tr-sm bg-blue-600 text-white shadow-sm' : 'rounded-tl-sm border border-slate-100 bg-white text-slate-800 shadow-sm'}`}>
              <p className="whitespace-pre-line">{message.text}</p>
              {/* Chỉ hiện form ở tin nhắn mới nhất: người dùng xác nhận thì lượt sau đã có câu trả lời khác. */}
              {clarificationForm && isLast && (
                <TripDetailsForm form={clarificationForm} onConfirm={setInput} disabled={isRunning} />
              )}
              {noResultsSuggestions && isLast && (
                <SuggestionChips suggestions={noResultsSuggestions} onSelect={sendMessage} disabled={isRunning} />
              )}
              {showStructuredResponse && showResponseInline && (
                <div className="mt-4 border-t border-slate-100 pt-4">
                  <AssistantResultPanel
                    response={message.response}
                    showMap={false}
                    onSuggestion={sendMessage}
                    onIntentOverride={submitIntentOverride}
                    onAddToCart={addItineraryToCart}
                    busy={isRunning}
                    readOnly={message.response !== state.response}
                  />
                </div>
              )}
            </div>
          </div>;
        })}

        {isRunning && <div className="ml-10 rounded-2xl border border-blue-100 bg-blue-50/80 p-3.5 text-xs text-blue-900">
          <p className="flex items-center gap-2 font-semibold">{state.isSlow ? 'Yêu cầu đang mất nhiều thời gian hơn dự kiến…' : 'Trợ lý đang tìm kiếm và xếp lịch trình…'} {!state.isSlow && <Loader2 className="h-4 w-4 animate-spin text-blue-600" />}</p>
          {!!state.progress.length && <ol aria-label="Tiến trình xử lý" className="mt-2 space-y-1 text-[11px] text-blue-800">{state.progress.map((step, index) => <li key={`${step.sequence ?? index}-${step.nodeId ?? 'node'}`} className="flex items-center gap-1.5"><Check className="h-3 w-3 shrink-0 text-emerald-600" aria-hidden="true" /><span>{nodeLabel(step.nodeId)}</span>{step.durationMs != null && <span className="text-blue-500">· {(step.durationMs / 1000).toFixed(1)} giây</span>}</li>)}</ol>}
        </div>}

        {state.error && <div role="alert" className="ml-10 rounded-2xl border border-rose-200 bg-rose-50 p-3.5 text-xs text-rose-800">
          <p className="font-semibold">{state.error.message}</p>
          {(state.error.retryable || state.error.code === 'CONVERSATION_NOT_FOUND') && <button onClick={retry} className="mt-2 inline-flex items-center gap-1 font-bold"><RotateCcw className="h-3.5 w-3.5" /> Thử lại</button>}
        </div>}
        {state.phase === 'aborted' && <p className="ml-10 text-xs text-slate-500">Đã dừng yêu cầu.</p>}
        {interimTranscript && <p className="ml-10 text-xs italic text-slate-400">{interimTranscript}</p>}
        <div ref={endRef} />
      </div>

      <div className="border-t border-slate-200 bg-white p-3 sm:p-4">
        <form onSubmit={submit} className="rounded-2xl border border-slate-200 bg-slate-50 p-1.5 transition focus-within:border-blue-300 focus-within:bg-white focus-within:ring-4 focus-within:ring-blue-50">
          <label className="sr-only" htmlFor={inputId}>Tin nhắn cho trợ lý</label>
          <textarea id={inputId} rows={2} maxLength={1000} value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} placeholder="Mô tả chuyến đi bạn mong muốn…" className="min-h-12 w-full resize-none bg-transparent px-3 py-2 text-sm outline-none placeholder:text-slate-400" />
          <div className="flex items-center justify-between gap-2 px-1 pb-0.5">
            <div className="flex items-center gap-1.5">
              {isSpeechSupported && <button type="button" onClick={toggleListening} disabled={isRunning} aria-label={isListening ? 'Dừng nhập giọng nói' : 'Nhập bằng giọng nói'} title={isListening ? `Đang nghe (${currentLang})` : 'Nhập bằng giọng nói'} className={`flex h-9 items-center gap-1.5 rounded-xl px-2.5 text-xs font-semibold transition ${isListening ? 'bg-rose-100 text-rose-700' : 'text-slate-500 hover:bg-slate-100 hover:text-slate-800'}`}>{isListening ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}<span className="hidden sm:inline">{isListening ? 'Đang nghe' : 'Giọng nói'}</span></button>}
              <span className="hidden text-[10px] text-slate-400 sm:inline">Enter để gửi · {input.length}/1000</span>
            </div>
            <div className="flex items-center gap-1.5">
              {isRunning ? <button type="button" onClick={abort} className="flex h-9 items-center gap-1.5 rounded-xl bg-rose-600 px-3 text-xs font-bold text-white shadow-sm transition hover:bg-rose-700" title="Dừng yêu cầu"><Square className="h-3.5 w-3.5" /> Dừng</button> : <button type="submit" disabled={!input.trim()} className="flex h-9 items-center gap-1.5 rounded-xl bg-blue-600 px-3.5 text-xs font-bold text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40"><Send className="h-3.5 w-3.5" /> Gửi</button>}
            </div>
          </div>
        </form>
        <div className="mt-2 flex items-center justify-between px-1 text-[10px] text-slate-400">
          <span>{state.conversationId ? 'Đang tiếp tục phiên của tab này' : 'Cuộc trò chuyện mới'}</span>
          <button type="button" onClick={resetConversation} className="inline-flex items-center gap-1 font-medium transition hover:text-slate-700"><RotateCcw className="h-3 w-3" /> Cuộc trò chuyện mới</button>
        </div>
      </div>
    </div>
  );
}
