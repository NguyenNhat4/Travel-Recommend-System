'use client';

import React, { useState } from 'react';
import { Briefcase, Check, ChevronRight, Plane, ShoppingBag } from 'lucide-react';
import { SkeletonBlock } from '../../../components/common/Skeleton';
import { AirlineBadge } from './AirlineBadge';
import { dateOfIso, dayTag, groupDigits } from './flightFormat';
import { formatDuration, type FareOption, type FlightOption } from './flightModel';

interface FlightCardProps {
  option: FlightOption;
  /** Hạng của hành trình này đang nằm trong "Vé của tôi", nếu có. */
  chosen: FareOption | null;
  expanded: boolean;
  onToggleExpanded: () => void;
  preferredFareId?: string | null;
  onPick: (option: FlightOption, fare: FareOption) => void;
  onClear: () => void;
}

const kg = (value: number): string => (value === 0 ? 'Không gồm' : `${value} kg`);

const TimeBox: React.FC<{ clock: string; tag: string; code: string }> = ({ clock, tag, code }) => (
  <div className="flex items-center gap-2.5 rounded-2xl border border-brand-200 px-3.5 py-2.5 @max-[30rem]:flex-col @max-[30rem]:items-start @max-[30rem]:gap-0.5 @max-[30rem]:px-2.5">
    <span className="text-2xl font-semibold tabular-nums tracking-tight text-brand-600 @max-[30rem]:text-xl">{clock}</span>
    <span className="flex flex-col whitespace-nowrap text-xs leading-snug text-slate-500 @max-[30rem]:flex-row @max-[30rem]:items-baseline @max-[30rem]:gap-1.5">
      <span>{tag}</span>
      <b className="text-base font-semibold text-slate-900 @max-[30rem]:order-first @max-[30rem]:text-[13px]">{code}</b>
    </span>
  </div>
);

/** Khung thẻ chuyến bay trong lúc tải: hai ô giờ hai bên đường bay, dòng hãng và hạng, số hiệu, cột giá kèm nút Chọn. */
export const FlightCardSkeleton: React.FC = () => (
  <div aria-hidden="true" className="@container rounded-[20px] border-[1.5px] border-slate-100 bg-white">
    <div className="grid @min-[40rem]:grid-cols-[minmax(0,1fr)_12rem]">
      <div className="flex min-w-0 flex-col gap-3 p-3.5 @min-[30rem]:px-5 @min-[30rem]:py-4">
        <div className="grid grid-cols-[auto_minmax(4rem,1fr)_auto] items-center gap-2 @min-[30rem]:gap-3.5">
          <SkeletonBlock className="h-[58px] w-28 rounded-2xl" />
          <div className="flex flex-col items-center gap-1.5">
            <SkeletonBlock className="h-1.5 w-full max-w-[7.5rem] rounded-full" />
            <SkeletonBlock className="h-3.5 w-20 rounded" />
          </div>
          <SkeletonBlock className="h-[58px] w-28 rounded-2xl" />
        </div>
        <div className="flex items-center justify-between gap-3">
          <SkeletonBlock className="h-4 w-32 rounded" />
          <SkeletonBlock className="h-5 w-24 rounded-full" />
        </div>
        <div className="flex items-center justify-between gap-3">
          <SkeletonBlock className="h-5 w-20 rounded" />
          <SkeletonBlock className="h-4 w-36 rounded" />
        </div>
      </div>
      <div className="mx-3.5 flex items-center justify-between gap-3 border-t border-slate-200 py-3.5 @min-[30rem]:mx-5 @min-[40rem]:mx-0 @min-[40rem]:my-4 @min-[40rem]:flex-col @min-[40rem]:items-end @min-[40rem]:justify-center @min-[40rem]:border-l @min-[40rem]:border-t-0 @min-[40rem]:px-5 @min-[40rem]:py-0">
        <div className="space-y-1.5 @min-[40rem]:flex @min-[40rem]:flex-col @min-[40rem]:items-end">
          <SkeletonBlock className="h-6 w-28 rounded" />
          <SkeletonBlock className="h-3 w-12 rounded" />
        </div>
        <SkeletonBlock className="h-11 w-[8.25rem] rounded-full" />
      </div>
    </div>
  </div>
);

/** Khung dải ngày phía trên danh sách chuyến: bảy ô ngày kèm giá thấp nhất. */
export const FlightDateStripSkeleton: React.FC = () => (
  <div aria-hidden="true" className="flex gap-2 overflow-hidden rounded-[20px] border border-slate-100 bg-white px-3 py-4 sm:px-5">
    {[0, 1, 2, 3, 4, 5, 6].map((i) => <SkeletonBlock key={i} className="h-[76px] min-w-[74px] shrink-0 rounded-[13px]" />)}
  </div>
);

/**
 * Một hành trình bay: giờ đi, giờ đến, hãng, thời lượng, hạng vé, giá và nút Chọn. Hành lý chỉ hiện khi nguồn có số liệu
 * (`null` là chưa biết, không hiện "0 kg"). Có từ hai hạng thì chọn hạng ngay trong thẻ, giá và nút theo hạng đó.
 */
export const FlightCard: React.FC<FlightCardProps> = ({ option, chosen, preferredFareId, expanded, onToggleExpanded, onPick, onClear }) => {
  const defaultFare = option.fares.find((fare) => fare.productId === preferredFareId)
    ?? [...option.fares].sort((a, b) => a.price - b.price)[0];
  const [fareId, setFareId] = useState(defaultFare.productId);
  const fare = option.fares.find((f) => f.productId === (chosen?.productId ?? fareId)) ?? defaultFare;
  const selected = chosen !== null;
  const detailId = `flight-detail-${option.key.replace(/[^a-zA-Z0-9]/g, '')}`;
  const stopLabel = option.nonstop === true ? 'Bay thẳng' : option.nonstop === false ? 'Có điểm dừng' : null;
  const knownBags = fare.carryOnKg !== null || fare.checkedKg !== null;

  return (
    <article className={`@container rounded-[20px] border-[1.5px] bg-white shadow-[0_8px_40px_rgba(15,28,58,0.05)] ${selected ? 'border-brand-600' : 'border-slate-100'}`}>
      <div className="grid @min-[40rem]:grid-cols-[minmax(0,1fr)_12rem]">
        <div className="flex min-w-0 flex-col gap-3 p-3.5 @min-[30rem]:px-5 @min-[30rem]:py-4">
          <div className="grid grid-cols-[auto_minmax(4rem,1fr)_auto] items-center gap-2 @min-[30rem]:gap-3.5">
            <TimeBox clock={option.depClock} tag={dayTag(option.date)} code={option.from} />
            <div className="flex min-w-0 flex-col items-center gap-1.5 text-center">
              <AirlineBadge name={option.airline} code={option.airlineCode} />
              <span className="flex w-full max-w-[7.5rem] items-center text-slate-400" aria-hidden="true">
                <i className="h-1.5 w-1.5 shrink-0 rounded-full bg-current" />
                <span className="h-px flex-1 bg-current opacity-70" />
                {option.nonstop === true && <Plane className="mx-0.5 h-[15px] w-[15px] shrink-0 rotate-45 text-brand-600" />}
                {option.nonstop === false && <i className="h-2 w-2 shrink-0 rounded-full border-[1.5px] border-current bg-white" />}
                {option.nonstop !== null && <span className="h-px flex-1 bg-current opacity-70" />}
                <i className="h-1.5 w-1.5 shrink-0 rounded-full bg-current" />
              </span>
              <span className="text-xs leading-snug text-slate-900">
                {option.durationMinutes !== null && <b className="font-semibold">{formatDuration(option.durationMinutes)}</b>}
                {stopLabel && <span className="ml-1 inline-block text-slate-500">{stopLabel}</span>}
              </span>
            </div>
            <TimeBox clock={option.arrClock} tag={dayTag(option.date, option.arrDayOffset)} code={option.to} />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1.5">
            <span className="text-[13px] font-medium text-slate-500">{option.airline}</span>
            {option.fares.length === 1 ? (
              fare.name && <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[10.5px] font-bold uppercase tracking-wider text-slate-800">{fare.name}</span>
            ) : (
              <div role="radiogroup" aria-label={`Hạng vé ${option.flightNumber}`} className="flex flex-wrap gap-1.5">
                {option.fares.map((f) => (
                  <button key={f.productId} type="button" role="radio" aria-checked={f.productId === fare.productId} disabled={selected}
                    onClick={() => setFareId(f.productId)}
                    className={`cursor-pointer rounded-full border px-2.5 py-0.5 text-[11px] font-semibold transition-colors disabled:cursor-default ${
                      f.productId === fare.productId ? 'border-brand-600 bg-brand-50 text-brand-700' : 'border-slate-200 text-slate-600 enabled:hover:border-brand-300'}`}>
                    {f.name || 'Giá rẻ nhất'}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
            <span className="text-[15px] font-semibold">{option.flightNumber}</span>
            <span className="flex items-center gap-3.5 text-[13px] text-slate-500">
              {knownBags && fare.carryOnKg !== null && <span className="inline-flex items-center gap-1.5"><ShoppingBag className="h-4 w-4" aria-hidden="true" />{kg(fare.carryOnKg)} xách tay</span>}
              {knownBags && fare.checkedKg !== null && <span className="inline-flex items-center gap-1.5"><Briefcase className="h-4 w-4" aria-hidden="true" />{kg(fare.checkedKg)} ký gửi</span>}
              <button type="button" onClick={onToggleExpanded} aria-expanded={expanded} aria-controls={detailId} aria-label={`Chi tiết chuyến ${option.flightNumber}`}
                className="-mr-1.5 grid h-7 w-7 cursor-pointer place-items-center rounded-full text-slate-500 hover:bg-slate-100">
                <ChevronRight className={`h-[18px] w-[18px] transition-transform ${expanded ? 'rotate-90' : ''}`} aria-hidden="true" />
              </button>
            </span>
          </div>
        </div>

        <div className="mx-3.5 flex items-center justify-between gap-3 border-t border-slate-200 py-3.5 @min-[30rem]:mx-5 @min-[40rem]:mx-0 @min-[40rem]:my-4 @min-[40rem]:flex-col @min-[40rem]:items-stretch @min-[40rem]:justify-center @min-[40rem]:border-l @min-[40rem]:border-t-0 @min-[40rem]:px-5 @min-[40rem]:py-0 @min-[40rem]:text-right">
          <div>
            <b className="text-xl font-bold tracking-tight tabular-nums text-slate-900">{groupDigits(fare.price)}<u className="ml-px text-[13px]">₫</u></b>
            <span className="block text-xs text-slate-500">/ khách</span>
            {fare.simulated && <span className="mt-0.5 inline-block rounded bg-amber-100 px-1.5 py-0.5 text-[10.5px] font-bold text-amber-800">Giá minh hoạ</span>}
            {fare.expired && <span className="block text-[11px] text-amber-700">Giá có thể đã thay đổi</span>}
          </div>
          <button type="button" aria-pressed={selected} onClick={() => (selected ? onClear() : onPick(option, fare))}
            aria-label={`${selected ? 'Bỏ chọn' : 'Chọn'} chuyến ${option.flightNumber}`}
            className={`inline-flex h-11 min-w-[8.25rem] cursor-pointer items-center justify-center gap-1.5 rounded-full px-[18px] font-display text-base transition ${
              selected ? 'bg-white text-brand-700 shadow-[inset_0_0_0_1.5px_var(--color-brand-600)]' : 'bg-gradient-to-br from-brand-600 to-brand-800 text-white shadow-[0_6px_14px_rgba(6,82,207,0.24)] hover:brightness-110'}`}>
            {selected ? <><Check className="h-4 w-4" aria-hidden="true" />Đã chọn</> : 'Chọn'}
          </button>
        </div>

        {expanded && (
          <div id={detailId} className="grid gap-x-7 gap-y-5 border-t border-dashed border-slate-200 px-3.5 pb-5 pt-4 @min-[30rem]:px-5 @min-[40rem]:col-span-2 @min-[40rem]:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
            <div>
              <h4 className="mb-2.5 text-xs font-bold uppercase tracking-wider text-slate-500">Hành trình</h4>
              <ol className="space-y-1 text-sm">
                <li><b className="tabular-nums">{option.depClock}</b> · <b>{option.from}</b>{option.fromCity && ` · ${option.fromCity}`}</li>
                <li className="text-xs text-slate-500">{option.flightNumber} · {option.airline}{option.durationMinutes !== null && ` · ${formatDuration(option.durationMinutes)}`}</li>
                <li><b className="tabular-nums">{option.arrClock}</b> · <b>{option.to}</b>{option.toAirportName ? ` · ${option.toAirportName}` : option.toCity && ` · ${option.toCity}`}</li>
              </ol>
              {option.priceObservedAt && <p className="mt-2.5 text-xs text-slate-500">Giá ghi nhận ngày {dateOfIso(option.priceObservedAt)}.</p>}
            </div>
            <div>
              <h4 className="mb-2.5 text-xs font-bold uppercase tracking-wider text-slate-500">Hạng vé</h4>
              <ul className="space-y-2 text-[13px]">
                {option.fares.map((f) => (
                  <li key={f.productId} className="flex flex-col gap-0.5 border-b border-slate-100 pb-2 last:border-b-0">
                    <span className="flex items-baseline justify-between gap-3">
                      <span className="text-slate-600">{f.name || 'Giá rẻ nhất'}{f.simulated && <em className="ml-1.5 rounded bg-amber-100 px-1.5 py-0.5 text-[10.5px] font-bold not-italic text-amber-800">Giá minh hoạ</em>}</span>
                      <b className="tabular-nums">{groupDigits(f.price)} ₫</b>
                    </span>
                    {(f.carryOnKg !== null || f.checkedKg !== null) && (
                      <span className="text-xs text-slate-500">
                        {f.carryOnKg !== null && `Xách tay: ${kg(f.carryOnKg)}`}{f.carryOnKg !== null && f.checkedKg !== null && ' · '}{f.checkedKg !== null && `Ký gửi: ${kg(f.checkedKg)}`}
                      </span>
                    )}
                    {f.expired && <span className="text-xs text-amber-700">Giá có thể đã thay đổi</span>}
                  </li>
                ))}
              </ul>
              <p className="mt-2.5 text-xs text-slate-500">Hành lý, suất ăn và điều kiện đổi vé chỉ hiện khi hãng công bố.</p>
            </div>
          </div>
        )}
      </div>
    </article>
  );
};
