'use client';

import React, { useState, useEffect } from 'react';
import { useTravel } from '../../context/TravelContext';
import { TaxonomyBadge } from '../common/TaxonomyBadge';
import { Check, ShieldAlert, Loader2, Edit3, Info } from 'lucide-react';

export const CheckoutView: React.FC = () => {
  const { cart, currentPersona, createBooking, navigate } = useTravel();
  const isEmptyCart = cart.length === 0;

  useEffect(() => {
    if (isEmptyCart) navigate('/cart');
  }, [isEmptyCart, navigate]);

  // Contact info state
  const [fullName, setFullName] = useState(currentPersona?.name || 'Nguyễn Minh Anh');
  const [email] = useState(currentPersona?.email || 'minhanh.nguyen@v-ota.demo');
  const [phoneNumber, setPhoneNumber] = useState('0912345678');
  const [specialRequests, setSpecialRequests] = useState('');

  // Agreement and submitting states
  const [termsAgreed, setTermsAgreed] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [phoneError, setPhoneError] = useState('');

  const totalAmount = cart.reduce((sum, item) => sum + item.totalPrice, 0);

  if (isEmptyCart) {
    return null;
  }

  const handleSubmitBooking = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return; // Prevent double click

    if (!phoneNumber || phoneNumber.length < 9) {
      setPhoneError('Vui lòng nhập số điện thoại hợp lệ (từ 9-11 số)');
      return;
    }
    setPhoneError('');

    setIsSubmitting(true);
    try {
      const booking = await createBooking(
        {
          fullName,
          email,
          phoneNumber
        },
        {
          specialRequests
        }
      );

      // Navigate to confirmation page
      navigate(`/booking/${booking.referenceCode}`);
    } catch (err) {
      console.error('Booking failed:', err);
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
        {/* Form Column (2/3) */}
        <div className="lg:col-span-2 space-y-6">
          <form onSubmit={handleSubmitBooking} className="space-y-6">
            {/* Block 1: Contact Info */}
            <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <div className="flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-bold flex items-center justify-center">
                    1
                  </span>
                  <h3 className="text-sm font-bold text-slate-900">
                    THÔNG TIN LIÊN HỆ
                  </h3>
                </div>
                <span className="text-xs text-emerald-600 font-semibold flex items-center gap-1">
                  <Check className="w-3.5 h-3.5" />
                  Hợp lệ
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Họ và tên người đặt *
                  </label>
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    className="w-full px-3 py-2 text-xs sm:text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-hidden"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Số điện thoại *
                  </label>
                  <input
                    type="tel"
                    required
                    value={phoneNumber}
                    onChange={(e) => {
                      setPhoneNumber(e.target.value);
                      if (phoneError) setPhoneError('');
                    }}
                    placeholder="0912 345 678"
                    className="w-full px-3 py-2 text-xs sm:text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-hidden"
                  />
                  {phoneError && (
                    <p className="text-[11px] text-rose-600 mt-1">{phoneError}</p>
                  )}
                </div>

                <div className="sm:col-span-2">
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Email nhận thông tin (khóa theo tài khoản)
                  </label>
                  <input
                    type="email"
                    disabled
                    value={email}
                    className="w-full px-3 py-2 text-xs sm:text-sm bg-slate-100 border border-slate-300 rounded-lg text-slate-500 cursor-not-allowed"
                  />
                  <p className="text-[11px] text-slate-400 mt-1">
                    Thông tin liên hệ được hiển thị trên phiếu xác nhận điện tử.
                  </p>
                </div>
              </div>
            </div>

            {/* Block 2: Service-specific Details */}
            <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4">
              <div className="flex items-center gap-2 pb-3 border-b border-slate-100">
                <span className="w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-bold flex items-center justify-center">
                  2
                </span>
                <h3 className="text-sm font-bold text-slate-900">
                  THÔNG TIN TỪNG DỊCH VỤ
                </h3>
              </div>

              <div className="space-y-4">
                {cart.map((item, index) => (
                  <div key={item.id} className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 space-y-2 text-xs">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <TaxonomyBadge taxonomy={item.taxonomy} size="sm" />
                        <span className="font-bold text-slate-800">{item.product.name}</span>
                      </div>
                      <span className="text-slate-500">Mục #{index + 1}</span>
                    </div>

                    <div className="text-[11px] text-slate-600">
                      {item.taxonomy === 'hotel' ? (
                        <span>Khách nhận phòng chính: <strong>{fullName}</strong> (Được điền tự động)</span>
                      ) : item.taxonomy === 'flight' ? (
                        <span>Hành khách: <strong>{fullName}</strong> + {item.quantity - 1} khách khác</span>
                      ) : (
                        <span>Vé điện tử kích hoạt theo ngày: <strong>{item.usingDate}</strong></span>
                      )}
                    </div>
                  </div>
                ))}

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Yêu cầu đặc biệt (nếu có)
                  </label>
                  <textarea
                    rows={2}
                    value={specialRequests}
                    onChange={(e) => setSpecialRequests(e.target.value)}
                    placeholder="Ví dụ: Phòng tầng cao, phòng không hút thuốc, hỗ trợ suất ăn trên máy bay..."
                    className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg outline-hidden focus:ring-1 focus:ring-blue-500"
                  />
                </div>
              </div>
            </div>

            {/* Block 3: Review & Confirm */}
            <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-xs space-y-4">
              <div className="flex items-center gap-2 pb-3 border-b border-slate-100">
                <span className="w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-bold flex items-center justify-center">
                  3
                </span>
                <h3 className="text-sm font-bold text-slate-900">
                  XEM LẠI & XÁC NHẬN
                </h3>
              </div>

              <div className="space-y-4">
                <label className="flex items-start gap-3 text-xs text-slate-700 cursor-pointer p-3 bg-slate-50 rounded-xl border border-slate-200">
                  <input
                    type="checkbox"
                    checked={termsAgreed}
                    onChange={(e) => setTermsAgreed(e.target.checked)}
                    className="mt-0.5 rounded border-slate-300 text-blue-600 focus:ring-blue-500 w-4 h-4"
                  />
                  <span>
                    Tôi đồng ý với <strong>Điều khoản dịch vụ</strong> và <strong>Chính sách bảo mật</strong> khi đặt chỗ trên V-OTA.
                  </span>
                </label>

                <button
                  type="submit"
                  disabled={!termsAgreed || isSubmitting}
                  className="w-full py-3.5 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white font-bold text-sm sm:text-base rounded-xl shadow-md transition-all flex items-center justify-center gap-2"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      <span>Đang xác nhận đặt chỗ...</span>
                    </>
                  ) : (
                    <span>
                      Xác nhận đặt chỗ ({new Intl.NumberFormat('vi-VN').format(totalAmount)} ₫)
                    </span>
                  )}
                </button>
              </div>
            </div>
          </form>
        </div>

        {/* Right Sticky Order Summary */}
        <div className="sticky top-20 bg-white p-6 rounded-2xl border border-slate-200 shadow-xl space-y-5">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h3 className="text-sm font-bold text-slate-900">
              Đơn đặt của bạn ({cart.length})
            </h3>
            <button
              onClick={() => navigate('/cart')}
              className="text-xs text-blue-600 hover:underline flex items-center gap-1"
            >
              <Edit3 className="w-3 h-3" />
              Sửa giỏ hàng
            </button>
          </div>

          <div className="divide-y divide-slate-100 max-h-80 overflow-y-auto space-y-2 pr-1">
            {cart.map(item => (
              <div key={item.id} className="pt-2 flex items-center gap-3">
                <img
                  src={item.product.imageUrl}
                  alt={item.product.name}
                  referrerPolicy="no-referrer"
                  className="w-12 h-12 rounded-lg object-cover bg-slate-100 shrink-0"
                />
                <div className="min-w-0 flex-1">
                  <h5 className="text-xs font-bold text-slate-900 truncate">
                    {item.product.name}
                  </h5>
                  <div className="text-[10px] text-slate-500">
                    {item.usingDate} · {item.quantity} {item.taxonomy === 'hotel' ? 'phòng' : 'khách'}
                  </div>
                </div>
                <span className="text-xs font-bold text-slate-800 font-mono">
                  {new Intl.NumberFormat('vi-VN').format(item.totalPrice)} ₫
                </span>
              </div>
            ))}
          </div>

          <div className="pt-3 border-t border-slate-200 space-y-1.5 text-xs">
            <div className="flex justify-between text-slate-500">
              <span>Tạm tính:</span>
              <span>{new Intl.NumberFormat('vi-VN').format(totalAmount)} ₫</span>
            </div>
            <div className="flex justify-between text-slate-500">
              <span>Thuế & Phí:</span>
              <span className="text-emerald-600 font-medium">Đã bao gồm</span>
            </div>
            <div className="pt-2 border-t border-slate-100 flex justify-between items-baseline">
              <span className="text-sm font-bold text-slate-900">Tổng thanh toán:</span>
              <span className="text-base font-black text-blue-900 font-mono">
                {new Intl.NumberFormat('vi-VN').format(totalAmount)} ₫
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
