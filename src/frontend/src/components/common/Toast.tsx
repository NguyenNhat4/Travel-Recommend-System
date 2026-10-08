import React from 'react';
import { useTravel } from '../../context/TravelContext';
import { CheckCircle2, X } from 'lucide-react';

export const Toast: React.FC = () => {
  const { toast, hideToast } = useTravel();

  if (!toast) return null;

  return (
    <div role="status" aria-live="polite" className="fixed bottom-4 right-4 left-4 z-[1200] sm:left-auto sm:bottom-6 sm:right-6 sm:w-full sm:max-w-md animate-in slide-in-from-bottom-5 duration-200 motion-reduce:animate-none">
      <div className="flex flex-wrap items-center justify-between gap-3 p-4 bg-slate-900 text-white rounded-xl shadow-lg border border-slate-700/80">
        <div className="flex items-center gap-3 min-w-0">
          <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
          <p className="text-sm font-medium leading-relaxed text-slate-100 break-words">
            {toast.message}
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {toast.actionText && toast.onAction && (
            <button
              onClick={() => {
                toast.onAction!();
                hideToast();
              }}
              className="min-h-11 text-sm font-semibold text-brand-300 hover:text-brand-200 underline px-2 py-1 focus-visible:outline-2 focus-visible:outline-white"
            >
              {toast.actionText}
            </button>
          )}
          <button
            onClick={hideToast}
            aria-label="Đóng thông báo"
            className="min-h-11 min-w-11 flex items-center justify-center text-slate-300 hover:text-white rounded-md transition-colors focus-visible:outline-2 focus-visible:outline-white"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
