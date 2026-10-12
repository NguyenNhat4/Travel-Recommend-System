import React, { useState, useRef, useEffect, useLayoutEffect, useMemo, useCallback } from 'react';
import { useTravel } from '../../../context/TravelContext';
import { useAssistant } from '../../../context/AssistantProvider';
import { useAssistantCart, useBookItinerary } from '../../../hooks/useAssistantCart';
import { isCartEligible } from '../../../services/booking';
import { listAssistantConversations, type AssistantConversationList } from '../../../services/assistantHistory';
import { convertItineraryCompletedToGroundedPlan, locateProduct, narrationProducts, stayCardKey, stayOptionCards } from './widgetPlan';
import type { WidgetPlan, WidgetChatMessage, ConversationSession, StayOptionCard } from './widgetTypes';
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
    selectStayOption,
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
  // Khoá (`stayCardKey`) của thẻ khách sạn đang lưu lên server (AC-AGT-04), trong lúc đó hàng thẻ tạm khoá; khoá theo
  // khách sạn vì số phương án đánh lại sau khi đổi.
  const [selectingStay, setSelectingStay] = useState<string | null>(null);
  // Thẻ khách sạn đang xem trước ở cột phải (chưa đổi, chưa lưu) và câu trả lời chứa nó.
  const [stayPreview, setStayPreview] = useState<{ messageId: string; key: string } | null>(null);
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
    // Response mới (lượt mới, hoặc vừa đổi khách sạn) thì cột phải là lịch đã lưu, không còn xem trước.
    setStayPreview(null);
  }, [assistantState.response]);

  // Derive messages from the provider transcript
  const messages = useMemo<WidgetChatMessage[]>(() => {
    if (assistantState.transcript.length === 0) {
      return [];
    }

    return assistantState.transcript.map((item) => {
      let plan: WidgetPlan | undefined = undefined;
      let products: Record<string, Product> | undefined = undefined;
      let stayOptions: StayOptionCard[] | undefined = undefined;
      if (item.response?.status === 'COMPLETED') {
        plan = convertItineraryCompletedToGroundedPlan(item.response);
        products = narrationProducts(item.response);
        stayOptions = stayOptionCards(item.response, plan);
      } else if (item.response?.status === 'FALLBACK') {
        // Câu FALLBACK mời xem các ứng viên "bên dưới": thẻ dựng từ `searchResults`.
        products = narrationProducts(item.response);
      } else if (item.response?.status === 'NEEDS_CLARIFICATION' && item.response.searchResults) {
        // Lượt khám phá (FR-AGT-06): mỗi thẻ đứng ngay sau dòng đầu tiên nhắc sản phẩm, như lời diễn giải lịch trình.
        products = narrationProducts(item.response);
      }

      return {
        id: item.id,
        sender: item.sender,
        text: item.text,
        plan,
        products,
        stayOptions,
        clarificationForm: item.response?.status === 'NEEDS_CLARIFICATION' ? item.response.clarificationForm : undefined,
        // COMPLETED có nút gợi ý từ contract 1.25.0 (ví dụ lập lại lịch từ ngày còn mở bán), cùng cách hiện như hỏi lại.
        suggestions: item.response?.status === 'NO_RESULTS' || item.response?.status === 'NEEDS_CLARIFICATION'
          || item.response?.status === 'COMPLETED'
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

  // Cuộn xuống tin mới nhất khi có tin nhắn mới hoặc chữ của tin cuối dài thêm (đang stream). Không cuộn khi chỉ đổi
  // `response` (bấm thẻ khách sạn): người dùng đang bấm ở giữa bong bóng, kéo xuống cuối là bị "giật".
  const lastMessage = messages[messages.length - 1];
  useEffect(() => {
    if (isOpen && messages.length) {
      chatScrollRef.current?.scrollTo({ top: chatScrollRef.current.scrollHeight, behavior: 'smooth' });
    }
  }, [isOpen, messages.length, lastMessage?.id, lastMessage?.text]);

  // Thu gọn và mở rộng là hai cây DOM khác nhau (`FloatingWidget`), nên khung chat dựng lại và mất vị trí cuộn. Mở rộng vì
  // chạm thẻ khách sạn thì giữ hàng thẻ đó ở giữa khung; còn lại về tin mới nhất như trước. Cuộn tức thì, trước khi vẽ.
  const keepInViewRef = useRef<string | null>(null);
  useLayoutEffect(() => {
    const chat = chatScrollRef.current;
    if (!isOpen || !chat) return;
    const anchor = keepInViewRef.current ? chat.querySelector<HTMLElement>(keepInViewRef.current) : null;
    keepInViewRef.current = null;
    if (!anchor) {
      chat.scrollTop = chat.scrollHeight;
      return;
    }
    const offset = anchor.getBoundingClientRect().top - chat.getBoundingClientRect().top;
    chat.scrollTop += offset - (chat.clientHeight - anchor.offsetHeight) / 2;
  }, [isExpanded]);

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

  const canChangeStay = (message: WidgetChatMessage) =>
    !isRunning && selectingStay === null && message.id === messages[messages.length - 1]?.id;

  // Dải "Đang xem trước" ở cột phải: thẻ đang xem và câu trả lời chứa nó.
  const previewedStay = (() => {
    if (!stayPreview) return null;
    const message = messages.find((item) => item.id === stayPreview.messageId);
    const card = message?.stayOptions?.find((item) => stayCardKey(item) === stayPreview.key);
    return message && card ? { message, card } : null;
  })();

  /** Cột phải hiện `plan` của một thẻ khách sạn; widget đang thu gọn thì mở rộng và giữ hàng thẻ đó trong khung chat. */
  const showStayPlan = (message: WidgetChatMessage, plan: WidgetPlan | undefined) => {
    setSelectedProduct(null);
    setFocusedProductId(null);
    if (!isExpanded) keepInViewRef.current = `[data-message-id="${CSS.escape(message.id)}"] [data-stay-row]`;
    setIsExpanded(true);
    if (plan) setActivePlan(plan);
    setActiveDayTab(1);
  };

  /**
   * Chạm một thẻ khách sạn trong hàng "Phương án khác" (AC-AGT-04, chốt 2026-10-08): cột phải, bản đồ và tổng tiền xem
   * trước lịch của thẻ đó, chưa đổi lịch đã lưu. Chạm thẻ đang chọn thì thôi xem trước.
   */
  const previewStayOption = (message: WidgetChatMessage, card: StayOptionCard) => {
    if (card.index !== null && !canChangeStay(message)) return;
    showStayPlan(message, card.plan);
    setStayPreview(card.index === null ? null : { messageId: message.id, key: stayCardKey(card) });
  };

  const cancelStayPreview = () => {
    if (previewedStay?.message.plan) setActivePlan(previewedStay.message.plan);
    setStayPreview(null);
  };

  /**
   * Nút "Đổi sang khách sạn này": lịch, bản đồ và tổng tiền ở cột phải đổi ngay; lựa chọn được lưu lên server ở nền, không
   * thêm tin nhắn. Server trả về thì hàng thẻ tính lại chênh tiền/km theo lịch mới; lỗi thì quay về lịch cũ. Chỉ hàng thẻ
   * của câu trả lời mới nhất đổi được (server chỉ giữ phương án của lượt gần nhất).
   */
  const chooseStayOption = async (message: WidgetChatMessage, card: StayOptionCard) => {
    if (card.index === null || !canChangeStay(message)) return;
    showStayPlan(message, card.plan);
    setStayPreview(null);
    setSelectingStay(stayCardKey(card));
    const saved = await selectStayOption(card.index);
    setSelectingStay(null);
    if (!saved) {
      if (message.plan) setActivePlan(message.plan);
      showToast('Chưa đổi được khách sạn, bạn thử lại nhé.');
    }
  };

  const addSelectedToCart = selectedProduct?.plan?.cartItems.some((item) => item.product.productId === selectedProduct.productId)
    ? () => addPlanItemToCart(selectedProduct.plan!, selectedProduct.productId)
    : undefined;

  // Panel chi tiết: khách sạn và vé máy bay chỉ có Đặt ngay; tour, golf, combo có thêm Thêm vào giỏ (R-DIR-02).
  const selectedItem = selectedProduct?.plan?.cartItems.find((item) => item.product.productId === selectedProduct.productId);
  const selectedCanAddToCart = Boolean(selectedItem && isCartEligible(selectedItem.product.taxonomy));
  const bookSelectedNow = selectedItem ? () => { void bookItinerary(selectedItem); } : undefined;

  /** "Đặt ngay" trên thẻ trong khung chat (vé máy bay): đặt đúng mục đó của lịch trong câu trả lời chứa thẻ. */
  const bookPlanItem = (plan: WidgetPlan, productId: string) => {
    const item = plan.cartItems.find((candidate) => candidate.product.productId === productId);
    if (item) void bookItinerary(item);
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
      bookNow: () => { void bookItinerary(item); },
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
    isChatCollapsed, setIsChatCollapsed, hoveredCoordinate, hoveredPointId,
    setHoveredCoordinate, setHoveredPointId, focusedProductId, isHistoryOpen, setIsHistoryOpen, conversations, activeSessionId,
    isSignedIn, historyStatus, loadHistory,
    selectedProduct, openProductDetail, closeProductDetail, addPlanItemToCart, addSelectedToCart, cartAddStates, bookPlanItem,
    selectedCanAddToCart, bookSelectedNow, itemActions,
    selectingStay, chooseStayOption, previewStayOption, cancelStayPreview, previewedStay,
    assistantState, isRunning, messages, inputVal, setInputVal, chatScrollRef, retry, abort,
    handleSendMessage, handleQuickPrompt, handleConfirmTripDetails,
    handleStartNewChat, handleSelectConversation };
}

export type FloatingWidgetController = ReturnType<typeof useFloatingWidget>;
