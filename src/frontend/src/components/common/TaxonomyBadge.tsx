import React from 'react';
import { Taxonomy } from '../../types/travel';
import { Building2, Plane, Ticket, Sparkles, Flag, MapPin } from 'lucide-react';

interface TaxonomyBadgeProps {
  taxonomy: Taxonomy;
  size?: 'sm' | 'md';
  className?: string;
  /** Điểm tham quan tự do (biển, cầu, phố đi bộ): ghi "Điểm tham quan", không gọi là vé. */
  freeToVisit?: boolean;
}

export const TaxonomyBadge: React.FC<TaxonomyBadgeProps> = ({ taxonomy, size = 'sm', className = '', freeToVisit = false }) => {
  const configs: Record<Taxonomy, { label: string; icon: React.ReactNode; bg: string; text: string; border: string }> = {
    hotel: {
      label: 'Khách sạn',
      icon: <Building2 className={size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5'} />,
      bg: 'bg-brand-50',
      text: 'text-brand-700',
      border: 'border-brand-200'
    },
    flight: {
      label: 'Vé máy bay',
      icon: <Plane className={size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5'} />,
      bg: 'bg-brand-50',
      text: 'text-brand-700',
      border: 'border-brand-200'
    },
    attraction: {
      label: 'Vé tham quan',
      icon: <Ticket className={size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5'} />,
      bg: 'bg-amber-50',
      text: 'text-amber-800',
      border: 'border-amber-200'
    },
    combo: {
      label: 'Combo',
      icon: <Sparkles className={size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5'} />,
      bg: 'bg-emerald-50',
      text: 'text-emerald-700',
      border: 'border-emerald-200'
    },
    golf: {
      label: 'Golf',
      icon: <Flag className={size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5'} />,
      bg: 'bg-teal-50',
      text: 'text-teal-700',
      border: 'border-teal-200'
    }
  };

  const c = freeToVisit && taxonomy === 'attraction'
    ? { label: 'Điểm tham quan', icon: <MapPin className={size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5'} />,
        bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' }
    : configs[taxonomy] || configs.hotel;
  const padding = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs';

  return (
    <span 
      className={`inline-flex items-center gap-1 font-medium rounded border ${c.bg} ${c.text} ${c.border} ${padding} whitespace-nowrap ${className}`}
    >
      {c.icon}
      <span>{c.label}</span>
    </span>
  );
};
