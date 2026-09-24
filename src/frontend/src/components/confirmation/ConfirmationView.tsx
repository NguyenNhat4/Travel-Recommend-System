'use client';

import React, { useEffect, useState } from 'react';
import { useTravel } from '../../context/TravelContext';
import { fetchRecommendations } from '../../services/recsys';
import { ProductCard } from '../common/ProductCard';
import { CheckCircle2, Copy, Check, Sparkles, Home, HelpCircle, Loader2 } from 'lucide-react';
import { WhyPopover } from '../common/WhyPopover';
import type { BookingRecord, RecommendationResponse, Taxonomy } from '../../types/travel';

interface ConfirmationViewProps {
  referenceCode: string;
}

const TRIP_VERTICALS: Array<{ taxonomy: Taxonomy; label: string }> = [
  { taxonomy: 'hotel', label: 'Khách sạn' },
  { taxonomy: 'flight', label: 'Vé máy bay' },
  { taxonomy: 'attraction', label: 'Vé tham quan' },
];

const formatVnd = (value: number) => new Intl.NumberFormat('vi-VN').format(value);

export const ConfirmationView: React.FC<ConfirmationViewProps> = ({ referenceCode }) => {
  const { getBookingByCode, loadBooking, navigate, showToast, debugMode } = useTravel();
  const [copied, setCopied] = useState(false);
  const [showWhy, setShowWhy] = useState(false);

  // Đơn: dùng response POST /bookings nếu còn trong state; tải lại trang thì GET /bookings/{ref} (frontend §4.6).
  const cached = getBookingByCode(referenceCode);
  const [booking, setBooking] = useState<BookingRecord | null>(cached ?? null);
  const [bookingMissing, setBookingMissing] = useState(false);
  useEffect(() => {
    if (cached) {
      setBooking(cached);
      return;
    }
    let cancelled = false;
    loadBooking(referenceCode).then((record) => {
      if (cancelled) return;
      setBooking(record);
      setBookingMissing(record === null);
    });
    return () => { cancelled = true; };
  }, [cached, loadBooking, referenceCode]);

  // "Tiếp theo cho chuyến": gọi engine thật SAU khi đơn đã hiển thị. Checkout đã ghi purchase sang CDP
  // trước khi trả 201, nên gợi ý ở đây đã chuyển sang phần còn thiếu của chuyến (K1, AC-REC-02).
  const destination = booking?.destination;
  const [recResponse, setRecResponse] = useState<RecommendationResponse | null>(null);
  const [recLoading, setRecLoading] = useState(false);
  useEffect(() => {
    if (!destination) return;
    const controller = new AbortController();
    setRecLoading(true);
    fetchRecommendations({ k: 4, destination, signal: controller.signal })
      .then(setRecResponse)
      .catch(() => { if (!controller.signal.aborted) setRecResponse(null); }) // lỗi → ẩn khối, giữ CTA
      .finally(() => { if (!controller.signal.aborted) setRecLoading(false); });
    return () => controller.abort();
  }, [destination]);

  const handleCopyCode = () => {
    navigator.clipboard.writeText(referenceCode);
    setCopied(true);
    showToast('Đã sao chép mã đặt chỗ!');
    setTimeout(() => setCopied(false), 3000);
  };

  if (bookingMissing) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-16 text-center space-y-4">
        <h2 className="text-xl font-bold text-slate-800">Không tìm thấy đơn đặt chỗ này</h2>
        <button
          onClick={() => navigate('/')}
          className="px-5 py-2 bg-blue-600 text-white text-xs font-bold rounded-lg hover:bg-blue-700 transition-colors"
        >
          Về trang chủ
        </button>
      </div>
    );
  }

  const recommendations = recResponse?.recommendations ?? [];
  const excluded = recResponse?.diagnostics.excludedVerticals ?? [];
  const firstBecause = recommendations[0]?.because?.[0];

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
            Lượt đặt đã được ghi vào hồ sơ của bạn — gợi ý bên dưới được tính lại từ chính lượt đặt này.
          </p>
        </div>

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

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
          <button
            onClick={() => navigate('/')}
            className="w-full sm:w-auto px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs sm:text-sm rounded-xl shadow-xs transition-colors flex items-center justify-center gap-2"
          >
            <Home className="w-4 h-4" />
            <span>Xem gợi ý mới trên trang chủ</span>
          </button>
          {destination && (
            <button
              onClick={() => navigate(`/assistant?destination=${encodeURIComponent(destination)}`)}
              className="w-full sm:w-auto px-6 py-3 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 font-bold text-xs sm:text-sm rounded-xl transition-colors flex items-center justify-center gap-2"
            >
              <Sparkles className="w-4 h-4 text-indigo-600" />
              <span>Lên lịch trình cho chuyến {destination}</span>
            </button>
          )}
        </div>
      </div>

      {/* Booking Summary breakdown */}
      {booking && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <h3 className="text-sm font-bold text-slate-900">CHI TIẾT ĐƠN ĐẶT CHỖ</h3>
            <span className="text-xs text-slate-500 font-mono">Tổng: {formatVnd(booking.totalAmount)} ₫</span>
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
                      {item.taxonomy === 'hotel' && item.checkOutDate
                        ? `${item.usingDate} → ${item.checkOutDate} · ${item.nights} đêm · ${item.quantity} phòng`
                        : `${item.usingDate} · ${item.quantity} khách`}
                    </p>
                  </div>
                </div>
                <span className="text-xs font-semibold text-slate-800 font-mono">{formatVnd(item.totalPrice)} ₫</span>
              </div>
            ))}
          </div>

          <div className="pt-3 border-t border-slate-100 text-xs text-slate-500 flex justify-between">
            <span>Người liên hệ: <strong>{booking.contact.fullName}</strong> ({booking.contact.phoneNumber})</span>
            <span>Trạng thái: <span className="text-emerald-600 font-bold">Đã xác nhận</span></span>
          </div>
        </div>
      )}

      {/* Tiếp theo cho chuyến — gợi ý thật từ engine (K1). Lỗi hoặc rỗng thì ẩn (frontend §4.6). */}
      {recLoading && (
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span>Đang tính gợi ý cho chuyến {destination}…</span>
        </div>
      )}
      {!recLoading && recommendations.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-1.5">
              <h2 className="text-lg font-black text-slate-900 tracking-tight">
                TIẾP THEO CHO CHUYẾN {(recResponse?.destination || destination || '').toUpperCase()}
              </h2>
              {firstBecause && (
                <p className="text-xs text-slate-600">
                  Vì bạn vừa đặt <strong>{firstBecause.productName}</strong> — đây là phần còn thiếu của chuyến đi.
                </p>
              )}
              {recResponse?.strategy === 'cross_vertical' && (
                <div className="flex flex-wrap gap-2 text-[11px] font-semibold">
                  {TRIP_VERTICALS.map(({ taxonomy, label }) => {
                    const done = excluded.includes(taxonomy);
                    return (
                      <span
                        key={taxonomy}
                        className={`px-2 py-0.5 rounded-full border ${done ? 'bg-emerald-50 border-emerald-200 text-emerald-700' : 'bg-slate-50 border-slate-200 text-slate-600'}`}
                      >
                        {done ? '✓' : '○'} {label}
                      </span>
                    );
                  })}
                </div>
              )}
            </div>
            <button
              onClick={() => setShowWhy(true)}
              className="text-xs font-semibold text-blue-700 hover:text-blue-800 flex items-center gap-1 shrink-0"
            >
              <HelpCircle className="w-3.5 h-3.5" />
              <span>Vì sao?</span>
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {recommendations.map(rec => (
              <ProductCard
                key={rec.product.id}
                product={rec.product}
                variant="grid"
                because={rec.because}
                strategy={recResponse?.strategy}
                excludedVerticals={excluded}
              />
            ))}
          </div>

          {debugMode && recResponse && (
            <p className="text-[11px] font-mono text-slate-400">
              strategy={recResponse.strategy} · nextVertical={recResponse.nextVertical ?? '—'} ·
              eventsUsed={recResponse.diagnostics.eventsUsed} · model={recResponse.diagnostics.modelVersion}
              {recResponse.diagnostics.latencyMs != null && ` · ${recResponse.diagnostics.latencyMs} ms`}
            </p>
          )}

          <WhyPopover
            isOpen={showWhy}
            onClose={() => setShowWhy(false)}
            targetProductName={`Chuyến đi ${recResponse?.destination || destination}`}
            becauseItems={recommendations[0]?.because || []}
            strategy={recResponse?.strategy || 'popular'}
            excludedVerticals={excluded}
            destination={recResponse?.destination || destination}
          />
        </div>
      )}
    </div>
  );
};
