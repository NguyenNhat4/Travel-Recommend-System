import React from 'react';
import { Check, Loader2, Sparkles, Star } from 'lucide-react';
import type { Product } from '../../../types/travel';
import type { CartAddState } from './useWidgetCart';
import { placeholderOnError } from './widgetVisuals';

export function comboBadge(product: Product, peers: Product[]): string {
  const original = product.attributes.originalPrice;
  if (typeof original === 'number' && product.unitPrice != null && original > product.unitPrice) {
    return `Giảm ${Math.round((original - product.unitPrice) / original * 100)}%`;
  }
  const review = product.aggregateRating;
  if (review && review.count >= 50 && review.count === Math.max(...peers.map((peer) => peer.aggregateRating?.count ?? 0))) return 'Được yêu thích nhất';
  if (review && review.score >= 4.5) return 'Đánh giá cao';
  return 'Combo trọn gói';
}

export function WidgetComboCard({ product, peers, onOpen, onBook, onAdd, addState }: {
  product: Product; peers: Product[]; onOpen: () => void;
  onBook?: () => void; onAdd?: () => void; addState?: CartAddState;
}) {
  const pending = addState === 'adding';
  const added = addState === 'added';
  return <article className="overflow-hidden rounded-2xl border border-amber-200 bg-amber-50/50 shadow-sm">
    <button type="button" onClick={onOpen} className="group block w-full text-left focus-visible:outline-2 focus-visible:outline-amber-600">
      <div className="relative aspect-[16/8] overflow-hidden bg-slate-100">
        <img src={product.imageUrl} alt={product.name} onError={placeholderOnError('combo')} className="h-full w-full object-cover transition-transform group-hover:scale-105 motion-reduce:transition-none" />
        <span className="absolute left-3 top-3 inline-flex items-center gap-1 rounded-full bg-amber-100 px-3 py-1 text-xs font-bold text-amber-950 shadow-sm"><Sparkles className="h-3.5 w-3.5" />{comboBadge(product, peers)}</span>
      </div>
      <div className="space-y-2 p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Gói kết hợp · {product.destination}</p>
        <h4 className="text-base font-bold leading-snug text-slate-900">{product.name}</h4>
        {product.aggregateRating && <p className="flex items-center gap-1 text-xs text-slate-600"><Star className="h-3.5 w-3.5 fill-amber-400 text-amber-500" />{product.aggregateRating.score}/5 · {product.aggregateRating.count} lượt đánh giá</p>}
        <p className="text-lg font-bold text-amber-900">{product.unitPrice != null ? `${new Intl.NumberFormat('vi-VN').format(product.unitPrice)} ₫` : 'Chưa có giá'}<span className="text-xs font-normal text-slate-500"> /gói</span></p>
      </div>
    </button>
    {(onBook || onAdd) && <div className="space-y-2 px-4 pb-4">
      {onBook && <button type="button" onClick={onBook} className="min-h-11 w-full rounded-xl bg-amber-700 px-4 font-semibold text-white hover:bg-amber-800">Đặt ngay</button>}
      {onAdd && <button type="button" onClick={onAdd} disabled={pending || added} className="flex min-h-11 w-full items-center justify-center gap-2 rounded-xl border border-amber-300 bg-white px-4 text-sm font-semibold text-amber-900 disabled:opacity-60">
        {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : added ? <Check className="h-4 w-4" /> : null}{pending ? 'Đang thêm…' : added ? 'Đã thêm vào giỏ' : 'Thêm vào giỏ'}
      </button>}
    </div>}
  </article>;
}
