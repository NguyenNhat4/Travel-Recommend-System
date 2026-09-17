import React, { useState, useEffect, useRef } from 'react';
import { useTravel } from '../../context/TravelContext';
import { SUPPORTED_LOCALES } from '../../types/locale';
import { AIAssistantDrawer } from '../assistant/AIAssistantDrawer';
import { DemoAccountSwitcher } from './DemoAccountSwitcher';
import { 
  Sparkles, 
  Luggage, 
  User, 
  ChevronDown, 
  Award, 
  Settings, 
  LogOut, 
  Tag
} from 'lucide-react';

interface HeaderProps {
  isCheckout?: boolean;
}

export const Header: React.FC<HeaderProps> = ({ isCheckout = false }) => {
  const { 
    currentPersona, 
    switchPersona, 
    cart, 
    bookings, 
    navigate, 
    openLoginModal, 
    currentLocale, 
    setLocale,
    showToast
  } = useTravel();

  // Dropdowns state
  const [isAIDrawerOpen, setIsAIDrawerOpen] = useState(false);
  const [isLangDropdownOpen, setIsLangDropdownOpen] = useState(false);
  const [isTripsDropdownOpen, setIsTripsDropdownOpen] = useState(false);
  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);
  const [isAccountDropdownOpen, setIsAccountDropdownOpen] = useState(false);
  const [showDemoPersonasInAccount, setShowDemoPersonasInAccount] = useState(false);

  // Refs for click outside
  const langDropdownRef = useRef<HTMLDivElement>(null);
  const tripsDropdownRef = useRef<HTMLDivElement>(null);
  const notifDropdownRef = useRef<HTMLDivElement>(null);
  const accountDropdownRef = useRef<HTMLDivElement>(null);

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
      if (notifDropdownRef.current && !notifDropdownRef.current.contains(target)) {
        setIsNotificationsOpen(false);
      }
      if (accountDropdownRef.current && !accountDropdownRef.current.contains(target)) {
        setIsAccountDropdownOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const currentLocaleInfo = SUPPORTED_LOCALES.find(l => l.code === currentLocale) || SUPPORTED_LOCALES[0];

  const upcomingBookingsCount = bookings.length;
  const activeTripsBadge = upcomingBookingsCount > 0 ? upcomingBookingsCount : (cart.length > 0 ? cart.length : 0);

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

  return (
    <>
      <header className="w-full bg-white border-b border-slate-200/80 shadow-xs">
        <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14 sm:h-16 py-2 gap-2 sm:gap-4 relative">
            
            {/* Brand Logo & Primary Category Navigator */}
            <div className="flex items-center gap-3 sm:gap-5 shrink-0 z-20">
              <button 
                onClick={() => navigate('/')} 
                className="flex items-center gap-2.5 group text-left cursor-pointer shrink-0"
              >
                <div className="w-9 h-9 sm:w-10 sm:h-10 rounded-xl bg-gradient-to-tr from-amber-500 to-amber-300 flex items-center justify-center text-white font-extrabold text-xl sm:text-2xl shadow-md shadow-amber-500/20 group-hover:scale-105 transition-transform">
                  V
                </div>
                <div className="flex flex-col">
                  <span className="text-base sm:text-lg font-black tracking-widest leading-none uppercase text-slate-900">V-OTA</span>
                  <span className="text-[9px] tracking-wider text-slate-500 uppercase font-bold">Resorts & Hotels</span>
                </div>
              </button>

              {/* Main Service Navigator Tabs */}
              <nav 
                className="hidden lg:flex items-center gap-1 xl:gap-1.5 ml-2 border-l border-slate-200/80 pl-3 transition-all duration-200 text-xs font-semibold text-slate-700" 
                aria-label="Main Navigation"
              >
                <button 
                  type="button"
                  onClick={() => navigate('/search?type=flight')}
                  className="px-3.5 py-1.5 rounded-full hover:text-blue-700 hover:bg-slate-100 transition cursor-pointer"
                >
                  Di chuyển
                </button>
                <button 
                  type="button"
                  onClick={() => navigate('/search?type=hotel')}
                  className="px-4 py-1.5 rounded-full bg-slate-900 text-white font-bold shadow-xs transition cursor-pointer"
                >
                  Lưu trú
                </button>
                <button 
                  type="button"
                  onClick={() => navigate('/search?type=attraction')}
                  className="px-3.5 py-1.5 rounded-full hover:text-blue-700 hover:bg-slate-100 transition cursor-pointer"
                >
                  Tour và trải nghiệm
                </button>
                <button 
                  type="button"
                  onClick={() => navigate('/search?type=combo')}
                  className="px-3.5 py-1.5 rounded-full hover:text-blue-700 hover:bg-slate-100 transition cursor-pointer"
                >
                  Tiện ích khác
                </button>
              </nav>
            </div>

            {/* Right Action Utilities (AI Assistant, Language, Trips, Notifications, Account) */}
            <div className="flex items-center gap-1.5 sm:gap-3 shrink-0 z-20 ml-auto">
              {/* [AI ASSISTANT TRIGGER BUTTON] */}
              {/* <button 
                id="aiAssistantBtn" 
                onClick={() => setIsAIDrawerOpen(true)}
                className="flex items-center gap-1.5 sm:gap-2 px-2.5 sm:px-3.5 py-1.5 rounded-full bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 transition font-semibold text-xs sm:text-sm cursor-pointer active:scale-95 shrink-0"
                title="Trợ lý Du lịch AI"
              >
                <svg className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-indigo-600 animate-pulse" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 2l2.4 7.2h7.6l-6 4.8 2.4 7.2-6.4-4.8-6.4 4.8 2.4-7.2-6-4.8h7.6z"/>
                </svg>
                <span className="hidden xs:inline">Trợ lý AI</span>
              </button> */}

              {/* Language & Currency Selector */}
              <div className="relative" ref={langDropdownRef}>
                <button 
                  onClick={() => setIsLangDropdownOpen(!isLangDropdownOpen)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-slate-700 hover:bg-slate-100 text-xs sm:text-sm font-semibold transition cursor-pointer"
                  title="Thay đổi ngôn ngữ và tiền tệ"
                >
                  <span className="text-base">{currentLocaleInfo.flag}</span>
                  <span>{currentLocaleInfo.currencyCode}</span>
                  <svg className={`w-3.5 h-3.5 text-slate-400 transition-transform ${isLangDropdownOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path></svg>
                </button>

                {isLangDropdownOpen && (
                  <div className="absolute right-0 mt-2 w-64 bg-white rounded-2xl shadow-xl border border-slate-200/90 p-2.5 z-50 animate-in fade-in zoom-in-95 duration-150">
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
                  className="hidden md:flex items-center p-2 rounded-lg text-slate-700 hover:bg-slate-100 relative transition cursor-pointer" 
                  title="Đặt chỗ của tôi"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path></svg>
                  {activeTripsBadge > 0 && (
                    <span className="absolute top-1 right-1 min-w-[16px] h-4 px-1 rounded-full bg-blue-600 text-white text-[9px] font-extrabold flex items-center justify-center shadow-xs">
                      {activeTripsBadge}
                    </span>
                  )}
                </button>

                {isTripsDropdownOpen && (
                  <div className="absolute right-0 mt-2 w-72 bg-white rounded-2xl shadow-xl border border-slate-200/90 p-3 z-50 animate-in fade-in zoom-in-95 duration-150">
                    <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                      <span className="text-xs font-bold text-slate-800">Đặt chỗ của tôi</span>
                      <button 
                        onClick={() => {
                          setIsTripsDropdownOpen(false);
                          navigate('/cart');
                        }}
                        className="text-[11px] text-blue-600 hover:underline font-semibold cursor-pointer"
                      >
                        Giỏ hàng ({cart.length})
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
                              <span className="text-emerald-700 text-[10px]">Đã xác nhận</span>
                            </div>
                            <div className="text-[10px] text-slate-500 mt-0.5">
                              {b.items.length} dịch vụ · {new Intl.NumberFormat('vi-VN').format(b.totalAmount)} ₫
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

              {/* Notification */}
              <div className="relative" ref={notifDropdownRef}>
                <button 
                  onClick={() => setIsNotificationsOpen(!isNotificationsOpen)}
                  className="relative p-2 rounded-lg text-slate-700 hover:bg-slate-100 transition cursor-pointer" 
                  title="Thông báo"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"></path></svg>
                  <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-rose-500 rounded-full ring-2 ring-white"></span>
                </button>

                {isNotificationsOpen && (
                  <div className="absolute right-0 mt-2 w-80 bg-white rounded-2xl shadow-xl border border-slate-200/90 p-3 z-50 animate-in fade-in zoom-in-95 duration-150">
                    <div className="text-xs font-bold text-slate-800 pb-2 border-b border-slate-100">
                      Thông báo mới nhất
                    </div>
                    <div className="py-2 space-y-2 text-xs">
                      <div className="p-2 bg-blue-50/70 rounded-lg border border-blue-100">
                        <div className="font-bold text-blue-900 flex items-center gap-1">
                          <Sparkles className="w-3.5 h-3.5 text-blue-600" />
                          <span>Gợi ý độc quyền cho bạn</span>
                        </div>
                        <p className="text-[11px] text-slate-600 mt-0.5 leading-relaxed">
                          Khách sạn V-OTA Nha Trang giảm 15% cho thành viên V-OTA tuần này.
                        </p>
                      </div>
                      <div className="p-2 bg-slate-50 rounded-lg border border-slate-200/70">
                        <div className="font-semibold text-slate-800 flex items-center gap-1">
                          <Tag className="w-3.5 h-3.5 text-amber-600" />
                          <span>Vé VinWonders ưu đãi</span>
                        </div>
                        <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">
                          Đặt vé cáp treo & công viên giải trí nhận ngay voucher ăn uống 100k.
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Auth Buttons */}
              {currentPersona ? (
                <div className="relative" ref={accountDropdownRef}>
                  <button
                    onClick={() => setIsAccountDropdownOpen(!isAccountDropdownOpen)}
                    className={`flex items-center gap-2 p-1.5 pl-2 pr-2.5 rounded-full transition-colors border cursor-pointer ${
                      isAccountDropdownOpen 
                        ? 'bg-slate-100 border-slate-300' 
                        : 'bg-white hover:bg-slate-50 border-slate-200'
                    }`}
                  >
                    <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-blue-700 via-blue-600 to-indigo-500 text-white font-bold text-xs flex items-center justify-center shadow-2xs">
                      {currentPersona.name.split(' ').pop()?.charAt(0) || 'M'}
                    </div>
                    <div className="text-left hidden lg:block leading-tight">
                      <div className="text-xs font-bold text-slate-900 truncate max-w-[110px]">
                        {currentPersona.name}
                      </div>
                      <div className="text-[10px] text-blue-600 font-semibold">
                        Thành viên
                      </div>
                    </div>
                    <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
                  </button>

                  {isAccountDropdownOpen && (
                    <div className="absolute right-0 mt-2 w-72 bg-white rounded-2xl shadow-2xl border border-slate-200/90 p-3 z-50 animate-in fade-in zoom-in-95 duration-150">
                      <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200/60 mb-2">
                        <div className="font-bold text-xs text-slate-900">{currentPersona.name}</div>
                        <div className="text-[11px] text-slate-500">{currentPersona.email}</div>
                        <div className="mt-2 flex items-center justify-between text-[11px] pt-1.5 border-t border-slate-200/60">
                          <span className="text-slate-500">Điểm thưởng:</span>
                          <span className="font-bold text-blue-700 font-mono">1.250 V-Points</span>
                        </div>
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
                            showToast('Ưu đãi hội viên V-OTA Silver');
                          }}
                          className="w-full px-2.5 py-2 text-left hover:bg-slate-50 rounded-lg flex items-center gap-2 transition-colors cursor-pointer"
                        >
                          <Award className="w-3.5 h-3.5 text-amber-500" />
                          <span>Ưu đãi thành viên</span>
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

                      <div className="pt-2 border-t border-slate-100">
                        <button
                          type="button"
                          onClick={() => setShowDemoPersonasInAccount(!showDemoPersonasInAccount)}
                          className="w-full px-2 py-1.5 text-left text-[11px] font-semibold text-slate-500 hover:text-slate-800 flex items-center justify-between cursor-pointer"
                        >
                          <span>Thử nghiệm hồ sơ mẫu (Demo)</span>
                          <ChevronDown className={`w-3 h-3 transition-transform ${showDemoPersonasInAccount ? 'rotate-180' : ''}`} />
                        </button>

                        {showDemoPersonasInAccount && (
                          <div className="p-2 bg-slate-50 rounded-xl mt-1 border border-slate-200/60">
                            <DemoAccountSwitcher compact onSelect={() => setIsAccountDropdownOpen(false)} />
                          </div>
                        )}
                      </div>

                      <div className="pt-2 border-t border-slate-100 mt-1">
                        <button
                          onClick={() => {
                            switchPersona(null);
                            setIsAccountDropdownOpen(false);
                            showToast('Đã đăng xuất tài khoản');
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
                    className="px-3.5 py-1.5 text-xs sm:text-sm font-semibold text-slate-700 hover:text-blue-600 transition cursor-pointer"
                  >
                    Đăng nhập
                  </button>
                  <button 
                    onClick={() => openLoginModal()}
                    className="px-4 py-1.5 text-xs sm:text-sm font-bold text-white bg-blue-600 hover:bg-blue-700 active:scale-95 transition rounded-full shadow-sm cursor-pointer"
                  >
                    Đăng ký
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* ========================================================================= */}
      {/* 4. AI ASSISTANT DRAWER (AI TRAVEL ASSISTANT)                              */}
      {/* Ngăn kéo trượt bên phải phục vụ hội thoại & tư vấn du lịch thông minh AI  */}
      {/* ========================================================================= */}
      <AIAssistantDrawer 
        isOpen={isAIDrawerOpen}
        onClose={() => setIsAIDrawerOpen(false)}
      />
    </>
  );
};
