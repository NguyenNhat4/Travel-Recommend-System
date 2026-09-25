import React from 'react';
import { useTravel } from '../../context/TravelContext';
import { Home, Search, Sparkles, ShoppingBag, User } from 'lucide-react';

export const MobileTabBar: React.FC = () => {
  const { currentRoute, navigate, cartCount, currentPersona, openLoginModal } = useTravel();

  // Hide in checkout
  if (currentRoute.startsWith('/checkout')) {
    return null;
  }

  const isHome = currentRoute === '/' || currentRoute === '';
  const isSearch = currentRoute.startsWith('/search');
  const isAssistant = currentRoute.startsWith('/assistant');
  const isCart = currentRoute.startsWith('/cart');
  const isLogin = currentRoute.startsWith('/login');

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-white/95 backdrop-blur-md border-t border-slate-200 safe-area-inset-bottom">
      <div className="grid grid-cols-5 h-14">
        <button
          onClick={() => navigate('/')}
          className={`flex flex-col items-center justify-center gap-0.5 ${isHome ? 'text-blue-600 font-bold' : 'text-slate-500'}`}
        >
          <Home className="w-5 h-5" />
          <span className="text-[10px]">Trang chủ</span>
        </button>

        <button
          onClick={() => navigate('/search')}
          className={`flex flex-col items-center justify-center gap-0.5 ${isSearch ? 'text-blue-600 font-bold' : 'text-slate-500'}`}
        >
          <Search className="w-5 h-5" />
          <span className="text-[10px]">Tìm kiếm</span>
        </button>

        <button
          onClick={() => navigate('/assistant')}
          className={`flex flex-col items-center justify-center gap-0.5 ${isAssistant ? 'font-bold text-indigo-600' : 'text-slate-500'}`}
        >
          <Sparkles className="w-5 h-5" />
          <span className="text-[10px]">Trợ lý</span>
        </button>

        <button
          onClick={() => navigate('/cart')}
          className={`relative flex flex-col items-center justify-center gap-0.5 ${isCart ? 'text-blue-600 font-bold' : 'text-slate-500'}`}
        >
          <div className="relative">
            <ShoppingBag className="w-5 h-5" />
            {cartCount > 0 && (
              <span className="absolute -top-1 -right-2 w-4 h-4 bg-blue-600 text-white rounded-full text-[9px] font-bold flex items-center justify-center">
                {cartCount}
              </span>
            )}
          </div>
          <span className="text-[10px]">Giỏ hàng</span>
        </button>

        <button
          onClick={() => {
            if (currentPersona) {
              navigate('/login');
            } else {
              openLoginModal();
            }
          }}
          className={`flex flex-col items-center justify-center gap-0.5 ${isLogin ? 'text-blue-600 font-bold' : 'text-slate-500'}`}
        >
          <User className="w-5 h-5" />
          <span className="text-[10px]">
            {currentPersona ? currentPersona.code : 'Tài khoản'}
          </span>
        </button>
      </div>
    </nav>
  );
};
