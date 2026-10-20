import React, { useEffect, useState } from 'react';
import Image from 'next/image';
import { X } from 'lucide-react';

export function WidgetLauncher({ onOpen }: { onOpen: () => void }) {
  const [showBubble, setShowBubble] = useState(true);
  const [displayedText, setDisplayedText] = useState('');
  const text = 'Muốn mình tư vấn gì đó\nvề du lịch không?';

  useEffect(() => {
    if (!showBubble) return;
    let index = 0;
    const timer = setInterval(() => {
      index += 1;
      setDisplayedText(text.slice(0, index));
      if (index >= text.length) clearInterval(timer);
    }, 50);
    return () => clearInterval(timer);
  }, [showBubble]);

  return (
    // Trên mobile nâng widget lên trên thanh tab dưới (h-14 + safe area), không che các nút tab.
    <div className="fixed bottom-[calc(3.5rem+env(safe-area-inset-bottom)+0.75rem)] right-5 z-40 flex flex-col items-end motion-safe:animate-float md:bottom-5">
      {showBubble && <div className="relative mb-2.5 max-w-60 rounded-2xl border border-slate-100 bg-white shadow-xl">
        <button onClick={onOpen} className="rounded-2xl py-3 pl-4 pr-10 text-left text-sm font-semibold leading-snug text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ai-500">
          <span className="whitespace-pre-line" aria-hidden="true">{displayedText || '\u00a0'}</span><span className="sr-only">{text}</span>
        </button>
        <button onClick={() => setShowBubble(false)} aria-label="Ẩn lời mời trợ lý" className="absolute right-1 top-1 flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100"><X className="h-3.5 w-3.5" aria-hidden="true" /></button>
      </div>}
      <button onClick={onOpen} aria-label="Mở trợ lý du lịch AI" className="relative rounded-2xl transition-transform hover:scale-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ai-500 focus-visible:ring-offset-2">
        <Image src="/mascot_welcome.webp" alt="" width={96} height={96} className="h-20 w-20 select-none object-contain drop-shadow-xl sm:h-24 sm:w-24" />
        <span className="absolute bottom-1 right-2 h-3.5 w-3.5 rounded-full border-2 border-white bg-emerald-500" />
      </button>
    </div>
  );
}
