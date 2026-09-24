'use client';

/**
 * Travel Context & Global Application State
 * Manages seed personas, event tracking, cart, bookings, feedback loop flags, and debug mode.
 */

import React, { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { 
  UserPersona, 
  Product, 
  CartItem, 
  BookingRecord, 
  BookingContact, 
  BookingGuestDetails, 
  UserEvent, 
  EventType,
  Destination 
} from '../types/travel';
import { SupportedLocale, DEFAULT_LOCALE } from '../types/locale';
import { PERSONA_LOGIN, SEED_PERSONAS } from '../data/personas';
import * as authApi from '../services/auth';
import * as bookingApi from '../services/booking';
import { SESSION_EXPIRED_EVENT } from '../services/http';

interface ToastState {
  id: string;
  message: string;
  actionText?: string;
  onAction?: () => void;
}

interface TravelContextType {
  currentPersona: UserPersona | null;
  /** false tới khi GET /api/auth/session trả về lần đầu. */
  authReady: boolean;
  /** Đăng xuất, về chế độ khách. */
  signOut: () => Promise<void>;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, fullName: string) => Promise<void>;
  /** Email điền sẵn khi phiên hết hạn giữa chừng (§4.2 điều 4). */
  loginPrefillEmail: string | null;
  currentLocale: SupportedLocale;
  setLocale: (locale: SupportedLocale) => void;
  /** Giỏ phía server (backend §7.1): mọi thao tác trả toàn bộ giỏ và thay state này. */
  cart: CartItem[];
  /** `CartResponse.total` — Web không tự cộng tiền (frontend §4.4). */
  cartTotal: number;
  /** Thêm một đơn vị đặt được (hạng phòng, chuyến bay, vé...). true khi backend đã nhận. */
  addToCart: (product: Product, quantity?: number, usingDate?: string, checkOutDate?: string) => Promise<boolean>;
  removeFromCart: (cartItemId: string) => Promise<void>;
  updateCartItem: (cartItemId: string, updates: { usingDate?: string; quantity?: number; nights?: number }) => Promise<void>;
  clearCart: () => void;
  activeEvents: UserEvent[];
  recordEvent: (eventType: EventType, product: Product) => void;
  bookings: BookingRecord[];
  createBooking: (contact: BookingContact, guestDetails?: BookingGuestDetails) => Promise<BookingRecord>;
  getBookingByCode: (code: string) => BookingRecord | undefined;
  /** Tải lại đơn khi mở thẳng /booking/:referenceCode (GET /bookings/{referenceCode}). */
  loadBooking: (code: string) => Promise<BookingRecord | null>;
  justBooked: boolean;
  clearJustBooked: () => void;
  debugMode: boolean;
  setDebugMode: (enabled: boolean) => void;
  toggleDebugMode: () => void;
  toast: ToastState | null;
  showToast: (message: string, actionText?: string, onAction?: () => void) => void;
  hideToast: () => void;
  isLoginModalOpen: boolean;
  openLoginModal: (onSuccessCallback?: () => void) => void;
  closeLoginModal: () => void;
  currentRoute: string;
  navigate: (route: string) => void;
  pendingPostLoginAction: (() => void) | null;
}

const TravelContext = createContext<TravelContextType | undefined>(undefined);

/** Người dùng của phiên → persona hiển thị. 4 persona seed giữ thẻ demo; tài khoản khác dùng thẻ chung. */
function personaFromUser(user: authApi.AuthUser): UserPersona {
  const seedKey = Object.keys(PERSONA_LOGIN).find((key) => PERSONA_LOGIN[key].cdpUserId === user.cdpUserId);
  if (seedKey) return { ...SEED_PERSONAS[seedKey], email: user.email };
  const initials = user.fullName.split(/\s+/).filter(Boolean).slice(-2).map((w) => w[0]).join('').toUpperCase() || 'KH';
  return {
    id: user.cdpUserId, code: initials, name: user.fullName, email: user.email, avatarText: initials,
    tagline: 'Tài khoản mới', description: 'Tài khoản vừa đăng ký, chưa có lịch sử.',
    historySummary: 'Chưa có lịch sử', coldStart: true, bookedVerticals: [], seedEvents: [],
  };
}

export const TravelProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const router = useRouter();
  const pathname = usePathname();

  // Locale State persisted in localStorage
  const [currentLocale, setCurrentLocaleState] = useState<SupportedLocale>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('v_ota_locale') as SupportedLocale;
      if (saved) return saved;
    }
    return DEFAULT_LOCALE;
  });

  const setLocale = useCallback((locale: SupportedLocale) => {
    setCurrentLocaleState(locale);
    if (typeof window !== 'undefined') {
      try {
        localStorage.setItem('v_ota_locale', locale);
      } catch (e) {
        console.error('Failed to save locale preference', e);
      }
    }
  }, []);

  // Danh tính chỉ đến từ phiên phía server (BFF); khởi đầu là khách tới khi GET /api/auth/session trả về.
  const [currentPersona, setCurrentPersona] = useState<UserPersona | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [loginPrefillEmail, setLoginPrefillEmail] = useState<string | null>(null);
  const personaRef = useRef<UserPersona | null>(null);
  useEffect(() => { personaRef.current = currentPersona; }, [currentPersona]);
  const [activeEvents, setActiveEvents] = useState<UserEvent[]>([]);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [cartTotal, setCartTotal] = useState(0);
  const [bookings, setBookings] = useState<BookingRecord[]>([]);
  const [justBooked, setJustBooked] = useState<boolean>(false);
  const [debugMode, setDebugMode] = useState<boolean>(false);
  const [toast, setToast] = useState<ToastState | null>(null);
  const [isLoginModalOpen, setIsLoginModalOpen] = useState<boolean>(false);
  const [pendingPostLoginAction, setPendingPostLoginAction] = useState<(() => void) | null>(null);

  // Keep the existing navigation API while delegating URL state to Next.
  const currentRoute = pathname || '/';
  const navigate = useCallback((route: string) => {
    router.push(route);
  }, [router]);

  // Keyboard shortcut Shift+D for debug mode
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.shiftKey && (e.key === 'D' || e.key === 'd')) {
        setDebugMode(prev => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);

    // Also check URL parameter ?debug=1
    if (typeof window !== 'undefined' && window.location.search.includes('debug=1')) {
      setDebugMode(true);
    }

    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const showToast = useCallback((message: string, actionText?: string, onAction?: () => void) => {
    const id = Math.random().toString(36).substring(7);
    setToast({ id, message, actionText, onAction });
  }, []);

  const hideToast = useCallback(() => {
    setToast(null);
  }, []);

  // Auto hide toast after 5s
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => {
      setToast(null);
    }, 5000);
    return () => clearTimeout(timer);
  }, [toast]);

  /** Đổi tài khoản/đăng xuất: xoá MỌI state phía client của người trước (§4.2 điều 6). */
  const resetClientState = useCallback(() => {
    setCart([]);
    setCartTotal(0);
    setActiveEvents([]);
    setBookings([]);
    setJustBooked(false);
  }, []);

  const applySession = useCallback((session: authApi.SessionView) => {
    const persona = session.state === 'authenticated' && session.user ? personaFromUser(session.user) : null;
    // Gán ref ngay: hành động chờ sau đăng nhập (vd. thêm giỏ) chạy trước khi effect đồng bộ ref.
    personaRef.current = persona;
    setCurrentPersona(persona);
  }, []);

  const applyCart = useCallback((response: bookingApi.CartResponse) => {
    setCart(bookingApi.cartItemsFromResponse(response));
    setCartTotal(response.total);
  }, []);

  // Giỏ lưu ở backend theo tài khoản: đăng nhập (hoặc khôi phục phiên) thì tải lại.
  const personaId = currentPersona?.id;
  useEffect(() => {
    if (!authReady || !personaId) return;
    let cancelled = false;
    bookingApi.fetchCart()
      .then((response) => { if (!cancelled) applyCart(response); })
      .catch(() => undefined);
    return () => { cancelled = true; };
  }, [authReady, personaId, applyCart]);

  // Reload → khôi phục phiên. Khách (anonymous) thì ở chế độ khách, KHÔNG mở modal (§4.2 điều 3).
  useEffect(() => {
    let cancelled = false;
    authApi.getSession()
      .then((session) => { if (!cancelled) applySession(session); })
      .catch(() => { if (!cancelled) setCurrentPersona(null); })
      .finally(() => { if (!cancelled) setAuthReady(true); });
    return () => { cancelled = true; };
  }, [applySession]);

  const signIn = useCallback(async (email: string, password: string) => {
    const session = await authApi.login(email, password);
    resetClientState();
    applySession(session);
    setLoginPrefillEmail(null);
  }, [applySession, resetClientState]);

  const signUp = useCallback(async (email: string, password: string, fullName: string) => {
    const session = await authApi.register(email, password, fullName);
    resetClientState();
    applySession(session);
  }, [applySession, resetClientState]);

  const signOut = useCallback(async () => {
    await authApi.logout().catch(() => undefined);
    setCurrentPersona(null);
    resetClientState();
    showToast('Đã đăng xuất. Bạn đang ở chế độ khách vãng lai.');
  }, [showToast, resetClientState]);

  const recordEvent = useCallback((eventType: EventType, product: Product) => {
    const newEvent: UserEvent = {
      id: 'ev-' + Math.random().toString(36).substring(5),
      userId: currentPersona?.id || 'guest',
      productId: product.id,
      productName: product.name,
      eventType,
      taxonomy: product.taxonomy,
      destination: product.destination,
      timestamp: new Date().toISOString()
    };
    setActiveEvents(prev => [newEvent, ...prev]);
  }, [currentPersona]);

  const openLoginModal = useCallback((onSuccessCallback?: () => void) => {
    if (onSuccessCallback) {
      setPendingPostLoginAction(() => onSuccessCallback);
    }
    setIsLoginModalOpen(true);
  }, []);

  const closeLoginModal = useCallback(() => {
    setIsLoginModalOpen(false);
    setPendingPostLoginAction(null);
  }, []);

  // BFF báo phiên hết hạn giữa chừng (§3.8 dòng I): về chế độ khách, mở modal có email điền sẵn.
  useEffect(() => {
    const onExpired = () => {
      const persona = personaRef.current;
      if (!persona) return; // khách: BFF đã cấp phiên khách mới, không có gì để báo
      setCurrentPersona(null);
      resetClientState();
      setLoginPrefillEmail(persona.email);
      setIsLoginModalOpen(true);
      showToast('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.');
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired);
  }, [showToast, resetClientState]);

  const addToCart = useCallback(async (
    product: Product,
    quantity: number = 1,
    usingDate?: string,
    checkOutDate?: string
  ): Promise<boolean> => {
    // Khách phải đăng nhập trước thao tác ghi (§3.1). Đọc qua ref: callback sau đăng nhập chạy trước khi state kịp đổi.
    if (!personaRef.current) {
      openLoginModal(() => { void addToCart(product, quantity, usingDate, checkOutDate); });
      return false;
    }
    const day = usingDate || product.availableFrom || new Date().toISOString().slice(0, 10);
    // nights chỉ gửi với hotel (frontend §4.3); backend tính thành tiền và trả lại cả giỏ.
    const nights = product.taxonomy === 'hotel'
      ? Math.max(1, checkOutDate ? Math.round((Date.parse(checkOutDate) - Date.parse(day)) / 86_400_000) : 1)
      : null;
    try {
      applyCart(await bookingApi.addCartItem({ productId: product.id, usingDate: day, quantity, nights }));
    } catch (error) {
      showToast(error instanceof bookingApi.ApiError ? error.message : 'Chưa thêm được vào giỏ. Vui lòng thử lại.');
      return false;
    }
    recordEvent('add_to_cart', product);
    showToast(`Đã thêm "${product.name}" vào giỏ hàng`, 'Xem giỏ', () => navigate('/cart'));
    return true;
  }, [applyCart, openLoginModal, recordEvent, showToast, navigate]);

  const removeFromCart = useCallback(async (cartItemId: string) => {
    const item = cart.find(i => i.id === cartItemId);
    try {
      applyCart(await bookingApi.removeCartItem(cartItemId));
    } catch (error) {
      showToast(error instanceof bookingApi.ApiError ? error.message : 'Chưa xóa được. Vui lòng thử lại.');
      return;
    }
    if (item) {
      showToast(`Đã xóa "${item.product.name}"`, 'Hoàn tác', () => {
        void addToCart(item.product, item.quantity, item.usingDate, item.checkOutDate);
      });
    }
  }, [cart, applyCart, addToCart, showToast]);

  const updateCartItem = useCallback(async (
    cartItemId: string,
    updates: { usingDate?: string; quantity?: number; nights?: number }
  ) => {
    try {
      applyCart(await bookingApi.updateCartItem(cartItemId, updates));
    } catch (error) {
      showToast(error instanceof bookingApi.ApiError ? error.message : 'Chưa cập nhật được giỏ. Vui lòng thử lại.');
    }
  }, [applyCart, showToast]);

  const clearCart = useCallback(() => {
    setCart([]);
    setCartTotal(0);
  }, []);

  const createBooking = useCallback(async (
    contact: BookingContact,
    guestDetails?: BookingGuestDetails
  ): Promise<BookingRecord> => {
    // Quy tắc form → itemDetails (frontend §4.5): hotel/flight gửi tên khách; yêu cầu đặc biệt là của cả đơn.
    const request = guestDetails?.specialRequests?.trim();
    const response = await bookingApi.createBooking({
      contact: { fullName: contact.fullName, email: contact.email, phone: contact.phoneNumber },
      itemDetails: cart.map((item, index) => ({
        cartItemId: item.id,
        ...(item.taxonomy === 'hotel' || item.taxonomy === 'flight' ? { guestNames: [contact.fullName] } : {}),
        ...(index === 0 && request ? { specialRequest: request } : {}),
      })),
    });
    // Backend đã ghi purchase sang CDP trước khi trả 201: /recommendations gọi sau đây đã thấy lượt đặt (K1).
    const record = bookingApi.bookingRecordFromResponse(response, personaRef.current?.id || 'guest');
    cart.forEach(item => recordEvent('purchase', item.product));
    setBookings(prev => [record, ...prev.filter(b => b.referenceCode !== record.referenceCode)]);
    clearCart();
    setJustBooked(true);
    return record;
  }, [cart, clearCart, recordEvent]);

  const getBookingByCode = useCallback((code: string) => {
    return bookings.find(b => b.referenceCode === code);
  }, [bookings]);

  const loadBooking = useCallback(async (code: string) => {
    try {
      const record = bookingApi.bookingRecordFromResponse(await bookingApi.fetchBooking(code), personaRef.current?.id || 'guest');
      setBookings(prev => [record, ...prev.filter(b => b.referenceCode !== record.referenceCode)]);
      return record;
    } catch {
      return null;
    }
  }, []);

  const clearJustBooked = useCallback(() => {
    setJustBooked(false);
  }, []);

  const toggleDebugMode = useCallback(() => {
    setDebugMode(prev => !prev);
  }, []);

  return (
    <TravelContext.Provider
      value={{
        currentPersona,
        authReady,
        signOut,
        signIn,
        signUp,
        loginPrefillEmail,
        currentLocale,
        setLocale,
        cart,
        cartTotal,
        addToCart,
        removeFromCart,
        updateCartItem,
        clearCart,
        activeEvents,
        recordEvent,
        bookings,
        createBooking,
        getBookingByCode,
        loadBooking,
        justBooked,
        clearJustBooked,
        debugMode,
        setDebugMode,
        toggleDebugMode,
        toast,
        showToast,
        hideToast,
        isLoginModalOpen,
        openLoginModal,
        closeLoginModal,
        currentRoute,
        navigate,
        pendingPostLoginAction
      }}
    >
      {children}
    </TravelContext.Provider>
  );
};

export function useTravel() {
  const context = useContext(TravelContext);
  if (!context) {
    throw new Error('useTravel must be used within a TravelProvider');
  }
  return context;
}
