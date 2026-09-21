import React, { useState, useEffect } from 'react';
import { useTravel } from '../../context/TravelContext';
import { useSpeechRecognition } from '../../hooks/useSpeechRecognition';
import { 
  Search, 
  Mic, 
  MicOff, 
  X, 
  Sparkles, 
  Type, 
  Volume2,
  SlidersHorizontal
} from 'lucide-react';

interface SearchBoxProps {
  value: string;
  onChange: (value: string) => void;
  onSearch: (query: string) => void;
  placeholder?: string;
  suggestions?: string[];
  variant?: 'hero' | 'page' | 'header';
  autoFocus?: boolean;
}

const DEFAULT_SUGGESTIONS_VI = [
  'Vinpearl Nha Trang',
  'VinWonders Phú Quốc',
  'Combo 3N2Đ tiết kiệm',
  'Villa ven biển',
  'Vé máy bay Hà Nội - Đà Nẵng'
];

const DEFAULT_SUGGESTIONS_EN = [
  'Vinpearl Nha Trang',
  'VinWonders Phu Quoc',
  '3D2N Combo Deals',
  'Beachfront Villa',
  'Hanoi - Da Nang Flight'
];

export const SearchBox: React.FC<SearchBoxProps> = ({
  value,
  onChange,
  onSearch,
  placeholder,
  suggestions,
  variant = 'hero',
  autoFocus = false
}) => {
  const { currentLocale, showToast } = useTravel();
  const [isLargeTextMode, setIsLargeTextMode] = useState<boolean>(() => {
    try {
      return localStorage.getItem('vota_elder_text_mode') === 'true';
    } catch {
      return false;
    }
  });

  const isVi = currentLocale === 'vi';
  const defaultPlaceholder = isVi
    ? 'Nhập địa điểm hoặc từ khóa: "Nghỉ dưỡng biển", "VinWonders", "Khách sạn 5 sao"...'
    : 'Enter destination or keywords: "Beach resort", "VinWonders", "5-star hotel"...';

  const defaultList = isVi ? DEFAULT_SUGGESTIONS_VI : DEFAULT_SUGGESTIONS_EN;
  const effectiveSuggestions = suggestions && suggestions.length > 0 
    ? suggestions 
    : (variant !== 'header' ? defaultList : []);

  // Speech Recognition for Elder & Hands-free users
  const speechLang = isVi ? 'vi-VN' : 'en-US';
  const {
    isListening,
    transcript,
    interimTranscript,
    isSupported,
    startListening,
    stopListening
  } = useSpeechRecognition({
    lang: speechLang,
    onFinalResult: (text) => {
      if (text.trim()) {
        onChange(text.trim());
        showToast(
          isVi 
            ? `Đã nhận diện giọng nói: "${text.trim()}"` 
            : `Voice recognized: "${text.trim()}"`
        );
        // Traditional user flow: trigger search on final result
        onSearch(text.trim());
      }
    },
    onError: (err) => {
      showToast(err);
    }
  });

  const toggleLargeTextMode = () => {
    const next = !isLargeTextMode;
    setIsLargeTextMode(next);
    try {
      localStorage.setItem('vota_elder_text_mode', String(next));
    } catch {
      // ignore
    }
    showToast(
      next
        ? (isVi ? 'Đã bật chế độ chữ lớn cho người cao tuổi' : 'Elder-friendly large text mode enabled')
        : (isVi ? 'Đã chuyển về cỡ chữ tiêu chuẩn' : 'Standard text mode restored')
    );
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!value.trim()) return;
    onSearch(value.trim());
  };

  const handleClear = () => {
    onChange('');
  };

  const handleMicToggle = () => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  };

  const isHero = variant === 'hero';

  return (
    <div className="w-full space-y-3">
      {/* Top Elder / Accessibility Bar (Hero Variant) */}
      {isHero && (
        <div className="flex items-center justify-between text-xs text-slate-500 px-1">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-slate-700 flex items-center gap-1">
              <Sparkles className="w-3.5 h-3.5 text-blue-600" />
              <span>{isVi ? 'Tìm kiếm thông minh đa thế hệ' : 'Multi-generational Smart Search'}</span>
            </span>
          </div>

          <button
            type="button"
            onClick={toggleLargeTextMode}
            className={`px-2.5 py-1 rounded-lg text-xs font-bold transition-colors flex items-center gap-1.5 border ${
              isLargeTextMode
                ? 'bg-amber-100 text-amber-900 border-amber-300 shadow-2xs'
                : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50 hover:text-slate-900'
            }`}
            title={isVi ? 'Bật/Tắt cỡ chữ lớn cho người lớn tuổi dễ đọc' : 'Toggle large text for seniors'}
          >
            <Type className="w-3.5 h-3.5" />
            <span>
              {isLargeTextMode 
                ? (isVi ? 'Chữ to: ĐANG BẬT' : 'Large Text: ON') 
                : (isVi ? 'Chữ to cho người cao tuổi' : 'Senior Large Font')}
            </span>
          </button>
        </div>
      )}

      {/* Main Search Bar Form */}
      <form onSubmit={handleSubmit} className="relative group">
        <div
          className={`relative flex items-center bg-white rounded-2xl border-2 transition-all shadow-md ${
            isListening 
              ? 'border-red-500 ring-4 ring-red-100' 
              : 'border-slate-300 hover:border-blue-400 focus-within:border-blue-600 focus-within:ring-4 focus-within:ring-blue-100'
          } ${isLargeTextMode ? 'p-2 sm:p-2.5' : 'p-1.5 sm:p-2'}`}
        >
          {/* Text Input */}
          <input
            type="text"
            value={value}
            autoFocus={autoFocus}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder || defaultPlaceholder}
            className={`w-full pl-4 sm:pl-5 pr-3 bg-transparent text-slate-900 placeholder:text-slate-400 outline-hidden font-medium ${
              isLargeTextMode 
                ? 'text-base sm:text-lg py-3 placeholder:text-slate-500' 
                : isHero 
                  ? 'text-sm sm:text-base py-2.5' 
                  : 'text-sm py-2'
            }`}
          />

          {/* Actions on the right side of the input (Voice Mic & Clear Button) */}
          <div className="flex items-center gap-1.5 pr-2 shrink-0">
            {/* Clear Text button */}
            {value && (
              <button
                type="button"
                onClick={handleClear}
                className="p-2 text-slate-400 hover:text-slate-600 rounded-full hover:bg-slate-100 transition-colors"
                title={isVi ? 'Xóa nội dung' : 'Clear input'}
              >
                <X className="w-4 h-4" />
              </button>
            )}

            {/* Voice Search Button (crucial for elder persons) */}
            {isSupported && (
              <button
                type="button"
                onClick={handleMicToggle}
                className={`p-2.5 rounded-xl font-bold transition-all flex items-center gap-1.5 border ${
                  isListening
                    ? 'bg-red-600 text-white border-red-700 animate-pulse shadow-md'
                    : 'bg-slate-100 hover:bg-blue-50 text-slate-700 hover:text-blue-700 border-slate-200 hover:border-blue-200'
                }`}
                title={
                  isVi 
                    ? 'Tìm bằng giọng nói (Rất tiện lợi cho người cao tuổi)' 
                    : 'Voice search (Elder-friendly speech input)'
                }
              >
                {isListening ? (
                  <>
                    <Mic className="w-4 h-4 animate-bounce" />
                    <span className="text-[11px] font-bold hidden sm:inline-block">
                      {isVi ? 'Đang nghe...' : 'Listening...'}
                    </span>
                  </>
                ) : (
                  <>
                    <Mic className="w-4 h-4 text-slate-600 hover:text-blue-600" />
                    <span className="text-[11px] font-semibold text-slate-600 hidden md:inline-block">
                      {isVi ? 'Nói' : 'Voice'}
                    </span>
                  </>
                )}
              </button>
            )}

            {/* Search Button (Solid blue, icon only) */}
            <button
              type="submit"
              className={`relative overflow-hidden font-black rounded-xl transition-all shadow-md active:scale-95 flex items-center justify-center shrink-0 bg-blue-600 hover:bg-blue-700 text-white focus:ring-4 focus:ring-blue-300 ${
                isLargeTextMode
                  ? 'p-3.5 sm:p-4 min-h-[52px] min-w-[52px]'
                  : isHero
                    ? 'p-3 min-h-[46px] min-w-[46px]'
                    : 'p-2.5 min-h-[42px] min-w-[42px]'
              }`}
              title={
                isVi 
                  ? 'Bấm để tìm kiếm ngay (hoặc nhấn phím Enter trên bàn phím)' 
                  : 'Click to search (or press Enter)'
              }
              aria-label={isVi ? 'Tìm kiếm' : 'Search'}
            >
              {/* Search Icon */}
              <Search className={`${isLargeTextMode ? 'w-6 h-6' : isHero ? 'w-5 h-5' : 'w-4 h-4'} stroke-[2.5] text-white`} />
            </button>
          </div>
        </div>
      </form>

      {/* Voice Listening Transcript Feedback */}
      {isListening && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-800 flex items-center justify-between gap-3 animate-in fade-in duration-200">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-red-600 animate-ping shrink-0" />
            <span>
              {isVi ? 'Xin hãy nói địa điểm hoặc dịch vụ du lịch...' : 'Please say your destination or travel service...'}
              {interimTranscript && (
                <strong className="ml-1.5 font-bold text-red-950">&ldquo;{interimTranscript}&rdquo;</strong>
              )}
            </span>
          </div>
          <button
            type="button"
            onClick={stopListening}
            className="px-2.5 py-1 bg-white border border-red-300 text-red-700 font-bold rounded-lg hover:bg-red-100 transition-colors text-[11px]"
          >
            {isVi ? 'Hoàn tất' : 'Done'}
          </button>
        </div>
      )}

      {/* Suggestion Chips */}
      {effectiveSuggestions.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap text-xs pt-1">
          <span className={`font-semibold text-slate-500 ${isLargeTextMode ? 'text-sm' : 'text-xs'}`}>
            {isVi ? 'Gợi ý tìm kiếm:' : 'Popular searches:'}
          </span>
          {effectiveSuggestions.map((chip, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => {
                onChange(chip);
                onSearch(chip);
              }}
              className={`rounded-full bg-white border border-slate-200 font-medium text-slate-700 hover:bg-blue-50 hover:text-blue-700 hover:border-blue-300 transition-colors shadow-2xs flex items-center gap-1 ${
                isLargeTextMode 
                  ? 'px-3.5 py-1.5 text-sm' 
                  : 'px-3 py-1 text-xs'
              }`}
            >
              <span>{chip}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
