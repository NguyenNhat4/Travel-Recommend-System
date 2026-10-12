'use client';
import React, { useId } from 'react';

/** Ô tự nhập mong muốn khác, cạnh các lựa chọn cố định (AC-AGT-01, chốt 12/10). */
export const MAX_PREFERENCE_NOTE = 150;

/**
 * Sở thích của form: lựa chọn cố định trong `interestOptions` (chọn nhiều) và một ô tự nhập ngắn. Không gọi LLM.
 */
export function TripPreferenceFields({ options, selected, onToggle, note, onNote, disabled, chipClass }: {
  options: readonly string[]; selected: readonly string[]; onToggle: (option: string) => void;
  note: string; onNote: (note: string) => void; disabled: boolean; chipClass: (selected: boolean) => string;
}) {
  const noteId = useId();
  return <fieldset className="space-y-2">
    <legend className="text-xs font-bold text-slate-700">Sở thích (không bắt buộc)</legend>
    {options.length > 0 && <div className="flex flex-wrap gap-1.5">
      {options.map((option) => <button key={option} type="button" aria-pressed={selected.includes(option)} disabled={disabled}
        onClick={() => onToggle(option)} className={chipClass(selected.includes(option))}>{option}</button>)}
    </div>}
    <label htmlFor={noteId} className="sr-only">Mong muốn khác</label>
    <input id={noteId} type="text" value={note} disabled={disabled} maxLength={MAX_PREFERENCE_NOTE}
      onChange={(event) => onNote(event.target.value)} placeholder="Mong muốn khác, ví dụ: gần chợ đêm, đi chậm…"
      className="min-h-9 w-full rounded-lg border border-slate-300 bg-white px-2 text-xs focus:outline-none focus:ring-1 focus:ring-ai-500" />
  </fieldset>;
}
