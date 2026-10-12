import React from 'react';
import Link from 'next/link';
import { NAV_ITEMS } from '../layout/nav/navConfig';
import { useTravel } from '../../context/TravelContext';
import {
  Phone,
  Mail,
  MapPin,
  Smartphone,
  ArrowUpRight,
  ArrowUp
} from 'lucide-react';

export const Footer: React.FC = () => {
  const { navigate } = useTravel();

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <footer className="bg-[#00254d] text-white pt-16 pb-12 border-t border-brand-900/50 mt-12 transition-colors">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-10 pb-12 border-b border-brand-900/60">

          {/* Company Info Column */}
          <div className="lg:col-span-2 space-y-4">
            <div
              onClick={() => navigate('/')}
              className="flex items-center space-x-2.5 cursor-pointer group"
            >
              <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-amber-500 to-amber-300 flex items-center justify-center font-black text-slate-900 text-lg shadow-md group-hover:scale-105 transition-transform">
                S
              </div>
              <span className="text-xl font-extrabold tracking-widest uppercase">Sota</span>
            </div>
            <p className="text-xs text-brand-100/70 max-w-sm leading-relaxed">
              Hệ sinh thái khách sạn, nghỉ dưỡng, hội nghị và vui chơi giải trí hàng đầu Việt Nam.
            </p>

            <div className="space-y-3 pt-2 text-xs text-brand-100">
              <div className="flex items-center space-x-3">
                <div className="w-8 h-8 rounded-full bg-brand-900/80 flex items-center justify-center text-brand-300">
                  <Phone className="w-4 h-4" />
                </div>
                <div>
                  <div className="font-medium text-white">xxx xxx xxx xxx</div>
                  <div className="text-[11px] text-brand-300">Hỗ trợ 24/7 toàn quốc</div>
                </div>
              </div>

              <div className="flex items-center space-x-3">
                <div className="w-8 h-8 rounded-full bg-brand-900/80 flex items-center justify-center text-brand-300">
                  <Mail className="w-4 h-4" />
                </div>
                <span className="text-brand-100/90">xxxxxxxxx@gmail.com</span>
              </div>

              <div className="flex items-center space-x-3">
                <div className="w-8 h-8 rounded-full bg-brand-900/80 flex items-center justify-center text-brand-300 shrink-0">
                  <MapPin className="w-4 h-4" />
                </div>
                <span className="text-brand-100/90 leading-snug">Thành phố Hồ Chí Minh, Việt Nam</span>
              </div>
            </div>
          </div>

          {/* Links Column 1: Dịch vụ (route thật, cùng nguồn với header: navConfig) */}
          <div>
            <h4 className="font-sans text-xs font-bold uppercase tracking-wider text-brand-300 mb-4">DỊCH VỤ</h4>
            <ul className="space-y-2.5 text-xs text-brand-100/80">
              {NAV_ITEMS.map((item) => (
                <li key={item.id}>
                  <Link href={item.href} className="hover:text-white flex items-center justify-between group transition w-full text-left">
                    <span>{item.label}</span>
                    <ArrowUpRight className="w-3.5 h-3.5 opacity-60 group-hover:opacity-100 transition" aria-hidden="true" />
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Links Column 2: Điều khoản & Quy định */}
          <div>
            <h4 className="font-sans text-xs font-bold uppercase tracking-wider text-brand-300 mb-4">ĐIỀU KHOẢN & QUY ĐỊNH</h4>
            <ul className="space-y-2.5 text-xs text-brand-100/80">
              <li>
                <button onClick={() => navigate('/')} className="hover:text-white flex items-center justify-between group transition w-full text-left cursor-pointer">
                  <span>Điều khoản chung</span>
                  <ArrowUpRight className="w-3.5 h-3.5 opacity-60 group-hover:opacity-100 transition" />
                </button>
              </li>
              <li>
                <button onClick={() => navigate('/')} className="hover:text-white flex items-center justify-between group transition w-full text-left cursor-pointer">
                  <span>Quy định về thanh toán</span>
                  <ArrowUpRight className="w-3.5 h-3.5 opacity-60 group-hover:opacity-100 transition" />
                </button>
              </li>
              <li>
                <button onClick={() => navigate('/')} className="hover:text-white flex items-center justify-between group transition w-full text-left cursor-pointer">
                  <span>Chính sách giải quyết tranh chấp</span>
                  <ArrowUpRight className="w-3.5 h-3.5 opacity-60 group-hover:opacity-100 transition" />
                </button>
              </li>
              <li>
                <button onClick={() => navigate('/')} className="hover:text-white flex items-center justify-between group transition w-full text-left cursor-pointer">
                  <span>Chính sách Bảo vệ Dữ liệu cá nhân</span>
                  <ArrowUpRight className="w-3.5 h-3.5 opacity-60 group-hover:opacity-100 transition" />
                </button>
              </li>
            </ul>
          </div>

          {/* App Download */}
          <div>
            <h4 className="font-sans text-xs font-bold uppercase tracking-wider text-brand-300 mb-4">TẢI ỨNG DỤNG</h4>
            <p className="text-xs text-brand-100/70 mb-3">Tận hưởng ưu đãi độc quyền trên ứng dụng Sota Booking</p>
            <div className="flex flex-col space-y-2">
              <button
                onClick={() => { }}
                className="bg-brand-900/60 hover:bg-brand-800 text-white text-xs px-3.5 py-2.5 rounded-xl flex items-center space-x-2 border border-brand-700/50 transition cursor-pointer"
              >
                <Smartphone className="w-4 h-4 text-amber-400" />
                <span>App Store & Google Play</span>
              </button>
            </div>
          </div>

        </div>

        {/* Copyright Notice */}
        <div className="pt-8 flex flex-col sm:flex-row items-center justify-between text-[11px] text-brand-200/60">
          <div>© 2026 Sota Joint Stock Company. Tất cả các quyền được bảo lưu.</div>
          <div className="flex items-center space-x-4 mt-3 sm:mt-0">
            <button onClick={() => navigate('/')} className="hover:text-white transition cursor-pointer">Bảo mật</button>
            <button onClick={() => navigate('/')} className="hover:text-white transition cursor-pointer">Cookies</button>
            <button onClick={() => navigate('/')} className="hover:text-white transition cursor-pointer">Sơ đồ trang</button>
            <button
              onClick={scrollToTop}
              className="ml-2 flex items-center gap-1 text-brand-300 hover:text-white transition cursor-pointer"
              title="Lên đầu trang"
            >
              <ArrowUp className="w-3.5 h-3.5" />
              <span>Đầu trang</span>
            </button>
          </div>
        </div>
      </div>
    </footer>
  );
};
