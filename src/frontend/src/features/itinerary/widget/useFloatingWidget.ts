import React, { useState, useRef, useEffect, useMemo } from 'react';
import { useTravel } from '../../../context/TravelContext';
import { useAssistant } from '../../../context/AssistantProvider';
import { useAssistantCart } from '../../../hooks/useAssistantCart';
import { convertItineraryCompletedToGroundedPlan } from './widgetPlan';
import type { WidgetPlan, WidgetChatMessage, ConversationSession } from './widgetTypes';

export function useFloatingWidget() {
  const { addToCart, showToast, navigate, currentRoute } = useTravel();
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

  // Widget States
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [isExpanded, setIsExpanded] = useState<boolean>(false);
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
      setIsSavedPlan(false);
    }
  }, [assistantState.response]);

  // Derive messages from the provider transcript
  const messages = useMemo<WidgetChatMessage[]>(() => {
    if (assistantState.transcript.length === 0) {
      return [];
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
        clarificationForm: item.response?.status === 'NEEDS_CLARIFICATION' ? item.response.clarificationForm : undefined,
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
        } else if (isExpanded) {
          setIsExpanded(false);
        } else if (isOpen) {
          setIsOpen(false);
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isExpanded, isOpen, isHistoryOpen]);

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
    setInputVal(promptText);
  };

  // Xác nhận form gợi ý: đặt câu yêu cầu hoàn chỉnh vào ô nhập để người dùng đọc lại, sửa rồi mới gửi — không tự gửi.
  const handleConfirmTripDetails = (prompt: string) => {
    setInputVal(prompt);
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
    setInputVal('');
    setIsChatCollapsed(false);
    setActiveDayTab(1);
    setIsSavedPlan(false);
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
    setActiveDayTab(1);
    setIsSavedPlan(false);
    setIsHistoryOpen(false);
  };

  const handleDeleteConversation = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    setConversations(prev => prev.filter(c => c.id !== id));
  };

  return { isOpen, setIsOpen, isExpanded, setIsExpanded, activePlan, activeDayTab, setActiveDayTab,
    isSavedPlan, isCheckingOut, isChatCollapsed, setIsChatCollapsed, hoveredCoordinate, hoveredPointId,
    setHoveredCoordinate, setHoveredPointId, isHistoryOpen, setIsHistoryOpen, conversations, activeSessionId,
    assistantState, isRunning, messages, inputVal, setInputVal, chatScrollRef, addToCart, retry, abort,
    handleSendMessage, handleQuickPrompt, handleConfirmTripDetails, handleToggleSavePlan, handleCheckoutPlan,
    handleStartNewChat, handleSelectConversation, handleDeleteConversation };
}

export type FloatingWidgetController = ReturnType<typeof useFloatingWidget>;
