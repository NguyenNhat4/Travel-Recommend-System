'use client';

import React from 'react';
import { Compass } from 'lucide-react';

interface GuestRecommendationBannerProps {
  onLogin: () => void;
  onRegister: () => void;
}

/** Khách vãng lai không có khối gợi ý ①; thay bằng lời mời đăng nhập (product.md §4.1.3). */
export const GuestRecommendationBanner: React.FC<GuestRecommendationBannerProps> = ({ onLogin, onRegister }) => (
  <section aria-label="Đăng nhập để nhận gợi ý" className="mx-auto max-w-7xl px-4 pt-6 sm:px-6 lg:px-8">
    <div className="flex flex-col gap-4 rounded-3xl border border-brand-100 bg-brand-50/60 p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6">
      <div className="flex items-start gap-4">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-white text-brand-600 shadow-sm" aria-hidden="true">
          <Compass className="h-5 w-5" />
        </span>
        <div className="min-w-0">
          <h2 className="font-display text-base leading-6 text-slate-900">Đăng nhập để nhận gợi ý theo chuyến đi của bạn</h2>
          <p className="mt-0.5 text-sm leading-5 text-slate-600">
            Gợi ý bám theo những gì bạn đã xem và đặt, ví dụ vé máy bay hay tour cho chuyến sắp tới.
          </p>
        </div>
      </div>
      <div className="flex shrink-0 gap-2">
        <button
          type="button"
          onClick={onLogin}
          className="inline-flex h-11 flex-1 cursor-pointer items-center justify-center rounded-xl bg-brand-600 px-5 text-sm font-semibold text-white transition-colors hover:bg-brand-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600 sm:flex-none"
        >
          Đăng nhập
        </button>
        <button
          type="button"
          onClick={onRegister}
          className="inline-flex h-11 flex-1 cursor-pointer items-center justify-center rounded-xl border border-brand-200 bg-white px-5 text-sm font-semibold text-brand-700 transition-colors hover:bg-brand-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600 sm:flex-none"
        >
          Đăng ký
        </button>
      </div>
    </div>
  </section>
);
