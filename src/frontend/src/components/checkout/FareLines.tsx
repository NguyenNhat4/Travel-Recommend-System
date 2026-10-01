'use client';

/**
 * Các dòng giá theo loại khách của một mục (giỏ, bước Dịch vụ, trang đơn). Chỉ hiển thị `fares` do Backend trả về, không tự tính
 * (docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md §4.3).
 */
import React from 'react';
import { formatVnd } from '../confirmation/bookingLabels';
import type { FareLine } from './fareEstimate';

const FARE_LABEL: Record<FareLine['fareType'], string> = { ADULT: 'Người lớn', CHILD: 'Trẻ em', ROOM: 'Giá phòng', PACKAGE: 'Gói' };

export function fareText(fare: FareLine): string {
  return fare.fareType === 'ROOM'
    ? `${formatVnd(fare.unitPrice)} × ${fare.nights} đêm × ${fare.count} phòng`
    : `${fare.count} × ${formatVnd(fare.unitPrice)}`;
}

export const FareLines: React.FC<{ fares: FareLine[]; className?: string; testId?: string }> = ({ fares, className = '', testId = 'fare-lines' }) => {
  if (!fares.length) return null;
  return (
    <div className={`rounded-lg bg-slate-50 border border-slate-100 px-3 py-2.5 text-xs space-y-1 ${className}`} data-testid={testId}>
      {fares.map((fare) => (
        <div key={fare.fareType} className="flex justify-between gap-3">
          <span className="text-slate-600">{FARE_LABEL[fare.fareType]}</span>
          <span className="tabular-nums">{fareText(fare)} = <b className="text-slate-800">{formatVnd(fare.amount)}</b></span>
        </div>
      ))}
    </div>
  );
};
