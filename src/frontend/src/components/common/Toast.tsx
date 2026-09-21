import React from 'react';
import { useTravel } from '../../context/TravelContext';
import { CheckCircle2, X } from 'lucide-react';

export const Toast: React.FC = () => {
  const { toast, hideToast } = useTravel();

  if (!toast) return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 max-w-md w-full animate-in slide-in-from-bottom-5 duration-200">
      <div className="flex items-center justify-between gap-3 p-4 bg-slate-900 text-white rounded-xl shadow-2xl border border-slate-700/80">
        <div className="flex items-center gap-3 min-w-0">
          <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
          <p className="text-xs font-medium text-slate-100 truncate">
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
              className="text-xs font-bold text-blue-400 hover:text-blue-300 underline px-2 py-1"
            >
              {toast.actionText}
            </button>
          )}
          <button
            onClick={hideToast}
            className="p-1 text-slate-400 hover:text-slate-200 rounded-md transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
