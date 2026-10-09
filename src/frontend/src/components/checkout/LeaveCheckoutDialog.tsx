'use client';

/**
 * Hộp "Rời trang thanh toán?" (FR-BKG-01, AC-BKG-20): nêu thứ sẽ mất và thứ còn lại trong giỏ, mặc định là ở lại.
 * Dưới `sm` hộp trượt lên từ đáy màn hình; từ `sm` trở lên nằm giữa màn hình như các hộp xác nhận khác của trang thanh toán.
 */
import React, { useEffect, useRef } from 'react';
import { AlertTriangle, Check, Clock, X } from 'lucide-react';
import { useTravel } from '../../context/TravelContext';
import { isCartEligible } from '../../services/booking';
import type { ApiCartItem } from '../../services/booking';
import { formatDmy } from './checkoutRules';

export interface LeaveLines {
  /** Thứ khách mất khi rời trang. */
  lose: string[];
  /** Thứ vẫn còn sau khi rời trang. */
  keep: string[];
}

/**
 * Nội dung hộp theo nguồn. Đơn nháp của Đặt ngay: khách sạn, vé máy bay không được giữ; tour và tiện ích đã được chép vào giỏ lúc
 * bấm Đặt ngay nên còn nguyên. Giỏ: các dịch vụ vẫn ở trong giỏ. Cả hai nguồn đều mất thông tin hành khách đã nhập, vì họ tên và
 * ngày sinh chỉ nằm trong bộ nhớ của trang. `basket` là giỏ hiện tại; chưa tải được (`null`) thì coi mục vào giỏ được là còn trong giỏ.
 */
export function leaveLines(items: ApiCartItem[], sourceKind: 'cart' | 'draft', basket: ApiCartItem[] | null): LeaveLines {
  const hasFlight = items.some((item) => item.product.taxonomy === 'flight');
  const input = hasFlight
    ? 'Họ tên, ngày sinh và giấy tờ hành khách đã nhập sẽ bị xoá.'
    : 'Họ tên và ngày sinh hành khách đã nhập sẽ bị xoá.';
  if (sourceKind === 'cart') {
    return { lose: [input], keep: [`${items.length} dịch vụ trong giỏ hàng vẫn được giữ nguyên.`] };
  }
  const lose: string[] = [];
  const keep: string[] = [];
  for (const item of items) {
    const { name, taxonomy, productId } = item.product;
    if (taxonomy === 'hotel') lose.push(`${name} không được giữ lại. Bạn phải chọn lại phòng và giá có thể đã đổi.`);
    else if (taxonomy === 'flight') lose.push(`Chuyến bay ${name} ngày ${formatDmy(item.usingDate)} không được giữ lại. Bạn phải tìm lại chuyến và giá có thể đã đổi.`);
    else if (isCartEligible(taxonomy) && (!basket || basket.some((c) => c.product.productId === productId && c.usingDate === item.usingDate))) {
      keep.push(`${name} ngày ${formatDmy(item.usingDate)} vẫn nằm trong giỏ hàng, bạn thanh toán sau được.`);
    }
  }
  return { lose: [...lose, input], keep };
}

export const LeaveCheckoutDialog: React.FC<{
  items: ApiCartItem[];
  sourceKind: 'cart' | 'draft';
  /** Thời gian còn lại của đơn nháp (`mm:ss`); null với giỏ. */
  timeLeft: string | null;
  onStay: () => void;
  onLeave: () => void;
}> = ({ items, sourceKind, timeLeft, onStay, onLeave }) => {
  const { cart } = useTravel();
  const { lose, keep } = leaveLines(items, sourceKind, cart?.items ?? null);
  const stayRef = useRef<HTMLButtonElement>(null);
  const leaveRef = useRef<HTMLButtonElement>(null);

  // Mở hộp: đưa con trỏ vào nút an toàn (ở lại). Đóng hộp: trả con trỏ về chỗ khách đang đứng.
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    stayRef.current?.focus();
    return () => previous?.focus?.();
  }, []);

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Escape') {
      event.stopPropagation();
      onStay();
    } else if (event.key === 'Tab') {
      // Hộp chỉ có hai nút: Tab và Shift+Tab đổi qua lại giữa hai nút, không lọt ra trang bên dưới.
      event.preventDefault();
      (document.activeElement === stayRef.current ? leaveRef : stayRef).current?.focus();
    }
  };

  return (
    <div
      className="leave-scrim-in fixed inset-0 z-50 bg-slate-900/40 flex items-end sm:items-center justify-center sm:p-4"
      onClick={(event) => { if (event.target === event.currentTarget) onStay(); }}
      onKeyDown={onKeyDown}
      data-testid="leave-checkout"
    >
      <div
        role="alertdialog" aria-modal="true" aria-labelledby="leave-checkout-title" aria-describedby="leave-checkout-body"
        className="leave-dialog-in bg-white w-full sm:max-w-md max-h-[calc(100dvh-2rem)] overflow-y-auto rounded-t-2xl sm:rounded-2xl shadow-xl px-5 pt-3 pb-[calc(1.25rem+env(safe-area-inset-bottom,0px))] sm:p-6 space-y-4"
      >
        <span className="sm:hidden block w-9 h-1 rounded-full bg-slate-300 mx-auto" aria-hidden="true" />
        <div className="flex items-start gap-3">
          <span className="shrink-0 w-10 h-10 rounded-full bg-amber-50 border border-amber-200 text-amber-600 flex items-center justify-center">
            <AlertTriangle className="w-5 h-5" aria-hidden="true" />
          </span>
          <div className="min-w-0 space-y-1">
            <h3 id="leave-checkout-title" className="text-base font-bold text-slate-900">Rời trang thanh toán?</h3>
            <p className="text-sm text-slate-600">Bạn chưa thanh toán. Nếu rời trang lúc này:</p>
          </div>
        </div>
        <ul id="leave-checkout-body" className="rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-3 space-y-2.5 text-[13px] leading-snug text-slate-900">
          {lose.map((text) => (
            <li key={text} className="flex items-start gap-2.5" data-testid="leave-lose">
              <X className="w-4 h-4 shrink-0 mt-0.5 text-rose-600" aria-hidden="true" /><span>{text}</span>
            </li>
          ))}
          {keep.map((text) => (
            <li key={text} className="flex items-start gap-2.5" data-testid="leave-keep">
              <Check className="w-4 h-4 shrink-0 mt-0.5 text-emerald-600" aria-hidden="true" /><span>{text}</span>
            </li>
          ))}
        </ul>
        {timeLeft && (
          <div className="inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs text-amber-800">
            <Clock className="w-3.5 h-3.5" aria-hidden="true" />Phiên thanh toán còn <span className="font-bold tabular-nums">{timeLeft}</span>
          </div>
        )}
        <div className="flex flex-col sm:flex-row-reverse gap-2">
          <button ref={stayRef} type="button" onClick={onStay} className="w-full sm:w-auto min-h-[46px] sm:min-h-[42px] px-5 bg-brand-600 hover:bg-brand-700 text-white text-sm font-bold rounded-xl transition-colors outline-hidden focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2">
            Ở lại thanh toán
          </button>
          <button ref={leaveRef} type="button" onClick={onLeave} className="w-full sm:w-auto min-h-[46px] sm:min-h-[42px] px-5 bg-white border border-rose-300 text-rose-700 hover:bg-rose-50 text-sm font-bold rounded-xl transition-colors outline-hidden focus-visible:ring-2 focus-visible:ring-rose-400 focus-visible:ring-offset-2">
            Rời trang
          </button>
        </div>
      </div>
    </div>
  );
};
