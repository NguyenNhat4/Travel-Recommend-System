import React, { useId, useState } from 'react';
import Image from 'next/image';
import { ChevronDown, Compass, Palmtree, Users } from 'lucide-react';
import { AssistantTripStarter, tripStarterMessage } from '../../../components/assistant/AssistantTripStarter';
import { WidgetComposer } from './WidgetComposer';

const SUGGESTIONS = [
  { label: 'Nghỉ dưỡng', icon: Palmtree, prompt: 'Mình muốn một chuyến nghỉ dưỡng, ưu tiên thư giãn và nghỉ ngơi.' },
  { label: 'Gia đình', icon: Users, prompt: 'Giúp mình lên lịch trình cho gia đình có trẻ nhỏ.' },
  { label: 'Khám phá', icon: Compass, prompt: 'Mình muốn khám phá văn hóa và ẩm thực địa phương.' },
];

interface WidgetOpeningProps {
  value: string;
  onChange: (value: string) => void;
  onSend: (message?: string) => void;
  busy: boolean;
}

export function WidgetOpening({ value, onChange, onSend, busy }: WidgetOpeningProps) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const detailsId = useId();
  const headingId = useId();

  return (
    <section aria-labelledby={headingId} className="mx-auto my-auto flex w-full shrink-0 max-w-lg flex-col items-center px-4 py-8 sm:px-6">
      <Image src="/mascot_welcome.webp" alt="" width={72} height={72} className="mb-4 h-18 w-18 object-contain" />
      <h2 id={headingId} className="text-center text-2xl font-bold leading-tight text-slate-900">Bạn muốn đi đâu tiếp theo?</h2>
      <p className="mb-6 mt-3 text-center text-sm leading-relaxed text-slate-600">Kể ý tưởng chuyến đi, mình giúp bạn lên lịch trình.</p>
      <WidgetComposer value={value} onChange={onChange} onSend={() => onSend()} busy={busy} initial />
      <p className="mt-3 w-full text-xs leading-relaxed text-slate-500">Ví dụ: Đi biển 3 ngày, 2 người, ngân sách 5 triệu.</p>
      <div className="mt-5 flex flex-wrap justify-center gap-2" aria-label="Gợi ý yêu cầu du lịch">
        {SUGGESTIONS.map(({ label, icon: Icon, prompt }) => (
          <button key={label} type="button" disabled={busy} onClick={() => onChange(prompt)} className="inline-flex min-h-11 items-center gap-2 rounded-full border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 transition hover:border-ai-300 hover:bg-ai-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ai-500 focus-visible:ring-offset-2 disabled:opacity-50">
            <Icon className="h-4 w-4 text-ai-600" aria-hidden="true" />{label}
          </button>
        ))}
      </div>
      <button type="button" aria-expanded={detailsOpen} aria-controls={detailsId} onClick={() => setDetailsOpen((open) => !open)} className="mt-5 inline-flex min-h-11 items-center gap-2 rounded-lg px-3 text-sm font-semibold text-ai-700 hover:bg-ai-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ai-500">
        Thêm thông tin chuyến đi <ChevronDown className={`h-4 w-4 transition ${detailsOpen ? 'rotate-180' : ''}`} aria-hidden="true" />
      </button>
      <div id={detailsId} hidden={!detailsOpen} className="w-full">
        {detailsOpen && <AssistantTripStarter disabled={busy} onSubmit={(selection) => onSend(tripStarterMessage(selection))} />}
      </div>
    </section>
  );
}
