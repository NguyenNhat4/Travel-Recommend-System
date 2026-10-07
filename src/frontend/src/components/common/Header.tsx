import React, { Suspense, useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useTravel } from '../../context/TravelContext';
import { formatDay } from '../../features/bookings/historyModel';
import { SUPPORTED_LOCALES } from '../../types/locale';
import { AllServicesMenu, NavMenu } from '../layout/nav/NavMenu';
import { NAV_GROUPS, isOverlayRoute, resolveActiveGroup } from '../layout/nav/navConfig';
import {
  PANEL_CLASS, PANEL_LABEL_CLASS, chipClass, controlClass, primaryClass, rowClass, type NavTone,
} from '../layout/nav/headerStyles';
import {
  Luggage,
  ShoppingCart,
  User,
  ChevronDown,
  Settings,
  LogOut,
} from 'lucide-react';

interface HeaderProps {
  isCheckout?: boolean;
}

type ParamSource = { get(name: string): string | null };

interface NavGroupsProps {
  pathname: string;
  tone: NavTone;
  openId: string | null;
  setOpenId: React.Dispatch<React.SetStateAction<string | null>>;
}

function NavGroupsView({ pathname, tone, openId, setOpenId, params }: NavGroupsProps & { params?: ParamSource }) {
  const activeGroup = resolveActiveGroup(pathname, params);
  const setOpen = (id: string) => (open: boolean) =>
    setOpenId((prev) => (open ? id : prev === id ? null : prev));

  return (
    <nav aria-label="Dịch vụ" className="flex items-center gap-1">
      {NAV_GROUPS.map((group) => (
        <NavMenu
          key={group.id}
          group={group}
          active={activeGroup === group.id}
          tone={tone}
          open={openId === group.id}
          onOpenChange={setOpen(group.id)}
          align="center"
          pathname={pathname}
          params={params}
        />
      ))}
      <AllServicesMenu
        tone={tone}
        open={openId === 'all'}
        onOpenChange={setOpen('all')}
        pathname={pathname}
        params={params}
        className="hidden xl:block"
      />
    </nav>
  );
}

function NavGroupsWithParams(props: NavGroupsProps) {
  return <NavGroupsView {...props} params={useSearchParams()} />;
}

/**
 * `useSearchParams` bắt cả nhánh render phía client tới ranh giới Suspense gần nhất. Bọc riêng thanh nhóm để phần còn lại
 * của header vẫn có trong HTML render sẵn; fallback là chính thanh nhóm nhưng chỉ biết `pathname` (đủ cho mọi route trừ
 * `/search?type=` và `/experiences?type=golf`, nơi trạng thái chọn được cập nhật ngay sau khi hydrate).
 */
function NavGroups(props: NavGroupsProps) {
  return (
    <Suspense fallback={<NavGroupsView {...props} />}>
      <NavGroupsWithParams {...props} />
    </Suspense>
  );
}

/** true khi đã cuộn qua phần hero: khi đó header nổi trên ảnh đổi sang nền trắng để chữ không chìm vào nội dung. */
function usePastHero(enabled: boolean) {
  const ref = useRef<HTMLDivElement>(null);
  const [past, setPast] = useState(false);

  useEffect(() => {
    if (!enabled) {
      setPast(false);
      return;
    }
    const element = ref.current;
    if (!element || typeof IntersectionObserver === 'undefined') return;
    const observer = new IntersectionObserver(([entry]) => setPast(!entry.isIntersecting), { threshold: 0 });
    observer.observe(element);
    return () => observer.disconnect();
  }, [enabled]);

  return [ref, past] as const;
}

/** Trang thanh toán đang mở cho một đơn nháp (`/checkout?draft=<mã>`) chứ không phải cho giỏ. */
/**
 * Nút quay lại ở header rút gọn của trang thanh toán. Thanh toán giỏ thì về giỏ; thanh toán một đơn nháp của Đặt ngay
 * (`?draft=`) thì về trang trước (sản phẩm, vé máy bay, trợ lý). Đọc `draft` bằng `useSearchParams` để đúng ngay cả khi
 * vừa chuyển trang (lúc đó `window.location` còn là URL cũ).
 */
function CheckoutBackLabelled({ onCart }: { onCart: () => void }) {
  const isDraft = Boolean(useSearchParams()?.has('draft'));
  return <CheckoutBackButton label={isDraft ? '← Quay lại' : '← Quay lại giỏ hàng'} onClick={isDraft ? () => window.history.back() : onCart} />;
}

function CheckoutBackButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button onClick={onClick} className="text-xs font-semibold text-blue-600 hover:text-blue-800 flex items-center gap-1 transition-colors">
      {label}
    </button>
  );
}

function CheckoutBack({ onCart }: { onCart: () => void }) {
  return (
    <Suspense fallback={<CheckoutBackButton label="← Quay lại giỏ hàng" onClick={onCart} />}>
      <CheckoutBackLabelled onCart={onCart} />
    </Suspense>
  );
}

/** Panel thả xuống của ngôn ngữ, đặt chỗ và tài khoản: cách viên header 12 px, cùng vỏ với menu dịch vụ. */
const DROPDOWN_CLASS = `${PANEL_CLASS} absolute right-0 top-full z-50 mt-3`;

export const Header: React.FC<HeaderProps> = ({ isCheckout = false }) => {
  const {
    currentPersona,
    signOut,
    cartCount,
    cart,
    navigate,
    currentRoute,
    openLoginModal,
    currentLocale,
    setLocale,
    showToast
  } = useTravel();

  // Dropdowns state
  const [isLangDropdownOpen, setIsLangDropdownOpen] = useState(false);
  const [isTripsDropdownOpen, setIsTripsDropdownOpen] = useState(false);
  const [isAccountDropdownOpen, setIsAccountDropdownOpen] = useState(false);
  const [openNavId, setOpenNavId] = useState<string | null>(null);

  // Refs for click outside
  const langDropdownRef = useRef<HTMLDivElement>(null);
  const tripsDropdownRef = useRef<HTMLDivElement>(null);
  const accountDropdownRef = useRef<HTMLDivElement>(null);
  const navRef = useRef<HTMLDivElement>(null);

  const overlayRoute = isOverlayRoute(currentRoute);
  const [heroSentinelRef, pastHero] = usePastHero(overlayRoute && !isCheckout);
  const tone: NavTone = overlayRoute && !pastHero ? 'overlay' : 'solid';

  // Close dropdowns on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      if (langDropdownRef.current && !langDropdownRef.current.contains(target)) {
        setIsLangDropdownOpen(false);
      }
      if (tripsDropdownRef.current && !tripsDropdownRef.current.contains(target)) {
        setIsTripsDropdownOpen(false);
      }
      if (accountDropdownRef.current && !accountDropdownRef.current.contains(target)) {
        setIsAccountDropdownOpen(false);
      }
      if (navRef.current && !navRef.current.contains(target)) {
        setOpenNavId(null);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Đổi trang thì đóng menu nhóm (liên kết trong menu đã tự đóng; đây là lưới an toàn cho điều hướng bằng nút Back).
  useEffect(() => {
    setOpenNavId(null);
  }, [currentRoute]);

  const currentLocaleInfo = SUPPORTED_LOCALES.find(l => l.code === currentLocale) || SUPPORTED_LOCALES[0];

  // Simplified Checkout Header
  if (isCheckout) {
    return (
      <header className="w-full bg-white border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div
            onClick={() => navigate('/')}
            className="flex items-center gap-2 cursor-pointer group"
          >
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white font-display text-lg shadow-xs group-hover:opacity-90 transition-opacity">
              V
            </div>
            <div className="flex items-center gap-1.5">
              <span className="font-display text-xl tracking-wide text-slate-900">V-OTA</span>
              <span className="text-[10px] font-bold px-1.5 py-0.2 rounded-md bg-blue-50 text-blue-700 border border-blue-200">
                Thanh toán an toàn
              </span>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <CheckoutBack onCart={() => navigate('/cart')} />
          </div>
        </div>
      </header>
    );
  }

  const onHero = tone === 'overlay';
  const chevron = (open: boolean) => (
    <ChevronDown className={`h-4 w-4 opacity-70 transition-transform duration-200 ${open ? 'rotate-180' : ''}`} aria-hidden="true" />
  );

  return (
    <>
      {overlayRoute && (
        <div ref={heroSentinelRef} aria-hidden="true" className="pointer-events-none absolute inset-x-0 top-0 h-[360px]" />
      )}
      {/*
        Viên header cao 64 px (56 px mobile). Điều khiển bên trong cao 40 px nên cách mép đều 12 px (8 px mobile). Ở route có hero,
        viên rộng hơn cột nội dung đúng 12 px mỗi bên để logo và nút tài khoản thẳng hàng với tiêu đề và tấm tìm kiếm bên dưới.
      */}
      <header
        className={overlayRoute
          ? 'fixed inset-x-0 top-0 z-40 px-2 pt-3 sm:px-3 lg:px-5'
          : 'w-full bg-white border-b border-slate-200/80 shadow-xs'}
      >
        <div
          className={overlayRoute
            ? `mx-auto max-w-[77.5rem] rounded-full px-2 transition-colors duration-200 sm:px-3 ${
              onHero ? 'glass-pill text-white' : 'bg-white/95 text-slate-900 shadow-lg ring-1 ring-slate-900/5 backdrop-blur'
            }`
            : 'max-w-7xl mx-auto px-3 sm:px-6 lg:px-8'}
        >
          <div className="flex h-14 items-center gap-2 sm:h-16 lg:gap-4">

            {/* Thương hiệu */}
            <Link
              href="/"
              aria-label="V-OTA, về trang chủ"
              className={`group flex shrink-0 items-center gap-3 rounded-full focus-visible:outline-2 focus-visible:outline-offset-4 ${
                onHero ? 'focus-visible:outline-white' : 'focus-visible:outline-blue-600'
              }`}
            >
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-tr from-amber-500 to-amber-300 font-display text-2xl leading-none text-white shadow-md shadow-amber-500/20 transition-transform duration-200 group-hover:scale-105">
                V
              </span>
              <span className="hidden flex-col sm:flex lg:hidden xl:flex">
                <span className={`font-display text-xl uppercase leading-none tracking-wide ${onHero ? 'text-white' : 'text-slate-900'}`}>V-OTA</span>
                <span className={`mt-1 text-[10px] font-medium uppercase leading-none tracking-[0.14em] ${onHero ? 'text-white/80' : 'text-slate-500'}`}>Resorts & Hotels</span>
              </span>
            </Link>

            {/* Nhóm dịch vụ: nằm giữa hai cụm, ẩn dưới 1024 px (lối vào mobile là VerticalChips) */}
            <div ref={navRef} className="hidden min-w-0 flex-1 justify-center lg:flex">
              <NavGroups pathname={currentRoute} tone={tone} openId={openNavId} setOpenId={setOpenNavId} />
            </div>

            {/* Tiện ích: ngôn ngữ, đặt chỗ, tài khoản */}
            <div className="ml-auto flex items-center gap-2 lg:ml-0">

              {/* Language & Currency Selector */}
              <div className="relative" ref={langDropdownRef}>
                <button
                  onClick={() => setIsLangDropdownOpen(!isLangDropdownOpen)}
                  aria-expanded={isLangDropdownOpen}
                  className={controlClass(tone, { active: isLangDropdownOpen, compact: true })}
                  title="Thay đổi ngôn ngữ và tiền tệ"
                >
                  <span className="text-base leading-none">{currentLocaleInfo.flag}</span>
                  <span className="hidden sm:inline lg:hidden xl:inline">{currentLocaleInfo.currencyCode}</span>
                  {chevron(isLangDropdownOpen)}
                </button>

                {isLangDropdownOpen && (
                  <div className={`${DROPDOWN_CLASS} w-72`}>
                    <p className={PANEL_LABEL_CLASS}>Chọn ngôn ngữ & tiền tệ</p>
                    <div className="max-h-72 space-y-0.5 overflow-y-auto">
                      {SUPPORTED_LOCALES.map((loc) => (
                        <button
                          key={loc.code}
                          onClick={() => {
                            setLocale(loc.code);
                            setIsLangDropdownOpen(false);
                            showToast(`Đã chuyển ngôn ngữ sang ${loc.nativeName}`);
                          }}
                          className={`${rowClass(currentLocale === loc.code ? 'selected' : 'default')} justify-between`}
                        >
                          <span className="flex items-center gap-3">
                            <span className="text-lg leading-none">{loc.flag}</span>
                            <span>{loc.nativeName}</span>
                          </span>
                          <span className="font-mono text-xs uppercase text-slate-400">{loc.currencyCode}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Giỏ hàng: chỉ hiện giỏ. Đơn đã đặt xem ở /profile (menu tài khoản), không lặp ở đây. */}
              <div className="relative hidden md:block" ref={tripsDropdownRef}>
                <button
                  onClick={() => setIsTripsDropdownOpen(!isTripsDropdownOpen)}
                  aria-expanded={isTripsDropdownOpen}
                  className={`relative ${controlClass(tone, { active: isTripsDropdownOpen, iconOnly: true })}`}
                  title="Giỏ hàng"
                  aria-label="Giỏ hàng"
                >
                  <ShoppingCart className="h-5 w-5" aria-hidden="true" />
                  {cartCount > 0 && (
                    <span className="absolute right-0 top-0 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-blue-600 px-1 text-[10px] font-bold leading-none text-white shadow-xs">
                      {cartCount}
                    </span>
                  )}
                </button>

                {isTripsDropdownOpen && (
                  <div className={`${DROPDOWN_CLASS} w-80`}>
                    <div className="px-3 pb-1 pt-2">
                      <span className="font-display text-[15px] text-slate-900">Giỏ hàng ({cartCount})</span>
                    </div>

                    <div className="space-y-1 py-1">
                      {cart && cart.items.length > 0 ? (
                        <>
                          {cart.items.slice(0, 3).map((item) => (
                            <button
                              key={item.cartItemId}
                              type="button"
                              onClick={() => {
                                setIsTripsDropdownOpen(false);
                                navigate('/cart');
                              }}
                              className={rowClass('default', { stacked: true })}
                            >
                              <span className="line-clamp-2 text-sm font-semibold text-slate-900">{item.product.name}</span>
                              <span className="text-[13px] text-slate-500">
                                {formatDay(item.usingDate)} · {new Intl.NumberFormat('vi-VN').format(item.lineTotal)} ₫
                              </span>
                            </button>
                          ))}
                          {cart.items.length > 3 && (
                            <p className="px-3 py-1 text-[13px] text-slate-500">và {cart.items.length - 3} dịch vụ khác</p>
                          )}
                        </>
                      ) : (
                        <div className="py-5 text-center text-[13px] text-slate-500">
                          <ShoppingCart className="mx-auto mb-1.5 h-6 w-6 text-slate-300" aria-hidden="true" />
                          <p>Giỏ hàng đang trống</p>
                        </div>
                      )}
                    </div>

                    {cartCount > 0 && (
                      <button
                        onClick={() => {
                          setIsTripsDropdownOpen(false);
                          navigate('/cart');
                        }}
                        className={`${rowClass('accent')} justify-center`}
                      >
                        Xem giỏ hàng →
                      </button>
                    )}
                  </div>
                )}
              </div>

              <span aria-hidden="true" className={`mx-1 hidden h-5 w-px md:block ${onHero ? 'bg-white/30' : 'bg-slate-200'}`} />

              {/* Auth Buttons */}
              {currentPersona ? (
                <div className="relative" ref={accountDropdownRef}>
                  <button
                    onClick={() => setIsAccountDropdownOpen(!isAccountDropdownOpen)}
                    aria-expanded={isAccountDropdownOpen}
                    aria-label={`Tài khoản ${currentPersona.name}`}
                    className={chipClass(tone)}
                  >
                    <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-gradient-to-tr from-blue-700 via-blue-600 to-indigo-500 font-display text-sm leading-none text-white shadow-2xs">
                      {currentPersona.name.split(' ').pop()?.charAt(0) || 'M'}
                    </span>
                    <span className="hidden text-left xl:block">
                      <span className="block max-w-[9rem] truncate font-display text-sm leading-4">{currentPersona.name}</span>
                      <span className={`block font-sans text-xs leading-4 ${onHero ? 'text-white/80' : 'text-blue-600'}`}>Thành viên</span>
                    </span>
                    {chevron(isAccountDropdownOpen)}
                  </button>

                  {isAccountDropdownOpen && (
                    <div className={`${DROPDOWN_CLASS} w-72`}>
                      <div className="mb-1 rounded-2xl bg-slate-50 px-3 py-2.5">
                        <div className="font-display text-[15px] text-slate-900">{currentPersona.name}</div>
                        <div className="text-[13px] text-slate-500">{currentPersona.email}</div>
                      </div>

                      <div className="space-y-0.5">
                        <button
                          onClick={() => {
                            setIsAccountDropdownOpen(false);
                            navigate('/profile');
                          }}
                          className={rowClass()}
                        >
                          <User className="h-4 w-4 text-slate-400" aria-hidden="true" />
                          <span>Hồ sơ cá nhân</span>
                        </button>
                        <button
                          onClick={() => {
                            setIsAccountDropdownOpen(false);
                            navigate('/profile/booking_history');
                          }}
                          className={rowClass()}
                        >
                          <Luggage className="h-4 w-4 text-slate-400" aria-hidden="true" />
                          <span>Chuyến đi & Đặt phòng của tôi</span>
                        </button>
                        <button
                          onClick={() => {
                            setIsAccountDropdownOpen(false);
                            showToast('Cài đặt tài khoản');
                          }}
                          className={rowClass()}
                        >
                          <Settings className="h-4 w-4 text-slate-400" aria-hidden="true" />
                          <span>Cài đặt</span>
                        </button>
                      </div>

                      <div className="mt-1 border-t border-slate-100 pt-1">
                        <button
                          onClick={() => {
                            setIsAccountDropdownOpen(false);
                            void signOut();
                          }}
                          className={rowClass('danger')}
                        >
                          <LogOut className="h-4 w-4" aria-hidden="true" />
                          <span>Đăng xuất</span>
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <button onClick={() => openLoginModal()} className={controlClass(tone)}>
                    Đăng nhập
                  </button>
                  <button onClick={() => navigate('/register')} className={primaryClass()}>
                    Đăng ký
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>
    </>
  );
};
