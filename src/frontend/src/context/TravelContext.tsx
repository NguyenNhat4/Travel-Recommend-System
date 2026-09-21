'use client';

/**
 * Travel Context & Global Application State
 * Manages seed personas, event tracking, cart, bookings, feedback loop flags, and debug mode.
 */

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
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
import { SEED_PERSONAS } from '../data/personas';
import { CATALOG } from '../data/catalog';

interface ToastState {
  id: string;
  message: string;
  actionText?: string;
  onAction?: () => void;
}

interface TravelContextType {
  currentPersona: UserPersona | null;
  switchPersona: (personaId: string | null) => void;
  currentLocale: SupportedLocale;
  setLocale: (locale: SupportedLocale) => void;
  cart: CartItem[];
  addToCart: (product: Product, quantity?: number, usingDate?: string, checkOutDate?: string) => void;
  removeFromCart: (cartItemId: string) => void;
  updateCartItem: (cartItemId: string, updates: Partial<CartItem>) => void;
  clearCart: () => void;
  activeEvents: UserEvent[];
  recordEvent: (eventType: EventType, product: Product) => void;
  bookings: BookingRecord[];
  createBooking: (contact: BookingContact, guestDetails?: BookingGuestDetails) => Promise<BookingRecord>;
  getBookingByCode: (code: string) => BookingRecord | undefined;
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

  // Default to P1 Minh Anh so demo starts in personalized high-fidelity mode as specified
  const [currentPersona, setCurrentPersona] = useState<UserPersona | null>(SEED_PERSONAS.P1);
  const [activeEvents, setActiveEvents] = useState<UserEvent[]>([]);
  const [cart, setCart] = useState<CartItem[]>([]);
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

  // Switch persona - clears active events and cart for that persona
  const switchPersona = useCallback((personaId: string | null) => {
    if (!personaId) {
      setCurrentPersona(null);
      setCart([]);
      setActiveEvents([]);
      showToast('Đã đăng xuất. Bạn đang ở chế độ khách vãng lai.');
      return;
    }

    const persona = SEED_PERSONAS[personaId];
    if (persona) {
      setCurrentPersona(persona);
      setCart([]);
      setActiveEvents([]);
      setJustBooked(false);
      showToast(`Đã chuyển sang: ${persona.name} (${persona.tagline})`);
      navigate('/');
    }
  }, [showToast, navigate]);

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

  const addToCart = useCallback((
    product: Product, 
    quantity: number = 1, 
    usingDate?: string, 
    checkOutDate?: string
  ) => {
    // Guest must login before write action (§3.1)
    if (!currentPersona) {
      openLoginModal(() => {
        addToCart(product, quantity, usingDate, checkOutDate);
      });
      return;
    }

    let nights = 1;
    if (product.taxonomy === 'hotel' && usingDate && checkOutDate) {
      const d1 = new Date(usingDate).getTime();
      const d2 = new Date(checkOutDate).getTime();
      nights = Math.max(1, Math.round((d2 - d1) / (24 * 3600 * 1000)));
    }

    const unitTotal = product.taxonomy === 'hotel' 
      ? product.unitPrice * nights * quantity 
      : product.unitPrice * quantity;

    const newItem: CartItem = {
      id: 'cart-' + Math.random().toString(36).substring(5),
      productId: product.id,
      product,
      destination: product.destination,
      taxonomy: product.taxonomy,
      usingDate: usingDate || '2026-10-15',
      checkOutDate: checkOutDate || '2026-10-18',
      quantity,
      nights,
      totalPrice: unitTotal
    };

    setCart(prev => [...prev, newItem]);
    recordEvent('add_to_cart', product);

    showToast(
      `Đã thêm "${product.name}" vào giỏ hàng`,
      'Xem giỏ',
      () => navigate('/cart')
    );
  }, [currentPersona, openLoginModal, recordEvent, showToast, navigate]);

  const removeFromCart = useCallback((cartItemId: string) => {
    setCart(prev => {
      const item = prev.find(i => i.id === cartItemId);
      if (item) {
        showToast(`Đã xóa "${item.product.name}"`, 'Hoàn tác', () => {
          setCart(current => [...current, item]);
        });
      }
      return prev.filter(i => i.id !== cartItemId);
    });
  }, [showToast]);

  const updateCartItem = useCallback((cartItemId: string, updates: Partial<CartItem>) => {
    setCart(prev => prev.map(item => {
      if (item.id !== cartItemId) return item;
      const updated = { ...item, ...updates };
      if (updates.quantity !== undefined || updates.nights !== undefined) {
        const qty = updates.quantity ?? item.quantity;
        const n = updates.nights ?? item.nights ?? 1;
        updated.totalPrice = item.taxonomy === 'hotel' 
          ? item.product.unitPrice * n * qty 
          : item.product.unitPrice * qty;
      }
      return updated;
    }));
  }, []);

  const clearCart = useCallback(() => {
    setCart([]);
  }, []);

  const createBooking = useCallback(async (
    contact: BookingContact, 
    guestDetails?: BookingGuestDetails
  ): Promise<BookingRecord> => {
    const refCode = `VOTA-${new Date().toISOString().slice(0, 10).replace(/-/g, '')}-${Math.random().toString(36).substring(2, 6).toUpperCase()}`;
    const totalAmount = cart.reduce((sum, item) => sum + item.totalPrice, 0);
    const dest = cart[0]?.destination || 'Nha Trang';

    const newBooking: BookingRecord = {
      referenceCode: refCode,
      createdAt: new Date().toISOString(),
      userId: currentPersona?.id || 'guest',
      contact,
      items: [...cart],
      totalAmount,
      destination: dest,
      guestDetails
    };

    // Record purchase events for each item (Crucial for Moment K1 feedback loop!)
    cart.forEach(item => {
      recordEvent('purchase', item.product);
    });

    setBookings(prev => [newBooking, ...prev]);
    setCart([]);
    setJustBooked(true);

    return newBooking;
  }, [cart, currentPersona, recordEvent]);

  const getBookingByCode = useCallback((code: string) => {
    return bookings.find(b => b.referenceCode === code);
  }, [bookings]);

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
        switchPersona,
        currentLocale,
        setLocale,
        cart,
        addToCart,
        removeFromCart,
        updateCartItem,
        clearCart,
        activeEvents,
        recordEvent,
        bookings,
        createBooking,
        getBookingByCode,
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
