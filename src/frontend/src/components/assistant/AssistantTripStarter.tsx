'use client';

import React, { useCallback, useEffect, useId, useRef, useState } from 'react';
import { Calendar, Check, Loader2, MapPin, RotateCcw, SlidersHorizontal, Sparkles, Users } from 'lucide-react';
import { listDestinations, type DestinationOption } from '../../services/destinations';

export type TripStarterParty = 'solo' | 'couple' | 'family_with_kids' | 'friends';
export type TripStarterStyle = 'luxury' | 'budget';

export interface TripStarterSelection {
  destination: string;
  days: number;
  party: TripStarterParty;
  style: TripStarterStyle;
}

const DAYS = [2, 3, 4, 5];
const PARTIES: { id: TripStarterParty; label: string }[] = [
  { id: 'family_with_kids', label: '👨‍👩‍👧 Gia đình có trẻ nhỏ' },
  { id: 'couple', label: '💑 Cặp đôi lãng mạn' },
  { id: 'friends', label: '🏄 Nhóm bạn trẻ' },
  { id: 'solo', label: '🎒 Độc hành' },
];
const STYLES: { id: TripStarterStyle; label: string; description: string }[] = [
  { id: 'luxury', label: '💎 Nghỉ dưỡng sang trọng', description: 'Resort, spa và trải nghiệm cao cấp' },
  { id: 'budget', label: '💰 Tối ưu chi phí', description: 'Combo tiết kiệm và lịch trình năng động' },
];

const PARTY_NAMES: Record<TripStarterParty, string> = {
  family_with_kids: 'gia đình có trẻ nhỏ',
  couple: 'cặp đôi',
  friends: 'nhóm bạn',
  solo: 'một người',
};
const STYLE_NAMES: Record<TripStarterStyle, string> = {
  luxury: 'nghỉ dưỡng sang trọng',
  budget: 'tối ưu chi phí',
};

export function tripStarterMessage(selection: TripStarterSelection): string {
  return `Tôi chọn đi ${selection.destination} trong ${selection.days} ngày cho ${PARTY_NAMES[selection.party]}, ưu tiên ${STYLE_NAMES[selection.style]}.`;
}

export function AssistantTripStarter({
  onSubmit,
  disabled = false,
}: {
  onSubmit: (selection: TripStarterSelection) => void;
  disabled?: boolean;
}) {
  const [options, setOptions] = useState<DestinationOption[]>([]);
  const [loadState, setLoadState] = useState<'loading' | 'ready' | 'empty' | 'error'>('loading');
  const [destination, setDestination] = useState('');
  const [days, setDays] = useState(3);
  const [party, setParty] = useState<TripStarterParty>('family_with_kids');
  const [style, setStyle] = useState<TripStarterStyle>('luxury');
  const requestRef = useRef<AbortController | null>(null);
  const titleId = useId();

  const load = useCallback(() => {
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    setLoadState('loading');

    void listDestinations(controller.signal).then((destinations) => {
      if (controller.signal.aborted) return;
      setOptions(destinations);
      setDestination((current) => destinations.some((item) => item.destination === current)
        ? current
        : destinations[0]?.destination ?? '');
      setLoadState(destinations.length > 0 ? 'ready' : 'empty');
    }).catch((error: unknown) => {
      if (controller.signal.aborted || (error instanceof Error && error.name === 'AbortError')) return;
      setOptions([]);
      setDestination('');
      setLoadState('error');
    });
  }, []);

  useEffect(() => {
    load();
    return () => requestRef.current?.abort();
  }, [load]);

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (disabled || loadState !== 'ready' || !destination) return;
    onSubmit({ destination, days, party, style });
  };

  const choiceClass = (selected: boolean) => `min-h-11 rounded-xl border px-3 py-2 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ai-500 focus-visible:ring-offset-2 ${
    selected
      ? 'border-ai-600 bg-ai-600 text-white'
      : 'border-slate-200 bg-white text-slate-700 hover:border-ai-300 hover:bg-ai-50'
  } disabled:cursor-not-allowed disabled:opacity-50`;

  return (
    <section aria-labelledby={titleId} className="mt-3.5 space-y-3.5 rounded-2xl border border-ai-200 bg-white p-4 text-slate-800 shadow-sm">
      <div className="flex items-start gap-2 border-b border-slate-100 pb-2.5">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-ai-100 text-ai-700" aria-hidden="true">
          <SlidersHorizontal className="h-4 w-4" />
        </span>
        <div>
          <p className="text-[11px] font-extrabold uppercase tracking-wider text-ai-700">Tương tác cùng AI</p>
          <h3 id={titleId} className="text-sm font-bold text-slate-900">Chọn nhanh nhu cầu chuyến đi</h3>
        </div>
      </div>

      <p className="text-xs leading-relaxed text-slate-600">Chọn nhanh các tiêu chí bên dưới hoặc nhập yêu cầu chi tiết ở ô chat.</p>

      <form onSubmit={submit} className="space-y-3.5">
        <fieldset>
          <legend className="mb-2 flex items-center gap-1.5 text-xs font-bold text-slate-700">
            <MapPin className="h-3.5 w-3.5 text-ai-600" aria-hidden="true" /> Điểm đến
          </legend>
          {loadState === 'loading' && (
            <div role="status" className="flex min-h-11 items-center gap-2 rounded-xl bg-slate-50 px-3 text-xs text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Đang tải danh sách điểm đến…
            </div>
          )}
          {loadState === 'error' && (
            <div role="alert" className="flex min-h-11 items-center justify-between gap-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-800">
              <span>Chưa tải được danh sách điểm đến.</span>
              <button type="button" onClick={load} className="inline-flex min-h-9 shrink-0 items-center gap-1 font-bold underline underline-offset-2">
                <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" /> Thử lại
              </button>
            </div>
          )}
          {loadState === 'empty' && <p role="status" className="rounded-xl bg-slate-50 px-3 py-2.5 text-xs text-slate-500">Catalog hiện chưa có điểm đến khả dụng.</p>}
          {loadState === 'ready' && (
            <div className="flex max-h-36 flex-wrap gap-2 overflow-y-auto pr-1" aria-label="Danh sách điểm đến">
              {options.map((option) => (
                <button key={option.destination} type="button" disabled={disabled} aria-pressed={destination === option.destination} onClick={() => setDestination(option.destination)} className={choiceClass(destination === option.destination)}>
                  {option.destination}
                </button>
              ))}
            </div>
          )}
        </fieldset>

        <fieldset>
          <legend className="mb-2 flex items-center gap-1.5 text-xs font-bold text-slate-700"><Calendar className="h-3.5 w-3.5 text-ai-600" aria-hidden="true" /> Thời lượng</legend>
          <div className="flex flex-wrap gap-2">{DAYS.map((value) => <button key={value} type="button" disabled={disabled} aria-pressed={days === value} onClick={() => setDays(value)} className={choiceClass(days === value)}>{value} ngày ({value - 1} đêm)</button>)}</div>
        </fieldset>

        <fieldset>
          <legend className="mb-2 flex items-center gap-1.5 text-xs font-bold text-slate-700"><Sparkles className="h-3.5 w-3.5 text-amber-500" aria-hidden="true" /> Phong cách ưu tiên</legend>
          <div className="grid gap-2 sm:grid-cols-2">{STYLES.map((item) => <button key={item.id} type="button" disabled={disabled} aria-pressed={style === item.id} onClick={() => setStyle(item.id)} className={`${choiceClass(style === item.id)} text-left`}><span className="block font-bold">{item.label}</span><span className={`mt-0.5 block text-[11px] font-normal ${style === item.id ? 'text-ai-100' : 'text-slate-500'}`}>{item.description}</span></button>)}</div>
        </fieldset>

        <fieldset>
          <legend className="mb-2 flex items-center gap-1.5 text-xs font-bold text-slate-700"><Users className="h-3.5 w-3.5 text-ai-600" aria-hidden="true" /> Nhóm đồng hành</legend>
          <div className="flex flex-wrap gap-2">{PARTIES.map((item) => <button key={item.id} type="button" disabled={disabled} aria-pressed={party === item.id} onClick={() => setParty(item.id)} className={choiceClass(party === item.id)}>{item.label}</button>)}</div>
        </fieldset>

        <button type="submit" disabled={disabled || loadState !== 'ready' || !destination} className="flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-ai-600 px-4 py-2.5 text-xs font-bold text-white transition hover:bg-ai-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ai-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-300">
          <Check className="h-4 w-4" aria-hidden="true" /> Tạo lịch trình
        </button>
      </form>
    </section>
  );
}
