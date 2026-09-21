'use client';

import React, { useState, useRef, useEffect } from 'react';
import { useTravel } from '../../context/TravelContext';
import { X, Send } from 'lucide-react';

interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
}

export const AiFloatingWidget: React.FC = () => {
  const { navigate, showToast } = useTravel();
  const [isOpen, setIsOpen] = useState(false);
  const [showBubble, setShowBubble] = useState(true);
  const [inputVal, setInputVal] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: '1',
      sender: 'assistant',
      text: 'Xin chào! Mình có thể giúp bạn tìm khách sạn, biệt thự nghỉ dưỡng, đặt vé VinWonders hay gợi ý lịch trình không?'
    }
  ]);
  const chatScrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const fullBubbleText = 'Muốn mình tư vấn gì đó\nvề du lịch không?';
  const [displayedText, setDisplayedText] = useState('');
  const [isTyping, setIsTyping] = useState(true);

  useEffect(() => {
    if (!showBubble || isOpen) return;

    let currentIndex = 0;
    setDisplayedText('');
    setIsTyping(true);

    let timer: NodeJS.Timeout;
    const startTimeout = setTimeout(() => {
      timer = setInterval(() => {
        if (currentIndex < fullBubbleText.length) {
          setDisplayedText(fullBubbleText.slice(0, currentIndex + 1));
          currentIndex++;
        } else {
          setIsTyping(false);
          clearInterval(timer);
        }
      }, 50);
    }, 350);

    return () => {
      clearTimeout(startTimeout);
      if (timer) clearInterval(timer);
    };
  }, [showBubble, isOpen]);

  useEffect(() => {
    if (isOpen) {
      chatScrollRef.current?.scrollTo({ top: chatScrollRef.current.scrollHeight, behavior: 'smooth' });
      inputRef.current?.focus();
    }
  }, [isOpen, messages]);

  const handleSendMessage = () => {
    const text = inputVal.trim();
    if (!text) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      sender: 'user',
      text
    };
    setMessages(prev => [...prev, userMsg]);
    setInputVal('');

    // Simulated AI response
    setTimeout(() => {
      const botMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'assistant',
        text: 'Dạ với chuyến đi này, V-OTA đang có gói ưu đãi độc quyền giảm 30% kèm vé vui chơi miễn phí tại VinWonders! Bạn có muốn tôi hỗ trợ xem chi tiết ưu đãi hoặc lên lịch trình không ạ?'
      };
      setMessages(prev => [...prev, botMsg]);
    }, 700);
  };

  const handleQuickPrompt = (promptText: string) => {
    setInputVal(promptText);
    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      sender: 'user',
      text: promptText
    };
    setMessages(prev => [...prev, userMsg]);

    setTimeout(() => {
      let reply = 'Dạ mình đã ghi nhận yêu cầu và đang tìm các ưu đãi V-OTA hấp dẫn nhất cho bạn!';
      if (promptText.includes('Nha Trang')) {
        reply = 'Dạ tại Nha Trang, V-OTA Resort & Spa Nha Trang Bay đang có mức giá ưu đãi từ 2.294.500 ₫/đêm gồm cano đưa đón 24/7 và buffet sáng!';
      } else if (promptText.includes('Phú Quốc')) {
        reply = 'Dạ tại Phú Quốc, gói VinHolidays Fiesta kết hợp vé VinWonders & Safari trọn gói chỉ từ 1.007.500 ₫/khách!';
      }
      const botMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'assistant',
        text: reply
      };
      setMessages(prev => [...prev, botMsg]);
    }, 600);
  };

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col items-end">
      {/* AI Chat Window Modal */}
      {isOpen && (
        <div className="mb-3 w-80 sm:w-96 bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden transition-all duration-300 animate-in fade-in zoom-in-95 origin-bottom-right">
          {/* Chat Header */}
          <div className="bg-gradient-to-r from-blue-700 to-indigo-600 text-white p-3.5 flex items-center justify-between shadow-xs">
            <div className="flex items-center space-x-2.5">
              <div className="w-10 h-10 flex items-center justify-center">
                <img 
                  src="/mascot_welcome.png" 
                  alt="Trợ lý du lịch V-OTA AI" 
                  className="w-full h-full object-contain" 
                />
              </div>
              <div>
                <div className="text-xs font-bold">Trợ lý du lịch V-OTA AI</div>
                <div className="text-[10px] text-blue-100 flex items-center space-x-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block animate-pulse"></span>
                  <span>Đang trực tuyến</span>
                </div>
              </div>
            </div>
            <div className="flex items-center space-x-1">
              <button 
                onClick={() => {
                  setIsOpen(false);
                  navigate('/assistant');
                }} 
                className="text-white/80 hover:text-white text-[11px] px-2 py-0.5 rounded-md hover:bg-white/15 transition cursor-pointer"
                title="Mở toàn màn hình"
              >
                Mở rộng
              </button>
              <button 
                onClick={() => setIsOpen(false)} 
                className="text-white/80 hover:text-white p-1 rounded-lg hover:bg-white/15 transition cursor-pointer"
                title="Đóng"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Chat Messages Body */}
          <div ref={chatScrollRef} className="p-3.5 space-y-3 max-h-72 overflow-y-auto text-xs bg-slate-50">
            {messages.map((m) => (
              <div 
                key={m.id} 
                className={`flex items-start space-x-2 ${m.sender === 'user' ? 'justify-end' : ''}`}
              >
                {m.sender === 'assistant' && (
                  <div className="w-8 h-8 shrink-0 flex items-center justify-center">
                    <img 
                      src="/mascot_welcome.png" 
                      alt="AI" 
                      className="w-full h-full object-contain" 
                    />
                  </div>
                )}
                <div 
                  className={`p-2.5 rounded-2xl text-xs leading-relaxed shadow-xs ${
                    m.sender === 'user'
                      ? 'bg-blue-600 text-white rounded-tr-none max-w-[80%]'
                      : 'bg-white border border-slate-200 text-slate-700 rounded-tl-none max-w-[85%]'
                  }`}
                >
                  {m.text}
                </div>
              </div>
            ))}
          </div>

          {/* Quick prompts */}
          <div className="px-3 py-1.5 flex gap-1.5 overflow-x-auto no-scrollbar text-[11px] bg-slate-50 border-t border-slate-100">
            <button 
              onClick={() => handleQuickPrompt('Khách sạn ở Nha Trang giá tốt')} 
              className="whitespace-nowrap px-2.5 py-1 bg-blue-50 text-blue-700 rounded-full hover:bg-blue-100 transition font-medium cursor-pointer border border-blue-200/60"
            >
              🏨 KS Nha Trang
            </button>
            <button 
              onClick={() => handleQuickPrompt('Combo VinWonders Phú Quốc')} 
              className="whitespace-nowrap px-2.5 py-1 bg-blue-50 text-blue-700 rounded-full hover:bg-blue-100 transition font-medium cursor-pointer border border-blue-200/60"
            >
              🎢 Combo Phú Quốc
            </button>
            <button 
              onClick={() => handleQuickPrompt('Lên lịch trình 3N2Đ')} 
              className="whitespace-nowrap px-2.5 py-1 bg-indigo-50 text-indigo-700 rounded-full hover:bg-indigo-100 transition font-medium cursor-pointer border border-indigo-200/60"
            >
              ✨ Lịch trình 3N2Đ
            </button>
          </div>

          {/* Chat Input Area */}
          <div className="p-2.5 bg-white border-t border-slate-200 flex items-center space-x-1.5">
            <input 
              ref={inputRef}
              type="text" 
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              placeholder="Nhập câu hỏi cho AI..." 
              className="flex-1 bg-slate-100 text-xs px-3 py-2 rounded-xl focus:outline-none focus:ring-1 focus:ring-blue-600 text-slate-800 placeholder:text-slate-400"
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  handleSendMessage();
                }
              }}
            />
            <button 
              onClick={handleSendMessage} 
              className="p-2 bg-blue-600 hover:bg-blue-700 active:scale-95 text-white rounded-xl shadow-md transition cursor-pointer"
              title="Gửi"
            >
              <Send className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Floating Chat Trigger Pill & Mascot Button */}
      <div className="flex flex-col items-end animate-float">
        {/* Chat Bubble Prompt */}
        {showBubble && !isOpen && (
          <div 
            onClick={() => setIsOpen(true)}
            className="group relative mb-2.5 bg-white text-slate-800 text-xs font-semibold pl-3.5 pr-7 py-2.5 rounded-2xl shadow-xl border border-slate-100/90 cursor-pointer hover:shadow-2xl transition-all duration-200 hover:-translate-y-0.5 text-left max-w-[210px]"
          >
            <div className="leading-snug whitespace-pre-line">
              <span>{displayedText}</span>
              {isTyping && (
                <span className="inline-block w-0.5 h-3 bg-blue-600 ml-0.5 animate-pulse align-middle" />
              )}
            </div>
            <button 
              onClick={(e) => {
                e.stopPropagation();
                setShowBubble(false);
              }} 
              className="absolute top-2 right-2 text-slate-400 hover:text-slate-600 p-0.5 rounded-full hover:bg-slate-100 cursor-pointer" 
              title="Đóng"
            >
              <X className="w-3 h-3" />
            </button>

            {/* Speech bubble tail pointer pointing down to mascot */}
            <div className="absolute -bottom-1.5 right-8 sm:right-10 w-3 h-3 bg-white border-r border-b border-slate-100/90 transform rotate-45 pointer-events-none" />
          </div>
        )}

        {/* Mascot Avatar Button */}
        <button 
          onClick={() => setIsOpen(!isOpen)} 
          className="relative transition-transform hover:scale-105 active:scale-95 cursor-pointer focus:outline-none"
          aria-label="Mở trợ lý du lịch AI"
        >
          <img 
            src="/mascot_welcome.png" 
            alt="Mascot V-OTA" 
            className="w-20 h-20 sm:w-24 sm:h-24 object-contain select-none drop-shadow-xl" 
          />
          <span className="absolute bottom-1 right-2 w-3.5 h-3.5 bg-emerald-500 border-2 border-white rounded-full shadow-xs"></span>
        </button>
      </div>
    </div>
  );
};
