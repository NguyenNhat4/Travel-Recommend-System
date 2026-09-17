'use client';

import React, { useState, useMemo } from 'react';
import { useTravel } from '../../context/TravelContext';
import { calculateRecommendations } from '../../services/recsys';
import { ProductCard } from '../common/ProductCard';
import { CheckCircle2, Copy, Check, Sparkles, ArrowRight, Home, Calendar, MapPin, HelpCircle } from 'lucide-react';
import { WhyPopover } from '../common/WhyPopover';

interface ConfirmationViewProps {
  referenceCode: string;
}

export const ConfirmationView: React.FC<ConfirmationViewProps> = ({ referenceCode }) => {
  const { getBookingByCode, currentPersona, activeEvents, navigate, showToast } = useTravel();
  const [copied, setCopied] = useState(false);
  const [showWhy, setShowWhy] = useState(false);

  const booking = getBookingByCode(referenceCode);

  // Recommendations immediately refreshed after booking (Moment K1!)
  const recResponse = useMemo(() => {
    return calculateRecommendations(currentPersona, activeEvents);
  }, [currentPersona, activeEvents]);

  const destination = booking?.destination || recResponse.destination || 'Nha Trang';

  const handleCopyCode = () => {
    navigator.clipboard.writeText(referenceCode);
    setCopied(true);
    showToast('Đã sao chép mã đặt chỗ!');
    setTimeout(() => setCopied(false), 3000);
  };

  const handleGoHome = () => {
    // Navigates to home where K1 feedback loop will highlight the updated section
    navigate('/');
  };

  const handleGoAssistant = () => {
    navigate('/assistant');
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-10">
      {/* Success Box */}
      <div className="p-8 bg-white rounded-3xl border border-slate-200 shadow-xl text-center space-y-6">
        <div className="w-16 h-16 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto shadow-xs">
          <CheckCircle2 className="w-10 h-10" />
        </div>

        <div className="space-y-1">
          <h1 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
            Đặt chỗ thành công!
          </h1>
          <p className="text-xs sm:text-sm text-slate-500">
            Hệ sinh thái gợi ý V-OTA đã ghi nhận giao dịch vào hồ sơ cá nhân hóa của bạn.
          </p>
        </div>

        {/* Reference Code Monospace */}
        <div className="inline-flex items-center gap-3 px-5 py-3 rounded-2xl bg-slate-50 border border-slate-200">
          <div className="text-left">
            <span className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider">
              Mã tham chiếu điện tử
            </span>
            <span className="font-mono text-lg font-black text-blue-900 tracking-wider">
              {referenceCode}
            </span>
          </div>

          <button
            onClick={handleCopyCode}
            className="p-2 rounded-xl bg-white border border-slate-200 hover:bg-slate-100 text-slate-600 transition-colors shadow-2xs"
            title="Sao chép mã"
          >
            {copied ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
          </button>
        </div>

        {/* Two Key Action Buttons (§4.6.2) */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
          <button
            onClick={handleGoHome}
            className="w-full sm:w-auto px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs sm:text-sm rounded-xl shadow-xs transition-colors flex items-center justify-center gap-2"
          >
            <Home className="w-4 h-4" />
            <span>Xem gợi ý mới trên trang chủ (K1)</span>
          </button>

          <button
            onClick={handleGoAssistant}
            className="w-full sm:w-auto px-6 py-3 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 font-bold text-xs sm:text-sm rounded-xl transition-colors flex items-center justify-center gap-2"
          >
            <Sparkles className="w-4 h-4 text-indigo-600" />
            <span>Lên lịch trình cho chuyến {destination}</span>
          </button>
        </div>
      </div>

      {/* Booking Summary breakdown */}
      {booking && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <h3 className="text-sm font-bold text-slate-900">
              CHI TIẾT ĐƠN ĐẶT CHỖ
            </h3>
            <span className="text-xs text-slate-500 font-mono">
              Tổng: {new Intl.NumberFormat('vi-VN').format(booking.totalAmount)} ₫
            </span>
          </div>

          <div className="divide-y divide-slate-100">
            {booking.items.map(item => (
              <div key={item.id} className="py-3 flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <img
                    src={item.product.imageUrl}
                    alt={item.product.name}
                    referrerPolicy="no-referrer"
                    className="w-12 h-12 rounded-lg object-cover bg-slate-100 shrink-0"
                  />
                  <div>
                    <h5 className="text-xs font-bold text-slate-900">{item.product.name}</h5>
                    <p className="text-[11px] text-slate-500">
                      {item.usingDate} · {item.quantity} {item.taxonomy === 'hotel' ? 'phòng' : 'khách'}
                    </p>
                  </div>
                </div>
                <span className="text-xs font-semibold text-slate-800 font-mono">
                  {new Intl.NumberFormat('vi-VN').format(item.totalPrice)} ₫
                </span>
              </div>
            ))}
          </div>

          <div className="pt-3 border-t border-slate-100 text-xs text-slate-500 flex justify-between">
            <span>Người liên hệ: <strong>{booking.contact.fullName}</strong> ({booking.contact.phoneNumber})</span>
            <span>Trạng thái: <span className="text-emerald-600 font-bold">Đã xác nhận thành công</span></span>
          </div>
        </div>
      )}

      {/* SECTION: Next for this trip (Feedback Loop Moment K1!) */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-black text-slate-900 tracking-tight flex items-center gap-2">
              TIẾP THEO CHO CHUYẾN {destination.toUpperCase()}
            </h2>
            <p className="text-xs text-slate-600">
              Vì bạn vừa đặt dịch vụ tại {destination} — đây là các đề xuất bổ trợ cho hành trình của bạn.
            </p>
          </div>
          <button
            onClick={() => setShowWhy(true)}
            className="text-xs font-semibold text-blue-700 hover:text-blue-800 flex items-center gap-1"
          >
            <HelpCircle className="w-3.5 h-3.5" />
            <span>Vì sao?</span>
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {recResponse.recommendations.slice(0, 3).map(rec => (
            <ProductCard
              key={rec.product.id}
              product={rec.product}
              variant="grid"
              because={rec.because}
              strategy={recResponse.strategy}
              excludedVerticals={recResponse.diagnostics.excludedVerticals}
            />
          ))}
        </div>

        <WhyPopover
          isOpen={showWhy}
          onClose={() => setShowWhy(false)}
          targetProductName={`Chuyến đi ${destination}`}
          becauseItems={recResponse.recommendations[0]?.because || []}
          strategy={recResponse.strategy}
          excludedVerticals={recResponse.diagnostics.excludedVerticals}
          destination={destination}
        />
      </div>
    </div>
  );
};
