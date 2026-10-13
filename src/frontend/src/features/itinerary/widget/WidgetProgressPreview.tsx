import React from 'react';
import type { components } from '../../../types/api.gen';
import { kindLabel } from './widgetProgressLabels';
export function WidgetProgressPreview({products,onOpen}:{products:components['schemas']['ProductSummary'][];onOpen:(id:string)=>void}) {
  return <section aria-label="Sản phẩm đã chọn" className="mt-3 min-w-0 space-y-2">
    <p className="text-xs font-medium text-slate-600">Đã chọn xong, đang viết lời tư vấn</p>
    <div className="grid grid-cols-2 gap-2">{products.map((p) => <button type="button" key={p.productId} onClick={() => onOpen(p.productId)} className="min-w-0 rounded-xl border border-slate-200 bg-white p-2 text-left hover:border-ai-300 focus-visible:outline-2 focus-visible:outline-ai-600">
      <span className="block text-[11px] text-slate-500">{kindLabel[p.taxonomy]}</span><span className="block break-words text-xs font-semibold leading-5 text-slate-800">{p.name}</span>
      {p.unitPrice!==null && <span className="text-xs text-slate-600">{p.unitPrice.toLocaleString('vi-VN')} ₫</span>}
    </button>)}</div>
  </section>;
}
