import React from 'react';

/** Gợi ý bấm được của phản hồi NO_RESULTS và NEEDS_CLARIFICATION (điều kiện bắt buộc chưa có sản phẩm);
 * bấm là gửi ngay câu đó làm lượt chat kế tiếp. */
export function SuggestionChips({ suggestions, onSelect, disabled }: {
  suggestions: string[];
  onSelect: (suggestion: string) => void;
  disabled?: boolean;
}) {
  if (suggestions.length === 0) return null;
  return (
    <div className="mt-3 flex flex-wrap gap-2" role="group" aria-label="Gợi ý điều chỉnh yêu cầu">
      {suggestions.map((suggestion) => (
        <button
          key={suggestion}
          type="button"
          disabled={disabled}
          onClick={() => onSelect(suggestion)}
          className="min-h-11 rounded-full border border-blue-200 bg-white px-4 py-2 text-left text-sm font-medium text-blue-700 transition hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {suggestion}
        </button>
      ))}
    </div>
  );
}
