import React, { useEffect, useState } from 'react';
import { Check, Clock, Loader2 } from 'lucide-react';
import type { AssistantProgress } from '../../../context/assistantState';
import type { ProgressModel, ProgressActivity } from './progressModel';
import { progressView, type ProgressStep, type ProgressView } from './widgetProgressView';

const REVEAL_MS = 450;

function StepIcon({ status }: { status: ProgressStep['status'] }) {
  return status==='done' ? <Check aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
    : status==='active' ? <Loader2 aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 motion-safe:animate-spin text-ai-600" />
    : <span aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 rounded-full border-2 border-slate-200" />;
}

export function ProgressSteps({ steps, waiting }: { steps: ProgressStep[]; waiting?: string }) {
  return <ol className="space-y-3 text-sm">
    {/* Mọi bước (Think lẫn việc) cùng một dạng: vòng quay khi đang chạy, ✓ khi xong, chi tiết xám bên dưới. */}
    {steps.map((step) => <li key={step.key} className="progress-step-in flex min-w-0 items-start gap-2.5">
        <StepIcon status={step.status} />
        <div className="min-w-0 flex-1 break-words">
          <p className={step.status==='active' ? 'font-semibold text-slate-800' : step.status==='done' ? 'font-medium text-slate-700' : 'text-slate-400'}>{step.label}</p>
          {!!step.lines.length && <div className={`mt-1 space-y-1 leading-5 text-slate-600 ${step.tone==='think' ? 'text-sm' : 'text-xs'}`}>{step.lines.slice(0,4).map((line,index) => <p key={index}>{line}</p>)}{step.lines.length>4 && <p>+{step.lines.length-4} mục khác</p>}</div>}
          {step.notices.map((line,index) => <p key={index} className="mt-1 text-xs leading-5 text-amber-700">⚠ {line}</p>)}
        </div>
      </li>)}
    {waiting && <li className="progress-step-in flex min-w-0 items-start gap-2.5">
      <StepIcon status="active" /><p className="min-w-0 flex-1 break-words text-slate-500">{waiting}</p>
    </li>}
  </ol>;
}

/** Hiện từng bước một: sự kiện đến dồn (tool trả nhanh) vẫn được đọc lần lượt, không nhảy cả khối cùng lúc. */
function useRevealed(total: number) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    if (shown > total) { setShown(total); return; }
    if (shown === total) return;
    const timer = window.setTimeout(() => setShown((count) => count + 1), shown ? REVEAL_MS : 0);
    return () => window.clearTimeout(timer);
  }, [shown, total]);
  return Math.min(shown, total);
}

export function WidgetProgress({ progress, model, activity, isSlow, debugMode=false }: {progress:AssistantProgress[]; model?:ProgressModel; activity?:ProgressActivity; isSlow:boolean; debugMode?:boolean}) {
  const view: ProgressView = progressView(model ?? progress,activity);
  const revealed = useRevealed(view.steps.length);
  const steps = view.steps.slice(0, revealed);
  const catchingUp = revealed < view.steps.length;
  const waiting = !catchingUp && !steps.some((step) => step.status==='active') ? view.current : undefined;
  return <div className="min-w-0 space-y-3 rounded-2xl border border-slate-100 bg-slate-50/70 p-4">
    <p role="status" className="sr-only">{view.current}{isSlow ? ' Đang lâu hơn thường lệ.' : ''}</p>
    <ProgressSteps steps={steps} waiting={waiting} />
    {debugMode && <div className="text-xs font-mono text-slate-500">{progress.slice(-1).map((p) => <p key={p.sequence}>{p.nodeId} · {p.durationMs} ms</p>)}</div>}
    {isSlow && <p className="flex items-center gap-1.5 text-xs text-amber-700"><Clock aria-hidden="true" className="h-3.5 w-3.5 shrink-0" />Đang lâu hơn thường lệ. Bạn có thể đợi thêm hoặc dừng.</p>}
  </div>;
}
