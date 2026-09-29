import React, { Suspense, useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useTravel } from '../../context/TravelContext';
import { bookingItems } from '../../services/booking';
import { BOOKING_STATUS_BADGE } from '../confirmation/bookingLabels';
import { SUPPORTED_LOCALES } from '../../types/locale';
import { AllServicesMenu, NavMenu, type NavTone } from '../layout/nav/NavMenu';
import { NAV_GROUPS, isOverlayRoute, resolveActiveGroup } from '../layout/nav/navConfig';
import {
  Sparkles,
  Luggage,
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
      {NAV_GROUPS.map((group, index) => (
        <NavMenu
          key={group.id}
          group={group}
          active={activeGroup === group.id}
          tone={tone}
          open={openId === group.id}
          onOpenChange={setOpen(group.id)}
          align={index >= 2 ? 'right' : 'left'}
          pathname={pathname}
          params={params}
        />
      ))}
      <AllServicesMenu tone={tone} open={openId === 'all'} onOpenChange={setOpen('all')} pathname={pathname} params={params} />
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

export const Header: React.FC<HeaderProps> = ({ isCheckout = false }) => {
  const {
    currentPersona,
    signOut,
    cartCount,
    bookings,
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

  const upcomingBookingsCount = bookings.filter(b => b.status === 'CONFIRMED' || b.status === 'PENDING_PAYMENT').length;
  const activeTripsBadge = upcomingBookingsCount > 0 ? upcomingBookingsCount : cartCount;

  // Simplified Checkout Header
  if (isCheckout) {
    return (
      <header className="w-full bg-white border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div
            onClick={() => navigate('/')}
            className="flex items-center gap-2 cursor-pointer group"
          >
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white font-black text-lg shadow-xs group-hover:opacity-90 transition-opacity">
              V
            </div>
            <div className="flex items-center gap-1.5">
              <span className="font-black text-xl tracking-tight text-slate-900">V-OTA</span>
              <span className="text-[10px] font-bold px-1.5 py-0.2 rounded-md bg-blue-50 text-blue-700 border border-blue-200">
                Thanh toán an toàn
              </span>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/cart')}
              className="text-xs font-semibold text-blue-600 hover:text-blue-800 flex items-center gap-1 transition-colors"
            >
              ← Quay lại giỏ hàng
            </button>
          </div>
        </div>
      </header>
    );
  }

  const onHero = tone === 'overlay';
  const iconButtonClass = onHero
    ? 'text-white hover:bg-white/15 focus-visible:outline-white'
    : 'text-slate-700 hover:bg-slate-100 focus-visible:outline-blue-600';

  return (
    <>
      {overlayRoute && (
        <div ref={heroSentinelRef} aria-hidden="true" className="pointer-events-none absolute inset-x-0 top-0 h-[360px]" />
      )}
      <header
        className={overlayRoute
          ? 'fixed inset-x-0 top-0 z-40 px-3 pt-3 sm:px-6'
          : 'w-full bg-white border-b border-slate-200/80 shadow-xs'}
      >
        <div
          className={overlayRoute
            ? `mx-auto max-w-7xl rounded-[38px] px-4 transition-colors duration-200 sm:px-5 ${
              onHero ? 'glass-pill text-white' : 'bg-white/95 text-slate-900 shadow-lg ring-1 ring-slate-900/5 backdrop-blur'
            }`
            : 'max-w-7xl mx-auto px-3 sm:px-6 lg:px-8'}
        >
          <div className="flex items-center justify-between h-14 sm:h-16 py-2 gap-2 sm:gap-4 relative">

            {/* Brand Logo & Primary Category Navigator */}
            <div className="flex items-center gap-3 sm:gap-5 shrink-0 z-20">
              <Link
                href="/"
                aria-label="V-OTA, về trang chủ"
                className="flex items-center gap-2.5 group text-left cursor-pointer shrink-0 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-blue-600"
              >
                <div className="w-9 h-9 sm:w-10 sm:h-10 rounded-xl bg-gradient-to-tr from-amber-500 to-amber-300 flex items-center justify-center text-white font-extrabold text-xl sm:text-2xl shadow-md shadow-amber-500/20 group-hover:scale-105 transition-transform">
                  V
                </div>
                <div className="hidden sm:flex flex-col">
                  <span className={`text-base sm:text-lg font-black tracking-widest leading-none uppercase ${onHero ? 'text-white' : 'text-slate-900'}`}>V-OTA</span>
                  <span className={`text-[9px] tracking-wider uppercase font-bold ${onHero ? 'text-white/80' : 'text-slate-500'}`}>Resorts & Hotels</span>
                </div>
              </Link>

              {/* Nhóm dịch vụ: mỗi nhóm một menu con, ẩn dưới 1024 px (lối vào mobile là VerticalChips) */}
              <div ref={navRef} className="hidden lg:flex items-center">
                <NavGroups pathname={currentRoute} tone={tone} openId={openNavId} setOpenId={setOpenNavId} />
              </div>
            </div>

            {/* Right Action Utilities (AI Assistant, Language, Trips, Account) */}
            <div className="flex items-center gap-1.5 sm:gap-3 shrink-0 z-20 ml-auto">

              <Link
                href="/assistant"
                className={`hidden lg:inline-flex items-center gap-1.5 rounded-full border px-3.5 py-2 text-sm font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 ${
                  onHero
                    ? 'border-white/40 bg-white/15 text-white hover:bg-white/25 focus-visible:outline-white'
                    : 'border-indigo-200 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 focus-visible:outline-blue-600'
                }`}
              >
                <Sparkles className="w-4 h-4" aria-hidden="true" />
                Trợ lý AI
              </Link>

              {/* Language & Currency Selector */}
              <div className="relative" ref={langDropdownRef}>
                <button
                  onClick={() => setIsLangDropdownOpen(!isLangDropdownOpen)}
                  aria-expanded={isLangDropdownOpen}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs sm:text-sm font-semibold transition cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 ${iconButtonClass}`}
                  title="Thay đổi ngôn ngữ và tiền tệ"
                >
                  <span className="text-base">{currentLocaleInfo.flag}</span>
                  <span className="hidden sm:inline">{currentLocaleInfo.currencyCode}</span>
                  <svg className={`w-3.5 h-3.5 opacity-70 transition-transform ${isLangDropdownOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path></svg>
                </button>

                {isLangDropdownOpen && (
                  <div className="absolute right-0 mt-2 w-64 bg-white text-slate-800 rounded-2xl shadow-xl border border-slate-200/90 p-2.5 z-50">
                    <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider px-2 py-1">
                      Chọn ngôn ngữ & tiền tệ
                    </div>
                    <div className="max-h-60 overflow-y-auto space-y-0.5 mt-1">
                      {SUPPORTED_LOCALES.map((loc) => (
                        <button
                          key={loc.code}
                          onClick={() => {
                            setLocale(loc.code);
                            setIsLangDropdownOpen(false);
                            showToast(`Đã chuyển ngôn ngữ sang ${loc.nativeName}`);
                          }}
                          className={`w-full px-2.5 py-2 text-left rounded-lg text-xs flex items-center justify-between transition-colors cursor-pointer ${
                            currentLocale === loc.code
                              ? 'bg-blue-50 text-blue-800 font-bold'
                              : 'text-slate-700 hover:bg-slate-50'
                          }`}
                        >
                          <span className="flex items-center gap-2">
                            <span className="text-base">{loc.flag}</span>
                            <span>{loc.nativeName}</span>
                          </span>
                          <span className="text-[10px] font-mono text-slate-400 uppercase">
                            {loc.currencyCode}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Booking Management */}
              <div className="relative" ref={tripsDropdownRef}>
                <button
                  onClick={() => setIsTripsDropdownOpen(!isTripsDropdownOpen)}
                  aria-expanded={isTripsDropdownOpen}
                  className={`hidden md:flex items-center p-2 rounded-lg relative transition cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 ${iconButtonClass}`}
                  title="Đặt chỗ của tôi"
                  aria-label="Đặt chỗ của tôi"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path></svg>
                  {activeTripsBadge > 0 && (
                    <span className="absolute top-1 right-1 min-w-[16px] h-4 px-1 rounded-full bg-blue-600 text-white text-[9px] font-extrabold flex items-center justify-center shadow-xs">
                      {activeTripsBadge}
                    </span>
                  )}
                </button>

                {isTripsDropdownOpen && (
                  <div className="absolute right-0 mt-2 w-72 bg-white text-slate-800 rounded-2xl shadow-xl border border-slate-200/90 p-3 z-50">
                    <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                      <span className="text-xs font-bold text-slate-800">Đặt chỗ của tôi</span>
                      <button
                        onClick={() => {
                          setIsTripsDropdownOpen(false);
                          navigate('/cart');
                        }}
                        className="text-[11px] text-blue-600 hover:underline font-semibold cursor-pointer"
                      >
                        Giỏ hàng ({cartCount})
                      </button>
                    </div>

                    <div className="py-2.5 space-y-2">
                      {bookings.length > 0 ? (
                        bookings.slice(0, 3).map((b, idx) => (
                          <div
                            key={idx}
                            onClick={() => {
                              setIsTripsDropdownOpen(false);
                              navigate(`/booking/${b.referenceCode}`);
                            }}
                            className="p-2 rounded-lg bg-slate-50 hover:bg-blue-50/60 border border-slate-200/60 cursor-pointer transition-colors"
                          >
                            <div className="text-[11px] font-bold text-slate-900 flex items-center justify-between">
                              <span>Đơn #{b.referenceCode}</span>
                              <span className={`text-[10px] ${BOOKING_STATUS_BADGE[b.status].className}`}>
                                {BOOKING_STATUS_BADGE[b.status].label}
                              </span>
                            </div>
                            <div className="text-[10px] text-slate-500 mt-0.5">
                              {bookingItems(b).length} dịch vụ · {new Intl.NumberFormat('vi-VN').format(b.total)} ₫
                            </div>
                          </div>
                        ))
                      ) : (
                        <div className="text-center py-4 text-xs text-slate-400">
                          <Luggage className="w-6 h-6 mx-auto text-slate-300 mb-1" />
                          <p>Bạn chưa có chuyến đi nào sắp tới</p>
                        </div>
                      )}
                    </div>

                    <button
                      onClick={() => {
                        setIsTripsDropdownOpen(false);
                        navigate('/cart');
                      }}
                      className="w-full py-1.5 text-center text-xs font-bold text-blue-600 hover:bg-blue-50 rounded-lg transition-colors cursor-pointer"
                    >
                      Xem tất cả dịch vụ trong giỏ →
                    </button>
                  </div>
                )}
              </div>

              {/* Auth Buttons */}
              {currentPersona ? (
                <div className="relative" ref={accountDropdownRef}>
                  <button
                    onClick={() => setIsAccountDropdownOpen(!isAccountDropdownOpen)}
                    aria-expanded={isAccountDropdownOpen}
                    aria-label={`Tài khoản ${currentPersona.name}`}
                    className={`flex items-center gap-2 p-1.5 pl-2 pr-2.5 rounded-full transition-colors border cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 ${
                      onHero
                        ? 'border-white/40 bg-white/10 text-white hover:bg-white/20'
                        : isAccountDropdownOpen
                          ? 'bg-slate-100 border-slate-300'
                          : 'bg-white hover:bg-slate-50 border-slate-200'
                    }`}
                  >
                    <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-blue-700 via-blue-600 to-indigo-500 text-white font-bold text-xs flex items-center justify-center shadow-2xs">
                      {currentPersona.name.split(' ').pop()?.charAt(0) || 'M'}
                    </div>
                    <div className="text-left hidden xl:block leading-tight">
                      <div className={`text-xs font-bold truncate max-w-[110px] ${onHero ? 'text-white' : 'text-slate-900'}`}>
                        {currentPersona.name}
                      </div>
                      <div className={`text-[10px] font-semibold ${onHero ? 'text-white/80' : 'text-blue-600'}`}>
                        Thành viên
                      </div>
                    </div>
                    <ChevronDown className="w-3.5 h-3.5 opacity-70" />
                  </button>

                  {isAccountDropdownOpen && (
                    <div className="absolute right-0 mt-2 w-72 bg-white text-slate-800 rounded-2xl shadow-2xl border border-slate-200/90 p-3 z-50">
                      <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200/60 mb-2">
                        <div className="font-bold text-xs text-slate-900">{currentPersona.name}</div>
                        <div className="text-[11px] text-slate-500">{currentPersona.email}</div>
                      </div>

                      <div className="py-1 space-y-0.5 text-xs font-medium text-slate-700">
                        <button
                          onClick={() => {
                            setIsAccountDropdownOpen(false);
                            showToast('Chức năng Hồ sơ cá nhân');
                          }}
                          className="w-full px-2.5 py-2 text-left hover:bg-slate-50 rounded-lg flex items-center gap-2 transition-colors cursor-pointer"
                        >
                          <User className="w-3.5 h-3.5 text-slate-400" />
                          <span>Hồ sơ cá nhân</span>
                        </button>
                        <button
                          onClick={() => {
                            setIsAccountDropdownOpen(false);
                            navigate('/cart');
                          }}
                          className="w-full px-2.5 py-2 text-left hover:bg-slate-50 rounded-lg flex items-center gap-2 transition-colors cursor-pointer"
                        >
                          <Luggage className="w-3.5 h-3.5 text-slate-400" />
                          <span>Chuyến đi & Đặt phòng của tôi</span>
                        </button>
                        <button
                          onClick={() => {
                            setIsAccountDropdownOpen(false);
                            showToast('Cài đặt tài khoản');
                          }}
                          className="w-full px-2.5 py-2 text-left hover:bg-slate-50 rounded-lg flex items-center gap-2 transition-colors cursor-pointer"
                        >
                          <Settings className="w-3.5 h-3.5 text-slate-400" />
                          <span>Cài đặt</span>
                        </button>
                      </div>

                      <div className="pt-2 border-t border-slate-100 mt-1">
                        <button
                          onClick={() => {
                            setIsAccountDropdownOpen(false);
                            void signOut();
                          }}
                          className="w-full px-2.5 py-1.5 text-left text-xs font-semibold text-rose-600 hover:bg-rose-50 rounded-lg flex items-center gap-2 transition-colors cursor-pointer"
                        >
                          <LogOut className="w-3.5 h-3.5" />
                          <span>Đăng xuất</span>
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => openLoginModal()}
                    className={`px-2 sm:px-3.5 py-1.5 text-xs sm:text-sm font-semibold transition cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 ${
                      onHero ? 'text-white hover:text-white/80 focus-visible:outline-white' : 'text-slate-700 hover:text-blue-600 focus-visible:outline-blue-600'
                    }`}
                  >
                    Đăng nhập
                  </button>
                  <button
                    onClick={() => navigate('/register')}
                    className="px-3 sm:px-4 py-1.5 text-xs sm:text-sm font-bold text-white bg-blue-600 hover:bg-blue-700 active:scale-95 transition rounded-full shadow-sm cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
                  >
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
