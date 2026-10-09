import React from 'react';
import { Check, Clock, Loader2 } from 'lucide-react';
import type { AssistantProgress } from '../../../context/assistantState';
import { progressView } from './widgetProgress';

export function WidgetProgress({ progress, isSlow }: { progress: AssistantProgress[]; isSlow: boolean }) {
  const view = progressView(progress);

  return (
    <div className="space-y-3">
      {/* Chỉ đọc câu đang làm, không đọc lại cả danh sách mỗi khi một bước xong. */}
      <p role="status" className="sr-only">{isSlow ? `${view.current} Đang lâu hơn thường lệ.` : view.current}</p>
      <ol aria-hidden="true" className="space-y-2 text-sm">
        {view.steps.map((step) => (
          <li key={step.label} className="flex items-center gap-2.5">
            {step.status === 'done' && (
              <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
                <Check className="h-3.5 w-3.5" strokeWidth={3} />
              </span>
            )}
            {step.status === 'active' && <Loader2 className="h-5 w-5 shrink-0 animate-spin text-ai-600" />}
            {step.status === 'pending' && <span className="h-5 w-5 shrink-0 rounded-full border-2 border-slate-200" />}
            <span className={step.status === 'active' ? 'font-semibold text-slate-800' : step.status === 'done' ? 'text-slate-600' : 'text-slate-400'}>
              {step.label}
            </span>
          </li>
        ))}
      </ol>
      {isSlow && (
        <p aria-hidden="true" className="flex items-center gap-1.5 text-xs text-amber-700">
          <Clock className="h-3.5 w-3.5 shrink-0" />Đang lâu hơn thường lệ. Bạn có thể đợi thêm hoặc dừng.
        </p>
      )}
    </div>
  );
}
