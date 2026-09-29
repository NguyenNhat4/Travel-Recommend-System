'use client';

import React, { useEffect, useId, useRef } from 'react';

interface MenuShellProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Nhãn của panel cho trình đọc màn hình. */
  panelLabel: string;
  /** aria-label của nút khi nút chỉ có icon. */
  buttonLabel?: string;
  buttonClassName: string;
  /** Panel neo theo mép trái hay mép phải của nút; nhóm cuối header neo phải để không tràn màn hình. */
  align?: 'left' | 'right';
  button: React.ReactNode;
  children: React.ReactNode;
}

const OPEN_DELAY_MS = 120;
const CLOSE_DELAY_MS = 160;

function canHover(): boolean {
  return typeof window !== 'undefined' && Boolean(window.matchMedia?.('(hover: hover)').matches);
}

/**
 * Vỏ menu kiểu disclosure (nút `aria-expanded` + panel chứa liên kết): rê chuột mở sau 120 ms chỉ trên thiết bị có hover,
 * bấm mở/đóng, Esc đóng và trả focus về nút, Tab ra ngoài thì đóng. Việc đóng khi bấm ra ngoài và khi đổi route do Header lo.
 */
export function MenuShell({
  open, onOpenChange, panelLabel, buttonLabel, buttonClassName, align = 'left', button, children,
}: MenuShellProps) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const panelId = useId();

  useEffect(() => () => clearTimeout(timer.current), []);

  const schedule = (next: boolean, delay: number) => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => onOpenChange(next), delay);
  };

  return (
    <div
      ref={wrapRef}
      className="relative"
      onMouseEnter={() => { if (canHover()) schedule(true, OPEN_DELAY_MS); }}
      onMouseLeave={() => { if (canHover()) schedule(false, CLOSE_DELAY_MS); }}
      onKeyDown={(event) => {
        if (event.key === 'Escape' && open) {
          event.stopPropagation();
          clearTimeout(timer.current);
          onOpenChange(false);
          buttonRef.current?.focus();
        }
      }}
      onBlur={(event) => {
        if (open && !wrapRef.current?.contains(event.relatedTarget as Node | null)) onOpenChange(false);
      }}
    >
      <button
        ref={buttonRef}
        type="button"
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        aria-label={buttonLabel}
        className={buttonClassName}
        onClick={(event) => {
          clearTimeout(timer.current);
          // Chuột: menu đã mở nhờ rê thì bấm giữ nguyên. Bàn phím (detail = 0): Enter/Space bật tắt.
          if (event.detail > 0 && canHover() && open) return;
          onOpenChange(!open);
        }}
      >
        {button}
      </button>
      {open && (
        <div
          id={panelId}
          role="group"
          aria-label={panelLabel}
          className={`absolute top-full z-50 pt-3 ${align === 'right' ? 'right-0' : 'left-0'}`}
        >
          <div className="glass-panel w-[min(calc(100vw-2rem),34rem)] rounded-3xl border border-white/60 p-3 text-slate-800 shadow-2xl ring-1 ring-slate-900/5 sm:p-4">
            {children}
          </div>
        </div>
      )}
    </div>
  );
}
