import React, { useState, useEffect } from 'react';
import { 
  Sun, CloudSun, Cloud, CloudRain, CloudLightning, CloudFog, 
  Droplets, Wind, ThermometerSun, RefreshCw, ChevronDown, ChevronUp, 
  Sparkles, CheckCircle2, ShieldAlert, Luggage
} from 'lucide-react';
import { DestinationWeather, DayForecast, fetchWeatherForecast } from '../../services/weather';

interface WeatherForecastCardProps {
  destination: string;
  className?: string;
  defaultExpanded?: boolean;
}

export const WeatherForecastCard: React.FC<WeatherForecastCardProps> = ({
  destination,
  className = '',
  defaultExpanded = true
}) => {
  const [weatherData, setWeatherData] = useState<DestinationWeather | null>(null);
  const [selectedDayIndex, setSelectedDayIndex] = useState<number>(0);
  const [isExpanded, setIsExpanded] = useState<boolean>(defaultExpanded);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const loadWeather = async (targetDest: string) => {
    setIsLoading(true);
    try {
      const data = await fetchWeatherForecast(targetDest);
      setWeatherData(data);
    } catch (e) {
      console.error('Error fetching weather:', e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (destination) {
      loadWeather(destination);
      setSelectedDayIndex(0);
    }
  }, [destination]);

  if (!weatherData) {
    return null;
  }

  const renderWeatherIcon = (iconType: DayForecast['iconType'], sizeClass = 'w-6 h-6') => {
    switch (iconType) {
      case 'sunny':
        return <Sun className={`${sizeClass} text-amber-500 fill-amber-400/30 animate-pulse`} />;
      case 'partly_cloudy':
        return <CloudSun className={`${sizeClass} text-amber-600`} />;
      case 'cloudy':
        return <Cloud className={`${sizeClass} text-slate-500`} />;
      case 'rainy':
        return <CloudRain className={`${sizeClass} text-blue-500`} />;
      case 'storm':
        return <CloudLightning className={`${sizeClass} text-purple-600`} />;
      case 'fog':
        return <CloudFog className={`${sizeClass} text-slate-400`} />;
      default:
        return <Sun className={`${sizeClass} text-amber-500`} />;
    }
  };

  const selectedDay = weatherData.days[selectedDayIndex] || weatherData.days[0];

  return (
    <div className={`bg-gradient-to-br from-blue-50/90 via-sky-50/60 to-white rounded-2xl border border-sky-200/80 shadow-2xs overflow-hidden transition-all ${className}`}>
      {/* Header Bar */}
      <div className="p-3.5 sm:p-4 flex items-center justify-between gap-3 border-b border-sky-100/80 bg-white/70 backdrop-blur-xs">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-9 h-9 rounded-xl bg-amber-100/90 text-amber-600 flex items-center justify-center shrink-0 shadow-2xs border border-amber-200/60">
            {renderWeatherIcon(weatherData.days[0]?.iconType || 'sunny', 'w-5 h-5')}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-bold uppercase tracking-wider text-sky-800 flex items-center gap-1">
                <ThermometerSun className="w-3.5 h-3.5 text-sky-600" />
                Dự báo thời tiết 5 ngày
              </span>
              <span className="px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 text-[11px] font-bold">
                {destination}
              </span>
              {weatherData.source === 'live' && (
                <span className="hidden sm:inline-flex items-center gap-1 px-1.5 py-0.2 bg-emerald-100 text-emerald-700 text-[10px] font-semibold rounded-md">
                  <CheckCircle2 className="w-3 h-3" /> Trực tiếp
                </span>
              )}
            </div>
            <p className="text-xs text-slate-600 font-medium truncate mt-0.5">
              {weatherData.currentTemp}°C · {weatherData.currentCondition}
              <span className="text-slate-400 text-[11px] ml-1.5 hidden md:inline">
                (Cập nhật lúc {weatherData.lastUpdated})
              </span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          <button
            onClick={() => loadWeather(destination)}
            disabled={isLoading}
            className="p-1.5 text-slate-500 hover:text-blue-600 hover:bg-sky-100/80 rounded-lg transition-colors disabled:opacity-50"
            title="Làm mới dự báo"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-blue-600' : ''}`} />
          </button>
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="px-2.5 py-1.5 text-xs font-semibold text-sky-700 hover:bg-sky-100/80 rounded-lg transition-colors flex items-center gap-1"
          >
            <span>{isExpanded ? 'Thu gọn' : 'Xem 5 ngày'}</span>
            {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {/* Expanded Forecast Details */}
      {isExpanded && (
        <div className="p-3.5 sm:p-4 space-y-3.5">
          {/* Destination Weather Summary */}
          <div className="text-xs text-slate-600 bg-white/80 p-2.5 rounded-xl border border-sky-100 flex items-start gap-2">
            <Sparkles className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-slate-800">{weatherData.summary}</p>
              <p className="text-[11px] text-slate-500 mt-0.5">
                <span className="font-semibold text-sky-800">Hoạt động lý tưởng:</span> {weatherData.bestFor}
              </p>
            </div>
          </div>

          {/* 5-Day Horizontal Grid */}
          <div className="grid grid-cols-5 gap-1.5 sm:gap-2 overflow-x-auto pb-1">
            {weatherData.days.map((day, idx) => {
              const isSelected = idx === selectedDayIndex;

              return (
                <button
                  key={day.date}
                  onClick={() => setSelectedDayIndex(idx)}
                  className={`p-2 sm:p-2.5 rounded-xl text-center flex flex-col items-center justify-between gap-1.5 transition-all border ${
                    isSelected
                      ? 'bg-blue-600 text-white border-blue-600 shadow-xs ring-2 ring-blue-300/60'
                      : 'bg-white/90 hover:bg-white text-slate-700 border-sky-100 hover:border-sky-300'
                  }`}
                >
                  <div className="text-[11px] font-bold leading-tight">
                    <div className={`${isSelected ? 'text-white' : 'text-slate-900'} truncate`}>
                      {day.dayName}
                    </div>
                    <div className={`text-[10px] font-medium ${isSelected ? 'text-blue-100' : 'text-slate-400'}`}>
                      {day.date}
                    </div>
                  </div>

                  <div className="py-1">
                    {renderWeatherIcon(day.iconType, 'w-6 h-6')}
                  </div>

                  <div className="text-[11px] font-bold leading-none">
                    <span className={isSelected ? 'text-white' : 'text-slate-900'}>
                      {day.tempMax}°
                    </span>
                    <span className={`text-[10px] ml-1 font-medium ${isSelected ? 'text-blue-200' : 'text-slate-400'}`}>
                      {day.tempMin}°
                    </span>
                  </div>

                  <div className={`text-[10px] flex items-center gap-0.5 font-semibold ${
                    isSelected ? 'text-blue-100' : day.precipitationProb > 30 ? 'text-blue-600' : 'text-slate-400'
                  }`}>
                    <Droplets className="w-2.5 h-2.5" />
                    <span>{day.precipitationProb}%</span>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Selected Day In-Depth Details Banner */}
          {selectedDay && (
            <div className="p-3 bg-white rounded-xl border border-sky-100 space-y-2.5">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-2">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-xs text-slate-800">
                    Chi tiết {selectedDay.dayName} ({selectedDay.date}):
                  </span>
                  <span className="text-xs text-blue-700 font-semibold">
                    {selectedDay.condition}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-[11px] text-slate-600">
                  <span className="flex items-center gap-1">
                    <Wind className="w-3.5 h-3.5 text-sky-500" /> Gió {selectedDay.windSpeed} km/h
                  </span>
                  <span className="flex items-center gap-1">
                    <Droplets className="w-3.5 h-3.5 text-blue-500" /> Độ ẩm {selectedDay.humidity}%
                  </span>
                  <span className={`flex items-center gap-1 font-semibold ${selectedDay.uvIndex >= 8 ? 'text-amber-700' : 'text-emerald-700'}`}>
                    <ShieldAlert className="w-3.5 h-3.5" /> UV {selectedDay.uvIndex} ({selectedDay.uvLevel})
                  </span>
                </div>
              </div>

              {/* Day Tip & Packing recommendations */}
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2.5 text-xs">
                <div className="text-slate-700 flex items-start gap-1.5">
                  <span className="text-amber-600 font-bold shrink-0">Gợi ý lịch trình:</span>
                  <span>{selectedDay.activityTip}</span>
                </div>

                {weatherData.packingTips.length > 0 && (
                  <div className="flex items-center gap-1.5 flex-wrap shrink-0">
                    <span className="text-[11px] text-slate-400 flex items-center gap-1">
                      <Luggage className="w-3 h-3 text-slate-400" /> Đồ nên mang:
                    </span>
                    {weatherData.packingTips.map((tip, tIdx) => (
                      <span key={tIdx} className="px-2 py-0.5 bg-slate-100 text-slate-700 text-[10px] font-medium rounded-md border border-slate-200">
                        {tip}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
