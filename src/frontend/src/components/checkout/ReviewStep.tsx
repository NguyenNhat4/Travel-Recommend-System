'use client';

/**
 * Bước ③ Xem lại và thanh toán (spec checkout-nhieu-buoc-hanh-khach.md §6.7). Tổng thanh toán là `CartResponse.total`; chỉ khi bấm
 * Thanh toán mới giữ chỗ, tạo đơn và chuyển sang Stripe (FR-BKG-06).
 */
import React from 'react';
import { AlertTriangle, ArrowLeft, Baby, ChevronRight, CreditCard, Lock, PenLine, RefreshCw, Timer, User } from 'lucide-react';
import { FlightSummary } from '../common/FlightSummary';
import { TaxonomyBadge } from '../common/TaxonomyBadge';
import { formatDateTimeVn, formatVnd } from '../confirmation/bookingLabels';
import type { ApiCartItem } from '../../services/booking';
import type { Taxonomy } from '../../types/travel';
import { displayName, isHotel, shortName } from './allocation';
import { ageOn, formatDmy, normalizeName } from './checkoutRules';
import { PrimaryButton, SectionTitle, Skeleton, cardClass } from './CheckoutParts';
import { cancelDeadlinePassed, cancelDeadlineText, type Banner, type CheckoutController } from './useCheckout';

/** Phương thức thanh toán. Hiện chỉ Stripe; mục khác hiển thị vô hiệu hoá, nhãn "Sắp có" (user-flow §3.3). */
const PAYMENT_METHODS = [
  { id: 'stripe', label: 'Stripe — Thẻ thanh toán (chế độ test)', enabled: true },
  { id: 'ewallet', label: 'Ví điện tử', enabled: false },
  { id: 'bank_transfer', label: 'Chuyển khoản ngân hàng', enabled: false },
] as const;

const FARE_LABEL = { ADULT: 'Người lớn', CHILD: 'Trẻ em', ROOM: 'Giá phòng', PACKAGE: 'Gói' } as const;

function BannerView({ banner, onAcceptPrice, onRetry, onBack }: { banner: Banner; onAcceptPrice: () => void; onRetry: () => void; onBack: () => void }) {
  return (
    <div role="alert" className="flex items-start gap-2 p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800">
      <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
      <div className="space-y-2 flex-1">
        {banner.kind === 'price' && (
          <>
            <p>
              Giá {banner.fareType === 'CHILD' ? 'vé trẻ em của ' : ''}{banner.name} đã đổi từ {formatVnd(banner.oldPrice)} thành {formatVnd(banner.newPrice)}.
            </p>
            <button type="button" onClick={onAcceptPrice} className="font-bold underline">Cập nhật và tiếp tục</button>
          </>
        )}
        {(banner.kind === 'unavailable' || banner.kind === 'date') && (
          <>
            <p>{banner.text}</p>
            <button type="button" onClick={onBack} className="font-bold underline">Quay lại giỏ</button>
          </>
        )}
        {banner.kind === 'error' && (
          <>
            <p>{banner.text}</p>
            {banner.retryable && <button type="button" onClick={onRetry} className="font-bold underline flex items-center gap-1"><RefreshCw className="w-3 h-3" aria-hidden="true" /> Thử lại</button>}
            {banner.requestId && <p className="text-[10px] text-rose-500 font-mono">Mã yêu cầu: {banner.requestId}</p>}
          </>
        )}
      </div>
    </div>
  );
}

const ItemReview: React.FC<{ ctl: CheckoutController; item: ApiCartItem }> = ({ ctl, item }) => {
  const alloc = ctl.allocs[item.cartItemId];
  const guests = ctl.guestsOfAlloc(item);
  const pending = Boolean(ctl.pending[item.cartItemId]);
  const summary = isHotel(item)
    ? `${alloc?.rooms.length ?? item.quantity} phòng, ${guests.adults + guests.children} khách`
    : item.product.taxonomy === 'combo'
      ? `${item.quantity} gói`
      : `${guests.adults} người lớn${guests.children ? `, ${guests.children} trẻ em` : ''}`;
  const rooms = isHotel(item) && alloc
    ? alloc.rooms.map((room, k) => `Phòng ${k + 1}: ${room.refs.map((ref) => {
      const d = ctl.drafts.find((x) => x.ref === ref);
      return d ? `${shortName(d, ctl.drafts)}${ref === room.lead ? ' (đại diện)' : ''}` : ref;
    }).join(', ')}`).join(' · ')
    : null;
  return (
    <div className="py-3 flex items-start gap-3" data-testid="review-item">
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex items-center gap-2 flex-wrap">
          <TaxonomyBadge taxonomy={item.product.taxonomy as Taxonomy} size="sm" />
          <span className="text-sm font-semibold text-slate-900">{item.product.name}</span>
        </div>
        <FlightSummary product={item.product} />
        <div className="text-xs text-slate-500 tabular-nums">{formatDmy(item.usingDate)}{isHotel(item) ? ` · ${item.nights ?? 1} đêm` : ''} · {summary}</div>
        {rooms && <div className="text-xs text-slate-600">{rooms}</div>}
        <details className="text-xs">
          <summary className="cursor-pointer select-none text-blue-600 font-semibold inline-flex items-center gap-1">
            <ChevronRight className="w-3.5 h-3.5" aria-hidden="true" />Chi tiết giá
          </summary>
          <div className="mt-1.5 space-y-1 tabular-nums text-slate-600">
            {(item.fares ?? []).map((f) => (
              <div key={f.fareType}>
                {FARE_LABEL[f.fareType]}: {f.fareType === 'ROOM' ? `${formatVnd(f.unitPrice)} × ${f.nights} đêm × ${f.count} phòng` : `${f.count} × ${formatVnd(f.unitPrice)}`} = <b className="text-slate-800">{formatVnd(f.amount)}</b>
              </div>
            ))}
          </div>
        </details>
      </div>
      <span className="text-sm font-bold text-slate-900 tabular-nums whitespace-nowrap">{pending ? <Skeleton width={70} /> : formatVnd(item.lineTotal)}</span>
    </div>
  );
};

export const ReviewStep: React.FC<{ ctl: CheckoutController }> = ({ ctl }) => {
  const cart = ctl.cart;
  const deadline = cancelDeadlineText(ctl.earliest);
  const deadlinePassed = cancelDeadlinePassed(ctl.earliest);
  if (!cart) return null;
  const canPay = ctl.termsAgreed && ctl.method === 'stripe' && !ctl.hasUnavailable && !ctl.submitting && !ctl.anyPending;
  return (
    <>
      <div className="space-y-1">
        <h2 id="step-heading" tabIndex={-1} className="text-xl font-extrabold text-slate-900 outline-hidden">Xem lại và thanh toán</h2>
        <p className="text-sm text-slate-500">Kiểm tra họ tên và dịch vụ trước khi sang trang thanh toán.</p>
      </div>

      <section className={cardClass} aria-label="Hành khách">
        <SectionTitle
          title={`Hành khách (${ctl.drafts.length})`}
          extra={<button type="button" onClick={() => ctl.goto('travelers')} aria-label="Sửa hành khách" className="text-xs font-semibold text-blue-600 hover:underline inline-flex items-center gap-1"><PenLine className="w-3 h-3" aria-hidden="true" />Sửa</button>}
        />
        <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {ctl.drafts.map((d) => {
            const birth = d.type === 'CHILD' ? ctl.parseDob(d.birthText) : null;
            return (
              <li key={d.ref} className="flex items-center gap-2.5 rounded-lg bg-slate-50 border border-slate-100 px-3 py-2">
                <span className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 ${d.type === 'ADULT' ? 'bg-blue-100 text-blue-700' : 'bg-amber-100 text-amber-800'}`}>
                  {d.type === 'ADULT' ? <User className="w-3.5 h-3.5" aria-hidden="true" /> : <Baby className="w-3.5 h-3.5" aria-hidden="true" />}
                </span>
                <span className="text-sm font-semibold text-slate-900 truncate">{displayName(d, ctl.drafts)}</span>
                <span className="ml-auto text-[11px] text-slate-500 whitespace-nowrap">
                  {d.type === 'ADULT' ? 'Người lớn' : `Trẻ em${birth && ctl.earliest ? `, ${ageOn(birth, ctl.earliest)} tuổi` : ''}`}
                </span>
              </li>
            );
          })}
        </ul>
        <div className="text-xs text-slate-600">
          <b className="text-slate-800">Liên hệ:</b> {normalizeName(ctl.contactFullName)} · <span className="tabular-nums">{ctl.phone}</span> · {ctl.email}
        </div>
      </section>

      <section className={cardClass} aria-label="Dịch vụ">
        <SectionTitle
          title={`Dịch vụ (${ctl.items.length})`}
          extra={<button type="button" onClick={() => ctl.goto('services')} aria-label="Sửa dịch vụ" className="text-xs font-semibold text-blue-600 hover:underline inline-flex items-center gap-1"><PenLine className="w-3 h-3" aria-hidden="true" />Sửa</button>}
        />
        <div className="divide-y divide-slate-100 -mt-1">
          {ctl.items.map((item) => <ItemReview key={item.cartItemId} ctl={ctl} item={item} />)}
        </div>
        <div className="pt-3 border-t border-slate-200 flex justify-between items-baseline gap-3">
          <span className="text-sm font-bold text-slate-900">Tổng thanh toán</span>
          {ctl.anyPending ? <Skeleton width={110} /> : <span className="text-xl font-extrabold text-blue-900 tabular-nums" data-testid="review-total">{formatVnd(cart.total)}</span>}
        </div>
      </section>

      <section className={cardClass} aria-label="Phương thức thanh toán">
        <SectionTitle title="Phương thức thanh toán" />
        <div className="space-y-2" role="radiogroup" aria-label="Phương thức thanh toán">
          {PAYMENT_METHODS.map((option) => (
            <label key={option.id} className={`flex items-center justify-between gap-3 p-3 rounded-xl border text-sm ${option.enabled ? 'border-blue-300 bg-blue-50/40 cursor-pointer' : 'border-slate-200 text-slate-400 cursor-not-allowed'}`}>
              <span className="flex items-center gap-2.5">
                <input type="radio" name="payment-method" value={option.id} disabled={!option.enabled} checked={ctl.method === option.id} onChange={() => ctl.setMethod('stripe')} className="accent-blue-600" />
                <CreditCard className="w-4 h-4" aria-hidden="true" />
                {option.label}
              </span>
              {!option.enabled && <span className="px-1.5 py-0.5 rounded-md bg-slate-100 text-[10px] font-semibold">Sắp có</span>}
            </label>
          ))}
        </div>
        <p className="text-[11px] text-slate-500 flex items-start gap-1.5">
          <Lock className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
          Bạn nhập thẻ trên trang do Stripe host; V-OTA không nhận và không lưu số thẻ. Chế độ test: dùng thẻ 4242 4242 4242 4242.
        </p>
      </section>

      <section className={cardClass} aria-label="Xác nhận">
        <label htmlFor="terms" className="flex items-start gap-3 text-sm text-slate-700 cursor-pointer p-3 bg-slate-50 rounded-xl border border-slate-200">
          <input id="terms" type="checkbox" checked={ctl.termsAgreed} onChange={(e) => ctl.setTermsAgreed(e.target.checked)} className="mt-0.5 w-4 h-4 accent-blue-600 shrink-0" />
          <span>
            Tôi đã kiểm tra họ tên hành khách và đồng ý <b>Điều khoản dịch vụ</b>, <b>Chính sách huỷ</b>:{' '}
            {deadlinePassed ? (
              <>đã quá hạn hoàn tiền (00:00 ngày {deadline}), đơn này <b>không được hoàn tiền</b> nếu huỷ.</>
            ) : (
              <>hoàn 100% nếu huỷ trước <b>{deadline ? `00:00 ngày ${deadline}` : '00:00 ngày liền trước ngày sử dụng sớm nhất'}</b>.</>
            )}
          </span>
        </label>
        {ctl.banner && (
          <BannerView banner={ctl.banner} onAcceptPrice={() => void ctl.acceptNewPrice()} onRetry={() => void ctl.pay()} onBack={() => ctl.navigate('/cart')} />
        )}
        <div className="hidden lg:block">
          <PrimaryButton full onClick={() => void ctl.pay()} disabled={!canPay} busy={ctl.submitting ? 'Đang giữ chỗ và mở trang thanh toán…' : null}>
            Thanh toán {formatVnd(cart.total)}
          </PrimaryButton>
        </div>
        <p className="text-[11px] text-slate-500 text-center flex items-center justify-center gap-1">
          <Timer className="w-3.5 h-3.5" aria-hidden="true" />
          Giữ chỗ 30 phút sau khi bấm Thanh toán. Bạn sẽ được chuyển sang Stripe.
        </p>
      </section>

      <div className="flex">
        <button type="button" onClick={() => ctl.goto('services')} className="px-4 py-3 text-sm font-semibold text-slate-700 hover:text-slate-900 inline-flex items-center gap-1.5">
          <ArrowLeft className="w-4 h-4" aria-hidden="true" />Quay lại
        </button>
      </div>

      {ctl.pendingHold && (
        <div role="dialog" aria-modal="true" aria-labelledby="pending-hold-title" className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6 space-y-4">
            <h3 id="pending-hold-title" className="text-base font-bold text-slate-900">Bạn đang có một đơn chờ thanh toán</h3>
            <p className="text-xs text-slate-600">
              Đơn <strong className="font-mono">{ctl.pendingHold.referenceCode}</strong>
              {ctl.pendingHold.holdExpiresAt ? <> đang được giữ đến {formatDateTimeVn(ctl.pendingHold.holdExpiresAt)}</> : null}.
              Mỗi tài khoản chỉ giữ một đơn cùng lúc.
            </p>
            <div className="flex flex-col gap-2">
              <button type="button" onClick={() => void ctl.continuePending()} className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl">Tiếp tục thanh toán đơn đó</button>
              <button type="button" onClick={() => void ctl.cancelPendingAndRetry()} className="w-full py-2.5 bg-white border border-rose-300 text-rose-700 hover:bg-rose-50 text-xs font-bold rounded-xl">Huỷ đơn đó và đặt lại từ giỏ</button>
              <button type="button" onClick={() => ctl.setPendingHold(null)} className="w-full py-2 text-xs text-slate-500 hover:underline">Đóng</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
