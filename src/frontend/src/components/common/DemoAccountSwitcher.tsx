import React from 'react';
import { useTravel } from '../../context/TravelContext';
import { SEED_PERSONAS } from '../../data/personas';
import { Check } from 'lucide-react';

interface DemoAccountSwitcherProps {
  compact?: boolean;
  onSelect?: () => void;
  className?: string;
}

export const DemoAccountSwitcher: React.FC<DemoAccountSwitcherProps> = ({
  compact = false,
  onSelect,
  className = ''
}) => {
  const { currentPersona, switchPersona } = useTravel();

  const handleSwitch = async (personaId: string) => {
    try {
      await switchPersona(personaId);
      if (onSelect) onSelect();
    } catch {
      // switchPersona đã hiện toast lỗi; giữ modal mở để chọn lại.
    }
  };

  const personas = [
    {
      id: 'P1',
      persona: SEED_PERSONAS.P1,
      accent: 'border-blue-300 bg-blue-50/50 hover:bg-blue-50',
      tagColor: 'bg-blue-100 text-blue-800'
    },
    {
      id: 'P2',
      persona: SEED_PERSONAS.P2,
      accent: 'border-amber-300 bg-amber-50/50 hover:bg-amber-50',
      tagColor: 'bg-amber-100 text-amber-800'
    },
    {
      id: 'P3',
      persona: SEED_PERSONAS.P3,
      accent: 'border-purple-300 bg-purple-50/50 hover:bg-purple-50',
      tagColor: 'bg-purple-100 text-purple-800'
    },
    {
      id: 'P4',
      persona: SEED_PERSONAS.P4,
      accent: 'border-slate-300 bg-slate-50/70 hover:bg-slate-100/70',
      tagColor: 'bg-slate-200 text-slate-800'
    }
  ];

  if (compact) {
    return (
      <div className={`grid grid-cols-2 gap-2 ${className}`}>
        {personas.map(({ id, persona, tagColor }) => {
          const isSelected = currentPersona?.id === id;
          return (
            <button
              key={id}
              onClick={() => handleSwitch(id)}
              className={`flex items-center gap-2 p-2 rounded-lg border text-left transition-all ${isSelected ? 'border-blue-600 bg-blue-50 ring-1 ring-blue-500' : 'border-slate-200 bg-white hover:border-slate-300'}`}
            >
              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${tagColor}`}>
                {persona.code}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-800 truncate">{persona.name}</span>
                  {isSelected && <Check className="w-3.5 h-3.5 text-blue-600 shrink-0" />}
                </div>
                <p className="text-[10px] text-slate-500 truncate">{persona.tagline}</p>
              </div>
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <div className={`space-y-3 ${className}`}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-bold tracking-wider text-slate-500 uppercase">
          Chọn hồ sơ du khách trải nghiệm
        </span>
        <span className="text-[11px] text-slate-400 font-normal">
          Gợi ý cá nhân hóa thông minh
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {personas.map(({ id, persona, accent, tagColor }) => {
          const isSelected = currentPersona?.id === id;
          return (
            <div
              key={id}
              onClick={() => handleSwitch(id)}
              className={`relative p-3.5 rounded-xl border transition-all cursor-pointer flex flex-col justify-between ${isSelected ? 'border-blue-600 bg-blue-50/70 ring-2 ring-blue-500/20 shadow-xs' : `${accent} border-slate-200`}`}
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className={`inline-flex items-center justify-center w-8 h-8 rounded-full text-xs font-bold ${tagColor}`}>
                    {persona.code}
                  </span>
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-white/90 border border-slate-200 text-slate-600">
                    {persona.tagline}
                  </span>
                </div>
                <h4 className="text-sm font-bold text-slate-900 line-clamp-1">
                  {persona.name}
                </h4>
                <p className="text-xs text-slate-600 mt-1 line-clamp-2 leading-relaxed">
                  {persona.historySummary}
                </p>
              </div>

              <div className="mt-3 pt-2.5 border-t border-slate-200/60 flex items-center justify-between text-[11px]">
                <span className="text-slate-400 font-mono">{id}</span>
                {isSelected ? (
                  <span className="font-semibold text-blue-700 flex items-center gap-1">
                    <Check className="w-3.5 h-3.5" />
                    Đang chọn
                  </span>
                ) : (
                  <span className="text-slate-500 hover:text-blue-600 font-medium">
                    Chuyển sang →
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
