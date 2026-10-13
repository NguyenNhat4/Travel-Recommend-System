import React, { useId, useState } from 'react';
import { Check, ChevronDown } from 'lucide-react';
import { ProgressSteps } from './WidgetProgress';
import type { ProgressView } from './widgetProgressView';
export function WidgetProgressSummary({view}:{view:ProgressView}) {
  const [open,setOpen]=useState(false);
  const id=useId();
  if (!view.summary) return null;
  return <div className="mb-4 min-w-0 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs leading-5">
    <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} aria-controls={id} className="flex min-h-11 w-full items-start gap-2 text-left text-slate-600">
      <Check aria-hidden="true" className="mt-1 h-4 w-4 shrink-0 text-emerald-600" />
      <span className="min-w-0 flex-1 break-words">{view.summary}<span className="ml-2 font-semibold text-ai-700">{open ? 'Thu gọn' : 'Xem các bước'}</span></span>
      <ChevronDown aria-hidden="true" className={`mt-1 h-4 w-4 shrink-0 ${open ? 'rotate-180' : ''}`} />
    </button>
    <div id={id} hidden={!open} className="pt-3"><ProgressSteps view={view} /></div>
  </div>;
}
