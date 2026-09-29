import React from 'react';
import { X, Plus, MessageSquare, Trash2 } from 'lucide-react';
import type { FloatingWidgetController } from './useFloatingWidget';

export function WidgetHistory({ widget }: { widget: FloatingWidgetController }) {
  const { setIsHistoryOpen, handleStartNewChat, conversations, activeSessionId,
    handleSelectConversation, handleDeleteConversation } = widget;
  return (
    <div className="absolute inset-0 z-[1050] flex overflow-hidden">
      <button aria-label="Đóng lịch sử hội thoại" onClick={() => setIsHistoryOpen(false)} className="absolute inset-0 bg-slate-900/40 backdrop-blur-xs" tabIndex={-1} />
      <div data-widget-history className="relative z-10 flex h-full w-80 max-w-[85%] flex-col border-r border-slate-100 bg-white shadow-2xl">
        <div className="flex items-center justify-between gap-2 border-b border-slate-100 p-3.5">
          <button type="button" onClick={handleStartNewChat} className="flex min-h-11 flex-1 items-center justify-center gap-2 rounded-xl bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700">
            <Plus className="h-4 w-4" aria-hidden="true" />Đoạn chat mới
          </button>
          <button type="button" onClick={() => setIsHistoryOpen(false)} aria-label="Đóng sidebar" className="flex h-11 w-11 items-center justify-center rounded-xl text-slate-500 hover:bg-slate-100">
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
        <div className="flex-1 space-y-1 overflow-y-auto p-3">
          <h2 className="font-sans px-2 py-2 text-xs font-semibold uppercase tracking-wider text-slate-500">Lịch sử trò chuyện</h2>
          {conversations.length === 0 ? <p className="py-8 text-center text-sm text-slate-500">Chưa có lịch sử hội thoại nào</p> : conversations.map((session) => (
            <div key={session.id} className={`flex items-center gap-2 rounded-xl ${activeSessionId === session.id ? 'bg-blue-50 text-blue-900' : 'text-slate-700 hover:bg-slate-50'}`}>
              <button type="button" aria-label={`Mở hội thoại ${session.title}`} onClick={() => void handleSelectConversation(session)} className="flex min-h-11 min-w-0 flex-1 items-center gap-2 p-2.5 text-left text-sm">
                <MessageSquare className="h-4 w-4 shrink-0" aria-hidden="true" />
                <span className="min-w-0"><span className="block truncate font-semibold">{session.title}</span><span className="text-xs text-slate-500">{session.timestamp}</span></span>
              </button>
              <button type="button" onClick={(event) => handleDeleteConversation(event, session.id)} aria-label={`Xóa hội thoại ${session.title}`} className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-slate-500 hover:bg-rose-50 hover:text-rose-700">
                <Trash2 className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
