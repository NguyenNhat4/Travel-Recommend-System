import React from 'react';
import { Product, BecauseItem, Strategy, Taxonomy } from '../../types/travel';
import { TaxonomyBadge } from './TaxonomyBadge';
import { PriceTag } from './PriceTag';
import { useTravel } from '../../context/TravelContext';
import { MapPin, Star, Plus, ArrowRight, ExternalLink } from 'lucide-react';

interface ProductCardProps {
  product: Product;
  variant?: 'grid' | 'row' | 'compact';
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
  hideTaxonomyBadge?: boolean;
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
  hideTaxonomyBadge = false
}) => {
  const { navigate, debugMode, recordEvent } = useTravel();

  const handleCardClick = (e?: React.MouseEvent) => {
    recordEvent('product_view', product);
    if (openInNewTab) {
      if (e) {
        e.preventDefault();
      }
      window.open(`/product/${product.id}`, '_blank', 'noopener,noreferrer');
      return;
    }
    navigate(`/product/${product.id}`);
  };

  // ==================== COMPACT VARIANT ====================
  if (variant === 'compact') {
    return (
      <div 
        onClick={handleCardClick}
        className={`flex items-center justify-between p-3 bg-white rounded-lg border border-slate-200 cursor-pointer ${className} ${!product.available ? 'opacity-60 bg-slate-50' : ''}`}
      >
        <div className="flex items-center gap-3 min-w-0">
          <div className="relative w-16 h-16 rounded-md overflow-hidden bg-slate-100 shrink-0">
            <img 
              src={product.imageUrl} 
              alt={product.name}
              referrerPolicy="no-referrer"
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
              {!hideTaxonomyBadge && <TaxonomyBadge taxonomy={product.taxonomy} size="sm" />}
              {isPersonalizedMatch && (
                <span className="text-[10px] font-medium text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200">
                  ✨ Hợp với bạn
                </span>
              )}
              {product.attributes.starRating && (
                <span className="flex items-center text-[11px] font-medium text-amber-600">
                  <Star className="w-3 h-3 fill-amber-400 text-amber-400 mr-0.5" />
                  {product.attributes.starRating}★
                </span>
              )}
            </div>
            <h4 className="text-xs font-semibold text-slate-900 line-clamp-1">
              {product.name}
            </h4>
            <div className="flex items-center gap-2 mt-0.5">
              <PriceTag price={product.unitPrice} taxonomy={product.taxonomy} size="sm" />
              <span className="text-[11px] text-slate-400 flex items-center gap-0.5">
                <MapPin className="w-3 h-3" />
                {product.destination}
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
              onClick={(e) => {
                e.stopPropagation();
                onQuickAdd(product);
              }}
              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-blue-700 bg-blue-50 hover:bg-blue-100 rounded-md border border-blue-200 transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Thêm</span>
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
        className={`flex flex-col md:flex-row bg-white rounded-xl border border-slate-200 overflow-hidden cursor-pointer ${className} ${!product.available ? 'opacity-65' : ''}`}
      >
        <div className="relative w-full md:w-64 h-48 md:h-auto overflow-hidden bg-slate-100 shrink-0">
          <img 
            src={product.imageUrl} 
            alt={product.name}
            referrerPolicy="no-referrer"
            className="w-full h-full object-cover"
          />
          {!hideTaxonomyBadge && (
            <div className="absolute top-2.5 left-2.5">
              <TaxonomyBadge taxonomy={product.taxonomy} />
            </div>
          )}
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

        <div className="flex-1 p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between gap-2 mb-1">
              <span className="inline-flex items-center gap-1 text-xs text-slate-500 font-medium">
                <MapPin className="w-3.5 h-3.5 text-slate-400" />
                {product.destination}
              </span>
              {product.attributes.starRating && (
                <div className="flex items-center text-amber-500 text-xs font-semibold">
                  <Star className="w-3.5 h-3.5 fill-amber-400 text-amber-400 mr-1" />
                  {product.attributes.starRating}★ Khách sạn 5 sao
                </div>
              )}
            </div>

            <h3 className="text-base font-bold text-slate-900 line-clamp-1 mb-1.5">
              {product.name}
            </h3>

            <p className="text-xs text-slate-600 line-clamp-2 leading-relaxed mb-3">
              {product.description}
            </p>

            {/* Attribute tag chips */}
            <div className="flex flex-wrap gap-1.5 mb-3">
              {product.attributes.oceanView && (
                <span className="text-[11px] font-medium bg-blue-50 text-blue-700 px-2 py-0.5 rounded border border-blue-100">
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
                <span className="text-[11px] font-medium bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded border border-indigo-100">
                  {product.attributes.airline}
                </span>
              )}
            </div>
          </div>

          <div className="flex items-end justify-between pt-3 border-t border-slate-100">
            <PriceTag price={product.unitPrice} taxonomy={product.taxonomy} hasPrefixFrom showTaxesIncluded size="md" />
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1 text-xs font-semibold text-blue-700">
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
        {!hideTaxonomyBadge && (
          <div className="absolute top-2.5 left-2.5">
            <TaxonomyBadge taxonomy={product.taxonomy} />
          </div>
        )}
        {product.attributes.starRating && (
          <div className="absolute top-2.5 right-2.5 px-2 py-0.5 rounded bg-slate-900/70 text-amber-300 text-[11px] font-semibold backdrop-blur-xs flex items-center gap-0.5">
            <Star className="w-3 h-3 fill-amber-300 text-amber-300" />
            {product.attributes.starRating}★
          </div>
        )}
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
