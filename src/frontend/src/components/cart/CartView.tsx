'use client';

import React, { useMemo } from 'react';
import { useTravel } from '../../context/TravelContext';
import { calculateRecommendations } from '../../services/recsys';
import { TaxonomyBadge } from '../common/TaxonomyBadge';
import { PriceTag } from '../common/PriceTag';
import { ProductCard } from '../common/ProductCard';
import { Trash2, ShoppingBag, ArrowRight, ShieldCheck, Plus, Sparkles } from 'lucide-react';
import { Destination, CartItem } from '../../types/travel';

export const CartView: React.FC = () => {
  const { cart, removeFromCart, updateCartItem, navigate, currentPersona, activeEvents, addToCart } = useTravel();

  // Group items by destination
  const itemsByDestination = useMemo(() => {
    const groups: { [destination: string]: CartItem[] } = {};
    cart.forEach(item => {
      const dest = item.destination || 'Chung';
      if (!groups[dest]) groups[dest] = [];
      groups[dest].push(item);
    });
    return groups;
  }, [cart]);

  const totalAmount = useMemo(() => {
    return cart.reduce((sum, item) => sum + item.totalPrice, 0);
  }, [cart]);

  // Recommendations for cross-sell in cart
  const recResponse = useMemo(() => calculateRecommendations(currentPersona, activeEvents), [currentPersona, activeEvents]);
  const primaryDestination = cart[0]?.destination || 'Nha Trang';

  if (cart.length === 0) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-16 text-center space-y-6">
        <div className="w-16 h-16 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center mx-auto">
          <ShoppingBag className="w-8 h-8" />
        </div>
        <div className="space-y-1">
          <h2 className="text-xl font-bold text-slate-900">Giỏ hàng của bạn đang trống</h2>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            Chưa có dịch vụ nào được thêm vào giỏ. Hãy bắt đầu chọn khách sạn, chuyến bay hoặc vé vui chơi!
          </p>
        </div>
        <div className="flex justify-center gap-3">
          <button
            onClick={() => navigate('/')}
            className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs rounded-xl shadow-xs transition-colors"
          >
            Khám phá gợi ý trang chủ
          </button>
          <button
            onClick={() => navigate('/assistant')}
            className="px-5 py-2.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 font-bold text-xs rounded-xl transition-colors flex items-center gap-1.5"
          >
            <Sparkles className="w-3.5 h-3.5" />
            Lên kế hoạch cùng Trợ lý AI
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-10">
      <div className="flex items-baseline justify-between border-b border-slate-200 pb-4">
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">
          Giỏ hàng của bạn ({cart.length})
        </h1>
        <span className="text-xs text-slate-500">
          Các dịch vụ được gom nhóm theo từng điểm đến
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
        {/* Left: Cart Items by Destination */}
        <div className="lg:col-span-2 space-y-6">
          {Object.entries(itemsByDestination).map(([dest, items]: [string, CartItem[]]) => (
            <div key={dest} className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
              <div className="px-5 py-3.5 bg-slate-50 border-b border-slate-200/80 flex items-center justify-between">
                <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                  CHUYẾN {dest.toUpperCase()}
                </h3>
                <span className="text-xs text-slate-500 font-medium">
                  {items.length} dịch vụ
                </span>
              </div>

              <div className="divide-y divide-slate-100 p-2">
                {items.map(item => (
                  <div key={item.id} className="p-3 flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3.5 min-w-0">
                      <img
                        src={item.product.imageUrl}
                        alt={item.product.name}
                        referrerPolicy="no-referrer"
                        className="w-16 h-16 rounded-lg object-cover bg-slate-100 shrink-0"
                      />
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5 mb-1">
                          <TaxonomyBadge taxonomy={item.taxonomy} size="sm" />
                          <span className="text-[11px] text-slate-400 font-medium">
                            {item.destination}
                          </span>
                        </div>
                        <h4 className="text-xs sm:text-sm font-bold text-slate-900 truncate">
                          {item.product.name}
                        </h4>
                        <div className="text-[11px] text-slate-500 mt-0.5">
                          {item.taxonomy === 'hotel' 
                            ? `${item.usingDate} → ${item.checkOutDate} · ${item.nights} đêm · ${item.quantity} phòng`
                            : `Ngày dùng: ${item.usingDate} · Số lượng: ${item.quantity} khách`}
                        </div>
                      </div>
                    </div>

                    <div className="flex flex-col items-end gap-1.5 shrink-0">
                      <span className="text-sm font-bold text-blue-900 font-mono">
                        {new Intl.NumberFormat('vi-VN').format(item.totalPrice)} ₫
                      </span>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => removeFromCart(item.id)}
                          className="text-xs text-slate-400 hover:text-rose-600 flex items-center gap-1 transition-colors"
                          title="Xóa mục này"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                          <span>Xóa</span>
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}

          {/* Frequently Booked Together Section (§4.4.2) */}
          <div className="pt-4 space-y-3">
            <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
              Thường được đặt cùng chuyến {primaryDestination}
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {recResponse.recommendations.slice(0, 2).map(rec => (
                <ProductCard
                  key={rec.product.id}
                  product={rec.product}
                  variant="compact"
                  because={rec.because}
                  onQuickAdd={(p) => addToCart(p, 1)}
                />
              ))}
            </div>
          </div>
        </div>

        {/* Right: Sticky Summary Box */}
        <div className="sticky top-20 bg-white p-6 rounded-2xl border border-slate-200 shadow-xl space-y-5">
          <h3 className="text-sm font-bold text-slate-900 border-b border-slate-100 pb-3">
            Tóm tắt đơn đặt chỗ
          </h3>

          <div className="space-y-2.5 text-xs">
            <div className="flex justify-between text-slate-600">
              <span>Tổng số dịch vụ:</span>
              <span className="font-semibold text-slate-800">{cart.length}</span>
            </div>
            <div className="flex justify-between text-slate-600">
              <span>Tạm tính:</span>
              <span className="font-mono text-slate-800">
                {new Intl.NumberFormat('vi-VN').format(totalAmount)} ₫
              </span>
            </div>
            <div className="flex justify-between text-slate-600">
              <span>Thuế và phí:</span>
              <span className="text-emerald-600 font-semibold">Đã bao gồm</span>
            </div>
            <div className="pt-3 border-t border-slate-200 flex justify-between items-baseline">
              <span className="text-sm font-bold text-slate-900">Tổng thanh toán:</span>
              <span className="text-lg font-black text-blue-900 font-mono">
                {new Intl.NumberFormat('vi-VN').format(totalAmount)} ₫
              </span>
            </div>
          </div>

          <button
            onClick={() => navigate('/checkout')}
            className="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white font-bold text-sm rounded-xl shadow-xs transition-colors flex items-center justify-center gap-2"
          >
            <span>Tiến hành đặt chỗ</span>
            <ArrowRight className="w-4 h-4" />
          </button>

          <div className="text-center text-[11px] text-slate-500 space-y-1">
            <div className="flex items-center justify-center gap-1 text-slate-600 font-medium">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
              <span>Thanh toán an toàn & bảo mật thông tin 100%</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
