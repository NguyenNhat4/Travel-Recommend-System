'use client';

/**
 * Hỏi lại trước khi khách chủ động rời trang thanh toán (FR-BKG-01, AC-BKG-20; docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md §6.2).
 *
 * Bốn lối rời trang, mỗi lối một cách chặn:
 * - `navigate()` của `TravelContext` (logo, "Quay lại giỏ hàng", "Sửa giỏ hàng"): guard đăng ký vào context;
 * - thẻ `<a>` (liên kết ở chân trang): một listener `click` ở pha capture, chạy trước `<Link>` của Next;
 * - đóng tab, tải lại, gõ địa chỉ khác: `beforeunload`, trình duyệt hiện hộp mặc định của nó;
 * - nút Back của trình duyệt: không huỷ được `popstate`, nên đặt một mục lịch sử "chặn" ngay dưới trang. Back ở bước đầu rơi vào
 *   mục đó (cùng URL, trang không bị gỡ) và hộp cảnh báo hiện lên; "Ở lại" đi tới lại, "Rời trang" lùi thêm một mục.
 *
 * Mục chặn chỉ được đặt sau thao tác đầu tiên của khách: trình duyệt bỏ qua mục lịch sử do script thêm khi khách chưa chạm vào trang.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { useTravel } from '../../context/TravelContext';

export type LeavePrompt = { kind: 'route'; href: string } | { kind: 'back' };

/** Dấu trên `history.state` của các mục lịch sử thuộc trang thanh toán: `exit` là mục chặn, `in` là các mục phía trên nó. */
const MARK = 'votaCheckout';
const HAS_PREVIOUS = 'votaCheckoutHasPrevious';

type HistoryState = Record<string, unknown> | null;

function markOf(): 'exit' | 'in' | null {
  const value = (window.history.state as HistoryState)?.[MARK];
  return value === 'exit' || value === 'in' ? value : null;
}

/**
 * State cho `pushState` / `replaceState` của các bước `?step=`: giữ dấu của mục hiện tại, để sau khi tải lại trang ở một bước sau
 * trang vẫn biết bên dưới đã có mục chặn và không đặt thêm mục thứ hai.
 */
export function stepHistoryState(mode: 'push' | 'replace'): HistoryState {
  const mark = markOf();
  if (!mark) return null;
  if (mode === 'push' || mark === 'in') return { [MARK]: 'in' };
  return { [MARK]: 'exit', [HAS_PREVIOUS]: Boolean((window.history.state as HistoryState)?.[HAS_PREVIOUS]) };
}

export function useLeaveGuard({ active, fallback }: { active: boolean; fallback: string }) {
  const { navigate, setNavigationGuard } = useTravel();
  const [prompt, setPrompt] = useState<LeavePrompt | null>(null);

  // Các listener đọc cờ qua ref để một lần rời trang do hệ thống (sang Stripe) tắt được guard ngay, không chờ React vẽ lại.
  const activeRef = useRef(active);
  const bypass = useRef(false);
  const promptRef = useRef<LeavePrompt | null>(null);
  const fallbackRef = useRef(fallback);
  useEffect(() => { activeRef.current = active; promptRef.current = prompt; fallbackRef.current = fallback; });
  const guarding = () => activeRef.current && !bypass.current;

  // Guard bật lại sau mỗi lần đổi trạng thái (ví dụ bấm Thanh toán bị lỗi); hết hiệu lực thì đóng hộp đang mở.
  useEffect(() => {
    bypass.current = false;
    if (!active) setPrompt(null);
  }, [active]);

  useEffect(() => {
    if (!active) return undefined;

    setNavigationGuard((route) => {
      // Chuyển trong chính trang thanh toán (đổi bước, đổi đơn nháp) không phải là rời trang.
      if (!guarding() || route.split(/[?#]/)[0] === window.location.pathname) return false;
      setPrompt({ kind: 'route', href: route });
      return true;
    });

    const arm = () => {
      // Đang hỏi lại ở chính mục chặn: không thêm mục mới, "Ở lại" sẽ đi tới lại mục cũ.
      if (!guarding() || promptRef.current?.kind === 'back') return;
      const mark = markOf();
      if (mark === 'in') return;
      const url = window.location.href;
      if (mark === null) window.history.replaceState({ [MARK]: 'exit', [HAS_PREVIOUS]: window.history.length > 1 }, '', url);
      window.history.pushState({ [MARK]: 'in' }, '', url);
    };

    const onLinkClick = (event: MouseEvent) => {
      if (!guarding() || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const anchor = (event.target as Element | null)?.closest?.('a[href]') as HTMLAnchorElement | null;
      if (!anchor || anchor.hasAttribute('download') || (anchor.target && anchor.target !== '_self')) return;
      const url = new URL(anchor.href, window.location.href);
      // Trang khác origin rời bằng tải trang (đã có `beforeunload`); cùng đường dẫn là liên kết trong trang (#trường-lỗi).
      if (url.origin !== window.location.origin || url.pathname === window.location.pathname) return;
      event.preventDefault();
      event.stopPropagation();
      setPrompt({ kind: 'route', href: `${url.pathname}${url.search}${url.hash}` });
    };

    const onPopState = () => {
      if (!guarding()) return;
      if (markOf() === 'exit') setPrompt({ kind: 'back' });
      // Khách bấm Forward khi hộp của nút Back đang mở: đã quay lại trang, coi như ở lại.
      else if (promptRef.current?.kind === 'back') setPrompt(null);
    };

    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!guarding()) return;
      event.preventDefault();
      // Trình duyệt cũ chỉ hỏi lại khi `returnValue` được gán.
      event.returnValue = '';
    };

    document.addEventListener('click', arm, true);
    document.addEventListener('keydown', arm, true);
    document.addEventListener('click', onLinkClick, true);
    window.addEventListener('popstate', onPopState);
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => {
      setNavigationGuard(null);
      document.removeEventListener('click', arm, true);
      document.removeEventListener('keydown', arm, true);
      document.removeEventListener('click', onLinkClick, true);
      window.removeEventListener('popstate', onPopState);
      window.removeEventListener('beforeunload', onBeforeUnload);
    };
  }, [active, setNavigationGuard]);

  /** Ở lại: đóng hộp; nếu đang đứng ở mục chặn (vừa bấm Back) thì đi tới lại mục của trang. */
  const stay = useCallback(() => {
    const current = promptRef.current;
    setPrompt(null);
    if (current?.kind === 'back' && markOf() === 'exit') window.history.forward();
  }, []);

  /** Rời trang: tới đúng nơi khách định mở. Với nút Back là mục lịch sử ngay trước trang thanh toán, không có thì về `fallback`. */
  const leave = useCallback(() => {
    const current = promptRef.current;
    if (!current) return;
    bypass.current = true;
    setPrompt(null);
    if (current.kind === 'route') navigate(current.href);
    else if (markOf() === 'exit' && (window.history.state as HistoryState)?.[HAS_PREVIOUS]) window.history.back();
    else navigate(fallbackRef.current);
  }, [navigate]);

  /** Gọi ngay trước một lần rời trang do hệ thống thực hiện (sang Stripe, giỏ rỗng): lần đó không bị hỏi lại. */
  const allowLeave = useCallback(() => { bypass.current = true; }, []);

  return { prompt, stay, leave, allowLeave };
}
