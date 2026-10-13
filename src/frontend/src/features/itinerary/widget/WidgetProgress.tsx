import React from 'react';
import { Check, Clock, Loader2 } from 'lucide-react';
import type { AssistantProgress } from '../../../context/assistantState';
import type { ProgressModel, ProgressActivity } from './progressModel';
import { progressView, type ProgressView } from './widgetProgressView';

export function ProgressSteps({ view }: { view: ProgressView }) {
  return <ol className="space-y-3 text-sm">
    {view.steps.map((step) => <li key={step.key} className="flex min-w-0 items-start gap-2.5">
      {step.status==='done' ? <Check aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
        : step.status==='active' ? <Loader2 aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 motion-safe:animate-spin text-ai-600" />
        : <span aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 rounded-full border-2 border-slate-200" />}
      <div className="min-w-0 flex-1 break-words">
        <p className={step.status==='active' ? 'font-semibold text-slate-800' : step.status==='done' ? 'font-medium text-slate-700' : 'text-slate-400'}>{step.label}</p>
        <div className="mt-1 space-y-1 text-xs leading-5 text-slate-600">{step.lines.slice(0,4).map((line,index) => <p key={index}>{line}</p>)}{step.lines.length>4 && <p>+{step.lines.length-4} mục khác</p>}</div>
        {step.notices.map((line,index) => <p key={index} className="mt-1 text-xs leading-5 text-amber-700">⚠ {line}</p>)}
      </div>
    </li>)}
  </ol>;
}
export function WidgetProgress({ progress, model, activity, isSlow, debugMode=false }: {progress:AssistantProgress[]; model?:ProgressModel; activity?:ProgressActivity; isSlow:boolean; debugMode?:boolean}) {
  const view=progressView(model ?? progress,activity);
  return <div className="min-w-0 space-y-3 rounded-2xl border border-slate-100 bg-slate-50/70 p-4">
    <p role="status" className="sr-only">{view.current}{isSlow ? ' Đang lâu hơn thường lệ.' : ''}</p>
    <ProgressSteps view={view} />
    {debugMode && <div className="text-xs font-mono text-slate-500">{progress.slice(-1).map((p) => <p key={p.sequence}>{p.nodeId} · {p.durationMs} ms</p>)}</div>}
    {isSlow && <p className="flex items-center gap-1.5 text-xs text-amber-700"><Clock aria-hidden="true" className="h-3.5 w-3.5 shrink-0" />Đang lâu hơn thường lệ. Bạn có thể đợi thêm hoặc dừng.</p>}
  </div>;
}
