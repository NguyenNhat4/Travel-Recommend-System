'use client';

import { useCallback, useEffect, useId, useMemo, useState } from 'react';
import type React from 'react';
import type { SearchSuggestion } from '../../../services/suggest';
import { POPULAR_KEYWORDS, useRecentSearches } from './recentSearches';
import { suggestionKey, useInstantSearch, type InstantStatus } from './useInstantSearch';

/** Một dòng chọn được trong panel, theo đúng thứ tự hiển thị (để điều khiển bằng phím). */
export type InstantOption =
  | { kind: 'recent' | 'popular'; label: string }
  | { kind: 'suggestion'; label: string; suggestion: SearchSuggestion };

interface InstantSearchBoxOptions {
  /** Chữ đang có trong ô. */
  value: string;
  /** Tìm với một câu (Enter, "Xem tất cả", một từ khoá gần đây/phổ biến, một điểm đến): thường là sang `/search?q=`. */
  onSearch: (query: string) => void;
  /** Mở trang chi tiết của một sản phẩm được gợi ý. */
  onOpenProduct: (productId: string) => void;
}

export interface InstantSearchPanelState {
  listId: string;
  query: string;
  /** true khi chữ đang gõ đủ điều kiện gợi ý; false thì panel hiện tìm kiếm gần đây và từ khoá phổ biến. */
  typing: boolean;
  status: InstantStatus;
  options: InstantOption[];
  activeIndex: number;
  optionId: (index: number) => string;
  onPick: (option: InstantOption) => void;
  onSeeAll: () => void;
  onClearRecent: () => void;
}

/**
 * Điều khiển panel gợi ý của một ô tìm kiếm (FR-SRC-05): mở/đóng, phím ↑ ↓ Enter Esc, lịch sử tìm kiếm.
 * Ô nhập và form vẫn do nơi dùng tự vẽ; hook chỉ trả thuộc tính gắn vào `<input>` và dữ liệu cho `InstantSearchPanel`.
 */
export function useInstantSearchBox({ value, onSearch, onOpenProduct }: InstantSearchBoxOptions) {
  const listId = useId();
  // Phần tử bao ô nhập và panel, giữ bằng state (callback ref) để biết một cú bấm hay focus có nằm ngoài nó không.
  const [container, setContainer] = useState<HTMLDivElement | null>(null);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const recent = useRecentSearches();
  const instant = useInstantSearch(value, open);
  const typing = suggestionKey(value) !== null;

  const options = useMemo<InstantOption[]>(() => {
    if (typing) return instant.suggestions.map((suggestion) => ({ kind: 'suggestion', label: suggestion.label, suggestion }));
    return [
      ...recent.items.map((label) => ({ kind: 'recent' as const, label })),
      ...POPULAR_KEYWORDS.map((label) => ({ kind: 'popular' as const, label })),
    ];
  }, [typing, instant.suggestions, recent.items]);
  const active = activeIndex < options.length ? activeIndex : -1;

  const close = useCallback(() => {
    setOpen(false);
    setActiveIndex(-1);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!container?.contains(event.target as Node)) close();
    };
    document.addEventListener('mousedown', onPointerDown);
    return () => document.removeEventListener('mousedown', onPointerDown);
  }, [open, close, container]);

  const remember = recent.remember;
  /** Một lượt tìm thật: ghi vào lịch sử rồi giao cho nơi dùng điều hướng. */
  const search = useCallback(
    (query: string) => {
      const text = query.trim();
      if (!text) return;
      remember(text);
      close();
      onSearch(text);
    },
    [remember, close, onSearch],
  );

  const pick = useCallback(
    (option: InstantOption) => {
      if (option.kind === 'suggestion' && option.suggestion.type === 'product' && option.suggestion.productId) {
        close();
        onOpenProduct(option.suggestion.productId);
        return;
      }
      search(option.label);
    },
    [close, onOpenProduct, search],
  );

  const optionId = useCallback((index: number) => `${listId}-option-${index}`, [listId]);

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setOpen(true);
      setActiveIndex(Math.min(active + 1, options.length - 1));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveIndex(Math.max(active - 1, -1));
    } else if (event.key === 'Escape' && open) {
      event.preventDefault();
      close();
    } else if (event.key === 'Enter' && open && active >= 0 && options[active]) {
      // Enter khi chưa tô sáng mục nào thì để form gửi đi như cũ.
      event.preventDefault();
      pick(options[active]);
    }
  };

  const inputProps = {
    role: 'combobox' as const,
    'aria-expanded': open,
    'aria-controls': listId,
    'aria-autocomplete': 'list' as const,
    'aria-activedescendant': open && active >= 0 ? optionId(active) : undefined,
    autoComplete: 'off',
    onFocus: () => setOpen(true),
    onKeyDown,
    onBlur: (event: React.FocusEvent<HTMLInputElement>) => {
      // Tab ra ngoài thì đóng; bấm vào panel không làm ô mất focus (panel chặn mousedown).
      if (!container?.contains(event.relatedTarget as Node | null)) close();
    },
  };

  const panel: InstantSearchPanelState = {
    listId,
    query: value.trim(),
    typing,
    status: instant.status,
    options,
    activeIndex: active,
    optionId,
    onPick: pick,
    onSeeAll: () => search(value),
    onClearRecent: recent.clear,
  };

  return {
    /** Gắn vào `ref` của phần tử bao ô nhập và panel. */
    containerRef: setContainer,
    inputProps,
    panel,
    open,
    close,
    search,
    /** Ghi một câu vào lịch sử mà không điều hướng (chip là `<Link>` tự điều hướng). */
    remember,
    /** Gọi trong `onChange` của ô: gõ là mở panel và bỏ mục đang tô sáng. */
    onType: () => {
      setOpen(true);
      setActiveIndex(-1);
    },
  };
}
