import React from 'react';
import { Mic, MicOff, Send, X, Globe, Sparkles } from 'lucide-react';

interface VoiceListeningBannerProps {
  isListening: boolean;
  interimTranscript: string;
  transcript: string;
  lang: string;
  onToggleLang: () => void;
  onStop: () => void;
  onSend: () => void;
  onCancel: () => void;
  onSampleClick: (sample: string) => void;
}

const VOICE_SAMPLES = [
  'Lên lịch trình 3 ngày Nha Trang cho gia đình',
  'Gợi ý quán hải sản ngon ở Phú Quốc',
  'Tìm combo khách sạn 5 sao kèm vé VinWonders',
  'Lịch trình 2 ngày Đà Nẵng tránh nắng buổi trưa'
];

export const VoiceListeningBanner: React.FC<VoiceListeningBannerProps> = ({
  isListening,
  interimTranscript,
  transcript,
  lang,
  onToggleLang,
  onStop,
  onSend,
  onCancel,
  onSampleClick
}) => {
  if (!isListening) return null;

  const currentDisplay = interimTranscript || transcript;

  return (
    <div className="mb-2 p-3 bg-gradient-to-r from-rose-50 via-red-50 to-amber-50 border border-rose-200 rounded-2xl shadow-sm text-xs space-y-2.5 animate-in fade-in slide-in-from-bottom-2 duration-200">
      {/* Header with animated visualizer */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          {/* Pulsing Mic Indicator */}
          <div className="relative flex items-center justify-center">
            <span className="absolute w-6 h-6 rounded-full bg-rose-400/40 animate-ping"></span>
            <span className="relative w-6 h-6 rounded-full bg-rose-600 text-white flex items-center justify-center shadow-xs">
              <Mic className="w-3.5 h-3.5" />
            </span>
          </div>

          <div>
            <div className="flex items-center gap-1.5 font-bold text-rose-900">
              <span>Đang lắng nghe giọng nói...</span>
              {/* Animated wave bars */}
              <div className="flex items-center gap-0.5 h-3 ml-1">
                <span className="w-0.5 bg-rose-500 rounded-full animate-pulse h-2"></span>
                <span className="w-0.5 bg-rose-600 rounded-full animate-bounce h-3"></span>
                <span className="w-0.5 bg-rose-500 rounded-full animate-pulse h-2.5"></span>
                <span className="w-0.5 bg-rose-600 rounded-full animate-bounce h-3.5"></span>
                <span className="w-0.5 bg-rose-500 rounded-full animate-pulse h-1.5"></span>
              </div>
            </div>
            <p className="text-[10px] text-rose-700">
              Hãy mô tả chi tiết sở thích, điểm đến hoặc ngân sách của bạn
            </p>
          </div>
        </div>

        {/* Language & Actions */}
        <div className="flex items-center gap-1.5 shrink-0">
          <button
            type="button"
            onClick={onToggleLang}
            className="px-2 py-1 bg-white hover:bg-rose-100/60 border border-rose-200 rounded-lg text-[10px] font-semibold text-rose-800 flex items-center gap-1 transition-colors"
            title="Đổi ngôn ngữ nhận diện giọng nói"
          >
            <Globe className="w-3 h-3 text-rose-500" />
            <span>{lang === 'vi-VN' ? 'VI (Tiếng Việt)' : 'EN (English)'}</span>
          </button>

          <button
            type="button"
            onClick={onCancel}
            className="p-1 text-slate-400 hover:text-slate-700 hover:bg-white rounded-lg transition-colors"
            title="Đóng / Hủy"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Live speech transcription text preview */}
      <div className="bg-white/90 rounded-xl p-2.5 border border-rose-200/80 min-h-[44px] flex items-center shadow-2xs">
        {currentDisplay ? (
          <p className="text-xs text-slate-800 font-medium leading-relaxed italic">
            "{currentDisplay}"
          </p>
        ) : (
          <p className="text-xs text-slate-400 italic">
            Nói vào micro... (Ví dụ: "Lập kế hoạch 3 ngày Phú Quốc cho 2 người")
          </p>
        )}
      </div>

      {/* Spoken prompts suggestions */}
      <div className="space-y-1">
        <div className="flex items-center gap-1 text-[10px] text-rose-800/80 font-medium">
          <Sparkles className="w-3 h-3 text-rose-500" />
          <span>Mẫu câu gợi ý bạn có thể nói hoặc nhấn để áp dụng:</span>
        </div>
        <div className="flex flex-wrap gap-1">
          {VOICE_SAMPLES.map((sample, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => onSampleClick(sample)}
              className="px-2 py-0.5 text-[10px] bg-white/80 hover:bg-white border border-rose-200/80 text-rose-900 rounded-full shadow-2xs transition-colors truncate max-w-[260px]"
            >
              "{sample}"
            </button>
          ))}
        </div>
      </div>

      {/* Action Footer */}
      <div className="flex items-center justify-end gap-2 pt-1 border-t border-rose-200/60">
        <button
          type="button"
          onClick={onStop}
          className="px-3 py-1 bg-white hover:bg-slate-100 border border-slate-300 text-slate-700 font-medium rounded-lg text-xs transition-colors flex items-center gap-1.5"
        >
          <MicOff className="w-3.5 h-3.5 text-slate-500" />
          <span>Dừng ghi âm</span>
        </button>

        <button
          type="button"
          onClick={onSend}
          disabled={!currentDisplay.trim()}
          className="px-3.5 py-1 bg-rose-600 hover:bg-rose-700 disabled:bg-slate-200 text-white font-bold rounded-lg text-xs shadow-xs transition-colors flex items-center gap-1.5"
        >
          <Send className="w-3.5 h-3.5" />
          <span>Gửi yêu cầu này</span>
        </button>
      </div>
    </div>
  );
};
