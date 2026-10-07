import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { useTravel } from '../../../context/TravelContext';
import { useAssistant } from '../../../context/AssistantProvider';
import { useAssistantCart, useBookItinerary } from '../../../hooks/useAssistantCart';
import { isCartEligible } from '../../../services/booking';
import { listAssistantConversations, type AssistantConversationList } from '../../../services/assistantHistory';
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

const HISTORY_PAGE_SIZE = 20;
const HISTORY_TITLE_MAX = 35;
const historyTimeFormat = new Intl.DateTimeFormat('vi-VN', {
  timeZone: 'Asia/Ho_Chi_Minh', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
});

type HistoryStatus = 'idle' | 'loading' | 'error';

function truncateTitle(text: string) {
  return text.length > HISTORY_TITLE_MAX ? `${text.slice(0, HISTORY_TITLE_MAX)}...` : text;
}

function toConversationSession(summary: AssistantConversationList['data'][number]): ConversationSession {
  return {
    id: summary.conversationId,
    title: summary.title || 'Hội thoại mới',
    timestamp: historyTimeFormat.format(new Date(summary.updatedAt)),
  };
}

export function useFloatingWidget() {
  const { showToast, currentRoute, currentPersona } = useTravel();
  const personaId = currentPersona?.id ?? null;
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
  const [isCheckingOut, setIsCheckingOut] = useState<boolean>(false);
  const [isChatCollapsed, setIsChatCollapsed] = useState<boolean>(false);
  const [hoveredCoordinate, setHoveredCoordinate] = useState<{ lat: number; lng: number } | null>(null);
  const [hoveredPointId, setHoveredPointId] = useState<string | null>(null);
  // Sản phẩm vừa được bấm từ lời diễn giải trong chat: khung lịch trình cuộn tới và tô viền thẻ này.
  const [focusedProductId, setFocusedProductId] = useState<string | null>(null);
  // Panel chi tiết ở cột phải (PRD user-flow.md §4.2); null thì cột phải là lịch trình + bản đồ.
  const [selectedProduct, setSelectedProduct] = useState<SelectedProduct | null>(null);
  // History Conversation & Drawer States
  const [isHistoryOpen, setIsHistoryOpen] = useState<boolean>(false);
  // Lịch sử lấy từ archive của backend (FR-AGT-01, spec Frontend §9.6); khách không có lịch sử lâu dài.
  const [archivedConversations, setArchivedConversations] = useState<ConversationSession[]>([]);
  const [historyStatus, setHistoryStatus] = useState<HistoryStatus>('idle');
  const historyRequestRef = useRef(0);
  const isSignedIn = personaId !== null;
  const activeSessionId = assistantState.conversationId;

  const isRunning = assistantState.phase === 'connecting' || assistantState.phase === 'streaming';

  const loadHistory = useCallback(async () => {
    const requestId = ++historyRequestRef.current;
    if (!personaId) {
      setArchivedConversations([]);
      setHistoryStatus('idle');
      return;
    }
    setHistoryStatus('loading');
    try {
      const list = await listAssistantConversations(1, HISTORY_PAGE_SIZE);
      if (requestId !== historyRequestRef.current) return;
      setArchivedConversations(list.data.map(toConversationSession));
      setHistoryStatus('idle');
    } catch {
      // Giữ danh sách cũ để người dùng vẫn mở được; panel hiện lỗi và nút Thử lại.
      if (requestId !== historyRequestRef.current) return;
      setHistoryStatus('error');
    }
  }, [personaId]);

  // Đổi tài khoản: bỏ danh sách của tài khoản trước, kể cả response đang bay về.
  useEffect(() => {
    historyRequestRef.current += 1;
    setArchivedConversations([]);
    setHistoryStatus('idle');
  }, [personaId]);

  useEffect(() => {
    if (isHistoryOpen) void loadHistory();
  }, [isHistoryOpen, loadHistory]);

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

  // Cuộc đang chat có thể chưa vào archive (khách, hoặc lượt đầu chưa ghi xong): vẫn hiện ở đầu danh sách.
  const conversations = useMemo<ConversationSession[]>(() => {
    const currentId = assistantState.conversationId;
    const firstUserText = messages.find((m) => m.sender === 'user')?.text;
    if (!currentId || !firstUserText || archivedConversations.some((c) => c.id === currentId)) {
      return archivedConversations;
    }
    return [{ id: currentId, title: truncateTitle(firstUserText), timestamp: 'Đang trò chuyện' }, ...archivedConversations];
  }, [archivedConversations, assistantState.conversationId, messages]);

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
  const bookSelectedNow = selectedItem ? () => { void bookItinerary([selectedItem]); } : undefined;

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
    // Thanh toán tất cả: một đơn nháp gồm mọi mục đặt được của lịch trình (lưu trú và hoạt động), thanh toán một lần.
    setIsCheckingOut(true);
    void bookItinerary(activePlan.cartItems).finally(() => setIsCheckingOut(false));
  };

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
      bookNow: () => { void bookItinerary([item]); },
      addToCart: () => { void addItineraryToCart([item]); },
    };
  };

  const handleStartNewChat = () => {
    // Cuộc cũ đã nằm trong archive của backend; lần mở panel sau tải lại danh sách.
    resetConversation();
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
    if (session.id === assistantState.conversationId) {
      setIsHistoryOpen(false);
      return;
    }
    try {
      await loadConversation(session.id);
    } catch {
      showToast('Không thể mở lại hội thoại. Vui lòng thử lại.');
      return;
    }
    // Lịch trình dựng lại từ response đã lưu qua effect đồng bộ `assistantState.response` ở trên.
    setActivePlan(null);
    setFocusedProductId(null);
    setSelectedProduct(null);
    setActiveDayTab(1);
    setIsHistoryOpen(false);
  };

  return { isOpen, setIsOpen, isExpanded, setIsExpanded, activePlan, activeDayTab, setActiveDayTab,
    isCheckingOut, isChatCollapsed, setIsChatCollapsed, hoveredCoordinate, hoveredPointId,
    setHoveredCoordinate, setHoveredPointId, focusedProductId, isHistoryOpen, setIsHistoryOpen, conversations, activeSessionId,
    isSignedIn, historyStatus, loadHistory,
    selectedProduct, openProductDetail, closeProductDetail, addPlanItemToCart, addSelectedToCart, cartAddStates,
    selectedCanAddToCart, bookSelectedNow, itemActions,
    assistantState, isRunning, messages, inputVal, setInputVal, chatScrollRef, retry, abort,
    handleSendMessage, handleQuickPrompt, handleConfirmTripDetails, handleCheckoutPlan,
    handleStartNewChat, handleSelectConversation };
}

export type FloatingWidgetController = ReturnType<typeof useFloatingWidget>;
