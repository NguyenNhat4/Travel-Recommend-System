'use client';

import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { Bookmark, BookmarkCheck, CloudSun, History, List, Loader2, Map, Share2, Trash2, X } from 'lucide-react';
import dynamic from 'next/dynamic';
import type { components } from '../../types/api.gen';
import { useAssistant } from '../../context/AssistantProvider';
import { useTravel } from '../../context/TravelContext';
import { createAssistantShareUrl, decodeAssistantResponse } from '../../services/assistantShare';
import { convertItineraryResponseToGroundedPlan, planLocationCoverage } from '../../services/assistant';
import { useAssistantCart } from '../../hooks/useAssistantCart';
import type { GroundedPlan } from '../../types/travel';
import { AssistantConversation } from './AssistantConversation';
import { AssistantMapPanel, AssistantResultPanel } from './AssistantResultPanel';
import { WeatherForecastCard } from './WeatherForecastCard';
import { splitBoldTitle } from './inlineBold';
import { listAssistantConversations } from '../../services/assistantHistory';

const ItineraryMap = dynamic(
  () => import('./ItineraryMap').then((module) => module.ItineraryMap),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full min-h-[350px] items-center justify-center rounded-2xl bg-slate-100 text-xs text-slate-500">
        Đang tải bản đồ lộ trình…
      </div>
    ),
  }
);

type Response = components['schemas']['ItineraryResponse'];
type SavedItem = { id: string; savedAt: string; response: Response };
type ConversationSummary = components['schemas']['AssistantConversationSummary'];
const SAVED_KEY = 'vota.assistant.savedResponses';

function isResponse(value: unknown): value is Response {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const response = value as Record<string, unknown>;
  if (typeof response.conversationId !== 'string') return false;
  if (!['COMPLETED', 'NEEDS_CLARIFICATION', 'NO_RESULTS', 'FALLBACK'].includes(String(response.status))) return false;
  if (response.status === 'COMPLETED') return Boolean(response.itinerary && typeof response.itinerary === 'object');
  if (response.status === 'NEEDS_CLARIFICATION') return typeof response.question === 'string';
  return typeof response.message === 'string';
}

function titleOf(response: Response) {
  if (response.status === 'COMPLETED') return response.itinerary.title || `Lịch trình ${response.intent?.destination ?? ''}`.trim();
  // Dòng đầu `**Tiêu đề**` đã là bản tóm tắt: dùng làm tên khi chia sẻ/lưu, không lấy cả đoạn.
  const text = response.status === 'NEEDS_CLARIFICATION' ? response.question : response.message;
  return splitBoldTitle(text).title ?? text;
}

function destinationOf(response: Response) {
  if (response.status === 'COMPLETED' || response.status === 'NO_RESULTS') return response.intent?.destination;
  if (response.status === 'NEEDS_CLARIFICATION') return response.knownIntent?.destination ?? undefined;
  return response.intent?.destination ?? undefined;
}

export function AssistantView() {
  const { state, submitIntentOverride, sendMessage, loadConversation } = useAssistant();
  const { showToast, addToCart, currentPersona, authReady } = useTravel();
  const addItineraryToCart = useAssistantCart();
  const searchParams = useSearchParams();
  const sharedData = searchParams.get('data');
  const [sharedResponse, setSharedResponse] = useState<Response | null>(null);
  const [savedItems, setSavedItems] = useState<SavedItem[]>([]);
  const [savedReady, setSavedReady] = useState(false);
  const [selectedResponse, setSelectedResponse] = useState<Response | null>(null);
  const [showSaved, setShowSaved] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [historyItems, setHistoryItems] = useState<ConversationSummary[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [showWeather, setShowWeather] = useState(false);
  const [activeDayTab, setActiveDayTab] = useState(1);
  const [viewMode, setViewMode] = useState<'list' | 'map'>('list');

  useEffect(() => setSharedResponse(sharedData ? decodeAssistantResponse(sharedData) : null), [sharedData]);
  useEffect(() => {
    try {
      const parsed: unknown = JSON.parse(window.localStorage.getItem(SAVED_KEY) || '[]');
      if (Array.isArray(parsed)) setSavedItems(parsed.filter((item): item is SavedItem => Boolean(
        item && typeof item === 'object' && typeof item.id === 'string' && typeof item.savedAt === 'string' && isResponse(item.response),
      )).slice(0, 30));
    } catch { setSavedItems([]); }
    setSavedReady(true);
  }, []);
  useEffect(() => {
    if (!savedReady) return;
    try { window.localStorage.setItem(SAVED_KEY, JSON.stringify(savedItems)); }
    catch { showToast('Không thể lưu vào bộ nhớ thiết bị.'); }
  }, [savedReady, savedItems, showToast]);

  const response = selectedResponse ?? sharedResponse ?? state.response;
  const resultResponse = response?.status === 'NEEDS_CLARIFICATION' || response?.status === 'NO_RESULTS'
    ? null
    : response;
  const destination = response ? destinationOf(response) : undefined;
  const isSaved = Boolean(response && savedItems.some((item) => JSON.stringify(item.response) === JSON.stringify(response)));

  const isRunning = state.phase === 'connecting' || state.phase === 'streaming';
  const isArchived = Boolean(selectedResponse ?? sharedResponse);
  const archivedPriceAsOf = isArchived && response?.status === 'COMPLETED' ? response.itinerary.priceAsOf : null;

  const plan: GroundedPlan | null = React.useMemo(() => {
    return response ? convertItineraryResponseToGroundedPlan(response) : null;
  }, [response]);
  const coverage = plan ? planLocationCoverage(plan) : null;
  // Không có điểm nào có tọa độ thật thì hiện panel trống thay vì bản đồ không ghim.
  const mapPlan = plan && coverage && coverage.located > 0 ? plan : null;
  const missingPinsNote = coverage && coverage.missing > 0 && coverage.located > 0
    ? `${coverage.missing} địa điểm chưa có vị trí nên không hiện trên bản đồ.`
    : null;

  const saveResponse = () => {
    if (!response || response.status !== 'COMPLETED') return;
    setSavedItems((items) => [{ id: `saved-${Date.now()}`, savedAt: new Date().toISOString(), response }, ...items.filter((item) => JSON.stringify(item.response) !== JSON.stringify(response))].slice(0, 30));
    showToast('Đã lưu lịch trình trên thiết bị.');
  };
  const shareResponse = async () => {
    if (!response) return;
    const url = createAssistantShareUrl(response, window.location.origin);
    try {
      if (navigator.share) await navigator.share({ title: titleOf(response), url });
      else if (navigator.clipboard?.writeText) { await navigator.clipboard.writeText(url); showToast('Đã sao chép liên kết chia sẻ.'); }
      else window.prompt('Sao chép liên kết chia sẻ', url);
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') return;
      showToast('Không thể chia sẻ liên kết lúc này.');
    }
  };

  const openHistory = async () => {
    if (!currentPersona) {
      showToast('Đăng nhập để xem lịch sử hội thoại.');
      return;
    }
    setShowHistory(true);
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const result = await listAssistantConversations();
      setHistoryItems(result.data);
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : 'Không thể tải lịch sử hội thoại.');
    } finally {
      setHistoryLoading(false);
    }
  };

  const selectHistory = async (conversationId: string) => {
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      await loadConversation(conversationId);
      setSelectedResponse(null);
      setSharedResponse(null);
      setShowHistory(false);
    } catch (error) {
      setHistoryError(error instanceof Error ? error.message : 'Không thể mở hội thoại.');
    } finally {
      setHistoryLoading(false);
    }
  };

  return (
    <div className="mx-auto w-full max-w-[1760px] px-3 pb-6 pt-4 sm:px-5 lg:px-7">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm sm:px-5">
        <div className="flex min-w-0 items-center gap-3"><span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-600 to-blue-600 text-white shadow-md shadow-indigo-200"><span className="text-xl">✦</span></span><div className="min-w-0"><p className="text-[10px] font-extrabold uppercase tracking-[0.17em] text-indigo-600">V-OTA · ITINERARY AGENT</p><h1 className="truncate text-lg font-extrabold text-slate-900 sm:text-xl">Trợ lý du lịch AI</h1></div></div>
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" onClick={openHistory} disabled={!authReady || !currentPersona} className="inline-flex h-9 items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 text-xs font-bold text-slate-700 hover:border-indigo-200 hover:bg-indigo-50 disabled:cursor-not-allowed disabled:opacity-40" title={currentPersona ? 'Xem lịch sử hội thoại' : 'Đăng nhập để xem lịch sử'}><History className="h-3.5 w-3.5 text-indigo-600" /> Lịch sử</button>
          <button type="button" onClick={() => setShowSaved(true)} className="inline-flex h-9 items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 text-xs font-bold text-slate-700 hover:border-indigo-200 hover:bg-indigo-50"><Bookmark className="h-3.5 w-3.5 text-indigo-600" /> Đã lưu <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px]">{savedItems.length}</span></button>
          <button type="button" onClick={() => setShowWeather((value) => !value)} disabled={!destination} className="inline-flex h-9 items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 text-xs font-bold text-slate-700 hover:border-sky-200 hover:bg-sky-50 disabled:opacity-40"><CloudSun className="h-3.5 w-3.5 text-sky-600" /> Thời tiết</button>
          <button type="button" onClick={shareResponse} disabled={!response} className="inline-flex h-9 items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 text-xs font-bold text-slate-700 hover:border-indigo-200 hover:bg-indigo-50 disabled:opacity-40"><Share2 className="h-3.5 w-3.5 text-indigo-600" /> Chia sẻ</button>
          <button type="button" onClick={saveResponse} disabled={response?.status !== 'COMPLETED' || isSaved} className="inline-flex h-9 items-center gap-1.5 rounded-xl bg-indigo-600 px-3 text-xs font-bold text-white shadow-sm hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300"><BookmarkCheck className="h-3.5 w-3.5" /> {isSaved ? 'Đã lưu' : 'Lưu lịch trình'}</button>
        </div>
      </header>
      {showWeather && destination && <div className="mb-4"><WeatherForecastCard destination={destination} defaultExpanded={false} /></div>}

      <div className="grid min-h-[72vh] gap-4 xl:h-[calc(100dvh-13.5rem)] xl:min-h-[650px] xl:grid-cols-[minmax(300px,0.86fr)_minmax(380px,1.24fr)] 2xl:grid-cols-[minmax(320px,0.84fr)_minmax(480px,1.16fr)_minmax(320px,0.80fr)]">
        <section aria-label="Trò chuyện với trợ lý" className="flex min-h-[560px] min-w-0 flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm xl:min-h-0">
          <header className="flex items-center justify-between border-b border-slate-100 px-4 py-3.5"><div><h2 className="text-sm font-extrabold text-slate-800">Cuộc trò chuyện</h2><p className="mt-0.5 text-[10px] text-slate-500">Mô tả chuyến đi, trợ lý sẽ xếp lịch trình</p></div><span className={`h-2 w-2 rounded-full ${state.phase === 'connecting' || state.phase === 'streaming' ? 'animate-pulse bg-amber-400' : 'bg-emerald-500'}`} aria-label={state.phase === 'connecting' || state.phase === 'streaming' ? 'Agent đang chạy' : 'Agent sẵn sàng'} /></header>
          <AssistantConversation inputId="assistant-page-input" showResponseInline={false} />
        </section>
        <section aria-label="Lịch trình" className="flex min-w-0 flex-col overflow-hidden rounded-3xl border border-slate-200 bg-slate-100/70 p-3 shadow-sm sm:p-4">
          <div className="mb-3 flex shrink-0 items-center justify-between px-1">
            <h2 className="text-sm font-extrabold text-slate-800">
              {viewMode === 'map' ? 'Bản đồ lộ trình' : 'Lịch trình chi tiết'}
            </h2>
            {plan && (
              <div className="flex items-center gap-1 rounded-xl border border-slate-200 bg-white p-1 2xl:hidden">
                <button
                  type="button"
                  onClick={() => setViewMode('list')}
                  className={`flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-bold transition ${
                    viewMode === 'list'
                      ? 'bg-indigo-600 text-white shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <List className="h-3.5 w-3.5" /> Danh sách
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode('map')}
                  className={`flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-bold transition ${
                    viewMode === 'map'
                      ? 'bg-indigo-600 text-white shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <Map className="h-3.5 w-3.5" /> Bản đồ
                </button>
              </div>
            )}
          </div>

          {isArchived && (
            <div role="status" className="mb-3 flex items-start gap-2 rounded-2xl border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-[11px] leading-relaxed text-amber-900">
              <History className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <p>
                Đây là lịch trình {sharedResponse && !selectedResponse ? 'được chia sẻ' : 'đã lưu'}
                {archivedPriceAsOf ? `, giá ghi nhận ngày ${new Date(archivedPriceAsOf).toLocaleDateString('vi-VN')}` : ''}. Giá và chỗ có thể đã thay đổi; giá chính thức hiển thị ở giỏ hàng.
                {' '}<button type="button" onClick={() => { setSelectedResponse(null); setSharedResponse(null); }} className="font-bold underline">Quay lại cuộc trò chuyện</button>
              </p>
            </div>
          )}
          <div className="min-h-0 flex-1 overflow-y-auto">
            {viewMode === 'map' && plan ? (
              <div className="h-full min-h-[450px] overflow-hidden rounded-2xl border border-slate-200 bg-white p-2">
                {mapPlan ? <ItineraryMap
                  plan={mapPlan}
                  activeDay={activeDayTab}
                  onSelectDay={setActiveDayTab}
                  onAddToCart={addToCart}
                /> : <AssistantMapPanel />}
              </div>
            ) : (
              <>
                <AssistantResultPanel
                  response={resultResponse}
                  showMap={false}
                  onAddToCart={addItineraryToCart}
                  busy={isRunning}
                  readOnly={isArchived}
                  onIntentOverride={(intent) => {
                    setSelectedResponse(null);
                    submitIntentOverride(intent);
                  }}
                  onSuggestion={(suggestion) => {
                    setSelectedResponse(null);
                    sendMessage(suggestion);
                  }}
                />
                <div className="mt-4 2xl:hidden">
                  {mapPlan ? (
                    <div className="h-[380px] overflow-hidden rounded-2xl border border-slate-200 bg-white p-2">
                      <ItineraryMap
                        plan={mapPlan}
                        activeDay={activeDayTab}
                        onSelectDay={setActiveDayTab}
                        onAddToCart={addToCart}
                      />
                    </div>
                  ) : (
                    <AssistantMapPanel />
                  )}
                </div>
              </>
            )}
          </div>
        </section>
        <aside className="hidden min-w-0 flex-col gap-3 2xl:flex">
          <div className="flex items-center justify-between px-1">
            <h2 className="text-sm font-extrabold text-slate-800">Bản đồ lịch trình</h2>
            {plan && (
              <span className="text-[11px] font-semibold text-indigo-600">
                Ngày {activeDayTab} / {plan.days.length}
              </span>
            )}
          </div>
          <div className="min-h-64 flex-1 overflow-hidden rounded-2xl border border-slate-200 bg-white">
            {mapPlan ? (
              <ItineraryMap
                plan={mapPlan}
                activeDay={activeDayTab}
                onSelectDay={setActiveDayTab}
                onAddToCart={addToCart}
              />
            ) : (
              <AssistantMapPanel />
            )}
          </div>
          <p className="rounded-xl border border-slate-200 bg-white p-3 text-[11px] leading-relaxed text-slate-500">
            Bản đồ đi theo thứ tự hoạt động trong ngày.{missingPinsNote ? ` ${missingPinsNote}` : ''}
          </p>
        </aside>
      </div>

      {showSaved && <div className="fixed inset-0 z-[1200] flex items-center justify-center bg-slate-950/50 p-4 backdrop-blur-sm" onMouseDown={(event) => { if (event.target === event.currentTarget) setShowSaved(false); }}>
        <section role="dialog" aria-modal="true" aria-labelledby="saved-assistant-title" className="flex max-h-[85dvh] w-full max-w-2xl flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-2xl">
          <header className="flex items-center justify-between border-b border-slate-100 bg-slate-50 px-5 py-4"><div><h2 id="saved-assistant-title" className="text-lg font-extrabold text-slate-900">Chuyến đi đã lưu</h2><p className="mt-0.5 text-xs text-slate-500">Lưu trên thiết bị này · {savedItems.length} lịch trình</p></div><button type="button" onClick={() => setShowSaved(false)} aria-label="Đóng danh sách chuyến đi đã lưu" className="rounded-xl p-2 text-slate-500 hover:bg-white"><X className="h-4 w-4" /></button></header>
          <div className="flex-1 space-y-3 overflow-y-auto p-4 sm:p-5">
            {!savedItems.length && <div className="rounded-2xl border border-dashed border-slate-300 py-12 text-center"><Bookmark className="mx-auto h-7 w-7 text-slate-300" /><p className="mt-3 text-sm font-bold text-slate-700">Chưa có lịch trình được lưu</p><p className="mt-1 text-xs text-slate-500">Bấm “Lưu lịch trình” để xem lại sau.</p></div>}
            {savedItems.map((item) => <article key={item.id} className="flex items-center justify-between gap-3 rounded-2xl border border-slate-200 p-4"><button type="button" onClick={() => { setSelectedResponse(item.response); setSharedResponse(null); setShowSaved(false); }} className="min-w-0 flex-1 text-left"><span className="rounded-full bg-indigo-50 px-2.5 py-1 text-[10px] font-bold text-indigo-700">{destinationOf(item.response) || item.response.status}</span><h3 className="mt-2 truncate text-sm font-bold text-slate-900">{titleOf(item.response)}</h3><p className="mt-1 text-[11px] text-slate-500">{new Date(item.savedAt).toLocaleString('vi-VN')}</p></button><button type="button" onClick={() => setSavedItems((items) => items.filter((saved) => saved.id !== item.id))} aria-label={`Xóa ${titleOf(item.response)}`} className="rounded-xl p-2 text-slate-400 hover:bg-rose-50 hover:text-rose-600"><Trash2 className="h-4 w-4" /></button></article>)}
          </div>
          <footer className="border-t border-slate-100 bg-slate-50 px-5 py-3 text-[11px] text-slate-500">Lịch trình chỉ lưu trong trình duyệt này.</footer>
        </section>
      </div>}

      {showHistory && <div className="fixed inset-0 z-[1200] flex items-center justify-center bg-slate-950/50 p-4 backdrop-blur-sm" onMouseDown={(event) => { if (event.target === event.currentTarget) setShowHistory(false); }}>
        <section role="dialog" aria-modal="true" aria-labelledby="assistant-history-title" className="flex max-h-[85dvh] w-full max-w-2xl flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-2xl">
          <header className="flex items-center justify-between border-b border-slate-100 bg-slate-50 px-5 py-4"><div><h2 id="assistant-history-title" className="text-lg font-extrabold text-slate-900">Lịch sử hội thoại</h2><p className="mt-0.5 text-xs text-slate-500">Chỉ hiển thị hội thoại của tài khoản đang đăng nhập</p></div><button type="button" onClick={() => setShowHistory(false)} aria-label="Đóng lịch sử hội thoại" className="rounded-xl p-2 text-slate-500 hover:bg-white"><X className="h-4 w-4" /></button></header>
          <div className="flex-1 space-y-3 overflow-y-auto p-4 sm:p-5">
            {historyLoading && <div className="flex items-center justify-center gap-2 py-12 text-sm text-slate-500"><Loader2 className="h-4 w-4 animate-spin" /> Đang tải lịch sử…</div>}
            {!historyLoading && historyError && <div role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800"><p>{historyError}</p><button type="button" onClick={openHistory} className="mt-2 font-bold underline">Thử lại</button></div>}
            {!historyLoading && !historyError && !historyItems.length && <div className="rounded-2xl border border-dashed border-slate-300 py-12 text-center"><History className="mx-auto h-7 w-7 text-slate-300" /><p className="mt-3 text-sm font-bold text-slate-700">Chưa có hội thoại đã lưu</p><p className="mt-1 text-xs text-slate-500">Hội thoại mới sẽ xuất hiện sau lượt trả lời đầu tiên.</p></div>}
            {!historyLoading && !historyError && historyItems.map((item) => <button key={item.conversationId} type="button" onClick={() => void selectHistory(item.conversationId)} className={`w-full rounded-2xl border p-4 text-left transition hover:border-indigo-300 hover:bg-indigo-50/40 ${state.conversationId === item.conversationId ? 'border-indigo-300 bg-indigo-50' : 'border-slate-200 bg-white'}`}><div className="flex items-start justify-between gap-3"><div className="min-w-0"><h3 className="truncate text-sm font-bold text-slate-900">{item.title}</h3><p className="mt-1 text-[11px] text-slate-500">{new Date(item.updatedAt).toLocaleString('vi-VN')} · {item.messageCount} tin nhắn</p></div>{state.conversationId === item.conversationId && <span className="shrink-0 rounded-full bg-indigo-100 px-2 py-1 text-[10px] font-bold text-indigo-700">Đang mở</span>}</div></button>)}
          </div>
        </section>
      </div>}
    </div>
  );
}
