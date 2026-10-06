import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { GroundedPlan, Product, TransitMode } from '../../types/travel';
import { MapPin, Navigation, Layers, ShoppingBag, Plus, Info, Home, Sun, CloudSun, Sunset, Moon, Car, Footprints, Ship, Plane, Compass } from 'lucide-react';
import {
  buildRouteRequests,
  defaultRouteProvider,
  resolveRouteRequests,
  RouteResult,
} from '../../services/routeGeometry';

interface ItineraryMapProps {
  plan: GroundedPlan;
  activeDay: number;
  onSelectDay: (day: number) => void;
  /** Nút của sản phẩm trên ghim: Đặt ngay, và Thêm vào giỏ với loại vào giỏ được. `null` khi sản phẩm chưa đặt được. */
  itemActions?: (product: Product) => { canAddToCart: boolean; bookNow: () => void; addToCart: () => void } | null;
  focusedCoordinate?: { lat: number; lng: number } | null;
  focusedPointId?: string | null;
  className?: string;
}

interface MapPoint {
  id: string;
  lat: number;
  lng: number;
  title: string;
  type: 'stay' | 'slot';
  day?: number;
  timeSlot?: string;
  product?: Product;
  address?: string;
  note?: string;
  orderNumber?: number;
  transitInfo?: string;
  transitMode?: TransitMode;
}

interface TransitVisual {
  type: 'plane' | 'boat_cable' | 'walking' | 'bicycle' | 'car';
  emoji: string;
  label: string;
  fullLabel: string;
  color: string;
  dashArray?: string;
  weight: number;
}

function getTransitVisual(mode: TransitMode): TransitVisual {
  switch (mode) {
    case 'flight':
      return {
        type: 'plane',
        emoji: '✈️',
        label: 'Sân bay',
        fullLabel: 'Xe đón tiễn sân bay / Chuyến bay',
        color: '#6366f1',
        dashArray: '8, 8',
        weight: 3.5,
      };
    case 'ferry':
    case 'cable':
      return {
        type: 'boat_cable',
        emoji: mode === 'cable' ? '🚡' : '🚤',
        label: mode === 'cable' ? 'Cáp treo' : 'Cano/Tàu',
        fullLabel: mode === 'cable' ? 'Cáp treo vượt biển' : 'Cano / Tàu cao tốc',
        color: '#0284c7',
        dashArray: '6, 6',
        weight: 3.5,
      };
    case 'walking':
      return {
        type: 'walking',
        emoji: '🚶',
        label: 'Đi bộ',
        fullLabel: 'Tản bộ dạo cảnh',
        color: '#10b981',
        dashArray: '3, 6',
        weight: 3,
      };
    case 'bicycle':
      return {
        type: 'bicycle',
        emoji: '🚲',
        label: 'Xe đạp',
        fullLabel: 'Xe đạp',
        color: '#d97706',
        dashArray: '5, 5',
        weight: 3,
      };
    case 'driving':
    default:
      return {
        type: 'car',
        emoji: '🚗',
        label: 'Ô tô/Taxi',
        fullLabel: 'Xe ô tô / Taxi du lịch',
        color: '#2563eb',
        weight: 3.5,
      };
  }
}

const DAY_COLORS: Record<number, { bg: string; text: string; hex: string; border: string }> = {
  1: { bg: 'bg-blue-600', text: 'text-white', hex: '#2563eb', border: '#1d4ed8' },
  2: { bg: 'bg-emerald-600', text: 'text-white', hex: '#059669', border: '#047857' },
  3: { bg: 'bg-amber-600', text: 'text-white', hex: '#d97706', border: '#b45309' },
  4: { bg: 'bg-purple-600', text: 'text-white', hex: '#7c3aed', border: '#6d28d9' },
  5: { bg: 'bg-rose-600', text: 'text-white', hex: '#e11d48', border: '#be123c' },
};

export const ItineraryMap: React.FC<ItineraryMapProps> = ({
  plan,
  activeDay,
  onSelectDay,
  itemActions,
  focusedCoordinate,
  focusedPointId,
  className = ''
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersLayerRef = useRef<L.LayerGroup | null>(null);
  const linesLayerRef = useRef<L.LayerGroup | null>(null);
  const highlightLayerRef = useRef<L.LayerGroup | null>(null);
  const [selectedPoint, setSelectedPoint] = useState<MapPoint | null>(null);
  const [filterDay, setFilterDay] = useState<number>(activeDay);
  const [routeResults, setRouteResults] = useState<RouteResult[]>([]);
  const [routeStatus, setRouteStatus] = useState<'idle' | 'loading' | 'ready' | 'partial'>('idle');

  // Sync internal filterDay with parent activeDay
  useEffect(() => {
    setFilterDay(activeDay);
  }, [activeDay]);

  // Extract all geocoded points from the plan
  const getAllPoints = (): MapPoint[] => {
    const points: MapPoint[] = [];

    // Stay points: Support both multiple stays (stays) and single stay (stay)
    if (plan.stays && plan.stays.length > 0) {
      plan.stays.forEach((s, idx) => {
        if (s.product.coordinates) {
          points.push({
            id: 'stay-' + (s.productId || idx),
            lat: s.product.coordinates.lat,
            lng: s.product.coordinates.lng,
            title: `${s.product.name} (${s.dayRange || `Khách sạn ${idx + 1}`})`,
            type: 'stay',
            product: s.product,
            address: s.product.address,
            note: s.note
          });
        }
      });
    } else if (plan.stay?.product.coordinates) {
      points.push({
        id: 'stay-' + plan.stay.productId,
        lat: plan.stay.product.coordinates.lat,
        lng: plan.stay.product.coordinates.lng,
        title: plan.stay.product.name,
        type: 'stay',
        product: plan.stay.product,
        address: plan.stay.product.address,
        note: plan.stay.note
      });
    }

    // Days slots points
    let order = 1;
    plan.days.forEach(day => {
      day.slots.forEach(slot => {
        // Đếm mọi slot, kể cả slot không có toạ độ (không vẽ điểm), để số và id điểm khớp danh sách ngày và `locateProduct`.
        const orderNumber = order++;
        const coord = slot.coordinates || slot.product?.coordinates;
        if (coord) {
          points.push({
            id: `day-${day.day}-slot-${slot.time}-${orderNumber}`,
            lat: coord.lat,
            lng: coord.lng,
            title: slot.product?.name || slot.activityTitle || 'Điểm tham quan',
            type: 'slot',
            day: day.day,
            timeSlot: slot.time,
            product: slot.product,
            address: slot.address || slot.product?.address,
            note: slot.note,
            orderNumber,
            transitInfo: slot.transitInfo,
            transitMode: slot.transitMode,
          });
        }
      });
    });

    return points;
  };

  // Initialize Map
  useEffect(() => {
    if (!mapContainerRef.current) return;

    // Destroy prior map instance if exists
    if (mapInstanceRef.current) {
      mapInstanceRef.current.remove();
      mapInstanceRef.current = null;
    }

    const points = getAllPoints();
    const defaultCenter: [number, number] = points.length > 0 
      ? [points[0].lat, points[0].lng] 
      : [12.2388, 109.1967]; // Default Nha Trang

    const map = L.map(mapContainerRef.current, {
      center: defaultCenter,
      zoom: 12,
      zoomControl: false,
      attributionControl: false,
    });

    // OpenStreetMap Standard tiles plus OSRM/FOSSGIS route attribution.
    L.control.attribution({
      position: 'bottomright',
      prefix: false,
    }).addTo(map);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors · Routing <a href="https://project-osrm.org/" target="_blank" rel="noreferrer">OSRM</a>/<a href="https://routing.openstreetmap.de/about.html" target="_blank" rel="noreferrer">FOSSGIS</a> · <a href="https://www.openstreetmap.org/fixthemap" target="_blank" rel="noreferrer">Sửa bản đồ</a>',
      maxZoom: 19,
    }).addTo(map);

    // Custom Zoom controls at bottom right
    L.control.zoom({ position: 'bottomright' }).addTo(map);

    const markersGroup = L.layerGroup().addTo(map);
    const linesGroup = L.layerGroup().addTo(map);
    const highlightGroup = L.layerGroup().addTo(map);

    markersLayerRef.current = markersGroup;
    linesLayerRef.current = linesGroup;
    highlightLayerRef.current = highlightGroup;
    mapInstanceRef.current = map;

    // Force map container recalculation
    setTimeout(() => {
      map.invalidateSize();
    }, 200);

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Handle map container resizing (khi thu nhỏ/mở rộng cột chat AI)
  useEffect(() => {
    if (!mapContainerRef.current) return;
    const resizeObserver = new ResizeObserver(() => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.invalidateSize();
      }
    });
    resizeObserver.observe(mapContainerRef.current);
    return () => {
      resizeObserver.disconnect();
    };
  }, []);

  // Update markers and request real route geometries when the plan/day changes.
  useEffect(() => {
    const map = mapInstanceRef.current;
    const markersGroup = markersLayerRef.current;
    const linesGroup = linesLayerRef.current;
    if (!map || !markersGroup || !linesGroup) return;

    let cancelled = false;
    markersGroup.clearLayers();
    linesGroup.clearLayers();
    setRouteResults([]);
    setRouteStatus('idle');

    const allPoints = getAllPoints();
    const visiblePoints = filterDay === 0
      ? allPoints
      : allPoints.filter((point) => point.type === 'stay' || point.day === filterDay);

    if (visiblePoints.length === 0) return () => {
      cancelled = true;
    };

    const bounds = L.latLngBounds([]);
    const stayHtml = `
      <div class="relative group cursor-pointer transform -translate-x-1/2 -translate-y-1/2">
        <div class="w-9 h-9 rounded-full bg-indigo-600 text-white flex items-center justify-center shadow-lg border-2 border-white ring-2 ring-indigo-300 transition-transform hover:scale-110">
          <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M7 13c1.66 0 3-1.34 3-3S8.66 7 7 7s-3 1.34-3 3 1.34 3 3 3zm12-6h-8v7H3V5H1v15h2v-3h18v3h2v-9c0-2.21-1.79-4-4-4z"/></svg>
        </div>
        <span class="absolute -bottom-5 left-1/2 -translate-x-1/2 bg-slate-900/90 text-white text-[10px] font-bold px-1.5 py-0.5 rounded whitespace-nowrap shadow-sm pointer-events-none">
          Chỗ ở
        </span>
      </div>
    `;
    const stayIcon = L.divIcon({
      className: 'custom-stay-pin',
      html: stayHtml,
      iconSize: [36, 36],
      iconAnchor: [18, 18],
    });

    // Tự động phân tách các marker trùng tọa độ (vd: Chỗ ở và hoạt động cùng địa điểm khi chọn "Tất cả")
    const clusters: MapPoint[][] = [];
    visiblePoints.forEach((p) => {
      let matched = false;
      for (const cluster of clusters) {
        const leader = cluster[0];
        if (Math.abs(leader.lat - p.lat) < 0.00025 && Math.abs(leader.lng - p.lng) < 0.00025) {
          cluster.push(p);
          matched = true;
          break;
        }
      }
      if (!matched) {
        clusters.push([p]);
      }
    });

    clusters.forEach((cluster) => {
      const isMulti = cluster.length > 1;
      const radius = 0.00035; // Bán kính phân tán ~35m tránh đè vạch
      const count = cluster.length;

      cluster.forEach((point, idx) => {
        bounds.extend([point.lat, point.lng]);

        let renderLat = point.lat;
        let renderLng = point.lng;
        if (isMulti) {
          const angle = (2 * Math.PI * idx) / count - Math.PI / 2;
          renderLat += radius * Math.sin(angle);
          renderLng += (radius * Math.cos(angle)) / Math.cos((point.lat * Math.PI) / 180);
        }

        if (point.type === 'stay') {
          L.marker([renderLat, renderLng], { icon: stayIcon })
            .addTo(markersGroup)
            .on('click', () => {
              setSelectedPoint(point);
              map.flyTo([point.lat, point.lng], 15, { duration: 0.8 });
            });
        } else {
          const dayCfg = DAY_COLORS[point.day || 1] || DAY_COLORS[1];
          const timeIcon = point.timeSlot === 'morning' ? '☀' : point.timeSlot === 'noon' ? '🌤' : point.timeSlot === 'afternoon' ? '⛅' : '🌙';
          const pinHtml = `
            <div class="relative group cursor-pointer transform -translate-x-1/2 -translate-y-1/2">
              <div style="background-color: ${dayCfg.hex}; border-color: white;" class="w-8 h-8 rounded-full text-white flex items-center justify-center shadow-md border-2 ring-2 ring-slate-200 transition-transform hover:scale-110">
                <span class="text-xs font-black tracking-tight">${point.orderNumber || timeIcon}</span>
              </div>
            </div>
          `;
          const pinIcon = L.divIcon({
            className: 'custom-slot-pin',
            html: pinHtml,
            iconSize: [32, 32],
            iconAnchor: [16, 16],
          });

          L.marker([renderLat, renderLng], { icon: pinIcon })
            .addTo(markersGroup)
            .on('click', () => {
              setSelectedPoint(point);
              map.flyTo([point.lat, point.lng], 15, { duration: 0.8 });
            });
        }
      });
    });

    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
    }

    const requests = buildRouteRequests(plan, filterDay);
    if (requests.length > 0) {
      setRouteStatus('loading');
      const onRouteResult = (result: RouteResult) => {
        if (cancelled) return;
        setRouteResults((current) => {
          const existingIndex = current.findIndex((item) => item.id === result.id);
          if (existingIndex < 0) return [...current, result];
          const next = [...current];
          next[existingIndex] = result;
          return next;
        });
      };

      void resolveRouteRequests(requests, defaultRouteProvider, onRouteResult).then((results) => {
        if (cancelled) return;
        setRouteStatus(results.some((result) => result.status === 'unavailable') ? 'partial' : 'ready');
      });
    }

    return () => {
      cancelled = true;
    };
  }, [plan, filterDay]);

  // Render only provider-returned geometry. There is deliberately no straight-line fallback.
  useEffect(() => {
    const linesGroup = linesLayerRef.current;
    if (!linesGroup) return;
    linesGroup.clearLayers();

    routeResults.filter((result) => result.status === 'routed').forEach((result) => {
      const transit = getTransitVisual(result.mode);
      const path = result.geometry.map((coordinate) => [coordinate.lat, coordinate.lng] as [number, number]);
      if (path.length < 2) return;

      const segmentLine = L.polyline(path, {
        color: transit.color,
        weight: transit.weight,
        opacity: 0.85,
        dashArray: transit.dashArray,
        lineCap: 'round',
        lineJoin: 'round',
      }).addTo(linesGroup);

      const tooltip = `<div class="text-xs font-sans p-0.5">
        <div class="font-bold text-slate-800 flex items-center gap-1.5">
          <span>${transit.emoji}</span>
          <span>${transit.fullLabel}</span>
        </div>
        <div class="text-[11px] text-slate-600 mt-1">${result.fromTitle} ➔ ${result.toTitle}</div>
        ${result.distanceMeters ? `<div class="text-[10px] text-slate-500 mt-1">${(result.distanceMeters / 1000).toFixed(1)} km · ${Math.round((result.durationSeconds ?? 0) / 60)} phút</div>` : ''}
        ${result.transitInfo ? `<div class="text-[10px] text-blue-600 font-medium mt-1">ℹ️ ${result.transitInfo}</div>` : ''}
      </div>`;
      segmentLine.bindTooltip(tooltip, { sticky: true, opacity: 0.95 });

      const midCoord = result.geometry[Math.floor(result.geometry.length / 2)];
      const transitBadgeIcon = L.divIcon({
        className: 'custom-transit-badge',
        html: `<div class="transit-badge group/transit relative flex items-center gap-1 px-2 py-0.5 rounded-full bg-white text-slate-800 shadow-md border border-slate-200 text-[11px] font-bold cursor-pointer transition-transform hover:scale-115 -translate-x-1/2 -translate-y-1/2">
          <span class="text-xs leading-none">${transit.emoji}</span>
          <span class="text-[9px] font-semibold text-slate-600 hidden sm:inline whitespace-nowrap">${transit.label}</span>
        </div>`,
        iconSize: [40, 24],
        iconAnchor: [20, 12],
      });
      L.marker([midCoord.lat, midCoord.lng], { icon: transitBadgeIcon })
        .addTo(linesGroup)
        .bindTooltip(tooltip, { direction: 'top', offset: [0, -10], opacity: 0.95 });
    });
  }, [routeResults]);

  // Handle FlyTo & Highlight Marker when hovering over itinerary cards
  useEffect(() => {
    const map = mapInstanceRef.current;
    const highlightGroup = highlightLayerRef.current;
    if (!map || !highlightGroup) return;

    highlightGroup.clearLayers();

    if (focusedCoordinate) {
      // 1. Bay mượt mà đến tọa độ của card đang hover
      map.flyTo([focusedCoordinate.lat, focusedCoordinate.lng], 15, {
        duration: 0.6,
        easeLinearity: 0.25
      });

      // 2. Thêm hiệu ứng pulse tỏa sáng (ripple effect) tại vị trí đó
      const pulseHtml = `
        <div class="relative flex items-center justify-center -translate-x-1/2 -translate-y-1/2 pointer-events-none">
          <div class="absolute w-12 h-12 rounded-full bg-blue-500/30 animate-ping"></div>
          <div class="absolute w-8 h-8 rounded-full bg-blue-600/40 animate-pulse"></div>
          <div class="w-4 h-4 rounded-full bg-blue-600 border-2 border-white shadow-lg"></div>
        </div>
      `;

      const pulseIcon = L.divIcon({
        className: 'custom-pulse-marker',
        html: pulseHtml,
        iconSize: [48, 48],
        iconAnchor: [24, 24]
      });

      L.marker([focusedCoordinate.lat, focusedCoordinate.lng], {
        icon: pulseIcon,
        zIndexOffset: 1000
      }).addTo(highlightGroup);
    }
  }, [focusedCoordinate]);

  const getTimeLabel = (time?: string) => {
    switch (time) {
      case 'morning': return '☀ Buổi Sáng';
      case 'noon': return '🌤 Buổi Trưa';
      case 'afternoon': return '⛅ Buổi Chiều';
      case 'evening': return '🌙 Buổi Tối';
      default: return 'Khung giờ';
    }
  };

  const handleFitAll = () => {
    const map = mapInstanceRef.current;
    if (!map) return;
    const allPoints = getAllPoints();
    const visiblePoints = filterDay === 0
      ? allPoints
      : allPoints.filter((point) => point.type === 'stay' || point.day === filterDay);
    const bounds = L.latLngBounds(visiblePoints.map(p => [p.lat, p.lng]));
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
    }
  };

  const pinActions = selectedPoint?.product && itemActions ? itemActions(selectedPoint.product) : null;

  return (
    <div className={`relative flex flex-col h-full bg-slate-50 overflow-hidden ${className}`}>
      {/* Top Map Control Bar */}
      <div className="absolute top-3 left-3 right-3 z-[1000] flex items-center justify-between pointer-events-none">
        {/* Day Filter Chips */}
        <div className="flex items-center gap-1.5 p-1 bg-white/95 backdrop-blur-xs rounded-xl shadow-md border border-slate-200 pointer-events-auto max-w-[calc(100%-4.5rem)] overflow-x-auto no-scrollbar">
          <button
            type="button"
            onClick={() => {
              setFilterDay(0);
              onSelectDay(1);
            }}
            className={`px-3 py-1 text-xs font-bold rounded-lg transition-colors cursor-pointer ${
              filterDay === 0 ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            Tất cả
          </button>
          {plan.days.map(d => (
            <button
              key={d.day}
              type="button"
              onClick={() => {
                setFilterDay(d.day);
                onSelectDay(d.day);
              }}
              className={`px-3 py-1 text-xs font-bold rounded-lg transition-colors flex items-center gap-1.5 cursor-pointer ${
                filterDay === d.day 
                  ? 'bg-blue-600 text-white shadow-2xs' 
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              <span className={`w-2 h-2 rounded-full ${filterDay === d.day ? 'bg-white' : 'bg-blue-500'}`} />
              Ngày {d.day}
            </button>
          ))}
        </div>

        {/* Fit Bounds Button */}
        <button
          type="button"
          onClick={handleFitAll}
          className="px-3 py-1.5 bg-white/95 backdrop-blur-xs hover:bg-white text-slate-700 text-xs font-semibold rounded-xl shadow-md border border-slate-200 transition-colors flex items-center gap-1.5 pointer-events-auto cursor-pointer"
          title="Khớp toàn bộ lộ trình"
        >
          <Compass className="w-3.5 h-3.5 text-blue-600" />
          <span className="hidden sm:inline">Khớp tầm nhìn</span>
        </button>
      </div>

      {/* Map Container */}
      <div ref={mapContainerRef} className="w-full h-full min-h-[350px] z-0" />

      {routeStatus === 'loading' && (
        <div className="absolute top-3 right-3 z-[1000] rounded-xl border border-slate-200 bg-white/95 px-3 py-2 text-[11px] font-semibold text-slate-600 shadow-md">
          Đang tải tuyến đường thực tế từ OSRM…
        </div>
      )}
      {routeStatus === 'partial' && (
        <div className="absolute top-3 right-3 z-[1000] max-w-[220px] rounded-xl border border-amber-200 bg-amber-50/95 px-3 py-2 text-[11px] font-semibold text-amber-800 shadow-md">
          Một số chặng chưa có geometry từ OSRM.
        </div>
      )}

      {/* Map Legend (Bottom-Left) */}
      <div className="absolute bottom-4 left-4 z-[1000] p-2.5 bg-white/95 backdrop-blur-xs rounded-xl shadow-md border border-slate-200 text-[11px] text-slate-600 space-y-1.5 hidden md:block max-w-[210px]">
        <div className="font-bold text-slate-800 flex items-center gap-1">
          <Layers className="w-3 h-3 text-blue-600" />
          <span>Phương tiện & Lộ trình</span>
        </div>
        <div className="grid grid-cols-2 gap-1.5 pt-0.5 text-[10px]">
          <div className="flex items-center gap-1.5">
            <span>🚗</span>
            <span>Ô tô / Taxi</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span>🚤</span>
            <span>Cano / Biển</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span>🚡</span>
            <span>Cáp treo</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span>🚶</span>
            <span>Đi bộ</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span>🚲</span>
            <span>Xe đạp</span>
          </div>
          <div className="flex items-center gap-1.5 col-span-2">
            <span>✈️</span>
            <span>Xe sân bay</span>
          </div>
        </div>
        <div className="pt-1 border-t border-slate-100 flex items-center gap-1.5 text-[10px] text-slate-500">
          <span className="w-2.5 h-2.5 rounded-full bg-indigo-600 inline-block shrink-0"></span>
          <span>Chỗ nghỉ cố định</span>
        </div>
      </div>

      {/* Active Selected Point Detail Card (Bottom or Floating) */}
      {selectedPoint && (
        <div className="absolute bottom-4 right-4 max-w-sm w-full z-[1000] p-4 bg-white rounded-2xl shadow-xl border border-slate-200 animate-in fade-in slide-in-from-bottom-2 duration-200">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                selectedPoint.type === 'stay' ? 'bg-indigo-100 text-indigo-800' : 'bg-blue-100 text-blue-800'
              }`}>
                {selectedPoint.type === 'stay' ? 'Chỗ nghỉ cả chuyến' : `Ngày ${selectedPoint.day} · ${getTimeLabel(selectedPoint.timeSlot)}`}
              </span>
              {selectedPoint.product?.unitPrice && (
                <span className="text-[11px] font-bold text-emerald-700">
                  {new Intl.NumberFormat('vi-VN').format(selectedPoint.product.unitPrice)} ₫
                </span>
              )}
            </div>
            <button
              onClick={() => setSelectedPoint(null)}
              className="text-slate-400 hover:text-slate-600 text-xs p-1"
            >
              ✕
            </button>
          </div>

          <h4 className="font-sans text-xs sm:text-sm font-bold text-slate-900 mt-1.5 line-clamp-2">
            {selectedPoint.title}
          </h4>

          {selectedPoint.address && (
            <p className="text-[11px] text-slate-500 mt-1 flex items-start gap-1">
              <MapPin className="w-3 h-3 text-slate-400 shrink-0 mt-0.5" />
              <span className="line-clamp-1">{selectedPoint.address}</span>
            </p>
          )}

          {selectedPoint.note && (
            <p className="text-[11px] text-slate-600 italic bg-slate-50 p-2 rounded-lg mt-2 border border-slate-100">
              "{selectedPoint.note}"
            </p>
          )}

          {pinActions && (
            <div className="mt-3 flex items-center justify-between gap-2 pt-2 border-t border-slate-100">
              <span className="text-[10px] text-slate-400">Sản phẩm thật trên V-OTA</span>
              <div className="flex items-center gap-1.5 shrink-0">
                {pinActions.canAddToCart && (
                  <button
                    onClick={pinActions.addToCart}
                    className="px-3 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 text-xs font-bold rounded-lg transition-colors flex items-center gap-1"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Thêm vào giỏ</span>
                  </button>
                )}
                <button
                  onClick={pinActions.bookNow}
                  className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-lg shadow-xs transition-colors"
                >
                  Đặt ngay
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
