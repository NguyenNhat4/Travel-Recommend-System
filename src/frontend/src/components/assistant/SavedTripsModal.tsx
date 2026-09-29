import React from 'react';
import { SavedTrip, GroundedPlan } from '../../types/travel';
import { Bookmark, Calendar, MapPin, Trash2, ArrowRight, X, Clock, Users, Sparkles, Check, Share2 } from 'lucide-react';

interface SavedTripsModalProps {
  isOpen: boolean;
  onClose: () => void;
  savedTrips: SavedTrip[];
  onSelectTrip: (plan: GroundedPlan) => void;
  onDeleteTrip: (id: string) => void;
  onShareTrip?: (plan: GroundedPlan) => void;
  currentPlanTitle?: string;
}

export const SavedTripsModal: React.FC<SavedTripsModalProps> = ({
  isOpen,
  onClose,
  savedTrips,
  onSelectTrip,
  onDeleteTrip,
  onShareTrip,
  currentPlanTitle
}) => {
  if (!isOpen) return null;

  const formatDate = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString('vi-VN', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="fixed inset-0 z-[1200] flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-200">
      <div 
        className="bg-white w-full max-w-2xl rounded-2xl shadow-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[85vh] animate-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="p-4 sm:p-5 border-b border-slate-100 flex items-center justify-between bg-slate-50/80">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-blue-100 text-blue-600 flex items-center justify-center font-bold">
              <Bookmark className="w-5 h-5 fill-blue-600/20" />
            </div>
            <div>
              <h3 className="text-base sm:text-lg font-black text-slate-900 tracking-tight">
                Chuyến Đi Đã Lưu
              </h3>
              <p className="text-xs text-slate-500">
                {savedTrips.length} lịch trình được lưu trong bộ nhớ cục bộ (Local Storage)
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-xl transition-colors"
            title="Đóng"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Content / List */}
        <div className="p-4 sm:p-5 overflow-y-auto flex-1 space-y-3">
          {savedTrips.length === 0 ? (
            <div className="py-12 text-center space-y-3">
              <div className="w-14 h-14 mx-auto rounded-2xl bg-slate-100 text-slate-400 flex items-center justify-center">
                <Bookmark className="w-7 h-7" />
              </div>
              <div>
                <h4 className="text-sm font-bold text-slate-700">Chưa có chuyến đi nào được lưu</h4>
                <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1">
                  Khi Trợ lý tạo ra lịch trình ưng ý, hãy nhấn nút <strong>"Lưu chuyến đi"</strong> để lưu giữ và xem lại bất cứ khi nào bạn muốn.
                </p>
              </div>
            </div>
          ) : (
            savedTrips.map((item) => {
              const isCurrentlyActive = currentPlanTitle === item.plan.title;

              return (
                <div
                  key={item.id}
                  className={`p-4 rounded-xl border transition-all ${
                    isCurrentlyActive 
                      ? 'border-blue-300 bg-blue-50/40 shadow-xs' 
                      : 'border-slate-200 hover:border-slate-300 bg-white hover:shadow-xs'
                  }`}
                >
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                    <div className="space-y-1.5 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="px-2.5 py-0.5 rounded-md bg-blue-100 text-blue-800 text-[11px] font-bold">
                          {item.plan.intent.destination}
                        </span>
                        <span className="text-xs text-slate-400 flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {formatDate(item.savedAt)}
                        </span>
                        {isCurrentlyActive && (
                          <span className="px-2 py-0.5 rounded-md bg-emerald-100 text-emerald-700 text-[10px] font-bold flex items-center gap-1">
                            <Check className="w-3 h-3" /> Đang hiển thị
                          </span>
                        )}
                      </div>

                      <h4 className="text-sm font-bold text-slate-900">
                        {item.plan.title}
                      </h4>

                      <div className="flex items-center gap-3 text-xs text-slate-600 flex-wrap">
                        <span className="flex items-center gap-1">
                          <Calendar className="w-3.5 h-3.5 text-slate-400" />
                          {item.plan.intent.days} ngày
                        </span>
                        <span className="flex items-center gap-1">
                          <Users className="w-3.5 h-3.5 text-slate-400" />
                          {item.plan.intent.party === 'family_with_kids' ? 'Gia đình có trẻ nhỏ' : 'Cặp đôi'}
                        </span>
                        <span className="font-semibold text-blue-700">
                          {item.plan.bookableProductsCount} dịch vụ đặt được
                        </span>
                        <span className="font-mono font-bold text-slate-900">
                          {item.plan.totalEstimatedPrice != null
                            ? `~${new Intl.NumberFormat('vi-VN').format(item.plan.totalEstimatedPrice)} ₫`
                            : 'Chưa tính được'}
                        </span>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
                      {onShareTrip && (
                        <button
                          onClick={() => {
                            onShareTrip(item.plan);
                          }}
                          className="px-2.5 py-1.5 text-xs font-semibold rounded-lg bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 transition-colors flex items-center gap-1 shadow-2xs"
                          title="Chia sẻ chuyến đi này"
                        >
                          <Share2 className="w-3.5 h-3.5" />
                          <span>Chia sẻ</span>
                        </button>
                      )}

                      <button
                        onClick={() => {
                          onSelectTrip(item.plan);
                          onClose();
                        }}
                        className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-colors flex items-center gap-1 ${
                          isCurrentlyActive
                            ? 'bg-blue-600 text-white'
                            : 'bg-slate-100 hover:bg-blue-50 text-slate-700 hover:text-blue-700'
                        }`}
                      >
                        <span>{isCurrentlyActive ? 'Đang mở' : 'Mở lại'}</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>

                      <button
                        onClick={() => onDeleteTrip(item.id)}
                        className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
                        title="Xóa khỏi danh sách lưu"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Modal Footer */}
        <div className="p-4 border-t border-slate-100 bg-slate-50 flex items-center justify-between text-xs text-slate-500">
          <span>Dữ liệu được lưu an toàn trong trình duyệt của bạn.</span>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 font-bold rounded-xl transition-colors"
          >
            Đóng
          </button>
        </div>
      </div>
    </div>
  );
};
