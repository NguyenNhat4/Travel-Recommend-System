'use client';

/**
 * Travel Context & Global Application State
 * Manages seed personas, event tracking, cart, bookings, feedback loop flags, and debug mode.
 */

import React, { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { UserPersona, Product, UserEvent, EventType } from '../types/travel';
import { SupportedLocale, DEFAULT_LOCALE } from '../types/locale';
import { PERSONA_LOGIN, SEED_PERSONAS } from '../data/personas';
import * as authApi from '../services/auth';
import * as bookingApi from '../services/booking';
import type { AddCartItemRequest, BookingDraft, BookingResponse, CartResponse, GuestCounts, UpdateCartItemRequest } from '../services/booking';
import { ApiError, SESSION_EXPIRED_EVENT } from '../services/http';
import { clearSectionCache } from '../hooks/useLazySection';

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
  /** Sửa họ tên, số điện thoại (FR-USR-04) và cập nhật người dùng hiện tại ngay, không cần đăng nhập lại. */
  updateProfile: (changes: authApi.ProfileChanges) => Promise<authApi.AuthUser>;
  /** Email điền sẵn khi phiên hết hạn giữa chừng (§4.2 điều 4). */
  loginPrefillEmail: string | null;
  currentLocale: SupportedLocale;
  setLocale: (locale: SupportedLocale) => void;
  /** Giỏ phía server (`GET /cart`); null khi là khách hoặc chưa tải xong. Mọi con số tiền lấy từ đây. */
  cart: CartResponse | null;
  cartCount: number;
  refreshCart: () => Promise<CartResponse | null>;
  /**
   * true nếu Backend đã nhận mục. `silent` bỏ toast từng mục (thêm nhiều mục thì caller tự tổng kết). `guests` là số người lớn
   * và trẻ em của mục (FR-BKG-08): dịch vụ tính theo người được bỏ `quantity` khi gửi `guests`.
   */
  addToCart: (
    product: Product, quantity?: number, usingDate?: string, checkOutDate?: string,
    options?: { silent?: boolean; guests?: GuestCounts },
  ) => Promise<boolean>;
  /**
   * Đặt ngay: tạo đơn nháp chỉ gồm các mục này rồi mở trang thanh toán `/checkout?draft=<mã>`; không kèm mục nào trong giỏ
   * (docs/spec/booking/dat-truc-tiep-theo-don-nhap.md §4). Trả null khi không tạo được (đã báo lỗi bằng toast).
   */
  startBooking: (items: BookNowItem[], options?: { allowPartial?: boolean }) => Promise<BookingDraft | null>;
  removeFromCart: (cartItemId: string) => Promise<void>;
  /**
   * Sửa một mục giỏ và cập nhật `cart` bằng response. Trả về lỗi API (null nếu thành công) để checkout gắn lỗi vào thẻ dịch vụ;
   * `silent` bỏ toast lỗi.
   */
  updateCartItem: (cartItemId: string, updates: UpdateCartItemRequest, options?: { silent?: boolean }) => Promise<ApiError | null>;
  activeEvents: UserEvent[];
  recordEvent: (eventType: EventType, product: Product) => void;
  /** Đơn đã tạo hoặc đã xem trong phiên này (contract không có API liệt kê đơn). */
  bookings: BookingResponse[];
  rememberBooking: (booking: BookingResponse) => void;
  getBookingByCode: (code: string) => BookingResponse | undefined;
  justBooked: boolean;
  markJustBooked: () => void;
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
  /**
   * Trang đang mở đăng ký một guard cho `navigate` (trang thanh toán hỏi lại trước khi khách rời, FR-BKG-01). Guard trả `true`
   * là đã chặn lần chuyển trang đó và tự lo phần còn lại; `null` để gỡ.
   */
  setNavigationGuard: (guard: ((route: string) => boolean) | null) => void;
  pendingPostLoginAction: (() => void) | null;
}

/** Một mục của lần Đặt ngay: sản phẩm, ngày, số lượng và số khách như khi thêm giỏ. */
export interface BookNowItem {
  product: Product;
  quantity?: number;
  usingDate?: string;
  checkOutDate?: string;
  guests?: GuestCounts;
}

const TravelContext = createContext<TravelContextType | undefined>(undefined);

function isoDate(date: Date): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh' }).format(date);
}

/** Không chọn ngày (thêm nhanh): ngày mai theo giờ Việt Nam, hoặc ngày mở bán nếu muộn hơn. Backend kiểm lại cửa sổ bán. */
function defaultUsingDate(product: Product): string {
  const tomorrow = isoDate(new Date(Date.now() + 24 * 3600 * 1000));
  return product.availableFrom && product.availableFrom > tomorrow ? product.availableFrom : tomorrow;
}

function nightsBetween(checkIn: string, checkOut?: string): number {
  if (!checkOut) return 1;
  const days = Math.round((Date.parse(checkOut) - Date.parse(checkIn)) / (24 * 3600 * 1000));
  return Math.max(1, days);
}

/** Body của một mục giỏ hoặc mục đơn nháp: cùng quy tắc ngày, số đêm, số lượng và số khách (frontend spec §4.3). */
function lineRequest(item: BookNowItem): AddCartItemRequest {
  const { product, quantity = 1, usingDate, checkOutDate, guests } = item;
  const start = usingDate || defaultUsingDate(product);
  const nights = product.taxonomy === 'hotel' ? nightsBetween(start, checkOutDate) : undefined;
  // Dịch vụ tính theo người gửi `guests` thì Backend tự tính quantity = người lớn + trẻ em; khách sạn và combo gửi cả hai.
  const perPerson = product.taxonomy === 'flight' || product.taxonomy === 'attraction' || product.taxonomy === 'golf';
  return {
    productId: product.id, usingDate: start, nights, ...(guests ? { guests } : {}),
    ...(guests && perPerson ? {} : { quantity }),
  } as AddCartItemRequest;
}

/** Thông điệp cho lỗi thêm/sửa giỏ (docs/spec/hop-dong-tich-hop-frontend.md §8). */
function cartErrorMessage(error: unknown, productName?: string): string {
  if (!(error instanceof ApiError)) return 'Không cập nhật được giỏ hàng. Vui lòng thử lại.';
  const name = productName ? `"${productName}"` : 'Sản phẩm';
  switch (error.code) {
    case 'PRODUCT_NOT_FOUND':
      return `${name} hiện không bán trên V-OTA.`;
    case 'PRODUCT_UNAVAILABLE':
      return `${name} vừa hết chỗ.`;
    case 'DIRECT_BOOKING_ONLY':
      return `${name} được đặt trực tiếp, không thêm vào giỏ hàng. Hãy bấm Đặt ngay.`;
    case 'DATE_OUT_OF_RANGE': {
      const from = error.details?.availableFrom, to = error.details?.availableTo;
      return from && to ? `${name} chỉ mở bán từ ${from} đến ${to}.` : `Ngày sử dụng của ${name} nằm ngoài thời gian mở bán.`;
    }
    case 'NETWORK_ERROR':
      return 'Mất kết nối. Vui lòng thử lại.';
    default:
      return error.message;
  }
}

/** Người dùng của phiên → persona hiển thị. 4 persona seed giữ thẻ demo; tài khoản khác dùng thẻ chung. */
function personaFromUser(user: authApi.AuthUser): UserPersona {
  const seedKey = Object.keys(PERSONA_LOGIN).find((key) => PERSONA_LOGIN[key].cdpUserId === user.cdpUserId);
  if (seedKey) return { ...SEED_PERSONAS[seedKey], email: user.email, name: user.fullName, phone: user.phone ?? null };
  const initials = user.fullName.split(/\s+/).filter(Boolean).slice(-2).map((w) => w[0]).join('').toUpperCase() || 'KH';
  return {
    id: user.cdpUserId, code: initials, name: user.fullName, email: user.email, phone: user.phone ?? null, avatarText: initials,
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
  const [cart, setCartState] = useState<CartResponse | null>(null);
  const [bookings, setBookings] = useState<BookingResponse[]>([]);
  const [justBooked, setJustBooked] = useState<boolean>(false);
  const [debugMode, setDebugMode] = useState<boolean>(false);
  const [toast, setToast] = useState<ToastState | null>(null);
  const [isLoginModalOpen, setIsLoginModalOpen] = useState<boolean>(false);
  const [pendingPostLoginAction, setPendingPostLoginAction] = useState<(() => void) | null>(null);

  // Keep the existing navigation API while delegating URL state to Next.
  const currentRoute = pathname || '/';
  const navigationGuard = useRef<((route: string) => boolean) | null>(null);
  const setNavigationGuard = useCallback((guard: ((route: string) => boolean) | null) => {
    navigationGuard.current = guard;
  }, []);
  const navigate = useCallback((route: string) => {
    if (navigationGuard.current?.(route)) return;
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

  // Response giỏ về không theo thứ tự gửi (GET lúc đăng nhập vs POST ngay sau đó): chỉ nhận bản mới hơn bản đã áp.
  const cartSeq = useRef({ issued: 0, applied: 0 });
  const trackCart = useCallback(async (request: () => Promise<CartResponse>): Promise<CartResponse> => {
    const seq = ++cartSeq.current.issued;
    const response = await request();
    if (seq > cartSeq.current.applied) {
      cartSeq.current.applied = seq;
      setCartState(response);
    }
    return response;
  }, []);

  /** Đổi tài khoản/đăng xuất: xoá MỌI state phía client của người trước (§4.2 điều 6). */
  const resetClientState = useCallback(() => {
    cartSeq.current.applied = ++cartSeq.current.issued;   // bỏ mọi response giỏ của người trước đang bay
    clearSectionCache();
    setCartState(null);
    setActiveEvents([]);
    setBookings([]);
    setJustBooked(false);
  }, []);

  const applySession = useCallback((session: authApi.SessionView) => {
    setCurrentPersona(session.state === 'authenticated' && session.user ? personaFromUser(session.user) : null);
  }, []);

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

  const updateProfile = useCallback(async (changes: authApi.ProfileChanges) => {
    const user = await authApi.updateProfile(changes);
    setCurrentPersona(personaFromUser(user));
    return user;
  }, []);

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

  // Khách chưa đăng nhập cũng có giỏ (BFF gắn mã khách, giỏ nằm ở Redis 3 ngày); sau khi đăng nhập, BFF gộp giỏ khách vào
  // tài khoản trước khi trả `GET /cart` (docs/spec/booking/dat-truc-tiep-theo-don-nhap.md §8).
  const refreshCart = useCallback(async (): Promise<CartResponse | null> => {
    try {
      return await trackCart(bookingApi.getCart);
    } catch (error) {
      console.warn('[cart] GET /cart failed', error);
      return null;
    }
  }, [trackCart]);

  // Giỏ là state phía server: tải khi phiên đã sẵn sàng và mỗi khi người dùng đăng nhập, đăng xuất hoặc đổi tài khoản.
  const personaId = currentPersona?.id ?? null;
  useEffect(() => {
    if (authReady) void refreshCart();
  }, [authReady, personaId, refreshCart]);

  const startBooking = useCallback(async (
    items: BookNowItem[], options: { allowPartial?: boolean } = {},
  ): Promise<BookingDraft | null> => {
    if (!items.length) return null;
    // Đặt ngay cần đăng nhập (FR-BKG-01): mở hộp đăng nhập trên trang; đăng nhập xong thì tạo đơn nháp và vào /checkout.
    if (!personaRef.current) {
      openLoginModal(() => { void startBookingRef.current(items, options); });
      return null;
    }
    let draft: BookingDraft;
    try {
      draft = await bookingApi.createBookingDraft({
        items: items.map(lineRequest), allowPartial: Boolean(options.allowPartial),
      });
    } catch (error) {
      showToast(cartErrorMessage(error, items.length === 1 ? items[0].product.name : undefined));
      return null;
    }
    const accepted = new Set(draft.items.map((i) => i.product.productId));
    for (const item of items) if (accepted.has(item.product.id)) recordEvent('add_to_cart', item.product);
    if (draft.rejectedItems?.length) {
      const names = draft.rejectedItems.map((r) => items.find((i) => i.product.id === r.productId)?.product.name ?? 'Một mục');
      showToast(`Chưa đặt được: ${names.join(', ')}. Các mục còn lại vẫn trong lần thanh toán này.`);
    }
    // Tour, trải nghiệm, tiện ích của lần đặt được chép vào giỏ: cập nhật số đếm giỏ.
    void refreshCart();
    navigate(bookingApi.checkoutPathOf(draft.draftId));
    return draft;
  }, [showToast, recordEvent, refreshCart, navigate, openLoginModal]);

  // Bản `startBooking` mới nhất cho callback sau đăng nhập (tránh closure cũ).
  const startBookingRef = useRef(startBooking);
  useEffect(() => { startBookingRef.current = startBooking; });

  const addToCart = useCallback(async (
    product: Product,
    quantity: number = 1,
    usingDate?: string,
    checkOutDate?: string,
    options: { silent?: boolean; guests?: GuestCounts } = {},
  ): Promise<boolean> => {
    // Khách sạn và vé máy bay không vào giỏ (R-DIR-02): mọi nơi gọi thêm giỏ cho hai loại này đều thành Đặt ngay.
    if (!bookingApi.isCartEligible(product.taxonomy)) {
      await startBooking([{ product, quantity, usingDate, checkOutDate, guests: options.guests }]);
      return false;
    }
    try {
      // Không cần đăng nhập: khách chưa đăng nhập có giỏ riêng, được gộp vào tài khoản khi đăng nhập (§8).
      await trackCart(() => bookingApi.addCartItem(lineRequest({ product, quantity, usingDate, checkOutDate, guests: options.guests })));
    } catch (error) {
      if (!options.silent) showToast(cartErrorMessage(error, product.name));
      return false;
    }
    recordEvent('add_to_cart', product);
    if (!options.silent) {
      showToast(`Đã thêm "${product.name}" vào giỏ hàng`, 'Xem giỏ', () => navigate('/cart'));
    }
    return true;
  }, [startBooking, trackCart, recordEvent, showToast, navigate]);

  const removeFromCart = useCallback(async (cartItemId: string) => {
    const item = cart?.items.find((i) => i.cartItemId === cartItemId);
    try {
      await trackCart(() => bookingApi.removeCartItem(cartItemId));
    } catch (error) {
      // 404 CART_ITEM_NOT_FOUND: mục đã không còn, tải lại giỏ, không báo lỗi (§8).
      if (error instanceof ApiError && error.code === 'CART_ITEM_NOT_FOUND') {
        await refreshCart();
        return;
      }
      showToast(cartErrorMessage(error));
      return;
    }
    if (item) {
      showToast(`Đã xóa "${item.product.name}"`, 'Hoàn tác', () => {
        void trackCart(() => bookingApi.addCartItem({
          productId: item.product.productId, usingDate: item.usingDate, quantity: item.quantity,
          nights: item.nights ?? undefined,
        })).catch((error) => showToast(cartErrorMessage(error, item.product.name)));
      });
    }
  }, [cart, trackCart, refreshCart, showToast]);

  const updateCartItem = useCallback(async (
    cartItemId: string, updates: UpdateCartItemRequest, options: { silent?: boolean } = {},
  ): Promise<ApiError | null> => {
    try {
      await trackCart(() => bookingApi.updateCartItem(cartItemId, updates));
      return null;
    } catch (error) {
      const apiError = error instanceof ApiError ? error : new ApiError('Không cập nhật được giỏ hàng.', 'INTERNAL_ERROR', 0, true);
      if (apiError.code === 'CART_ITEM_NOT_FOUND') {
        await refreshCart();
        return apiError;
      }
      if (!options.silent) showToast(cartErrorMessage(error));
      return apiError;
    }
  }, [trackCart, refreshCart, showToast]);

  const rememberBooking = useCallback((booking: BookingResponse) => {
    setBookings((prev) => [booking, ...prev.filter((b) => b.referenceCode !== booking.referenceCode)]);
  }, []);

  const getBookingByCode = useCallback((code: string) => {
    return bookings.find(b => b.referenceCode === code);
  }, [bookings]);

  const markJustBooked = useCallback(() => {
    setJustBooked(true);
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
        updateProfile,
        loginPrefillEmail,
        currentLocale,
        setLocale,
        cart,
        cartCount: cart?.itemCount ?? 0,
        refreshCart,
        addToCart,
        startBooking,
        removeFromCart,
        updateCartItem,
        activeEvents,
        recordEvent,
        bookings,
        rememberBooking,
        getBookingByCode,
        justBooked,
        markJustBooked,
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
        setNavigationGuard,
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
