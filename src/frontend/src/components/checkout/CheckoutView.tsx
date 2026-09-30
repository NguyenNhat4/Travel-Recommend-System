'use client';

/**
 * `/checkout`: ba bước Hành khách → Dịch vụ → Xem lại và thanh toán (docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md, FR-BKG-08).
 *
 * Trạng thái nằm ở hook `useCheckout` gọi ngay tại đây, nên không mất khi phiên hết hạn giữa chừng và hộp đăng nhập lại hiện lên
 * (§6.2). Bước hiện tại nằm ở `?step=`; mỗi lần chuyển bước là một mục trong lịch sử trình duyệt. Chỉ sửa giỏ ở hai bước đầu,
 * không giữ chỗ, không tạo đơn, không gọi Stripe cho tới khi khách bấm Thanh toán (FR-BKG-06).
 */
import React from 'react';
import { Loader2 } from 'lucide-react';
import { MobileBar, SummaryPanel } from './OrderSummary';
import { ReviewStep } from './ReviewStep';
import { ServicesStep } from './ServicesStep';
import { Stepper } from './CheckoutParts';
import { TravelersStep } from './TravelersStep';
import { useCheckout } from './useCheckout';

export const CheckoutView: React.FC = () => {
  const ctl = useCheckout();

  if (ctl.authReady && !ctl.currentPersona) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-16 text-center space-y-4">
        <h2 className="text-xl font-bold text-slate-900">Đăng nhập để thanh toán</h2>
        <button onClick={() => ctl.openLoginModal()} className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs rounded-xl">
          Đăng nhập
        </button>
      </div>
    );
  }

  if (!ctl.cart || ctl.items.length === 0 || ctl.drafts.length === 0) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-16 flex justify-center text-slate-400">
        <Loader2 className="w-6 h-6 animate-spin" aria-label="Đang tải giỏ hàng" />
      </div>
    );
  }

  return (
    <div id="checkout-top" className="pb-40 lg:pb-0">
      <div className="bg-white border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3"><Stepper ctl={ctl} /></div>
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
