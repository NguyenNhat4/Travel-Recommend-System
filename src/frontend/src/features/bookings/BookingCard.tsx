'use client';

import React from 'react';
import Link from 'next/link';
import { Building2, Flag, Loader2, Plane, Sparkles, Ticket } from 'lucide-react';
import { formatDateTimeVn, formatVnd } from '../../components/confirmation/bookingLabels';
import type { BookingSummary } from '../../services/booking';
import { canRebook, cardNote, cardStatus, itemSubtitle } from './historyModel';
import { TONE_PILL } from './tone';

const ICONS: Record<string, React.ComponentType<{ className?: string; 'aria-hidden'?: boolean }>> = {
  hotel: Building2, flight: Plane, attraction: Ticket, combo: Sparkles, golf: Flag,
};

const NOTE_TONE = {
  ok: 'bg-emerald-50 text-emerald-800',
  warn: 'bg-amber-50 text-amber-900',
  bad: 'bg-rose-50 text-rose-800',
  off: 'bg-slate-100 text-slate-700',
} as const;

interface BookingCardProps {
  booking: BookingSummary;
  rebooking: boolean;
  onRebook: (referenceCode: string) => void;
}

export const BookingCard: React.FC<BookingCardProps> = ({ booking, rebooking, onRebook }) => {
  const status = cardStatus(booking);
  const note = cardNote(booking);
  const detailHref = `/booking/${encodeURIComponent(booking.referenceCode)}`;
  const payNow = booking.status === 'PENDING_PAYMENT' && booking.tab === 'upcoming';
  const first = booking.items[0];
  const [, month, day] = first.usingDate.split('-');
  const dim = booking.tab === 'cancelled';
  return (
    <article className="overflow-hidden rounded-2xl border border-slate-200 bg-white" data-testid="booking-card">
      <div className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-3.5 gap-y-2 px-4 py-3.5 max-sm:grid-cols-[auto_minmax(0,1fr)]">
        <div
          className={`w-14 rounded-xl py-1.5 text-center leading-[1.1] ${dim ? 'bg-slate-100 text-slate-600' : 'bg-brand-50 text-brand-700'}`}
          aria-hidden="true" data-testid="booking-date-tile"
        >
          <small className="block text-[10.5px] font-bold uppercase tracking-wider">THG {Number(month)}</small>
          <b className="block text-[22px] font-bold tabular-nums">{Number(day)}</b>
        </div>
        <div className="min-w-0">
          <Link href={detailHref} className="font-mono text-[13px] font-semibold text-slate-900 hover:text-brand-700 hover:underline hover:underline-offset-4">
            {booking.referenceCode}
          </Link>
          <p className="text-xs text-slate-500">Đặt lúc {formatDateTimeVn(booking.createdAt)}</p>
        </div>
        <span className={`inline-flex min-h-7 items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold max-sm:col-span-full max-sm:justify-self-start ${TONE_PILL[status.tone]}`}>
          <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-current" />
          {status.label}
        </span>
      </div>

      <ul className="border-t border-slate-200 px-4">
        {booking.items.map((item) => {
          const Icon = ICONS[item.taxonomy] ?? Ticket;
          return (
            <li key={item.bookingItemId} className="grid grid-cols-[2.25rem_minmax(0,1fr)_auto] items-center gap-3 border-t border-slate-200 py-3 first:border-t-0">
              <span className="grid h-9 w-9 place-items-center rounded-xl bg-slate-100 text-brand-700">
                <Icon className="h-[18px] w-[18px]" aria-hidden={true} />
              </span>
              <div className="min-w-0">
                <div className="break-words text-sm font-medium text-slate-900">{item.name}</div>
                <div className="text-xs text-slate-500">{itemSubtitle(item)}</div>
              </div>
              <div className="whitespace-nowrap text-[13px] font-medium text-slate-800 tabular-nums">{formatVnd(item.lineTotal)}</div>
            </li>
          );
        })}
      </ul>

      {note && (
        <div role="status" className={`mx-4 mb-3.5 grid gap-0.5 rounded-xl px-3 py-2.5 text-[13px] ${NOTE_TONE[note.tone]}`}>
          <b className="font-semibold">{note.title}</b>
          <span>{note.text}</span>
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2.5 border-t border-slate-200 bg-slate-50 px-4 py-3 max-sm:flex-col max-sm:items-stretch">
        <div>
          <span className="block text-[11px] text-slate-500">Tổng thanh toán</span>
          <strong className="text-[17px] font-bold tabular-nums text-slate-900">{formatVnd(booking.total)}</strong>
        </div>
        <div className="flex flex-wrap gap-2 max-sm:[&>*]:flex-1">
          {!payNow && (
            <Link href={detailHref} className="inline-flex min-h-11 items-center justify-center rounded-full border border-slate-200 bg-white px-4 text-[13px] font-semibold text-slate-800 hover:border-brand-600 hover:text-brand-700">
              Xem chi tiết
            </Link>
          )}
          {payNow && (
            <Link href={detailHref} className="inline-flex min-h-11 items-center justify-center rounded-full bg-brand-600 px-5 text-[13px] font-semibold text-white hover:bg-brand-700">
              Tiếp tục thanh toán
            </Link>
          )}
          {canRebook(booking) && (
            <button
              type="button" disabled={rebooking} onClick={() => onRebook(booking.referenceCode)}
              className="inline-flex min-h-11 items-center justify-center gap-2 rounded-full bg-brand-600 px-5 text-[13px] font-semibold text-white hover:bg-brand-700 disabled:bg-slate-300"
            >
              {rebooking && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
              Đặt lại
            </button>
          )}
        </div>
      </div>
    </article>
  );
};
