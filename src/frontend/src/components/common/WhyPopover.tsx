import React from 'react';
import { BecauseItem, Strategy, Taxonomy } from '../../types/travel';
import { X, Luggage, ShoppingBag, Eye, Search, HelpCircle } from 'lucide-react';

interface WhyPopoverProps {
  isOpen: boolean;
  onClose: () => void;
  targetProductName: string;
  becauseItems: BecauseItem[];
  strategy?: Strategy;
  excludedVerticals?: Taxonomy[];
  destination?: string;
}

export const WhyPopover: React.FC<WhyPopoverProps> = ({
  isOpen,
  onClose,
  targetProductName,
  becauseItems,
  strategy = 'cross_vertical',
  excludedVerticals = ['hotel'],
  destination = 'Nha Trang'
}) => {
  if (!isOpen) return null;

  const renderEventIcon = (event: string) => {
    switch (event) {
      case 'purchase':
        return <Luggage className="w-4 h-4 text-emerald-600" />;
      case 'add_to_cart':
        return <ShoppingBag className="w-4 h-4 text-blue-600" />;
      case 'product_view':
        return <Eye className="w-4 h-4 text-amber-600" />;
      case 'search':
        return <Search className="w-4 h-4 text-purple-600" />;
      default:
        return <HelpCircle className="w-4 h-4 text-slate-500" />;
    }
  };

  const getVerb = (event: string) => {
    switch (event) {
      case 'purchase':
        return 'Bạn đã đặt';
      case 'add_to_cart':
        return 'Bạn đã chọn để đặt';
      case 'product_view':
        return 'Bạn đã xem';
      case 'search':
        return 'Bạn đã tìm';
      default:
        return 'Bạn đã quan tâm';
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

  const renderContributionDots = (contribution: number) => {
    if (contribution >= 0.5) {
      return (
        <div className="flex items-center gap-1.5 text-xs text-slate-700">
          <span className="text-blue-600 font-mono tracking-tighter">●●●○</span>
          <span className="font-medium text-blue-700">Nhiều</span>
        </div>
      );
    } else if (contribution >= 0.2) {
      return (
        <div className="flex items-center gap-1.5 text-xs text-slate-700">
          <span className="text-slate-600 font-mono tracking-tighter">●●○○</span>
          <span className="text-slate-600">Vừa</span>
        </div>
      );
    } else {
      return (
        <div className="flex items-center gap-1.5 text-xs text-slate-700">
          <span className="text-slate-400 font-mono tracking-tighter">●○○○</span>
          <span className="text-slate-500">Ít</span>
        </div>
      );
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs animate-in fade-in duration-150">
      <div 
        className="w-full max-w-lg bg-white rounded-xl shadow-2xl border border-slate-200 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 bg-slate-50">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">
              Vì sao bạn thấy gợi ý này?
            </h3>
            <p className="text-xs text-slate-500 mt-0.5 line-clamp-1">
              Gợi ý cho: {targetProductName}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-200/50 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-4 max-h-[70vh] overflow-y-auto">
          <p className="text-xs text-slate-600">
            Dựa trên hoạt động gần đây của bạn trên V-OTA:
          </p>

          <div className="space-y-3">
            {becauseItems.length > 0 ? (
              becauseItems.map((item, idx) => (
                <div 
                  key={idx} 
                  className="p-3 bg-slate-50 rounded-lg border border-slate-200/80 space-y-1.5"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <div className="p-1.5 bg-white rounded-md border border-slate-200 shadow-2xs">
                        {renderEventIcon(item.event)}
                      </div>
                      <span className="text-xs font-semibold text-slate-800 line-clamp-1">
                        {item.productName}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-xs text-slate-500 pl-8">
                    <span>{getVerb(item.event)} · {formatDaysAgo(item.daysAgo)}</span>
                    <div className="flex items-center gap-1.5">
                      <span>Mức độ ảnh hưởng:</span>
                      {renderContributionDots(item.contribution)}
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="p-3 bg-slate-50 rounded-lg text-xs text-slate-600">
                Gợi ý dựa trên các lựa chọn được đặt nhiều nhất của du khách tại {destination}.
              </div>
            )}
          </div>

          <div className="pt-3 border-t border-slate-100 text-xs text-slate-600 space-y-1.5 bg-blue-50/60 p-3 rounded-lg border border-blue-100">
            <p className="font-medium text-blue-900">Chiến lược đề xuất thông minh:</p>
            {strategy === 'cross_vertical' ? (
              <p className="text-blue-800 leading-relaxed">
                Chuyến {destination} của bạn đã có {excludedVerticals.includes('hotel') ? 'khách sạn' : 'dịch vụ'}, 
                hệ thống ưu tiên gợi ý vé máy bay và vé tham quan thay vì gợi ý trùng lặp khách sạn.
              </p>
            ) : strategy === 'dormant' ? (
              <p className="text-blue-800 leading-relaxed">
                Chào mừng bạn quay lại sau một thời gian! Gợi ý dựa trên điểm đến yêu thích trong chuyến đi trước đó của bạn.
              </p>
            ) : strategy === 'recent_views' ? (
              <p className="text-blue-800 leading-relaxed">
                Hệ thống nhận diện bạn đang quan tâm tới {destination} qua các lượt xem gần đây để đề xuất dịch vụ kết hợp.
              </p>
            ) : (
              <p className="text-blue-800 leading-relaxed">
                Các sản phẩm được chọn lọc theo mức độ phổ biến và đánh giá hài lòng cao tại các điểm đến nổi bật.
              </p>
            )}
            <p className="text-[11px] text-blue-700/80 pt-1">
              Gợi ý sẽ tự động thích ứng ngay khi bạn tìm kiếm hoặc đặt thêm dịch vụ.
            </p>
          </div>
        </div>

        <div className="px-5 py-3 border-t border-slate-100 bg-slate-50 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-300 rounded-md hover:bg-slate-100 transition-colors"
          >
            Đã hiểu
          </button>
        </div>
      </div>
    </div>
  );
};
