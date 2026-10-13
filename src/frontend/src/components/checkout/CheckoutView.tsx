'use client';

/**
 * `/checkout`: ba bước Hành khách → Dịch vụ → Xem lại và thanh toán (docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md, FR-BKG-08).
 *
 * Trạng thái nằm ở hook `useCheckout` gọi ngay tại đây, nên không mất khi phiên hết hạn giữa chừng và hộp đăng nhập lại hiện lên
 * (§6.2). Bước hiện tại nằm ở `?step=`; mỗi lần chuyển bước là một mục trong lịch sử trình duyệt. Chỉ sửa giỏ ở hai bước đầu,
 * không giữ chỗ, không tạo đơn, không gọi Stripe cho tới khi khách bấm Thanh toán (FR-BKG-06).
 *
 * Hai nguồn (docs/spec/booking/dat-truc-tiep-theo-don-nhap.md §13): `/checkout` thanh toán giỏ, `/checkout?draft=<mã>` thanh toán
 * đúng một đơn nháp của Đặt ngay (có đồng hồ 30 phút; hết hạn thì khách sạn, vé máy bay phải đặt lại, tour và tiện ích còn
 * trong giỏ). Khách chưa đăng nhập đi hết ba bước được; đăng nhập khi bấm Thanh toán. Khách chủ động rời trang khi chưa thanh
 * toán thì được hỏi lại (`useLeaveGuard`, `LeaveCheckoutDialog`).
 */
import React, { useEffect, useState } from 'react';
import { Clock } from 'lucide-react';
import { SkeletonBlock, SkeletonStatus } from '../common/Skeleton';
import { LeaveCheckoutDialog } from './LeaveCheckoutDialog';
import { MobileBar, SummaryPanel } from './OrderSummary';
import { ReviewStep } from './ReviewStep';
import { ServicesStep } from './ServicesStep';
import { Stepper } from './CheckoutParts';
import { TravelersStep } from './TravelersStep';
import { useCheckout } from './useCheckout';

const PRIMARY = 'px-5 py-2.5 bg-brand-600 hover:bg-brand-700 text-white font-bold text-xs rounded-xl';
const SECONDARY = 'px-5 py-2.5 bg-white border border-slate-300 hover:bg-slate-50 text-slate-800 font-bold text-xs rounded-xl';

/** Thời gian còn lại của đơn nháp, `mm:ss`; null khi không có hạn. Về 0 thì gọi `onExpire` một lần. */
function useCountdown(expiresAt: string | null, onExpire: () => void): string | null {
  const [now, setNow] = useState(() => Date.now());
  const deadline = expiresAt ? Date.parse(expiresAt) : null;
  const expired = deadline !== null && now >= deadline;
  useEffect(() => {
    if (deadline === null) return undefined;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [deadline]);
  useEffect(() => {
    if (expired) onExpire();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- chỉ báo một lần khi vừa hết hạn
  }, [expired]);
  if (deadline === null) return null;
  const left = Math.max(0, Math.floor((deadline - now) / 1000));
  return `${String(Math.floor(left / 60)).padStart(2, '0')}:${String(left % 60).padStart(2, '0')}`;
}

/** Đơn nháp quá 30 phút (R-DRF-21, R-DRF-22): khách sạn, vé máy bay đặt lại từ đầu; tour và tiện ích còn trong giỏ. */
const ExpiredDraft: React.FC<{ ctl: ReturnType<typeof useCheckout> }> = ({ ctl }) => {
  const inCart = ctl.expiredItems.some((item) => item.inCart);
  const hotel = ctl.expiredItems.find((item) => item.taxonomy === 'hotel');
  const hasFlight = ctl.expiredItems.some((item) => item.taxonomy === 'flight');
  const dropped = Boolean(hotel) || hasFlight;
  return (
    <div className="max-w-xl mx-auto px-4 py-16 text-center space-y-4" role="alert" data-testid="draft-expired">
      <h2 className="font-display text-2xl text-slate-900">Phiên thanh toán đã hết hạn</h2>
      {dropped && (
        <p className="text-sm text-slate-600">
          Đã quá 30 phút. Giá và chỗ trống của khách sạn, vé máy bay có thể đã đổi nên lựa chọn đó không được giữ lại. Vui lòng chọn lại để xem giá mới.
        </p>
      )}
      {inCart && (
        <p className="text-sm text-slate-600">Tour, trải nghiệm và tiện ích của lần đặt này vẫn nằm trong giỏ hàng của bạn.</p>
      )}
      <div className="flex flex-wrap justify-center gap-3 pt-2">
        {hotel && <button type="button" onClick={() => ctl.navigate(`/product/${hotel.productId}`)} className={PRIMARY}>Chọn lại phòng</button>}
        {hasFlight && <button type="button" onClick={() => ctl.navigate('/flights')} className={hotel ? SECONDARY : PRIMARY}>Tìm lại chuyến bay</button>}
        {inCart && <button type="button" onClick={() => ctl.navigate('/cart')} className={dropped ? SECONDARY : PRIMARY}>Về giỏ hàng</button>}
        {!dropped && !inCart && <button type="button" onClick={() => ctl.navigate('/')} className={PRIMARY}>Về trang chủ</button>}
      </div>
    </div>
  );
};

/**
 * Khung chờ của trang thanh toán: thanh ba bước, tiêu đề bước, hai thẻ hành khách và hộp tóm tắt đơn (từ `lg`). Dùng cả khi đơn
 * nháp chưa về và làm fallback Suspense của trang (`app/(storefront)/checkout/page.tsx`).
 */
export const CheckoutSkeleton: React.FC = () => (
  <SkeletonStatus label="Đang tải thông tin thanh toán" className="pb-40 lg:pb-0">
    <div className="bg-white border-b border-slate-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex items-center gap-2">
        {[0, 1, 2].map((i) => (
          <div key={i} className={`flex items-center gap-2 ${i < 2 ? 'flex-1' : ''}`}>
            <SkeletonBlock className="w-7 h-7 rounded-full shrink-0" />
            <SkeletonBlock className="h-4 w-24 rounded" />
          </div>
        ))}
      </div>
    </div>
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
        <div className="lg:col-span-2 space-y-5">
          <div className="space-y-2">
            <SkeletonBlock className="h-7 w-40 rounded-lg" />
            <SkeletonBlock className="h-4 w-80 max-w-full rounded" />
          </div>
          <div className="bg-white p-5 sm:p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4">
            <SkeletonBlock className="h-5 w-48 rounded" />
            {[0, 1].map((i) => (
              <div key={i} className="rounded-xl border border-slate-200 bg-slate-50/60 p-4 space-y-3">
                <div className="flex items-center gap-2">
                  <SkeletonBlock className="w-7 h-7 rounded-full" />
                  <SkeletonBlock className="h-4 w-32 rounded" />
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <SkeletonBlock className="h-11 w-full rounded-lg" />
                  <SkeletonBlock className="h-11 w-full rounded-lg" />
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="hidden lg:block bg-white p-5 sm:p-6 rounded-2xl border border-slate-200 shadow-xl space-y-4">
          <SkeletonBlock className="h-5 w-36 rounded" />
          {[0, 1, 2].map((i) => (
            <div key={i} className="flex justify-between gap-4">
              <SkeletonBlock className="h-4 w-32 rounded" />
              <SkeletonBlock className="h-4 w-20 rounded" />
            </div>
          ))}
          <div className="pt-3 border-t border-slate-200 flex justify-between gap-4">
            <SkeletonBlock className="h-5 w-24 rounded" />
            <SkeletonBlock className="h-6 w-28 rounded" />
          </div>
          <SkeletonBlock className="h-11 w-full rounded-xl" />
        </div>
      </div>
    </div>
  </SkeletonStatus>
);

export const CheckoutView: React.FC = () => {
  const ctl = useCheckout();
  const timeLeft = useCountdown(ctl.sourceStatus === 'ready' ? ctl.draftExpiresAt : null, () => void ctl.refreshCart());

  if (ctl.sourceStatus === 'expired') return <ExpiredDraft ctl={ctl} />;
  if (ctl.sourceStatus === 'not-found') {
    return (
      <div className="max-w-xl mx-auto px-4 py-16 text-center space-y-4" role="alert" data-testid="draft-not-found">
        <h2 className="font-display text-2xl text-slate-900">Không tìm thấy phiên thanh toán này</h2>
        <p className="text-sm text-slate-600">Phiên có thể đã được thanh toán, đã hết hạn từ lâu, hoặc thuộc tài khoản khác.</p>
        <button type="button" onClick={() => ctl.navigate('/')} className={PRIMARY}>Về trang chủ</button>
      </div>
    );
  }

  if (!ctl.cart || ctl.items.length === 0 || ctl.drafts.length === 0) return <CheckoutSkeleton />;

  return (
    <div id="checkout-top" className="pb-40 lg:pb-0">
      <div className="bg-white border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex flex-wrap items-center justify-between gap-3">
          <Stepper ctl={ctl} />
          {timeLeft && (
            <div className="inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs text-amber-800" data-testid="draft-countdown">
              <Clock className="w-3.5 h-3.5" aria-hidden="true" />Phiên thanh toán còn <span className="font-bold tabular-nums">{timeLeft}</span>
            </div>
          )}
        </div>
      </div>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
          <form className="lg:col-span-2 space-y-5" onSubmit={(e) => e.preventDefault()} aria-label="Thanh toán">
            {ctl.step === 'travelers' && <TravelersStep ctl={ctl} />}
            {ctl.step === 'services' && <ServicesStep ctl={ctl} />}
            {ctl.step === 'review' && <ReviewStep ctl={ctl} />}
          </form>
          <SummaryPanel ctl={ctl} />
        </div>
      </div>
      <MobileBar ctl={ctl} />
      {ctl.leavePrompt && (
        <LeaveCheckoutDialog items={ctl.items} sourceKind={ctl.sourceKind} timeLeft={timeLeft} onStay={ctl.stayOnCheckout} onLeave={ctl.confirmLeave} />
      )}
    </div>
  );
};
