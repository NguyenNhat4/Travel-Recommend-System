import React from 'react';
import { 
  Users, Sparkles, Bookmark, BookmarkCheck, 
  ShoppingCart, Share2, MessageSquare, X, Heart
} from 'lucide-react';
import { GroundedPlan } from '../../types/travel';

interface SharedTripWelcomeBannerProps {
  plan: GroundedPlan;
  senderName?: string;
  note?: string;
  isSaved: boolean;
  onSave: () => void;
  onAddAllToCart: () => void;
  onShareAgain: () => void;
  onDismiss: () => void;
}

export const SharedTripWelcomeBanner: React.FC<SharedTripWelcomeBannerProps> = ({
  plan,
  senderName = 'Người thân',
  note,
  isSaved,
  onSave,
  onAddAllToCart,
  onShareAgain,
  onDismiss,
}) => {
  return (
    <div className="p-4 bg-gradient-to-r from-amber-500/10 via-blue-500/10 to-indigo-500/10 border-2 border-indigo-200/80 rounded-2xl shadow-xs space-y-3 relative animate-in fade-in slide-in-from-top-3 duration-300">
      <button
        onClick={onDismiss}
        className="absolute top-3 right-3 p-1 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-white/60 transition-colors"
        title="Đóng thông báo"
      >
        <X className="w-4 h-4" />
      </button>

      <div className="flex items-start gap-3 pr-8">
        <div className="w-9 h-9 rounded-xl bg-indigo-600 text-white flex items-center justify-center shrink-0 shadow-xs">
          <Users className="w-5 h-5" />
        </div>

        <div className="space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-indigo-100 text-indigo-800 text-[10px] font-bold">
              <Sparkles className="w-3 h-3" />
              Lịch trình được chia sẻ
            </span>
            <span className="text-xs text-slate-500">
              Gửi bởi: <strong className="text-slate-800">{senderName}</strong>
            </span>
          </div>

          <h3 className="text-sm sm:text-base font-black text-slate-900 leading-snug">
            Khám phá chuyến đi: {plan.title}
          </h3>

          {note && (
            <div className="p-2.5 bg-white/80 rounded-xl border border-indigo-100 text-xs text-slate-700 italic flex items-start gap-2">
              <Heart className="w-3.5 h-3.5 text-rose-500 shrink-0 mt-0.5" />
              <span>"{note}"</span>
            </div>
          )}

          <p className="text-xs text-slate-600">
            Lịch trình đã được nạp đầy đủ {plan.days.length} ngày, các điểm tham quan trên bản đồ và {plan.bookableProductsCount} dịch vụ đặt được trực tiếp.
          </p>
        </div>
      </div>

      {/* Action shortcuts */}
      <div className="flex items-center gap-2 pt-1 flex-wrap border-t border-indigo-100/80">
        <button
          type="button"
          onClick={onSave}
          className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-colors flex items-center gap-1.5 shadow-2xs border ${
            isSaved
              ? 'bg-emerald-100 text-emerald-800 border-emerald-300'
              : 'bg-white hover:bg-slate-50 text-slate-700 border-slate-300'
          }`}
        >
          {isSaved ? (
            <>
              <BookmarkCheck className="w-3.5 h-3.5 text-emerald-600" />
              <span>Đã lưu vào danh sách của bạn</span>
            </>
          ) : (
            <>
              <Bookmark className="w-3.5 h-3.5 text-slate-400" />
              <span>Lưu chuyến đi này</span>
            </>
          )}
        </button>

        <button
          type="button"
          onClick={onAddAllToCart}
          className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold transition-colors flex items-center gap-1.5 shadow-2xs"
        >
          <ShoppingCart className="w-3.5 h-3.5" />
          <span>Thêm {plan.bookableProductsCount} dịch vụ vào giỏ</span>
        </button>

        <button
          type="button"
          onClick={onShareAgain}
          className="px-3 py-1.5 bg-white hover:bg-slate-50 text-indigo-700 border border-indigo-200 rounded-xl text-xs font-semibold transition-colors flex items-center gap-1.5 shadow-2xs"
        >
          <Share2 className="w-3.5 h-3.5 text-indigo-600" />
          <span>Chia sẻ tiếp</span>
        </button>
      </div>
    </div>
  );
};
