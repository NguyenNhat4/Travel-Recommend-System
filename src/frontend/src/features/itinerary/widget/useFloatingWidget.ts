import React, { useState, useRef, useEffect, useMemo } from 'react';
import { useTravel } from '../../../context/TravelContext';
import { useAssistant } from '../../../context/AssistantProvider';
import { useAssistantCart, useBookItinerary } from '../../../hooks/useAssistantCart';
import { isCartEligible } from '../../../services/booking';
import { convertItineraryCompletedToGroundedPlan, locateProduct, narrationProducts } from './widgetPlan';
import type { WidgetPlan, WidgetChatMessage, ConversationSession } from './widgetTypes';
import type { Product } from '../../../types/travel';
import { useWidgetCart } from './useWidgetCart';

/** Sản phẩm đang mở ở panel chi tiết; `summary` để hiện ngay trong lúc tải, `plan` để biết có đặt được không. */
interface SelectedProduct {
  productId: string;
  summary?: Product;
  plan?: WidgetPlan;
}

export function useFloatingWidget() {
  const { showToast, currentRoute } = useTravel();
  const {
    state: assistantState,
    sendMessage,
    retry,
    abort,
    resetConversation,
    consumeFloatingInitialMessage,
    loadConversation,
  } = useAssistant();
  const addItineraryToCart = useAssistantCart();
  const bookItinerary = useBookItinerary();
  const { addPlanItemToCart, cartAddStates } = useWidgetCart();

  // Widget States
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [isExpanded, setIsExpanded] = useState<boolean>(false);
  const [inputVal, setInputVal] = useState<string>('');
  const [activePlan, setActivePlan] = useState<WidgetPlan | null>(null);
  const [activeDayTab, setActiveDayTab] = useState<number>(1);
  const [isChatCollapsed, setIsChatCollapsed] = useState<boolean>(false);
  const [hoveredCoordinate, setHoveredCoordinate] = useState<{ lat: number; lng: number } | null>(null);
  const [hoveredPointId, setHoveredPointId] = useState<string | null>(null);
  // Sản phẩm vừa được bấm từ lời diễn giải trong chat: khung lịch trình cuộn tới và tô viền thẻ này.
  const [focusedProductId, setFocusedProductId] = useState<string | null>(null);
  // Panel chi tiết ở cột phải (PRD user-flow.md §4.2); null thì cột phải là lịch trình + bản đồ.
  const [selectedProduct, setSelectedProduct] = useState<SelectedProduct | null>(null);
  // History Conversation & Drawer States
  const [isHistoryOpen, setIsHistoryOpen] = useState<boolean>(false);
  const [conversations, setConversations] = useState<ConversationSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string>('conv-current');

  const isRunning = assistantState.phase === 'connecting' || assistantState.phase === 'streaming';

  const chatScrollRef = useRef<HTMLDivElement>(null);


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
    }
  }, [assistantState.response]);

  // Derive messages from the provider transcript
  const messages = useMemo<WidgetChatMessage[]>(() => {
    if (assistantState.transcript.length === 0) {
      return [];
    }

    return assistantState.transcript.map((item) => {
      let plan: WidgetPlan | undefined = undefined;
      let products: Record<string, Product> | undefined = undefined;
      if (item.response?.status === 'COMPLETED') {
        plan = convertItineraryCompletedToGroundedPlan(item.response);
        products = narrationProducts(item.response);
      } else if (item.response?.status === 'FALLBACK') {
        // Câu FALLBACK mời xem các ứng viên "bên dưới": thẻ dựng từ `searchResults`.
        products = narrationProducts(item.response);
      }

      return {
        id: item.id,
        sender: item.sender,
        text: item.text,
        plan,
        products,
        clarificationForm: item.response?.status === 'NEEDS_CLARIFICATION' ? item.response.clarificationForm : undefined,
        suggestions: item.response?.status === 'NO_RESULTS' || item.response?.status === 'NEEDS_CLARIFICATION'
          ? item.response.suggestions
          : undefined,
      };
    });
  }, [assistantState.transcript]);

  // Scroll to the latest message
  useEffect(() => {
    if (isOpen && messages.length) {
      chatScrollRef.current?.scrollTo({ top: chatScrollRef.current.scrollHeight, behavior: 'smooth' });

    }
  }, [isOpen, messages, isExpanded]);

  // Handle ESC key to close or minimize
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (isHistoryOpen) {
          setIsHistoryOpen(false);
        } else if (selectedProduct) {
          setSelectedProduct(null);
        } else if (isExpanded) {
          setIsExpanded(false);
        } else if (isOpen) {
          setIsOpen(false);
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isExpanded, isOpen, isHistoryOpen, selectedProduct]);

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

  // Đóng widget khi sang thanh toán hoặc giỏ hàng (toast "Xem giỏ"): widget phủ toàn màn hình nên không đóng thì che mất trang.
  useEffect(() => {
    if (currentRoute.startsWith('/checkout') || currentRoute.startsWith('/cart')) {
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
    setInputVal(promptText);
  };

  // Xác nhận form gợi ý: gửi ngay câu yêu cầu hoàn chỉnh (PRD user-flow.md, AC-AGT-01).
  const handleConfirmTripDetails = (prompt: string) => {
    handleSendMessage(prompt);
  };


  /**
   * Bấm thẻ hoặc tên sản phẩm trong lời diễn giải (PRD user-flow.md §4.2): mở widget toàn màn hình với panel chi tiết ở
   * cột phải. Lịch trình của tin nhắn đó được chọn sẵn ngày và focus sản phẩm, nên đóng panel là về đúng chỗ trong lịch.
   * Gói nhiều ngày không nằm trong lịch vẫn mở được panel.
   */
  const openProductDetail = (productId: string, source?: Pick<WidgetChatMessage, 'plan' | 'products'>) => {
    const plan = source?.plan;
    const target = plan ? locateProduct(plan, productId) : null;
    if (plan) setActivePlan(plan);
    if (target) {
      setActiveDayTab(target.day);
      setHoveredCoordinate(target.coordinate);
      setHoveredPointId(target.pointId);
      setFocusedProductId(productId);
    }
    setSelectedProduct({ productId, summary: source?.products?.[productId], plan });
    setIsExpanded(true);
  };

  const closeProductDetail = () => setSelectedProduct(null);

  const addSelectedToCart = selectedProduct?.plan?.cartItems.some((item) => item.product.productId === selectedProduct.productId)
    ? () => addPlanItemToCart(selectedProduct.plan!, selectedProduct.productId)
    : undefined;

  // Panel chi tiết: khách sạn và vé máy bay chỉ có Đặt ngay; tour, golf, combo có thêm Thêm vào giỏ (R-DIR-02).
  const selectedItem = selectedProduct?.plan?.cartItems.find((item) => item.product.productId === selectedProduct.productId);
  const selectedCanAddToCart = Boolean(selectedItem && isCartEligible(selectedItem.product.taxonomy));
  const bookSelectedNow = selectedItem ? () => { void bookItinerary(selectedItem); } : undefined;

  /**
   * Nút riêng của từng sản phẩm trong lịch trình (thẻ và ghim bản đồ): khách sạn, vé máy bay chỉ có Đặt ngay; tour, golf,
   * combo có thêm Thêm vào giỏ. Sản phẩm chưa đặt được (ví dụ khách sạn chưa có hạng phòng) không có nút nào: thẻ vẫn mở
   * trang chi tiết như trước (spec dat-truc-tiep-theo-don-nhap.md §16, ghi chú Q11c).
   */
  const itemActions = (productId: string) => {
    const item = activePlan?.cartItems?.find((i) => i.product.productId === productId);
    if (!item) return null;
    return {
      canAddToCart: isCartEligible(item.product.taxonomy),
      bookNow: () => { void bookItinerary(item); },
      addToCart: () => { void addItineraryToCart([item]); },
    };
  };

  const handleStartNewChat = () => {
    // Nếu phiên hiện tại có tin nhắn từ người dùng, lưu vào danh sách lịch sử
    const hasUserMsg = messages.some(m => m.sender === 'user');
    if (hasUserMsg && assistantState.conversationId) {
      const firstUserMsg = messages.find(m => m.sender === 'user')?.text || 'Hội thoại mới';
      const newSession: ConversationSession = {
        id: assistantState.conversationId,
        title: activePlan?.title || (firstUserMsg.length > 35 ? firstUserMsg.slice(0, 35) + '...' : firstUserMsg),
        timestamp: 'Vừa xong',
        messages: [...messages],
        plan: activePlan
      };
      setConversations(prev => [newSession, ...prev.filter(session => session.id !== newSession.id)]);
    }

    // Reset về hội thoại mới với backend agent
    resetConversation();
    setActiveSessionId('conv-' + Date.now());
    setActivePlan(null);
    setFocusedProductId(null);
    setSelectedProduct(null);
    setInputVal('');
    setIsChatCollapsed(false);
    setActiveDayTab(1);
    setIsHistoryOpen(false);
    showToast('Đã bắt đầu cuộc trò chuyện mới!');
  };

  const handleSelectConversation = async (session: ConversationSession) => {
    try {
      await loadConversation(session.id);
    } catch {
      showToast('Không thể mở lại hội thoại. Vui lòng thử lại.');
      return;
    }
    setActiveSessionId(session.id);
    setActivePlan(session.plan);
    setSelectedProduct(null);
    setActiveDayTab(1);
    setIsHistoryOpen(false);
  };

  const handleDeleteConversation = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    setConversations(prev => prev.filter(c => c.id !== id));
  };

  return { isOpen, setIsOpen, isExpanded, setIsExpanded, activePlan, activeDayTab, setActiveDayTab,
    isChatCollapsed, setIsChatCollapsed, hoveredCoordinate, hoveredPointId,
    setHoveredCoordinate, setHoveredPointId, focusedProductId, isHistoryOpen, setIsHistoryOpen, conversations, activeSessionId,
    selectedProduct, openProductDetail, closeProductDetail, addPlanItemToCart, addSelectedToCart, cartAddStates,
    selectedCanAddToCart, bookSelectedNow, itemActions,
    assistantState, isRunning, messages, inputVal, setInputVal, chatScrollRef, retry, abort,
    handleSendMessage, handleQuickPrompt, handleConfirmTripDetails,
    handleStartNewChat, handleSelectConversation, handleDeleteConversation };
}

export type FloatingWidgetController = ReturnType<typeof useFloatingWidget>;
