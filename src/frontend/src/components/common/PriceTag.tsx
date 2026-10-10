import React from 'react';
import { Taxonomy } from '../../types/travel';

interface PriceTagProps {
  /** null = chưa có giá (không phải miễn phí): hiển thị "Chưa có giá", không tiền tố/hậu tố. */
  price: number | null;
  taxonomy?: Taxonomy;
  hasPrefixFrom?: boolean;
  showTaxesIncluded?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export const PriceTag: React.FC<PriceTagProps> = ({
  price,
  taxonomy,
  hasPrefixFrom = false,
  showTaxesIncluded = false,
  size = 'md',
  className = ''
}) => {
  if (price == null) {
    return <span className={`text-sm font-medium text-slate-500 ${className}`}>Chưa có giá</span>;
  }
  const formatted = new Intl.NumberFormat('vi-VN').format(price) + ' ₫';

  let suffix = '';
  if (taxonomy === 'hotel') suffix = '/ đêm';
  else if (taxonomy === 'flight' || taxonomy === 'attraction') suffix = '/ khách';
  else if (taxonomy === 'golf') suffix = '/ lượt';
  else if (taxonomy === 'combo') suffix = '/ gói';

  const sizeClasses = {
    sm: 'text-sm font-semibold',
    md: 'text-base font-bold',
    lg: 'text-xl font-bold'
  };

  return (
    <div className={`inline-flex flex-col ${className}`}>
      <div className="inline-flex items-baseline gap-1 text-slate-900">
        {hasPrefixFrom && <span className="text-xs font-normal text-slate-500">Từ</span>}
        <span className={`${sizeClasses[size]} tracking-tight text-slate-900`}>{formatted}</span>
        {suffix && <span className="text-xs font-normal text-slate-500">{suffix}</span>}
      </div>
      {showTaxesIncluded && (
        <span className="text-[11px] text-slate-400 font-normal">Đã gồm thuế & phí</span>
      )}
    </div>
  );
};
