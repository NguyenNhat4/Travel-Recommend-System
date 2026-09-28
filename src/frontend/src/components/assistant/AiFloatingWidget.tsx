'use client';

import React, { useState, useRef, useEffect, useMemo } from 'react';
import dynamic from 'next/dynamic';
import { useTravel } from '../../context/TravelContext';
import { useAssistant } from '../../context/AssistantProvider';
import { productFromApi } from '../../services/catalog';
import type { components } from '../../types/api.gen';
import { GroundedPlan, Product, TravelIntent, ItineraryDay, ItinerarySlot } from '../../types/travel';
import { AssistantTripStarter, tripStarterMessage } from './AssistantTripStarter';
import { itineraryCartItems, type AssistantCartItem } from './AssistantResultPanel';
import { useAssistantCart } from '../../hooks/useAssistantCart';
import { 
  X, Send, Maximize2, Minimize2, Sparkles, MapPin, 
  Calendar, Users, Loader2, Compass,
  ShoppingBag, Hotel, Clock, ArrowRight, ChevronRight, ChevronLeft, List,
  Plus, MessageSquare, Trash2, ExternalLink, Bookmark, RotateCcw, AlertCircle
} from 'lucide-react';

// Dynamically load the Leaflet + OSM/OSRM itinerary map to avoid SSR issues.
const ItineraryMap = dynamic(
  () => import('./ItineraryMap').then((module) => module.ItineraryMap),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full min-h-[350px] items-center justify-center bg-slate-50 text-sm text-slate-500">
        Đang tải bản đồ lộ trình…
      </div>
    ),
  }
);

/**
 * Lịch trình hiển thị kèm các mục đặt được, tính từ response gốc theo đúng quy tắc của `/assistant`
 * (docs/spec/hop-dong-tich-hop-frontend.md §4.8): mỗi productId một lần, ngày dùng theo `days[].date`.
 */
type WidgetPlan = GroundedPlan & { cartItems: AssistantCartItem[] };

interface WidgetChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  plan?: WidgetPlan;
}

interface ConversationSession {
  id: string;
  title: string;
  timestamp: string;
  messages: WidgetChatMessage[];
  plan: WidgetPlan | null;
}

const DEFAULT_WELCOME_MESSAGE: WidgetChatMessage = {
  id: 'welcome',
  sender: 'assistant',
  text: 'Xin chào! Mình là Trợ lý Du lịch V-OTA AI. Hãy cung cấp thông tin đầy đủ nhất có thể về điểm đến, số ngày, nhóm đồng hành, ngân sách và sở thích để đề xuất chính xác và sát nhu cầu của bạn hơn.'
};

interface HotelVisualData {
  tags: { label: string; icon: string }[];
  images: { url: string; caption: string }[];
  isVilla: boolean;
}

/**
 * Trích xuất điểm HOT (Nha Trang, Biệt thự, Hồ bơi...) và 2 hình ảnh to rõ cho Khách sạn lưu trú
 */
const getHotelVisuals = (product: Product, destination: string): HotelVisualData => {
  const tags: { label: string; icon: string }[] = [];
  tags.push({ label: destination, icon: '📍' });

  const isVilla = product.name.toLowerCase().includes('biệt thự') ||
    product.id.includes('hotel-02');

  if (isVilla) {
    tags.push({ label: 'Biệt thự sang trọng', icon: '🏡' });
  } else {
    tags.push({ label: 'Resort 5★ biển', icon: '🏨' });
  }

  const hasPool = product.name.toLowerCase().includes('hồ bơi') ||
    product.attributes?.pool;

  if (hasPool) {
    tags.push({
      label: isVilla ? 'Hồ bơi riêng' : 'Hồ bơi lớn',
      icon: '🏊‍♂️'
    });
  }

  if (product.attributes?.oceanView || product.attributes?.privateBeach) {
    tags.push({ label: 'View biển', icon: '🌊' });
  }

  // Khớp ảnh chuẩn xác theo từng khách sạn và đặc trưng
  let img1 = product.imageUrl;
  let img2 = 'https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?auto=format&fit=crop&w=1200&q=80';

  if (product.id === 'nt-hotel-02') {
    // Biệt thự hồ bơi riêng Nha Trang: Biệt thự sang trọng & Hồ bơi riêng villa
    img1 = 'https://images.unsplash.com/photo-1582719508461-905c673771fd?auto=format&fit=crop&w=1200&q=80';
    img2 = 'https://images.unsplash.com/photo-1540555700478-4be289fbecef?auto=format&fit=crop&w=1200&q=80';
  } else if (product.id === 'nt-hotel-01') {
    // Deluxe Ocean View Nha Trang: Phòng nghỉ view biển & Hồ bơi lớn Hòn Tre
    img1 = 'https://images.unsplash.com/photo-1590490360182-c33d57733427?auto=format&fit=crop&w=1200&q=80';
    img2 = 'https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?auto=format&fit=crop&w=1200&q=80';
  } else if (product.id === 'pq-hotel-02') {
    // Wonder World Biệt thự biển Phú Quốc
    img1 = 'https://images.unsplash.com/photo-1618773928121-c32242e63f39?auto=format&fit=crop&w=1200&q=80';
    img2 = 'https://images.unsplash.com/photo-1540555700478-4be289fbecef?auto=format&fit=crop&w=1200&q=80';
  } else if (product.id === 'pq-hotel-01') {
    // Resort & Spa Bãi Dài Phú Quốc
    img1 = 'https://images.unsplash.com/photo-1590490360182-c33d57733427?auto=format&fit=crop&w=1200&q=80';
    img2 = 'https://images.unsplash.com/photo-1571896349842-33c89424de2d?auto=format&fit=crop&w=1200&q=80';
  } else if (product.id === 'dn-hotel-01') {
    // Biệt thự Non Nước Đà Nẵng
    img1 = 'https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=1200&q=80';
    img2 = 'https://images.unsplash.com/photo-1520250497591-112f2f40a3f4?auto=format&fit=crop&w=1200&q=80';
  } else if (isVilla) {
    img1 = 'https://images.unsplash.com/photo-1582719508461-905c673771fd?auto=format&fit=crop&w=1200&q=80';
    img2 = 'https://images.unsplash.com/photo-1540555700478-4be289fbecef?auto=format&fit=crop&w=1200&q=80';
  } else {
    img1 = product.imageUrl || 'https://images.unsplash.com/photo-1590490360182-c33d57733427?auto=format&fit=crop&w=1200&q=80';
    img2 = 'https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?auto=format&fit=crop&w=1200&q=80';
  }

  return {
    tags: tags.slice(0, 4),
    images: [
      { url: img1, caption: isVilla ? '🏡 Không gian biệt thự nghỉ dưỡng' : '🏨 Phòng nghỉ tiện nghi 5 sao' },
      { url: img2, caption: hasPool ? (isVilla ? '🏊‍♂️ Hồ bơi riêng & sân vườn' : '🏊‍♂️ Hồ bơi lớn & vịnh biển') : '🌊 Vịnh biển riêng tư' }
    ],
    isVilla
  };
};

/**
 * Trích xuất ảnh to rõ ĐÚNG 100% NỘI DUNG cho từng chặng hoạt động trong lộ trình
 */
const getSlotVisualUrl = (slot: ItinerarySlot, destination: string): string => {
  const title = (slot.activityTitle || '').toLowerCase();
  const note = (slot.note || '').toLowerCase();
  const name = (slot.product?.name || '').toLowerCase();
  const loc = (slot.locationName || '').toLowerCase();
  const text = `${title} ${note} ${name} ${loc}`;

  // 1. Show diễn nghệ thuật / Tata Show / Ánh sáng 3D mapping / Nhạc nước
  if (text.includes('tata show') || text.includes('show') || text.includes('mapping') || text.includes('nhạc nước') || text.includes('biểu diễn nghệ thuật')) {
    return 'https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=1200&q=80';
  }

  // 2. Akoya Spa thư giãn / Massage trị liệu tinh dầu
  if (text.includes('spa') || text.includes('massage') || text.includes('thư giãn') || text.includes('trị liệu') || text.includes('akoya')) {
    return 'https://images.unsplash.com/photo-1544161515-4ab6ce6db874?auto=format&fit=crop&w=1200&q=80';
  }

  // 3. Quán Cà phê ven biển / Ngắm sóng / Nước dừa xiêm / Trà chiều
  if (text.includes('cà phê') || text.includes('cafe') || text.includes('ngắm sóng') || text.includes('trà chiều')) {
    return 'https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?auto=format&fit=crop&w=1200&q=80';
  }

  // 4. Chèo kayak / Lặn biển / Ngắm san hô
  if (text.includes('kayak') || text.includes('chèo') || text.includes('lặn') || text.includes('san hô')) {
    return 'https://images.unsplash.com/photo-1544551763-46a013bb70d5?auto=format&fit=crop&w=1200&q=80';
  }

  // 5. Chợ đặc sản / Mua sắm quà lưu niệm (chợ Đầm, chợ Hàn, yến sào, ngọc trai...)
  if (text.includes('chợ') || text.includes('mua sắm') || text.includes('làm quà') || text.includes('quà lưu niệm') || text.includes('đặc sản làm quà')) {
    return 'https://images.unsplash.com/photo-1533900298318-6b8da08a523e?auto=format&fit=crop&w=1200&q=80';
  }

  // 6. Làm thủ tục trả phòng & Xe tiễn sân bay / Chuyến bay
  if (text.includes('sân bay') || text.includes('tiễn sân bay') || text.includes('trả phòng') || text.includes('đón xe')) {
    return 'https://images.unsplash.com/photo-1436491865332-7a61a109cc05?auto=format&fit=crop&w=1200&q=80';
  }

  // 7. Bãi biển / Tắm biển / Dạo bình minh trên cát / Hoàng hôn
  if (text.includes('bình minh') || text.includes('tắm biển') || text.includes('bãi biển') || text.includes('dạo biển') || text.includes('bãi cát')) {
    return 'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1200&q=80';
  }

  // 8. Ẩm thực địa phương / Ăn trưa / Bún quậy / Nem nướng / Bánh tráng thịt heo / Cao lầu / Hải sản
  if (text.includes('ẩm thực') || text.includes('ăn trưa') || text.includes('buffet') || text.includes('nem nướng') || text.includes('bún quậy') || text.includes('cao lầu') || text.includes('hải sản')) {
    return 'https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=1200&q=80';
  }

  // 9. Safari / River Safari / Động vật bán hoang dã
  if (text.includes('safari') || text.includes('vườn thú') || text.includes('động vật')) {
    return 'https://images.unsplash.com/photo-1534177616072-ef7dc120449d?auto=format&fit=crop&w=1200&q=80';
  }

  // 10. Bà Nà Hills / Cầu Vàng
  if (text.includes('cầu vàng') || text.includes('bà nà') || text.includes('bana')) {
    return 'https://images.unsplash.com/photo-1559592413-7cec4d0cae2b?auto=format&fit=crop&w=1200&q=80';
  }

  // 10b. Đà Lạt: thác, đồi chè, hoa và núi rừng
  if (text.includes('datanla') || text.includes('thác voi') || text.includes('thác nước')) {
    return 'https://images.unsplash.com/photo-1433086966358-54859d0ed716?auto=format&fit=crop&w=1200&q=80';
  }
  if (text.includes('đồi chè') || text.includes('săn mây') || text.includes('cầu đất')) {
    return 'https://images.unsplash.com/photo-1594631252845-29fc4cc8cde9?auto=format&fit=crop&w=1200&q=80';
  }
  if (text.includes('langbiang') || text.includes('đồi thông') || text.includes('cao nguyên')) {
    return 'https://images.unsplash.com/photo-1583417319070-4a69db38a482?auto=format&fit=crop&w=1200&q=80';
  }
  if (text.includes('vườn hoa') || text.includes('hoa theo mùa') || text.includes('trại mát')) {
    return 'https://images.unsplash.com/photo-1490750967868-88aa4486c946?auto=format&fit=crop&w=1200&q=80';
  }

  // 11. Sân Golf
  if (text.includes('golf') || text.includes('hố')) {
    return 'https://images.unsplash.com/photo-1535131749006-b7f58c99034b?auto=format&fit=crop&w=1200&q=80';
  }

  // 12. Nếu slot gắn liền với sản phẩm có ảnh đại diện sẵn trong catalog
  if (slot.product?.imageUrl) {
    return slot.product.imageUrl;
  }

  // 13. VinWonders / Công viên vui chơi / Cáp treo
  if (text.includes('vinwonders') || text.includes('công viên') || text.includes('cáp treo') || text.includes('vui chơi')) {
    return 'https://images.unsplash.com/photo-1513889961551-628c1e5e2ee9?auto=format&fit=crop&w=1200&q=80';
  }

  // Fallback theo điểm đến
  if (destination === 'Phú Quốc') {
    return 'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1200&q=80';
  }
  if (destination === 'Đà Nẵng' || destination === 'Hội An') {
    return 'https://images.unsplash.com/photo-1552465011-b4e21bf6e79a?auto=format&fit=crop&w=1200&q=80';
  }
  if (destination === 'Đà Lạt') {
    return 'https://images.unsplash.com/photo-1578637387939-43c525550085?auto=format&fit=crop&w=1200&q=80';
  }
  return 'https://images.unsplash.com/photo-1513889961551-628c1e5e2ee9?auto=format&fit=crop&w=1200&q=80';
};

const DESTINATION_COORDINATES: Record<string, { lat: number; lng: number }> = {
  'Nha Trang': { lat: 12.2388, lng: 109.1967 },
  'Phú Quốc': { lat: 10.2899, lng: 103.9840 },
  'Đà Nẵng': { lat: 16.0544, lng: 108.2022 },
  'Đà Lạt': { lat: 11.9404, lng: 108.4376 },
  'Hội An': { lat: 15.8801, lng: 108.3380 },
  'Hạ Long': { lat: 20.9501, lng: 107.0734 },
  'Hà Nội': { lat: 21.0285, lng: 105.8542 },
};

function adaptProductSummaryToProduct(summary: components['schemas']['ProductSummary']): Product {
  const product = productFromApi(summary);
  const defaultCoords = DESTINATION_COORDINATES[product.destination] || { lat: 12.2388, lng: 109.1967 };
  return {
    ...product,
    priceString: summary.unitPrice != null ? new Intl.NumberFormat('vi-VN').format(summary.unitPrice) + ' ₫' : undefined,
    coordinates: product.coordinates || defaultCoords,
  };
}

function convertItineraryCompletedToGroundedPlan(
  response: components['schemas']['ItineraryCompleted']
): WidgetPlan {
  const dest = (response.intent?.destination || 'Nha Trang') as any;
  const daysCount = response.intent?.days || response.itinerary.days.length || 3;
  const party = (response.intent?.party as any) || 'family_with_kids';
  const defaultCoords = DESTINATION_COORDINATES[dest] || { lat: 12.2388, lng: 109.1967 };

  const stayItem = response.itinerary.stay ? {
    productId: response.itinerary.stay.product.productId,
    product: adaptProductSummaryToProduct(response.itinerary.stay.product),
    nights: response.itinerary.stay.nights || (daysCount > 1 ? daysCount - 1 : 1),
    note: response.itinerary.stay.note || 'Khách sạn lưu trú 5 sao',
    source: (response.itinerary.stay.source as any) || 'search',
    because: response.itinerary.stay.because as any,
  } : undefined;

  const timeRanges: Record<string, string> = {
    morning: '08:00 - 11:30',
    noon: '11:45 - 13:30',
    afternoon: '14:30 - 17:30',
    evening: '18:00 - 21:00',
  };

  const days: ItineraryDay[] = response.itinerary.days.map((d) => {
    const slots: ItinerarySlot[] = d.slots.map((s) => {
      const product = s.product ? adaptProductSummaryToProduct(s.product) : undefined;
      const title = s.product?.name || s.activityType || s.note || 'Hoạt động trải nghiệm';
      const locName = s.product?.name || s.product?.destination || dest;
      const timeRange = (s.startTime && s.endTime) ? `${s.startTime} - ${s.endTime}` : (timeRanges[s.time] || '08:00 - 11:30');
      const coords = product?.coordinates || defaultCoords;

      return {
        time: s.time as any,
        timeRange,
        activityTitle: title,
        locationName: locName,
        productId: s.product?.productId,
        product,
        note: s.note || '',
        source: (s.source as any) || 'curated',
        coordinates: coords,
        address: product?.address || dest,
        transitInfo: '',
        transitMode: 'driving',
        isActivityNote: !s.product,
        because: s.because as any,
      };
    });

    return {
      day: d.day,
      title: d.title || `Ngày ${d.day} tại ${dest}`,
      slots,
    };
  });

  return {
    intent: {
      destination: dest,
      days: daysCount,
      party,
      interests: response.intent?.interests || [],
    },
    title: response.itinerary.title || `Lịch trình ${daysCount} ngày tại ${dest}`,
    stay: stayItem,
    stays: stayItem ? [stayItem] : undefined,
    days,
    totalEstimatedPrice: response.itinerary.estimatedTotal ?? 0,
    bookableProductsCount: response.itinerary.bookableCount ?? days.reduce((acc, cur) => acc + cur.slots.filter(s => !!s.product).length, 0),
    cartItems: itineraryCartItems(response.itinerary),
  };
}


export const AiFloatingWidget: React.FC = () => {
  const { currentPersona, activeEvents, addToCart, showToast, navigate, currentRoute } = useTravel();
  const {
    state: assistantState,
    sendMessage,
    retry,
    abort,
    resetConversation,
    consumeFloatingInitialMessage,
  } = useAssistant();
  const addItineraryToCart = useAssistantCart();

  // Widget States
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [isExpanded, setIsExpanded] = useState<boolean>(false);
  const [showBubble, setShowBubble] = useState<boolean>(true);
  const [inputVal, setInputVal] = useState<string>('');
  const [activePlan, setActivePlan] = useState<WidgetPlan | null>(null);
  const [activeDayTab, setActiveDayTab] = useState<number>(1);
  const [isSavedPlan, setIsSavedPlan] = useState<boolean>(false);
  const [isCheckingOut, setIsCheckingOut] = useState<boolean>(false);
  const [isChatCollapsed, setIsChatCollapsed] = useState<boolean>(false);
  const [hoveredCoordinate, setHoveredCoordinate] = useState<{ lat: number; lng: number } | null>(null);
  const [hoveredPointId, setHoveredPointId] = useState<string | null>(null);
  // History Conversation & Drawer States
  const [isHistoryOpen, setIsHistoryOpen] = useState<boolean>(false);
  const [conversations, setConversations] = useState<ConversationSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>('conv-current');

  const [localMessages, setLocalMessages] = useState<WidgetChatMessage[]>([DEFAULT_WELCOME_MESSAGE]);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const isRunning = assistantState.phase === 'connecting' || assistantState.phase === 'streaming' || isGenerating;

  const chatScrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Sync isOpen when provider requests opening floating widget
  useEffect(() => {
    if (assistantState.isFloatingOpen) {
      setIsOpen(true);
    }
  }, [assistantState.isFloatingOpen]);

  // Sync initial message if provided
  useEffect(() => {
    if (assistantState.floatingInitialMessage) {
      setInputVal(assistantState.floatingInitialMessage);
      consumeFloatingInitialMessage();
    }
  }, [assistantState.floatingInitialMessage, consumeFloatingInitialMessage]);

  // Sync latest completed plan from backend response
  useEffect(() => {
    if (assistantState.response?.status === 'COMPLETED') {
      const plan = convertItineraryCompletedToGroundedPlan(assistantState.response);
      setActivePlan(plan);
      setActiveDayTab(1);
      setIsSavedPlan(false);
    }
  }, [assistantState.response]);

  // Derive messages from assistantState.transcript or local fallback
  const messages = useMemo<WidgetChatMessage[]>(() => {
    if (assistantState.transcript.length === 0) {
      return localMessages;
    }

    return assistantState.transcript.map((item) => {
      let plan: WidgetPlan | undefined = undefined;
      if (item.response?.status === 'COMPLETED') {
        plan = convertItineraryCompletedToGroundedPlan(item.response);
      }

      return {
        id: item.id,
        sender: item.sender,
        text: item.text,
        plan,
      };
    });
  }, [assistantState.transcript, localMessages]);

  const setMessages = setLocalMessages;

  // Typing effect on the floating pill
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

  // Auto-scroll messages and focus input
  useEffect(() => {
    if (isOpen) {
      chatScrollRef.current?.scrollTo({ top: chatScrollRef.current.scrollHeight, behavior: 'smooth' });
      setTimeout(() => inputRef.current?.focus(), 150);
    }
  }, [isOpen, messages, isExpanded]);

  // Handle ESC key to close or minimize
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (isExpanded) {
          setIsExpanded(false);
        } else if (isOpen) {
          setIsOpen(false);
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isExpanded, isOpen]);

  // Lock main body/html scrollbar when AI assistant is open / fullscreen
  useEffect(() => {
    if (isOpen) {
      const prevBodyOverflow = document.body.style.overflow;
      const prevHtmlOverflow = document.documentElement.style.overflow;
      document.body.style.overflow = 'hidden';
      document.documentElement.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = prevBodyOverflow;
        document.documentElement.style.overflow = prevHtmlOverflow;
      };
    }
  }, [isOpen]);

  // Close widget when navigating to checkout
  useEffect(() => {
    if (currentRoute.startsWith('/checkout')) {
      setIsOpen(false);
      setIsExpanded(false);
    }
  }, [currentRoute]);

  const handleSendMessage = (textToSend?: string) => {
    const text = (textToSend || inputVal).trim();
    if (!text || isRunning) return;

    setInputVal('');
    sendMessage(text);
  };

  const handleQuickPrompt = (promptText: string) => {
    handleSendMessage(promptText);
  };


  const handleToggleSavePlan = (e?: React.MouseEvent) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    if (!activePlan) return;
    setIsSavedPlan(prev => {
      const next = !prev;
      showToast(next ? 'Đã lưu hành trình vào danh sách yêu thích!' : 'Đã bỏ lưu hành trình!');
      return next;
    });
  };

  const handleCheckoutPlan = (e?: React.MouseEvent) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    if (!activePlan || isCheckingOut) return;
    if (!activePlan.cartItems.length) {
      showToast('Lịch trình chưa có dịch vụ nào đặt được.');
      return;
    }
    // Thêm tuần tự rồi mới sang /checkout: checkout đọc GET /cart ngay khi mở, nên phải chờ mọi mục vào giỏ.
    setIsCheckingOut(true);
    void addItineraryToCart(activePlan.cartItems, () => navigate('/checkout'))
      .finally(() => setIsCheckingOut(false));
  };

  const handleStartNewChat = () => {
    // Nếu phiên hiện tại có tin nhắn từ người dùng, lưu vào danh sách lịch sử
    const hasUserMsg = messages.some(m => m.sender === 'user');
    if (hasUserMsg) {
      const firstUserMsg = messages.find(m => m.sender === 'user')?.text || 'Hội thoại mới';
      const newSession: ConversationSession = {
        id: 'conv-' + Date.now(),
        title: activePlan?.title || (firstUserMsg.length > 35 ? firstUserMsg.slice(0, 35) + '...' : firstUserMsg),
        timestamp: 'Vừa xong',
        messages: [...messages],
        plan: activePlan
      };
      setConversations(prev => [newSession, ...prev]);
    }

    // Reset về hội thoại mới với backend agent
    resetConversation();
    setActiveSessionId('conv-' + Date.now());
    setActivePlan(null);
    setActiveDayTab(1);
    setIsSavedPlan(false);
    setIsHistoryOpen(false);
    showToast('Đã bắt đầu cuộc trò chuyện mới!');
  };

  const handleSelectConversation = (session: ConversationSession) => {
    setActiveSessionId(session.id);
    setActivePlan(session.plan);
    setActiveDayTab(1);
    setIsSavedPlan(false);
    setIsHistoryOpen(false);
  };

  const handleDeleteConversation = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    setConversations(prev => prev.filter(c => c.id !== id));
  };

  // Render History Drawer bên trái (gồm nút New Chat và danh sách History Conversation)
  // Overlay toàn bộ 12/12 không gian của container chính với backdrop mờ và drawer trượt mượt mà
  const renderHistoryDrawer = () => (
    <div className="absolute inset-0 z-[1050] flex overflow-hidden">
      {/* Backdrop mờ phủ kín toàn bộ 12/12 - bấm vào để đóng drawer */}
      <div 
        onClick={() => setIsHistoryOpen(false)}
        className="absolute inset-0 bg-slate-900/40 backdrop-blur-xs transition-opacity animate-in fade-in duration-200"
      />

      {/* Drawer content trượt ra từ mép trái, chiếm 320px - max 85% */}
      <div className="relative w-[320px] max-w-[85%] bg-white h-full shadow-2xl flex flex-col border-r border-slate-100 z-10 animate-in slide-in-from-left duration-250 ease-out">
        {/* Header Drawer: New Chat & Đóng */}
        <div className="p-3.5 border-b border-slate-100 flex items-center justify-between gap-2">
          <button
            type="button"
            onClick={handleStartNewChat}
            className="flex-1 flex items-center justify-center gap-2 py-2 px-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-sm font-semibold transition shadow-xs cursor-pointer"
            title="Bắt đầu hội thoại mới"
          >
            <Plus className="w-4 h-4" />
            <span>Đoạn chat mới</span>
          </button>
          <button
            type="button"
            onClick={() => setIsHistoryOpen(false)}
            className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-xl transition cursor-pointer"
            title="Đóng sidebar"
            aria-label="Đóng sidebar"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Danh sách History Conversation */}
        <div className="flex-1 overflow-y-auto p-3 space-y-1">
          <div className="px-2 py-1.5 text-xs font-semibold text-slate-400 uppercase tracking-wider">
            Lịch sử trò chuyện
          </div>
          {conversations.length === 0 ? (
            <div className="text-center py-8 text-slate-400 text-sm">
              Chưa có lịch sử hội thoại nào
            </div>
          ) : (
            conversations.map((c) => {
              const isActive = activeSessionId === c.id;
              return (
                <div
                  key={c.id}
                  onClick={() => handleSelectConversation(c)}
                  className={`group flex items-center justify-between p-2.5 rounded-xl cursor-pointer text-sm transition ${
                    isActive 
                      ? 'bg-blue-50/80 text-blue-900 font-semibold' 
                      : 'hover:bg-slate-50 text-slate-700'
                  }`}
                >
                  <div className="flex items-center space-x-2.5 min-w-0 flex-1">
                    <MessageSquare className={`w-4 h-4 shrink-0 ${isActive ? 'text-blue-600' : 'text-slate-400 group-hover:text-slate-600'}`} />
                    <div className="truncate">
                      <div className="truncate text-[13.5px]">{c.title}</div>
                      <div className="text-[11px] text-slate-400 font-normal">{c.timestamp}</div>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={(e) => handleDeleteConversation(e, c.id)}
                    className="opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-rose-600 rounded-md transition cursor-pointer ml-1"
                    title="Xóa đoạn chat này"
                    aria-label="Xóa đoạn chat này"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );

  // Render Chat column content (used both in Sidebar and Fullscreen left column)
  const renderChatColumn = () => (
    <div className="flex flex-col h-full bg-white overflow-hidden">
      {/* Messages Scroll Area - Nền trắng đồng nhất với toàn khung chat */}
      <div ref={chatScrollRef} className="flex-1 p-4 space-y-4 overflow-y-auto text-base bg-white">
        {messages.map((m) => (
          <div 
            key={m.id} 
            className={`flex items-start space-x-3 ${m.sender === 'user' ? 'justify-end' : ''}`}
          >
            {m.sender === 'assistant' && (
              <div className="w-9 h-9 shrink-0 flex items-center justify-center mt-0.5">
                <img 
                  src="/mascot_welcome.webp" 
                  alt="AI Mascot" 
                  className="w-full h-full object-contain drop-shadow-xs" 
                />
              </div>
            )}
            <div 
              className={`p-4 rounded-2xl text-base leading-relaxed ${
                m.sender === 'user'
                  ? 'bg-blue-600 text-white rounded-tr-none max-w-[85%] shadow-xs'
                  : 'bg-slate-100 text-slate-800 rounded-tl-none max-w-[88%]'
              }`}
            >
              <div>{m.text}</div>
              {m.id === DEFAULT_WELCOME_MESSAGE.id && assistantState.transcript.length === 0 && (
                <AssistantTripStarter
                  disabled={isRunning}
                  onSubmit={(selection) => handleSendMessage(tripStarterMessage(selection))}
                />
              )}
              {m.plan && !isExpanded && (
                <button
                  onClick={() => setIsExpanded(true)}
                  className="mt-3 w-full py-2.5 px-3.5 bg-white text-blue-600 hover:bg-blue-50 font-semibold rounded-xl flex items-center justify-center gap-1.5 transition cursor-pointer text-sm shadow-2xs"
                  title="Mở rộng toàn màn hình để xem lộ trình và bản đồ"
                >
                  <Sparkles className="w-4 h-4 text-blue-600" />
                  <span>Xem lộ trình & Bản đồ song song</span>
                  <Maximize2 className="w-4 h-4 ml-0.5" />
                </button>
              )}
            </div>
          </div>
        ))}
        {isRunning && (
          <div className="flex flex-col space-y-2 text-slate-600 text-sm bg-blue-50/70 border border-blue-100/80 p-3.5 rounded-2xl w-fit max-w-[90%]">
            <div className="flex items-center space-x-2 font-semibold text-blue-900">
              <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
              <span>{assistantState.isSlow ? 'Yêu cầu đang mất nhiều thời gian hơn dự kiến…' : 'AI đang lập kế hoạch và tính toán lộ trình...'}</span>
            </div>
            {assistantState.progress.length > 0 && (
              <ol className="space-y-1 text-xs text-blue-800 pl-5 list-disc">
                {assistantState.progress.map((step, index) => (
                  <li key={`${step.sequence ?? index}-${step.nodeId ?? 'node'}`}>
                    <span className="font-semibold">{step.nodeId ?? 'Bước xử lý'}</span>
                    {step.message ? ` · ${step.message}` : ''}
                  </li>
                ))}
              </ol>
            )}
          </div>
        )}
        {assistantState.error && (
          <div className="flex items-start justify-between gap-3 p-3.5 bg-rose-50 border border-rose-200 rounded-2xl text-xs text-rose-800">
            <div className="flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <div>
                <div className="font-bold">Lỗi từ Backend Agent</div>
                <div className="mt-0.5 text-rose-700">{assistantState.error.message}</div>
              </div>
            </div>
            {assistantState.error.retryable && (
              <button 
                onClick={retry}
                className="flex items-center gap-1 px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded-lg font-bold transition shrink-0 cursor-pointer shadow-xs"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Thử lại</span>
              </button>
            )}
          </div>
        )}
      </div>

      {/* Chat Input Bar - Cách đáy thêm khoảng cách rộng rãi (pb-5 sm:pb-6) */}
      <div className="px-4 pt-2 pb-5 sm:pb-6 bg-white">
        <div className="flex items-center space-x-2 bg-slate-100 hover:bg-slate-100/90 focus-within:bg-slate-100 focus-within:ring-2 focus-within:ring-blue-600/30 rounded-2xl p-1.5 transition-all">
          <input 
            ref={inputRef}
            type="text" 
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            placeholder="Nhập yêu cầu du lịch hoặc lịch trình..." 
            className="flex-1 bg-transparent text-base px-3.5 py-2.5 focus:outline-hidden text-slate-800 placeholder:text-slate-400 min-h-[46px]"
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                handleSendMessage();
              }
            }}
          />
          <button 
            onClick={() => handleSendMessage()} 
            disabled={!inputVal.trim() || isRunning}
            className="p-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-200 text-white rounded-xl shadow-xs transition cursor-pointer shrink-0"
            title="Gửi yêu cầu"
            aria-label="Gửi yêu cầu"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        <div className="mt-2 flex items-center justify-between px-1 text-[11px] text-slate-400">
          <span>{assistantState.conversationId ? 'Phiên backend đang hoạt động' : 'Trợ lý AI V-OTA'}</span>
          {isRunning && (
            <button 
              type="button" 
              onClick={abort} 
              className="text-rose-600 hover:text-rose-700 hover:underline font-semibold cursor-pointer"
            >
              Dừng xử lý
            </button>
          )}
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* ========================================================================= */}
      {/* 1. FLOATING TRIGGER MASCOT (Khi widget chưa mở)                             */}
      {/* ========================================================================= */}
      {!isOpen && (
        <div className="fixed bottom-5 right-5 z-40 flex flex-col items-end animate-float">
          {/* Chat Bubble Prompt */}
          {showBubble && (
            <div 
              onClick={() => setIsOpen(true)}
              className="group relative mb-2.5 bg-white text-slate-800 text-sm font-semibold pl-4 pr-8 py-3 rounded-2xl shadow-xl border border-slate-100/90 cursor-pointer hover:shadow-2xl transition-all duration-200 hover:-translate-y-0.5 text-left max-w-[240px]"
            >
              <div className="leading-snug whitespace-pre-line">
                <span>{displayedText}</span>
                {isTyping && (
                  <span className="inline-block w-0.5 h-3.5 bg-blue-600 ml-0.5 animate-pulse align-middle" />
                )}
              </div>
              <button 
                onClick={(e) => {
                  e.stopPropagation();
                  setShowBubble(false);
                }} 
                className="absolute top-2.5 right-2.5 text-slate-400 hover:text-slate-600 p-0.5 rounded-full hover:bg-slate-100 cursor-pointer" 
                title="Đóng"
                aria-label="Đóng"
              >
                <X className="w-3.5 h-3.5" />
              </button>
              {/* Speech bubble tail pointer pointing down to mascot */}
              <div className="absolute -bottom-1.5 right-8 sm:right-10 w-3.5 h-3.5 bg-white border-r border-b border-slate-100/90 transform rotate-45 pointer-events-none" />
            </div>
          )}

          {/* Mascot Avatar Button */}
          <button 
            onClick={() => setIsOpen(true)} 
            className="relative transition-transform hover:scale-105 active:scale-95 cursor-pointer focus:outline-none"
            aria-label="Mở trợ lý du lịch AI"
          >
            <img 
              src="/mascot_welcome.webp" 
              alt="Mascot V-OTA" 
              className="w-20 h-20 sm:w-24 sm:h-24 object-contain select-none drop-shadow-xl" 
            />
            <span className="absolute bottom-1 right-2 w-3.5 h-3.5 bg-emerald-500 border-2 border-white rounded-full shadow-xs"></span>
          </button>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 2. CHẾ ĐỘ SIDEBAR (Mở trượt từ MÉP TRÁI)                                   */}
      {/* ========================================================================= */}
      {isOpen && !isExpanded && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          {/* Backdrop mờ phía sau - bấm vào để đóng */}
          <div 
            onClick={() => setIsOpen(false)}
            className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs transition-opacity duration-300"
          />

          {/* Slide-over Drawer từ mép trái màn hình - Chiếm 4 phần (4/12) trên desktop */}
          <div className="fixed inset-y-0 left-0 w-full sm:w-[420px] md:w-1/3 lg:w-4/12 min-w-[380px] max-w-[640px] bg-white shadow-2xl flex flex-col border-r border-slate-100 z-10 animate-in slide-in-from-left duration-300 ease-out">
            {/* Top Bar tối giản khi chưa mở rộng: Không Header xanh, giữ icon List + mock title bên trái, icon Mở rộng & icon Tắt bên phải */}
            <div className="px-4 pt-3.5 pb-2 bg-white flex items-center justify-between border-b border-slate-100/60 shadow-xs">
              {/* Bên trái: Icon List + Mock Title */}
              <div className="flex items-center space-x-2 text-slate-700 min-w-0 flex-1 mr-2">
                <button 
                  type="button"
                  onClick={() => setIsHistoryOpen(prev => !prev)} 
                  className="p-1.5 text-slate-600 hover:text-slate-900 rounded-lg hover:bg-slate-100 transition cursor-pointer shrink-0"
                  title="Danh sách hội thoại & Tạo chat mới"
                  aria-label="Danh sách hội thoại & Tạo chat mới"
                >
                  <List className="w-4 h-4" />
                </button>
                <span className="text-sm font-semibold text-slate-800 truncate">
                  {activePlan?.title || 'Trợ lý du lịch AI'}
                </span>
              </div>

              {/* Bên phải: 2 icon Mở rộng (Maximize2) và icon Tắt (X) */}
              <div className="flex items-center space-x-1 shrink-0">
                <button 
                  type="button"
                  onClick={() => setIsExpanded(true)} 
                  className="p-1.5 text-slate-600 hover:text-slate-900 rounded-lg hover:bg-slate-100 transition cursor-pointer"
                  title="Mở rộng toàn màn hình"
                  aria-label="Mở rộng toàn màn hình"
                >
                  <Maximize2 className="w-4 h-4" />
                </button>
                <button 
                  type="button"
                  onClick={() => setIsOpen(false)} 
                  className="p-1.5 text-slate-600 hover:text-rose-600 rounded-lg hover:bg-rose-50 transition cursor-pointer"
                  title="Đóng"
                  aria-label="Đóng"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Sub-sidebar trượt ra hiển thị History Conversation & New Chat trong chế độ Sidebar */}
            {isHistoryOpen && renderHistoryDrawer()}


            {/* Khung chat */}
            <div className="flex-1 overflow-hidden">
              {renderChatColumn()}
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 3. CHẾ ĐỘ TOÀN MÀN HÌNH (Full Width, Full Height - 4 phần Trái / 8 phần Phải) */}
      {/* ========================================================================= */}
      {isOpen && isExpanded && (
        <div className="fixed inset-0 z-50 bg-slate-100 flex flex-col overflow-hidden animate-in fade-in duration-200">
          {/* Floating Control Buttons: Thu nhỏ về sidebar & Đóng hoàn toàn (Top-Right) */}
          <div className="absolute top-3.5 right-3.5 z-[1100] flex items-center space-x-1.5 bg-white/90 backdrop-blur-md p-1.5 rounded-2xl shadow-lg border border-slate-200/80">
            <button 
              onClick={() => setIsExpanded(false)} 
              className="p-2 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-xl transition cursor-pointer"
              title="Thu nhỏ về sidebar"
              aria-label="Thu nhỏ về sidebar"
            >
              <Minimize2 className="w-4 h-4" />
            </button>
            <button 
              onClick={() => {
                setIsExpanded(false);
                setIsOpen(false);
              }} 
              className="p-2 text-slate-600 hover:text-rose-600 hover:bg-rose-50 rounded-xl transition cursor-pointer"
              title="Đóng"
              aria-label="Đóng"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Sub-sidebar trượt ra hiển thị History Conversation & New Chat - Overlay toàn bộ 12/12 */}
          {isHistoryOpen && renderHistoryDrawer()}

          {/* Main Container: Flex layout với hiệu ứng trượt vào/ra (slide in/out) mượt mà */}
          <div className="flex flex-1 h-full overflow-hidden relative">
            {/* =================================================================== */}
            {/* CỘT TRÁI (KHUNG CHAT AI): HIỆU ỨNG TRƯỢT VÀO VÀ TRƯỢT RA (SLIDE IN/OUT) */}
            {/* =================================================================== */}
            <div 
              className={`h-full shrink-0 flex flex-col bg-white border-r border-slate-100/90 shadow-xs transition-all duration-300 ease-in-out overflow-hidden z-20 ${
                isChatCollapsed 
                  ? 'w-0 opacity-0 -translate-x-4 pointer-events-none hidden lg:flex' 
                  : 'w-full lg:w-4/12 opacity-100 translate-x-0 flex'
              }`}
            >
              <div className="w-full min-w-[320px] lg:min-w-[380px] h-full flex flex-col">
                {/* Top chat bar: Icon List + Mock Title (không border, không khác màu) */}
                <div className="px-4 pt-3.5 pb-2 bg-white flex items-center justify-between shrink-0">
                  <div className="flex items-center space-x-2 text-slate-700">
                    <button 
                      type="button"
                      onClick={() => setIsHistoryOpen(prev => !prev)}
                      className="p-1.5 text-slate-600 hover:text-slate-900 rounded-lg hover:bg-slate-100 transition cursor-pointer"
                      title="Danh sách hội thoại & Tạo chat mới"
                      aria-label="Danh sách hội thoại & Tạo chat mới"
                    >
                      <List className="w-4 h-4" />
                    </button>
                    <span className="text-sm font-semibold text-slate-800 truncate">
                      {activePlan?.title || 'Trợ lý du lịch AI'}
                    </span>
                  </div>
                </div>

                <div className="flex-1 overflow-hidden">
                  {renderChatColumn()}
                </div>
              </div>
            </div>

            {/* =================================================================== */}
            {/* CỘT PHẢI: TÁCH 2 PHẦN (LỘ TRÌNH CÓ HEADER & MAP KHÔNG CÓ HEADER)  */}
            {/* Khi thu nhỏ chat, cột phải mở rộng trọn vẹn toàn bộ không gian    */}
            {/* =================================================================== */}
            <div className={`relative ${isChatCollapsed ? 'flex' : 'hidden lg:flex'} flex-1 h-full min-w-0 bg-slate-50/50`}>
              {/* Nút thu nhỏ / mở rộng nằm ngay tại ranh giới giữa cột 1 và cột 2 */}
              <button
                type="button"
                onClick={() => setIsChatCollapsed(prev => !prev)}
                className={`hidden lg:flex absolute top-1/2 -translate-y-1/2 z-30 transition-all duration-200 cursor-pointer items-center justify-center ${
                  isChatCollapsed
                    ? 'left-0 w-6 h-12 bg-white hover:bg-blue-50 text-slate-500 hover:text-blue-600 border border-l-0 border-slate-300/80 rounded-r-xl shadow-md hover:w-7'
                    : '-left-3.5 w-7 h-7 bg-white hover:bg-slate-50 text-slate-500 hover:text-blue-600 border border-slate-200 rounded-full shadow-md hover:scale-110'
                }`}
                title={isChatCollapsed ? "Mở rộng Khung Chat AI Assistant" : "Thu nhỏ Khung Chat AI Assistant"}
                aria-label={isChatCollapsed ? "Mở rộng Khung Chat AI Assistant" : "Thu nhỏ Khung Chat AI Assistant"}
              >
                {isChatCollapsed ? (
                  <ChevronRight className="w-4 h-4" />
                ) : (
                  <ChevronLeft className="w-4 h-4" />
                )}
              </button>
              {activePlan ? (
                <div className="grid grid-cols-1 md:grid-cols-2 w-full h-full overflow-hidden divide-x divide-slate-100">
                  {/* PHẦN Ở GIỮA: DANH SÁCH LỘ TRÌNH (CÓ HEADER) */}
                  <div className="flex flex-col h-full bg-white overflow-hidden">
                    {/* Header của phần ở giữa */}
                    <div className="p-4 bg-white border-b border-slate-100 space-y-3 shrink-0 shadow-2xs">
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <div>
                          <h2 className="text-base font-bold text-slate-900 tracking-tight">
                            {activePlan.title}
                          </h2>
                          <div className="flex items-center gap-3 text-sm text-slate-500 mt-1">
                            <span className="flex items-center gap-1.5">
                              <MapPin className="w-3.5 h-3.5 text-slate-400" />
                              {activePlan.intent.destination}
                            </span>
                            <span className="flex items-center gap-1.5">
                              <Calendar className="w-3.5 h-3.5 text-slate-400" />
                              {activePlan.intent.days} ngày
                            </span>
                            <span className="flex items-center gap-1.5">
                              <Users className="w-3.5 h-3.5 text-slate-400" />
                              {activePlan.intent.party === 'family_with_kids' ? 'Gia đình' : 'Cặp đôi'}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Day Tabs Selector */}
                      <div className="flex items-center gap-1.5 bg-slate-100/80 p-1 rounded-xl overflow-x-auto no-scrollbar">
                        <button
                          onClick={() => setActiveDayTab(0)}
                          className={`px-3.5 py-1.5 rounded-lg text-sm font-bold transition-all cursor-pointer whitespace-nowrap ${
                            activeDayTab === 0
                              ? 'bg-blue-600 text-white shadow-xs'
                              : 'text-slate-600 hover:text-slate-900'
                          }`}
                        >
                          Tất cả
                        </button>
                        {activePlan.days.map((d) => (
                          <button
                            key={d.day}
                            onClick={() => setActiveDayTab(d.day)}
                            className={`px-3.5 py-1.5 rounded-lg text-sm font-bold transition-all cursor-pointer whitespace-nowrap ${
                              activeDayTab === d.day
                                ? 'bg-blue-600 text-white shadow-xs'
                                : 'text-slate-600 hover:text-slate-900'
                            }`}
                          >
                            Ngày {d.day}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Nội dung danh sách chi tiết lộ trình cuộn - Nền trắng đồng bộ */}
                    <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-white">
                      {/* Render Days (Tất cả các ngày hoặc ngày đang chọn) */}
                      {activePlan.days
                        .filter((d) => activeDayTab === 0 || d.day === activeDayTab)
                        .map((dayItem) => {
                          const dayIndex = activePlan.days.findIndex((day) => day.day === dayItem.day);
                          const dayStartOrder = activePlan.days
                            .slice(0, dayIndex)
                            .reduce((total, day) => total + day.slots.length, 0);
                          const stayForThisDay = activePlan.stays && activePlan.stays.length >= 2
                            ? (dayItem.day <= Math.ceil(activePlan.days.length / 2) ? activePlan.stays[0] : activePlan.stays[1])
                            : activePlan.stay;
                          const stayHotelName = stayForThisDay?.product?.name || 'Khách sạn lưu trú';
                          const hotelVisuals = stayForThisDay?.product ? getHotelVisuals(stayForThisDay.product, activePlan.intent.destination) : null;

                          return (
                            <div key={dayItem.day} className="space-y-4 pt-1">
                              {/* Day Header Badge */}
                              <div className="flex items-center pt-1">
                                <span className="px-3.5 py-1.5 rounded-xl bg-blue-600 text-white text-sm font-bold shadow-xs">
                                  Ngày {dayItem.day}
                                </span>
                              </div>

                              {/* Vertical Timeline Track */}
                              <div className="relative pl-6 sm:pl-7 border-l-2 border-dashed border-blue-200 ml-3.5 sm:ml-4 space-y-4 my-2">
                                {/* Khách sạn lưu trú được tích hợp trực tiếp vào lộ trình ngày - Visual to rõ, ít nhất 2 ảnh */}
                                {stayForThisDay?.product && hotelVisuals && (
                                  <div className="relative group">
                                    {/* Timeline Step Node với Icon Khách Sạn */}
                                    <div className="absolute -left-[31px] sm:-left-[35px] top-3.5 w-6 h-6 sm:w-7 sm:h-7 rounded-full bg-indigo-600 text-white border-2 border-white shadow-xs flex items-center justify-center z-10">
                                      <Hotel className="w-3 h-3 sm:w-3.5 sm:h-3.5" />
                                    </div>

                                    {/* Hotel Card trong Lộ trình - Layout ưu tiên VISUAL TO RÕ (Ít nhất 2 ảnh: Biệt Thự & Hồ Bơi) */}
                                    <div 
                                      onClick={() => {
                                        if (stayForThisDay.product) {
                                          window.open(`/product/${stayForThisDay.product.id}`, '_blank', 'noopener,noreferrer');
                                        }
                                      }}
                                      onMouseEnter={() => {
                                        if (stayForThisDay.product?.coordinates) {
                                          setHoveredCoordinate(stayForThisDay.product.coordinates);
                                          setHoveredPointId('stay-' + (stayForThisDay.productId || 'default'));
                                        }
                                      }}
                                      onMouseLeave={() => {
                                        setHoveredCoordinate(null);
                                        setHoveredPointId(null);
                                      }}
                                      className="p-3.5 sm:p-4 rounded-2xl bg-white border border-slate-100 cursor-pointer space-y-3"
                                    >
                                      {/* Row 1: Header / Giá phòng */}
                                      <div className="flex items-center justify-between gap-2 pb-2 border-b border-slate-100">
                                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-indigo-50 text-indigo-700 text-xs font-bold">
                                          <Hotel className="w-3.5 h-3.5 text-indigo-600" />
                                          Khách sạn lưu trú {'dayRange' in stayForThisDay && stayForThisDay.dayRange ? `(${stayForThisDay.dayRange})` : ''}
                                        </span>
                                        <span className="text-sm font-black text-indigo-950 font-mono">
                                          {stayForThisDay.product.unitPrice != null ? `${stayForThisDay.product.unitPrice.toLocaleString('vi-VN')} ₫/đêm` : 'Chưa có giá'}
                                        </span>
                                      </div>

                                      {/* Row 2: Tên khách sạn & Icon link */}
                                      <div className="flex items-start justify-between gap-2">
                                        <h4 className="text-[15px] sm:text-base font-bold text-slate-900 leading-snug">
                                          {stayHotelName}
                                        </h4>
                                        <div className="p-1 text-slate-400 shrink-0">
                                          <ExternalLink className="w-4 h-4" />
                                        </div>
                                      </div>

                                      {/* Row 3: Hot Feature Tags trực quan: Điểm đến, Biệt Thự, Hồ Bơi, View Biển... */}
                                      <div className="flex items-center gap-1.5 flex-wrap">
                                        {hotelVisuals.tags.map((tag, tIdx) => (
                                          <span 
                                            key={tIdx} 
                                            className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-lg bg-slate-50 border border-slate-200/80 text-xs font-semibold text-slate-700"
                                          >
                                            <span>{tag.icon}</span>
                                            <span>{tag.label}</span>
                                          </span>
                                        ))}
                                      </div>

                                      {/* Row 4: KHÔNG GIAN HÌNH ẢNH TO RÕ (LƯỚI 2 ẢNH: BIỆT THỰ + HỒ BƠI/VIEW BIỂN) - KHÓA TỶ LỆ KHUNG HÌNH CHUẨN */}
                                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-1">
                                        {hotelVisuals.images.map((img, iIdx) => (
                                          <div 
                                            key={iIdx} 
                                            className="relative aspect-[4/3] sm:aspect-[16/10] w-full rounded-xl overflow-hidden bg-slate-100 shadow-2xs"
                                          >
                                            <img 
                                              src={img.url} 
                                              alt={stayHotelName} 
                                              className="w-full h-full object-cover"
                                            />
                                          </div>
                                        ))}
                                      </div>

                                      {/* Row 5: Ghi chú súc tích */}
                                      <p className="text-xs sm:text-sm text-slate-600 leading-relaxed pt-0.5">
                                        {stayForThisDay.note || 'Khách sạn lưu trú tiêu chuẩn cao cấp, điểm xuất phát và nghỉ ngơi thuận tiện cho cả ngày.'}
                                      </p>
                                    </div>
                                  </div>
                                )}

                                {/* Các chặng hoạt động trong ngày - ƯU TIÊN VISUAL TO RÕ */}
                                {dayItem.slots.map((slot, sIdx) => {
                                  const stepNumber = dayStartOrder + sIdx + 1;
                                  const formattedTimeRange = slot.timeRange || (
                                    slot.time === 'morning' ? '08:30 - 11:30' :
                                    slot.time === 'noon' ? '11:45 - 13:30' :
                                    slot.time === 'afternoon' ? '14:30 - 17:30' : '18:00 - 21:00'
                                  );

                                  const stopTitle = slot.activityTitle || (slot.product ? slot.product.name : 'Hoạt động trải nghiệm');
                                  const locationTitle = slot.locationName || (slot.product ? slot.product.name : slot.address ? slot.address.split(',')[0] : 'Khu vực trung tâm');
                                  const slotImgUrl = getSlotVisualUrl(slot, activePlan.intent.destination);

                                  return (
                                    <div key={sIdx} className="relative">
                                      {/* Timeline Step Node */}
                                      <div className="absolute -left-[31px] sm:-left-[35px] top-3.5 w-6 h-6 sm:w-7 sm:h-7 rounded-full bg-blue-600 text-white border-2 border-white shadow-xs flex items-center justify-center text-[11px] sm:text-xs font-black z-10">
                                        {stepNumber}
                                      </div>

                                      {/* Stop Card - Layout ưu tiên VISUAL TO RÕ - KHÔNG HOVER ANIMATIONS */}
                                      <div 
                                        onClick={() => {
                                          if (slot.product) {
                                            window.open(`/product/${slot.product.id}`, '_blank', 'noopener,noreferrer');
                                          }
                                        }}
                                        onMouseEnter={() => {
                                          const coord = slot.coordinates || slot.product?.coordinates;
                                          if (coord) {
                                            setHoveredCoordinate(coord);
                                            setHoveredPointId(`day-${dayItem.day}-slot-${slot.time}-${stepNumber}`);
                                          }
                                        }}
                                        onMouseLeave={() => {
                                          setHoveredCoordinate(null);
                                          setHoveredPointId(null);
                                        }}
                                        className={`p-3.5 sm:p-4 rounded-2xl bg-white border border-slate-100 space-y-3 ${slot.product ? 'cursor-pointer' : ''}`}
                                      >
                                        {/* Row 1: Khung giờ + Phân loại dịch vụ + Địa điểm */}
                                        <div className="flex items-center justify-between gap-2 pb-2 border-b border-slate-100 flex-wrap">
                                          <div className="flex items-center gap-1.5 flex-wrap">
                                            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-lg bg-blue-50 text-blue-700 text-xs font-black font-mono tracking-wide">
                                              <Clock className="w-3.5 h-3.5 text-blue-600" />
                                              {formattedTimeRange}
                                            </span>
                                            {slot.product && (
                                              <span className="px-2.5 py-0.5 rounded-lg bg-slate-100 text-slate-700 text-xs font-semibold">
                                                {slot.product.taxonomy === 'attraction' ? '🎡 Vé vui chơi giải trí' :
                                                 slot.product.taxonomy === 'combo' ? '✨ Combo & Show' : '🛎️ Dịch vụ nghỉ dưỡng'}
                                              </span>
                                            )}
                                          </div>
                                          <span className="text-xs text-slate-500 font-medium truncate max-w-[55%] flex items-center gap-1 justify-end">
                                            <MapPin className="w-3 h-3 text-slate-400 shrink-0" />
                                            <span className="truncate">{locationTitle}</span>
                                          </span>
                                        </div>

                                        {/* Row 2: Tên chặng hoạt động & Giá vé */}
                                        <div className="flex items-start justify-between gap-2">
                                          <h4 className="text-[15px] sm:text-base font-bold text-slate-900 leading-snug">
                                            {stopTitle}
                                          </h4>
                                          <div className="flex items-center gap-2 shrink-0">
                                            {slot.product && slot.product.unitPrice != null && (
                                              <span className="text-sm font-black font-mono text-indigo-950">
                                                {slot.product.unitPrice.toLocaleString('vi-VN')} ₫
                                              </span>
                                            )}
                                            {slot.product && (
                                              <div className="p-1 text-slate-400">
                                                <ExternalLink className="w-4 h-4" />
                                              </div>
                                            )}
                                          </div>
                                        </div>

                                        {/* Row 3: KHÔNG GIAN ẢNH TO RÕ CỦA CHẶNG HOẠT ĐỘNG - TỶ LỆ CHUẨN 16:9 KHÔNG KÉO DÃN KHI CO DÃN CỘT */}
                                        <div className="relative aspect-[16/9] w-full rounded-xl overflow-hidden shadow-2xs bg-slate-100">
                                          <img 
                                            src={slotImgUrl} 
                                            alt={stopTitle} 
                                            className="w-full h-full object-cover"
                                          />
                                        </div>

                                        {/* Row 4: Ghi chú súc tích */}
                                        <p className="text-xs sm:text-sm text-slate-600 leading-relaxed pt-0.5">
                                          {slot.note}
                                        </p>
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          );
                        })}
                    </div>

                    {/* Footer của phần lịch trình: Tổng tiền & Nút Thanh Toán */}
                    <div className="p-4 bg-white border-t border-slate-100 flex items-center justify-between gap-4 shrink-0 shadow-xs">
                      <div>
                        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">
                          Tổng tiền
                        </span>
                        <span className="text-lg font-black text-blue-900 font-mono">
                          {new Intl.NumberFormat('vi-VN').format(activePlan.totalEstimatedPrice)} ₫
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={handleToggleSavePlan}
                          className={`p-2.5 rounded-xl border transition cursor-pointer flex items-center justify-center shrink-0 ${
                            isSavedPlan 
                              ? 'bg-amber-50 border-amber-300 text-amber-600 hover:bg-amber-100' 
                              : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-slate-900 shadow-2xs'
                          }`}
                          title={isSavedPlan ? "Đã lưu hành trình" : "Lưu hành trình"}
                          aria-label="Lưu hành trình"
                        >
                          <Bookmark className={`w-4 h-4 ${isSavedPlan ? 'fill-amber-500 text-amber-500' : ''}`} />
                        </button>
                        <button
                          type="button"
                          onClick={handleCheckoutPlan}
                          disabled={isCheckingOut}
                          aria-busy={isCheckingOut}
                          className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 disabled:opacity-60 disabled:cursor-wait text-white text-sm font-bold rounded-xl shadow-xs transition flex items-center gap-2 cursor-pointer"
                        >
                          <span>{isCheckingOut ? 'Đang thêm vào giỏ…' : 'Thanh toán'}</span>
                          {isCheckingOut ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* PHẦN MAP BÊN PHẢI (KHÔNG CÓ HEADER - FULL HEIGHT) */}
                  <div className="h-full relative overflow-hidden bg-slate-100 flex flex-col">
                    <ItineraryMap 
                      plan={activePlan}
                      activeDay={activeDayTab}
                      onSelectDay={setActiveDayTab}
                      onAddToCart={(p) => addToCart(p, 2)}
                      focusedCoordinate={hoveredCoordinate}
                      focusedPointId={hoveredPointId}
                      className="w-full h-full flex-1"
                    />
                  </div>
                </div>
              ) : (
                /* Empty state when plan has not been generated yet */
                <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-slate-50">
                  <div className="w-20 h-20 mb-4 rounded-3xl bg-blue-100/60 text-blue-600 flex items-center justify-center shadow-inner">
                    <Compass className="w-10 h-10 animate-pulse" />
                  </div>
                  <h3 className="text-xl font-bold text-slate-900 mb-2">
                    Lộ trình du lịch thông minh & Bản đồ tương tác
                  </h3>
                  <p className="text-base text-slate-600 max-w-md mb-6 leading-relaxed">
                    Hãy nhắn cho AI ở cột bên trái (Ví dụ: &ldquo;Lên lịch trình 3 ngày ở Nha Trang&rdquo; hoặc chọn gợi ý sẵn), 
                    lộ trình chi tiết theo ngày và bản đồ vị trí sẽ tự động xuất hiện song song tại đây!
                  </p>
                  <div className="flex flex-wrap gap-2.5 justify-center">
                    <button
                      onClick={() => handleQuickPrompt('Lịch trình Nha Trang 3 ngày lưu trú 2 khách sạn')}
                      className="px-4 py-2.5 bg-white hover:bg-blue-50 text-blue-700 text-sm font-semibold rounded-xl border border-slate-200 shadow-2xs transition cursor-pointer"
                    >
                      🏨 Lịch trình 3 ngày (2 khách sạn)
                    </button>
                    <button
                      onClick={() => handleQuickPrompt('Lên lịch trình 3 ngày Nha Trang biệt thự hồ bơi')}
                      className="px-4 py-2.5 bg-white hover:bg-blue-50 text-blue-700 text-sm font-semibold rounded-xl border border-slate-200 shadow-2xs transition cursor-pointer"
                    >
                      🏖️ Lịch trình Nha Trang (Biệt thự & Hồ bơi)
                    </button>
                    <button
                      onClick={() => handleQuickPrompt('Lịch trình Phú Quốc 3N2Đ')}
                      className="px-4 py-2.5 bg-white hover:bg-blue-50 text-blue-700 text-sm font-semibold rounded-xl border border-slate-200 shadow-2xs transition cursor-pointer"
                    >
                      🌴 Lịch trình Phú Quốc 3N2Đ
                    </button>
                    <button
                      onClick={() => handleQuickPrompt('Lịch trình Đà Nẵng 2 ngày')}
                      className="px-4 py-2.5 bg-white hover:bg-blue-50 text-blue-700 text-sm font-semibold rounded-xl border border-slate-200 shadow-2xs transition cursor-pointer"
                    >
                      🌉 Lịch trình Đà Nẵng 2 ngày
                    </button>
                    <button
                      onClick={() => handleQuickPrompt('Lịch trình Đà Lạt 7 ngày')}
                      className="px-4 py-2.5 bg-white hover:bg-blue-50 text-blue-700 text-sm font-semibold rounded-xl border border-slate-200 shadow-2xs transition cursor-pointer"
                    >
                      🌲 Lịch trình Đà Lạt 7 ngày
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
};
