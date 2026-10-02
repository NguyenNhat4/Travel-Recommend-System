import React, { useEffect, useRef, useState } from 'react';
import { Clock, ExternalLink, Loader2, MapPin, Navigation, RotateCcw, ShoppingCart, X } from 'lucide-react';
import { getProduct, productFromApi, trackProductView } from '../../../services/catalog';
import { useTravel } from '../../../context/TravelContext';
import { PriceTag } from '../../../components/common/PriceTag';
import { TaxonomyBadge } from '../../../components/common/TaxonomyBadge';
import type { Product } from '../../../types/travel';
import { isFreeToVisit } from './widgetPlan';
import { placeholderOnError } from './widgetVisuals';

/** Mô tả dài hơn mức này thì thu gọn, có nút "Xem thêm" (mô tả khách sạn trung bình ~3.700 ký tự). */
const DESCRIPTION_CLAMP_CHARS = 400;
/** Số ảnh nhỏ cạnh ảnh lớn; ảnh còn lại gom thành "+n". */
const THUMBNAILS = 4;

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
}

type LoadState = { status: 'loading' | 'error' } | { status: 'ready'; product: Product };

/**
 * Panel chi tiết ở cột phải của widget khi bấm thẻ hoặc tên sản phẩm trong lời diễn giải (PRD user-flow.md §4.2).
 * Mọi nội dung lấy từ `GET /products/{productId}`; không có danh sách bình luận vì catalog không có dữ liệu đó.
 */
export function WidgetProductDetail({ productId, summary, onClose, onAddToCart }: WidgetProductDetailProps) {
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
          : <p role="status" className="flex items-center gap-2 text-sm text-slate-500"><Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />Đang tải chi tiết…</p>}
      </PanelFrame>
    );
  }

  const images = galleryImages(product);
  const mainImage = images[activeImage] ?? images[0];
  const thumbnails = images.filter((url) => url !== mainImage);
  const hiddenCount = Math.max(0, thumbnails.length - THUMBNAILS);
  const directions = directionsUrl(product.coordinates);
  const openingHours = typeof product.attributes.openingHours === 'string' ? product.attributes.openingHours : null;
  const openingHoursDetail = typeof product.attributes.openingHoursDetail === 'string' ? product.attributes.openingHoursDetail : null;
  const description = product.description?.trim() ?? '';
  const longDescription = description.length > DESCRIPTION_CLAMP_CHARS;

  return (
    <PanelFrame onClose={onClose}>
      {mainImage && (
        <div className={`grid gap-2 ${thumbnails.length ? 'grid-cols-3' : 'grid-cols-1'}`}>
          <div className={`relative overflow-hidden rounded-2xl bg-slate-100 ${thumbnails.length ? 'col-span-2 aspect-[4/3]' : 'aspect-[16/9]'}`}>
            <img src={mainImage} alt={product.name} onError={placeholderOnError(product.taxonomy)} className="h-full w-full object-cover" />
          </div>
          {thumbnails.length > 0 && (
            <div className="grid grid-cols-2 gap-2 content-start">
              {thumbnails.slice(0, THUMBNAILS).map((url, index) => (
                <button key={url} type="button" onClick={() => setActiveImage(images.indexOf(url))}
                  aria-label={`Xem ảnh ${index + 2} của ${product.name}`}
                  className="relative aspect-square overflow-hidden rounded-xl bg-slate-100">
                  <img src={url} alt="" onError={placeholderOnError(product.taxonomy)} className="h-full w-full object-cover" />
                  {hiddenCount > 0 && index === THUMBNAILS - 1 && (
                    <span className="absolute inset-0 flex items-center justify-center bg-slate-900/50 text-lg font-bold text-white">+{hiddenCount}</span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="space-y-2">
        <TaxonomyBadge taxonomy={product.taxonomy} size="sm" />
        <h2 className="text-xl font-bold text-slate-900">{product.name}</h2>
        {product.aggregateRating && (
          <p className="text-sm text-slate-600">
            <span className="font-bold text-slate-800">{product.aggregateRating.score}/5</span>
            {product.aggregateRating.count > 0 && <span className="text-slate-500"> · {product.aggregateRating.count.toLocaleString('vi-VN')} đánh giá</span>}
          </p>
        )}
      </div>

      {state.status === 'error' && <LoadError onRetry={() => setAttempt((count) => count + 1)} />}
      {state.status === 'loading' && (
        <p role="status" className="flex items-center gap-2 text-sm text-slate-500"><Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />Đang tải chi tiết…</p>
      )}

      {description && (
        <div>
          <p className={`whitespace-pre-line text-sm leading-relaxed text-slate-700 ${longDescription && !expanded ? 'line-clamp-6' : ''}`}>{description}</p>
          {longDescription && (
            <button type="button" onClick={() => setExpanded((open) => !open)} className="mt-1 text-sm font-semibold text-blue-700 hover:underline">
              {expanded ? 'Thu gọn' : 'Xem thêm'}
            </button>
          )}
        </div>
      )}

      <div className="grid gap-4 border-t border-slate-100 pt-4 sm:grid-cols-2">
        <div className="flex items-start gap-2 text-sm">
          <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
          <div>
            <p className="font-semibold text-slate-800">Địa chỉ</p>
            <p className="text-slate-600">{product.address || product.destination}</p>
            {directions && (
              <a href={directions} target="_blank" rel="noopener noreferrer" className="mt-1 inline-flex items-center gap-1 font-semibold text-blue-700 hover:underline">
                <Navigation className="h-3.5 w-3.5" aria-hidden="true" />Chỉ đường
              </a>
            )}
          </div>
        </div>
        {openingHours && (
          <div className="flex items-start gap-2 text-sm">
            <Clock className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
            <div>
              <p className="font-semibold text-slate-800">Giờ mở cửa</p>
              <p className="text-slate-600">{openingHours}</p>
              {openingHoursDetail && <p className="text-xs text-slate-500">{openingHoursDetail}</p>}
            </div>
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
        {isFreeToVisit(product)
          ? <span className="text-sm font-bold text-emerald-700">Tham quan tự do</span>
          : <PriceTag price={product.unitPrice} taxonomy={product.taxonomy} size="md" />}
        <div className="flex items-center gap-2">
          {onAddToCart && (
            <button type="button" onClick={onAddToCart}
              className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-blue-600 px-4 text-sm font-bold text-white hover:bg-blue-700">
              <ShoppingCart className="h-4 w-4" aria-hidden="true" />Thêm vào giỏ
            </button>
          )}
          <a href={`/product/${encodeURIComponent(product.id)}`} target="_blank" rel="noopener noreferrer"
            className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-slate-200 px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50">
            Xem trang chi tiết<ExternalLink className="h-4 w-4" aria-hidden="true" />
          </a>
        </div>
      </div>
    </PanelFrame>
  );
}

function PanelFrame({ onClose, children }: { onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="relative h-full w-full overflow-y-auto bg-white">
      <button type="button" onClick={onClose} aria-label="Đóng chi tiết"
        className="absolute right-4 top-4 z-10 flex min-h-11 min-w-11 items-center justify-center rounded-full bg-white/90 text-slate-600 shadow-md hover:text-slate-900">
        <X className="h-5 w-5" aria-hidden="true" />
      </button>
      <div className="mx-auto max-w-4xl space-y-5 p-6 pt-16">{children}</div>
    </div>
  );
}

function LoadError({ onRetry }: { onRetry: () => void }) {
  return (
    <div role="alert" className="flex items-center gap-3 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
      Chưa tải được chi tiết sản phẩm.
      <button type="button" onClick={onRetry} className="inline-flex items-center gap-1 font-semibold underline">
        <RotateCcw className="h-4 w-4" aria-hidden="true" />Thử lại
      </button>
    </div>
  );
}
