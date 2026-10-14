import React, { useEffect, useRef, useState } from 'react';
import { Check, Clock, ExternalLink, Loader2, MapPin, Navigation, RotateCcw, ShoppingCart, X } from 'lucide-react';
import { getProduct, productFromApi, trackProductView } from '../../../services/catalog';
import { useTravel } from '../../../context/TravelContext';
import { PriceTag } from '../../../components/common/PriceTag';
import { TaxonomyBadge } from '../../../components/common/TaxonomyBadge';
import { SkeletonBlock, SkeletonStatus } from '../../../components/common/Skeleton';
import type { Product } from '../../../types/travel';
import { isFreeToVisit } from './widgetPlan';
import { WidgetProductGallery } from './WidgetProductGallery';
import type { CartAddState } from './useWidgetCart';

/** Mô tả dài hơn mức này thì thu gọn, có nút "Xem thêm" (mô tả khách sạn trung bình ~3.700 ký tự). */
const DESCRIPTION_CLAMP_CHARS = 400;

/** Bộ ảnh của panel: ảnh đại diện rồi `attributes.images` của catalog, chỉ URL http(s), bỏ trùng. */
export function galleryImages(product: Pick<Product, 'imageUrl' | 'attributes'>): string[] {
  const extra = Array.isArray(product.attributes?.images) ? product.attributes.images : [];
  const urls = [product.imageUrl, ...extra].filter((url): url is string => typeof url === 'string' && /^https?:\/\//.test(url));
  return [...new Set(urls)];
}

/** Link chỉ đường của Google Maps theo toạ độ catalog; không có toạ độ thì không có link. */
export function directionsUrl(coordinates: Product['coordinates']): string | null {
  return coordinates ? `https://www.google.com/maps/dir/?api=1&destination=${coordinates.lat},${coordinates.lng}` : null;
}

interface WidgetProductDetailProps {
  productId: string;
  /** Dữ liệu đã có trong response (tên, ảnh, giá) để hiện ngay trong lúc tải chi tiết. */
  summary?: Product;
  onClose: () => void;
  /** Chỉ có khi sản phẩm là mục đặt được của lịch trình (`cartItems`). */
  onAddToCart?: () => void;
  /** Đặt ngay mục này (đơn nháp một mục); khách sạn và vé máy bay chỉ có nút này. */
  onBookNow?: () => void;
  cartAddState?: CartAddState;
}

type LoadState = { status: 'loading' | 'error' } | { status: 'ready'; product: Product };

/**
 * Panel chi tiết ở cột phải của widget khi bấm thẻ hoặc tên sản phẩm trong lời diễn giải (PRD user-flow.md §4.2).
 * Mọi nội dung lấy từ `GET /products/{productId}`; không có danh sách bình luận vì catalog không có dữ liệu đó.
 */
export function WidgetProductDetail({ productId, summary, onClose, onAddToCart, onBookNow, cartAddState }: WidgetProductDetailProps) {
  const { currentPersona } = useTravel();
  const [state, setState] = useState<LoadState>({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);
  const [activeImage, setActiveImage] = useState(0);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setState({ status: 'loading' });
    setActiveImage(0);
    setExpanded(false);
    getProduct(productId, controller.signal)
      .then((detail) => setState({ status: 'ready', product: productFromApi(detail) }))
      .catch(() => {
        if (!controller.signal.aborted) setState({ status: 'error' });
      });
    return () => controller.abort();
  }, [productId, attempt]);

  // Ghi product_view một lần mỗi sản phẩm, chỉ khi đã đăng nhập — như trang chi tiết (frontend §4.3).
  const trackedId = useRef<string | null>(null);
  useEffect(() => {
    if (!currentPersona || trackedId.current === productId) return;
    trackedId.current = productId;
    void trackProductView(productId);
  }, [productId, currentPersona]);

  const product = state.status === 'ready' ? state.product : summary;
  if (!product) {
    return (
      <PanelFrame onClose={onClose}>
        {state.status === 'error'
          ? <LoadError onRetry={() => setAttempt((count) => count + 1)} />
          : <DetailSkeleton />}
      </PanelFrame>
    );
  }

  const images = galleryImages(product);
  const directions = directionsUrl(product.coordinates);
  const openingHours = typeof product.attributes.openingHours === 'string' ? product.attributes.openingHours : null;
  const openingHoursDetail = typeof product.attributes.openingHoursDetail === 'string' ? product.attributes.openingHoursDetail : null;
  const description = product.description?.trim() ?? '';
  const longDescription = description.length > DESCRIPTION_CLAMP_CHARS;
  const freeToVisit = isFreeToVisit(product);

  return (
    <PanelFrame onClose={onClose} footer={
      <div className="shrink-0 space-y-3 border-t border-slate-200/70 bg-white px-5 py-4 xl:px-6">
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs text-slate-500">Giá dịch vụ</span>
          {freeToVisit
            ? <span className="text-sm font-semibold text-emerald-700">Tham quan tự do</span>
            : <PriceTag price={product.unitPrice} taxonomy={product.taxonomy} size="lg" className="[&>div]:flex-wrap [&>div]:justify-end" />}
        </div>
        <div className="flex flex-col gap-2 xl:flex-row">
          {onAddToCart && (
            <button type="button" onClick={onAddToCart} disabled={Boolean(cartAddState)} aria-busy={cartAddState === 'adding'}
              className={`inline-flex min-h-11 flex-1 items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold text-white transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600 disabled:cursor-default ${cartAddState === 'added' ? 'bg-emerald-600' : 'bg-brand-600 hover:bg-brand-700'}`}>
              {cartAddState === 'adding' ? <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                : cartAddState === 'added' ? <Check className="h-4 w-4" aria-hidden="true" /> : <ShoppingCart className="h-4 w-4" aria-hidden="true" />}
              <span aria-live="polite">{cartAddState === 'adding' ? 'Đang thêm…' : cartAddState === 'added' ? 'Đã thêm vào giỏ' : 'Thêm vào giỏ'}</span>
            </button>
          )}
          {onBookNow && (
            <button type="button" onClick={onBookNow}
              className="inline-flex min-h-11 flex-1 items-center justify-center gap-2 rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600">
              Đặt ngay
            </button>
          )}
          {!freeToVisit && <a href={`/product/${encodeURIComponent(product.id)}`} target="_blank" rel="noopener noreferrer"
            className="inline-flex min-h-11 flex-1 items-center justify-center gap-2 rounded-xl border-2 border-brand-600 bg-brand-50 px-4 py-2.5 text-sm font-semibold text-brand-700 transition hover:border-brand-700 hover:bg-brand-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600">
            Xem trang chi tiết<ExternalLink className="h-4 w-4 shrink-0" aria-hidden="true" />
          </a>}
        </div>
      </div>
    }>
      <WidgetProductGallery images={images} name={product.name} taxonomy={product.taxonomy}
        activeImage={activeImage} onSelect={setActiveImage} />

      <div className="space-y-3">
        <TaxonomyBadge taxonomy={product.taxonomy} size="sm" freeToVisit={freeToVisit} />
        <h2 className="font-sans break-words text-xl font-semibold leading-snug tracking-tight text-slate-900 xl:text-2xl">{product.name}</h2>
        {product.aggregateRating && (
          <p className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
            <span className="rounded-lg bg-brand-50 px-2 py-1 font-semibold text-brand-800">{product.aggregateRating.score}/5</span>
            {product.aggregateRating.count > 0 && <span className="text-slate-500"> · {product.aggregateRating.count.toLocaleString('vi-VN')} đánh giá</span>}
          </p>
        )}
      </div>

      {state.status === 'error' && <LoadError onRetry={() => setAttempt((count) => count + 1)} />}
      {state.status === 'loading' && (
        <SkeletonStatus label="Đang tải chi tiết…" className="space-y-2 border-t border-slate-100 pt-5">
          <SkeletonBlock className="h-4 w-24 rounded" />
          {['w-full', 'w-full', 'w-5/6', 'w-2/3'].map((w, i) => <SkeletonBlock key={i} className={`h-3 rounded ${w}`} />)}
        </SkeletonStatus>
      )}

      {description && (
        <div className="space-y-2 border-t border-slate-100 pt-5">
          <h3 className="font-sans text-sm font-semibold text-slate-900">Giới thiệu</h3>
          <p className={`whitespace-pre-line text-sm leading-relaxed text-slate-700 ${longDescription && !expanded ? 'line-clamp-6' : ''}`}>{description}</p>
          {longDescription && (
            <button type="button" onClick={() => setExpanded((open) => !open)} aria-expanded={expanded} className="inline-flex min-h-11 items-center text-sm font-semibold text-brand-700 hover:underline focus-visible:outline-2 focus-visible:outline-brand-600">
              {expanded ? 'Thu gọn' : 'Xem thêm'}
            </button>
          )}
        </div>
      )}

      <div className="grid gap-5 rounded-xl border border-slate-100 bg-slate-50 p-4">
        <div className="flex items-start gap-2 text-sm">
          <MapPin className="mt-0.5 h-5 w-5 shrink-0 text-brand-600" aria-hidden="true" />
          <div className="min-w-0 break-words">
            <p className="font-semibold text-slate-800">Địa chỉ</p>
            <p className="text-slate-600">{product.address || product.destination}</p>
            {directions && (
              <a href={directions} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 items-center gap-1.5 font-semibold text-brand-700 hover:underline focus-visible:outline-2 focus-visible:outline-brand-600">
                <Navigation className="h-3.5 w-3.5" aria-hidden="true" />Chỉ đường
              </a>
            )}
          </div>
        </div>
        {openingHours && (
          <div className="flex items-start gap-2 text-sm">
            <Clock className="mt-0.5 h-5 w-5 shrink-0 text-brand-600" aria-hidden="true" />
            <div>
              <p className="font-semibold text-slate-800">Giờ mở cửa</p>
              <p className="text-slate-600">{openingHours}</p>
              {openingHoursDetail && <p className="text-xs text-slate-500">{openingHoursDetail}</p>}
            </div>
          </div>
        )}
      </div>

    </PanelFrame>
  );
}

function PanelFrame({ onClose, children, footer }: { onClose: () => void; children: React.ReactNode; footer?: React.ReactNode }) {
  return (
    <section aria-label="Chi tiết sản phẩm" className="relative flex h-full min-w-0 flex-col overflow-hidden bg-white">
      <div className="flex min-h-20 shrink-0 items-center justify-between gap-3 border-b border-slate-200/70 px-5 py-3 xl:px-6">
        <p className="text-sm font-semibold text-slate-900">Chi tiết dịch vụ</p>
        <button type="button" onClick={onClose} aria-label="Đóng chi tiết"
          className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-50 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-2 focus-visible:outline-brand-600">
          <X className="h-5 w-5" aria-hidden="true" />
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
        <div className="mx-auto max-w-4xl space-y-5 p-5 xl:p-6">{children}</div>
      </div>
      {footer}
    </section>
  );
}

function LoadError({ onRetry }: { onRetry: () => void }) {
  return (
    <div role="alert" className="flex flex-wrap items-center justify-between gap-x-3 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
      <span>Chưa tải được chi tiết sản phẩm.</span>
      <button type="button" onClick={onRetry} className="inline-flex min-h-11 items-center gap-1.5 font-semibold underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-700">
        <RotateCcw className="h-4 w-4" aria-hidden="true" />Thử lại
      </button>
    </div>
  );
}

function DetailSkeleton() {
  return (
    <SkeletonStatus label="Đang tải chi tiết…" className="space-y-5">
      <SkeletonBlock className="aspect-[4/3] rounded-xl" />
      <SkeletonBlock className="h-6 w-3/4 rounded" />
      <div className="space-y-2">
        <SkeletonBlock className="h-3 w-full rounded" />
        <SkeletonBlock className="h-3 w-5/6 rounded" />
      </div>
    </SkeletonStatus>
  );
}
