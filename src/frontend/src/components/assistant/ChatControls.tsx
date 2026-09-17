import React from 'react';
import { 
  Bot, RefreshCw, Mic, Sparkles
} from 'lucide-react';
import { useTravel } from '../../context/TravelContext';
import { LocaleSwitcher } from '../common/LocaleSwitcher';

interface ChatControlsProps {
  onClearChat: () => void;
  isProcessing: boolean;
  isListening?: boolean;
  onToggleVoice?: () => void;
}

export const ChatControls: React.FC<ChatControlsProps> = ({
  onClearChat,
  isProcessing,
  isListening = false,
  onToggleVoice
}) => {
  const { currentLocale } = useTravel();

  return (
    <div className="border-b border-slate-200/80 bg-slate-50/70 px-3.5 py-2.5">
      {/* Top Bar: Title + Locale Switcher + Voice + Clear Chat */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-8 h-8 rounded-xl bg-blue-600 text-white flex items-center justify-center shadow-xs shrink-0">
            <Bot className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <h3 className="text-xs font-bold text-slate-900 truncate">
                {currentLocale === 'vi' ? 'Trợ lý Du lịch AI' : 'AI Travel Assistant'}
              </h3>
              {isListening && (
                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-rose-100 text-rose-700 text-[9px] font-bold animate-pulse">
                  <span className="w-1.5 h-1.5 rounded-full bg-rose-600 animate-ping"></span>
                  {currentLocale === 'vi' ? 'Ghi âm' : 'Listening'}
                </span>
              )}
            </div>
            <p className="text-[10px] text-slate-500 truncate flex items-center gap-1">
              <Sparkles className="w-2.5 h-2.5 text-blue-500 shrink-0" />
              <span>
                {currentLocale === 'vi' 
                  ? 'Tư vấn điểm đến, lịch trình và tối ưu chi phí thông minh' 
                  : 'Smart destination, itinerary & travel guidance'}
              </span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          {/* Quick Locale Switcher for Assistant */}
          <LocaleSwitcher variant="chat-toolbar" />

          {/* Voice Mic Toggle Button */}
          {onToggleVoice && (
            <button
              onClick={onToggleVoice}
              className={`p-1.5 rounded-lg transition-colors flex items-center justify-center cursor-pointer ${
                isListening
                  ? 'bg-rose-500 text-white shadow-xs animate-pulse ring-2 ring-rose-200'
                  : 'text-slate-400 hover:text-rose-600 hover:bg-slate-200/60'
              }`}
              title={isListening 
                ? (currentLocale === 'vi' ? 'Đang lắng nghe... Nhấn để dừng' : 'Listening... Click to stop') 
                : (currentLocale === 'vi' ? 'Bật nhận diện giọng nói (Voice)' : 'Enable Voice Recognition')}
            >
              <Mic className="w-3.5 h-3.5" />
            </button>
          )}

          {/* Reset chat button */}
          <button
            onClick={onClearChat}
            disabled={isProcessing}
            className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 rounded-lg transition-colors cursor-pointer"
            title={currentLocale === 'vi' ? 'Làm mới cuộc trò chuyện' : 'Reset conversation'}
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};
