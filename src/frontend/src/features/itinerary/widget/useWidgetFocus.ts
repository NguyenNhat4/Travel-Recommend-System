import { useEffect, useRef } from 'react';

export function useWidgetFocus(open: boolean, expanded: boolean, historyOpen: boolean) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const wasOpen = useRef(false);

  useEffect(() => {
    if (!open) {
      if (!wasOpen.current) return;
      wasOpen.current = false;
      const frame = requestAnimationFrame(() => {
        document.querySelector<HTMLButtonElement>('[aria-label="Mở trợ lý du lịch AI"]')?.focus();
      });
      return () => cancelAnimationFrame(frame);
    }
    wasOpen.current = true;
    const frame = requestAnimationFrame(() => {
      const root = dialogRef.current;
      const target = historyOpen ? root?.querySelector<HTMLButtonElement>('[data-widget-history] button') : root?.querySelector<HTMLTextAreaElement>('textarea');
      target?.focus();
    });
    const trapFocus = (event: KeyboardEvent) => {
      if (event.key !== 'Tab') return;
      const root = dialogRef.current;
      const scope = historyOpen ? root?.querySelector('[data-widget-history]') : root;
      const controls = Array.from(scope?.querySelectorAll<HTMLElement>('button:not(:disabled), textarea, a[href], [tabindex="0"]') ?? []).filter((item) => item.getClientRects().length > 0);
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (!first || !last) return;
      if (!controls.includes(document.activeElement as HTMLElement) || (event.shiftKey && document.activeElement === first)) {
        event.preventDefault();
        (event.shiftKey ? last : first).focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', trapFocus);
    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener('keydown', trapFocus);
    };
  }, [open, expanded, historyOpen]);

  return dialogRef;
}
