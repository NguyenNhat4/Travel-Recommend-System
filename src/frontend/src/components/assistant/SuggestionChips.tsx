import React from 'react';
import { CornerDownRight } from 'lucide-react';

/** Gợi ý bấm được của phản hồi NO_RESULTS và NEEDS_CLARIFICATION (điều kiện bắt buộc chưa có sản phẩm);
 * bấm là gửi ngay câu đó làm lượt chat kế tiếp. */
export function SuggestionChips({ suggestions, onSelect, disabled }: {
  suggestions: string[];
  onSelect: (suggestion: string) => void;
  disabled?: boolean;
}) {
  if (suggestions.length === 0) return null;
  return (
    <div className="mt-3 flex flex-col items-start gap-2" role="group" aria-label="Gợi ý điều chỉnh yêu cầu">
      {suggestions.map((suggestion) => (
        <button
          key={suggestion}
          type="button"
          disabled={disabled}
          onClick={() => onSelect(suggestion)}
          className="flex min-h-11 max-w-full items-center gap-2 rounded-lg bg-brand-50 px-3 py-2 text-left text-sm text-brand-700 transition hover:bg-brand-100 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <CornerDownRight aria-hidden="true" className="h-4 w-4 shrink-0" />
          <span className="min-w-0 break-words">{suggestion}</span>
        </button>
      ))}
    </div>
  );
}
