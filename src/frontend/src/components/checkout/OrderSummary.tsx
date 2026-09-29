'use client';

/**
 * Tóm tắt đơn (spec checkout-nhieu-buoc-hanh-khach.md §6.3): cột phải dính khi cuộn ở desktop; thanh cố định ở đáy màn hình kèm
 * bottom sheet chi tiết ở mobile. Mọi con số tiền lấy từ `CartResponse`; trong lúc một `PATCH` đang chạy thì hiện khung chờ.
 */
import React, { useState } from 'react';
import { ChevronUp, PenLine, Users } from 'lucide-react';
import { TaxonomyBadge } from '../common/TaxonomyBadge';
import { formatVnd } from '../confirmation/bookingLabels';
import type { ApiCartItem } from '../../services/booking';
import type { Taxonomy } from '../../types/travel';
import { guestsOfItem, isHotel, partyText } from './allocation';
import { formatDmy } from './checkoutRules';
import { PrimaryButton, Skeleton } from './CheckoutParts';
import type { CheckoutController } from './useCheckout';

function itemMeta(item: ApiCartItem): string {
  const g = guestsOfItem(item);
  if (isHotel(item)) {
    const end = new Date(`${item.usingDate}T00:00:00Z`);
    end.setUTCDate(end.getUTCDate() + (item.nights ?? 1));
    return `${formatDmy(item.usingDate).slice(0, 5)}–${formatDmy(end.toISOString().slice(0, 10)).slice(0, 5)} · ${item.quantity} phòng · ${g.adults + g.children} khách`;
  }
  if (item.product.taxonomy === 'flight') return `${formatDmy(item.usingDate).slice(0, 5)} · ${g.adults + g.children} khách`;
  if (item.product.taxonomy === 'combo') return `${formatDmy(item.usingDate).slice(0, 5)} · ${item.quantity} gói`;
  return `${formatDmy(item.usingDate).slice(0, 5)} · ${g.adults} người lớn${g.children ? `, ${g.children} trẻ em` : ''}`;
}

const SummaryBody: React.FC<{ ctl: CheckoutController }> = ({ ctl }) => {
  if (!ctl.cart) return null;
  return (
    <>
      <div className="flex items-center justify-between border-b border-slate-100 pb-3">
        <h3 className="text-sm font-bold text-slate-900">Đơn của bạn ({ctl.items.length} dịch vụ)</h3>
        <button type="button" onClick={() => ctl.navigate('/cart')} className="text-xs text-blue-600 hover:underline inline-flex items-center gap-1">
          <PenLine className="w-3 h-3" aria-hidden="true" />Sửa giỏ hàng
        </button>
      </div>
      <div className="flex items-center gap-2 text-xs font-semibold text-slate-700 bg-slate-50 border border-slate-100 rounded-lg px-3 py-2" data-testid="party-text">
        <Users className="w-4 h-4 text-slate-500" aria-hidden="true" />{partyText(ctl.drafts)}
      </div>
      <div className="divide-y divide-slate-100" data-testid="summary-items">
        {ctl.items.map((item) => (
          <div key={item.cartItemId} className="py-2.5 flex items-start gap-3">
            <div className="min-w-0 flex-1 space-y-0.5">
              <div className="flex items-center gap-1.5"><TaxonomyBadge taxonomy={item.product.taxonomy as Taxonomy} size="sm" /></div>
              <div className="text-xs font-bold text-slate-900 truncate">{item.product.name}</div>
              <div className="text-[11px] text-slate-500">{itemMeta(item)}</div>
            </div>
            <span className="text-xs font-bold text-slate-800 tabular-nums whitespace-nowrap">
              {ctl.pending[item.cartItemId] ? <Skeleton width={70} /> : formatVnd(item.lineTotal)}
            </span>
          </div>
        ))}
      </div>
      <div className="pt-3 border-t border-slate-200 flex justify-between items-baseline gap-3">
        <span className="text-sm font-bold text-slate-900">Tổng thanh toán</span>
        {ctl.anyPending ? <Skeleton width={110} /> : <span className="text-lg font-extrabold text-blue-900 tabular-nums" data-testid="summary-total">{formatVnd(ctl.cart.total)}</span>}
      </div>
    </>
  );
};

export const SummaryPanel: React.FC<{ ctl: CheckoutController }> = ({ ctl }) => (
  <aside className="hidden lg:block lg:sticky lg:top-6 bg-white p-5 sm:p-6 rounded-2xl border border-slate-200 shadow-xl space-y-4" aria-label="Tóm tắt đơn">
    <SummaryBody ctl={ctl} />
  </aside>
);

/** Thanh cố định ở đáy màn hình (dưới breakpoint `lg`): đoàn khách, tổng tiền và nút chính của bước. */
export const MobileBar: React.FC<{ ctl: CheckoutController }> = ({ ctl }) => {
  const [open, setOpen] = useState(false);
  if (!ctl.cart) return null;
  const canPay = ctl.termsAgreed && !ctl.hasUnavailable && !ctl.submitting && !ctl.anyPending;
  return (
    <>
      <div className="lg:hidden fixed bottom-0 inset-x-0 z-30 bg-white border-t border-slate-200 shadow-[0_-6px_20px_-8px_rgba(15,23,42,0.18)] px-4 pt-3 pb-3 space-y-2.5" data-testid="mobile-bar">
        <button type="button" onClick={() => setOpen(true)} aria-label="Xem tóm tắt đơn" className="w-full flex items-center justify-between gap-3 text-left">
          <span className="text-xs font-semibold text-slate-600 flex items-center gap-1.5"><Users className="w-3.5 h-3.5" aria-hidden="true" />{partyText(ctl.drafts)}</span>
          <span className="flex items-center gap-1 text-base font-extrabold text-blue-900 tabular-nums">
            {ctl.anyPending ? <Skeleton width={100} /> : formatVnd(ctl.cart.total)}<ChevronUp className="w-4 h-4 text-slate-500" aria-hidden="true" />
          </span>
        </button>
        {ctl.step === 'travelers' && <PrimaryButton full onClick={() => void ctl.continueFromTravelers()} busy={ctl.busy}>Tiếp tục</PrimaryButton>}
        {ctl.step === 'services' && <PrimaryButton full onClick={() => void ctl.continueFromServices()} busy={ctl.busy}>Tiếp tục</PrimaryButton>}
        {ctl.step === 'review' && (
          <PrimaryButton full onClick={() => void ctl.pay()} disabled={!canPay} busy={ctl.submitting ? 'Đang giữ chỗ…' : null}>
            Thanh toán {formatVnd(ctl.cart.total)}
          </PrimaryButton>
        )}
      </div>
      {open && (
        <>
          <div className="lg:hidden fixed inset-0 z-40 bg-slate-900/40" onClick={() => setOpen(false)} aria-hidden="true" />
          <div role="dialog" aria-modal="true" aria-label="Tóm tắt đơn" className="lg:hidden fixed inset-x-0 bottom-0 z-50 bg-white rounded-t-2xl p-5 space-y-4 max-h-[80%] overflow-y-auto shadow-2xl">
            <div className="w-10 h-1 rounded-full bg-slate-300 mx-auto" />
            <SummaryBody ctl={ctl} />
            <button type="button" onClick={() => setOpen(false)} className="w-full py-2.5 border border-slate-300 rounded-xl text-sm font-semibold text-slate-700">Đóng</button>
          </div>
        </>
      )}
    </>
  );
};
