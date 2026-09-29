/**
 * Đưa `VALIDATION_ERROR` của Backend (`details.fields[]`) về đúng bước và đúng trường của checkout
 * (docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md §6.7, AC-BKG-07).
 *
 * Trường `travelers[…]` và `contact.*` thuộc bước ① Hành khách; `itemDetails[…]` thuộc bước ② Dịch vụ. Lỗi ở nhiều bước thì về
 * bước sớm nhất. Code thuần để test được.
 */
import type { ValidationFieldError } from '../../services/booking';

export type Step = 'travelers' | 'services' | 'review';

export interface SummaryEntry {
  /** id của phần tử DOM để link tới và đưa focus vào. */
  targetId: string;
  where: string;
  message: string;
}

export interface MappedErrors {
  /** id phần tử DOM của trường → thông điệp (bước ①). */
  fieldErrors: Record<string, string>;
  /** cartItemId → thông điệp ở mức thẻ dịch vụ (bước ②). */
  itemErrors: Record<string, string[]>;
  /** cartItemId → chỉ số phòng → thông điệp (khách sạn). */
  roomErrors: Record<string, Record<number, string[]>>;
  /** Chỉ gồm lỗi của bước đích (`step`): mục ở bước sau không có ô nào để link tới, sẽ hiện khi khách tới bước đó. */
  summary: SummaryEntry[];
  /** Bước chứa lỗi sớm nhất; null khi không có lỗi nào định vị được. */
  step: Step | null;
  /** Có lỗi GUEST_COUNT_MISMATCH: Web tải lại giỏ và tính lại phân bổ cho các mục này. */
  mismatchedItems: string[];
}

export interface ErrorContext {
  /** `travelerRef` theo đúng thứ tự đã gửi (chỉ số trong `travelers[i]`). */
  travelerRefs: string[];
  /** `cartItemId` theo đúng thứ tự đã gửi (chỉ số trong `itemDetails[j]`). */
  cartItemIds: string[];
  /** Nhãn hiển thị của hành khách (ví dụ "Người lớn 1") theo `travelerRef`. */
  travelerLabels: Record<string, string>;
  /** Tên dịch vụ theo `cartItemId`. */
  itemNames: Record<string, string>;
}

export const TRAVELER_FIELD_IDS = { surname: 'sn', givenNames: 'gn', birthDate: 'dob' } as const;

const PARTY_ID = 'party-counters';

function travelerTarget(path: string, ctx: ErrorContext): { id: string; where: string } | null {
  const m = /^travelers\[(\d+)\]\.(surname|givenNames|birthDate|travelerRef)$/.exec(path);
  if (!m) return null;
  const ref = ctx.travelerRefs[Number(m[1])];
  if (!ref) return null;
  const label = ctx.travelerLabels[ref] ?? 'Hành khách';
  if (m[2] === 'travelerRef') return { id: PARTY_ID, where: label };
  const part = { surname: 'Họ', givenNames: 'Tên đệm và tên', birthDate: 'Ngày sinh' }[m[2] as 'surname' | 'givenNames' | 'birthDate'];
  return { id: `${TRAVELER_FIELD_IDS[m[2] as keyof typeof TRAVELER_FIELD_IDS]}-${ref}`, where: `${label} · ${part}` };
}

const CONTACT_TARGETS: Record<string, { id: string; where: string }> = {
  'contact.fullName': { id: 'c-name', where: 'Người liên hệ · Họ và tên' },
  'contact.phone': { id: 'c-phone', where: 'Người liên hệ · Số điện thoại' },
  'contact.email': { id: 'c-email', where: 'Người liên hệ · Email' },
};

export function mapValidationFields(fields: ValidationFieldError[], ctx: ErrorContext): MappedErrors {
  const out: MappedErrors = { fieldErrors: {}, itemErrors: {}, roomErrors: {}, summary: [], step: null, mismatchedItems: [] };
  let sawStep1 = false;
  let sawStep2 = false;
  const summary1: SummaryEntry[] = [];
  const summary2: SummaryEntry[] = [];
  for (const f of fields) {
    const traveler = travelerTarget(f.field, ctx);
    const contact = CONTACT_TARGETS[f.field];
    if (traveler || contact || f.field === 'travelers') {
      sawStep1 = true;
      const target = traveler ?? contact ?? { id: PARTY_ID, where: 'Đoàn khách' };
      if (!(target.id in out.fieldErrors)) out.fieldErrors[target.id] = f.message;
      summary1.push({ targetId: target.id, where: target.where, message: f.message });
      continue;
    }
    const item = /^itemDetails(?:\[(\d+)\])?(?:\.(.*))?$/.exec(f.field);
    if (item || f.cartItemId) {
      sawStep2 = true;
      const cartItemId = f.cartItemId ?? (item?.[1] !== undefined ? ctx.cartItemIds[Number(item[1])] : undefined);
      const name = cartItemId ? ctx.itemNames[cartItemId] : undefined;
      const room = /rooms\[(\d+)\]/.exec(item?.[2] ?? '');
      if (cartItemId) {
        if (room) {
          const rooms = (out.roomErrors[cartItemId] ??= {});
          (rooms[Number(room[1])] ??= []).push(f.message);
        } else (out.itemErrors[cartItemId] ??= []).push(f.message);
        if (f.reason === 'GUEST_COUNT_MISMATCH') out.mismatchedItems.push(cartItemId);
      }
      summary2.push({ targetId: cartItemId ? (room ? `room-${cartItemId}-${room[1]}` : `card-${cartItemId}`) : 'checkout-top',
        where: name ?? 'Dịch vụ', message: f.message });
    }
  }
  out.step = sawStep1 ? 'travelers' : sawStep2 ? 'services' : null;
  out.summary = sawStep1 ? summary1 : summary2;
  return out;
}
