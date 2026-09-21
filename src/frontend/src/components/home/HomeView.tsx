'use client';

import React, { useState, useRef, useEffect } from 'react';
import { useTravel } from '../../context/TravelContext';
import { calculateRecommendations } from '../../services/recsys';
import { CATALOG } from '../../data/catalog';
import { ProductCard } from '../common/ProductCard';
import { DemoAccountSwitcher } from '../common/DemoAccountSwitcher';
import {
  Search,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Star,
  LayoutGrid,
  ShieldCheck,
  Bot,
  Sparkles,
  CheckCircle2,
  HelpCircle,
  ArrowRight
} from 'lucide-react';
import { WhyPopover } from '../common/WhyPopover';

interface HotelItem {
  id: string;
  name: string;
  tag: string;
  tagColor: string;
  image: string;
  address: string;
  stars: number;
  ratingScore: number;
  reviewsCount: number;
  originalPrice: string;
  price: string;
  catalogId?: string;
}

const SECTION_1_HOTELS: HotelItem[] = [
  {
    id: 'h1',
    name: 'V-OTA Resort & Spa Nha Trang Bay',
    tag: 'Biển Hòn Tre',
    tagColor: 'text-blue-700 bg-white/90',
    image: 'https://images.unsplash.com/photo-1566073771259-6a8506099945?q=80&w=800&auto=format&fit=crop',
    address: 'Hòn Tre, Vĩnh Nguyên, Tp. Nha Trang, Khánh Hòa',
    stars: 5,
    ratingScore: 4.8,
    reviewsCount: 4149,
    originalPrice: '3.530.000 ₫',
    price: '2.294.500 ₫',
    catalogId: 'nt-hotel-01'
  },
  {
    id: 'h2',
    name: 'VinHolidays Fiesta Phú Quốc',
    tag: 'Grand World',
    tagColor: 'text-emerald-700 bg-white/90',
    image: 'https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?q=80&w=800&auto=format&fit=crop',
    address: 'Gành Dầu, Cửa Cạn, Dương Đông, Phú Quốc',
    stars: 4,
    ratingScore: 4.8,
    reviewsCount: 773,
    originalPrice: '1.550.000 ₫',
    price: '1.007.500 ₫',
    catalogId: 'pq-hotel-01'
  },
  {
    id: 'h3',
    name: 'Hòn Tằm Resort',
    tag: 'Tắm Bùn Khoáng',
    tagColor: 'text-blue-700 bg-white/90',
    image: 'https://images.unsplash.com/photo-1571896349842-33c89424de2d?q=80&w=800&auto=format&fit=crop',
    address: 'Đảo Hòn Tằm, Phường Vĩnh Nguyên, Tp. Nha Trang',
    stars: 5,
    ratingScore: 4.7,
    reviewsCount: 1941,
    originalPrice: '2.970.000 ₫',
    price: '1.930.500 ₫',
    catalogId: 'nt-hotel-02'
  },
  {
    id: 'h4',
    name: 'V-OTA Beachfront Nha Trang',
    tag: 'Mặt Biển Trần Phú',
    tagColor: 'text-indigo-700 bg-white/90',
    image: 'https://images.unsplash.com/photo-1520250497591-112f2f40a3f4?q=80&w=800&auto=format&fit=crop',
    address: '78 - 80 Đường Trần Phú, Phường Lộc Thọ',
    stars: 5,
    ratingScore: 4.9,
    reviewsCount: 2180,
    originalPrice: '1.870.000 ₫',
    price: '1.215.500 ₫',
    catalogId: 'nt-hotel-01'
  },
  {
    id: 'h5',
    name: 'V-OTA Resort & Spa Phú Quốc',
    tag: 'Bãi Dài Hoàng Hôn',
    tagColor: 'text-rose-700 bg-white/90',
    image: 'https://images.unsplash.com/photo-1582719508461-905c673771fd?q=80&w=800&auto=format&fit=crop',
    address: 'Bãi Dài, Xã Gành Dầu, Tp. Phú Quốc, Kiên Giang',
    stars: 5,
    ratingScore: 4.8,
    reviewsCount: 2650,
    originalPrice: '3.200.000 ₫',
    price: '2.080.000 ₫',
    catalogId: 'pq-hotel-01'
  },
  {
    id: 'h6',
    name: 'V-OTA Resort & Spa Hạ Long',
    tag: 'Đảo Rều Độc Bản',
    tagColor: 'text-teal-700 bg-white/90',
    image: 'https://images.unsplash.com/photo-1578683010236-d716f9a3f461?q=80&w=800&auto=format&fit=crop',
    address: 'Đảo Rều, Phường Bãi Cháy, Tp. Hạ Long, Quảng Ninh',
    stars: 5,
    ratingScore: 4.9,
    reviewsCount: 3120,
    originalPrice: '3.650.000 ₫',
    price: '2.372.500 ₫',
    catalogId: 'nt-hotel-01'
  },
  {
    id: 'h7',
    name: 'V-OTA Luxury Nha Trang',
    tag: 'Biệt Thự Riêng Tư',
    tagColor: 'text-amber-700 bg-white/90',
    image: 'https://images.unsplash.com/photo-1618773928121-c32242e63f39?q=80&w=800&auto=format&fit=crop',
    address: 'Đảo Hòn Tre, Vĩnh Nguyên, Tp. Nha Trang',
    stars: 5,
    ratingScore: 5.0,
    reviewsCount: 1420,
    originalPrice: '5.800.000 ₫',
    price: '3.770.000 ₫',
    catalogId: 'nt-hotel-02'
  },
  {
    id: 'h8',
    name: 'V-OTA Resort & Golf Nam Hội An',
    tag: 'Di Sản & Nghỉ Dưỡng',
    tagColor: 'text-emerald-700 bg-white/90',
    image: 'https://images.unsplash.com/photo-1584132967334-10e028bd69f7?q=80&w=800&auto=format&fit=crop',
    address: 'Xã Bình Dương, Thăng Bình, Quảng Nam',
    stars: 5,
    ratingScore: 4.9,
    reviewsCount: 3825,
    originalPrice: '2.900.000 ₫',
    price: '1.885.000 ₫',
    catalogId: 'dn-hotel-01'
  }
];

const SECTION_2_HOTELS: HotelItem[] = [
  {
    id: 'p1',
    name: 'V-OTA Resort & Spa Nha Trang Bay',
    tag: 'Top Yêu Thích',
    tagColor: 'bg-amber-500 text-white',
    image: 'https://images.unsplash.com/photo-1540541338287-41700207dee6?q=80&w=800&auto=format&fit=crop',
    address: 'Hòn Tre, Vĩnh Nguyên, Tp. Nha Trang, Khánh Hòa',
    stars: 5,
    ratingScore: 4.8,
    reviewsCount: 4149,
    originalPrice: '3.530.000 ₫',
    price: '2.294.500 ₫',
    catalogId: 'nt-hotel-01'
  },
  {
    id: 'p2',
    name: 'V-OTA Resort & Golf Nam Hội An',
    tag: 'Golf 18 Lỗ',
    tagColor: 'text-emerald-700 bg-white/90',
    image: 'https://images.unsplash.com/photo-1584132967334-10e028bd69f7?q=80&w=800&auto=format&fit=crop',
    address: 'Xã Bình Dương, Xã Bình Minh, Huyện Thăng Bình',
    stars: 5,
    ratingScore: 4.9,
    reviewsCount: 3825,
    originalPrice: '2.710.000 ₫',
    price: '1.761.500 ₫',
    catalogId: 'dn-hotel-01'
  },
  {
    id: 'p3',
    name: 'VinHolidays Fiesta Phú Quốc',
    tag: 'Tiết Kiệm Nhất',
    tagColor: 'text-sky-700 bg-white/90',
    image: 'https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?q=80&w=800&auto=format&fit=crop',
    address: 'Gành Dầu, Cửa Cạn, Dương Đông, Phú Quốc',
    stars: 4,
    ratingScore: 4.8,
    reviewsCount: 773,
    originalPrice: '1.550.000 ₫',
    price: '1.007.500 ₫',
    catalogId: 'pq-hotel-01'
  },
  {
    id: 'p4',
    name: 'V-OTA Resort Nha Trang',
    tag: 'Đảo Thiên Đường',
    tagColor: 'text-blue-700 bg-white/90',
    image: 'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?q=80&w=800&auto=format&fit=crop',
    address: 'Đảo Hòn Tre, Tp. Nha Trang, Tỉnh Khánh Hòa',
    stars: 5,
    ratingScore: 4.6,
    reviewsCount: 3120,
    originalPrice: '3.120.000 ₫',
    price: '2.028.000 ₫',
    catalogId: 'nt-hotel-01'
  },
  {
    id: 'p5',
    name: 'V-OTA Discovery Cửa Hội',
    tag: 'Biển Cửa Lò',
    tagColor: 'text-cyan-700 bg-white/90',
    image: 'https://images.unsplash.com/photo-1563911302283-d2bc129e7570?q=80&w=800&auto=format&fit=crop',
    address: 'Đường Bình Minh, Phường Nghi Hải, Cửa Lò, Nghệ An',
    stars: 5,
    ratingScore: 4.7,
    reviewsCount: 1840,
    originalPrice: '2.100.000 ₫',
    price: '1.365.000 ₫',
    catalogId: 'nt-hotel-01'
  },
  {
    id: 'p6',
    name: 'V-OTA Condotel Empire Nha Trang',
    tag: 'Phố Biển Sôi Động',
    tagColor: 'text-violet-700 bg-white/90',
    image: 'https://images.unsplash.com/photo-1551882547-ff40c63fe5fa?q=80&w=800&auto=format&fit=crop',
    address: '44 - 46 Lê Thánh Tôn, Lộc Thọ, Nha Trang',
    stars: 5,
    ratingScore: 4.8,
    reviewsCount: 2290,
    originalPrice: '1.650.000 ₫',
    price: '1.072.500 ₫',
    catalogId: 'nt-hotel-01'
  },
  {
    id: 'p7',
    name: 'V-OTA Wonderworld Phú Quốc',
    tag: 'Công Viên Safari',
    tagColor: 'text-orange-700 bg-white/90',
    image: 'https://images.unsplash.com/photo-1590490360182-c33d57733427?q=80&w=800&auto=format&fit=crop',
    address: 'Khu Bãi Dài, Gành Dầu, Tp. Phú Quốc',
    stars: 5,
    ratingScore: 4.9,
    reviewsCount: 3410,
    originalPrice: '3.800.000 ₫',
    price: '2.470.000 ₫',
    catalogId: 'pq-hotel-01'
  },
  {
    id: 'p8',
    name: 'V-OTA Resort Cần Giờ',
    tag: 'Sinh Thái Rừng Ngập Mặn',
    tagColor: 'text-emerald-800 bg-white/90',
    image: 'https://images.unsplash.com/photo-1549294413-26f195200c16?q=80&w=800&auto=format&fit=crop',
    address: 'Đường Thạnh Thới, Long Hòa, Cần Giờ, TP. HCM',
    stars: 5,
    ratingScore: 4.6,
    reviewsCount: 1560,
    originalPrice: '2.300.000 ₫',
    price: '1.495.000 ₫',
    catalogId: 'nt-hotel-02'
  }
];

const DESTINATIONS = [
  {
    name: 'Nha Trang',
    desc: '36 Khách sạn & Resort',
    image: 'https://images.unsplash.com/photo-1544644181-1484b3fdfc62?q=80&w=800&auto=format&fit=crop'
  },
  {
    name: 'Phú Quốc',
    desc: '24 Khu nghỉ dưỡng biển',
    image: 'https://images.unsplash.com/photo-1506744038136-46273834b3fb?q=80&w=800&auto=format&fit=crop'
  },
  {
    name: 'Đà Nẵng & Hội An',
    desc: '42 Điểm lưu trú cao cấp',
    image: 'https://images.unsplash.com/photo-1559592413-7cec4d0cae2b?q=80&w=800&auto=format&fit=crop'
  },
  {
    name: 'TP. Hồ Chí Minh',
    desc: 'Khách sạn Landmark 81',
    image: 'https://images.unsplash.com/photo-1583417319070-4a69db38a482?q=80&w=800&auto=format&fit=crop'
  },
  {
    name: 'Hạ Long',
    desc: 'V-OTA Resort & Spa Hạ Long',
    image: 'https://images.unsplash.com/photo-1528127269322-539801943592?q=80&w=800&auto=format&fit=crop'
  },
  {
    name: 'Quy Nhơn',
    desc: 'Biển Kỳ Co & Eo Gió',
    image: 'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?q=80&w=800&auto=format&fit=crop'
  },
  {
    name: 'Đà Lạt',
    desc: 'Nghỉ dưỡng đồi thông',
    image: 'https://images.unsplash.com/photo-1519681393784-d120267933ba?q=80&w=800&auto=format&fit=crop'
  }
];

export const HomeView: React.FC = () => {
  const { currentPersona, activeEvents, navigate, showToast, addToCart } = useTravel();

  // Search state
  const [destinationInput, setDestinationInput] = useState('Nha Trang');
  const [checkinDate, setCheckinDate] = useState('18/09/2026');
  const [checkoutDate, setCheckoutDate] = useState('19/09/2026');

  // Guest Popover state
  const [isGuestOpen, setIsGuestOpen] = useState(false);
  const [rooms, setRooms] = useState(1);
  const [adults, setAdults] = useState(2);
  const guestDropdownRef = useRef<HTMLDivElement>(null);

  // Carousel refs
  const hotelTrack1Ref = useRef<HTMLDivElement>(null);
  const hotelTrack2Ref = useRef<HTMLDivElement>(null);
  const destinationTrackRef = useRef<HTMLDivElement>(null);

  // AI Search state & Dynamic typewriter placeholder
  const [aiSearchQuery, setAiSearchQuery] = useState('');
  const [aiPlaceholderIndex, setAiPlaceholderIndex] = useState(0);
  const [aiDisplayedPlaceholder, setAiDisplayedPlaceholder] = useState('');
  const [isDeletingPlaceholder, setIsDeletingPlaceholder] = useState(false);

  const AI_PLACEHOLDERS = [
    'Tìm resort V-OTA view biển cho gia đình 4 người, ngân sách 10 triệu...',
    'Combo Phú Quốc 3N2Đ vé máy bay + khách sạn + vui chơi VinWonders...',
    'Tư vấn khách sạn V-OTA Nha Trang gần bãi biển, có bể bơi vô cực...',
    'Gợi ý lịch trình 4N3Đ Đà Nẵng - Hội An nghỉ dưỡng cao cấp...'
  ];

  useEffect(() => {
    const currentText = AI_PLACEHOLDERS[aiPlaceholderIndex];
    let timeoutId: NodeJS.Timeout;

    if (!isDeletingPlaceholder) {
      if (aiDisplayedPlaceholder.length < currentText.length) {
        timeoutId = setTimeout(() => {
          setAiDisplayedPlaceholder(currentText.slice(0, aiDisplayedPlaceholder.length + 1));
        }, 35);
      } else {
        timeoutId = setTimeout(() => {
          setIsDeletingPlaceholder(true);
        }, 2800);
      }
    } else {
      if (aiDisplayedPlaceholder.length > 0) {
        timeoutId = setTimeout(() => {
          setAiDisplayedPlaceholder(currentText.slice(0, aiDisplayedPlaceholder.length - 1));
        }, 18);
      } else {
        setIsDeletingPlaceholder(false);
        setAiPlaceholderIndex((prev) => (prev + 1) % AI_PLACEHOLDERS.length);
      }
    }

    return () => clearTimeout(timeoutId);
  }, [aiDisplayedPlaceholder, isDeletingPlaceholder, aiPlaceholderIndex]);

  const handleAiSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const query = aiSearchQuery.trim() || aiDisplayedPlaceholder || 'Resort V-OTA';
    showToast(`Đang tìm kiếm: "${query.slice(0, 32)}..."`);
    navigate(`/search?q=${encodeURIComponent(query)}`);
  };

  // Recommendation logic from V-OTA system
  const recResponse = calculateRecommendations(currentPersona, activeEvents);
  const { strategy, destination = 'Nha Trang', recommendations, diagnostics } = recResponse;
  const [showSectionWhy, setShowSectionWhy] = useState(false);

  // Close guest popover on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (guestDropdownRef.current && !guestDropdownRef.current.contains(e.target as Node)) {
        setIsGuestOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const scrollTrack = (ref: React.RefObject<HTMLDivElement | null>, offset: number) => {
    if (ref.current) {
      ref.current.scrollBy({ left: offset, behavior: 'smooth' });
    }
  };

  const handleSearch = () => {
    const q = destinationInput.trim() || 'Nha Trang';
    showToast(`Đang tìm các khách sạn tại ${q} (${rooms} phòng, ${adults} khách)...`);
    navigate(`/search?q=${encodeURIComponent(q)}&type=hotel&rooms=${rooms}&guests=${adults}`);
  };

  const handleSelectDestination = (destName: string) => {
    setDestinationInput(destName);
    showToast(`Đã chọn điểm đến: ${destName}. Đang chuyển đến kết quả phù hợp...`);
    window.scrollTo({ top: 120, behavior: 'smooth' });
  };

  const handleBookHotel = (item: HotelItem) => {
    const matchedProduct = CATALOG.find(p => p.id === item.catalogId) || CATALOG[0];
    addToCart(matchedProduct, 1);
    showToast(`Đã thêm "${item.name}" vào chuyến đi của bạn!`);
  };

  return (
    <div className="bg-[#f8fafc] text-slate-800 antialiased font-sans flex flex-col min-h-screen">

      {/* ========================================================================= */}
      {/* HERO SECTION WITH CINEMATIC RESORT BACKGROUND                            */}
      {/* ========================================================================= */}
      <section className="relative min-h-[580px] lg:min-h-[640px] flex items-center justify-center pt-28 pb-16 px-4 sm:px-6">
        {/* Background Image with Dark Vignette Gradient */}
        <div className="absolute inset-0 z-0 overflow-hidden">
          <img
            src="https://images.unsplash.com/photo-1582719508461-905c673771fd?q=80&w=2000&auto=format&fit=crop"
            alt="V-OTA Resort & Luxury Hotel Pool View"
            className="w-full h-full object-cover object-center filter brightness-[0.78] transform scale-105"
            loading="eager"
          />
          <div className="absolute inset-0 bg-gradient-to-b from-slate-900/60 via-slate-900/30 to-slate-950/80"></div>
        </div>

        <div className="relative z-10 max-w-5xl w-full mx-auto text-center mt-6">
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-white tracking-tight drop-shadow-md">
            Khách sạn
          </h1>
          <p className="mt-3 text-slate-100 text-base sm:text-lg font-light max-w-xl mx-auto drop-shadow">
            Lưu lại các điểm đến trong mơ cho chuyến đi tiếp theo
          </p>

          {/* DUAL SEARCH CONTAINER: AI SEARCH (PRIMARY)*/}
          <div className="mt-8 max-w-4xl mx-auto w-full space-y-3">

            {/* 1. PRIMARY AI SEARCH BAR */}
            <form
              onSubmit={handleAiSubmit}
              className="bg-white/95 backdrop-blur-xl rounded-2xl sm:rounded-full p-2 sm:p-2.5 shadow-2xl border border-white/60 text-slate-700 flex items-center justify-between gap-2 transition hover:shadow-3xl ring-2 ring-blue-500/20"
            >
              <div className="flex items-center gap-3 pl-3.5 sm:pl-4 flex-1 min-w-0">
                {/* <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white shrink-0 shadow-md shadow-blue-500/25">
                  <Sparkles className="w-4 h-4 text-amber-300 animate-pulse" />
                </div> */}
                <input
                  type="text"
                  value={aiSearchQuery}
                  onChange={(e) => setAiSearchQuery(e.target.value)}
                  placeholder={aiDisplayedPlaceholder || "Hỏi AI: Tìm resort V-OTA view biển cho gia đình 4 người, ngân sách 10 triệu..."}
                  className="w-full text-slate-800 font-semibold text-xs sm:text-sm md:text-base focus:outline-none bg-transparent placeholder:text-slate-400 truncate"
                />
              </div>

              <div className="flex items-center gap-1.5 shrink-0 pr-1">
                <button
                  type="submit"
                  aria-label="Tìm kiếm"
                  className="w-9 h-9 sm:w-10 sm:h-10 bg-blue-600 hover:bg-blue-700 text-white rounded-full shadow-md hover:shadow-blue-500/25 flex items-center justify-center transition duration-200 transform active:scale-95 cursor-pointer"
                >
                  <Search className="w-4 h-4 sm:w-5 sm:h-5" />
                </button>
              </div>
            </form>

            {/* Quick AI Suggestion Chips */}
            <div className="flex items-center justify-center gap-1.5 sm:gap-2 flex-wrap text-[11px] sm:text-xs">
              <span className="text-white/80 font-medium flex items-center gap-1 drop-shadow">
                💡 Gợi ý câu hỏi:
              </span>
              {[
                'Resort V-OTA Nha Trang cho gia đình',
                'Combo Phú Quốc 3N2Đ giá tốt',
                'Villa ven biển view hoàng hôn'
              ].map((chip) => (
                <button
                  key={chip}
                  type="button"
                  onClick={() => {
                    setAiSearchQuery(chip);
                    showToast(`Đang tìm kiếm: "${chip}"`);
                    navigate(`/search?q=${encodeURIComponent(chip)}`);
                  }}
                  className="px-2.5 py-1 rounded-full bg-white/20 hover:bg-white/35 backdrop-blur-md text-white border border-white/25 transition cursor-pointer font-medium shadow-xs"
                >
                  {chip}
                </button>
              ))}
            </div>

          </div>

        </div>
      </section>

      {/* Main Content Sections */}
      <main className="flex-grow">
        {/* Top spacing before search bar (ensures top gap > bottom gap in normal flow) */}
        <div className="h-8 sm:h-10" aria-hidden="true" />

        {/* COMPACT HOTEL SEARCH BAR - STICKY */}
        <section className="sticky top-1 sm:top-1.5 z-40 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-0 pb-1.5 sm:pb-2">

          <div className="bg-white/95 backdrop-blur-md rounded-3xl px-3 py-1.5 sm:py-1 shadow-lg border border-white/50 text-slate-700 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-1.5 sm:gap-2 transition hover:bg-white">

            {/* Field 1: Destination (Compact) */}
            <div className="flex-1 text-left px-3 py-1 hover:bg-slate-50/80 rounded-xl sm:rounded-full transition cursor-pointer relative group">
              <label className="block text-[9px] font-extrabold text-slate-400 uppercase tracking-wider">
                Điểm đến
              </label>
              <div className="flex items-center mt-0.5">
                <input
                  type="text"
                  value={destinationInput}
                  onChange={(e) => setDestinationInput(e.target.value)}
                  placeholder="Điểm đến khách sạn..."
                  className="w-full text-slate-800 font-bold text-xs sm:text-sm focus:outline-none bg-transparent placeholder:text-slate-400"
                />
              </div>
            </div>

            <div className="hidden md:block w-px h-6 bg-slate-200"></div>

            {/* Field 2: Dates (Check-in & Check-out Compact) */}
            <div className="flex-1 text-left px-3 py-1 hover:bg-slate-50/80 rounded-xl sm:rounded-full transition cursor-pointer flex items-center justify-between gap-2">
              <div className="w-1/2">
                <label className="block text-[9px] font-extrabold text-slate-400 uppercase tracking-wider">Ngày đi</label>
                <input
                  type="text"
                  value={checkinDate}
                  onChange={(e) => setCheckinDate(e.target.value)}
                  className="w-full font-bold text-xs sm:text-sm text-slate-800 bg-transparent focus:outline-none cursor-pointer"
                />
              </div>
              <div className="w-px h-5 bg-slate-200"></div>
              <div className="w-1/2">
                <label className="block text-[9px] font-extrabold text-slate-400 uppercase tracking-wider">Ngày về</label>
                <input
                  type="text"
                  value={checkoutDate}
                  onChange={(e) => setCheckoutDate(e.target.value)}
                  className="w-full font-bold text-xs sm:text-sm text-slate-800 bg-transparent focus:outline-none cursor-pointer"
                />
              </div>
            </div>

            <div className="hidden md:block w-px h-6 bg-slate-200"></div>

            {/* Field 3: Rooms & Guests (Compact) */}
            <div
              ref={guestDropdownRef}
              className="flex-1 text-left px-3 py-1 hover:bg-slate-50/80 rounded-xl sm:rounded-full transition cursor-pointer relative"
              onClick={() => setIsGuestOpen(!isGuestOpen)}
            >
              <label className="block text-[9px] font-extrabold text-slate-400 uppercase tracking-wider">Số lượng</label>
              <div className="flex items-center justify-between">
                <span className="font-bold text-xs sm:text-sm text-slate-800 truncate">
                  {rooms} phòng, {adults} người lớn
                </span>
                <ChevronDown className="w-3.5 h-3.5 text-slate-400 shrink-0 ml-1" />
              </div>

              {/* Guest Popover */}
              {isGuestOpen && (
                <div
                  onClick={(e) => e.stopPropagation()}
                  className="absolute top-full mt-3 right-0 md:left-0 w-72 bg-white rounded-2xl shadow-2xl border border-slate-100 p-4 z-50 text-slate-800 animate-in fade-in zoom-in-95 duration-150"
                >
                  <div className="flex items-center justify-between py-2 border-b border-slate-100">
                    <div>
                      <div className="font-semibold text-sm">Phòng</div>
                      <div className="text-xs text-slate-400">Số lượng phòng</div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <button
                        type="button"
                        className="w-7 h-7 rounded-full border border-slate-200 flex items-center justify-center font-bold hover:bg-slate-100 text-slate-600 transition cursor-pointer"
                        onClick={() => setRooms(Math.max(1, rooms - 1))}
                      >
                        -
                      </button>
                      <span className="w-5 text-center font-semibold text-sm">{rooms}</span>
                      <button
                        type="button"
                        className="w-7 h-7 rounded-full border border-slate-200 flex items-center justify-center font-bold hover:bg-slate-100 text-slate-600 transition cursor-pointer"
                        onClick={() => setRooms(Math.min(8, rooms + 1))}
                      >
                        +
                      </button>
                    </div>
                  </div>

                  <div className="flex items-center justify-between py-2.5">
                    <div>
                      <div className="font-semibold text-sm">Người lớn</div>
                      <div className="text-xs text-slate-400">Từ 12 tuổi trở lên</div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <button
                        type="button"
                        className="w-7 h-7 rounded-full border border-slate-200 flex items-center justify-center font-bold hover:bg-slate-100 text-slate-600 transition cursor-pointer"
                        onClick={() => setAdults(Math.max(1, adults - 1))}
                      >
                        -
                      </button>
                      <span className="w-5 text-center font-semibold text-sm">{adults}</span>
                      <button
                        type="button"
                        className="w-7 h-7 rounded-full border border-slate-200 flex items-center justify-center font-bold hover:bg-slate-100 text-slate-600 transition cursor-pointer"
                        onClick={() => setAdults(Math.min(16, adults + 1))}
                      >
                        +
                      </button>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => setIsGuestOpen(false)}
                    className="w-full mt-2 py-2 bg-blue-600 hover:bg-blue-700 active:scale-98 text-white font-medium text-xs rounded-xl shadow transition cursor-pointer"
                  >
                    Áp dụng
                  </button>
                </div>
              )}
            </div>

            {/* Search Action Button (Compact) */}
            <button
              onClick={handleSearch}
              className="w-full md:w-auto px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs rounded-xl sm:rounded-full shadow-md hover:shadow-slate-900/30 flex items-center justify-center space-x-1.5 transition duration-200 transform active:scale-95 cursor-pointer shrink-0"
            >
              <Search className="w-3.5 h-3.5" />
              <span>Tìm khách sạn</span>
            </button>
          </div>

        </section>

        {/* ========================================================================= */}
        {/* OPTIONAL PERSONALIZATION PANEL (K1 / K2 V-OTA DEMO ACCORDION)              */}
        {/* ========================================================================= */}
        {currentPersona && recommendations.length > 0 && (
          <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-3 pb-10">
            <div className="p-6 rounded-3xl bg-white border border-slate-200/80 shadow-sm">
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between pb-4 border-b border-slate-100 gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
                      Gợi ý
                    </h2>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => showToast('Tính năng đang được cập nhật!')}
                    className="inline-flex items-center gap-1 text-xs sm:text-sm font-semibold text-blue-600 hover:text-blue-700 transition cursor-pointer"
                  >
                    <span>Xem thêm</span>
                    <ArrowRight className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                  </button>
                  <button
                    onClick={() => setShowSectionWhy(true)}
                    className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold text-blue-700 bg-blue-50 hover:bg-blue-100 rounded-xl border border-blue-200 transition-colors cursor-pointer"
                  >
                    <HelpCircle className="w-3.5 h-3.5" />
                    <span>Vì sao có gợi ý này?</span>
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-5">
                {recommendations.slice(0, 4).map((rec) => (
                  <ProductCard
                    key={rec.product.id}
                    product={rec.product}
                    variant="grid"
                    because={rec.because}
                    strategy={strategy}
                    excludedVerticals={diagnostics.excludedVerticals}
                    score={rec.score}
                    rank={rec.rank}
                  />
                ))}
              </div>

              <WhyPopover
                isOpen={showSectionWhy}
                onClose={() => setShowSectionWhy(false)}
                targetProductName={`Toàn bộ danh mục chuyến ${destination}`}
                becauseItems={recommendations[0]?.because || []}
                strategy={strategy}
                excludedVerticals={diagnostics.excludedVerticals}
                destination={destination}
              />
            </div>
          </section>
        )}

        {/* ========================================================================= */}
        {/* SECTION 1: KHÁCH SẠN VÀ RESORT (CAROUSEL 1)                               */}
        {/* ========================================================================= */}
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-4 pb-12">
          {/* Section Header with Arrows & Xem thêm */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
                Khách sạn và resort
              </h2>
            </div>
            <div className="flex items-center space-x-3">
              <button
                type="button"
                onClick={() => showToast('Tính năng đang được cập nhật!')}
                className="inline-flex items-center gap-1 text-xs sm:text-sm font-semibold text-blue-600 hover:text-blue-700 transition cursor-pointer"
              >
                <span>Xem thêm</span>
                <ArrowRight className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
              </button>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => scrollTrack(hotelTrack1Ref, -340)}
                  className="w-10 h-10 rounded-full border border-slate-200 hover:bg-slate-100 flex items-center justify-center text-slate-600 transition shadow-sm active:scale-95 cursor-pointer"
                  aria-label="Cuộn sang trái"
                >
                  <ChevronLeft className="w-5 h-5" />
                </button>
                <button
                  onClick={() => scrollTrack(hotelTrack1Ref, 340)}
                  className="w-10 h-10 rounded-full border border-slate-200 hover:bg-slate-100 flex items-center justify-center text-slate-600 transition shadow-sm active:scale-95 cursor-pointer"
                  aria-label="Cuộn sang phải"
                >
                  <ChevronRight className="w-5 h-5" />
                </button>
              </div>
            </div>
          </div>

          {/* Hotel Cards Carousel */}
          <div
            ref={hotelTrack1Ref}
            className="flex space-x-6 overflow-x-auto no-scrollbar scroll-smooth pb-4 -mx-4 px-4 sm:mx-0 sm:px-0"
          >
            {SECTION_1_HOTELS.map((hotel) => (
              <div
                key={hotel.id}
                className="w-[280px] sm:w-[305px] lg:w-[calc((100%-72px)/4)] flex-shrink-0 bg-white rounded-2xl overflow-hidden border border-slate-100 shadow-sm hover:shadow-xl transition-all duration-300 flex flex-col group"
              >
                <div className="relative h-48 overflow-hidden">
                  <img
                    src={hotel.image}
                    alt={hotel.name}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                  />
                  <span className={`absolute top-3 left-3 backdrop-blur-md px-2.5 py-1 rounded-full text-[11px] font-bold shadow-sm ${hotel.tagColor}`}>
                    {hotel.tag}
                  </span>
                </div>
                <div className="p-4 flex flex-col flex-grow justify-between">
                  <div>
                    <h3 className="font-bold text-slate-900 text-base leading-snug group-hover:text-blue-600 transition-colors line-clamp-1">
                      {hotel.name}
                    </h3>

                    {/* Stars */}
                    <div className="flex items-center text-amber-400 text-xs mt-1">
                      {Array.from({ length: hotel.stars }).map((_, i) => (
                        <Star key={i} className="w-3.5 h-3.5 fill-current" />
                      ))}
                    </div>
                    <p className="text-xs text-slate-500 mt-1 truncate">{hotel.address}</p>

                    {/* TripAdvisor Review Rating */}
                    <div className="flex items-center space-x-2 mt-2.5 text-xs text-slate-600">
                      <div className="tripadvisor-dots">
                        <div className="tripadvisor-dot"></div>
                        <div className="tripadvisor-dot"></div>
                        <div className="tripadvisor-dot"></div>
                        <div className="tripadvisor-dot"></div>
                        <div className="tripadvisor-dot tripadvisor-dot-half"></div>
                      </div>
                      <span className="font-bold text-slate-800">{hotel.ratingScore}</span>
                      <span className="text-slate-400">· {hotel.reviewsCount.toLocaleString('vi-VN')} đánh giá</span>
                    </div>
                  </div>

                  {/* Pricing & CTA */}
                  <div className="mt-4 pt-3 border-t border-slate-100 flex items-baseline justify-between">
                    <div>
                      <span className="text-xs text-slate-400 line-through">{hotel.originalPrice}</span>
                      <div className="text-lg font-extrabold text-slate-900 tracking-tight">{hotel.price}</div>
                    </div>
                    <button
                      onClick={() => handleBookHotel(hotel)}
                      className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-blue-50 text-blue-600 hover:bg-blue-600 hover:text-white transition cursor-pointer"
                    >
                      Đặt ngay
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ========================================================================= */}
        {/* SECTION 2: KHÁCH SẠN ĐƯỢC LỰA CHỌN (CAROUSEL 2)                           */}
        {/* ========================================================================= */}
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
                Khách sạn được lựa chọn
              </h2>
            </div>
            <div className="flex items-center space-x-3">
              <button
                type="button"
                onClick={() => showToast('Tính năng đang được cập nhật!')}
                className="inline-flex items-center gap-1 text-xs sm:text-sm font-semibold text-blue-600 hover:text-blue-700 transition cursor-pointer"
              >
                <span>Xem thêm</span>
                <ArrowRight className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
              </button>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => scrollTrack(hotelTrack2Ref, -340)}
                  className="w-10 h-10 rounded-full border border-slate-200 hover:bg-slate-100 flex items-center justify-center text-slate-600 transition shadow-sm active:scale-95 cursor-pointer"
                  aria-label="Cuộn sang trái"
                >
                  <ChevronLeft className="w-5 h-5" />
                </button>
                <button
                  onClick={() => scrollTrack(hotelTrack2Ref, 340)}
                  className="w-10 h-10 rounded-full border border-slate-200 hover:bg-slate-100 flex items-center justify-center text-slate-600 transition shadow-sm active:scale-95 cursor-pointer"
                  aria-label="Cuộn sang phải"
                >
                  <ChevronRight className="w-5 h-5" />
                </button>
              </div>
            </div>
          </div>

          <div
            ref={hotelTrack2Ref}
            className="flex space-x-6 overflow-x-auto no-scrollbar scroll-smooth pb-4 -mx-4 px-4 sm:mx-0 sm:px-0"
          >
            {SECTION_2_HOTELS.map((hotel) => (
              <div
                key={hotel.id}
                className="w-[280px] sm:w-[305px] lg:w-[calc((100%-72px)/4)] flex-shrink-0 bg-white rounded-2xl overflow-hidden border border-slate-100 shadow-sm hover:shadow-xl transition-all duration-300 flex flex-col group"
              >
                <div className="relative h-48 overflow-hidden">
                  <img
                    src={hotel.image}
                    alt={hotel.name}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                  />
                  <span className={`absolute top-3 left-3 px-2.5 py-0.5 rounded-full text-[11px] font-bold shadow-sm ${hotel.tagColor}`}>
                    {hotel.tag}
                  </span>
                </div>
                <div className="p-4 flex flex-col flex-grow justify-between">
                  <div>
                    <h3 className="font-bold text-slate-900 text-base leading-snug group-hover:text-blue-600 transition-colors line-clamp-1">
                      {hotel.name}
                    </h3>
                    <div className="flex items-center text-amber-400 text-xs mt-1">
                      {Array.from({ length: hotel.stars }).map((_, i) => (
                        <Star key={i} className="w-3.5 h-3.5 fill-current" />
                      ))}
                    </div>
                    <p className="text-xs text-slate-500 mt-1 truncate">{hotel.address}</p>

                    <div className="flex items-center space-x-2 mt-2.5 text-xs text-slate-600">
                      <div className="tripadvisor-dots">
                        <div className="tripadvisor-dot"></div>
                        <div className="tripadvisor-dot"></div>
                        <div className="tripadvisor-dot"></div>
                        <div className="tripadvisor-dot"></div>
                        <div className="tripadvisor-dot tripadvisor-dot-half"></div>
                      </div>
                      <span className="font-bold text-slate-800">{hotel.ratingScore}</span>
                      <span className="text-slate-400">· {hotel.reviewsCount.toLocaleString('vi-VN')} đánh giá</span>
                    </div>
                  </div>

                  <div className="mt-4 pt-3 border-t border-slate-100 flex items-baseline justify-between">
                    <div>
                      <span className="text-xs text-slate-400 line-through">{hotel.originalPrice}</span>
                      <div className="text-lg font-extrabold text-slate-900 tracking-tight">{hotel.price}</div>
                    </div>
                    <button
                      onClick={() => handleBookHotel(hotel)}
                      className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-blue-50 text-blue-600 hover:bg-blue-600 hover:text-white transition cursor-pointer"
                    >
                      Đặt ngay
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ========================================================================= */}
        {/* SECTION 3: BẠN MUỐN ĐI ĐÂU? (DESTINATION CAROUSEL)                        */}
        {/* ========================================================================= */}
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
                Bạn muốn đi đâu?
              </h2>
            </div>
            <div className="flex items-center space-x-3">
              <button
                type="button"
                onClick={() => showToast('Tính năng đang được cập nhật!')}
                className="inline-flex items-center gap-1 text-xs sm:text-sm font-semibold text-blue-600 hover:text-blue-700 transition cursor-pointer"
              >
                <span>Xem thêm</span>
                <ArrowRight className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
              </button>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => scrollTrack(destinationTrackRef, -260)}
                  className="w-10 h-10 rounded-full border border-slate-200 hover:bg-slate-100 flex items-center justify-center text-slate-600 transition shadow-sm active:scale-95 cursor-pointer"
                  aria-label="Cuộn sang trái"
                >
                  <ChevronLeft className="w-5 h-5" />
                </button>
                <button
                  onClick={() => scrollTrack(destinationTrackRef, 260)}
                  className="w-10 h-10 rounded-full border border-slate-200 hover:bg-slate-100 flex items-center justify-center text-slate-600 transition shadow-sm active:scale-95 cursor-pointer"
                  aria-label="Cuộn sang phải"
                >
                  <ChevronRight className="w-5 h-5" />
                </button>
              </div>
            </div>
          </div>

          <div
            ref={destinationTrackRef}
            className="flex space-x-5 overflow-x-auto no-scrollbar scroll-smooth pb-3 -mx-4 px-4 sm:mx-0 sm:px-0"
          >
            {DESTINATIONS.map((dest) => (
              <div
                key={dest.name}
                onClick={() => handleSelectDestination(dest.name)}
                className="w-56 sm:w-60 h-80 rounded-2xl overflow-hidden relative flex-shrink-0 cursor-pointer group shadow-md hover:shadow-2xl transition-all duration-300"
              >
                <img
                  src={dest.image}
                  alt={dest.name}
                  className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-700"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/20 to-transparent"></div>
                <div className="absolute bottom-5 inset-x-0 text-center px-3">
                  <h3 className="text-white text-xl font-bold tracking-tight drop-shadow-md">{dest.name}</h3>
                  <p className="text-xs text-slate-200 mt-0.5 opacity-0 group-hover:opacity-100 transition duration-300 font-medium">
                    {dest.desc}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ========================================================================= */}
        {/* SECTION 4: NGƯỜI BẠN ĐỒNG HÀNH ĐÁNG TIN CẬY (TRUST GLASS CARDS)           */}
        {/* ========================================================================= */}
        <section className="relative py-20 overflow-hidden mt-6">
          {/* Panoramic Background with Light Gradient Overlay */}
          <div className="absolute inset-0 z-0">
            <img
              src="https://images.unsplash.com/photo-1506929562872-bb421503ef21?q=80&w=2000&auto=format&fit=crop"
              alt="Coastal paradise panoramic"
              className="w-full h-full object-cover filter brightness-[0.85]"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-white/90 via-transparent to-white/70"></div>
          </div>

          <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight mb-8">
              Người bạn đồng hành đáng tin cậy
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Trust Badge 1 */}
              <div className="glass-card rounded-2xl p-6 border border-white/70 shadow-lg hover:shadow-2xl transition duration-300 flex flex-col items-start">
                <div className="w-12 h-12 rounded-xl bg-blue-600 text-white flex items-center justify-center mb-4 shadow-md shadow-blue-500/30">
                  <LayoutGrid className="w-6 h-6" />
                </div>
                <h3 className="text-base font-bold text-slate-900 leading-snug">
                  Hệ sinh thái du lịch & giải trí toàn diện
                </h3>
                <p className="text-xs sm:text-sm text-slate-600 mt-2 leading-relaxed">
                  Mang đến trải nghiệm du lịch và giải trí đẳng cấp với hệ sinh thái dịch vụ chất lượng cao.
                </p>
              </div>

              {/* Trust Badge 2 */}
              <div className="glass-card rounded-2xl p-6 border border-white/70 shadow-lg hover:shadow-2xl transition duration-300 flex flex-col items-start">
                <div className="w-12 h-12 rounded-xl bg-blue-600 text-white flex items-center justify-center mb-4 shadow-md shadow-blue-500/30">
                  <ShieldCheck className="w-6 h-6" />
                </div>
                <h3 className="text-base font-bold text-slate-900 leading-snug">
                  Trải nghiệm đặt dịch vụ liền mạch
                </h3>
                <p className="text-xs sm:text-sm text-slate-600 mt-2 leading-relaxed">
                  Tìm kiếm, đặt dịch vụ, thanh toán và quản lý hành trình trên một nền tảng duy nhất.
                </p>
              </div>

              {/* Trust Badge 3 */}
              <div className="glass-card rounded-2xl p-6 border border-white/70 shadow-lg hover:shadow-2xl transition duration-300 flex flex-col items-start">
                <div className="w-12 h-12 rounded-xl bg-blue-600 text-white flex items-center justify-center mb-4 shadow-md shadow-blue-500/30">
                  <Bot className="w-6 h-6" />
                </div>
                <h3 className="text-base font-bold text-slate-900 leading-snug">
                  Trợ lý AI đồng hành du lịch
                </h3>
                <p className="text-xs sm:text-sm text-slate-600 mt-2 leading-relaxed">
                  AI tư vấn, cá nhân hóa và hỗ trợ xuyên suốt hành trình trải nghiệm của khách hàng.
                </p>
              </div>
            </div>
          </div>
        </section>


      </main>
    </div>
  );
};
