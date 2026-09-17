import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { GroundedPlan, Product, ItinerarySlot } from '../../types/travel';
import { MapPin, Navigation, Compass, Layers, ShoppingBag, Plus, Info, Home, Sun, CloudSun, Sunset, Moon } from 'lucide-react';

interface ItineraryMapProps {
  plan: GroundedPlan;
  activeDay: number;
  onSelectDay: (day: number) => void;
  onAddToCart?: (product: Product) => void;
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
  onAddToCart,
  className = ''
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersLayerRef = useRef<L.LayerGroup | null>(null);
  const linesLayerRef = useRef<L.LayerGroup | null>(null);
  const [selectedPoint, setSelectedPoint] = useState<MapPoint | null>(null);
  const [filterDay, setFilterDay] = useState<number>(activeDay);

  // Sync internal filterDay with parent activeDay
  useEffect(() => {
    setFilterDay(activeDay);
  }, [activeDay]);

  // Extract all geocoded points from the plan
  const getAllPoints = (): MapPoint[] => {
    const points: MapPoint[] = [];

    // Stay point
    if (plan.stay?.product.coordinates) {
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
    plan.days.forEach(day => {
      let order = 1;
      day.slots.forEach(slot => {
        const coord = slot.coordinates || slot.product?.coordinates;
        if (coord) {
          points.push({
            id: `day-${day.day}-slot-${slot.time}-${order}`,
            lat: coord.lat,
            lng: coord.lng,
            title: slot.product?.name || slot.activityTitle || 'Điểm tham quan',
            type: 'slot',
            day: day.day,
            timeSlot: slot.time,
            product: slot.product,
            address: slot.address || slot.product?.address,
            note: slot.note,
            orderNumber: order++
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
    });

    // Add clean CartoDB / OSM tiles
    L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
      maxZoom: 19,
      subdomains: 'abcd',
    }).addTo(map);

    // Custom Zoom controls at top right
    L.control.zoom({ position: 'topright' }).addTo(map);

    const markersGroup = L.layerGroup().addTo(map);
    const linesGroup = L.layerGroup().addTo(map);

    markersLayerRef.current = markersGroup;
    linesLayerRef.current = linesGroup;
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

  // Update Markers & Polylines when plan or filterDay changes
  useEffect(() => {
    const map = mapInstanceRef.current;
    const markersGroup = markersLayerRef.current;
    const linesGroup = linesLayerRef.current;
    if (!map || !markersGroup || !linesGroup) return;

    markersGroup.clearLayers();
    linesGroup.clearLayers();

    const allPoints = getAllPoints();
    const visiblePoints = filterDay === 0 
      ? allPoints 
      : allPoints.filter(p => p.type === 'stay' || p.day === filterDay);

    if (visiblePoints.length === 0) return;

    const bounds = L.latLngBounds([]);

    // Plot Hotel / Stay Marker
    const stayPoint = allPoints.find(p => p.type === 'stay');
    if (stayPoint) {
      bounds.extend([stayPoint.lat, stayPoint.lng]);

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

      const stayMarker = L.marker([stayPoint.lat, stayPoint.lng], { icon: stayIcon })
        .addTo(markersGroup)
        .on('click', () => {
          setSelectedPoint(stayPoint);
          map.flyTo([stayPoint.lat, stayPoint.lng], 14, { duration: 0.8 });
        });
    }

    // Plot Day Slots Markers
    const slotsPoints = visiblePoints.filter(p => p.type === 'slot');

    slotsPoints.forEach((point) => {
      bounds.extend([point.lat, point.lng]);

      const dayCfg = DAY_COLORS[point.day || 1] || DAY_COLORS[1];
      const timeIcon = point.timeSlot === 'morning' ? '☀' : point.timeSlot === 'noon' ? '🌤' : point.timeSlot === 'afternoon' ? '⛅' : '🌙';

      const pinHtml = `
        <div class="relative group cursor-pointer transform -translate-x-1/2 -translate-y-1/2">
          <div style="background-color: ${dayCfg.hex}; border-color: white;" class="w-8 h-8 rounded-full text-white flex items-center justify-center shadow-md border-2 ring-2 ring-slate-200 transition-transform hover:scale-110">
            <span class="text-xs font-black tracking-tight">${point.orderNumber || timeIcon}</span>
          </div>
          <span style="background-color: ${dayCfg.hex};" class="absolute -top-3 -right-2 text-[9px] font-extrabold text-white px-1 rounded-full shadow-2xs border border-white">
            N${point.day}
          </span>
        </div>
      `;

      const pinIcon = L.divIcon({
        className: 'custom-slot-pin',
        html: pinHtml,
        iconSize: [32, 32],
        iconAnchor: [16, 16],
      });

      L.marker([point.lat, point.lng], { icon: pinIcon })
        .addTo(markersGroup)
        .on('click', () => {
          setSelectedPoint(point);
          map.flyTo([point.lat, point.lng], 14, { duration: 0.8 });
        });
    });

    // Draw connecting routes per day
    const daysToDraw = filterDay === 0 ? plan.days.map(d => d.day) : [filterDay];

    daysToDraw.forEach(d => {
      const daySlots = allPoints.filter(p => p.type === 'slot' && p.day === d);
      if (daySlots.length === 0) return;

      const dayCfg = DAY_COLORS[d] || DAY_COLORS[1];
      const routeCoords: [number, number][] = [];

      // Start from hotel if exists
      if (stayPoint) {
        routeCoords.push([stayPoint.lat, stayPoint.lng]);
      }

      // Add slots in order
      daySlots.forEach(s => {
        routeCoords.push([s.lat, s.lng]);
      });

      // Loop back to hotel in the evening
      if (stayPoint) {
        routeCoords.push([stayPoint.lat, stayPoint.lng]);
      }

      if (routeCoords.length >= 2) {
        L.polyline(routeCoords, {
          color: dayCfg.hex,
          weight: 3.5,
          opacity: 0.8,
          dashArray: '6, 8',
          lineCap: 'round',
          lineJoin: 'round',
        }).addTo(linesGroup);
      }
    });

    // Fit map bounds
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
    }
  }, [plan, filterDay]);

  const handleFitAll = () => {
    const map = mapInstanceRef.current;
    if (!map) return;
    const points = getAllPoints();
    const bounds = L.latLngBounds(points.map(p => [p.lat, p.lng]));
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
    }
  };

  const getTimeLabel = (time?: string) => {
    switch (time) {
      case 'morning': return '☀ Buổi Sáng';
      case 'noon': return '🌤 Buổi Trưa';
      case 'afternoon': return '⛅ Buổi Chiều';
      case 'evening': return '🌙 Buổi Tối';
      default: return 'Khung giờ';
    }
  };

  return (
    <div className={`relative flex flex-col h-full bg-slate-50 overflow-hidden ${className}`}>
      {/* Top Map Control Bar */}
      <div className="absolute top-3 left-3 right-3 z-[1000] flex flex-wrap items-center justify-between gap-2 pointer-events-none">
        {/* Day Filter Chips */}
        <div className="flex items-center gap-1.5 p-1 bg-white/95 backdrop-blur-xs rounded-xl shadow-md border border-slate-200 pointer-events-auto">
          <button
            onClick={() => {
              setFilterDay(0);
              onSelectDay(1);
            }}
            className={`px-3 py-1 text-xs font-bold rounded-lg transition-colors ${
              filterDay === 0 ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            Tất cả
          </button>
          {plan.days.map(d => (
            <button
              key={d.day}
              onClick={() => {
                setFilterDay(d.day);
                onSelectDay(d.day);
              }}
              className={`px-3 py-1 text-xs font-bold rounded-lg transition-colors flex items-center gap-1.5 ${
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
          onClick={handleFitAll}
          className="px-3 py-1.5 bg-white/95 backdrop-blur-xs hover:bg-white text-slate-700 text-xs font-semibold rounded-xl shadow-md border border-slate-200 transition-colors flex items-center gap-1.5 pointer-events-auto"
          title="Khớp toàn bộ lộ trình"
        >
          <Compass className="w-3.5 h-3.5 text-blue-600" />
          <span className="hidden sm:inline">Khớp tầm nhìn</span>
        </button>
      </div>

      {/* Map Container */}
      <div ref={mapContainerRef} className="w-full h-full min-h-[350px] z-0" />

      {/* Map Legend (Bottom-Left) */}
      <div className="absolute bottom-4 left-4 z-[1000] p-2.5 bg-white/95 backdrop-blur-xs rounded-xl shadow-md border border-slate-200 text-[11px] text-slate-600 space-y-1.5 hidden md:block">
        <div className="font-bold text-slate-800 flex items-center gap-1">
          <Layers className="w-3 h-3 text-blue-600" />
          <span>Chú giải lộ trình</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-indigo-600 inline-block"></span>
          <span>Khách sạn (Chỗ ở cố định)</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-blue-600 inline-block"></span>
          <span>Điểm dừng theo ngày (1, 2, 3...)</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-4 h-0.5 border-b-2 border-dashed border-blue-600 inline-block"></span>
          <span>Đường di chuyển gợi ý</span>
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

          <h4 className="text-xs sm:text-sm font-bold text-slate-900 mt-1.5 line-clamp-2">
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

          {selectedPoint.product && onAddToCart && (
            <div className="mt-3 flex items-center justify-between gap-2 pt-2 border-t border-slate-100">
              <span className="text-[10px] text-slate-400">Sản phẩm thật trên V-OTA</span>
              <button
                onClick={() => {
                  if (selectedPoint.product) {
                    onAddToCart(selectedPoint.product);
                  }
                }}
                className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-lg shadow-xs transition-colors flex items-center gap-1 shrink-0"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Thêm vào giỏ</span>
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
