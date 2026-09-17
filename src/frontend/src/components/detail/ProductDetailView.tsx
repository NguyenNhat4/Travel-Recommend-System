'use client';

import React, { useState, useMemo } from 'react';
import { useTravel } from '../../context/TravelContext';
import { getProductById } from '../../data/catalog';
import { getSimilarProducts, calculateRecommendations } from '../../services/recsys';
import { TaxonomyBadge } from '../common/TaxonomyBadge';
import { PriceTag } from '../common/PriceTag';
import { ProductCard } from '../common/ProductCard';
import { 
  MapPin, Star, ShieldCheck, Check, Calendar, Users, 
  Sparkles, ArrowRight, Clock, Info, Heart 
} from 'lucide-react';

interface ProductDetailViewProps {
  productId: string;
}

export const ProductDetailView: React.FC<ProductDetailViewProps> = ({ productId }) => {
  const { addToCart, navigate, currentPersona, activeEvents, openLoginModal } = useTravel();
  const product = useMemo(() => getProductById(productId), [productId]);

  // Form states for booking box
  const [checkInDate, setCheckInDate] = useState('2026-10-15');
  const [checkOutDate, setCheckOutDate] = useState('2026-10-18');
  const [quantity, setQuantity] = useState(1);
  const [selectedQuickDate, setSelectedQuickDate] = useState<'today' | 'tomorrow' | 'custom'>('custom');

  const similarProducts = useMemo(
    () => (product ? getSimilarProducts(product.id) : []),
    [product?.id],
  );
  const recResponse = useMemo(() => calculateRecommendations(currentPersona, activeEvents), [currentPersona, activeEvents]);

  // Calculate nights
  const nights = useMemo(() => {
    if (!product || product.taxonomy !== 'hotel') return 1;
    const d1 = new Date(checkInDate).getTime();
    const d2 = new Date(checkOutDate).getTime();
    return Math.max(1, Math.round((d2 - d1) / (24 * 3600 * 1000)));
  }, [product?.taxonomy, checkInDate, checkOutDate]);

  // Total price calculation
  const calculatedTotal = useMemo(() => {
    if (!product) return 0;
    if (product.taxonomy === 'hotel') {
      return product.unitPrice * nights * quantity;
    }
    return product.unitPrice * quantity;
  }, [product?.unitPrice, product?.taxonomy, nights, quantity]);

  if (!product) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-16 text-center space-y-4">
        <h2 className="text-xl font-bold text-slate-800">Sản phẩm này không còn trên V-OTA</h2>
        <p className="text-xs text-slate-500">Mã sản phẩm không tồn tại hoặc đã hết thời hạn mở bán.</p>
        <button
          onClick={() => navigate('/')}
          className="px-5 py-2 bg-blue-600 text-white text-xs font-bold rounded-lg hover:bg-blue-700 transition-colors"
        >
          Về trang chủ
        </button>
      </div>
    );
  }

  const handleAddToCartClick = () => {
    addToCart(product, quantity, checkInDate, checkOutDate);
  };

  const handleBookNowClick = () => {
    if (!currentPersona) {
      openLoginModal(() => {
        addToCart(product, quantity, checkInDate, checkOutDate);
        navigate('/checkout');
      });
      return;
    }
    addToCart(product, quantity, checkInDate, checkOutDate);
    navigate('/checkout');
  };

  const handleAskAssistant = () => {
    navigate('/assistant');
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-10">
      {/* Breadcrumbs & Header */}
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span className="hover:text-blue-600 cursor-pointer" onClick={() => navigate('/')}>Trang chủ</span>
          <span>›</span>
          <span className="hover:text-blue-600 cursor-pointer" onClick={() => navigate(`/search?q=${product.destination}`)}>{product.destination}</span>
          <span>›</span>
          <TaxonomyBadge taxonomy={product.taxonomy} size="sm" />
        </div>

        <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 flex-wrap mb-1.5">
              <TaxonomyBadge taxonomy={product.taxonomy} size="md" />
              {product.attributes.starRating && (
                <div className="flex items-center text-amber-500 text-xs font-bold">
                  {[...Array(product.attributes.starRating)].map((_, i) => (
                    <Star key={i} className="w-3.5 h-3.5 fill-amber-400 text-amber-400" />
                  ))}
                  <span className="ml-1 text-slate-700">5 sao</span>
                </div>
              )}
              <span className="flex items-center gap-1 text-xs text-slate-500">
                <MapPin className="w-3.5 h-3.5 text-slate-400" />
                {product.destination}
              </span>
            </div>

            <h1 className="text-xl sm:text-3xl font-black text-slate-900 tracking-tight">
              {product.name}
            </h1>

            {product.aggregateRating && (
              <p className="text-xs text-slate-500 mt-1">
                ⭐ <strong className="text-slate-800 font-semibold">{product.aggregateRating.score}/5</strong> ({product.aggregateRating.count} đánh giá tổng hợp từ du khách)
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Hero Gallery (16:7 aspect ratio) */}
      <div className="relative rounded-2xl overflow-hidden aspect-16/7 bg-slate-100 shadow-md border border-slate-200">
        <img
          src={product.imageUrl}
          alt={product.name}
          referrerPolicy="no-referrer"
          className="w-full h-full object-cover"
        />
        {!product.available && (
          <div className="absolute inset-0 bg-slate-900/70 flex items-center justify-center text-sm sm:text-base font-bold text-white uppercase tracking-wider">
            Sản phẩm hiện đã tạm hết chỗ
          </div>
        )}
      </div>

      {/* Main 2-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
        {/* Left Column (2/3): Description, Highlights, Amenities */}
        <div className="lg:col-span-2 space-y-8">
          {/* Highlights */}
          {product.highlights && product.highlights.length > 0 && (
            <div className="p-5 rounded-2xl bg-blue-50/70 border border-blue-100 space-y-3">
              <h3 className="text-sm font-bold text-blue-950 flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-blue-600" />
                Điểm nổi bật của dịch vụ
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                {product.highlights.map((h, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs text-slate-700">
                    <Check className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                    <span>{h}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Description */}
          <div className="space-y-3">
            <h3 className="text-base font-bold text-slate-900">Mô tả chi tiết</h3>
            <p className="text-sm text-slate-700 leading-relaxed">
              {product.description}
            </p>
          </div>

          {/* What's Included */}
          {product.included && product.included.length > 0 && (
            <div className="space-y-3 pt-4 border-t border-slate-200">
              <h3 className="text-base font-bold text-slate-900">Bao gồm trong dịch vụ</h3>
              <ul className="space-y-2">
                {product.included.map((item, idx) => (
                  <li key={idx} className="flex items-center gap-2 text-xs text-slate-700">
                    <ShieldCheck className="w-4 h-4 text-blue-600 shrink-0" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Assistant Teaser */}
          <div className="p-4 bg-indigo-50 border border-indigo-200 rounded-xl flex items-center justify-between gap-4">
            <div className="space-y-0.5">
              <div className="text-xs font-bold text-indigo-900 flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
                Lên lịch trình kết hợp xung quanh {product.destination}
              </div>
              <p className="text-[11px] text-indigo-700">
                Nhờ Trợ lý AI sắp xếp ngày giờ hợp lý từ chỗ ở này đến các điểm tham quan.
              </p>
            </div>
            <button
              onClick={handleAskAssistant}
              className="px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-lg shadow-xs transition-colors shrink-0"
            >
              Hỏi Trợ lý AI →
            </button>
          </div>
        </div>

        {/* Right Column (1/3 Sticky Booking Box) */}
        <div className="sticky top-20 bg-white p-6 rounded-2xl border border-slate-200 shadow-xl space-y-5">
          <div>
            <div className="text-xs text-slate-500 mb-1">Giá công khai từ V-OTA</div>
            <PriceTag 
              price={product.unitPrice} 
              taxonomy={product.taxonomy} 
              size="lg" 
              showTaxesIncluded 
            />
          </div>

          {/* Booking Inputs by Taxonomy */}
          <div className="space-y-3 pt-3 border-t border-slate-100">
            {product.taxonomy === 'hotel' ? (
              <>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-[11px] font-bold text-slate-600 mb-1">Nhận phòng</label>
                    <input
                      type="date"
                      value={checkInDate}
                      onChange={(e) => setCheckInDate(e.target.value)}
                      className="w-full px-2.5 py-1.5 text-xs border border-slate-300 rounded-lg outline-hidden focus:ring-1 focus:ring-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-bold text-slate-600 mb-1">Trả phòng</label>
                    <input
                      type="date"
                      value={checkOutDate}
                      onChange={(e) => setCheckOutDate(e.target.value)}
                      className="w-full px-2.5 py-1.5 text-xs border border-slate-300 rounded-lg outline-hidden focus:ring-1 focus:ring-blue-500"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 mb-1">Số phòng</label>
                  <div className="flex items-center border border-slate-300 rounded-lg overflow-hidden w-32">
                    <button
                      onClick={() => setQuantity(Math.max(1, quantity - 1))}
                      className="px-3 py-1 bg-slate-50 hover:bg-slate-100 text-slate-700 font-bold text-sm"
                    >
                      –
                    </button>
                    <span className="flex-1 text-center text-xs font-bold text-slate-800">{quantity}</span>
                    <button
                      onClick={() => setQuantity(quantity + 1)}
                      className="px-3 py-1 bg-slate-50 hover:bg-slate-100 text-slate-700 font-bold text-sm"
                    >
                      +
                    </button>
                  </div>
                </div>
              </>
            ) : product.taxonomy === 'flight' ? (
              <>
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 mb-1">Ngày bay</label>
                  <input
                    type="date"
                    value={checkInDate}
                    onChange={(e) => setCheckInDate(e.target.value)}
                    className="w-full px-2.5 py-1.5 text-xs border border-slate-300 rounded-lg outline-hidden focus:ring-1 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 mb-1">Số hành khách</label>
                  <div className="flex items-center border border-slate-300 rounded-lg overflow-hidden w-32">
                    <button
                      onClick={() => setQuantity(Math.max(1, quantity - 1))}
                      className="px-3 py-1 bg-slate-50 hover:bg-slate-100 text-slate-700 font-bold text-sm"
                    >
                      –
                    </button>
                    <span className="flex-1 text-center text-xs font-bold text-slate-800">{quantity}</span>
                    <button
                      onClick={() => setQuantity(quantity + 1)}
                      className="px-3 py-1 bg-slate-50 hover:bg-slate-100 text-slate-700 font-bold text-sm"
                    >
                      +
                    </button>
                  </div>
                </div>
              </>
            ) : (
              /* Attraction / Combo / Golf */
              <>
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 mb-1">Ngày sử dụng</label>
                  <div className="flex items-center gap-1 mb-2">
                    <button
                      onClick={() => setSelectedQuickDate('today')}
                      className={`px-2 py-1 text-[11px] rounded border ${selectedQuickDate === 'today' ? 'bg-blue-600 text-white border-blue-600' : 'border-slate-200 text-slate-600'}`}
                    >
                      Hôm nay
                    </button>
                    <button
                      onClick={() => setSelectedQuickDate('tomorrow')}
                      className={`px-2 py-1 text-[11px] rounded border ${selectedQuickDate === 'tomorrow' ? 'bg-blue-600 text-white border-blue-600' : 'border-slate-200 text-slate-600'}`}
                    >
                      Ngày mai
                    </button>
                    <button
                      onClick={() => setSelectedQuickDate('custom')}
                      className={`px-2 py-1 text-[11px] rounded border ${selectedQuickDate === 'custom' ? 'bg-blue-600 text-white border-blue-600' : 'border-slate-200 text-slate-600'}`}
                    >
                      Chọn ngày
                    </button>
                  </div>
                  <input
                    type="date"
                    value={checkInDate}
                    onChange={(e) => setCheckInDate(e.target.value)}
                    className="w-full px-2.5 py-1.5 text-xs border border-slate-300 rounded-lg outline-hidden focus:ring-1 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 mb-1">Số lượng vé</label>
                  <div className="flex items-center border border-slate-300 rounded-lg overflow-hidden w-32">
                    <button
                      onClick={() => setQuantity(Math.max(1, quantity - 1))}
                      className="px-3 py-1 bg-slate-50 hover:bg-slate-100 text-slate-700 font-bold text-sm"
                    >
                      –
                    </button>
                    <span className="flex-1 text-center text-xs font-bold text-slate-800">{quantity}</span>
                    <button
                      onClick={() => setQuantity(quantity + 1)}
                      className="px-3 py-1 bg-slate-50 hover:bg-slate-100 text-slate-700 font-bold text-sm"
                    >
                      +
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Total Calculation Display */}
          <div className="p-3 bg-slate-50 rounded-xl space-y-1 text-xs">
            <div className="flex justify-between text-slate-500">
              <span>Tạm tính:</span>
              <span>
                {product.taxonomy === 'hotel' 
                  ? `${nights} đêm × ${quantity} phòng` 
                  : `${quantity} khách/vé`}
              </span>
            </div>
            <div className="flex justify-between items-baseline pt-1 border-t border-slate-200/80">
              <span className="font-bold text-slate-800">Tổng cộng:</span>
              <span className="text-base font-extrabold text-blue-900 font-mono">
                {new Intl.NumberFormat('vi-VN').format(calculatedTotal)} ₫
              </span>
            </div>
          </div>

          {/* Action CTAs (§4.3.2) */}
          <div className="space-y-2">
            <button
              onClick={handleAddToCartClick}
              disabled={!product.available}
              className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white font-bold text-sm rounded-xl shadow-xs transition-colors"
            >
              Thêm vào giỏ hàng
            </button>

            <button
              onClick={handleBookNowClick}
              disabled={!product.available}
              className="w-full py-2.5 bg-blue-50 hover:bg-blue-100 disabled:bg-slate-100 text-blue-700 font-bold text-xs rounded-xl border border-blue-200 transition-colors"
            >
              Đặt ngay
            </button>
          </div>

          {/* Reassurance note */}
          <div className="flex items-center gap-1.5 text-[11px] text-slate-500 justify-center">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
            <span>Xác nhận tức thì · Hỗ trợ khách hàng 24/7</span>
          </div>
        </div>
      </div>

      {/* SECTION: Similar Products (/similar/:id) */}
      {similarProducts.length > 0 && (
        <div className="pt-8 border-t border-slate-200 space-y-4">
          <h2 className="text-lg font-black text-slate-900 tracking-tight">
            Tương tự {product.name}
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {similarProducts.map(sim => (
              <ProductCard
                key={sim.id}
                product={sim}
                variant="grid"
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
