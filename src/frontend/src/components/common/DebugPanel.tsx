import React, { useState } from 'react';
import { useTravel } from '../../context/TravelContext';
import { Bug, X, ChevronUp, ChevronDown } from 'lucide-react';
import { calculateRecommendations } from '../../services/recsys';

export const DebugPanel: React.FC = () => {
  const { debugMode, toggleDebugMode, currentPersona, activeEvents, cart, bookings } = useTravel();
  const [isExpanded, setIsExpanded] = useState(false);

  if (!debugMode) {
    return (
      <button
        onClick={toggleDebugMode}
        title="Bật chế độ chẩn đoán (Shift + D)"
        className="fixed bottom-4 left-4 z-40 px-2.5 py-1 text-[11px] font-mono font-bold bg-slate-800/80 hover:bg-slate-900 text-slate-300 rounded-full border border-slate-700 shadow-lg backdrop-blur-xs flex items-center gap-1.5 transition-all"
      >
        <Bug className="w-3.5 h-3.5 text-amber-400" />
        <span>DEBUG (Shift+D)</span>
      </button>
    );
  }

  const recs = calculateRecommendations(currentPersona, activeEvents);

  return (
    <div className="fixed bottom-4 left-4 z-50 max-w-sm w-full bg-slate-900 text-slate-200 rounded-xl shadow-2xl border border-slate-700 overflow-hidden font-mono text-xs">
      <div 
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center justify-between px-3.5 py-2.5 bg-slate-800 cursor-pointer select-none"
      >
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span className="font-bold text-amber-300">DIAGNOSTICS / CHẨN ĐOÁN</span>
        </div>
        <div className="flex items-center gap-2">
          {isExpanded ? <ChevronDown className="w-4 h-4 text-slate-400" /> : <ChevronUp className="w-4 h-4 text-slate-400" />}
          <button
            onClick={(e) => {
              e.stopPropagation();
              toggleDebugMode();
            }}
            className="p-0.5 hover:text-white"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {isExpanded && (
        <div className="p-3.5 space-y-3 max-h-96 overflow-y-auto">
          <div className="space-y-1">
            <div className="text-slate-400 text-[10px] uppercase tracking-wider font-semibold">User Context</div>
            <div className="bg-slate-800/60 p-2 rounded text-[11px] space-y-0.5">
              <div>Persona: <span className="text-emerald-400 font-bold">{currentPersona ? `${currentPersona.id} (${currentPersona.name})` : 'Guest'}</span></div>
              <div>ColdStart: <span className="text-blue-300">{recs.diagnostics.coldStart ? 'true' : 'false'}</span></div>
              <div>Events count: <span className="text-amber-300">{recs.diagnostics.eventsUsed}</span></div>
              <div>Cart items: <span className="text-slate-300">{cart.length}</span></div>
              <div>Completed Bookings: <span className="text-slate-300">{bookings.length}</span></div>
            </div>
          </div>

          <div className="space-y-1">
            <div className="text-slate-400 text-[10px] uppercase tracking-wider font-semibold">RecSys State</div>
            <div className="bg-slate-800/60 p-2 rounded text-[11px] space-y-0.5">
              <div>Strategy: <span className="text-purple-300 font-bold">{recs.strategy}</span></div>
              <div>Next Vertical: <span className="text-cyan-300">{recs.nextVertical || 'none'}</span></div>
              <div>Excluded: <span className="text-rose-300">{recs.diagnostics.excludedVerticals.join(', ') || 'none'}</span></div>
              <div>Model: <span className="text-slate-400">{recs.diagnostics.modelVersion}</span></div>
              <div>Latency: <span className="text-slate-400">{recs.diagnostics.latencyMs}ms</span></div>
            </div>
          </div>

          <div className="text-[10px] text-slate-400 flex items-center justify-between pt-1 border-t border-slate-800">
            <span>Nhấn Shift + D để ẩn</span>
            <button
              onClick={toggleDebugMode}
              className="text-amber-400 underline hover:text-amber-300"
            >
              Tắt Debug
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
