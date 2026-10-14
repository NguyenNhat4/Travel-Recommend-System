import React from 'react';
import Link from 'next/link';
import { Product, BecauseItem, Strategy, Taxonomy } from '../../types/travel';
import { PriceTag } from './PriceTag';
import { TaxonomyBadge } from './TaxonomyBadge';
import { useTravel } from '../../context/TravelContext';
import { flightProductHref } from '../../features/flights/results/flightHref';
import { placeholderImage } from '../../services/catalog';
import { MapPin, Star, ShoppingCart, ArrowRight, ExternalLink, Loader2, Check } from 'lucide-react';

interface ProductCardProps {
  product: Product;
  /** tile: thẻ vuông của carousel ở trang danh mục và Home; là liên kết thật để mở tab mới và điều hướng bằng bàn phím. */
  variant?: 'grid' | 'row' | 'compact' | 'tile';
  because?: BecauseItem[];
  strategy?: Strategy;
  excludedVerticals?: Taxonomy[];
  score?: number;
  rank?: number;
  onQuickAdd?: (product: Product) => void;
  className?: string;
  assistantNote?: string;
  isPersonalizedMatch?: boolean;
  openInNewTab?: boolean;
  /** Query string ngữ cảnh chuyến đi (ngày, số khách) nối vào `/product/{id}` để điền sẵn hộp đặt. */
  tripQuery?: string;
  /** compact: bấm thẻ gọi hàm này thay vì mở trang sản phẩm (thẻ trong lời diễn giải của trợ lý mở panel chi tiết). */
  onSelect?: (product: Product) => void;
  /** compact: thay `PriceTag`, ví dụ "Tham quan tự do" cho điểm tham quan không bán vé. */
  priceLabel?: string;
  /** compact: hiện điểm đánh giá (nếu có) và địa chỉ thay cho điểm đến. */
  showRatingAndAddress?: boolean;
  quickAddState?: 'adding' | 'added';
  /**
   * tile: gắn nhãn loại ở góc ảnh. Chỉ bật ở kệ trộn nhiều loại (product.md §4.0; ngoại lệ của quyết định bỏ nhãn
   * ngày 2026-10-01); các biến thể khác bỏ qua prop này.
   */
  showTaxonomy?: boolean;
}

export const ProductCard: React.FC<ProductCardProps> = ({
  product,
  variant = 'grid',
  because,
  strategy,
  excludedVerticals,
  score,
  rank,
  onQuickAdd,
  className = '',
  assistantNote,
  isPersonalizedMatch = false,
  openInNewTab = false,
  tripQuery,
  onSelect,
  priceLabel,
  showRatingAndAddress = false,
  quickAddState,
  showTaxonomy = false,
}) => {
  const { navigate, debugMode, recordEvent } = useTravel();

  const href = (product.taxonomy === 'flight' ? flightProductHref(product, tripQuery) : null)
    ?? `/product/${product.id}${tripQuery ? `?${tripQuery}` : ''}`;

  const handleCardClick = (e?: React.MouseEvent) => {
    recordEvent('product_view', product);
    if (openInNewTab) {
      if (e) {
        e.preventDefault();
      }
      window.open(href, '_blank', 'noopener,noreferrer');
      return;
    }
    navigate(href);
  };

  // ==================== TILE VARIANT (LANDING / HOME CAROUSEL) ====================
  if (variant === 'tile') {
    return (
      <Link
        href={href}
        target={openInNewTab ? '_blank' : undefined}
        rel={openInNewTab ? 'noopener noreferrer' : undefined}
        onClick={() => recordEvent('product_view', product)}
        className={`group flex min-w-0 flex-col gap-3 rounded-3xl focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand-600 ${className}`}
      >
        <div className="relative aspect-square w-full overflow-hidden rounded-3xl bg-slate-100">
          <img
            src={product.imageUrl}
            alt={product.name}
            loading="lazy"
            decoding="async"
            referrerPolicy="no-referrer"
            className={`h-full w-full object-cover transition-transform duration-500 group-hover:scale-105 ${!product.available ? 'grayscale' : ''}`}
          />
          {showTaxonomy && (
            // Chữ nhãn nằm trong tên truy cập của liên kết (không aria-hidden): trình đọc màn hình cũng cần biết loại,
            // vì có combo tên mở đầu bằng "Vé máy bay khứ hồi … +".
            <div className="absolute left-3 top-3">
              <TaxonomyBadge taxonomy={product.taxonomy} size="sm" className="shadow-sm" />
            </div>
          )}
          {!product.available && (
            <div className="absolute inset-0 flex items-center justify-center bg-slate-900/55 text-xs font-bold uppercase tracking-wider text-white">
              Tạm hết chỗ
            </div>
          )}
        </div>
        <div className="flex min-w-0 flex-col gap-1 px-1">
          <h3 className="line-clamp-2 text-base font-bold leading-snug text-slate-900 transition-colors group-hover:text-brand-600">
            {product.name}
          </h3>
          <p className="flex items-center gap-1 text-sm text-slate-500">
            <MapPin className="h-3.5 w-3.5 shrink-0 text-slate-400" aria-hidden="true" />
            <span className="truncate">{product.destination}</span>
          </p>
          {product.aggregateRating && (
            <p className="text-xs text-slate-600">
              <span className="font-bold text-slate-800">★ {product.aggregateRating.score}</span>
              {product.aggregateRating.count > 0 && (
                <span className="text-slate-500"> · {product.aggregateRating.count.toLocaleString('vi-VN')} đánh giá</span>
              )}
            </p>
          )}
          <PriceTag price={product.unitPrice} taxonomy={product.taxonomy} hasPrefixFrom size="md" />
        </div>
      </Link>
    );
  }

  // ==================== COMPACT VARIANT ====================
  if (variant === 'compact') {
    // Có `onSelect`: cả thẻ bấm được bằng chuột; tên là nút để dùng bàn phím/trình đọc màn hình. Nút không có handler
    // riêng, click của nó nổi lên thẻ nên chỉ gọi `onSelect` một lần, và nút "Thêm" vẫn không lồng trong một nút khác.
    const handleCompactClick = onSelect ? () => onSelect(product) : handleCardClick;
    return (
      <div
        onClick={handleCompactClick}
        className={`flex items-center justify-between p-3 bg-white rounded-lg border border-slate-200 cursor-pointer ${className} ${!product.available ? 'opacity-60 bg-slate-50' : ''}`}
      >
        <div className="flex items-center gap-3 min-w-0">
          <div className="relative w-16 h-16 rounded-md overflow-hidden bg-slate-100 shrink-0">
            <img
              src={product.imageUrl}
              alt={product.name}
              referrerPolicy="no-referrer"
              onError={(event) => {
                const fallback = placeholderImage(product.taxonomy);
                if (!event.currentTarget.src.endsWith(fallback)) event.currentTarget.src = fallback;
              }}
              className="w-full h-full object-cover"
            />
            {!product.available && (
              <div className="absolute inset-0 bg-slate-900/60 flex items-center justify-center text-[10px] font-semibold text-white">
                Hết chỗ
              </div>
            )}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5 flex-wrap mb-0.5">
              {isPersonalizedMatch && (
                <span className="text-[10px] font-medium text-brand-700 bg-brand-50 px-1.5 py-0.5 rounded border border-brand-200">
                  ✨ Hợp với bạn
                </span>
              )}
              {/* `showRatingAndAddress` có dòng "x/5 · n đánh giá" dưới tên rồi, không hiện điểm lần thứ hai. */}
              {product.aggregateRating && !showRatingAndAddress && (
                <span className="flex items-center text-[11px] font-medium text-amber-600">
                  <Star className="w-3 h-3 fill-amber-400 text-amber-400 mr-0.5" />
                  {product.aggregateRating.score}
                </span>
              )}
            </div>
            <h4 className="font-sans text-xs font-semibold text-slate-900 line-clamp-1">
              {onSelect ? (
                <button type="button" aria-label={`Xem chi tiết ${product.name}`} className="text-left hover:text-brand-700">
                  {product.name}
                </button>
              ) : product.name}
            </h4>
            {/* Điểm đánh giá (khác hạng sao `starRating`, nên không dùng biểu tượng sao) */}
            {showRatingAndAddress && product.aggregateRating && (
              <p className="text-[11px] text-slate-600">
                <span className="font-semibold text-slate-800">{product.aggregateRating.score}/5</span>
                {product.aggregateRating.count > 0 && (
                  <span className="text-slate-500"> · {product.aggregateRating.count.toLocaleString('vi-VN')} đánh giá</span>
                )}
              </p>
            )}
            <div className="flex items-center gap-2 mt-0.5 min-w-0">
              {priceLabel
                ? <span className="shrink-0 text-[11px] font-bold text-emerald-700">{priceLabel}</span>
                : <PriceTag price={product.unitPrice} taxonomy={product.taxonomy} size="sm" />}
              <span className="min-w-0 text-[11px] text-slate-400 flex items-center gap-0.5">
                <MapPin className="w-3 h-3 shrink-0" />
                <span className="truncate">{showRatingAndAddress ? product.address || product.destination : product.destination}</span>
              </span>
            </div>
            {assistantNote && (
              <p className="text-[11px] text-slate-500 italic mt-1 line-clamp-1">
                💬 &ldquo;{assistantNote}&rdquo;
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0 ml-3">
          {onQuickAdd && product.available && (
            <button
              disabled={Boolean(quickAddState)}
              aria-busy={quickAddState === 'adding'}
              aria-label={quickAddState ? undefined : `Thêm ${product.name} vào giỏ`}
              onClick={(e) => {
                e.stopPropagation();
                onQuickAdd(product);
              }}
              className={`inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-md border transition-colors disabled:cursor-default ${quickAddState === 'added' ? 'text-emerald-700 bg-emerald-50 border-emerald-200' : 'text-brand-700 bg-brand-50 hover:bg-brand-100 border-brand-200'}`}
            >
              {quickAddState === 'adding' ? <Loader2 className="w-3.5 h-3.5 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                : quickAddState === 'added' ? <Check className="w-3.5 h-3.5" aria-hidden="true" /> : <ShoppingCart className="w-3.5 h-3.5" aria-hidden="true" />}
              <span aria-live="polite" className="whitespace-nowrap">{quickAddState === 'adding' ? 'Đang thêm…' : quickAddState === 'added' ? 'Đã thêm vào giỏ' : 'Thêm vào giỏ'}</span>
            </button>
          )}
          {openInNewTab && (
            <span title="Mở tab mới" className="text-slate-400 p-0.5">
              <ExternalLink className="w-3.5 h-3.5" />
            </span>
          )}
        </div>
      </div>
    );
  }

  // ==================== ROW VARIANT (SEARCH) ====================
  if (variant === 'row') {
    return (
      <div 
        onClick={handleCardClick}
        className={`flex flex-col md:flex-row md:h-60 bg-white rounded-xl border border-slate-200 overflow-hidden cursor-pointer ${className} ${!product.available ? 'opacity-65' : ''}`}
      >
        {/* Khung ảnh có kích thước cố định (16:10 trên điện thoại, cao bằng thẻ trên màn hình rộng): ảnh phủ kín bất kể tỉ lệ gốc,
            nên mọi thẻ trong danh sách cao bằng nhau; thiếu hoặc lỗi ảnh thì dùng ảnh dự phòng theo loại. */}
        <div className="relative w-full md:w-64 aspect-16/10 md:aspect-auto md:h-full overflow-hidden bg-slate-100 shrink-0">
          <img
            src={product.imageUrl || placeholderImage(product.taxonomy)}
            alt={product.name}
            loading="lazy"
            decoding="async"
            referrerPolicy="no-referrer"
            onError={(event) => {
              const fallback = placeholderImage(product.taxonomy);
              if (!event.currentTarget.src.endsWith(fallback)) event.currentTarget.src = fallback;
            }}
            className="absolute inset-0 w-full h-full object-cover"
          />
          {!product.available && (
            <div className="absolute inset-0 bg-slate-900/60 flex items-center justify-center text-xs font-bold text-white uppercase tracking-wider">
              Tạm hết chỗ
            </div>
          )}
          {debugMode && score !== undefined && (
            <div className="absolute bottom-2 left-2 px-1.5 py-0.5 bg-slate-900/80 text-[10px] font-mono text-emerald-300 rounded backdrop-blur-xs">
              Rank #{rank} · Rel {score}
            </div>
          )}
        </div>

        <div className="flex-1 min-w-0 p-5 flex flex-col justify-between gap-3 overflow-hidden">
          <div className="min-w-0">
            <div className="flex items-center justify-between gap-2 mb-1">
              <span className="inline-flex items-center gap-1 text-xs text-slate-500 font-medium">
                <MapPin className="w-3.5 h-3.5 text-slate-400" />
                {product.destination}
              </span>
              {product.aggregateRating && (
                <div className="flex items-center text-amber-500 text-xs font-semibold">
                  <Star className="w-3.5 h-3.5 fill-amber-400 text-amber-400 mr-1" />
                  {product.aggregateRating.score}
                  {product.aggregateRating.count > 0 && (
                    <span className="ml-1 font-normal text-slate-500">({product.aggregateRating.count.toLocaleString('vi-VN')} đánh giá)</span>
                  )}
                </div>
              )}
            </div>

            <h3 className="text-base font-bold text-slate-900 line-clamp-1 mb-1.5">
              {product.name}
            </h3>

            <p className="text-xs text-slate-600 line-clamp-2 leading-relaxed min-h-10 mb-3">
              {product.description}
            </p>

            {/* Attribute tag chips: một hàng cao cố định, nhiều tag thì cắt bớt thay vì làm thẻ cao thêm */}
            <div className="flex flex-nowrap gap-1.5 h-[22px] overflow-hidden whitespace-nowrap">
              {product.attributes.oceanView && (
                <span className="text-[11px] font-medium bg-brand-50 text-brand-700 px-2 py-0.5 rounded border border-brand-100">
                  Hướng biển
                </span>
              )}
              {product.attributes.familyFriendly && (
                <span className="text-[11px] font-medium bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded border border-emerald-100">
                  Phù hợp gia đình
                </span>
              )}
              {product.attributes.pool && (
                <span className="text-[11px] font-medium bg-cyan-50 text-cyan-700 px-2 py-0.5 rounded border border-cyan-100">
                  Hồ bơi lớn
                </span>
              )}
              {product.attributes.cableCar && (
                <span className="text-[11px] font-medium bg-amber-50 text-amber-700 px-2 py-0.5 rounded border border-amber-100">
                  Cáp treo
                </span>
              )}
              {product.attributes.airline && (
                <span className="text-[11px] font-medium bg-brand-50 text-brand-700 px-2 py-0.5 rounded border border-brand-100">
                  {product.attributes.airline}
                </span>
              )}
            </div>
          </div>

          <div className="flex items-end justify-between pt-3 min-h-[54px] border-t border-slate-100">
            <PriceTag price={product.unitPrice} taxonomy={product.taxonomy} hasPrefixFrom showTaxesIncluded size="md" />
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1 text-xs font-semibold text-brand-700">
                Xem chi tiết
                <ArrowRight className="w-3.5 h-3.5" />
              </span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ==================== GRID VARIANT (HOME / CAROUSEL) ====================
  return (
    <div 
      onClick={handleCardClick}
      className={`flex flex-col bg-white rounded-xl border border-slate-200 overflow-hidden cursor-pointer ${className} ${!product.available ? 'opacity-60' : ''}`}
    >
      <div className="relative aspect-16/10 overflow-hidden bg-slate-100">
        <img 
          src={product.imageUrl} 
          alt={product.name}
          referrerPolicy="no-referrer"
          className="w-full h-full object-cover"
        />
        {!product.available && (
          <div className="absolute inset-0 bg-slate-900/60 flex items-center justify-center text-xs font-bold text-white uppercase tracking-wider">
            Tạm hết chỗ
          </div>
        )}
        {debugMode && score !== undefined && (
          <div className="absolute bottom-2 left-2 px-1.5 py-0.5 bg-slate-900/85 text-[10px] font-mono text-emerald-300 rounded backdrop-blur-xs">
            #{rank} · Score: {score}
          </div>
        )}
      </div>

      <div className="p-4 flex-1 flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
            <span className="flex items-center gap-1 font-medium">
              <MapPin className="w-3.5 h-3.5 text-slate-400" />
              {product.destination}
            </span>
            {product.aggregateRating && (
              <span className="font-semibold text-slate-700">
                ★ {product.aggregateRating.score} ({product.aggregateRating.count})
              </span>
            )}
          </div>

          <h3 className="text-sm font-bold text-slate-900 line-clamp-2 leading-snug mb-2">
            {product.name}
          </h3>
        </div>

        <div className="pt-2 border-t border-slate-100">
          <PriceTag price={product.unitPrice} taxonomy={product.taxonomy} hasPrefixFrom size="md" />
        </div>
      </div>
    </div>
  );
};
