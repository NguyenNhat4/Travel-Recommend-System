import React, { useMemo } from 'react';
import { 
  Bot, User, Sparkles, Map, List, Bookmark, 
  BookmarkCheck, Share2
} from 'lucide-react';
import { ChatMessage, GroundedPlan } from '../../types/travel';
import { useTravel } from '../../context/TravelContext';
import { localizePlan, TRANSLATIONS, formatLocalizedCurrency } from '../../services/localization';

interface ChatMessageBubbleProps {
  message: ChatMessage;
  savedTrips: { plan: GroundedPlan }[];
  onSelectPlan: (plan: GroundedPlan, view: 'map' | 'list') => void;
  onToggleSaveTrip: (plan: GroundedPlan) => void;
  onSelectFollowUp: (prompt: string) => void;
  onSharePlan?: (plan: GroundedPlan) => void;
}

export const ChatMessageBubble: React.FC<ChatMessageBubbleProps> = ({
  message,
  savedTrips,
  onSelectPlan,
  onToggleSaveTrip,
  onSelectFollowUp,
  onSharePlan
}) => {
  const { currentLocale } = useTravel();
  const t = TRANSLATIONS[currentLocale] || TRANSLATIONS.vi;

  const isUser = message.sender === 'user';

  const localizedMsgPlan = useMemo(() => {
    if (!message.plan) return null;
    return localizePlan(message.plan, currentLocale);
  }, [message.plan, currentLocale]);

  const isSaved = message.plan
    ? savedTrips.some(
        st => st.plan.title === message.plan?.title && st.plan.intent.destination === message.plan?.intent.destination
      )
    : false;

  // Simple clean markdown parser for bold, lists, and paragraphs
  const renderFormattedText = (rawText: string) => {
    const lines = rawText.split('\n');
    return (
      <div className="space-y-1.5">
        {lines.map((line, idx) => {
          const trimmed = line.trim();
          if (!trimmed) return <div key={idx} className="h-1" />;

          // Bullet points
          if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
            const content = trimmed.substring(2);
            return (
              <div key={idx} className="flex items-start gap-1.5 pl-1 text-xs sm:text-sm">
                <span className="text-blue-500 font-bold shrink-0 mt-0.5">•</span>
                <span>{parseInlineBold(content)}</span>
              </div>
            );
          }

          // Numbered lists
          const numMatch = trimmed.match(/^(\d+)\.\s+(.*)/);
          if (numMatch) {
            return (
              <div key={idx} className="flex items-start gap-1.5 pl-1 text-xs sm:text-sm">
                <span className="font-bold text-blue-600 shrink-0 mt-0.5">{numMatch[1]}.</span>
                <span>{parseInlineBold(numMatch[2])}</span>
              </div>
            );
          }

          // Regular paragraph
          return (
            <p key={idx} className="text-xs sm:text-sm leading-relaxed">
              {parseInlineBold(trimmed)}
            </p>
          );
        })}
      </div>
    );
  };

  const parseInlineBold = (text: string) => {
    const parts = text.split(/(\*\*.*?\*\*)/g);
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={i} className="font-bold text-slate-900">{part.slice(2, -2)}</strong>;
      }
      return part;
    });
  };

  return (
    <div className={`flex gap-2.5 ${isUser ? 'justify-end' : 'justify-start'}`}>
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center shrink-0 mt-0.5 shadow-2xs border border-blue-200">
          <Bot className="w-4 h-4" />
        </div>
      )}

      <div className={`space-y-1.5 max-w-[88%] ${isUser ? 'items-end' : 'items-start'}`}>
        {/* Header timestamp for Assistant Messages */}
        {!isUser && message.timestamp && (
          <div className="flex items-center gap-1.5 text-[10px] text-slate-400 pl-1">
            <span>{currentLocale === 'vi' ? 'Trợ lý AI' : 'AI Assistant'}</span>
            <span>•</span>
            <span>{message.timestamp}</span>
          </div>
        )}

        {/* Message Bubble Body */}
        <div
          className={`p-3.5 rounded-2xl ${
            isUser
              ? 'bg-blue-600 text-white rounded-br-xs shadow-2xs'
              : 'bg-slate-50 text-slate-800 rounded-bl-xs border border-slate-200/80 shadow-2xs'
          }`}
        >
          {isUser ? (
            <p className="text-xs sm:text-sm leading-relaxed whitespace-pre-wrap">{message.text}</p>
          ) : (
            renderFormattedText(message.text)
          )}
        </div>

        {/* Grounded Plan Card Attachment */}
        {localizedMsgPlan && (
          <div className="p-3 bg-gradient-to-br from-blue-50 to-sky-50/50 border border-blue-200 rounded-xl text-xs text-blue-950 space-y-2 shadow-2xs">
            <div>
              <div className="font-bold flex items-center gap-1.5 text-blue-900">
                <Sparkles className="w-3.5 h-3.5 text-blue-600" />
                <span>{localizedMsgPlan.title}</span>
              </div>
              <p className="text-[11px] text-blue-700 mt-0.5">
                {localizedMsgPlan.bookableProductsCount} {t.bookableServices}
                {localizedMsgPlan.totalEstimatedPrice != null
                  && ` · ${t.estimated} ~${formatLocalizedCurrency(localizedMsgPlan.totalEstimatedPrice, currentLocale).formatted}`}
              </p>
            </div>

            <div className="flex items-center gap-1.5 pt-1 flex-wrap">
              <button
                onClick={() => message.plan && onSelectPlan(message.plan, 'map')}
                className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-bold bg-white text-blue-700 hover:bg-blue-100 rounded-lg border border-blue-300 shadow-2xs transition-colors"
              >
                <Map className="w-3.5 h-3.5 text-blue-600" />
                <span>{t.mapView}</span>
              </button>
              <button
                onClick={() => message.plan && onSelectPlan(message.plan, 'list')}
                className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium bg-white/80 text-slate-700 hover:bg-white rounded-lg border border-slate-200 transition-colors"
              >
                <List className="w-3.5 h-3.5 text-slate-500" />
                <span>{currentLocale === 'vi' ? 'Xem chi tiết' : 'Details'}</span>
              </button>
              <button
                onClick={() => message.plan && onToggleSaveTrip(message.plan)}
                className={`inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-bold rounded-lg border transition-colors ${
                  isSaved
                    ? 'bg-emerald-100 text-emerald-800 border-emerald-300 shadow-2xs'
                    : 'bg-white text-slate-700 hover:bg-slate-100 border-slate-200'
                }`}
              >
                {isSaved ? (
                  <>
                    <BookmarkCheck className="w-3.5 h-3.5 text-emerald-600" />
                    <span>{t.saved}</span>
                  </>
                ) : (
                  <>
                    <Bookmark className="w-3.5 h-3.5 text-slate-400" />
                    <span>{t.saveTrip}</span>
                  </>
                )}
              </button>

              {onSharePlan && (
                <button
                  onClick={() => message.plan && onSharePlan(message.plan)}
                  className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-bold bg-indigo-50 text-indigo-700 hover:bg-indigo-100 rounded-lg border border-indigo-200 transition-colors shadow-2xs"
                  title={t.share}
                >
                  <Share2 className="w-3.5 h-3.5 text-indigo-600" />
                  <span>{t.share}</span>
                </button>
              )}
            </div>
          </div>
        )}

        {/* Suggested Follow-Up Prompts */}
        {message.suggestedFollowUps && message.suggestedFollowUps.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {message.suggestedFollowUps.map((chip, i) => (
              <button
                key={i}
                onClick={() => onSelectFollowUp(chip)}
                className="px-2.5 py-1 text-[11px] bg-white hover:bg-blue-50 border border-slate-200 hover:border-blue-300 text-slate-700 hover:text-blue-700 rounded-full shadow-2xs transition-all flex items-center gap-1"
              >
                <span>{chip}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {isUser && (
        <div className="w-8 h-8 rounded-full bg-slate-800 text-white flex items-center justify-center shrink-0 mt-0.5 shadow-2xs">
          <User className="w-4 h-4" />
        </div>
      )}
    </div>
  );
};
