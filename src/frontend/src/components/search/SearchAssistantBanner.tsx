'use client';

import React from 'react';
import { Sparkles } from 'lucide-react';
import { useAssistant } from '../../context/AssistantProvider';

/** Thẻ mời ghép kết quả thành lịch trình (product §4.2.3): chèn sau kết quả thứ 3 và cuối tab "Tất cả". */
export const SearchAssistantBanner: React.FC<{ query: string }> = ({ query }) => {
  const { openFloatingWidget } = useAssistant();
  return (
    <div className="p-4 rounded-xl bg-gradient-to-r from-blue-900 to-indigo-900 text-white flex flex-col sm:flex-row items-center justify-between gap-3 shadow-sm my-2">
      <div className="flex items-center gap-2.5">
        <div className="p-2 rounded-lg bg-blue-500/30 text-indigo-300">
          <Sparkles className="w-5 h-5" />
        </div>
        <div>
          <h4 className="font-sans text-xs font-bold text-white">
            Muốn ghép các dịch vụ này thành lịch trình trọn gói?
          </h4>
          <p className="text-[11px] text-slate-300">
            Trợ lý AI sẽ tự động phân bổ khách sạn, vé tham quan và ăn uống theo ngày.
          </p>
        </div>
      </div>
      <button
        onClick={() => openFloatingWidget(query || undefined)}
        className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs rounded-lg shadow-xs transition-colors shrink-0 whitespace-nowrap"
      >
        Hỏi trợ lý với truy vấn này →
      </button>
    </div>
  );
};
