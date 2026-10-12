'use client';

import { useSearchParams } from 'next/navigation';

import React, { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { AlertCircle, Loader2, Search } from 'lucide-react';
import { useTravel } from '../../../context/TravelContext';
import { guestsText } from '../../../components/checkout/guestCounts';
import { SortMenu } from '../../../components/search/SortMenu';
import { productFromApi } from '../../../services/catalog';
import { todayVN } from '../../search/tripContext';
import { FlightCard } from './FlightCard';
import { FlightDateStrip } from './FlightDateStrip';
import { FlightFilters } from './FlightFilters';
import { TicketPanel, type LegId, type TicketLeg } from './TicketPanel';
import { shortDate, thousands, weekdayLong } from './flightFormat';
import { buildFlightResultsHref, type FlightSearch } from './flightHref';
import {
  FLIGHT_SORT_LABELS, applyFilters, canFollow, countActiveFilters, countFacets, noFilters, pickDate, pruneFilters,
  sortFlights, summarizeDays, type FareOption, type FlightFilters as Filters, type FlightOption, type FlightSort,
} from './flightModel';
import { useOutboundLeg, useReturnLeg } from './useFlightLegs';

type Chosen = { option: FlightOption; fare: FareOption } | null;

const CARD = 'rounded-[20px] border border-slate-100 bg-white shadow-[0_8px_40px_rgba(15,28,58,0.05)]';

const Notice: React.FC<{ tone?: 'info' | 'warn'; children: React.ReactNode }> = ({ tone = 'info', children }) => (
  <p role="status" className={`flex items-start gap-2 rounded-xl px-3.5 py-2.5 text-[13px] ${tone === 'warn' ? 'bg-amber-50 text-amber-900' : 'bg-brand-50 text-brand-900'}`}>
    <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
    <span>{children}</span>
  </p>
);

/**
 * Kết quả vé máy bay dưới tấm tìm kiếm của `/flights` cho một lần tìm `{origin, destination, trip}` (frontend §4.1b).
 * `notice`: lần bấm Tìm sau đó còn thiếu thông tin; kết quả cũ ở lại kèm lời báo.
 *
 * Chọn từng chặng: chiều đi rồi chiều về (khách chọn khứ hồi). Mỗi chặng là một chuyến bay một chiều đặt được (`level: flight`);
 * "Đặt vé" thêm từng chặng vào giỏ, giỏ hiển thị hai chặng ngược chiều là một chuyến khứ hồi (FR-BKG-10).
 * Bộ lọc, sắp xếp và gom ngày chạy phía client trên các chuyến của tuyến vì Backend chưa lọc theo ngày, giờ hay hãng.
 */
export const FlightResultsView: React.FC<{ search: FlightSearch; notice?: string | null }> = ({ search, notice }) => {
  const { origin, destination, trip } = search;
  const preferredFareId = useSearchParams()?.get('fare');
  const { startBooking } = useTravel();
  const today = todayVN();
  const adults = trip.adults ?? 1;
  const kids = trip.children ?? 0;

  const [retry, setRetry] = useState(0);
  const [mode, setMode] = useState<'round' | 'one'>(trip.checkOut ? 'round' : 'one');
  const [requestedStep, setStep] = useState<LegId>('out');
  const [dates, setDates] = useState<Partial<Record<LegId, string>>>({});
  const [chosen, setChosen] = useState<Record<LegId, Chosen>>({ out: null, ret: null });
  const [filters, setFilters] = useState<Filters>(noFilters);
  const [sort, setSort] = useState<FlightSort>('price');
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(new Set());
  const [submitting, setSubmitting] = useState(false);

  // Hero và tấm tìm kiếm chiếm gần hết màn hình đầu: đưa khối kết quả lên khi vào trang bằng một lần tìm.
  const rootRef = useRef<HTMLElement>(null);
  useEffect(() => {
    rootRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
  }, []);

  const outbound = useOutboundLeg(origin, destination, retry);
  const outboundRoute = outbound.status === 'ready' ? outbound.leg.route : null;
  const back = useReturnLeg(outboundRoute, mode === 'round', retry);
  const roundTrip = mode === 'round' && back.status === 'ready';
  // Chưa có tuyến chiều về thì chỉ còn chặng đi, dù trước đó đã sang bước chiều về.
  const step: LegId = requestedStep === 'ret' && back.status === 'none' ? 'out' : requestedStep;

  // Chặng đang xem: danh sách chuyến đã bỏ chuyến không nối được với chuyến chiều đi.
  const active = step === 'ret' ? (back.status === 'ready' ? back.leg : null) : (outbound.status === 'ready' ? outbound.leg : null);
  let legOptions: FlightOption[] = [];
  if (active) {
    const out = chosen.out?.option;
    const earliest = dates.out ?? trip.checkIn;
    legOptions = step === 'out'
      ? active.options
      : active.options.filter((option) => (out ? canFollow(out, option) : !earliest || option.date >= earliest));
  }

  const days = summarizeDays(legOptions, today);
  // Ngày khách đã tìm hoặc đã bấm trên dải ngày. Chiều về không nhập ngày thì chưa có ngày mong muốn: mở ngày đầu tiên có chuyến
  // nối được. Ngày mong muốn không có chuyến thì không hiện chuyến của ngày khác, chỉ báo và gợi ý ngày gần nhất (frontend §4.1b).
  const wantedDate = dates[step] ?? (step === 'out' ? trip.checkIn : trip.checkOut);
  const pick = pickDate(days, wantedDate);
  const activeDate = pick?.date ?? null;
  const pickDay = (date: string) => setDates((prev) => ({ ...prev, [step]: date }));

  const dayOptions = legOptions.filter((option) => option.date === activeDate);
  const facets = countFacets(dayOptions);
  const effective = pruneFilters(filters, facets);
  const visible = sortFlights(applyFilters(dayOptions, effective), sort);
  const airlineCodes = new Map<string, string>();
  for (const option of dayOptions) if (!airlineCodes.has(option.airline)) airlineCodes.set(option.airline, option.airlineCode);
  const airlines = [...airlineCodes].map(([name, code]) => ({ name, code })).sort((a, b) => a.name.localeCompare(b.name, 'vi'));
  const activeFilters = countActiveFilters(effective);

  const originCity = outboundRoute ? String((outboundRoute.attributes as Record<string, unknown>)?.originCity ?? origin) : origin;
  const legFrom = step === 'ret' ? destination : originCity;
  const legTo = step === 'ret' ? originCity : destination;

  const choose = (option: FlightOption, fare: FareOption) => {
    setChosen((prev) => {
      const next = { ...prev, [step]: { option, fare } };
      // Chiều đi đổi thì chiều về đã chọn phải còn cất cánh sau khi chiều đi hạ cánh.
      if (step === 'out' && prev.ret && !canFollow(option, prev.ret.option)) next.ret = null;
      return next;
    });
    // Chiều về còn đang tải thì vẫn sang bước đó (hiện khung chờ), để bấm sớm không bị kẹt ở chiều đi.
    if (step === 'out' && mode === 'round' && back.status !== 'none' && back.status !== 'error') setStep('ret');
  };
  const clearChoice = () => setChosen((prev) => ({ ...prev, [step]: null }));
  const setTrip = (next: 'round' | 'one') => {
    setMode(next);
    if (next === 'one') {
      setStep('out');
      setChosen((prev) => ({ ...prev, ret: null }));
    }
  };

  const legs: TicketLeg[] = [
    { id: 'out', label: 'Chiều đi', fromCity: originCity, toCity: destination, chosen: chosen.out },
    ...(mode === 'round'
      ? [{ id: 'ret', label: 'Chiều về', fromCity: destination, toCity: originCity, chosen: chosen.ret, unavailable: back.status === 'none' } as TicketLeg]
      : []),
  ];

  const checkout = async () => {
    const picks = [chosen.out, roundTrip ? chosen.ret : null].filter((c): c is NonNullable<Chosen> => c !== null);
    if (picks.length === 0 || submitting) return;
    setSubmitting(true);
    // Vé máy bay đặt trực tiếp: một đơn nháp cho một hoặc hai chặng rồi mở trang thanh toán, không qua giỏ (FR-BKG-01,
    // FR-BKG-10). Khách chưa đăng nhập được mời đăng nhập trước (startBooking), xong thì tự tạo đơn nháp.
    await startBooking(picks.map(({ option, fare }) => ({
      product: productFromApi(fare.summary), quantity: adults + kids, usingDate: option.date,
      guests: { adults, children: kids },
    })));
    setSubmitting(false);
  };

  const codes = outboundRoute
    ? [(outboundRoute.attributes as Record<string, unknown>).originAirports, (outboundRoute.attributes as Record<string, unknown>).destinationAirports]
      .map((list) => (Array.isArray(list) ? String(list[0] ?? '') : '')).filter(Boolean).join(' – ')
    : '';

  let body: React.ReactNode;
  if (outbound.status === 'loading' || (step === 'ret' && back.status === 'loading')) {
    body = (
      <div className="space-y-3.5" aria-busy="true">
        <div className="h-28 animate-pulse rounded-[20px] bg-slate-200/70" />
        {[0, 1, 2].map((i) => <div key={i} className="h-44 animate-pulse rounded-[20px] bg-slate-200/70" />)}
      </div>
    );
  } else if (outbound.status === 'error' || (step === 'ret' && back.status === 'error')) {
    body = (
      <div className={`${CARD} space-y-3 p-10 text-center`}>
        <h3 className="text-base font-bold text-slate-800">Chưa tải được chuyến bay lúc này.</h3>
        <button type="button" onClick={() => setRetry((n) => n + 1)} className="cursor-pointer rounded-lg bg-brand-600 px-4 py-2 text-xs font-bold text-white hover:bg-brand-700">Thử lại</button>
      </div>
    );
  } else if (outbound.status === 'no-route') {
    body = (
      <div className={`${CARD} space-y-4 p-8`}>
        <h3 className="font-display text-lg text-slate-900">Chưa có chặng {origin} → {destination} trên V-OTA</h3>
        {outbound.choices.length > 0 ? (
          <>
            <p className="text-sm text-slate-600">Đổi điểm đi ở ô tìm kiếm phía trên, hoặc chọn một điểm đi có chuyến tới {destination}:</p>
            <ul className="flex flex-wrap gap-2">
              {outbound.choices.map((choice) => (
                <li key={choice.city}>
                  <Link href={buildFlightResultsHref({ origin: choice.city, destination, trip })}
                    className="inline-flex h-9 items-center rounded-full border border-slate-200 bg-slate-50 px-3.5 text-sm font-semibold text-slate-700 hover:border-brand-300 hover:text-brand-700">
                    {choice.city}{choice.code && <span className="ml-1.5 text-xs font-normal text-slate-500">{choice.code}</span>}
                  </Link>
                </li>
              ))}
            </ul>
          </>
        ) : <p className="text-sm text-slate-600">Hiện chưa có chuyến bay nào tới {destination}.</p>}
      </div>
    );
  } else if (!active || days.length === 0) {
    body = (
      <div className={`${CARD} space-y-3 p-10 text-center`}>
        <h3 className="font-display text-lg text-slate-900">Chưa có chuyến bay đặt được cho {legFrom} → {legTo}</h3>
        <p className="text-sm text-slate-600">
          {step === 'ret' ? 'Không có chuyến chiều về nào cất cánh sau chuyến chiều đi đã chọn.' : 'Các chuyến đã qua hoặc hết mở bán không được hiển thị.'}
        </p>
        {step === 'ret' && <button type="button" onClick={() => setStep('out')} className="cursor-pointer text-sm font-semibold text-brand-700 hover:underline">Đổi chuyến chiều đi</button>}
      </div>
    );
  } else if (activeDate === null && wantedDate) {
    body = (
      <>
        <FlightDateStrip days={days} selected={null} onSelect={pickDay} />
        <div role="status" className={`${CARD} space-y-3 p-10 text-center`} data-testid="no-flights-on-date">
          <h3 className="font-display text-lg text-slate-900">
            Không có chuyến bay {legFrom} → {legTo} ngày {weekdayLong(wantedDate)}, {shortDate(wantedDate)}/{wantedDate.slice(0, 4)}
          </h3>
          {step === 'ret' && chosen.out && (
            <p className="text-sm text-slate-600">Không có chuyến chiều về nào ngày này cất cánh sau chuyến chiều đi đã chọn.</p>
          )}
          {pick && pick.nearest.length > 0 && (
            <>
              <p className="text-sm text-slate-600">Ngày gần nhất có chuyến:</p>
              <div className="flex flex-wrap justify-center gap-2">
                {pick.nearest.map((day) => (
                  <button key={day.date} type="button" onClick={() => pickDay(day.date)}
                    className="inline-flex min-h-11 cursor-pointer items-center gap-1.5 rounded-full border border-brand-600 bg-white px-4 text-sm font-semibold text-brand-700 hover:bg-brand-50">
                    <span>{weekdayLong(day.date)}, {shortDate(day.date)}</span>{' '}
                    <span className="font-medium tabular-nums text-slate-500">· từ {thousands(day.minPrice)}</span>
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      </>
    );
  } else {
    body = (
      <>
        <FlightDateStrip days={days} selected={activeDate} onSelect={pickDay} />
        <p className="px-0.5 text-[13px] text-slate-500" aria-live="polite">
          {visible.length} chuyến bay{visible.length !== dayOptions.length ? ` (lọc từ ${dayOptions.length})` : ''} · {legFrom} → {legTo}
          {activeDate && ` · ${weekdayLong(activeDate)}, ${shortDate(activeDate)}/${activeDate.slice(0, 4)}`}
        </p>
        {visible.length > 0 ? (
          <div className="flex flex-col gap-3.5">
            {visible.map((option) => (
              <FlightCard key={option.key} option={option} expanded={expanded.has(option.key)}
                preferredFareId={preferredFareId}
                chosen={chosen[step]?.option.key === option.key ? chosen[step]!.fare : null}
                onToggleExpanded={() => setExpanded((prev) => { const next = new Set(prev); if (!next.delete(option.key)) next.add(option.key); return next; })}
                onPick={choose} onClear={clearChoice} />
            ))}
          </div>
        ) : (
          <div className={`${CARD} space-y-3 p-10 text-center`}>
            <h3 className="font-display text-lg text-slate-900">Không có chuyến nào khớp bộ lọc</h3>
            <button type="button" onClick={() => setFilters(noFilters())} className="cursor-pointer rounded-full border border-brand-600 bg-white px-5 py-2 text-sm font-semibold text-brand-700">Đặt lại bộ lọc</button>
          </div>
        )}
      </>
    );
  }

  return (
    <section ref={rootRef} aria-label="Kết quả vé máy bay" className="relative z-10 -mt-8 scroll-mt-24 rounded-t-4xl bg-[#f1f4f9] pb-12 pt-6">
      <div className="mx-auto mb-5 flex max-w-7xl flex-wrap items-end justify-between gap-x-6 gap-y-3 px-4 sm:px-6 lg:px-8">
        <div>
          <h2 className="flex flex-wrap items-center gap-x-3 text-2xl text-slate-900 sm:text-[28px]">
            <span>{originCity}</span><span aria-label="đến">→</span><span>{destination}</span>
            {codes && <span className="font-sans text-xs font-bold tracking-widest text-slate-500">{codes}</span>}
          </h2>
          <p className="mt-1 text-sm text-slate-600">{mode === 'round' ? 'Khứ hồi' : 'Một chiều'} · {guestsText({ adults, children: kids })}</p>
        </div>
        <div role="group" aria-label="Loại vé" className="inline-flex gap-0.5 rounded-full border border-slate-200 bg-white p-[3px]">
          {([['round', 'Khứ hồi'], ['one', 'Một chiều']] as const).map(([id, label]) => (
            <button key={id} type="button" aria-pressed={mode === id} onClick={() => setTrip(id)}
              className={`cursor-pointer rounded-full px-[18px] py-1.5 text-sm font-semibold transition-colors ${mode === id ? 'bg-gradient-to-br from-brand-600 to-brand-800 text-white' : 'text-slate-600 hover:bg-slate-100'}`}>{label}</button>
          ))}
        </div>
      </div>

      {notice && (
        <div className="mx-auto mb-4 max-w-7xl px-4 sm:px-6 lg:px-8">
          <p role="alert" className="rounded-xl bg-amber-50 px-4 py-2.5 text-sm font-medium text-amber-900">
            {notice} Kết quả bên dưới vẫn là của lần tìm trước.
          </p>
        </div>
      )}

      <div className="relative mx-auto grid max-w-7xl items-start gap-5 px-4 sm:px-6 md:grid-cols-[17rem_minmax(0,1fr)] lg:px-8 xl:grid-cols-[17.5rem_minmax(0,1fr)_18.75rem]">
        <TicketPanel className="md:col-span-2 xl:order-3 xl:col-span-1 xl:sticky xl:top-4" legs={legs} activeLeg={step} onSelectLeg={setStep}
          adults={adults} kids={kids} submitting={submitting} onCheckout={() => void checkout()} />

        <FlightFilters className="md:sticky md:top-4 xl:order-1" facets={facets} airlines={airlines} filters={effective}
          onChange={setFilters} onReset={() => setFilters(noFilters())} activeCount={activeFilters} />

        <section aria-label="Danh sách chuyến bay" className="min-w-0 space-y-3.5 xl:order-2">
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2.5">
            <h3 className="font-display text-[22px] text-slate-900" aria-live="polite">{step === 'ret' ? 'Chọn vé chiều về' : 'Chọn vé chiều đi'}</h3>
            <SortMenu<FlightSort> value={sort} onChange={setSort} labels={FLIGHT_SORT_LABELS} />
          </div>
          {mode === 'round' && back.status === 'none' && <Notice tone="warn">Chưa có chuyến chiều về {destination} → {originCity} trên V-OTA. Bạn vẫn đặt được vé một chiều.</Notice>}
          {mode === 'round' && back.status === 'loading' && outbound.status === 'ready' && step === 'out' && (
            <p className="flex items-center gap-2 text-xs text-slate-500"><Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />Đang tìm chuyến chiều về…</p>
          )}
          {body}
        </section>
      </div>
    </section>
  );
};
