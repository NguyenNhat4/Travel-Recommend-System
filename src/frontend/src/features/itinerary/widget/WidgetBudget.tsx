import React from 'react';
import { BedDouble, Plane, Ticket, type LucideIcon } from 'lucide-react';
import type { WidgetBudgetSummary } from './widgetTypes';

const vnd = new Intl.NumberFormat('vi-VN');

const GROUPS: { key: 'flights' | 'stays' | 'activities'; label: string; icon: LucideIcon; bar: string; chip: string }[] = [
  { key: 'flights', label: 'Vé máy bay', icon: Plane, bar: 'bg-sky-400', chip: 'bg-sky-50 text-sky-600' },
  { key: 'stays', label: 'Lưu trú', icon: BedDouble, bar: 'bg-blue-600', chip: 'bg-blue-50 text-blue-600' },
  { key: 'activities', label: 'Vui chơi', icon: Ticket, bar: 'bg-emerald-500', chip: 'bg-emerald-50 text-emerald-600' },
];

/** "3N2Đ" cho chuyến nhiều ngày (số đêm = số ngày − 1), "1 ngày" cho chuyến trong ngày. */
export function tripLength(days: number): string {
  return days > 1 ? `${days}N${days - 1}Đ` : '1 ngày';
}

/**
 * Khối "Ngân sách dự tính" cuối câu trả lời (user-flow §4.2, chốt 2026-10-09): tổng tiền và thanh màu chia theo vé máy
 * bay, lưu trú, vui chơi. Mọi số lấy nguyên từ `costBreakdown` của backend (cộng lại bằng tổng); độ dài đoạn trên thanh
 * chỉ để nhìn. Không có khoản ăn uống hay đi lại ước tính.
 */
export function WidgetBudget({ summary, days }: { summary: WidgetBudgetSummary; days: number }) {
  return (
    <section aria-label="Ngân sách dự tính" className="my-4 whitespace-normal rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-slate-900">Ngân sách dự tính</h3>
          <p className="text-xs text-slate-500">{tripLength(days)}</p>
        </div>
        <p className="text-base font-bold tabular-nums text-slate-900">{vnd.format(summary.total)} ₫</p>
      </div>
      {summary.total > 0 && (
        <div className="mt-3 flex h-2.5 gap-0.5 overflow-hidden rounded-full bg-slate-100" aria-hidden="true">
          {GROUPS.filter((group) => summary[group.key] > 0).map((group) => (
            <span key={group.key} data-budget-segment={group.key} className={group.bar}
              style={{ width: `${(summary[group.key] / summary.total) * 100}%` }} />
          ))}
        </div>
      )}
      <ul className="mt-3 space-y-2">
        {GROUPS.filter((group) => summary[group.key] > 0).map(({ key, label, icon: Icon, chip }) => (
          <li key={key} className="flex items-center justify-between gap-3 text-sm">
            <span className="flex items-center gap-2 text-slate-700">
              <span className={`flex h-7 w-7 items-center justify-center rounded-full ${chip}`}>
                <Icon className="h-3.5 w-3.5" aria-hidden="true" />
              </span>
              {label}
            </span>
            <span className="font-semibold tabular-nums text-slate-900">{vnd.format(summary[key])} ₫</span>
          </li>
        ))}
      </ul>
      {summary.budget != null && summary.status !== 'NO_BUDGET' && (
        <p className="mt-3 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3 text-sm text-slate-700">
          Ngân sách của bạn: <span className="font-semibold tabular-nums">{vnd.format(summary.budget)} ₫</span>
          <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${summary.status === 'WITHIN_BUDGET'
            ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'}`}>
            {summary.status === 'WITHIN_BUDGET' ? 'Trong ngân sách' : 'Vượt ngân sách'}
          </span>
        </p>
      )}
      <p className="mt-3 text-xs text-slate-500">Chỉ gồm vé, phòng và vé tham quan trong lịch; chưa gồm ăn uống, đi lại tại điểm đến.</p>
    </section>
  );
}
