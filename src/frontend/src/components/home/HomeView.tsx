'use client';

import React, { useState, useRef, useEffect } from 'react';
import { useTravel } from '../../context/TravelContext';
import { fetchRecommendations } from '../../services/recsys';
import type { RecommendationResponse } from '../../types/travel';
import { CATALOG } from '../../data/catalog';
import { ProductCard } from '../common/ProductCard';
import {
  Search,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Star,
  Sparkles,
  CheckCircle2,
  HelpCircle,
  ArrowRight,
  Calendar,
  MapPin,
  Clock,
  Building2
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

export interface PopularHotelDestination {
  name: string;
  location: string;
  fullName: string;
  desc: string;
  image: string;
}

const POPULAR_HOTEL_DESTINATIONS: PopularHotelDestination[] = [
  {
    name: 'V-OTA Resort & Spa',
    location: 'tại Nha Trang',
    fullName: 'V-OTA Resort & Spa tại Nha Trang',
    desc: 'Đảo Hòn Tre, Nha Trang',
    image: 'https://images.unsplash.com/photo-1566073771259-6a8506099945?q=80&w=800&auto=format&fit=crop'
  },
  {
    name: 'VinHolidays Fiesta',
    location: 'tại Phú Quốc',
    fullName: 'VinHolidays Fiesta tại Phú Quốc',
    desc: 'Grand World, Bãi Dài, Phú Quốc',
    image: 'https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?q=80&w=800&auto=format&fit=crop'
  },
  {
    name: 'V-OTA Resort & Golf',
    location: 'tại Nam Hội An',
    fullName: 'V-OTA Resort & Golf tại Nam Hội An',
    desc: 'Bình Minh, Thăng Bình, Quảng Nam',
    image: 'https://images.unsplash.com/photo-1584132967334-10e028bd69f7?q=80&w=800&auto=format&fit=crop'
  },
  {
    name: 'V-OTA Resort & Spa',
    location: 'tại Hạ Long',
    fullName: 'V-OTA Resort & Spa tại Hạ Long',
    desc: 'Đảo Rều, Bãi Cháy, Hạ Long',
    image: 'https://images.unsplash.com/photo-1578683010236-d716f9a3f461?q=80&w=800&auto=format&fit=crop'
  },
  {
    name: 'V-OTA Resort & Spa',
    location: 'tại Đà Nẵng',
    fullName: 'V-OTA Resort & Spa tại Đà Nẵng',
    desc: 'Bãi biển Non Nước, Đà Nẵng',
    image: 'https://images.unsplash.com/photo-1566073771259-6a8506099945?q=80&w=800&auto=format&fit=crop'
  },
  {
    name: 'V-OTA Landmark 81',
    location: 'tại TP. Hồ Chí Minh',
    fullName: 'V-OTA Landmark 81 tại TP. Hồ Chí Minh',
    desc: '720A Điện Biên Phủ, Bình Thạnh',
    image: 'https://images.unsplash.com/photo-1583417319070-4a69db38a482?q=80&w=800&auto=format&fit=crop'
  }
];

function getHotelLocationTag(address: string): string {
  if (address.includes('Nha Trang')) return 'tại Nha Trang';
  if (address.includes('Phú Quốc')) return 'tại Phú Quốc';
  if (address.includes('Cửa Lò') || address.includes('Cửa Hội')) return 'tại Cửa Lò';
  if (address.includes('Hạ Long')) return 'tại Hạ Long';
  if (address.includes('Hội An')) return 'tại Nam Hội An';
  if (address.includes('Đà Nẵng')) return 'tại Đà Nẵng';
  if (address.includes('TP. HCM') || address.includes('Hồ Chí Minh') || address.includes('Cần Giờ')) return 'tại TP. HCM';
  const parts = address.split(',');
  return `tại ${parts[parts.length - 1].trim()}`;
}

// DatePicker helper functions
function parseDateStr(str: string): Date {
  const parts = str.split('/');
  if (parts.length === 3) {
    const d = parseInt(parts[0], 10);
    const m = parseInt(parts[1], 10) - 1;
    const y = parseInt(parts[2], 10);
    if (!isNaN(d) && !isNaN(m) && !isNaN(y)) {
      return new Date(y, m, d);
    }
  }
  return new Date();
}

function formatDateStr(d: Date): string {
  const day = String(d.getDate()).padStart(2, '0');
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const year = d.getFullYear();
  return `${day}/${month}/${year}`;
}

function isSameDate(d1: Date, d2: Date): boolean {
  return (
    d1.getFullYear() === d2.getFullYear() &&
    d1.getMonth() === d2.getMonth() &&
    d1.getDate() === d2.getDate()
  );
}

export const HomeView: React.FC = () => {
  const { currentPersona, activeEvents, navigate, showToast, addToCart } = useTravel();

  // Search state
  const [destinationInput, setDestinationInput] = useState('V-OTA Resort & Spa tại Nha Trang');
  const [checkinDate, setCheckinDate] = useState('18/09/2026');
  const [checkoutDate, setCheckoutDate] = useState('19/09/2026');
  const [recentSearches, setRecentSearches] = useState<string[]>([
    'V-OTA Resort & Spa tại Nha Trang',
    'VinHolidays Fiesta tại Phú Quốc',
    'V-OTA Resort & Golf tại Nam Hội An'
  ]);

  // Search Panel (Separate Tab) state
  const [activeSearchTab, setActiveSearchTab] = useState<'destination' | 'dates' | 'guests' | null>(null);
  const [selectingDateType, setSelectingDateType] = useState<'checkin' | 'checkout'>('checkin');
  const [calendarViewDate, setCalendarViewDate] = useState(() => parseDateStr('18/09/2026'));
  const [hoveredDate, setHoveredDate] = useState<Date | null>(null);
  const searchBarContainerRef = useRef<HTMLDivElement>(null);

  // Rooms & Guests state
  const [rooms, setRooms] = useState(1);
  const [adults, setAdults] = useState(2);

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

  // Gợi ý từ engine thật (GET /recommendations). Không mô phỏng khi lỗi: lỗi thì hiện dòng "Thử lại" (frontend §4.1).
  const [recResponse, setRecResponse] = useState<RecommendationResponse | null>(null);
  const [recError, setRecError] = useState(false);
  const [recReload, setRecReload] = useState(0);
  const [isLoadingRecs, setIsLoadingRecs] = useState(false);
  const [showSectionWhy, setShowSectionWhy] = useState(false);

  useEffect(() => {
    const controller = new AbortController();

    // Danh tính do BFF gắn từ cookie phiên; đổi persona = đổi phiên nên effect chạy lại.
    // Không gửi destination: engine tự lấy điểm đến của chuyến vừa đặt, nên đặt phòng Đà Nẵng xong
    // thì trang chủ chuyển sang chuyến Đà Nẵng (AC-REC-02).
    setIsLoadingRecs(true);
    setRecError(false);
    fetchRecommendations({
      k: 4,
      signal: controller.signal,
    })
      .then((data) => {
        setRecResponse(data);
      })
      .catch((err) => {
        if (!controller.signal.aborted) {
          console.error('[HomeView] Failed to load recommendations:', err);
          setRecResponse(null);
          setRecError(true);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoadingRecs(false);
        }
      });

    return () => {
      controller.abort();
    };
  }, [currentPersona, activeEvents, recReload]);

  const strategy = recResponse?.strategy ?? 'popular';
  const destination = recResponse?.destination ?? '';
  const recommendations = recResponse?.recommendations ?? [];
  const excludedVerticals = recResponse?.diagnostics.excludedVerticals ?? [];

  // Close search panel on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (searchBarContainerRef.current && !searchBarContainerRef.current.contains(e.target as Node)) {
        setActiveSearchTab(null);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // DatePicker state handlers & calculations
  const parsedCheckin = parseDateStr(checkinDate);
  const parsedCheckout = parseDateStr(checkoutDate);

  const handlePrevMonth = () => {
    setCalendarViewDate(prev => new Date(prev.getFullYear(), prev.getMonth() - 1, 1));
  };

  const handleNextMonth = () => {
    setCalendarViewDate(prev => new Date(prev.getFullYear(), prev.getMonth() + 1, 1));
  };

  const handleDayClick = (dayDate: Date) => {
    if (selectingDateType === 'checkin') {
      setCheckinDate(formatDateStr(dayDate));
      if (dayDate.getTime() >= parsedCheckout.getTime()) {
        const nextDay = new Date(dayDate.getTime() + 86400000);
        setCheckoutDate(formatDateStr(nextDay));
      }
      setSelectingDateType('checkout');
    } else {
      if (dayDate.getTime() <= parsedCheckin.getTime()) {
        setCheckinDate(formatDateStr(dayDate));
        const nextDay = new Date(dayDate.getTime() + 86400000);
        setCheckoutDate(formatDateStr(nextDay));
        setSelectingDateType('checkout');
      } else {
        setCheckoutDate(formatDateStr(dayDate));
        setSelectingDateType('checkin');
      }
    }
  };

  const handleResetDates = () => {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const tomorrow = new Date(today.getTime() + 86400000);
    setCheckinDate(formatDateStr(today));
    setCheckoutDate(formatDateStr(tomorrow));
    setCalendarViewDate(new Date(today.getFullYear(), today.getMonth(), 1));
  };

  const viewYear = calendarViewDate.getFullYear();
  const viewMonth = calendarViewDate.getMonth();
  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
  const startDayOfWeek = (new Date(viewYear, viewMonth, 1).getDay() + 6) % 7;

  const scrollTrack = (ref: React.RefObject<HTMLDivElement | null>, direction: number, cardsCount: number = 2) => {
    if (ref.current) {
      const container = ref.current;
      const children = container.children;
      let cardDistance = 340;
      if (children.length >= 2) {
        const first = (children[0] as HTMLElement).getBoundingClientRect();
        const second = (children[1] as HTMLElement).getBoundingClientRect();
        const diff = second.left - first.left;
        if (diff > 0) {
          cardDistance = diff;
        }
      }
      const numCards = Math.max(2, cardsCount);
      const sign = direction < 0 ? -1 : 1;
      container.scrollBy({ left: sign * cardDistance * numCards, behavior: 'smooth' });
    }
  };

  const handleSearch = () => {
    setActiveSearchTab(null);
    const q = destinationInput.trim() || 'V-OTA Resort & Spa tại Nha Trang';
    setRecentSearches(prev => [q, ...prev.filter(item => item.toLowerCase() !== q.toLowerCase())].slice(0, 5));
    showToast(q.includes('tại') ? `Đang tìm ${q} (${rooms} phòng, ${adults} khách)...` : `Đang tìm các khách sạn tại ${q} (${rooms} phòng, ${adults} khách)...`);
    navigate(`/search?q=${encodeURIComponent(q)}&type=hotel&rooms=${rooms}&guests=${adults}`);
  };

  const handleSelectDestination = (destName: string) => {
    const hotelQuery = `Khách sạn tại ${destName}`;
    setDestinationInput(hotelQuery);
    showToast(`Đã chọn: ${hotelQuery}. Đang chuyển đến kết quả phù hợp...`);
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

          <div
            ref={searchBarContainerRef}
            className="relative"
          >
            {/* The Search Bar Trigger Bar */}
            <div
              className={`bg-white/95 backdrop-blur-md rounded-3xl px-3 py-1.5 sm:py-1 shadow-lg border text-slate-700 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-1.5 sm:gap-2 transition hover:bg-white ${
                activeSearchTab ? 'border-blue-500/50 ring-2 ring-blue-500/20 shadow-xl' : 'border-white/50'
              }`}
            >
              {/* Field 1: Destination (Compact) */}
              <div
                onClick={() => setActiveSearchTab(activeSearchTab === 'destination' ? null : 'destination')}
                className={`flex-1 text-left px-3 py-1 rounded-xl sm:rounded-full transition cursor-pointer relative group ${
                  activeSearchTab === 'destination' ? 'bg-blue-50/80 ring-1 ring-blue-500/30' : 'hover:bg-slate-50/80'
                }`}
              >
                <label className="block text-[9px] font-extrabold text-slate-400 uppercase tracking-wider group-hover:text-blue-600 transition-colors pointer-events-none">
                  Khách sạn / Điểm đến
                </label>
                <div className="flex items-center mt-0.5">
                  <input
                    type="text"
                    value={destinationInput}
                    onChange={(e) => setDestinationInput(e.target.value)}
                    onClick={(e) => {
                      e.stopPropagation();
                      setActiveSearchTab('destination');
                    }}
                    onFocus={() => setActiveSearchTab('destination')}
                    placeholder="Tên khách sạn, resort (vd: Hotel tại Nha Trang)..."
                    className="w-full text-slate-800 font-bold text-xs sm:text-sm focus:outline-none bg-transparent placeholder:text-slate-400 cursor-pointer"
                  />
                </div>
              </div>

              <div className="hidden md:block w-px h-6 bg-slate-200"></div>

              {/* Field 2: Dates (Check-in & Check-out Compact) */}
              <div
                onClick={() => setActiveSearchTab(activeSearchTab === 'dates' ? null : 'dates')}
                className={`flex-1 text-left px-3 py-1 rounded-xl sm:rounded-full transition cursor-pointer group ${
                  activeSearchTab === 'dates' ? 'bg-blue-50/80 ring-1 ring-blue-500/30' : 'hover:bg-slate-50/80'
                }`}
              >
                <div className="flex items-center justify-between gap-1.5 sm:gap-2">
                  {/* Ngày đi */}
                  <div className="flex-1 min-w-0">
                    <label className="block text-[9px] font-extrabold text-slate-400 uppercase tracking-wider group-hover:text-blue-600 transition-colors">
                      Ngày đi
                    </label>
                    <div className="font-bold text-xs sm:text-sm text-slate-800 truncate">
                      {checkinDate}
                    </div>
                  </div>

                  <div className="w-px h-5 bg-slate-200 shrink-0 mx-1"></div>

                  {/* Ngày về */}
                  <div className="flex-1 min-w-0 text-right sm:text-left">
                    <label className="block text-[9px] font-extrabold text-slate-400 uppercase tracking-wider group-hover:text-blue-600 transition-colors">
                      Ngày về
                    </label>
                    <div className="font-bold text-xs sm:text-sm text-slate-800 truncate">
                      {checkoutDate}
                    </div>
                  </div>

                  <Calendar className="w-3.5 h-3.5 text-slate-400 shrink-0 group-hover:text-blue-600 transition-colors hidden sm:block" />
                </div>
              </div>

              <div className="hidden md:block w-px h-6 bg-slate-200"></div>

              {/* Field 3: Rooms & Guests (Compact) */}
              <div
                onClick={() => setActiveSearchTab(activeSearchTab === 'guests' ? null : 'guests')}
                className={`flex-1 text-left px-3 py-1 rounded-xl sm:rounded-full transition cursor-pointer group ${
                  activeSearchTab === 'guests' ? 'bg-blue-50/80 ring-1 ring-blue-500/30' : 'hover:bg-slate-50/80'
                }`}
              >
                <label className="block text-[9px] font-extrabold text-slate-400 uppercase tracking-wider group-hover:text-blue-600 transition-colors">
                  Số lượng
                </label>
                <div className="flex items-center justify-between">
                  <span className="font-bold text-xs sm:text-sm text-slate-800 truncate">
                    {rooms} phòng, {adults} người lớn
                  </span>
                  <ChevronDown className={`w-3.5 h-3.5 text-slate-400 shrink-0 ml-1 transition-transform ${
                    activeSearchTab === 'guests' ? 'rotate-180 text-blue-600' : 'group-hover:text-blue-600'
                  }`} />
                </div>
              </div>

              {/* Search Action Button (Compact) */}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleSearch();
                }}
                className="w-full md:w-auto px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs rounded-xl sm:rounded-full shadow-md hover:shadow-slate-900/30 flex items-center justify-center space-x-1.5 transition duration-200 transform active:scale-95 cursor-pointer shrink-0"
                aria-label="Tìm kiếm"
              >
                <Search className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* ========================================================================= */}
            {/* PANEL 1: ĐIỂM ĐẾN (FULL-WIDTH = WIDTH THANH SEARCH)                      */}
            {/* ========================================================================= */}
            {activeSearchTab === 'destination' && (
              <div
                onClick={(e) => e.stopPropagation()}
                className="absolute top-full left-0 right-0 mt-2 bg-white rounded-3xl shadow-2xl border border-slate-100 p-5 sm:p-6 z-50 text-slate-800 animate-in fade-in zoom-in-95 duration-150 max-h-[85vh] overflow-y-auto space-y-6"
              >
                {/* PHẦN 1: TÌM KIẾM GẦN ĐÂY */}
                <div>
                  <div className="flex items-center justify-between mb-2.5">
                    <div className="flex items-center space-x-2">
                      <div className="w-6 h-6 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center">
                        <Clock className="w-3.5 h-3.5" />
                      </div>
                      <h4 className="font-bold text-xs sm:text-sm text-slate-800 uppercase tracking-wider">Tìm kiếm gần đây</h4>
                    </div>
                    {recentSearches.length > 0 && (
                      <button
                        type="button"
                        onClick={() => setRecentSearches([])}
                        className="text-[11px] text-slate-400 hover:text-rose-500 transition cursor-pointer font-medium"
                      >
                        Xóa lịch sử
                      </button>
                    )}
                  </div>

                  {recentSearches.length > 0 ? (
                    <div className="flex flex-wrap gap-2">
                      {recentSearches.map((item) => (
                        <button
                          key={item}
                          type="button"
                          onClick={() => {
                            setDestinationInput(item);
                            showToast(`Đã chọn: ${item}`);
                            setActiveSearchTab('dates');
                          }}
                          className="px-3.5 py-1.5 rounded-full bg-slate-50 hover:bg-blue-50 border border-slate-200/80 hover:border-blue-300 text-slate-700 hover:text-blue-700 text-xs font-semibold flex items-center space-x-1.5 transition cursor-pointer shadow-2xs group"
                        >
                          <Clock className="w-3 h-3 text-slate-400 group-hover:text-blue-500" />
                          <span>{item}</span>
                        </button>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-slate-400 italic">Chưa có tìm kiếm gần đây</p>
                  )}
                </div>

                {/* PHẦN 2: KHÁCH SẠN THEO ĐIỂM ĐẾN PHỔ BIẾN */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center space-x-2">
                      <div className="w-6 h-6 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
                        <MapPin className="w-3.5 h-3.5" />
                      </div>
                      <h4 className="font-bold text-xs sm:text-sm text-slate-800 uppercase tracking-wider">Khách sạn & Resort theo điểm đến</h4>
                    </div>
                    <span className="text-xs text-slate-400 font-medium">Vinpearl Resorts & Hotels</span>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5">
                    {POPULAR_HOTEL_DESTINATIONS.map((dest) => {
                      const isSelected = destinationInput.toLowerCase().includes(dest.name.toLowerCase()) || destinationInput.toLowerCase().includes(dest.fullName.toLowerCase());
                      return (
                        <button
                          key={dest.fullName}
                          type="button"
                          onClick={() => {
                            setDestinationInput(dest.fullName);
                            showToast(`Đã chọn: ${dest.fullName}`);
                            setActiveSearchTab('dates');
                          }}
                          className={`p-2 rounded-2xl text-left transition cursor-pointer border flex flex-col items-center text-center group ${
                            isSelected
                              ? 'bg-blue-50/80 border-blue-400 ring-2 ring-blue-500/20 shadow-xs'
                              : 'bg-slate-50/60 hover:bg-blue-50/40 border-slate-100 hover:border-blue-200'
                          }`}
                        >
                          <div className="relative w-full h-16 sm:h-20 rounded-xl overflow-hidden shadow-2xs">
                            <img
                              src={dest.image}
                              alt={dest.fullName}
                              className="w-full h-full object-cover group-hover:scale-105 transition duration-300"
                            />
                            <div className="absolute inset-0 bg-gradient-to-t from-slate-900/70 via-transparent to-transparent"></div>
                            <span className="absolute bottom-1.5 left-1.5 px-1.5 py-0.5 rounded-md bg-blue-600/90 text-white text-[9px] font-bold shadow-xs">
                              {dest.location}
                            </span>
                          </div>
                          <div className="mt-2 w-full text-center">
                            <div className="font-bold text-xs text-slate-800 truncate group-hover:text-blue-600 transition-colors">
                              {dest.name}
                            </div>
                            <div className="text-[10px] text-slate-400 truncate mt-0.5">
                              {dest.desc}
                            </div>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* PHẦN 3: GỢI Ý KHÁCH SẠN */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center space-x-2">
                      <div className="w-6 h-6 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
                        <Building2 className="w-3.5 h-3.5" />
                      </div>
                      <h4 className="font-bold text-xs sm:text-sm text-slate-800 uppercase tracking-wider">Gợi ý khách sạn & Resort nổi bật</h4>
                    </div>
                    <span className="text-xs text-blue-600 font-semibold bg-blue-50 px-2.5 py-0.5 rounded-full">
                      Ưu đãi giá tốt
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                    {SECTION_1_HOTELS.slice(0, 4).map((hotel) => {
                      const locTag = getHotelLocationTag(hotel.address);
                      const fullHotelName = `${hotel.name} ${locTag}`;
                      return (
                        <button
                          key={hotel.id}
                          type="button"
                          onClick={() => {
                            setDestinationInput(fullHotelName);
                            showToast(`Đã chọn: ${fullHotelName}`);
                            setActiveSearchTab('dates');
                          }}
                          className="p-2.5 rounded-2xl bg-white border border-slate-200/80 hover:border-blue-400 hover:shadow-md transition text-left cursor-pointer flex space-x-3 group"
                        >
                          <img
                            src={hotel.image}
                            alt={hotel.name}
                            className="w-16 h-16 rounded-xl object-cover shrink-0 shadow-2xs group-hover:scale-103 transition duration-200"
                          />
                          <div className="min-w-0 flex-1 flex flex-col justify-between">
                            <div>
                              <div className="font-bold text-xs text-slate-900 line-clamp-1 group-hover:text-blue-600 transition-colors">
                                {hotel.name}
                              </div>
                              <div className="flex items-center gap-1.5 mt-0.5">
                                <span className="text-[9px] font-bold text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded shrink-0">
                                  {locTag}
                                </span>
                                <div className="flex items-center space-x-1">
                                  <Star className="w-3 h-3 text-amber-400 fill-amber-400 shrink-0" />
                                  <span className="text-[11px] font-bold text-slate-700">{hotel.ratingScore}</span>
                                  <span className="text-[10px] text-slate-400">({hotel.reviewsCount})</span>
                                </div>
                              </div>
                            </div>
                            <div className="mt-1 flex items-baseline justify-between">
                              <span className="text-[10px] text-slate-400 line-through">{hotel.originalPrice}</span>
                              <span className="text-xs font-black text-blue-600">{hotel.price}</span>
                            </div>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}

            {/* ========================================================================= */}
            {/* PANEL 2: DATE PICKER (COMPACT MODAL / DROPDOWN)                          */}
            {/* ========================================================================= */}
            {activeSearchTab === 'dates' && (
              <div
                onClick={(e) => e.stopPropagation()}
                className="absolute top-full left-1/2 -translate-x-1/2 mt-2 w-[340px] sm:w-[380px] bg-white rounded-3xl shadow-2xl border border-slate-100 p-4 sm:p-5 z-50 text-slate-800 animate-in fade-in zoom-in-95 duration-150 max-h-[85vh] overflow-y-auto"
              >
                <div className="space-y-3.5">
                  {/* Switcher ngày nhận / trả phòng */}
                  <div className="flex items-center justify-between gap-1.5 p-1 bg-slate-100/80 rounded-xl">
                    <button
                      type="button"
                      onClick={() => setSelectingDateType('checkin')}
                      className={`flex-1 py-1.5 px-2.5 rounded-lg text-left transition cursor-pointer ${
                        selectingDateType === 'checkin'
                          ? 'bg-white shadow-xs font-bold text-blue-600 ring-1 ring-blue-500/20'
                          : 'text-slate-600 hover:text-slate-900 font-medium'
                      }`}
                    >
                      <span className="block text-[9px] uppercase tracking-wider text-slate-400 font-extrabold">Ngày nhận phòng</span>
                      <span className="text-xs sm:text-sm font-bold block truncate">{checkinDate}</span>
                    </button>

                    <div className="w-px h-6 bg-slate-200 shrink-0"></div>

                    <button
                      type="button"
                      onClick={() => setSelectingDateType('checkout')}
                      className={`flex-1 py-1.5 px-2.5 rounded-lg text-left transition cursor-pointer ${
                        selectingDateType === 'checkout'
                          ? 'bg-white shadow-xs font-bold text-blue-600 ring-1 ring-blue-500/20'
                          : 'text-slate-600 hover:text-slate-900 font-medium'
                      }`}
                    >
                      <span className="block text-[9px] uppercase tracking-wider text-slate-400 font-extrabold">Ngày trả phòng</span>
                      <span className="text-xs sm:text-sm font-bold block truncate">{checkoutDate}</span>
                    </button>
                  </div>

                  {/* Header điều hướng tháng */}
                  <div className="flex items-center justify-between px-1">
                    <button
                      type="button"
                      onClick={handlePrevMonth}
                      className="w-7 h-7 rounded-lg hover:bg-slate-100 flex items-center justify-center text-slate-600 transition cursor-pointer"
                      aria-label="Tháng trước"
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </button>
                    <span className="text-xs sm:text-sm font-bold text-slate-800 select-none">
                      Tháng {viewMonth + 1}, {viewYear}
                    </span>
                    <button
                      type="button"
                      onClick={handleNextMonth}
                      className="w-7 h-7 rounded-lg hover:bg-slate-100 flex items-center justify-center text-slate-600 transition cursor-pointer"
                      aria-label="Tháng sau"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>

                  {/* Thứ trong tuần */}
                  <div className="grid grid-cols-7 text-center text-[11px] font-bold text-slate-400 select-none py-1 border-b border-slate-100">
                    <div>T2</div>
                    <div>T3</div>
                    <div>T4</div>
                    <div>T5</div>
                    <div>T6</div>
                    <div className="text-amber-500">T7</div>
                    <div className="text-rose-500">CN</div>
                  </div>

                  {/* Lưới ngày */}
                  <div
                    className="grid grid-cols-7 gap-y-1 text-center text-xs"
                    onMouseLeave={() => setHoveredDate(null)}
                  >
                    {Array.from({ length: startDayOfWeek }).map((_, idx) => (
                      <div key={`empty-${idx}`} className="h-7 sm:h-8" />
                    ))}

                    {Array.from({ length: daysInMonth }).map((_, idx) => {
                      const dayNum = idx + 1;
                      const dayDate = new Date(viewYear, viewMonth, dayNum);
                      const isCheckin = isSameDate(dayDate, parsedCheckin);
                      const isCheckout = isSameDate(dayDate, parsedCheckout);
                      const isInRange = dayDate > parsedCheckin && dayDate < parsedCheckout;
                      const isInHover = selectingDateType === 'checkout' && hoveredDate && hoveredDate > parsedCheckin && dayDate > parsedCheckin && dayDate <= hoveredDate;

                      return (
                        <div
                          key={`day-${dayNum}`}
                          className={`h-7 sm:h-8 flex items-center justify-center relative ${
                            isInRange || isInHover ? 'bg-blue-50/80' : ''
                          } ${isCheckin && !isCheckout ? 'rounded-l-full' : ''} ${
                            isCheckout && !isCheckin ? 'rounded-r-full' : ''
                          }`}
                        >
                          <button
                            type="button"
                            onClick={() => handleDayClick(dayDate)}
                            onMouseEnter={() => setHoveredDate(dayDate)}
                            className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold transition cursor-pointer ${
                              isCheckin || isCheckout
                                ? 'bg-blue-600 text-white font-bold shadow-xs'
                                : isInRange || isInHover
                                ? 'text-blue-700 font-bold hover:bg-blue-100'
                                : 'text-slate-700 hover:bg-slate-100'
                            }`}
                          >
                            {dayNum}
                          </button>
                        </div>
                      );
                    })}
                  </div>

                  {/* Footer DatePicker: Đặt lại ngày */}
                  <div className="flex items-center justify-end pt-2 border-t border-slate-100">
                    <button
                      type="button"
                      onClick={handleResetDates}
                      className="text-xs text-slate-500 hover:text-blue-600 font-medium transition cursor-pointer"
                    >
                      Đặt lại
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* ========================================================================= */}
            {/* PANEL 3: SỐ LƯỢNG PHÒNG & KHÁCH (COMPACT DROPDOWN BÊN PHẢI)              */}
            {/* ========================================================================= */}
            {activeSearchTab === 'guests' && (
              <div
                onClick={(e) => e.stopPropagation()}
                className="absolute top-full right-0 mt-2 w-72 sm:w-80 bg-white rounded-3xl shadow-2xl border border-slate-100 p-4 sm:p-5 z-50 text-slate-800 animate-in fade-in zoom-in-95 duration-150 max-h-[85vh] overflow-y-auto"
              >
                <div className="max-w-md mx-auto space-y-4">
                  <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                    <div>
                      <h4 className="font-bold text-sm sm:text-base text-slate-900">Số lượng phòng & khách</h4>
                      <p className="text-xs text-slate-400">Chọn số phòng và thành viên cho chuyến đi</p>
                    </div>
                  </div>

                  {/* Phòng */}
                  <div className="p-3.5 bg-slate-50/80 rounded-2xl flex items-center justify-between border border-slate-100">
                    <div>
                      <div className="font-bold text-sm text-slate-900">Phòng</div>
                      <div className="text-xs text-slate-400">Số lượng phòng đặt</div>
                    </div>
                    <div className="flex items-center space-x-3">
                      <button
                        type="button"
                        className="w-9 h-9 rounded-full border border-slate-200 bg-white flex items-center justify-center font-bold hover:bg-slate-100 text-slate-600 transition cursor-pointer shadow-xs disabled:opacity-40"
                        onClick={() => setRooms(Math.max(1, rooms - 1))}
                        disabled={rooms <= 1}
                      >
                        -
                      </button>
                      <span className="w-6 text-center font-bold text-sm text-slate-800">{rooms}</span>
                      <button
                        type="button"
                        className="w-9 h-9 rounded-full border border-slate-200 bg-white flex items-center justify-center font-bold hover:bg-slate-100 text-slate-600 transition cursor-pointer shadow-xs disabled:opacity-40"
                        onClick={() => setRooms(Math.min(8, rooms + 1))}
                        disabled={rooms >= 8}
                      >
                        +
                      </button>
                    </div>
                  </div>

                  {/* Người lớn */}
                  <div className="p-3.5 bg-slate-50/80 rounded-2xl flex items-center justify-between border border-slate-100">
                    <div>
                      <div className="font-bold text-sm text-slate-900">Người lớn</div>
                      <div className="text-xs text-slate-400">Từ 12 tuổi trở lên</div>
                    </div>
                    <div className="flex items-center space-x-3">
                      <button
                        type="button"
                        className="w-9 h-9 rounded-full border border-slate-200 bg-white flex items-center justify-center font-bold hover:bg-slate-100 text-slate-600 transition cursor-pointer shadow-xs disabled:opacity-40"
                        onClick={() => setAdults(Math.max(1, adults - 1))}
                        disabled={adults <= 1}
                      >
                        -
                      </button>
                      <span className="w-6 text-center font-bold text-sm text-slate-800">{adults}</span>
                      <button
                        type="button"
                        className="w-9 h-9 rounded-full border border-slate-200 bg-white flex items-center justify-center font-bold hover:bg-slate-100 text-slate-600 transition cursor-pointer shadow-xs disabled:opacity-40"
                        onClick={() => setAdults(Math.min(16, adults + 1))}
                        disabled={adults >= 16}
                      >
                        +
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

        </section>        {/* ========================================================================= */}
        {/* OPTIONAL PERSONALIZATION PANEL (K1 / K2 V-OTA DEMO ACCORDION)              */}
        {/* ========================================================================= */}
        {currentPersona && recError && (
          <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-3 pb-4">
            <p className="text-xs text-slate-500">
              Chưa tải được gợi ý ·{' '}
              <button type="button" onClick={() => setRecReload((n) => n + 1)} className="font-semibold text-blue-700 hover:underline">
                Thử lại
              </button>
            </p>
          </section>
        )}
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
                  {/* <button
                    type="button"
                    onClick={() => showToast('Tính năng đang được cập nhật!')}
                    className="inline-flex items-center gap-1 text-xs sm:text-sm font-semibold text-blue-600 hover:text-blue-700 transition cursor-pointer"
                  >
                    <span>Xem thêm</span>
                    <ArrowRight className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                  </button> */}
                  <button
                    onClick={() => setShowSectionWhy(true)}
                    className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold text-blue-700 bg-blue-50 hover:bg-blue-100 rounded-xl border border-blue-200 transition-colors cursor-pointer"
                  >
                    <HelpCircle className="w-3.5 h-3.5" />
                    <span>Vì sao có gợi ý này?</span>
                  </button>
                </div>
              </div>

              <div className={`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-5 transition-opacity duration-200 ${isLoadingRecs ? 'opacity-60 pointer-events-none' : 'opacity-100'}`}>
                {recommendations.slice(0, 4).map((rec) => (
                  <ProductCard
                    key={rec.product.id}
                    product={rec.product}
                    variant="grid"
                    because={rec.because}
                    strategy={strategy}
                    excludedVerticals={excludedVerticals}
                    score={rec.score}
                    rank={rec.rank}
                  />
                ))}
              </div>

              <WhyPopover
                isOpen={showSectionWhy}
                onClose={() => setShowSectionWhy(false)}
                targetProductName={destination ? `Toàn bộ danh mục chuyến ${destination}` : 'Gợi ý cho bạn'}
                becauseItems={recommendations[0]?.because || []}
                strategy={strategy}
                excludedVerticals={excludedVerticals}
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
              {/* <button
                type="button"
                onClick={() => showToast('Tính năng đang được cập nhật!')}
                className="inline-flex items-center gap-1 text-xs sm:text-sm font-semibold text-blue-600 hover:text-blue-700 transition cursor-pointer"
              >
                <span>Xem thêm</span>
                <ArrowRight className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
              </button> */}
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => scrollTrack(hotelTrack1Ref, -1)}
                  className="w-10 h-10 rounded-full border border-slate-200 hover:bg-slate-100 flex items-center justify-center text-slate-600 transition shadow-sm active:scale-95 cursor-pointer"
                  aria-label="Cuộn sang trái"
                >
                  <ChevronLeft className="w-5 h-5" />
                </button>
                <button
                  onClick={() => scrollTrack(hotelTrack1Ref, 1)}
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
        {/* SECTION 2: KHÁCH SẠN ĐƯỢC YÊU THÍCH NHẤT (CAROUSEL 2)                    */}
        {/* ========================================================================= */}
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
                Khách sạn được yêu thích nhất
              </h2>
            </div>
            <div className="flex items-center space-x-3">
              {/* <button
                type="button"
                onClick={() => showToast('Tính năng đang được cập nhật!')}
                className="inline-flex items-center gap-1 text-xs sm:text-sm font-semibold text-blue-600 hover:text-blue-700 transition cursor-pointer"
              >
                <span>Xem thêm</span>
                <ArrowRight className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
              </button> */}
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => scrollTrack(hotelTrack2Ref, -1)}
                  className="w-10 h-10 rounded-full border border-slate-200 hover:bg-slate-100 flex items-center justify-center text-slate-600 transition shadow-sm active:scale-95 cursor-pointer"
                  aria-label="Cuộn sang trái"
                >
                  <ChevronLeft className="w-5 h-5" />
                </button>
                <button
                  onClick={() => scrollTrack(hotelTrack2Ref, 1)}
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
              {/* <button
                type="button"
                onClick={() => showToast('Tính năng đang được cập nhật!')}
                className="inline-flex items-center gap-1 text-xs sm:text-sm font-semibold text-blue-600 hover:text-blue-700 transition cursor-pointer"
              >
                <span>Xem thêm</span>
                <ArrowRight className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
              </button> */}
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => scrollTrack(destinationTrackRef, -1)}
                  className="w-10 h-10 rounded-full border border-slate-200 hover:bg-slate-100 flex items-center justify-center text-slate-600 transition shadow-sm active:scale-95 cursor-pointer"
                  aria-label="Cuộn sang trái"
                >
                  <ChevronLeft className="w-5 h-5" />
                </button>
                <button
                  onClick={() => scrollTrack(destinationTrackRef, 1)}
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
                className="w-56 sm:w-60 md:w-[calc((100%-40px)/3)] lg:w-[calc((100%-60px)/4)] xl:w-[calc((100%-80px)/5)] h-80 rounded-2xl overflow-hidden relative flex-shrink-0 cursor-pointer group shadow-md hover:shadow-2xl transition-all duration-300"
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
                <div className="w-12 h-12 rounded-xl bg-blue-50 border border-blue-100/80 flex items-center justify-center mb-4 shadow-md shadow-blue-500/10 overflow-hidden">
                  <img
                    src="/trust_badge_ecosystem.webp"
                    alt="Hệ sinh thái du lịch & giải trí toàn diện"
                    className="w-10 h-10 object-contain drop-shadow-xs"
                  />
                </div>
                <h3 className="text-base font-bold text-slate-900 leading-snug">
                  Hệ sinh thái du lịch & giải trí toàn diện
                </h3>
                <p className="text-xs text-slate-500 mt-2 leading-relaxed">
                  Tích hợp đồng bộ từ khách sạn, vui chơi giải trí VinWonders, ẩm thực tới di chuyển trong cùng một tài khoản.
                </p>
              </div>

              {/* Trust Badge 2 */}
              <div className="glass-card rounded-2xl p-6 border border-white/70 shadow-lg hover:shadow-2xl transition duration-300 flex flex-col items-start">
                <div className="w-12 h-12 rounded-xl bg-blue-50 border border-blue-100/80 flex items-center justify-center mb-4 shadow-md shadow-blue-500/10 overflow-hidden">
                  <img
                    src="/trust_badge_booking.webp"
                    alt="Trải nghiệm đặt dịch vụ liền mạch"
                    className="w-10 h-10 object-contain drop-shadow-xs"
                  />
                </div>
                <h3 className="text-base font-bold text-slate-900 leading-snug">
                  Trải nghiệm đặt dịch vụ liền mạch
                </h3>
                <p className="text-xs text-slate-500 mt-2 leading-relaxed">
                  Xác nhận đặt chỗ theo thời gian thực, lưu trữ vé điện tử và mã QR bảo mật ngay trên ứng dụng mà không cần in giấy.
                </p>
              </div>

              {/* Trust Badge 3 */}
              <div className="glass-card rounded-2xl p-6 border border-white/70 shadow-lg hover:shadow-2xl transition duration-300 flex flex-col items-start">
                <div className="w-12 h-12 rounded-xl bg-blue-50 border border-blue-100/80 flex items-center justify-center mb-4 shadow-md shadow-blue-500/10 overflow-hidden">
                  <img
                    src="/trust_badge_ai_assistant.webp"
                    alt="Trợ lý AI đồng hành du lịch"
                    className="w-10 h-10 object-contain drop-shadow-xs"
                  />
                </div>
                <h3 className="text-base font-bold text-slate-900 leading-snug">
                  Trợ lý AI đồng hành du lịch
                </h3>
                <p className="text-xs text-slate-500 mt-2 leading-relaxed">
                  Lên kế hoạch thông minh theo sở thích và ngân sách, tối ưu hóa thời gian và tuyến điểm di chuyển cho cả gia đình.
                </p>
              </div>
            </div>
          </div>
        </section>


      </main>
    </div>
  );
};
