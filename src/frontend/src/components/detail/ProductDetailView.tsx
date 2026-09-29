'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useTravel } from '../../context/TravelContext';
import {
  getProduct, getSimilarProducts, hasVariants, listProducts, listVariants, productFromApi, trackProductView,
  type VariantSummary,
} from '../../services/catalog';
import { fetchRecommendations } from '../../services/recsys';
import { ApiError } from '../../services/http';
import type { Product, RecommendationResponse } from '../../types/travel';
import { TaxonomyBadge } from '../common/TaxonomyBadge';
import { FlightSummary } from '../common/FlightSummary';
import { PriceTag } from '../common/PriceTag';
import { ProductCard } from '../common/ProductCard';
import { formatVnd } from '../confirmation/bookingLabels';
import type { CartState } from '../checkout/allocation';
import { estimateFares } from '../checkout/fareEstimate';
import { FareLines } from '../checkout/FareLines';
import { GuestCounters } from '../checkout/GuestCounters';
import { cartPayload, guestModeOf, initialCounts, isValidCounts, maxOccupancyFromAttributes } from '../checkout/guestCounts';
import { MapPin, Star, ShieldCheck, Users, BedDouble, Plane, Loader2 } from 'lucide-react';

/**
 * Trang chi tiết `/product/{productId}` (docs/spec/hop-dong-tich-hop-frontend.md §4.3, product.md §4.3).
 *
 * Mọi dữ liệu từ API: GET /products/{id}, /products/{id}/similar, /recommendations. Khách sạn (property) và
 * tuyến bay (route) chỉ để xem — khách chọn một hạng phòng / chuyến bay cụ thể (GET /products?parentProductId=)
 * và mục đó mới được thêm vào giỏ (FR-CAT-02).
 */

type LoadState =
  | { status: 'loading' }
  | { status: 'not_found' }
  | { status: 'error'; error: ApiError }
  | { status: 'ready'; product: Product; variantSummary: VariantSummary | null };

const DAY_MS = 24 * 3600 * 1000;

function isoDate(date: Date): string {
  return date.toLocaleDateString('en-CA', { timeZone: 'Asia/Ho_Chi_Minh' });
}

function addDays(iso: string, days: number): string {
  return isoDate(new Date(new Date(`${iso}T12:00:00+07:00`).getTime() + days * DAY_MS));
}

function clamp(iso: string, min?: string, max?: string): string {
  if (min && iso < min) return min;
  if (max && iso > max) return max;
  return iso;
}

/** Mặc định: ngày mai (giờ Việt Nam), kéo vào cửa sổ mở bán của mục đặt được. */
function defaultStart(unit: Product): string {
  return clamp(addDays(isoDate(new Date()), 1), unit.availableFrom, unit.availableTo);
}

function isBookable(unit: Product | null): unit is Product {
  return Boolean(unit && unit.available && unit.unitPrice != null && unit.attributes?.ticketed !== false
    && !hasVariants(unit));
}

function variantTitle(variant: Product): string {
  const a = variant.attributes || {};
  if (variant.taxonomy === 'flight') {
    const departure = typeof a.departureAt === 'string' ? a.departureAt.slice(11, 16) : '';
    return [a.flightNumber, departure && `khởi hành ${departure}`].filter(Boolean).join(' · ') || variant.name;
  }
  return a.roomName || variant.name;
}

function variantFacts(variant: Product): string[] {
  const a = variant.attributes || {};
  const facts: string[] = [];
  if (variant.taxonomy === 'flight') {
    if (variant.availableFrom) facts.push(new Date(`${variant.availableFrom}T12:00:00+07:00`).toLocaleDateString('vi-VN'));
    if (a.durationMinutes) facts.push(`${a.durationMinutes} phút`);
    if (a.nonstop) facts.push('Bay thẳng');
  } else {
    if (a.maxOccupancy) facts.push(`Tối đa ${a.maxOccupancy} khách`);
    if (a.roomSizeM2) facts.push(`${a.roomSizeM2} m²`);
    if (typeof a.bed === 'string' && a.bed) facts.push(a.bed);
  }
  return facts;
}

const DateInput: React.FC<{ label: string; value: string; min?: string; max?: string; onChange: (v: string) => void }> = ({
  label, value, min, max, onChange,
}) => (
  <div>
    <label className="block text-[11px] font-bold text-slate-600 mb-1">{label}</label>
    <input type="date" value={value} min={min} max={max} onChange={(e) => onChange(e.target.value)}
      className="w-full px-2.5 py-1.5 text-xs border border-slate-300 rounded-lg outline-hidden focus:ring-1 focus:ring-blue-500" />
  </div>
);

/** 404: "Sản phẩm này không còn trên V-OTA" + carousel phổ biến (product.md §4.3.4). */
const NotFound: React.FC<{ onHome: () => void }> = ({ onHome }) => {
  const [popular, setPopular] = useState<Product[]>([]);
  useEffect(() => {
    const controller = new AbortController();
    listProducts({ sort: 'popular', limit: 4 }, controller.signal)
      .then((page) => setPopular(page.results.map(productFromApi)))
      .catch(() => setPopular([]));
    return () => controller.abort();
  }, []);
  return (
    <div className="max-w-5xl mx-auto px-4 py-16 space-y-10">
      <div className="text-center space-y-4">
        <h2 className="text-xl font-bold text-slate-800">Sản phẩm này không còn trên V-OTA</h2>
        <p className="text-xs text-slate-500">Mã sản phẩm không tồn tại hoặc đã hết thời hạn mở bán.</p>
        <button onClick={onHome}
          className="px-5 py-2 bg-blue-600 text-white text-xs font-bold rounded-lg hover:bg-blue-700 transition-colors">
          Về trang chủ
        </button>
      </div>
      {popular.length > 0 && (
        <div className="space-y-4">
          <h3 className="text-base font-bold text-slate-900">Phổ biến trên V-OTA</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {popular.map((p) => <ProductCard key={p.id} product={p} variant="grid" />)}
          </div>
        </div>
      )}
    </div>
  );
};

export const ProductDetailView: React.FC<{ productId: string }> = ({ productId }) => {
  const { addToCart, navigate, currentPersona } = useTravel();
  const [state, setState] = useState<LoadState>({ status: 'loading' });
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setState({ status: 'loading' });
    getProduct(productId, controller.signal)
      .then((detail) => setState({
        status: 'ready', product: productFromApi(detail), variantSummary: detail.variantSummary ?? null,
      }))
      .catch((error) => {
        if (controller.signal.aborted) return;
        if (error instanceof ApiError && error.code === 'PRODUCT_NOT_FOUND') setState({ status: 'not_found' });
        else setState({ status: 'error', error: error instanceof ApiError ? error : new ApiError('Có lỗi xảy ra.', 'INTERNAL_ERROR', 0, true) });
      });
    return () => controller.abort();
  }, [productId, retry]);

  const product = state.status === 'ready' ? state.product : null;
  const variantSummary = state.status === 'ready' ? state.variantSummary : null;
  const needsVariant = product ? hasVariants(product) : false;

  // Ghi product_view đúng một lần mỗi sản phẩm, chỉ khi đã đăng nhập (frontend §4.3).
  const trackedId = useRef<string | null>(null);
  useEffect(() => {
    if (!product || !currentPersona || trackedId.current === product.id) return;
    trackedId.current = product.id;
    void trackProductView(product.id);
  }, [product, currentPersona]);

  // Hạng phòng / chuyến bay của sản phẩm cha.
  const [variants, setVariants] = useState<Product[] | null>(null);
  const [variantsFailed, setVariantsFailed] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  useEffect(() => {
    setVariants(null);
    setVariantsFailed(false);
    setSelectedId(null);
    if (!product || !needsVariant) return;
    const controller = new AbortController();
    listVariants(product.id, controller.signal)
      .then((page) => {
        const items = page.results.map(productFromApi);
        setVariants(items);
        setSelectedId(items.find(isBookable)?.id ?? null);
      })
      .catch(() => { if (!controller.signal.aborted) setVariantsFailed(true); });
    return () => controller.abort();
  }, [product, needsVariant]);

  const unit: Product | null = needsVariant ? variants?.find((v) => v.id === selectedId) ?? null : product;
  const bookable = isBookable(unit);

  // Ngày và số lượng theo mục đặt được đang chọn.
  const [checkIn, setCheckIn] = useState('');
  const [checkOut, setCheckOut] = useState('');
  // Số khách/số phòng/số gói (spec checkout-nhieu-buoc-hanh-khach.md §6.9); đổi hạng phòng/chuyến bay thì đặt lại.
  const [counts, setCounts] = useState<CartState>(initialCounts);
  useEffect(() => {
    if (!unit) return;
    const start = defaultStart(unit);
    setCheckIn(start);
    setCheckOut(clamp(addDays(start, 1), addDays(start, 1), unit.availableTo ? addDays(unit.availableTo, 1) : undefined));
    setCounts(initialCounts());
  }, [unit?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const isHotel = unit?.taxonomy === 'hotel';
  const fixedDate = unit?.availableFrom && unit.availableFrom === unit.availableTo;
  const nights = isHotel && checkIn && checkOut
    ? Math.max(1, Math.round((new Date(checkOut).getTime() - new Date(checkIn).getTime()) / DAY_MS))
    : 1;
  const mode = unit ? guestModeOf(unit.taxonomy) : 'person';
  const unitAttributes = (unit?.attributes ?? null) as Record<string, unknown> | null;
  const validCounts = bookable && isValidCounts(mode, counts, maxOccupancyFromAttributes(unitAttributes));
  // Chỉ để hiển thị: giá chính thức do Backend tính khi thêm vào giỏ và ở bước thanh toán.
  const estimate = bookable
    ? estimateFares({
      taxonomy: unit.taxonomy, unitPrice: unit.unitPrice as number, attributes: unitAttributes,
      quantity: counts.quantity, nights: isHotel ? nights : null, adults: counts.guests.adults, children: counts.guests.children,
    })
    : null;

  // Sản phẩm tương tự: lỗi hoặc rỗng thì ẩn section.
  const [similar, setSimilar] = useState<Product[]>([]);
  useEffect(() => {
    setSimilar([]);
    if (!product) return;
    const controller = new AbortController();
    getSimilarProducts(product.id, 8, controller.signal)
      .then((res) => setSimilar(res.results.map(productFromApi)))
      .catch(() => setSimilar([]));
    return () => controller.abort();
  }, [product]);

  // Hoàn thiện chuyến: chỉ khi đăng nhập và gợi ý cùng điểm đến với sản phẩm.
  const [trip, setTrip] = useState<RecommendationResponse | null>(null);
  useEffect(() => {
    setTrip(null);
    if (!product || !currentPersona) return;
    const controller = new AbortController();
    fetchRecommendations({ k: 4, destination: product.destination, signal: controller.signal })
      .then(setTrip)
      .catch(() => setTrip(null));
    return () => controller.abort();
  }, [product, currentPersona]);

  const handleAddToCart = () => {
    if (!bookable || !validCounts) return;
    const { quantity, guests } = cartPayload(mode, counts);
    void addToCart(unit, quantity, checkIn, isHotel ? checkOut : undefined, guests ? { guests } : undefined);
  };
  const handleBookNow = async () => {
    if (!bookable || !validCounts) return;
    const { quantity, guests } = cartPayload(mode, counts);
    if (await addToCart(unit, quantity, checkIn, isHotel ? checkOut : undefined, { silent: true, ...(guests ? { guests } : {}) })) {
      navigate('/checkout');
    }
  };

  if (state.status === 'loading') {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6" aria-busy="true">
        <div className="h-8 w-2/3 rounded-lg bg-slate-100 animate-pulse" />
        <div className="aspect-16/7 rounded-2xl bg-slate-100 animate-pulse" />
        <div className="h-40 rounded-2xl bg-slate-100 animate-pulse" />
      </div>
    );
  }
  if (state.status === 'not_found') return <NotFound onHome={() => navigate('/')} />;
  if (state.status === 'error' || !product) {
    const error = state.status === 'error' ? state.error : null;
    return (
      <div className="max-w-4xl mx-auto px-4 py-16 text-center space-y-4">
        <h2 className="text-xl font-bold text-slate-800">{error?.message || 'Có lỗi xảy ra.'}</h2>
        {error?.retryable !== false && (
          <button onClick={() => setRetry((n) => n + 1)}
            className="px-5 py-2 bg-blue-600 text-white text-xs font-bold rounded-lg hover:bg-blue-700 transition-colors">
            Thử lại
          </button>
        )}
      </div>
    );
  }

  const stars = Math.round(Number(product.attributes?.starRating) || 0);
  const variantNoun = product.taxonomy === 'flight' ? 'chuyến bay' : 'hạng phòng';
  const bookableVariants = (variants ?? []).filter(isBookable);
  const unavailableReason = !unit
    ? (needsVariant ? (variants && bookableVariants.length === 0
      ? `Hiện chưa có ${variantNoun} nào đặt được trên V-OTA.` : `Chọn một ${variantNoun} để đặt.`) : null)
    : !unit.available ? 'Sản phẩm này hiện đã hết chỗ.'
      : unit.unitPrice == null || unit.attributes?.ticketed === false ? 'Sản phẩm này chỉ để tham khảo, không bán vé trên V-OTA.'
        : null;
  const tripRecs = trip && trip.destination === product.destination
    ? trip.recommendations.filter((r) => r.product.id !== product.id) : [];

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-10">
      {/* Breadcrumbs & Header */}
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span className="hover:text-blue-600 cursor-pointer" onClick={() => navigate('/')}>Trang chủ</span>
          <span>›</span>
          <span className="hover:text-blue-600 cursor-pointer"
            onClick={() => navigate(`/search?q=${encodeURIComponent(product.destination)}&destination=${encodeURIComponent(product.destination)}`)}>
            {product.destination}
          </span>
          <span>›</span>
          <TaxonomyBadge taxonomy={product.taxonomy} size="sm" />
        </div>

        <div className="flex items-center gap-2 flex-wrap mb-1.5">
          <TaxonomyBadge taxonomy={product.taxonomy} size="md" />
          {stars > 0 && (
            <div className="flex items-center text-amber-500 text-xs font-bold">
              {Array.from({ length: stars }).map((_, i) => <Star key={i} className="w-3.5 h-3.5 fill-amber-400 text-amber-400" />)}
              <span className="ml-1 text-slate-700">{stars} sao</span>
            </div>
          )}
          <span className="flex items-center gap-1 text-xs text-slate-500">
            <MapPin className="w-3.5 h-3.5 text-slate-400" />
            {product.address || product.destination}
          </span>
        </div>
        <h1 className="text-xl sm:text-3xl font-black text-slate-900 tracking-tight">{product.name}</h1>
        {product.aggregateRating && (
          <p className="text-xs text-slate-500">
            ⭐ <strong className="text-slate-800 font-semibold">{product.aggregateRating.score}/5</strong>
            {product.aggregateRating.count > 0 && ` (${product.aggregateRating.count.toLocaleString('vi-VN')} đánh giá tổng hợp)`}
          </p>
        )}
      </div>

      {/* Ảnh: MVP chỉ có một imageUrl (backend §2.3) */}
      <div className="relative rounded-2xl overflow-hidden aspect-16/7 bg-slate-100 shadow-md border border-slate-200">
        <img src={product.imageUrl} alt={product.name} referrerPolicy="no-referrer" className="w-full h-full object-cover" />
        {!product.available && (
          <div className="absolute inset-0 bg-slate-900/70 flex items-center justify-center text-sm sm:text-base font-bold text-white uppercase tracking-wider">
            Sản phẩm hiện đã tạm hết chỗ
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
        {/* Cột trái: mô tả + chọn hạng phòng/chuyến bay */}
        <div className="lg:col-span-2 space-y-8">
          <div className="space-y-3">
            <h3 className="text-base font-bold text-slate-900">Mô tả chi tiết</h3>
            <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-line">
              {product.description || 'Chưa có mô tả cho dịch vụ này.'}
            </p>
          </div>

          {needsVariant && (
            <div className="space-y-3 pt-4 border-t border-slate-200" id="variants">
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                {product.taxonomy === 'flight' ? <Plane className="w-4 h-4 text-blue-600" /> : <BedDouble className="w-4 h-4 text-blue-600" />}
                Chọn {variantNoun}
                {variantSummary && variantSummary.count > 0 && (
                  <span className="text-xs font-medium text-slate-500">({variantSummary.count} lựa chọn)</span>
                )}
              </h3>
              {variantsFailed ? (
                <p className="text-xs text-slate-500">Chưa tải được danh sách {variantNoun}.</p>
              ) : variants === null ? (
                <div className="flex items-center gap-2 text-xs text-slate-500">
                  <Loader2 className="w-4 h-4 animate-spin" /> Đang tải {variantNoun}…
                </div>
              ) : variants.length === 0 ? (
                <p className="text-xs text-slate-500">
                  {product.taxonomy === 'flight' ? 'Tuyến bay' : 'Khách sạn'} này chưa có {variantNoun} nào trên V-OTA — chỉ để tham khảo.
                </p>
              ) : (
                <div className="space-y-2" role="radiogroup" aria-label={`Chọn ${variantNoun}`}>
                  {variants.map((variant) => {
                    const selectable = isBookable(variant);
                    const selected = variant.id === selectedId;
                    return (
                      <button key={variant.id} type="button" role="radio" aria-checked={selected} disabled={!selectable}
                        onClick={() => setSelectedId(variant.id)}
                        className={`w-full flex items-center justify-between gap-4 p-3.5 rounded-xl border text-left transition-colors ${
                          selected ? 'border-blue-600 bg-blue-50/60 ring-1 ring-blue-600'
                            : selectable ? 'border-slate-200 hover:border-blue-300 bg-white' : 'border-slate-100 bg-slate-50 opacity-60 cursor-not-allowed'}`}>
                        <div className="min-w-0">
                          <div className="text-sm font-bold text-slate-900 line-clamp-1">{variantTitle(variant)}</div>
                          <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 mt-0.5 text-[11px] text-slate-500">
                            {variantFacts(variant).map((fact) => (
                              <span key={fact} className="inline-flex items-center gap-1">
                                {fact.startsWith('Tối đa') && <Users className="w-3 h-3" />}{fact}
                              </span>
                            ))}
                            {!variant.available && <span className="font-semibold text-rose-600">Hết chỗ</span>}
                          </div>
                        </div>
                        <FlightSummary product={variant} />
                        <PriceTag price={variant.unitPrice} taxonomy={variant.taxonomy} size="sm" className="shrink-0 items-end" />
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          )}

        </div>

        {/* Cột phải: hộp đặt */}
        <div className="sticky top-20 bg-white p-6 rounded-2xl border border-slate-200 shadow-xl space-y-5">
          <div>
            <div className="text-xs text-slate-500 mb-1">
              {unit && needsVariant ? variantTitle(unit) : 'Giá công khai từ V-OTA'}
            </div>
            {unit ? (
              <>
                <PriceTag price={unit.unitPrice} taxonomy={unit.taxonomy} size="lg" showTaxesIncluded={unit.unitPrice != null} />
                <FlightSummary product={unit} />
              </>
            ) : (
              <PriceTag price={variantSummary?.minPrice ?? null} taxonomy={product.taxonomy} size="lg" hasPrefixFrom />
            )}
          </div>

          {bookable && (
            <div className="space-y-3 pt-3 border-t border-slate-100">
              {fixedDate ? (
                <div>
                  <div className="block text-[11px] font-bold text-slate-600 mb-1">
                    {unit.taxonomy === 'flight' ? 'Ngày bay' : 'Ngày sử dụng'}
                  </div>
                  <div className="text-sm font-semibold text-slate-800">
                    {new Date(`${unit.availableFrom}T12:00:00+07:00`).toLocaleDateString('vi-VN')}
                  </div>
                </div>
              ) : isHotel ? (
                <div className="grid grid-cols-2 gap-2">
                  <DateInput label="Nhận phòng" value={checkIn} min={unit.availableFrom} max={unit.availableTo}
                    onChange={(v) => { setCheckIn(v); if (checkOut <= v) setCheckOut(addDays(v, 1)); }} />
                  <DateInput label="Trả phòng" value={checkOut} min={checkIn ? addDays(checkIn, 1) : undefined}
                    max={unit.availableTo ? addDays(unit.availableTo, 1) : undefined} onChange={setCheckOut} />
                </div>
              ) : (
                <DateInput label="Ngày sử dụng" value={checkIn} min={unit.availableFrom} max={unit.availableTo} onChange={setCheckIn} />
              )}
              <GuestCounters taxonomy={unit.taxonomy} unitPrice={unit.unitPrice as number} attributes={unitAttributes}
                value={counts} onChange={setCounts} />
            </div>
          )}

          {estimate && (
            <div className="space-y-2" data-testid="estimate">
              <FareLines fares={estimate.lines} testId="estimate-lines" />
              <div className="flex justify-between items-baseline px-3 py-2 bg-slate-50 rounded-xl">
                <span className="text-xs font-bold text-slate-800">Tổng ước tính:</span>
                <span className="text-base font-extrabold text-blue-900 font-mono" data-testid="estimate-total">{formatVnd(estimate.total)}</span>
              </div>
            </div>
          )}

          {unavailableReason && (
            <p className="text-xs text-slate-600 bg-amber-50 border border-amber-200 rounded-lg p-2.5">{unavailableReason}</p>
          )}

          <div className="space-y-2">
            <button onClick={handleAddToCart} disabled={!bookable || !validCounts}
              className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white font-bold text-sm rounded-xl shadow-xs transition-colors">
              Thêm vào giỏ hàng
            </button>
            <button onClick={() => void handleBookNow()} disabled={!bookable || !validCounts}
              className="w-full py-2.5 bg-blue-50 hover:bg-blue-100 disabled:bg-slate-100 disabled:text-slate-400 text-blue-700 font-bold text-xs rounded-xl border border-blue-200 transition-colors">
              Đặt ngay
            </button>
          </div>

          <div className="flex items-center gap-1.5 text-[11px] text-slate-500 justify-center">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
            <span>Giá chính thức được xác nhận ở bước thanh toán</span>
          </div>
        </div>
      </div>

      {similar.length > 0 && (
        <div className="pt-8 border-t border-slate-200 space-y-4">
          <h2 className="text-lg font-black text-slate-900 tracking-tight">Tương tự {product.name}</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {similar.slice(0, 8).map((sim) => <ProductCard key={sim.id} product={sim} variant="grid" />)}
          </div>
        </div>
      )}

      {tripRecs.length > 0 && (
        <div className="pt-8 border-t border-slate-200 space-y-4">
          <h2 className="text-lg font-black text-slate-900 tracking-tight">Hoàn thiện chuyến {product.destination}</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {tripRecs.map((rec) => (
              <ProductCard key={rec.product.id} product={rec.product} variant="grid" because={rec.because}
                strategy={trip!.strategy} excludedVerticals={trip!.diagnostics.excludedVerticals} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
