'use client';

import React, { useCallback, useEffect, useId, useRef, useState } from 'react';
import { Calendar, LocateFixed, Loader2, MapPin, PlaneTakeoff, RotateCcw, Send, Users, Wallet } from 'lucide-react';
import { listDestinations } from '../../services/destinations';
import { listDepartureAirports, nearestDepartureCity } from '../../services/flights';
import type { components } from '../../types/api.gen';

type TripIntent = components['schemas']['TripIntent'];
export type ClarificationForm = NonNullable<
  components['schemas']['ItineraryNeedsClarification']['clarificationForm']
>;

const MIN_DAYS = 1;
const MAX_DAYS = 7;
//: Chỉ hiện vài điểm đến tiêu biểu (AGENTS.md §7 đề xuất đã chốt); không đổ toàn bộ catalog vào form.
const MAX_DESTINATION_OPTIONS = 8;

const PARTY_LABELS: Record<string, string> = {
  solo: 'Độc hành', couple: 'Cặp đôi', family_with_kids: 'Gia đình có trẻ nhỏ', friends: 'Nhóm bạn',
};

function formatBudget(value: number): string {
  return `${(value / 1_000_000).toLocaleString('vi-VN', { maximumFractionDigits: 1 })} triệu`;
}

/** Câu yêu cầu hoàn chỉnh dựng từ form; đặt vào ô nhập để người dùng đọc lại, sửa rồi mới gửi. */
export function tripDetailsPrompt(intent: TripIntent): string {
  const parts: string[] = [];
  parts.push(`Lên lịch trình ${intent.days ?? MIN_DAYS} ngày tại ${intent.destination ?? 'điểm đến bạn chọn'}`);
  if (intent.startDate) parts.push(`bắt đầu từ ngày ${intent.startDate}`);
  if (intent.party) {
    const { adults, children } = intent.party;
    const partyText = children > 0 ? `${adults} người lớn và ${children} trẻ em` : `${adults} người lớn`;
    parts.push(`cho ${partyText}`);
  }
  if (intent.budget) parts.push(`ngân sách khoảng ${formatBudget(intent.budget)}`);
  if (intent.origin?.trim()) parts.push(`đi từ ${intent.origin.trim()}`);
  return `${parts.join(', ')}.`;
}

type LocateState = 'idle' | 'locating' | 'denied' | 'failed';

const LOCATE_MESSAGE: Record<Exclude<LocateState, 'idle' | 'locating'>, string> = {
  denied: 'Bạn chưa cho phép dùng vị trí. Bạn nhập nơi đi giúp mình nhé.',
  failed: 'Chưa xác định được nơi đi từ vị trí. Bạn nhập nơi đi giúp mình nhé.',
};

/**
 * Gợi ý nơi đi từ vị trí trình duyệt (AC-AGT-03): chỉ hỏi quyền khi người dùng bấm nút. Toạ độ chỉ dùng trong hàm này
 * để chọn thành phố có sân bay gần nhất trong catalog; không lưu vào state, không gửi lên server.
 */
function useDepartureFromLocation(onCity: (city: string) => void) {
  const [state, setState] = useState<LocateState>('idle');
  const locate = useCallback(() => {
    if (typeof navigator === 'undefined' || !navigator.geolocation) {
      setState('failed');
      return;
    }
    setState('locating');
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude } = position.coords;
        void listDepartureAirports()
          .then((airports) => {
            const city = nearestDepartureCity({ latitude, longitude }, airports);
            if (city) {
              onCity(city);
              setState('idle');
            } else {
              setState('failed');
            }
          })
          .catch(() => setState('failed'));
      },
      (error) => setState(error.code === error.PERMISSION_DENIED ? 'denied' : 'failed'),
      { enableHighAccuracy: false, timeout: 10_000, maximumAge: 600_000 },
    );
  }, [onCity]);
  return { state, locate };
}

export function TripDetailsForm({
  form,
  onConfirm,
  disabled = false,
}: {
  form: ClarificationForm;
  onConfirm: (prompt: string) => void;
  disabled?: boolean;
}) {
  const [options, setOptions] = useState<string[]>([]);
  const [loadState, setLoadState] = useState<'loading' | 'ready' | 'empty' | 'error'>('loading');
  const [intent, setIntent] = useState<TripIntent>(form.defaults);
  // Điểm đến đến từ ô gõ hay từ chip: ô gõ chỉ hiện chữ người dùng tự gõ, chọn chip thì ô để trống (hiện placeholder).
  const [typedDestination, setTypedDestination] = useState(false);
  const requestRef = useRef<AbortController | null>(null);
  const titleId = useId();
  const today = form.startDateMin ?? new Date().toISOString().slice(0, 10);

  const load = useCallback(() => {
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    setLoadState('loading');
    void listDestinations(controller.signal).then((destinations) => {
      if (controller.signal.aborted) return;
      const top = [...destinations]
        .sort((a, b) => b.productCount - a.productCount)
        .slice(0, MAX_DESTINATION_OPTIONS)
        .map((item) => item.destination);
      setOptions(top);
      setLoadState(top.length > 0 ? 'ready' : 'empty');
    }).catch((error: unknown) => {
      if (controller.signal.aborted || (error instanceof Error && error.name === 'AbortError')) return;
      setOptions([]);
      setLoadState('error');
    });
  }, []);

  useEffect(() => {
    if (form.fields.includes('destination')) load();
    return () => requestRef.current?.abort();
  }, [form.fields, load]);

  const setDays = (value: number) => setIntent((prev) => ({ ...prev, days: Math.min(MAX_DAYS, Math.max(MIN_DAYS, value)) }));
  const setStartDate = (value: string) => setIntent((prev) => ({ ...prev, startDate: value < today ? today : value }));
  const setAdults = (value: number) => setIntent((prev) => ({
    ...prev, party: { type: prev.party?.type ?? null, adults: Math.max(1, value), children: prev.party?.children ?? 0 },
  }));
  const setChildren = (value: number) => setIntent((prev) => ({
    ...prev, party: { type: prev.party?.type ?? null, adults: prev.party?.adults ?? 1, children: Math.max(0, value) },
  }));
  const setOrigin = useCallback((origin: string) => setIntent((prev) => ({ ...prev, origin })), []);
  const departure = useDepartureFromLocation(setOrigin);
  const setBudget = (value: string) => {
    const parsed = value.trim() ? Number(value) * 1_000_000 : null;
    setIntent((prev) => ({ ...prev, budget: parsed && parsed > 0 ? parsed : null }));
  };

  const confirm = (event: React.FormEvent) => {
    event.preventDefault();
    onConfirm(tripDetailsPrompt(intent));
  };

  const chipClass = (selected: boolean) => `min-h-9 rounded-lg border px-2.5 py-1 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ai-500 focus-visible:ring-offset-2 ${
    selected ? 'border-ai-600 bg-ai-600 text-white' : 'border-slate-200 bg-white text-slate-700 hover:border-ai-300 hover:bg-ai-50'
  } disabled:cursor-not-allowed disabled:opacity-50`;

  const stepperButton = 'flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 bg-white text-sm font-bold text-slate-600 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-40';

  return (
    <section aria-labelledby={titleId} className="mt-2 space-y-3 rounded-2xl border border-ai-200 bg-white p-3.5 text-slate-800 shadow-sm">
      <h3 id={titleId} className="sr-only">Form gợi ý thông tin chuyến đi</h3>
      <form onSubmit={confirm} className="space-y-3">
        {form.fields.includes('destination') && (
          <fieldset>
            <legend className="mb-1.5 flex items-center gap-1.5 text-xs font-bold text-slate-700">
              <MapPin className="h-3.5 w-3.5 text-ai-600" aria-hidden="true" /> Điểm đến
            </legend>
            {loadState === 'loading' && (
              <div role="status" className="flex min-h-9 items-center gap-2 rounded-lg bg-slate-50 px-3 text-xs text-slate-500">
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> Đang tải điểm đến…
              </div>
            )}
            {loadState === 'error' && (
              <div role="alert" className="flex min-h-9 items-center justify-between gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-1.5 text-xs text-rose-800">
                <span>Chưa tải được danh sách.</span>
                <button type="button" onClick={load} className="inline-flex items-center gap-1 font-bold underline underline-offset-2">
                  <RotateCcw className="h-3 w-3" aria-hidden="true" /> Thử lại
                </button>
              </div>
            )}
            {loadState === 'ready' && (
              <div className="flex flex-wrap gap-1.5" aria-label="Điểm đến gợi ý">
                {options.map((destination) => {
                  const selected = !typedDestination && intent.destination === destination;
                  return (
                  <button key={destination} type="button" disabled={disabled} aria-pressed={selected}
                    onClick={() => { setTypedDestination(false); setIntent((prev) => ({ ...prev, destination })); }} className={chipClass(selected)}>
                    {destination}
                  </button>
                  );
                })}
              </div>
            )}
            <input type="text" disabled={disabled}
              value={typedDestination || !intent.destination || !options.includes(intent.destination) ? intent.destination ?? '' : ''}
              onChange={(event) => { setTypedDestination(true); setIntent((prev) => ({ ...prev, destination: event.target.value })); }}
              onFocus={() => {
                // Bấm vào ô gõ khi đang chọn chip: bỏ chọn chip, tránh nhầm hai lựa chọn cùng lúc.
                if (typedDestination) return;
                setIntent((prev) => (prev.destination && options.includes(prev.destination) ? { ...prev, destination: '' } : prev));
              }}
              placeholder="Hoặc nhập điểm đến khác…"
              className="mt-1.5 w-full rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs outline-hidden focus:ring-1 focus:ring-ai-500" />
          </fieldset>
        )}

        {form.fields.includes('days') && (
          <fieldset className="flex items-center justify-between gap-3">
            <legend className="flex items-center gap-1.5 text-xs font-bold text-slate-700">
              <Calendar className="h-3.5 w-3.5 text-ai-600" aria-hidden="true" /> Số ngày
            </legend>
            <div className="flex items-center gap-2.5">
              <button type="button" disabled={disabled || (intent.days ?? MIN_DAYS) <= MIN_DAYS} onClick={() => setDays((intent.days ?? MIN_DAYS) - 1)} className={stepperButton}>−</button>
              <span className="w-16 text-center text-xs font-bold text-slate-900">{intent.days ?? MIN_DAYS} ngày</span>
              <button type="button" disabled={disabled || (intent.days ?? MIN_DAYS) >= MAX_DAYS} onClick={() => setDays((intent.days ?? MIN_DAYS) + 1)} className={stepperButton}>+</button>
            </div>
          </fieldset>
        )}

        {form.fields.includes('startDate') && (
          <fieldset className="flex items-center justify-between gap-3">
            <legend className="text-xs font-bold text-slate-700">Ngày khởi hành</legend>
            <input type="date" value={intent.startDate ?? today} min={today} disabled={disabled}
              onChange={(event) => setStartDate(event.target.value)}
              className="rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs outline-hidden focus:ring-1 focus:ring-ai-500" />
          </fieldset>
        )}

        {form.fields.includes('party') && (
          <fieldset className="space-y-1.5">
            <legend className="flex items-center gap-1.5 text-xs font-bold text-slate-700">
              <Users className="h-3.5 w-3.5 text-ai-600" aria-hidden="true" /> Số người
              {intent.party?.type && PARTY_LABELS[intent.party.type] ? ` · ${PARTY_LABELS[intent.party.type]}` : ''}
            </legend>
            <div className="flex flex-wrap items-center gap-3 text-xs">
              <span className="flex items-center gap-2">Người lớn
                <button type="button" disabled={disabled || (intent.party?.adults ?? 1) <= 1} onClick={() => setAdults((intent.party?.adults ?? 1) - 1)} className={stepperButton}>−</button>
                <span className="w-4 text-center font-bold">{intent.party?.adults ?? 1}</span>
                <button type="button" disabled={disabled} onClick={() => setAdults((intent.party?.adults ?? 1) + 1)} className={stepperButton}>+</button>
              </span>
              <span className="flex items-center gap-2">Trẻ em
                <button type="button" disabled={disabled || (intent.party?.children ?? 0) <= 0} onClick={() => setChildren((intent.party?.children ?? 0) - 1)} className={stepperButton}>−</button>
                <span className="w-4 text-center font-bold">{intent.party?.children ?? 0}</span>
                <button type="button" disabled={disabled} onClick={() => setChildren((intent.party?.children ?? 0) + 1)} className={stepperButton}>+</button>
              </span>
            </div>
          </fieldset>
        )}

        {form.fields.includes('budget') && (
          <fieldset className="flex items-center justify-between gap-3">
            <legend className="flex items-center gap-1.5 text-xs font-bold text-slate-700">
              <Wallet className="h-3.5 w-3.5 text-ai-600" aria-hidden="true" /> Ngân sách (không bắt buộc)
            </legend>
            <div className="flex items-center gap-1.5">
              <input type="number" min={0} step={0.5} inputMode="decimal" disabled={disabled}
                value={intent.budget ? intent.budget / 1_000_000 : ''}
                onChange={(event) => setBudget(event.target.value)}
                placeholder="Không giới hạn"
                className="w-24 rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs outline-hidden focus:ring-1 focus:ring-ai-500" />
              <span className="text-xs font-semibold text-slate-500">triệu VNĐ</span>
            </div>
          </fieldset>
        )}

        {form.fields.includes('origin') && (
          <fieldset className="space-y-1.5">
            <legend className="flex items-center gap-1.5 text-xs font-bold text-slate-700">
              <PlaneTakeoff className="h-3.5 w-3.5 text-ai-600" aria-hidden="true" /> Nơi đi (không bắt buộc)
            </legend>
            <div className="flex items-center gap-1.5">
              <input type="text" disabled={disabled} value={intent.origin ?? ''} aria-label="Nơi đi"
                onChange={(event) => setOrigin(event.target.value)}
                placeholder="Để thêm vé máy bay, ví dụ Hà Nội"
                className="min-w-0 flex-1 rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs outline-hidden focus:ring-1 focus:ring-ai-500" />
              <button type="button" disabled={disabled || departure.state === 'locating'} onClick={departure.locate}
                className="inline-flex min-h-8 shrink-0 items-center gap-1 rounded-lg border border-ai-200 bg-ai-50 px-2.5 text-xs font-semibold text-ai-700 transition hover:bg-ai-100 disabled:cursor-not-allowed disabled:opacity-50">
                {departure.state === 'locating'
                  ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                  : <LocateFixed className="h-3.5 w-3.5" aria-hidden="true" />}
                Dùng vị trí hiện tại
              </button>
            </div>
            {(departure.state === 'denied' || departure.state === 'failed') && (
              <p role="status" className="text-xs text-slate-500">{LOCATE_MESSAGE[departure.state]}</p>
            )}
          </fieldset>
        )}

        <button type="submit" disabled={disabled} className="flex min-h-10 w-full items-center justify-center gap-2 rounded-xl bg-ai-600 px-4 py-2 text-xs font-bold text-white transition hover:bg-ai-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ai-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-300">
          <Send className="h-3.5 w-3.5" aria-hidden="true" /> Xác nhận
        </button>
      </form>
    </section>
  );
}
