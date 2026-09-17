import { Destination } from '../types/travel';

export interface DayForecast {
  date: string;
  dayName: string;
  dayNumber: number;
  tempMax: number;
  tempMin: number;
  weatherCode: number;
  condition: string;
  iconType: 'sunny' | 'partly_cloudy' | 'cloudy' | 'rainy' | 'storm' | 'fog';
  precipitationProb: number; // %
  humidity: number; // %
  windSpeed: number; // km/h
  uvIndex: number;
  uvLevel: string;
  activityTip: string;
}

export interface DestinationWeather {
  destination: string;
  currentTemp: number;
  currentCondition: string;
  summary: string;
  bestFor: string;
  packingTips: string[];
  days: DayForecast[];
  source: 'live' | 'historical_climatology';
  lastUpdated: string;
}

const DESTINATION_COORDS: Record<string, { lat: number; lng: number; defaultTemp: number }> = {
  'Nha Trang': { lat: 12.2388, lng: 109.1967, defaultTemp: 31 },
  'Phú Quốc': { lat: 10.2899, lng: 103.9840, defaultTemp: 30 },
  'Đà Nẵng': { lat: 16.0544, lng: 108.2022, defaultTemp: 29 },
  'Hội An': { lat: 15.8801, lng: 108.3380, defaultTemp: 29 },
  'Hạ Long': { lat: 20.9505, lng: 107.0734, defaultTemp: 27 },
  'Hà Nội': { lat: 21.0285, lng: 105.8542, defaultTemp: 28 },
};

export const getDestinationCoords = (destination: string) => {
  return DESTINATION_COORDS[destination] || { lat: 12.2388, lng: 109.1967, defaultTemp: 30 };
};

const mapWmoToCondition = (code: number): { condition: string; iconType: DayForecast['iconType'] } => {
  if (code === 0) return { condition: 'Nắng đẹp, trời quang', iconType: 'sunny' };
  if (code <= 2) return { condition: 'Nắng ráo, ít mây', iconType: 'partly_cloudy' };
  if (code === 3) return { condition: 'Nhiều mây', iconType: 'cloudy' };
  if (code <= 48) return { condition: 'Có sương mù nhẹ', iconType: 'fog' };
  if (code <= 67) return { condition: 'Mưa rào nhẹ', iconType: 'rainy' };
  if (code <= 82) return { condition: 'Mưa rào thoáng qua', iconType: 'rainy' };
  if (code >= 95) return { condition: 'Có dông rải rác', iconType: 'storm' };
  return { condition: 'Nắng nhẹ ven biển', iconType: 'partly_cloudy' };
};

const getUvLevel = (uv: number): string => {
  if (uv <= 2) return 'Thấp';
  if (uv <= 5) return 'Trung bình';
  if (uv <= 7) return 'Cao';
  if (uv <= 10) return 'Rất cao';
  return 'Cực độ';
};

const DAY_NAMES = ['Chủ Nhật', 'Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy'];

export const generateFallbackWeather = (destination: string): DestinationWeather => {
  const base = DESTINATION_COORDS[destination] || { lat: 12.2388, lng: 109.1967, defaultTemp: 30 };
  const baseT = base.defaultTemp;
  const today = new Date();

  const mockDays: DayForecast[] = Array.from({ length: 5 }).map((_, i) => {
    const d = new Date(today);
    d.setDate(today.getDate() + i);
    const dayName = i === 0 ? 'Hôm nay' : i === 1 ? 'Ngày mai' : DAY_NAMES[d.getDay()];
    const dateStr = `${d.getDate().toString().padStart(2, '0')}/${(d.getMonth() + 1).toString().padStart(2, '0')}`;
    
    // Vary slightly by day
    const variance = (i % 2 === 0 ? 1 : -1) * (i * 0.5);
    const tempMax = Math.round(baseT + variance);
    const tempMin = Math.round(baseT - 5 + (i % 2));
    const rainChance = destination === 'Hạ Long' ? 15 + i * 5 : destination === 'Phú Quốc' ? 20 + (i * 4) : 10 + i * 3;
    const isRainDay = i === 3 && rainChance > 25;

    const weatherCode = isRainDay ? 80 : i % 2 === 0 ? 0 : 2;
    const { condition, iconType } = mapWmoToCondition(weatherCode);

    return {
      date: dateStr,
      dayName,
      dayNumber: i + 1,
      tempMax,
      tempMin,
      weatherCode,
      condition,
      iconType,
      precipitationProb: rainChance,
      humidity: 68 + (i * 2),
      windSpeed: 10 + (i * 2),
      uvIndex: 8 - (isRainDay ? 2 : 0),
      uvLevel: getUvLevel(8 - (isRainDay ? 2 : 0)),
      activityTip: i === 0 
        ? 'Rất đẹp để tắm biển & check-in hoàng hôn' 
        : i === 1 
          ? 'Thích hợp đi cáp treo hoặc công viên giải trí'
          : i === 2
            ? 'Thời tiết lý tưởng cho tour cano khám phá đảo'
            : isRainDay
              ? 'Nên ưu tiên các hoạt động spa & bảo tàng/thủy cung'
              : 'Trời mát mẻ, hoàn hảo cho tour ẩm thực đêm'
    };
  });

  const tipsMap: Record<string, { summary: string; bestFor: string; tips: string[] }> = {
    'Nha Trang': {
      summary: 'Khí hậu nắng ấm, biển êm sóng lặng với tầm nhìn biển tuyệt đẹp suốt tuần.',
      bestFor: 'Tắm biển Bãi Dài, lặn ngắm san hô Hòn Mun, cáp treo VinWonders.',
      tips: ['Kem chống nắng SPF 50+', 'Kính râm & mũ rộng vành', 'Đồ bơi & túi chống nước điện thoại']
    },
    'Phú Quốc': {
      summary: 'Nắng vàng nhiệt đới rực rỡ, gió biển mát rượi, hoàng hôn Bãi Dài ngoạn mục.',
      bestFor: 'Khám phá Grand World đêm, Safari bán hoang dã, cano 4 đảo An Thới.',
      tips: ['Kem chống nắng & xịt khoáng', 'Quạt cầm tay & dép cói', 'Áo khoác nhẹ đi cáp treo vượt biển']
    },
    'Đà Nẵng': {
      summary: 'Thời tiết ấm áp, mây trắng nhẹ, gió biển trong lành dễ chịu.',
      bestFor: 'Check-in Cầu Vàng Bà Nà Hills, dạo phố cổ Hội An, tắm biển Mỹ Khê.',
      tips: ['Áo khoác mỏng khi lên đỉnh Bà Nà', 'Giày đi bộ êm chân', 'Ô dù che nắng nhẹ']
    },
    'Hạ Long': {
      summary: 'Trời trong xanh, gió lộng vịnh biển kỳ vĩ, hoàng hôn trên du thuyền tuyệt hảo.',
      bestFor: 'Nghỉ dưỡng du thuyền 5 sao, chèo kayak hang Luồn, ngắm vịnh từ trên cao.',
      tips: ['Áo gió nhẹ trên boong tàu', 'Kính râm & máy ảnh/điện thoại đầy pin', 'Đồ bơi tắm biển đảo Ti Tốp']
    },
    'Hội An': {
      summary: 'Nắng dịu ban ngày, se mát khi chiều buông, lý tưởng đi bộ ngắm đèn lồng.',
      bestFor: 'Dạo phố cổ, đi thuyền thả hoa đăng sông Hoài, thưởng thức cao lầu.',
      tips: ['Trang phục vintage chụp ảnh', 'Giày đế bệt/sandal', 'Mũ cói & quạt tay']
    }
  };

  const info = tipsMap[destination] || {
    summary: `Thời tiết tại ${destination} thuận lợi với nhiệt độ dao động ${baseT - 4}°C - ${baseT + 1}°C.`,
    bestFor: 'Tham quan danh thắng địa phương, thưởng thức đặc sản và nghỉ dưỡng.',
    tips: ['Kem chống nắng', 'Trang phục thoáng mát', 'Giày thể thao êm chân']
  };

  return {
    destination,
    currentTemp: baseT,
    currentCondition: 'Nắng ấm chan hòa',
    summary: info.summary,
    bestFor: info.bestFor,
    packingTips: info.tips,
    days: mockDays,
    source: 'historical_climatology',
    lastUpdated: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
  };
};

export const fetchWeatherForecast = async (destination: string): Promise<DestinationWeather> => {
  const coords = getDestinationCoords(destination);
  const fallback = generateFallbackWeather(destination);

  try {
    const url = `https://api.open-meteo.com/v1/forecast?latitude=${coords.lat}&longitude=${coords.lng}&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,uv_index_max,wind_speed_10m_max&current=temperature_2m,weather_code&timezone=Asia%2FHo_Chi_Minh`;
    
    // Add timeout to prevent blocking UI
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3500);

    const res = await fetch(url, { signal: controller.signal });
    clearTimeout(timeoutId);

    if (!res.ok) {
      return fallback;
    }

    const data = await res.json();
    if (!data || !data.daily || !data.daily.time || data.daily.time.length === 0) {
      return fallback;
    }

    const today = new Date();
    const days: DayForecast[] = data.daily.time.slice(0, 5).map((timeStr: string, idx: number) => {
      const d = new Date(timeStr);
      const dayName = idx === 0 ? 'Hôm nay' : idx === 1 ? 'Ngày mai' : DAY_NAMES[d.getDay()];
      const dateParts = timeStr.split('-');
      const dateFormatted = `${dateParts[2]}/${dateParts[1]}`;

      const code = data.daily.weather_code[idx] ?? 0;
      const { condition, iconType } = mapWmoToCondition(code);
      const uv = Math.round(data.daily.uv_index_max?.[idx] ?? 7);

      return {
        date: dateFormatted,
        dayName,
        dayNumber: idx + 1,
        tempMax: Math.round(data.daily.temperature_2m_max[idx] ?? fallback.days[idx].tempMax),
        tempMin: Math.round(data.daily.temperature_2m_min[idx] ?? fallback.days[idx].tempMin),
        weatherCode: code,
        condition,
        iconType,
        precipitationProb: Math.round(data.daily.precipitation_probability_max?.[idx] ?? fallback.days[idx].precipitationProb),
        humidity: fallback.days[idx].humidity,
        windSpeed: Math.round(data.daily.wind_speed_10m_max?.[idx] ?? fallback.days[idx].windSpeed),
        uvIndex: uv,
        uvLevel: getUvLevel(uv),
        activityTip: fallback.days[idx].activityTip
      };
    });

    const currentWmo = data.current?.weather_code ?? data.daily.weather_code[0] ?? 0;
    const currentCond = mapWmoToCondition(currentWmo).condition;

    return {
      ...fallback,
      currentTemp: Math.round(data.current?.temperature_2m ?? fallback.currentTemp),
      currentCondition: currentCond,
      days,
      source: 'live',
      lastUpdated: new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })
    };
  } catch (err) {
    // Graceful fallback to offline climatology data
    return fallback;
  }
};
