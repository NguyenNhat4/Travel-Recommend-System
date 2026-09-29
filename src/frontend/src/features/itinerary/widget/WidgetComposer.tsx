import React, { useEffect, useId, useRef } from 'react';
import { ArrowUp, Sparkles } from 'lucide-react';

interface WidgetComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  busy: boolean;
  initial?: boolean;
}

export function WidgetComposer({ value, onChange, onSend, busy, initial = false }: WidgetComposerProps) {
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const inputId = useId();

  useEffect(() => {
    const input = inputRef.current;
    if (!input) return;
    input.style.height = 'auto';
    input.style.height = `${Math.min(input.scrollHeight, 192)}px`;
  }, [value, initial]);

  useEffect(() => {
    inputRef.current?.focus();
  }, [initial]);

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (value.trim() && !busy) onSend();
  };

  return (
    <form onSubmit={submit} aria-label="Gửi yêu cầu du lịch" className={`w-full rounded-2xl border bg-white p-3 transition focus-within:border-blue-500 focus-within:ring-4 focus-within:ring-blue-50 ${initial ? 'border-blue-200 shadow-sm' : 'border-slate-200'}`}>
      <label htmlFor={inputId} className="sr-only">Tin nhắn cho trợ lý du lịch AI</label>
      <textarea
        ref={inputRef}
        id={inputId}
        rows={initial ? 3 : 1}
        maxLength={1000}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
            event.preventDefault();
            event.currentTarget.form?.requestSubmit();
          }
        }}
        placeholder={initial ? 'Mô tả chuyến đi bạn mong muốn…' : 'Nhập yêu cầu du lịch hoặc lịch trình...'}
        className="block max-h-48 min-h-12 w-full resize-none bg-transparent px-1 py-2 text-base leading-relaxed text-slate-800 outline-none placeholder:text-slate-500"
      />
      <div className="mt-2 flex items-center justify-between gap-3">
        <span className="flex items-center gap-1.5 text-xs text-slate-500">
          {initial ? <><Sparkles className="h-3.5 w-3.5 text-blue-600" aria-hidden="true" /> Lên lịch trình cùng AI</> : 'Enter để gửi · Shift+Enter xuống dòng'}
        </span>
        <button type="submit" disabled={!value.trim() || busy} aria-label="Gửi yêu cầu" className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-white transition hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-500">
          <ArrowUp className="h-5 w-5" aria-hidden="true" />
        </button>
      </div>
    </form>
  );
}
