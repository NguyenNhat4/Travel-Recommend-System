import React, { useState } from 'react';
import { BecauseItem, Strategy, Taxonomy } from '../../types/travel';
import { Luggage, ShoppingBag, Eye, Search, HelpCircle } from 'lucide-react';
import { WhyPopover } from './WhyPopover';

interface BecauseLineProps {
  because?: BecauseItem[];
  productName: string;
  strategy?: Strategy;
  excludedVerticals?: Taxonomy[];
  destination?: string;
  className?: string;
}

export const BecauseLine: React.FC<BecauseLineProps> = ({
  because = [],
  productName,
  strategy = 'cross_vertical',
  excludedVerticals,
  destination,
  className = ''
}) => {
  const [showPopover, setShowPopover] = useState(false);

  if (!because || because.length === 0) return null;

  const primary = because[0];
  const countOther = because.length - 1;

  const renderEventIcon = (event: string) => {
    switch (event) {
      case 'purchase':
        return <Luggage className="w-3.5 h-3.5 text-emerald-600 shrink-0" />;
      case 'add_to_cart':
        return <ShoppingBag className="w-3.5 h-3.5 text-blue-600 shrink-0" />;
      case 'product_view':
        return <Eye className="w-3.5 h-3.5 text-amber-600 shrink-0" />;
      case 'search':
        return <Search className="w-3.5 h-3.5 text-purple-600 shrink-0" />;
      default:
        return <HelpCircle className="w-3.5 h-3.5 text-slate-500 shrink-0" />;
    }
  };

  const getVerb = (event: string) => {
    switch (event) {
      case 'purchase':
        return 'đã đặt';
      case 'add_to_cart':
        return 'đã thêm vào giỏ';
      case 'product_view':
        return 'đã xem';
      case 'search':
        return 'đã tìm';
      default:
        return 'đã quan tâm';
    }
  };

  const formatDaysAgo = (days: number) => {
    if (days === 0) return 'hôm nay';
    if (days === 1) return 'hôm qua';
    if (days < 7) return `${days} ngày trước`;
    if (days < 30) return `${Math.floor(days / 7)} tuần trước`;
    if (days < 365) return `${Math.floor(days / 30)} tháng trước`;
    return 'hơn 1 năm trước';
  };

  // Max 32 chars for product name
  const truncatedSource = primary.productName.length > 32 
    ? primary.productName.slice(0, 32) + '…' 
    : primary.productName;

  return (
    <>
      <div 
        className={`inline-flex items-center gap-1.5 text-xs text-slate-600 hover:text-blue-700 cursor-pointer transition-colors py-0.5 group ${className}`}
        onClick={(e) => {
          e.stopPropagation();
          setShowPopover(true);
        }}
        title={`Bấm để xem lý do vì sao gợi ý sản phẩm này`}
      >
        {renderEventIcon(primary.event)}
        <span className="truncate">
          Vì bạn {getVerb(primary.event)} <strong className="font-medium text-slate-800 group-hover:text-blue-800">{truncatedSource}</strong> · {formatDaysAgo(primary.daysAgo)}
          {countOther > 0 && (
            <span className="text-slate-400 font-normal ml-1">và {countOther} lý do khác</span>
          )}
        </span>
        <span className="text-[10px] text-blue-600 underline font-medium ml-0.5 shrink-0 opacity-80 group-hover:opacity-100">
          [Vì sao?]
        </span>
      </div>

      <WhyPopover
        isOpen={showPopover}
        onClose={() => setShowPopover(false)}
        targetProductName={productName}
        becauseItems={because}
        strategy={strategy}
        excludedVerticals={excludedVerticals}
        destination={destination}
      />
    </>
  );
};
