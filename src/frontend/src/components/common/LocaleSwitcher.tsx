import React, { useState, useRef, useEffect } from 'react';
import { Globe, Check, ChevronDown } from 'lucide-react';
import { SupportedLocale, SUPPORTED_LOCALES, LocaleInfo } from '../../types/locale';
import { useTravel } from '../../context/TravelContext';

interface LocaleSwitcherProps {
  variant?: 'header' | 'compact' | 'chat-toolbar';
  className?: string;
}

export const LocaleSwitcher: React.FC<LocaleSwitcherProps> = ({
  variant = 'header',
  className = ''
}) => {
  const { currentLocale, setLocale, showToast } = useTravel();
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const activeLocale = SUPPORTED_LOCALES.find(l => l.code === currentLocale) || SUPPORTED_LOCALES[0];

  // Close on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  const handleSelect = (loc: LocaleInfo) => {
    setLocale(loc.code);
    setIsOpen(false);
    showToast(
      loc.code === 'vi' 
        ? 'Đã chuyển sang Tiếng Việt. Trợ lý sẵn sàng phản hồi bằng Tiếng Việt!' 
        : `Switched language to ${loc.nativeName} (${loc.englishName}). Assistant is now ready in your language!`
    );
  };

  if (variant === 'chat-toolbar') {
    return (
      <div className={`relative inline-block ${className}`} ref={menuRef}>
        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          className="px-2 py-1 rounded-lg bg-white border border-slate-200 hover:border-slate-300 text-slate-700 text-xs font-semibold flex items-center gap-1.5 shadow-2xs hover:bg-slate-50 transition-colors"
          title="Thay đổi ngôn ngữ trò chuyện / Change language"
        >
          <span className="text-sm leading-none">{activeLocale.flag}</span>
          <span className="text-[11px] font-bold">{activeLocale.code.toUpperCase()}</span>
          <ChevronDown className={`w-3 h-3 text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
        </button>

        {isOpen && (
          <div className="absolute left-0 bottom-full mb-1 w-52 bg-white rounded-xl shadow-xl border border-slate-200 py-1.5 z-50 animate-in fade-in zoom-in-95 duration-100 max-h-72 overflow-y-auto">
            <div className="px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-slate-400 border-b border-slate-100 mb-1">
              Ngôn ngữ trợ lý / Language
            </div>
            {SUPPORTED_LOCALES.map((loc) => {
              const isSelected = loc.code === currentLocale;
              return (
                <button
                  key={loc.code}
                  onClick={() => handleSelect(loc)}
                  className={`w-full text-left px-3 py-1.5 text-xs flex items-center justify-between transition-colors ${
                    isSelected 
                      ? 'bg-brand-50 text-brand-700 font-bold' 
                      : 'text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-base">{loc.flag}</span>
                    <div>
                      <div className="font-medium text-xs text-slate-900 leading-tight">
                        {loc.nativeName}
                      </div>
                      <div className="text-[10px] text-slate-400">
                        {loc.englishName}
                      </div>
                    </div>
                  </div>
                  {isSelected && <Check className="w-3.5 h-3.5 text-brand-600" />}
                </button>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  // Header and Compact variants
  return (
    <div className={`relative inline-block ${className}`} ref={menuRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-full text-xs font-semibold text-slate-700 hover:text-brand-600 hover:bg-slate-100 border border-slate-200 transition-colors shadow-2xs"
        aria-label="Chọn ngôn ngữ / Select Language"
        title="Ngôn ngữ / Language"
      >
        <Globe className="w-3.5 h-3.5 text-slate-500" />
        <span className="text-sm leading-none">{activeLocale.flag}</span>
        <span className="font-bold text-[11px] text-slate-800 uppercase tracking-tight">
          {activeLocale.code}
        </span>
        <ChevronDown className={`w-3 h-3 text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute right-0 top-full mt-2 w-64 bg-white rounded-2xl shadow-xl border border-slate-200 p-2 z-50 animate-in fade-in zoom-in-95 duration-100 max-h-84 overflow-y-auto">
          <div className="px-3 py-1.5 flex items-center justify-between border-b border-slate-100 mb-1.5">
            <div className="text-[11px] font-bold text-slate-600 flex items-center gap-1.5">
              <Globe className="w-3.5 h-3.5 text-brand-600" />
              <span>Chọn ngôn ngữ / Language</span>
            </div>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-brand-50 text-brand-700 font-mono font-bold">
              {SUPPORTED_LOCALES.length}
            </span>
          </div>

          <div className="space-y-0.5">
            {SUPPORTED_LOCALES.map((loc) => {
              const isSelected = loc.code === currentLocale;
              return (
                <button
                  key={loc.code}
                  onClick={() => handleSelect(loc)}
                  className={`w-full text-left px-3 py-2 rounded-xl text-xs flex items-center justify-between transition-colors ${
                    isSelected 
                      ? 'bg-brand-50/80 text-brand-700 font-bold border border-brand-200' 
                      : 'text-slate-700 hover:bg-slate-50 border border-transparent'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <span className="text-lg leading-none">{loc.flag}</span>
                    <div>
                      <div className="font-bold text-xs text-slate-900 leading-tight">
                        {loc.nativeName}
                      </div>
                      <div className="text-[10px] text-slate-400 flex items-center gap-1.5">
                        <span>{loc.englishName}</span>
                        <span>·</span>
                        <span className="font-mono text-slate-500 uppercase">{loc.currencyCode}</span>
                      </div>
                    </div>
                  </div>
                  {isSelected && (
                    <div className="w-5 h-5 rounded-full bg-brand-600 text-white flex items-center justify-center">
                      <Check className="w-3 h-3 stroke-[3]" />
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
