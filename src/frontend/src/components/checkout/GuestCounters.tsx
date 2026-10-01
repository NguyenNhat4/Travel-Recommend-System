'use client';

/**
 * Bộ đếm khách dùng chung cho hộp đặt ở trang chi tiết và nút [Sửa] ở giỏ (docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md
 * §6.9, §6.10): vé tham quan/golf/chuyến bay có hai bộ đếm Người lớn và Trẻ em kèm đơn giá từng loại; khách sạn có số phòng,
 * người lớn, trẻ em và gợi ý sức chứa; combo chỉ có số gói. Chỉ dựng lựa chọn, tiền hiển thị là ước tính, Backend tính giá thật.
 */
import React from 'react';
import { formatVnd } from '../confirmation/bookingLabels';
import type { CartState } from './allocation';
import { CounterRow } from './CheckoutParts';
import { childUnitPrice } from './fareEstimate';
import {
  canChange, capacityIssue, changeCount, guestModeOf, maxOccupancyFromAttributes, totalGuests, type CounterKind,
} from './guestCounts';

export const FLIGHT_CHILD_NOTE = 'Chưa có giá vé trẻ em riêng: trẻ em và em bé có ghế riêng, tính giá người lớn.';

export const GuestCounters: React.FC<{
  taxonomy: string;
  unitPrice: number;
  attributes?: Record<string, unknown> | null;
  value: CartState;
  onChange: (next: CartState) => void;
  /** false khi chưa biết đơn giá từng loại (ví dụ chưa tải xong `attributes`): chỉ hiện giới hạn tuổi, không nói "cùng giá người lớn". */
  showPrices?: boolean;
}> = ({ taxonomy, unitPrice, attributes, value, onChange, showPrices = true }) => {
  const mode = guestModeOf(taxonomy);
  const step = (kind: CounterKind, delta: 1 | -1) => onChange(changeCount(mode, value, kind, delta));
  const can = (kind: CounterKind, delta: 1 | -1) => canChange(mode, value, kind, delta);

  if (mode === 'package') {
    return (
      <div className="divide-y divide-slate-100">
        <CounterRow label="Số gói" hint="Giá tính theo gói" value={value.quantity} canDec={can('quantity', -1)} canInc={can('quantity', 1)}
          decLabel="Bớt gói" incLabel="Thêm gói" onDec={() => step('quantity', -1)} onInc={() => step('quantity', 1)} />
      </div>
    );
  }

  const maxOccupancy = maxOccupancyFromAttributes(attributes);
  const childPrice = childUnitPrice(taxonomy, unitPrice, attributes);
  const issue = capacityIssue(mode, value, maxOccupancy);
  const adults = (
    <CounterRow label="Người lớn" hint={mode === 'person' && showPrices ? `Từ 12 tuổi · ${formatVnd(unitPrice)}` : 'Từ 12 tuổi'} value={value.guests.adults}
      canDec={can('adults', -1)} canInc={can('adults', 1)} decLabel="Bớt người lớn" incLabel="Thêm người lớn"
      onDec={() => step('adults', -1)} onInc={() => step('adults', 1)} />
  );
  const children = (
    <CounterRow label="Trẻ em"
      hint={mode === 'person' && showPrices ? `Dưới 12 tuổi · ${childPrice ? formatVnd(childPrice) : 'cùng giá người lớn'}` : 'Dưới 12 tuổi'}
      value={value.guests.children} canDec={can('children', -1)} canInc={can('children', 1)} decLabel="Bớt trẻ em" incLabel="Thêm trẻ em"
      onDec={() => step('children', -1)} onInc={() => step('children', 1)} />
  );

  if (mode === 'person') {
    return (
      <div>
        <div className="divide-y divide-slate-100">{adults}{children}</div>
        {taxonomy === 'flight' && value.guests.children > 0 && <p className="text-xs text-slate-500 pt-1" data-testid="flight-child-note">{FLIGHT_CHILD_NOTE}</p>}
      </div>
    );
  }

  return (
    <div>
      <div className="divide-y divide-slate-100">
        <CounterRow label="Số phòng" hint={maxOccupancy ? `Tối đa ${maxOccupancy} khách/phòng` : 'Khách sạn chưa công bố sức chứa phòng'}
          value={value.quantity} canDec={can('quantity', -1)} canInc={can('quantity', 1)} decLabel="Bớt phòng" incLabel="Thêm phòng"
          onDec={() => step('quantity', -1)} onInc={() => step('quantity', 1)} />
        {adults}
        {children}
      </div>
      {issue && (
        <div role="alert" className="mt-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900 flex items-start justify-between gap-3" data-testid="capacity-issue">
          <span>{totalGuests(value)} khách vượt sức chứa {issue.capacity} khách của {value.quantity} phòng. Cần ít nhất {issue.suggestedRooms} phòng.</span>
          {can('quantity', 1) && <button type="button" onClick={() => step('quantity', 1)} className="font-bold underline shrink-0">Thêm 1 phòng</button>}
        </div>
      )}
    </div>
  );
};
