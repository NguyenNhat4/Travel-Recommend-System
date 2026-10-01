import React from 'react';
import { Compass } from 'lucide-react';

const PROMPTS = ['Lịch trình Nha Trang 3 ngày lưu trú 2 khách sạn', 'Lên lịch trình 3 ngày Nha Trang biệt thự hồ bơi', 'Lịch trình Phú Quốc 3N2Đ', 'Lịch trình Đà Nẵng 2 ngày', 'Lịch trình Đà Lạt 7 ngày'];

export function WidgetPlanEmpty({ onPrompt }: { onPrompt: (prompt: string) => void }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center bg-slate-50 p-8 text-center">
      <Compass className="mb-4 h-12 w-12 text-blue-600" aria-hidden="true" />
      <h2 className="mb-2 text-xl font-bold text-slate-900">Lộ trình du lịch thông minh & Bản đồ tương tác</h2>
      <p className="mb-6 max-w-md text-base leading-relaxed text-slate-600">Kể cho AI ý tưởng chuyến đi của bạn. Lịch trình theo ngày và bản đồ sẽ xuất hiện tại đây.</p>
      <div className="flex flex-wrap justify-center gap-2">
        {PROMPTS.map((prompt) => <button key={prompt} type="button" onClick={() => onPrompt(prompt)} className="min-h-11 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-50">{prompt}</button>)}
      </div>
    </div>
  );
}
