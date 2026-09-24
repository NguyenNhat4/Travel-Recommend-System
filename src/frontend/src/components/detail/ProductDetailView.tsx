'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { useTravel } from '../../context/TravelContext';
import { getSimilarProducts } from '../../services/recsys';
import {
  ApiError,
  ProductDetail,
  ProductSummary,
  addDays,
  fetchProductDetail,
  firstOpenDate,
  isOpen,
  toProduct,
} from '../../services/booking';
import { TaxonomyBadge } from '../common/TaxonomyBadge';
import { PriceTag } from '../common/PriceTag';
import { ProductCard } from '../common/ProductCard';
import { MapPin, Star, ShieldCheck, Sparkles, Loader2, BedDouble, Plane } from 'lucide-react';

interface ProductDetailViewProps {
  productId: string;
}

const formatVnd = (value: number) => new Intl.NumberFormat('vi-VN').format(value);
const todayIso = () => new Date().toISOString().slice(0, 10);
const nightsBetween = (from: string, to: string) =>
  Math.max(1, Math.round((Date.parse(to) - Date.parse(from)) / 86_400_000));

/** Tên hạng phòng thường là "<Khách sạn> - <Hạng phòng>"; bỏ phần tên khách sạn cho gọn danh sách. */
const variantLabel = (parentName: string, variant: ProductSummary) =>
  variant.name.startsWith(`${parentName} - `) ? variant.name.slice(parentName.length + 3) : variant.name;

/** Ngày nhận phòng mặc định: đêm trống sớm nhất của hạng phòng rẻ nhất còn trống. */
function defaultSelection(detail: ProductDetail): { variantId?: string; date: string } {
  const today = todayIso();
  const units = detail.variants?.length ? detail.variants : [detail];
  for (const unit of units) {
    const date = firstOpenDate(unit, today, 1);
    if (date) return { variantId: detail.variants?.length ? unit.productId : undefined, date };
  }
  return { variantId: detail.variants?.[0]?.productId, date: detail.availableFrom && detail.availableFrom > today ? detail.availableFrom : today };
}

export const ProductDetailView: React.FC<ProductDetailViewProps> = ({ productId }) => {
  const { addToCart, navigate, currentPersona, openLoginModal } = useTravel();
  const [detail, setDetail] = useState<ProductDetail | null>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'not_found' | 'error'>('loading');

  // Booking box: đơn vị đặt được là hạng phòng / chuyến bay (FR-CAT-02) hoặc chính sản phẩm (vé, combo, golf).
  const [variantId, setVariantId] = useState<string | undefined>();
  const [checkInDate, setCheckInDate] = useState(todayIso());
  const [checkOutDate, setCheckOutDate] = useState(addDays(todayIso(), 1));
  const [quantity, setQuantity] = useState(1);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setStatus('loading');
    fetchProductDetail(productId)
      .then((data) => {
        if (cancelled) return;
        const selection = defaultSelection(data);
        setDetail(data);
        setVariantId(selection.variantId);
        setCheckInDate(selection.date);
        setCheckOutDate(addDays(selection.date, 1));
        setStatus('ready');
      })
      .catch((error) => {
        if (!cancelled) setStatus(error instanceof ApiError && error.status === 404 ? 'not_found' : 'error');
      });
    return () => { cancelled = true; };
  }, [productId]);

  const product = useMemo(() => (detail ? toProduct(detail) : null), [detail]);
  const variants = detail?.variants ?? [];
  const selectedVariant = variants.find((variant) => variant.productId === variantId);
  const isHotel = detail?.taxonomy === 'hotel';
  const isFlightRoute = detail?.taxonomy === 'flight' && variants.length > 0;
  // Đơn vị sẽ vào giỏ: con đã chọn, hoặc chính sản phẩm khi nó tự đặt được (bookable khác false).
  const unit: ProductSummary | ProductDetail | undefined =
    variants.length > 0 ? selectedVariant : detail?.bookable === false ? undefined : detail ?? undefined;
  const usingDate = isFlightRoute ? selectedVariant?.availableFrom ?? checkInDate : checkInDate;
  const nights = isHotel ? nightsBetween(checkInDate, checkOutDate) : 1;
  const unitOpen = unit ? isOpen(unit, usingDate, nights) : false;
  const unitPrice = unit?.unitPrice ?? detail?.unitPrice ?? 0;
  const estimatedTotal = unitPrice * quantity * (isHotel ? nights : 1);

  const similarProducts = useMemo(() => (product ? getSimilarProducts(product.id) : []), [product]);

  if (status === 'loading') {
    return (
      <div className="max-w-4xl mx-auto px-4 py-16 flex items-center justify-center gap-2 text-sm text-slate-500">
        <Loader2 className="w-4 h-4 animate-spin" />
        <span>Đang tải sản phẩm…</span>
      </div>
    );
  }

  if (status !== 'ready' || !detail || !product) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-16 text-center space-y-4">
        <h2 className="text-xl font-bold text-slate-800">
          {status === 'not_found' ? 'Sản phẩm này không còn trên V-OTA' : 'Chưa tải được sản phẩm'}
        </h2>
        <p className="text-xs text-slate-500">
          {status === 'not_found' ? 'Mã sản phẩm không tồn tại hoặc đã hết thời hạn mở bán.' : 'Vui lòng thử lại sau ít phút.'}
        </p>
        <button
          onClick={() => navigate('/')}
          className="px-5 py-2 bg-blue-600 text-white text-xs font-bold rounded-lg hover:bg-blue-700 transition-colors"
        >
          Về trang chủ
        </button>
      </div>
    );
  }

  const addSelected = async () => {
    if (!unit) return false;
    setSubmitting(true);
    try {
      return await addToCart(toProduct(unit), quantity, usingDate, isHotel ? checkOutDate : undefined);
    } finally {
      setSubmitting(false);
    }
  };

  const handleBookNow = async () => {
    if (!currentPersona) {
      openLoginModal(() => { void addSelected().then((added) => { if (added) navigate('/checkout'); }); });
      return;
    }
    if (await addSelected()) navigate('/checkout');
  };

  const canBook = Boolean(unit) && unitOpen && !submitting;
  const unavailableHint = !unit
    ? (variants.length === 0 && detail.bookable === false ? 'Hiện chưa có hạng phòng hoặc chuyến bay còn bán.' : 'Chọn một lựa chọn bên dưới để đặt.')
    : !unitOpen ? 'Lựa chọn này đã kín cho ngày đã chọn — hãy đổi ngày hoặc chọn loại khác.' : '';

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

        <div>
          <div className="flex items-center gap-2 flex-wrap mb-1.5">
            <TaxonomyBadge taxonomy={product.taxonomy} size="md" />
            {typeof product.attributes.starRating === 'number' && product.attributes.starRating > 0 && (
              <div className="flex items-center text-amber-500 text-xs font-bold">
                {[...Array(Math.round(product.attributes.starRating))].map((_, i) => (
                  <Star key={i} className="w-3.5 h-3.5 fill-amber-400 text-amber-400" />
                ))}
              </div>
            )}
            <span className="flex items-center gap-1 text-xs text-slate-500">
              <MapPin className="w-3.5 h-3.5 text-slate-400" />
              {product.destination}
            </span>
          </div>
          <h1 className="text-xl sm:text-3xl font-black text-slate-900 tracking-tight">{product.name}</h1>
          {product.aggregateRating && (
            <p className="text-xs text-slate-500 mt-1">
              ⭐ <strong className="text-slate-800 font-semibold">{product.aggregateRating.score}/5</strong> ({product.aggregateRating.count} đánh giá)
            </p>
          )}
        </div>
      </div>

      {/* Hero */}
      <div className="relative rounded-2xl overflow-hidden aspect-16/7 bg-slate-100 shadow-md border border-slate-200">
        <img src={product.imageUrl} alt={product.name} referrerPolicy="no-referrer" className="w-full h-full object-cover" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
        {/* Left: description + variant list */}
        <div className="lg:col-span-2 space-y-8">
          {product.description && (
            <div className="space-y-3">
              <h3 className="text-base font-bold text-slate-900">Mô tả chi tiết</h3>
              <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-line">{product.description}</p>
            </div>
          )}

          {variants.length > 0 && (
            <div className="space-y-3 pt-4 border-t border-slate-200">
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                {isHotel ? <BedDouble className="w-4 h-4 text-blue-600" /> : <Plane className="w-4 h-4 text-blue-600" />}
                {isHotel ? `Chọn hạng phòng (${variants.length})` : `Chọn chuyến bay (${variants.length})`}
              </h3>
              <div className="space-y-2">
                {variants.map((variant) => {
                  const date = isFlightRoute ? variant.availableFrom ?? checkInDate : checkInDate;
                  const open = isOpen(variant, date, nights);
                  const selected = variant.productId === variantId;
                  const occupancy = (variant.attributes as Record<string, unknown> | undefined)?.maxOccupancy;
                  return (
                    <label
                      key={variant.productId}
                      className={`flex items-center justify-between gap-3 p-3 rounded-xl border cursor-pointer transition-colors ${
                        selected ? 'border-blue-500 bg-blue-50/60' : 'border-slate-200 hover:border-slate-300'
                      } ${open ? '' : 'opacity-60'}`}
                    >
                      <span className="flex items-start gap-3 min-w-0">
                        <input
                          type="radio"
                          name="variant"
                          checked={selected}
                          onChange={() => setVariantId(variant.productId)}
                          className="mt-1"
                        />
                        <span className="min-w-0">
                          <span className="block text-sm font-semibold text-slate-900 truncate">
                            {variantLabel(product.name, variant)}
                          </span>
                          <span className="block text-[11px] text-slate-500">
                            {isFlightRoute ? `Ngày bay ${variant.availableFrom}` : occupancy ? `Tối đa ${occupancy} khách` : 'Hạng phòng'}
                            {' · '}
                            <span className={open ? 'text-emerald-600 font-semibold' : 'text-rose-600 font-semibold'}>
                              {open ? (isHotel ? 'Còn phòng ngày đã chọn' : 'Còn chỗ') : (isHotel ? 'Kín ngày đã chọn' : 'Hết chỗ')}
                            </span>
                          </span>
                        </span>
                      </span>
                      <span className="text-sm font-bold text-blue-900 font-mono shrink-0">
                        {formatVnd(variant.unitPrice ?? 0)} ₫<span className="text-[10px] text-slate-500 font-sans">{isHotel ? '/đêm' : '/khách'}</span>
                      </span>
                    </label>
                  );
                })}
              </div>
            </div>
          )}

          <div className="p-4 bg-indigo-50 border border-indigo-200 rounded-xl flex items-center justify-between gap-4">
            <div className="text-xs font-bold text-indigo-900 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
              Lên lịch trình kết hợp xung quanh {product.destination}
            </div>
            <button
              onClick={() => navigate('/assistant')}
              className="px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs rounded-lg shadow-xs transition-colors shrink-0"
            >
              Hỏi Trợ lý AI →
            </button>
          </div>
        </div>

        {/* Right: booking box */}
        <div className="sticky top-20 bg-white p-6 rounded-2xl border border-slate-200 shadow-xl space-y-5">
          <div>
            <div className="text-xs text-slate-500 mb-1">{selectedVariant ? variantLabel(product.name, selectedVariant) : 'Giá tham khảo'}</div>
            <PriceTag price={unitPrice} taxonomy={product.taxonomy} size="lg" showTaxesIncluded />
          </div>

          <div className="space-y-3 pt-3 border-t border-slate-100">
            {isHotel ? (
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 mb-1">Nhận phòng</label>
                  <input
                    type="date"
                    value={checkInDate}
                    min={todayIso()}
                    onChange={(e) => {
                      setCheckInDate(e.target.value);
                      if (e.target.value >= checkOutDate) setCheckOutDate(addDays(e.target.value, 1));
                    }}
                    className="w-full px-2.5 py-1.5 text-xs border border-slate-300 rounded-lg outline-hidden focus:ring-1 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold text-slate-600 mb-1">Trả phòng</label>
                  <input
                    type="date"
                    value={checkOutDate}
                    min={addDays(checkInDate, 1)}
                    onChange={(e) => setCheckOutDate(e.target.value)}
                    className="w-full px-2.5 py-1.5 text-xs border border-slate-300 rounded-lg outline-hidden focus:ring-1 focus:ring-blue-500"
                  />
                </div>
              </div>
            ) : !isFlightRoute ? (
              <div>
                <label className="block text-[11px] font-bold text-slate-600 mb-1">Ngày sử dụng</label>
                <input
                  type="date"
                  value={checkInDate}
                  min={detail.availableFrom ?? todayIso()}
                  max={detail.availableTo ?? undefined}
                  onChange={(e) => setCheckInDate(e.target.value)}
                  className="w-full px-2.5 py-1.5 text-xs border border-slate-300 rounded-lg outline-hidden focus:ring-1 focus:ring-blue-500"
                />
              </div>
            ) : null}

            <div>
              <label className="block text-[11px] font-bold text-slate-600 mb-1">
                {isHotel ? 'Số phòng' : detail.taxonomy === 'flight' ? 'Số hành khách' : 'Số lượng'}
              </label>
              <div className="flex items-center border border-slate-300 rounded-lg overflow-hidden w-32">
                <button onClick={() => setQuantity(Math.max(1, quantity - 1))} className="px-3 py-1 bg-slate-50 hover:bg-slate-100 text-slate-700 font-bold text-sm">–</button>
                <span className="flex-1 text-center text-xs font-bold text-slate-800">{quantity}</span>
                <button onClick={() => setQuantity(quantity + 1)} className="px-3 py-1 bg-slate-50 hover:bg-slate-100 text-slate-700 font-bold text-sm">+</button>
              </div>
            </div>
          </div>

          {/* Ước tính hiển thị; giá chính thức là lineTotal backend trả về (frontend §4.3) */}
          <div className="p-3 bg-slate-50 rounded-xl space-y-1 text-xs">
            <div className="flex justify-between text-slate-500">
              <span>Tạm tính:</span>
              <span>{isHotel ? `${nights} đêm × ${quantity} phòng` : `${quantity} khách/vé`}</span>
            </div>
            <div className="flex justify-between items-baseline pt-1 border-t border-slate-200/80">
              <span className="font-bold text-slate-800">Tổng cộng:</span>
              <span className="text-base font-extrabold text-blue-900 font-mono">{formatVnd(estimatedTotal)} ₫</span>
            </div>
          </div>

          {unavailableHint && <p className="text-[11px] text-amber-700">{unavailableHint}</p>}

          <div className="space-y-2">
            <button
              onClick={() => { void addSelected(); }}
              disabled={!canBook}
              className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white font-bold text-sm rounded-xl shadow-xs transition-colors"
            >
              Thêm vào giỏ hàng
            </button>
            <button
              onClick={() => { void handleBookNow(); }}
              disabled={!canBook}
              className="w-full py-2.5 bg-blue-50 hover:bg-blue-100 disabled:bg-slate-100 text-blue-700 font-bold text-xs rounded-xl border border-blue-200 transition-colors"
            >
              Đặt ngay
            </button>
          </div>

          <div className="flex items-center gap-1.5 text-[11px] text-slate-500 justify-center">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
            <span>Xác nhận tức thì · Hỗ trợ khách hàng 24/7</span>
          </div>
        </div>
      </div>

      {similarProducts.length > 0 && (
        <div className="pt-8 border-t border-slate-200 space-y-4">
          <h2 className="text-lg font-black text-slate-900 tracking-tight">Tương tự {product.name}</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {similarProducts.map(sim => (
              <ProductCard key={sim.id} product={sim} variant="grid" />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
