'use client';

import React from 'react';
import { ArrowRight } from 'lucide-react';
import { estimateFares } from '../../../components/checkout/fareEstimate';
import { formatVnd } from '../../../components/confirmation/bookingLabels';
import { dayTag, groupDigits } from './flightFormat';
import type { FareOption, FlightOption } from './flightModel';

export type LegId = 'out' | 'ret';

export interface TicketLeg {
  id: LegId;
  label: string;
  fromCity: string;
  toCity: string;
  chosen: { option: FlightOption; fare: FareOption } | null;
  /** Tuyến chiều về chưa có trong catalog: chỉ đặt được vé một chiều. */
  unavailable?: boolean;
}

interface TicketPanelProps {
  legs: TicketLeg[];
  activeLeg: LegId;
  onSelectLeg: (id: LegId) => void;
  adults: number;
  /** Số trẻ em. */
  kids: number;
  submitting: boolean;
  onCheckout: () => void;
  className?: string;
}

/**
 * "Vé của tôi": các chặng đã chọn và tổng ước tính. Đây là số để hiển thị (cùng công thức với hộp đặt ở trang chi tiết,
 * `estimateFares`); giá chính thức do Backend tính khi thêm vào giỏ và ở bước thanh toán (FR-BKG-10, frontend §4.3).
 */
export const TicketPanel: React.FC<TicketPanelProps> = ({ legs, activeLeg, onSelectLeg, adults, kids, submitting, onCheckout, className = '' }) => {
  const required = legs.filter((leg) => !leg.unavailable);
  const chosen = required.filter((leg) => leg.chosen);
  const total = chosen.reduce((sum, leg) => sum + estimateFares({
    taxonomy: 'flight', unitPrice: leg.chosen!.fare.price, attributes: null,
    quantity: adults + kids, nights: null, adults, children: kids,
  }).total, 0);
  const ready = required.length > 0 && chosen.length === required.length;
  const missing = required.find((leg) => !leg.chosen);
  const hint = ready ? '' : chosen.length === 0 ? 'Chọn chuyến bay để bắt đầu.' : `Chọn vé ${missing?.label.toLowerCase()} để tiếp tục.`;
  const guests = adults + kids;

  return (
    <aside aria-label="Vé của tôi" className={`overflow-hidden rounded-[20px] border border-slate-100 bg-white shadow-[0_8px_40px_rgba(15,28,58,0.05)] ${className}`}>
      <div className="bg-[linear-gradient(115deg,transparent_38%,rgba(255,255,255,0.42)_38%_52%,transparent_52%_60%,rgba(255,255,255,0.42)_60%_66%,transparent_66%),linear-gradient(100deg,#a4f0de,#eafaf6_70%)] px-[18px] pb-3.5 pt-5 font-display text-[19px] text-slate-900 md:pt-4.5">
        Vé của tôi
      </div>
      <div className="bg-slate-50 md:grid md:grid-cols-[minmax(0,1fr)_18.75rem] xl:block">
        <div className="grid gap-3 p-3 md:grid-cols-2 md:p-4 xl:grid-cols-1">
          {legs.map((leg) => {
            const active = leg.id === activeLeg;
            const pick = leg.chosen;
            return (
              <button key={leg.id} type="button" disabled={leg.unavailable} aria-current={active ? 'step' : undefined}
                onClick={() => onSelectLeg(leg.id)}
                className={`flex w-full cursor-pointer flex-col gap-2 rounded-[14px] border-2 bg-white px-4 py-3.5 text-left disabled:cursor-default ${active ? 'border-brand-600' : 'border-transparent'}`}>
                <span className={`self-start rounded-full px-3 py-0.5 text-xs font-semibold ${active ? 'bg-gradient-to-br from-brand-600 to-brand-800 text-white' : 'bg-slate-100 text-slate-500'}`}>{leg.label}</span>
                <span className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5 font-semibold text-slate-900">
                  {leg.fromCity}<ArrowRight className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />{leg.toCity}
                </span>
                {leg.unavailable && <span className="text-xs text-amber-700">Chưa có tuyến chiều về trên X-OTA.</span>}
                {pick && (
                  <>
                    <span className="flex flex-wrap items-baseline gap-x-2 tabular-nums">
                      <b className="text-[17px] font-semibold text-brand-700">{pick.option.depClock} → {pick.option.arrClock}</b>
                      <em className="text-xs not-italic text-slate-500">{dayTag(pick.option.date)}</em>
                    </span>
                    <span className="flex justify-between gap-2 text-xs text-slate-500">
                      <span>{pick.option.flightNumber} · {pick.option.airline}</span>
                      <b className="tabular-nums text-slate-900">{groupDigits(pick.fare.price)} ₫</b>
                    </span>
                    {pick.fare.simulated && <span className="self-start rounded bg-amber-100 px-1.5 py-0.5 text-[10.5px] font-bold text-amber-800">Giá minh hoạ</span>}
                  </>
                )}
              </button>
            );
          })}
        </div>

        <div className="border-t border-slate-200 bg-white p-4 md:border-l md:border-t-0 xl:border-l-0 xl:border-t">
          <div className="flex items-baseline justify-between gap-2.5">
            <span className="font-medium text-slate-500">Tổng ước tính</span>
            <b className="text-lg font-bold tabular-nums" data-testid="ticket-total">{chosen.length > 0 ? formatVnd(total) : '—'}</b>
          </div>
          <p className="mb-3 mt-0.5 text-right text-[11px] text-slate-500">
            {chosen.length > 0 ? `${guests} khách · giá chính thức ở bước thanh toán` : 'Giá chính thức ở bước thanh toán'}
          </p>
          <button type="button" onClick={onCheckout} disabled={!ready || submitting}
            className="h-12 w-full cursor-pointer rounded-full bg-gradient-to-br from-brand-600 to-brand-800 font-display text-[17px] text-white shadow-[0_6px_14px_rgba(6,82,207,0.24)] enabled:hover:brightness-110 disabled:cursor-not-allowed disabled:bg-none disabled:bg-slate-200 disabled:text-slate-500 disabled:shadow-none">
            {submitting ? 'Đang thêm vào giỏ…' : 'Đặt vé'}
          </button>
          <p role="status" className="mt-2.5 min-h-[18px] text-center text-xs text-slate-500">{hint}</p>
        </div>
      </div>
    </aside>
  );
};
