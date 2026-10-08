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
 * trong giỏ). Khách chưa đăng nhập đi hết ba bước được; đăng nhập khi bấm Thanh toán.
 */
import React, { useEffect, useState } from 'react';
import { Clock, Loader2 } from 'lucide-react';
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

  if (!ctl.cart || ctl.items.length === 0 || ctl.drafts.length === 0) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-16 flex justify-center text-slate-400">
        <Loader2 className="w-6 h-6 animate-spin" aria-label="Đang tải thông tin thanh toán" />
      </div>
    );
  }

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
    </div>
  );
};
