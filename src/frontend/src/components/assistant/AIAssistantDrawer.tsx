import React, { useState, useEffect, useRef } from 'react';
import { useTravel } from '../../context/TravelContext';
import { useSpeechRecognition } from '../../hooks/useSpeechRecognition';
import { 
  Sparkles, 
  X, 
  Send, 
  Mic, 
  Maximize2, 
  MapPin, 
  Calendar, 
  Compass, 
  ArrowRight, 
  Hotel, 
  Plane, 
  Ticket, 
  Check, 
  Loader2,
  Bot
} from 'lucide-react';

interface AIAssistantDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

interface DrawerMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  timestamp: string;
  quickActions?: Array<{ label: string; action: () => void }>;
}

export const AIAssistantDrawer: React.FC<AIAssistantDrawerProps> = ({ isOpen, onClose }) => {
  const { currentPersona, currentLocale, navigate, addToCart, showToast } = useTravel();
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<DrawerMessage[]>([
    {
      id: 'welcome',
      sender: 'assistant',
      text: currentPersona 
        ? `Xin chào ${currentPersona.name}! Mình là Trợ lý Du lịch AI của V-OTA. Mình có thể hỗ trợ bạn lên lịch trình, tìm khách sạn, so sánh giá vé và tối ưu chuyến đi theo nhu cầu riêng của bạn.`
        : 'Xin chào! Mình là Trợ lý Du lịch AI của V-OTA. Hãy cho mình biết bạn muốn đi đâu, đi cùng ai hoặc ngân sách dự kiến, mình sẽ gợi ý lịch trình và dịch vụ phù hợp nhất!',
      timestamp: 'Vừa xong'
    }
  ]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => {
        inputRef.current?.focus();
      }, 200);
    }
  }, [isOpen]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  // Voice recognition
  const speechLang = currentLocale === 'vi' ? 'vi-VN' : 'en-US';
  const { isListening, startListening, stopListening, isSupported } = useSpeechRecognition({
    lang: speechLang,
    onFinalResult: (text) => {
      if (text.trim()) {
        setInput(text.trim());
        handleSend(text.trim());
      }
    }
  });

  const handleSend = async (textToSend?: string) => {
    const query = (textToSend || input).trim();
    if (!query || loading) return;

    const userMsg: DrawerMessage = {
      id: Date.now().toString(),
      sender: 'user',
      text: query,
      timestamp: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
    };

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const response = await fetch('/api/assistant/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: query,
          conversationHistory: messages.map(m => ({
            sender: m.sender,
            text: m.text
          })),
          locale: currentLocale
        })
      });

      if (!response.ok) {
        throw new Error('Không thể kết nối với Trợ lý AI');
      }

      const data = await response.json();
      const assistantMsg: DrawerMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'assistant',
        text: data.reply || 'Mình đã tìm thấy thông tin phù hợp cho chuyến đi của bạn!',
        timestamp: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }),
        quickActions: data.plan ? [
          {
            label: 'Xem chi tiết lịch trình đầy đủ →',
            action: () => {
              onClose();
              navigate('/assistant');
            }
          }
        ] : undefined
      };

      setMessages(prev => [...prev, assistantMsg]);
    } catch (err) {
      setMessages(prev => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          sender: 'assistant',
          text: `Dạ mình gợi ý nhanh các dịch vụ nổi bật tại Nha Trang & Phú Quốc cho bạn: Khách sạn 5 sao mặt biển, vé VinWonders ưu đãi và combo bay trọn gói. Bạn muốn xem chi tiết theo ngân sách nào ạ?`,
          timestamp: 'Vừa xong',
          quickActions: [
            {
              label: 'Mở trang Trợ lý đầy đủ',
              action: () => {
                onClose();
                navigate('/assistant');
              }
            }
          ]
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div 
        onClick={onClose}
        className="absolute inset-0 bg-slate-900/40 backdrop-blur-xs transition-opacity animate-in fade-in duration-200"
      />

      {/* Drawer Body */}
      <div className="absolute inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-md md:max-w-lg bg-white shadow-2xl border-l border-slate-200 flex flex-col animate-in slide-in-from-right duration-300">
          {/* Header */}
          <div className="p-4 sm:p-5 border-b border-slate-200 bg-gradient-to-r from-blue-50/80 via-indigo-50/40 to-white flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white shadow-xs">
                <Sparkles className="w-4 h-4" />
              </div>
              <div>
                <div className="flex items-center gap-1.5">
                  <h3 className="text-sm font-bold text-slate-900">Trợ lý AI V-OTA</h3>
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                </div>
                <p className="text-[11px] text-slate-500">
                  Tư vấn lịch trình, so sánh giá & tối ưu chuyến đi
                </p>
              </div>
            </div>

            <div className="flex items-center gap-1">
              <button
                onClick={() => {
                  onClose();
                  navigate('/assistant');
                }}
                className="p-2 text-slate-500 hover:text-blue-600 hover:bg-slate-100 rounded-lg transition-colors"
                title="Mở toàn màn hình"
              >
                <Maximize2 className="w-4 h-4" />
              </button>
              <button
                onClick={onClose}
                className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
                title="Đóng"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Quick AI Capability Chips */}
          <div className="px-4 py-2.5 bg-slate-50 border-b border-slate-200 flex items-center gap-1.5 overflow-x-auto scrollbar-none text-[11px]">
            {[
              { label: '🗓️ Lên lịch trình', query: 'Gợi ý lịch trình 3 ngày 2 đêm ở Nha Trang cho gia đình' },
              { label: '🏨 Tìm khách sạn', query: 'Khách sạn 5 sao view biển đẹp ở Phú Quốc' },
              { label: '💰 So sánh combo', query: 'Combo tiết kiệm bay + phòng ở Đà Nẵng' },
              { label: '🎡 Vé VinWonders', query: 'Vé VinWonders Nha Trang trọn gói cáp treo' }
            ].map((cap, idx) => (
              <button
                key={idx}
                onClick={() => handleSend(cap.query)}
                className="px-2.5 py-1 rounded-full bg-white border border-slate-200 text-slate-700 hover:border-blue-400 hover:text-blue-700 whitespace-nowrap transition-colors shadow-2xs font-medium"
              >
                {cap.label}
              </button>
            ))}
          </div>

          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-4">
            {messages.map((m) => (
              <div 
                key={m.id}
                className={`flex gap-2.5 ${m.sender === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {m.sender === 'assistant' && (
                  <div className="w-7 h-7 rounded-lg bg-indigo-600 text-white flex items-center justify-center shrink-0 mt-0.5 shadow-2xs">
                    <Bot className="w-4 h-4" />
                  </div>
                )}

                <div className={`max-w-[85%] rounded-2xl p-3.5 text-xs sm:text-sm leading-relaxed ${
                  m.sender === 'user'
                    ? 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-tr-xs shadow-xs'
                    : 'bg-slate-100 text-slate-800 rounded-tl-xs border border-slate-200/80'
                }`}>
                  <p className="whitespace-pre-line">{m.text}</p>
                  
                  {m.quickActions && m.quickActions.length > 0 && (
                    <div className="mt-3 pt-2.5 border-t border-slate-200/60 space-y-1.5">
                      {m.quickActions.map((act, aIdx) => (
                        <button
                          key={aIdx}
                          onClick={act.action}
                          className="w-full text-left font-bold text-blue-700 hover:text-blue-800 hover:underline flex items-center gap-1 text-xs"
                        >
                          <span>{act.label}</span>
                        </button>
                      ))}
                    </div>
                  )}

                  <span className={`block text-[10px] mt-1.5 text-right ${
                    m.sender === 'user' ? 'text-blue-100' : 'text-slate-400'
                  }`}>
                    {m.timestamp}
                  </span>
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex gap-2.5 items-center text-xs text-slate-500">
                <div className="w-7 h-7 rounded-lg bg-indigo-600 text-white flex items-center justify-center shrink-0">
                  <Bot className="w-4 h-4" />
                </div>
                <div className="bg-slate-100 p-3 rounded-2xl rounded-tl-xs flex items-center gap-2 border border-slate-200/80">
                  <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />
                  <span>Trợ lý AI đang tổng hợp lịch trình & dịch vụ tốt nhất...</span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Footer Input */}
          <div className="p-3 sm:p-4 border-t border-slate-200 bg-white">
            <form 
              onSubmit={(e) => {
                e.preventDefault();
                handleSend();
              }}
              className="relative flex items-center bg-slate-50 rounded-2xl border border-slate-300 focus-within:border-blue-600 focus-within:bg-white focus-within:ring-2 focus-within:ring-blue-100 transition-all p-1.5"
            >
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Nhập yêu cầu: 3 ngày Nha Trang, khách sạn gần biển..."
                className="w-full px-3 py-2 text-xs sm:text-sm text-slate-900 bg-transparent outline-hidden"
              />

              {isSupported && (
                <button
                  type="button"
                  onClick={isListening ? stopListening : startListening}
                  className={`p-2 rounded-xl transition-colors ${
                    isListening ? 'bg-red-500 text-white animate-pulse' : 'text-slate-400 hover:text-slate-700'
                  }`}
                  title="Tìm bằng giọng nói"
                >
                  <Mic className="w-4 h-4" />
                </button>
              )}

              <button
                type="submit"
                disabled={!input.trim() || loading}
                className="p-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed shrink-0 ml-1"
                title="Gửi"
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
            <div className="flex items-center justify-between text-[11px] text-slate-400 mt-2 px-1">
              <span>Được hỗ trợ bởi AI Du lịch V-OTA</span>
              <button
                onClick={() => {
                  onClose();
                  navigate('/assistant');
                }}
                className="text-blue-600 hover:underline font-medium"
              >
                Mở phiên bản đầy đủ →
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
