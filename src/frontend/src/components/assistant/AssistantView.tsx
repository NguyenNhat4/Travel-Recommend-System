'use client';

import React, { useState, useEffect, useRef, useMemo } from 'react';
import dynamic from 'next/dynamic';
import { useSearchParams } from 'next/navigation';
import { useTravel } from '../../context/TravelContext';
import { extractIntent, buildGroundedItinerary } from '../../services/assistant';
import { GroundedPlan, ChatMessage, Destination, TravelIntent, SavedTrip, AgentRole, GeminiModelChoice } from '../../types/travel';
import { ProductCard } from '../common/ProductCard';
import { SavedTripsModal } from './SavedTripsModal';
import { WeatherForecastCard } from './WeatherForecastCard';
import { ChatControls } from './ChatControls';
import { ChatMessageBubble } from './ChatMessageBubble';
import { VoiceListeningBanner } from './VoiceListeningBanner';
import { ShareItineraryModal } from './ShareItineraryModal';
import { SharedTripWelcomeBanner } from './SharedTripWelcomeBanner';
import { getSharedTrip } from '../../services/shareService';
import { useSpeechRecognition } from '../../hooks/useSpeechRecognition';
import { localizePlan, TRANSLATIONS, formatLocalizedCurrency } from '../../services/localization';
import { 
  Bot, Send, Sparkles, RefreshCw, MapPin, Calendar, 
  Users, CheckCircle2, Loader2, ArrowRight, Info, Plus, 
  Utensils, Coffee, Compass, Check, ChevronRight,
  Map, List, Eye, Bookmark, BookmarkCheck, CloudSun,
  Mic, MicOff, X, Share2
} from 'lucide-react';

const ItineraryMap = dynamic(
  () => import('./ItineraryMap').then((module) => module.ItineraryMap),
  { ssr: false },
);

export const AssistantView: React.FC = () => {
  const { currentPersona, activeEvents, addToCart, showToast, navigate, currentLocale } = useTravel();
  const searchParams = useSearchParams();
  const searchParamString = searchParams.toString();

  const t = TRANSLATIONS[currentLocale] || TRANSLATIONS.vi;

  const [inputPrompt, setInputPrompt] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingStep, setProcessingStep] = useState<number>(0); // 1: intent, 2: search, 3: arrange
  const [activePlan, setActivePlan] = useState<GroundedPlan | null>(null);
  const [activeDayTab, setActiveDayTab] = useState<number>(1);
  const [viewMode, setViewMode] = useState<'list' | 'map'>('list');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [showMapWeather, setShowMapWeather] = useState<boolean>(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Derive localized version of active plan for UI display
  const displayPlan = useMemo(() => {
    if (!activePlan) return null;
    return localizePlan(activePlan, currentLocale);
  }, [activePlan, currentLocale]);

  // Browser SpeechRecognition Integration for hands-free travel preference input
  const {
    isSupported: isSpeechSupported,
    isListening,
    interimTranscript,
    error: speechError,
    currentLang: speechLang,
    setCurrentLang: setSpeechLang,
    startListening,
    stopListening,
    toggleListening,
    resetTranscript,
  } = useSpeechRecognition({
    lang: currentLocale === 'en' ? 'en-US' : currentLocale === 'fr' ? 'fr-FR' : 'vi-VN',
    continuous: true,
    interimResults: true,
    onFinalResult: (finalText) => {
      setInputPrompt((prev) => (prev ? `${prev} ${finalText}` : finalText));
    },
    onError: (errMsg) => {
      showToast(errMsg);
    },
  });

  // Sync speech recognition language with current locale
  useEffect(() => {
    const speechLangs: Record<string, string> = {
      vi: 'vi-VN',
      en: 'en-US',
      fr: 'fr-FR',
      ja: 'ja-JP',
      ko: 'ko-KR',
      zh: 'zh-CN',
      de: 'de-DE',
      es: 'es-ES',
      ru: 'ru-RU',
      th: 'th-TH'
    };
    if (speechLangs[currentLocale]) {
      setSpeechLang(speechLangs[currentLocale]);
    }
  }, [currentLocale, setSpeechLang]);

  // Dynamic welcome message updates when locale changes (if conversation is fresh)
  useEffect(() => {
    setMessages(prev => {
      if (prev.length === 1 && prev[0].id === 'msg-welcome') {
        return [{
          ...prev[0],
          text: currentLocale === 'vi'
            ? `Chào ${currentPersona?.name || 'bạn'}! Mình là Trợ lý Du lịch Đa năng V-OTA (Gemini AI). Mình có thể lên kế hoạch chuyến đi theo ngày với 100% sản phẩm thật, giá thật từ kho V-OTA và đặt được ngay.`
            : `Hello ${currentPersona?.name || 'traveler'}! I am your AI Travel Assistant (powered by Gemini). I can design day-by-day travel itineraries with bookable services and instant cart integration.`,
          suggestedFollowUps: currentLocale === 'vi'
            ? [
                '3 ngày Nha Trang cho gia đình có trẻ nhỏ',
                'Cuối tuần Phú Quốc cho cặp đôi',
                'Đà Nẵng 2 ngày nghỉ dưỡng biển'
              ]
            : [
                '3-day Nha Trang trip for family with kids',
                'Weekend in Phu Quoc for couples',
                'Da Nang 2-day beach getaway'
              ]
        }];
      }
      return prev;
    });
  }, [currentLocale, currentPersona]);

  // Local Storage Saved Trips persistence
  const [savedTrips, setSavedTrips] = useState<SavedTrip[]>([]);
  const [isSavedModalOpen, setIsSavedModalOpen] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem('v_ota_saved_trips');
      if (raw) setSavedTrips(JSON.parse(raw));
    } catch (e) {
      console.error('Error loading saved trips from localStorage', e);
    }
  }, []);

  // Social Sharing States
  const [isShareModalOpen, setIsShareModalOpen] = useState(false);
  const [planToShare, setPlanToShare] = useState<GroundedPlan | null>(null);
  const [sharedBannerData, setSharedBannerData] = useState<{
    plan: GroundedPlan;
    senderName?: string;
    note?: string;
  } | null>(null);

  // Initial welcome message or load shared itinerary from URL query
  useEffect(() => {
    // Check if user opened a shared itinerary link
    const urlParams = new URLSearchParams(searchParamString);
    const shareId = urlParams.get('share');
    const shareData = urlParams.get('data');

    if (shareId || shareData) {
      getSharedTrip(shareId || '', shareData || '').then((sharedRecord) => {
        if (sharedRecord && sharedRecord.plan) {
          setActivePlan(sharedRecord.plan);
          setActiveDayTab(1);
          setSharedBannerData({
            plan: sharedRecord.plan,
            senderName: sharedRecord.senderName,
            note: sharedRecord.note
          });

          const sharedWelcomeMsg: ChatMessage = {
            id: 'msg-shared-trip',
            sender: 'assistant',
            text: `Chào ${currentPersona?.name || 'bạn'}! Bạn đang xem lịch trình **"${sharedRecord.plan.title}"** được chia sẻ bởi **${sharedRecord.senderName || 'Người thân'}**. Lịch trình bao gồm ${sharedRecord.plan.days.length} ngày khám phá với ${sharedRecord.plan.bookableProductsCount} dịch vụ thật có thể đặt được ngay!`,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            role: 'general',
            modelUsed: 'gemini-3.5-flash',
            plan: sharedRecord.plan,
            suggestedFollowUps: [
              'Tùy chỉnh lịch trình này cho trẻ nhỏ',
              'Gợi ý thêm quán ăn đặc sản gần đây',
              'Chi phí chuyến đi ước tính bao nhiêu?'
            ]
          };
          setMessages([sharedWelcomeMsg]);
          showToast(`Đã tải lịch trình được chia sẻ: ${sharedRecord.plan.title}`);
          return;
        }
      });
    }

    const welcomeMsg: ChatMessage = {
      id: 'msg-welcome',
      sender: 'assistant',
      text: `Chào ${currentPersona?.name || 'bạn'}! Mình là Trợ lý Du lịch Đa năng V-OTA (Gemini AI). Mình có thể lên kế hoạch chuyến đi theo ngày với 100% sản phẩm thật, giá thật từ kho V-OTA và đặt được ngay.`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      role: 'general',
      modelUsed: 'gemini-3.5-flash',
      suggestedFollowUps: [
        '3 ngày Nha Trang cho gia đình có trẻ nhỏ',
        'Cuối tuần Phú Quốc cho cặp đôi',
        'Đà Nẵng 2 ngày nghỉ dưỡng biển'
      ]
    };
    setMessages([welcomeMsg]);

    // Auto-generate initial plan for Nha Trang if not opened via share link and no incoming query
    if (!shareId && !shareData) {
      const incomingQuery = urlParams.get('q') || urlParams.get('prompt');
      if (!incomingQuery) {
        const initialIntent: TravelIntent = {
          destination: 'Nha Trang',
          days: 3,
          party: 'family_with_kids',
          interests: ['theme_park', 'beach']
        };
        const plan = buildGroundedItinerary(initialIntent, currentPersona, activeEvents);
        setActivePlan(plan);
      }
    }
  }, [searchParamString]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isProcessing]);

  const handleClearChat = () => {
    setMessages([
      {
        id: 'msg-welcome-' + Date.now(),
        sender: 'assistant',
        text: currentLocale === 'vi'
          ? `Chào ${currentPersona?.name || 'bạn'}! Mình đã làm mới hội thoại. Mình có thể giúp bạn lên kế hoạch chuyến đi, gợi ý điểm đến và giải đáp mọi thắc mắc!`
          : `Hello ${currentPersona?.name || 'traveler'}! Conversation reset. How can I help you with your trip planning today?`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        suggestedFollowUps: currentLocale === 'vi' ? [
          '3 ngày Nha Trang cho gia đình có trẻ nhỏ',
          'Cuối tuần Phú Quốc cho cặp đôi',
          'Đà Nẵng 2 ngày nghỉ dưỡng biển'
        ] : [
          '3-day Nha Trang trip for family with kids',
          'Weekend in Phu Quoc for couples',
          'Da Nang 2-day beach getaway'
        ]
      }
    ]);
    showToast(currentLocale === 'vi' ? 'Đã làm mới cuộc hội thoại.' : 'Conversation cleared.');
  };

  const handleSendMessage = async (textToSend?: string) => {
    if (isListening) {
      stopListening();
    }
    const query = textToSend || inputPrompt;
    if (!query.trim() || isProcessing) return;

    const userMsg: ChatMessage = {
      id: 'msg-' + Math.random().toString(36).substring(5),
      sender: 'user',
      text: query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages(prev => [...prev, userMsg]);
    setInputPrompt('');
    resetTranscript();
    setIsProcessing(true);
    setProcessingStep(1);

    try {
      // Step 1: Extract intent locally
      const { intent } = extractIntent(query);
      setProcessingStep(2);

      // Collect conversation history for multi-turn chat
      const historyPayload = messages
        .filter(m => m.sender === 'user' || m.sender === 'assistant')
        .map(m => ({
          role: m.sender === 'user' ? 'user' : 'model',
          text: m.text
        }));

      // Call Gemini multi-turn endpoint
      const response = await fetch('/api/assistant/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: query,
          history: historyPayload,
          role: 'general',
          model: 'auto',
          locale: currentLocale,
          context: {
            destination: intent.destination || activePlan?.intent.destination || 'Nha Trang',
            days: intent.days || activePlan?.intent.days || 3,
            party: intent.party || activePlan?.intent.party || 'family_with_kids',
            activePlanTitle: activePlan?.title || '',
            persona: currentPersona?.name || 'Khách du lịch'
          }
        })
      });

      setProcessingStep(3);

      let data: any = null;
      if (response.ok) {
        data = await response.json();
      }

      // Check if we should update or generate the grounded visual itinerary
      let newPlan: GroundedPlan | null = null;
      const detected = data?.detectedIntent;
      const lowerQuery = query.toLowerCase();
      const shouldUpdatePlan = detected || intent.destination || intent.days || 
        lowerQuery.includes('lịch trình') || lowerQuery.includes('kế hoạch') || lowerQuery.includes('chuyến đi') ||
        lowerQuery.includes('itinerary') || lowerQuery.includes('plan') || lowerQuery.includes('trip') || lowerQuery.includes('schedule');

      if (shouldUpdatePlan) {
        const fullIntent: TravelIntent = {
          destination: detected?.destination || intent.destination || activePlan?.intent.destination || 'Nha Trang',
          days: detected?.days || intent.days || activePlan?.intent.days || 3,
          party: detected?.party || intent.party || activePlan?.intent.party || 'family_with_kids',
          interests: intent.interests || activePlan?.intent.interests || ['theme_park', 'beach']
        };

        newPlan = buildGroundedItinerary(fullIntent, currentPersona, activeEvents);
        setActivePlan(newPlan);
        setActiveDayTab(1);
      }

      const defaultAssistantReply = currentLocale === 'vi'
        ? 'Mình đã xử lý yêu cầu của bạn. Toàn bộ dịch vụ đặt được đã được tối ưu hóa cho chuyến đi!'
        : 'I have processed your request. Verified bookable travel services have been optimized for your journey!';

      const defaultFollowUps = currentLocale === 'vi'
        ? [
            'Tối ưu thêm cho gia đình có trẻ nhỏ',
            'Gợi ý ẩm thực đặc sản buổi tối',
            'Kiểm tra dự báo thời tiết 5 ngày'
          ]
        : [
            'Optimize for families with young children',
            'Recommend local dining for tonight',
            'Check 5-day destination weather'
          ];

      const assistantMsg: ChatMessage = {
        id: 'msg-' + Math.random().toString(36).substring(5),
        sender: 'assistant',
        text: data?.reply || defaultAssistantReply,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        role: (data?.role as AgentRole) || 'general',
        modelUsed: data?.modelUsed || 'gemini-3.5-flash',
        plan: newPlan || undefined,
        suggestedFollowUps: data?.suggestedFollowUps || defaultFollowUps
      };

      setMessages(prev => [...prev, assistantMsg]);
    } catch (err) {
      console.error('Chat error:', err);
      // Graceful fallback
      const { intent } = extractIntent(query);
      const fullIntent: TravelIntent = {
        destination: intent.destination || activePlan?.intent.destination || 'Nha Trang',
        days: intent.days || activePlan?.intent.days || 3,
        party: intent.party || activePlan?.intent.party || 'family_with_kids',
        interests: intent.interests || ['theme_park', 'beach']
      };
      const fallbackPlan = buildGroundedItinerary(fullIntent, currentPersona, activeEvents);
      setActivePlan(fallbackPlan);

      const fallbackMsg: ChatMessage = {
        id: 'msg-' + Math.random().toString(36).substring(5),
        sender: 'assistant',
        text: currentLocale === 'vi'
          ? `Mình đã tối ưu hóa lịch trình ${fallbackPlan.intent.days} ngày tại ${fallbackPlan.intent.destination} cho bạn. Mọi dịch vụ được liên kết trực tiếp với dữ liệu V-OTA!`
          : `I have tailored a ${fallbackPlan.intent.days}-day itinerary in ${fallbackPlan.intent.destination} for you with verified bookable experiences!`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        role: 'general',
        modelUsed: 'gemini-3.5-flash',
        plan: fallbackPlan,
        suggestedFollowUps: currentLocale === 'vi'
          ? [
              'Đổi thành 2 ngày',
              'Thêm hoạt động biển',
              'Gợi ý đặc sản'
            ]
          : [
              'Change to 2 days',
              'Add more beach activities',
              'Suggest culinary specialties'
            ]
      };
      setMessages(prev => [...prev, fallbackMsg]);
    } finally {
      setIsProcessing(false);
      setProcessingStep(0);
    }
  };

  // Handle incoming query from Home AI tab navigation (?q=... or ?prompt=...)
  const handledIncomingQueryRef = useRef<string | null>(null);
  useEffect(() => {
    const urlParams = new URLSearchParams(searchParamString);
    const incomingQuery = urlParams.get('q') || urlParams.get('prompt');
    if (incomingQuery && incomingQuery !== handledIncomingQueryRef.current) {
      handledIncomingQueryRef.current = incomingQuery;
      handleSendMessage(incomingQuery);
    }
  }, [searchParamString]);

  const handleAddAllToCart = () => {
    if (!activePlan) return;
    let addedCount = 0;

    // Add stay
    if (activePlan.stay) {
      addToCart(activePlan.stay.product, 1);
      addedCount++;
    }

    // Add attractions & combos
    activePlan.days.forEach(day => {
      day.slots.forEach(slot => {
        if (slot.product && !slot.isActivityNote) {
          addToCart(slot.product, 2);
          addedCount++;
        }
      });
    });

    showToast(`Đã thêm ${addedCount} dịch vụ từ lịch trình vào giỏ hàng!`, 'Xem giỏ', () => navigate('/cart'));
  };

  // Helper to check if the currently active plan is saved
  const isCurrentTripSaved = activePlan 
    ? savedTrips.some(st => st.plan.title === activePlan.title && st.plan.intent.destination === activePlan.intent.destination)
    : false;

  // Toggle saving / unsaving a trip to localStorage
  const handleToggleSaveTrip = (planToSave?: GroundedPlan) => {
    const targetPlan = planToSave || activePlan;
    if (!targetPlan) return;

    const isSaved = savedTrips.some(
      st => st.plan.title === targetPlan.title && st.plan.intent.destination === targetPlan.intent.destination
    );

    if (isSaved) {
      const updated = savedTrips.filter(
        st => !(st.plan.title === targetPlan.title && st.plan.intent.destination === targetPlan.intent.destination)
      );
      setSavedTrips(updated);
      try {
        localStorage.setItem('v_ota_saved_trips', JSON.stringify(updated));
      } catch (e) {
        console.error('Error saving to localStorage', e);
      }
      showToast(`Đã hủy lưu chuyến đi "${targetPlan.title}".`);
    } else {
      const newEntry: SavedTrip = {
        id: 'trip-' + Date.now() + '-' + Math.random().toString(36).substring(5),
        savedAt: new Date().toISOString(),
        plan: targetPlan
      };
      const updated = [newEntry, ...savedTrips];
      setSavedTrips(updated);
      try {
        localStorage.setItem('v_ota_saved_trips', JSON.stringify(updated));
      } catch (e) {
        console.error('Error saving to localStorage', e);
      }
      showToast(`Đã lưu chuyến đi "${targetPlan.title}" vào danh sách!`);
    }
  };

  const handleDeleteSavedTrip = (id: string) => {
    const updated = savedTrips.filter(st => st.id !== id);
    setSavedTrips(updated);
    try {
      localStorage.setItem('v_ota_saved_trips', JSON.stringify(updated));
    } catch (e) {
      console.error('Error saving to localStorage', e);
    }
    showToast('Đã xóa chuyến đi khỏi danh sách lưu.');
  };

  const handleSelectSavedTrip = (plan: GroundedPlan) => {
    setActivePlan(plan);
    setActiveDayTab(1);
    showToast(`Đã tải lại lịch trình: ${plan.title}`);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-4">
      {/* Top Banner */}
      <div className="p-4 bg-gradient-to-r from-blue-900 to-indigo-900 text-white rounded-2xl shadow-md flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-blue-500/30 flex items-center justify-center text-indigo-300">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white">
              {t.aiAssistantTitle}
            </h2>
            <p className="text-xs text-blue-200">
              {t.aiAssistantSubtitle}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-end sm:self-auto">
          {/* Saved Trips Button */}
          <button
            onClick={() => setIsSavedModalOpen(true)}
            className="px-3 py-1.5 bg-white/10 hover:bg-white/20 text-white text-xs font-semibold rounded-lg border border-white/20 transition-colors flex items-center gap-1.5 shadow-2xs"
            title={t.savedTrips}
          >
            <Bookmark className="w-3.5 h-3.5 fill-white/30" />
            <span>{t.savedTrips}</span>
            {savedTrips.length > 0 && (
              <span className="ml-0.5 px-1.5 py-0.2 bg-blue-500 text-white text-[10px] font-extrabold rounded-full">
                {savedTrips.length}
              </span>
            )}
          </button>

          {/* Share Itinerary Button */}
          {activePlan && (
            <button
              onClick={() => {
                setPlanToShare(activePlan);
                setIsShareModalOpen(true);
              }}
              className="px-3 py-1.5 bg-indigo-600/90 hover:bg-indigo-600 text-white text-xs font-semibold rounded-lg border border-indigo-400/40 transition-colors flex items-center gap-1.5 shadow-2xs"
              title={t.share}
            >
              <Share2 className="w-3.5 h-3.5" />
              <span>{t.share}</span>
            </button>
          )}

          <button
            onClick={() => {
              setMessages([]);
              setActivePlan(null);
              setSharedBannerData(null);
              showToast(currentLocale === 'vi' ? 'Đã làm mới cuộc hội thoại.' : 'Conversation reset.');
            }}
            className="px-3 py-1.5 bg-white/10 hover:bg-white/20 text-white text-xs font-semibold rounded-lg border border-white/20 transition-colors flex items-center gap-1.5"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>{currentLocale === 'vi' ? 'Cuộc mới' : 'New Chat'}</span>
          </button>
        </div>
      </div>

      {/* Shared Trip Welcome Banner (When opened via a shared URL) */}
      {sharedBannerData && (
        <SharedTripWelcomeBanner
          plan={sharedBannerData.plan}
          senderName={sharedBannerData.senderName}
          note={sharedBannerData.note}
          isSaved={isCurrentTripSaved}
          onSave={() => handleToggleSaveTrip(sharedBannerData.plan)}
          onAddAllToCart={handleAddAllToCart}
          onShareAgain={() => {
            setPlanToShare(sharedBannerData.plan);
            setIsShareModalOpen(true);
          }}
          onDismiss={() => setSharedBannerData(null)}
        />
      )}

      {/* Main Split Screen: Chat (40%) + Itinerary Plan (60%) on Desktop */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start h-[750px]">
        {/* Left Column: Chat Assistant (40% / 5 cols) */}
        <div className="lg:col-span-5 bg-white rounded-2xl border border-slate-200 shadow-xs flex flex-col h-full overflow-hidden">
          {/* Chat Controls (Title, Locale Switcher, Voice & Reset) */}
          <ChatControls
            onClearChat={handleClearChat}
            isProcessing={isProcessing}
            isListening={isListening}
            onToggleVoice={() => {
              if (!isSpeechSupported) {
                showToast('Trình duyệt chưa hỗ trợ Web Speech API. Vui lòng dùng Chrome hoặc Edge.');
                return;
              }
              toggleListening();
            }}
          />

          {/* Messages Scroll Area */}
          <div className="flex-1 p-4 overflow-y-auto space-y-4">
            {messages.map(msg => (
              <ChatMessageBubble
                key={msg.id}
                message={msg}
                savedTrips={savedTrips}
                onSelectPlan={(plan, view) => {
                  setActivePlan(plan);
                  setViewMode(view);
                }}
                onToggleSaveTrip={handleToggleSaveTrip}
                onSelectFollowUp={handleSendMessage}
                onSharePlan={(plan) => {
                  setPlanToShare(plan);
                  setIsShareModalOpen(true);
                }}
              />
            ))}

            {/* 3-Step Progress Indicator (§6.1) */}
            {isProcessing && (
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-2.5 text-xs text-slate-700">
                <div className="font-bold text-slate-900 flex items-center gap-2">
                  <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />
                  <span>{t.processing}</span>
                </div>
                <div className="space-y-1.5 pl-6">
                  <div className={`flex items-center gap-2 ${processingStep >= 1 ? 'text-blue-700 font-semibold' : 'text-slate-400'}`}>
                    {processingStep > 1 ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <span className="w-1.5 h-1.5 rounded-full bg-blue-600"></span>}
                    <span>{t.step1}</span>
                  </div>
                  <div className={`flex items-center gap-2 ${processingStep >= 2 ? 'text-blue-700 font-semibold' : 'text-slate-400'}`}>
                    {processingStep > 2 ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <span className="w-1.5 h-1.5 rounded-full bg-blue-600"></span>}
                    <span>{t.step2}</span>
                  </div>
                  <div className={`flex items-center gap-2 ${processingStep >= 3 ? 'text-blue-700 font-semibold' : 'text-slate-400'}`}>
                    <span className="w-1.5 h-1.5 rounded-full bg-blue-600 animate-ping"></span>
                    <span>{t.step3}</span>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Chat Input */}
          <div className="p-3 bg-white border-t border-slate-100">
            {/* Voice Dictation Live Banner */}
            <VoiceListeningBanner
              isListening={isListening}
              interimTranscript={interimTranscript}
              transcript={inputPrompt}
              lang={speechLang}
              onToggleLang={() => setSpeechLang(speechLang === 'vi-VN' ? 'en-US' : 'vi-VN')}
              onStop={stopListening}
              onSend={() => {
                stopListening();
                const sendText = (inputPrompt.trim() + ' ' + interimTranscript.trim()).trim();
                if (sendText) {
                  handleSendMessage(sendText);
                }
              }}
              onCancel={() => {
                stopListening();
                resetTranscript();
              }}
              onSampleClick={(sample) => {
                setInputPrompt(sample);
                stopListening();
              }}
            />

            <form onSubmit={(e) => { e.preventDefault(); handleSendMessage(); }} className="flex items-center gap-2">
              <div className="relative flex-1 flex items-center">
                <input
                  type="text"
                  value={inputPrompt}
                  onChange={(e) => setInputPrompt(e.target.value)}
                  placeholder={
                    isListening
                      ? (currentLocale === 'vi' ? 'Đang lắng nghe... Hãy nói yêu cầu của bạn' : 'Listening... Speak your request')
                      : t.inputPlaceholder
                  }
                  className={`w-full px-3.5 py-2.5 pr-9 text-xs sm:text-sm border rounded-xl outline-hidden transition-all ${
                    isListening
                      ? 'border-rose-400 ring-2 ring-rose-200 bg-rose-50/40 placeholder:text-rose-400'
                      : 'border-slate-300 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white'
                  }`}
                />
                {inputPrompt && !isProcessing && (
                  <button
                    type="button"
                    onClick={() => { setInputPrompt(''); resetTranscript(); }}
                    className="absolute right-2.5 p-1 text-slate-400 hover:text-slate-600 rounded-full hover:bg-slate-100 transition-colors"
                    title="Xóa nội dung"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>

              {/* Voice Dictation Button */}
              <button
                type="button"
                onClick={() => {
                  if (!isSpeechSupported) {
                    showToast(currentLocale === 'vi' ? 'Trình duyệt chưa hỗ trợ Web Speech API. Vui lòng dùng Chrome hoặc Edge!' : 'Browser does not support Web Speech API. Please use Chrome or Edge.');
                    return;
                  }
                  toggleListening();
                }}
                className={`p-2.5 rounded-xl transition-all flex items-center justify-center shrink-0 ${
                  isListening
                    ? 'bg-rose-600 text-white shadow-md animate-pulse ring-2 ring-rose-300 hover:bg-rose-700'
                    : 'bg-slate-100 hover:bg-slate-200 text-slate-700 hover:text-rose-600'
                }`}
                title={
                  !isSpeechSupported
                    ? (currentLocale === 'vi' ? 'Trình duyệt chưa hỗ trợ giọng nói' : 'Speech recognition not supported')
                    : isListening
                    ? (currentLocale === 'vi' ? 'Đang lắng nghe... Nhấn để dừng' : 'Listening... Click to stop')
                    : (currentLocale === 'vi' ? 'Nói để mô tả yêu cầu du lịch' : 'Speak your travel request')
                }
              >
                {isListening ? (
                  <Mic className="w-4 h-4 text-white animate-bounce" />
                ) : (
                  <Mic className="w-4 h-4" />
                )}
              </button>

              <button
                type="submit"
                disabled={!inputPrompt.trim() || isProcessing}
                className="p-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-200 text-white rounded-xl shadow-xs transition-colors shrink-0"
                title={t.send}
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
            <p className="text-[10px] text-slate-400 text-center mt-2">
              Gemini AI tích hợp kho dữ liệu du lịch Việt Nam 100% thời gian thực.
            </p>
          </div>
        </div>

        {/* Right Column: Grounded Itinerary Plan (60% / 7 cols) */}
        <div className="lg:col-span-7 bg-white rounded-2xl border border-slate-200 shadow-xs flex flex-col h-full overflow-hidden">
          {displayPlan ? (
            <div className="flex flex-col h-full">
              {/* Plan Header with Editable Intent Chips (§6.2) */}
              <div className="p-5 border-b border-slate-100 bg-slate-50/80 space-y-3">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <div>
                    <h3 className="text-base font-black text-slate-900 tracking-tight">
                      {displayPlan.title}
                    </h3>
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      {t.locatedCoordinates}
                    </p>
                  </div>

                  {/* View Mode Toggle Switcher & Save Button */}
                  <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap">
                    <button
                      onClick={() => handleToggleSaveTrip()}
                      className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all border flex items-center gap-1.5 shadow-2xs ${
                        isCurrentTripSaved
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-300 hover:bg-emerald-100'
                          : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50 hover:text-blue-600'
                      }`}
                      title={isCurrentTripSaved ? t.saved : t.saveTrip}
                    >
                      {isCurrentTripSaved ? (
                        <>
                          <BookmarkCheck className="w-4 h-4 text-emerald-600 fill-emerald-600/20" />
                          <span>{t.saved}</span>
                        </>
                      ) : (
                        <>
                          <Bookmark className="w-4 h-4 text-slate-500" />
                          <span>{t.saveTrip}</span>
                        </>
                      )}
                    </button>

                    {/* Social Share Itinerary Button */}
                    <button
                      onClick={() => {
                        setPlanToShare(activePlan);
                        setIsShareModalOpen(true);
                      }}
                      className="px-3 py-1.5 rounded-xl text-xs font-bold transition-all border flex items-center gap-1.5 shadow-2xs bg-indigo-50 text-indigo-700 border-indigo-200 hover:bg-indigo-100"
                      title={t.share}
                    >
                      <Share2 className="w-4 h-4 text-indigo-600" />
                      <span>{t.share}</span>
                    </button>

                    <div className="flex items-center bg-slate-200/90 p-1 rounded-xl shadow-inner">
                      <button
                        onClick={() => setViewMode('list')}
                        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                          viewMode === 'list' 
                            ? 'bg-white text-slate-900 shadow-xs' 
                            : 'text-slate-600 hover:text-slate-900'
                        }`}
                      >
                        <List className="w-3.5 h-3.5 text-slate-500" />
                        <span>{t.listView}</span>
                      </button>
                      <button
                        onClick={() => setViewMode('map')}
                        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                          viewMode === 'map' 
                            ? 'bg-white text-blue-600 shadow-xs' 
                            : 'text-slate-600 hover:text-slate-900'
                        }`}
                      >
                        <Map className="w-3.5 h-3.5 text-blue-600" />
                        <span>{t.mapView}</span>
                      </button>
                    </div>

                    <span className="text-xs font-semibold text-blue-700 bg-blue-50 px-2.5 py-1 rounded-md border border-blue-200 hidden xl:inline-block">
                      {displayPlan.bookableProductsCount} {t.bookableServices}
                    </span>
                  </div>
                </div>

                {/* Intent Chips */}
                <div className="flex flex-wrap items-center gap-1.5 text-xs">
                  <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-white rounded-lg border border-slate-200 font-medium text-slate-700">
                    <MapPin className="w-3.5 h-3.5 text-slate-400" />
                    {displayPlan.intent.destination}
                  </span>
                  <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-white rounded-lg border border-slate-200 font-medium text-slate-700">
                    <Calendar className="w-3.5 h-3.5 text-slate-400" />
                    {displayPlan.intent.days} {currentLocale === 'vi' ? 'ngày' : 'days'}
                  </span>
                  <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-white rounded-lg border border-slate-200 font-medium text-slate-700">
                    <Users className="w-3.5 h-3.5 text-slate-400" />
                    {displayPlan.intent.party === 'family_with_kids' 
                      ? (currentLocale === 'vi' ? 'Gia đình & trẻ nhỏ' : 'Family with kids') 
                      : (currentLocale === 'vi' ? 'Cặp đôi' : 'Couples')}
                  </span>
                  <button
                    onClick={() => {
                      if (viewMode === 'map') {
                        setShowMapWeather(prev => !prev);
                      }
                    }}
                    className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg border text-xs font-semibold transition-colors ${
                      viewMode === 'map' && showMapWeather
                        ? 'bg-sky-600 text-white border-sky-600 shadow-2xs'
                        : 'bg-sky-50 hover:bg-sky-100 text-sky-800 border-sky-200'
                    }`}
                    title={currentLocale === 'vi' ? 'Dự báo thời tiết 5 ngày cho điểm đến' : '5-Day destination weather forecast'}
                  >
                    <CloudSun className="w-3.5 h-3.5 text-amber-500" />
                    <span>{currentLocale === 'vi' ? 'Dự báo thời tiết 5 ngày' : '5-Day Weather Forecast'}</span>
                  </button>
                </div>
              </div>

              {/* View Switch: Map View vs List View */}
              {viewMode === 'map' ? (
                <div className="flex-1 relative flex flex-col min-h-[460px] overflow-hidden">
                  <ItineraryMap
                    plan={displayPlan}
                    activeDay={activeDayTab}
                    onSelectDay={setActiveDayTab}
                    onAddToCart={(p) => addToCart(p, 2)}
                    className="flex-1 w-full h-full"
                  />

                  {/* Floating Weather Overlay in Map View */}
                  {showMapWeather && (
                    <div className="absolute top-3 left-3 right-3 sm:left-auto sm:right-3 sm:w-96 z-[1000] shadow-xl animate-in fade-in zoom-in-95 duration-200">
                      <WeatherForecastCard 
                        destination={displayPlan.intent.destination} 
                        defaultExpanded={true}
                        className="bg-white/95 backdrop-blur-md shadow-lg"
                      />
                    </div>
                  )}
                </div>
              ) : (
                /* Plan Body with Tabs for Days */
                <div className="flex-1 overflow-y-auto p-5 space-y-5">
                  {/* 5-Day Destination Weather Forecast Information Card */}
                  <WeatherForecastCard 
                    destination={displayPlan.intent.destination} 
                    defaultExpanded={true}
                  />

                  {/* Stay for whole trip */}
                  {displayPlan.stay && (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                          {t.stayEntireTrip}
                        </h4>
                        <button
                          onClick={() => setViewMode('map')}
                          className="text-[11px] font-semibold text-blue-600 hover:text-blue-800 flex items-center gap-1"
                        >
                          <MapPin className="w-3 h-3" />
                          <span>{currentLocale === 'vi' ? 'Xem vị trí khách sạn' : 'View hotel on map'}</span>
                        </button>
                      </div>
                      <ProductCard
                        product={displayPlan.stay.product}
                        variant="compact"
                        assistantNote={displayPlan.stay.note}
                        isPersonalizedMatch={displayPlan.stay.source === 'recommendation'}
                        because={displayPlan.stay.because}
                        onQuickAdd={(p) => addToCart(p, 1)}
                      />
                    </div>
                  )}

                  {/* Days Tabs */}
                  <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                    <div className="flex items-center gap-2">
                      {displayPlan.days.map(d => (
                        <button
                          key={d.day}
                          onClick={() => setActiveDayTab(d.day)}
                          className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${activeDayTab === d.day ? 'bg-blue-600 text-white shadow-2xs' : 'text-slate-600 hover:bg-slate-100'}`}
                        >
                          {typeof t.day === 'function' ? t.day(d.day) : `${t.dayTabPrefix || (currentLocale === 'vi' ? 'Ngày' : 'Day')} ${d.day}`}
                        </button>
                      ))}
                    </div>

                    <button
                      onClick={() => setViewMode('map')}
                      className="text-xs font-bold text-blue-600 hover:text-blue-700 flex items-center gap-1 px-2.5 py-1 bg-blue-50 rounded-lg border border-blue-200 transition-colors"
                    >
                      <Map className="w-3.5 h-3.5" />
                      <span>{t.viewRoute || (currentLocale === 'vi' ? 'Xem lộ trình' : 'View route')} {typeof t.day === 'function' ? t.day(activeDayTab) : `${t.dayTabPrefix || (currentLocale === 'vi' ? 'Ngày' : 'Day')} ${activeDayTab}`}</span>
                    </button>
                  </div>

                  {/* Slots of the Active Day */}
                  {displayPlan.days.find(d => d.day === activeDayTab) && (
                    <div className="space-y-4">
                      <div className="text-xs font-bold text-slate-800">
                        {displayPlan.days.find(d => d.day === activeDayTab)?.title}
                      </div>

                      <div className="space-y-3">
                        {displayPlan.days.find(d => d.day === activeDayTab)?.slots.map((slot, sIdx) => {
                          const morningStr = t.morning || t.timeSlots?.morning || (currentLocale === 'vi' ? 'Buổi sáng' : 'Morning');
                          const noonStr = t.noon || t.timeSlots?.noon || (currentLocale === 'vi' ? 'Buổi trưa' : 'Noon');
                          const afternoonStr = t.afternoon || t.timeSlots?.afternoon || (currentLocale === 'vi' ? 'Buổi chiều' : 'Afternoon');
                          const eveningStr = t.evening || t.timeSlots?.evening || (currentLocale === 'vi' ? 'Buổi tối' : 'Evening');

                          const timeLabel = slot.time === 'morning' 
                            ? `☀ ${morningStr.toUpperCase()}` 
                            : slot.time === 'noon' 
                              ? `🌤 ${noonStr.toUpperCase()}` 
                              : slot.time === 'afternoon' 
                                ? `⛅ ${afternoonStr.toUpperCase()}` 
                                : `🌙 ${eveningStr.toUpperCase()}`;

                          return (
                            <div key={sIdx} className="space-y-1.5">
                              <div className="flex items-center justify-between">
                                <span className="text-[11px] font-bold text-slate-400 tracking-wider">
                                  {timeLabel}
                                </span>
                                {(slot.address || slot.product?.address) && (
                                  <button
                                    onClick={() => setViewMode('map')}
                                    className="text-[10px] text-slate-400 hover:text-blue-600 flex items-center gap-1 transition-colors"
                                  >
                                    <MapPin className="w-3 h-3" />
                                    <span className="truncate max-w-[180px]">{slot.address || slot.product?.address}</span>
                                  </button>
                                )}
                              </div>

                              {slot.isActivityNote ? (
                                /* Non-Bookable Activity Note (§6.3) */
                                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80 text-xs text-slate-700 flex items-start gap-2.5">
                                  <Coffee className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
                                  <div className="flex-1">
                                    <h5 className="font-bold text-slate-800">{slot.activityTitle}</h5>
                                    <p className="text-[11px] text-slate-600 italic mt-0.5">
                                      {slot.note}
                                    </p>
                                    {slot.address && (
                                      <p className="text-[10px] text-slate-400 mt-1 flex items-center gap-1">
                                        <MapPin className="w-2.5 h-2.5 text-slate-400" />
                                        <span>{slot.address}</span>
                                      </p>
                                    )}
                                  </div>
                                </div>
                              ) : slot.product ? (
                                /* Bookable Product Card */
                                <ProductCard
                                  product={slot.product}
                                  variant="compact"
                                  assistantNote={slot.note}
                                  isPersonalizedMatch={slot.source === 'recommendation'}
                                  because={slot.because}
                                  onQuickAdd={(p) => addToCart(p, 2)}
                                />
                              ) : null}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Plan Footer: Total & Add All To Cart & Save Trip (§6.3) */}
              <div className="p-4 border-t border-slate-100 bg-slate-50 flex items-center justify-between gap-4 flex-wrap sm:flex-nowrap">
                <div>
                  <div className="text-[11px] text-slate-500">
                    {displayPlan.bookableProductsCount} {t.bookableServices} · {t.estimated}
                  </div>
                  <div className="text-base font-black text-blue-900 font-mono">
                    {formatLocalizedCurrency(displayPlan.totalEstimatedPrice, currentLocale).formatted}
                    {formatLocalizedCurrency(displayPlan.totalEstimatedPrice, currentLocale).secondary && (
                      <span className="text-xs text-slate-400 font-normal ml-1.5 font-sans">
                        ({formatLocalizedCurrency(displayPlan.totalEstimatedPrice, currentLocale).secondary})
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleToggleSaveTrip()}
                    className={`px-3.5 py-2.5 rounded-xl text-xs font-bold transition-colors border flex items-center gap-1.5 shadow-2xs ${
                      isCurrentTripSaved
                        ? 'bg-emerald-50 text-emerald-700 border-emerald-300 hover:bg-emerald-100'
                        : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50 hover:text-blue-600'
                    }`}
                  >
                    {isCurrentTripSaved ? (
                      <>
                        <BookmarkCheck className="w-4 h-4 text-emerald-600 fill-emerald-600/20" />
                        <span>{t.saved}</span>
                      </>
                    ) : (
                      <>
                        <Bookmark className="w-4 h-4 text-slate-500" />
                        <span>{t.saveTrip}</span>
                      </>
                    )}
                  </button>

                  <button
                    onClick={handleAddAllToCart}
                    className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs sm:text-sm rounded-xl shadow-xs transition-colors flex items-center gap-1.5 shrink-0"
                  >
                    <Plus className="w-4 h-4" />
                    <span>{t.addAllToCart}</span>
                  </button>

                  <button
                    onClick={() => {
                      setPlanToShare(activePlan);
                      setIsShareModalOpen(true);
                    }}
                    className="px-3.5 py-2.5 rounded-xl text-xs font-bold transition-colors border flex items-center gap-1.5 shadow-2xs bg-indigo-50 text-indigo-700 border-indigo-200 hover:bg-indigo-100"
                    title={t.share}
                  >
                    <Share2 className="w-4 h-4 text-indigo-600" />
                    <span>{t.share}</span>
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="h-full flex items-center justify-center p-8 text-center text-slate-400 space-y-2">
              <div>
                <Sparkles className="w-10 h-10 mx-auto text-slate-300 mb-2" />
                <p className="text-sm font-semibold text-slate-700">{t.noPlanSelected}</p>
                <p className="text-xs text-slate-500">{t.noPlanHint}</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Saved Trips Modal */}
      <SavedTripsModal
        isOpen={isSavedModalOpen}
        onClose={() => setIsSavedModalOpen(false)}
        savedTrips={savedTrips}
        onSelectTrip={handleSelectSavedTrip}
        onDeleteTrip={handleDeleteSavedTrip}
        onShareTrip={(plan) => {
          setPlanToShare(plan);
          setIsShareModalOpen(true);
        }}
        currentPlanTitle={activePlan?.title}
      />

      {/* Social Share Itinerary Modal */}
      <ShareItineraryModal
        isOpen={isShareModalOpen}
        onClose={() => setIsShareModalOpen(false)}
        plan={planToShare || activePlan}
        senderName={currentPersona?.name || 'Du khách V-OTA'}
        onToast={showToast}
      />
    </div>
  );
};
