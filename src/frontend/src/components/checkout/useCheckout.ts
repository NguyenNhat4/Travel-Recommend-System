'use client';

/**
 * Trạng thái và hành động của checkout ba bước (docs/spec/booking/checkout-nhieu-buoc-hanh-khach.md §6).
 *
 * Giữ ở một hook, tách khỏi phần hiển thị, để: (1) trạng thái nằm ở component gốc và không mất khi phiên hết hạn giữa chừng
 * (hộp đăng nhập lại hiện lên, dữ liệu đang nhập vẫn còn — §6.2); (2) các bước chỉ lo hiển thị.
 *
 * Quy tắc bất di bất dịch: Web không tự cộng tiền. Mọi con số tiền lấy từ `CartResponse` sau mỗi `PATCH /cart/items`.
 *
 * Nguồn mục là giỏ (`/checkout`) hoặc một đơn nháp của Đặt ngay (`/checkout?draft=<mã>`), qua `useCheckoutSource`; hai nguồn
 * trả cùng hình dạng mục nên phần còn lại của hook không phân biệt (docs/spec/booking/dat-truc-tiep-theo-don-nhap.md §6, §13).
 * Khách chưa đăng nhập đi hết ba bước được; bấm Thanh toán thì hộp đăng nhập mở ngay trên trang (R-CHK-06).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTravel } from '../../context/TravelContext';
import * as bookingApi from '../../services/booking';
import type { ApiCartItem, BookingResponse, CheckoutRequest } from '../../services/booking';
import { ApiError } from '../../services/http';
import { formatVnd } from '../confirmation/bookingLabels';
import {
  blankFlight, contactInputOf, defaultAllocation, defaultParty, desiredCartState, draftToTraveler, guestsFromAllocation, isHotel,
  itemInputsOf, newDrafts, partyCounts, cartFactsOf, cartStateOf, reconcileAllocation, refsOf, sameCartState, toTravelerInputs,
  travelerLabel, displayName, fixLead, type Allocation, type CartState, type FlightDraft, type RoomDraft, type TravelerDraft,
} from './allocation';
import {
  MAX_ROOMS, checkContact, checkItems, checkParty, fareTypeOn, formatDmy, isInfantOn, maskDmy, messageFor, normalizeName, orderPartyCap,
  parseDmy, splitFullName, type Violation,
} from './checkoutRules';
import { useCheckoutSource } from './checkoutSource';
import { createPatchQueue } from './patchQueue';
import { mapValidationFields, type Step, type SummaryEntry } from './serverErrors';

export const STEPS: Array<{ key: Step; label: string }> = [
  { key: 'travelers', label: 'Hành khách' },
  { key: 'services', label: 'Dịch vụ' },
  { key: 'review', label: 'Xem lại và thanh toán' },
];

export type Banner =
  | { kind: 'price'; cartItemId: string | null; name: string; oldPrice: number; newPrice: number; fareType: 'ADULT' | 'CHILD' }
  | { kind: 'unavailable' | 'date'; name: string; text: string }
  | { kind: 'error'; text: string; retryable: boolean; requestId: string | null };

export interface PendingHold {
  referenceCode: string;
  holdExpiresAt: string | null;
}

const PATCH_DEBOUNCE_MS = 400;
export const RELOAD_NOTE =
  'Để bảo vệ thông tin cá nhân, họ tên và ngày sinh không được lưu khi tải lại trang. Vui lòng nhập lại.';

/** Ngày hôm nay theo lịch Việt Nam, `YYYY-MM-DD`. */
export function todayVn(): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh' }).format(new Date());
}

/** Ngày liền trước ngày sử dụng sớm nhất, `YYYY-MM-DD`. */
function dayBefore(earliest: string): string {
  const d = new Date(`${earliest}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() - 1);
  return d.toISOString().slice(0, 10);
}

/** 00:00 ngày liền trước ngày sử dụng sớm nhất (FR-BKG-07); chỉ để hiển thị, Backend vẫn quyết định `cancellableUntil`. */
export function cancelDeadlineText(earliest: string | null): string | null {
  return earliest ? formatDmy(dayBefore(earliest)) : null;
}

/**
 * Hạn huỷ có hoàn tiền đã qua ngay từ lúc đặt (ngày sử dụng sớm nhất là hôm nay hoặc ngày mai): đơn không được hoàn tiền nếu huỷ.
 * 00:00 giờ Việt Nam của ngày liền trước, khớp `cancellable_until` của Backend.
 */
export function cancelDeadlinePassed(earliest: string | null, now: Date = new Date()): boolean {
  return earliest !== null && now.getTime() >= Date.parse(`${dayBefore(earliest)}T00:00:00+07:00`);
}

function readStep(): Step {
  if (typeof window === 'undefined') return 'travelers';
  const value = new URLSearchParams(window.location.search).get('step');
  return value === 'services' || value === 'review' ? value : 'travelers';
}

/** URL của một bước, giữ `draft=<mã>`: mất tham số này thì tải lại trang sẽ thành thanh toán giỏ thay vì đơn nháp. */
function stepUrl(step: Step, draftId: string | null): string {
  return draftId ? `?draft=${encodeURIComponent(draftId)}&step=${step}` : `?step=${step}`;
}

const sortItems = (items: ApiCartItem[]) => [...items].sort((a, b) => a.usingDate.localeCompare(b.usingDate));

export function useCheckout() {
  const { currentPersona, authReady, navigate, rememberBooking, showToast, openLoginModal } = useTravel();
  const source = useCheckoutSource();
  const { data: cart, refresh: refreshCart, updateItem: updateCartItem } = source;
  const items = useMemo(() => sortItems(cart?.items ?? []), [cart]);
  const email = currentPersona?.email ?? '';

  // --- đoàn khách, người liên hệ, phân bổ ---------------------------------------------------------------
  const [drafts, setDrafts] = useState<TravelerDraft[]>([]);
  const [seq, setSeq] = useState(0);
  const [contactName, setContactName] = useState('');
  const [phone, setPhone] = useState('');
  const [syncContact, setSyncContactState] = useState(true);
  const [allocs, setAllocs] = useState<Record<string, Allocation>>({});
  const [special, setSpecial] = useState<Record<string, string>>({});
  const [confirmRemove, setConfirmRemove] = useState<string | null>(null);

  // --- điều hướng và lỗi ------------------------------------------------------------------------------------
  const [step, setStepState] = useState<Step>(readStep);
  const [done, setDone] = useState<{ travelers: boolean; services: boolean }>({ travelers: false, services: false });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [summary, setSummary] = useState<SummaryEntry[]>([]);
  const [serverItemErrors, setServerItemErrors] = useState<Record<string, string[]>>({});
  const [serverRoomErrors, setServerRoomErrors] = useState<Record<string, Record<number, string[]>>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [pending, setPending] = useState<Record<string, boolean>>({});
  const [patchErrors, setPatchErrors] = useState<Record<string, ApiError>>({});
  const [notice, setNotice] = useState<string | null>(null);
  const [cartChanged, setCartChanged] = useState(false);
  const [banner, setBanner] = useState<Banner | null>(null);
  const [pendingHold, setPendingHold] = useState<PendingHold | null>(null);
  const [termsAgreed, setTermsAgreed] = useState(false);
  const [method, setMethod] = useState<'stripe'>('stripe');
  const [submitting, setSubmitting] = useState(false);

  // --- tham chiếu mới nhất cho mã bất đồng bộ (PATCH nối tiếp, submit) --------------------------------------------
  // Cập nhật sau mỗi lần vẽ (khai báo đầu tiên nên chạy trước các effect bên dưới); các hàm xử lý sự kiện tự ghi thẳng vào đây khi
  // cần thấy ngay giá trị mới (hai thao tác liên tiếp trước khi React kịp vẽ lại).
  const latest = useRef({ items, drafts, allocs, cart });
  useEffect(() => { latest.current = { items, drafts, allocs, cart }; });
  const initializedFor = useRef<string | null>(null);
  // Tài khoản mới nhất cho mã chạy sau khi đăng nhập ngay trên trang (callback của hộp đăng nhập chạy ở lần vẽ sau).
  const personaRef = useRef(currentPersona);
  useEffect(() => { personaRef.current = currentPersona; });
  const knownPrices = useRef<Record<string, number | null>>({});
  const seenItemIds = useRef<string>('');
  /** Số lượng/số khách đã gửi (hoặc đang gửi) lên Backend cho từng mục: so với đây chứ không so với `items`, vì React chưa kịp vẽ lại giỏ mới. */
  const sent = useRef<Record<string, CartState>>({});
  /** Lỗi PATCH giữ ở ref (nguồn sự thật cho mã bất đồng bộ) và phản chiếu sang state để hiển thị. */
  const patchErrorsRef = useRef<Record<string, ApiError>>({});
  const [queue] = useState(() => createPatchQueue(PATCH_DEBOUNCE_MS));
  // Rời màn hình (đi sửa giỏ, đổi trang): gửi nốt thay đổi còn đang chờ debounce, không bỏ rơi lựa chọn cuối của khách.
  useEffect(() => () => { void queue.flush(); }, [queue]);

  // --- khởi tạo: đoàn mặc định từ giỏ, phân bổ mặc định (§6.5) ----------------------------------------------------
  useEffect(() => {
    if (!authReady || !cart || cart.items.length === 0) return;
    const owner = source.draftId ? `draft:${source.draftId}` : `cart:${currentPersona?.id ?? 'guest'}`;
    if (initializedFor.current === owner) return;
    // Khách vừa đăng nhập ngay trên trang thanh toán (giỏ của khách đã được gộp vào tài khoản): giữ thông tin đang nhập.
    const keepsInput = initializedFor.current === 'cart:guest' && currentPersona !== null;
    initializedFor.current = owner;
    // Số điện thoại hồ sơ (FR-USR-04) điền sẵn ô liên hệ; người dùng đã gõ rồi thì không ghi đè.
    const profilePhone = currentPersona?.phone ?? '';
    if (keepsInput) {
      if (profilePhone) setPhone((current) => current || profilePhone);
      return;
    }
    const { drafts: initial, seq: nextSeq } = newDrafts(defaultParty(cart.items), currentPersona?.name ?? '');
    setDrafts(initial);
    setSeq(nextSeq);
    setContactName(currentPersona?.name ?? '');
    setPhone(profilePhone);
    setAllocs(Object.fromEntries(cart.items.map((item) => [item.cartItemId, defaultAllocation(item, initial)])));
    setDone({ travelers: false, services: false });
    setErrors({});
    setSummary([]);
    seenItemIds.current = cart.items.map((i) => i.cartItemId).sort().join('|');
    // Mở thẳng một bước sau khi chưa có dữ liệu (tải lại trang): về bước đầu và nói rõ vì sao.
    if (readStep() !== 'travelers') {
      setNotice(RELOAD_NOTE);
      window.history.replaceState(null, '', stepUrl('travelers', source.draftId));
      setStepState('travelers');
    }
  }, [cart, currentPersona, authReady, source.draftId]);

  // Giỏ đổi (ví dụ ở tab khác): mục mới nhận phân bổ mặc định, mục đã xoá bị bỏ (§6.2).
  useEffect(() => {
    if (!cart || initializedFor.current === null) return;
    const ids = cart.items.map((i) => i.cartItemId).sort().join('|');
    if (ids === seenItemIds.current) return;
    const first = seenItemIds.current === '';
    seenItemIds.current = ids;
    setAllocs((prev) => {
      const next: Record<string, Allocation> = {};
      for (const item of cart.items) next[item.cartItemId] = prev[item.cartItemId] ?? defaultAllocation(item, latest.current.drafts);
      return next;
    });
    if (!first) setCartChanged(true);
  }, [cart]);

  // Đổi giá do catalog cập nhật (không do đổi số khách): báo bằng toast (§6.6).
  useEffect(() => {
    if (!cart) return;
    for (const item of cart.items) {
      const before = knownPrices.current[item.cartItemId];
      const now = item.product.unitPrice ?? null;
      if (before !== undefined && before !== null && now !== null && before !== now) {
        showToast(`Giá ${item.product.name} vừa cập nhật: ${formatVnd(before)} → ${formatVnd(now)}`);
      }
      knownPrices.current[item.cartItemId] = now;
    }
  }, [cart, showToast]);

  // Giỏ rỗng thì về /cart (§6.2), trừ khi đang gửi đơn. Đơn nháp không còn mục nào (đã bỏ mục cuối) thì về trang chủ.
  useEffect(() => {
    if (cart && cart.items.length === 0 && !submitting) navigate(source.kind === 'cart' ? '/cart' : '/');
  }, [cart, submitting, navigate, source.kind]);

  // Nút Back / Forward của trình duyệt đổi `?step=` mà không mất dữ liệu (§6.2).
  useEffect(() => {
    const onPop = () => setStepState(readStep());
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  // --- dẫn xuất ------------------------------------------------------------------------------------------------------
  const travelers = useMemo(() => drafts.map(draftToTraveler), [drafts]);
  const earliest = useMemo(() => items.reduce<string | null>((min, i) => (min === null || i.usingDate < min ? i.usingDate : min), null), [items]);
  const facts = useMemo(() => items.map(cartFactsOf), [items]);
  // Trần của đoàn: theo mục lớn nhất trong đơn (khách sạn 9 khách mỗi phòng, loại khác 9 khách; FR-BKG-08).
  const partyCap = useMemo(() => orderPartyCap(facts), [facts]);
  const adult1 = drafts.find((d) => d.type === 'ADULT');
  const contactFullName = syncContact && adult1 ? normalizeName(`${adult1.surname} ${adult1.givenNames}`) : contactName;
  const labels = useMemo(() => Object.fromEntries(drafts.map((d) => [d.ref, travelerLabel(d, drafts)])), [drafts]);
  const anyPending = Object.values(pending).some(Boolean);
  const hasUnavailable = items.some((i) => !i.product.available);

  // Giỏ có vé máy bay thì mỗi hành khách khai thêm thông tin cho hãng bay (FR-BKG-13).
  const flightDates = useMemo(() => items.filter((i) => i.product.taxonomy === 'flight').map((i) => i.usingDate), [items]);
  const hasFlight = flightDates.length > 0;
  const isInfant = useCallback((d: TravelerDraft) => {
    const t = draftToTraveler(d);
    return flightDates.some((day) => isInfantOn(t, day));
  }, [flightDates]);

  const partyViolations = useCallback((): Violation[] => {
    const party = checkParty(toTravelerInputs(latest.current.drafts, hasFlight), { earliest, today: todayVn(), flightDates, maxParty: partyCap });
    // Thứ tự hiển thị trên màn hình (thẻ hành khách rồi tới người liên hệ) quyết định lỗi nào được đưa con trỏ tới trước.
    const contact = checkContact(contactInputOf(contactFullName, phone, email));
    // Khách chưa đăng nhập chưa có email: email nhận thông tin lấy theo tài khoản, và tạo đơn luôn cần đăng nhập (R-CHK-06),
    // nên chỉ kiểm email khi đã có tài khoản. Nhờ vậy khách điền được cả ba bước trước khi đăng nhập.
    const signedIn = Boolean(currentPersona);
    return [...party.violations, ...contact.filter((v) => signedIn || v.field !== 'contact.email')];
  }, [earliest, flightDates, hasFlight, partyCap, contactFullName, phone, email, currentPersona]);

  /**
   * Lỗi từng thẻ dịch vụ, tính trực tiếp từ phân bổ hiện tại (bước ②). Trong lúc PATCH của một mục còn chờ hoặc đang chạy thì
   * `guests` của giỏ chưa kịp đổi theo phân bổ, nên chưa so số khách của mục đó (tránh nháy lỗi GUEST_COUNT_MISMATCH giả).
   */
  const itemViolations = useMemo(() => {
    const details = itemInputsOf(items, allocs, drafts);
    return checkItems(travelers, details, facts).filter((v) => !(v.reason === 'GUEST_COUNT_MISMATCH' && v.cartItemId && pending[v.cartItemId]));
  }, [items, allocs, drafts, travelers, facts, pending]);

  // --- mã bước ------------------------------------------------------------------------------------------------------------
  const focusHeading = useCallback(() => {
    window.setTimeout(() => document.getElementById('step-heading')?.focus({ preventScroll: false }), 0);
  }, []);

  const goto = useCallback((next: Step, opts: { replace?: boolean; refresh?: boolean } = {}) => {
    const url = stepUrl(next, source.draftId);
    if (opts.replace) window.history.replaceState(null, '', url); else window.history.pushState(null, '', url);
    setStepState(next);
    setSummary([]);
    focusHeading();
    // Mỗi lần chuyển bước tải lại giỏ vì giỏ có thể đã đổi ở tab khác (§6.2). Chờ các PATCH đang bay xong trước khi GET,
    // để bản GET cũ không đè kết quả PATCH.
    if (opts.refresh !== false) void queue.flush().then(() => refreshCart());
  }, [focusHeading, refreshCart, queue, source.draftId]);

  // Chỉ vào được bước sau khi các bước trước đã đạt; nếu không thì về bước đầu tiên chưa đạt.
  useEffect(() => {
    if (!cart || initializedFor.current === null) return;
    if (step === 'services' && !done.travelers) goto('travelers', { replace: true });
    else if (step === 'review' && !(done.travelers && done.services)) goto(done.travelers ? 'services' : 'travelers', { replace: true });
  }, [step, done, cart, goto]);

  const focusId = useCallback((id: string) => {
    window.setTimeout(() => {
      const el = document.getElementById(id);
      if (el) { el.scrollIntoView?.({ block: 'center' }); (el as HTMLElement).focus?.(); }
    }, 0);
  }, []);

  // --- bước ①: chỉnh đoàn khách -------------------------------------------------------------------------------------------
  const clearError = (id: string) => setErrors((prev) => { if (!(id in prev)) return prev; const { [id]: _drop, ...rest } = prev; return rest; });

  const updateAllocsForParty = useCallback((nextDrafts: TravelerDraft[]) => {
    const allocs = Object.fromEntries(latest.current.items.map((item) => [
      item.cartItemId,
      reconcileAllocation(item, latest.current.allocs[item.cartItemId] ?? defaultAllocation(item, nextDrafts), nextDrafts)]));
    latest.current = { ...latest.current, drafts: nextDrafts, allocs };
    setAllocs(allocs);
  }, []);

  const addTraveler = (type: 'ADULT' | 'CHILD') => {
    const counts = partyCounts(drafts);
    if (counts.adults + counts.children >= orderPartyCap(latest.current.items.map(cartFactsOf))) return;
    const ref = `t${seq + 1}`;
    setSeq(seq + 1);
    const draft: TravelerDraft = { ref, type, surname: '', givenNames: '', birthText: '', flight: blankFlight() };
    const lastAdult = drafts.map((d) => d.type).lastIndexOf('ADULT');
    const next = type === 'ADULT' ? [...drafts.slice(0, lastAdult + 1), draft, ...drafts.slice(lastAdult + 1)] : [...drafts, draft];
    setDrafts(next);
    updateAllocsForParty(next);
  };

  const removeTraveler = (type: 'ADULT' | 'CHILD', confirmed = false) => {
    const group = drafts.filter((d) => d.type === type);
    if ((type === 'ADULT' && group.length <= 1) || group.length === 0) return;
    const last = group[group.length - 1];
    const hasData = Boolean(last.surname.trim() || last.givenNames.trim() || last.birthText.trim() || last.flight.docNumber.trim());
    if (hasData && !confirmed) { setConfirmRemove(last.ref); return; }
    // Em bé đang chọn người vừa bỏ làm người đi kèm thì xoá lựa chọn đó.
    const next = drafts.filter((d) => d.ref !== last.ref).map((d) => (d.flight.escortRef === last.ref ? { ...d, flight: { ...d.flight, escortRef: '' } } : d));
    setConfirmRemove(null);
    setDrafts(next);
    updateAllocsForParty(next);
  };

  const updateDraft = (ref: string, patch: Partial<TravelerDraft>, fieldId?: string) => {
    if (fieldId) clearError(fieldId);
    setDrafts((prev) => prev.map((d) => (d.ref === ref ? { ...d, ...patch } : d)));
  };

  /**
   * Sửa khối thông tin bay của một người. Đổi quốc tịch sang khác Việt Nam khi đang chọn CCCD thì tự chuyển sang hộ chiếu và
   * xoá số giấy tờ, ngày hết hạn (AC-BKG-12); đổi loại giấy tờ cũng xoá số và ngày hết hạn cũ.
   */
  const updateFlight = (ref: string, patch: Partial<FlightDraft>, fieldId?: string) => {
    if (fieldId) clearError(fieldId);
    setDrafts((prev) => prev.map((d) => {
      if (d.ref !== ref) return d;
      let flight = { ...d.flight, ...patch };
      if (patch.nationality !== undefined && flight.nationality !== 'VN' && flight.docType === 'CCCD') {
        flight = { ...flight, docType: 'PASSPORT', docNumber: '', docExpiryText: '' };
        clearError(`x-doc-${ref}`); clearError(`x-docNo-${ref}`); clearError(`x-exp-${ref}`);
      } else if (patch.docType !== undefined && patch.docType !== d.flight.docType) {
        flight = { ...flight, docNumber: '', docExpiryText: '' };
        clearError(`x-docNo-${ref}`); clearError(`x-exp-${ref}`);
      }
      return { ...d, flight };
    }));
  };

  const setFlightDate = (ref: string, key: 'docExpiryText', value: string, fieldId: string) => {
    const previous = drafts.find((d) => d.ref === ref)?.flight[key] ?? '';
    updateFlight(ref, { [key]: maskDmy(previous, value) }, fieldId);
  };

  const setBirthText = (ref: string, value: string) => {
    const previous = drafts.find((d) => d.ref === ref)?.birthText ?? '';
    updateDraft(ref, { birthText: maskDmy(previous, value) }, `dob-${ref}`);
  };

  const setContactFullName = (value: string) => {
    clearError('c-name');
    if (syncContact && adult1) {
      const [surname, givenNames] = splitFullName(value);
      updateDraft(adult1.ref, { surname, givenNames });
      setContactName(value);
    } else setContactName(value);
  };

  const setSyncContact = (on: boolean) => {
    if (on && adult1 && contactName.trim()) {
      const [surname, givenNames] = splitFullName(contactName);
      updateDraft(adult1.ref, { surname, givenNames });
    }
    if (!on) setContactName(contactFullName);
    setSyncContactState(on);
  };

  /** Kiểm một trường khi rời trường (blur): chỉ cập nhật lỗi của đúng trường đó. */
  const validateField = (id: string) => {
    const violations = partyViolations();
    const ctx = { travelerRefs: latest.current.drafts.map((d) => d.ref), cartItemIds: [], travelerLabels: labels, itemNames: {} };
    const mapped = mapValidationFields(violations.map((v) => ({ field: v.field, reason: v.reason, message: messageFor(v) })), ctx);
    setErrors((prev) => {
      const next = { ...prev };
      if (mapped.fieldErrors[id]) next[id] = mapped.fieldErrors[id]; else delete next[id];
      return next;
    });
  };

  // --- đồng bộ giỏ (PATCH) ------------------------------------------------------------------------------------------------------
  const writePatchErrors = (update: (prev: Record<string, ApiError>) => Record<string, ApiError>) => {
    const next = update(patchErrorsRef.current);
    patchErrorsRef.current = next;
    setPatchErrors(next);
  };

  /** Ghi số khách và số lượng mong muốn của một mục vào giỏ nếu Backend chưa có đúng giá trị đó. */
  const syncItem = async (cartItemId: string): Promise<void> => {
    const { items: nowItems, drafts: nowDrafts, allocs: nowAllocs } = latest.current;
    const item = nowItems.find((i) => i.cartItemId === cartItemId);
    const alloc = nowAllocs[cartItemId];
    if (!item || !alloc) return;
    const desired = desiredCartState(item, alloc, nowDrafts);
    if (!desired || sameCartState(sent.current[cartItemId] ?? cartStateOf(item), desired)) return;
    sent.current[cartItemId] = desired;
    const error = await updateCartItem(cartItemId, { guests: desired.guests, quantity: desired.quantity }, { silent: true });
    if (error) delete sent.current[cartItemId];
    writePatchErrors(({ [cartItemId]: _drop, ...rest }) => (error ? { ...rest, [cartItemId]: error } : rest));
  };
  useEffect(() => {
    queue.setHandlers({
      run: syncItem,
      onPending: (id, isPending) => {
        setPending((p) => ({ ...p, [id]: isPending }));
        if (!isPending) delete sent.current[id];
      },
    });
  });

  // --- bước ②: chỉnh phân bổ --------------------------------------------------------------------------------------------------------
  const editAlloc = (cartItemId: string, edit: (alloc: Allocation, item: ApiCartItem) => Allocation) => {
    const item = latest.current.items.find((i) => i.cartItemId === cartItemId);
    if (!item) return;
    setServerItemErrors((prev) => { const { [cartItemId]: _a, ...rest } = prev; return rest; });
    setServerRoomErrors((prev) => { const { [cartItemId]: _a, ...rest } = prev; return rest; });
    writePatchErrors(({ [cartItemId]: _a, ...rest }) => rest);
    const current = latest.current.allocs[cartItemId] ?? defaultAllocation(item, latest.current.drafts);
    const allocs = { ...latest.current.allocs, [cartItemId]: { ...edit(current, item), custom: true } };
    // Cập nhật ngay bản "mới nhất" để hai thao tác liên tiếp (trước khi React vẽ lại) không dẫm lên nhau.
    latest.current = { ...latest.current, allocs };
    setAllocs(allocs);
    queue.schedule(cartItemId);
  };

  const toggleTraveler = (cartItemId: string, ref: string) => editAlloc(cartItemId, (alloc) => ({
    ...alloc, refs: alloc.refs.includes(ref) ? alloc.refs.filter((r) => r !== ref) : [...alloc.refs, ref],
  }));

  const dropFromRooms = (rooms: RoomDraft[], ref: string) => rooms.map((r) => ({ ...r, refs: r.refs.filter((x) => x !== ref) }));

  const moveToRoom = (cartItemId: string, ref: string, roomIndex: number) => editAlloc(cartItemId, (alloc, item) => {
    const rooms = dropFromRooms(alloc.rooms, ref).map((r, k) => (k === roomIndex ? { ...r, refs: [...r.refs, ref] } : r));
    return { ...alloc, rooms: rooms.map((r) => fixLead(r, latest.current.drafts, item.usingDate)) };
  });

  const removeFromRoom = (cartItemId: string, ref: string) => editAlloc(cartItemId, (alloc, item) => ({
    ...alloc, rooms: dropFromRooms(alloc.rooms, ref).map((r) => fixLead(r, latest.current.drafts, item.usingDate)),
  }));

  const setLead = (cartItemId: string, roomIndex: number, ref: string) => editAlloc(cartItemId, (alloc) => ({
    ...alloc, rooms: alloc.rooms.map((r, k) => (k === roomIndex ? { ...r, lead: ref } : r)),
  }));

  const addRoom = (cartItemId: string) => editAlloc(cartItemId, (alloc, item) => {
    if (alloc.rooms.length >= MAX_ROOMS) return alloc;
    // Phòng mới nhận người lớn chưa đứng tên phòng nào (nút chỉ hiện khi còn người lớn như vậy).
    const leads = new Set(alloc.rooms.map((r) => r.lead));
    const spare = latest.current.drafts.find((d) => fareTypeOn(draftToTraveler(d), item.usingDate) === 'ADULT'
      && !alloc.rooms.some((r) => r.refs.includes(d.ref) && leads.has(d.ref)));
    const rooms = spare ? dropFromRooms(alloc.rooms, spare.ref) : alloc.rooms;
    const created: RoomDraft = spare ? { refs: [spare.ref], lead: spare.ref } : { refs: [], lead: null };
    return { ...alloc, rooms: [...rooms.map((r) => fixLead(r, latest.current.drafts, item.usingDate)), created] };
  });

  const removeRoom = (cartItemId: string) => editAlloc(cartItemId, (alloc, item) => {
    if (alloc.rooms.length <= 1) return alloc;
    const emptyIndex = alloc.rooms.findIndex((r) => r.refs.length === 0);
    const index = emptyIndex >= 0 ? emptyIndex : alloc.rooms.length - 1;
    const rooms = alloc.rooms.filter((_, k) => k !== index);
    return { ...alloc, rooms: rooms.map((r) => fixLead(r, latest.current.drafts, item.usingDate)) };
  });

  const setSpecialRequest = (cartItemId: string, value: string) => setSpecial((prev) => ({ ...prev, [cartItemId]: value.slice(0, 500) }));

  const removeItem = async (cartItemId: string) => {
    await source.removeItem(cartItemId);
  };

  // --- điều hướng bước ---------------------------------------------------------------------------------------------------------------
  const showSummary = (violations: Violation[], targetOf: (v: Violation) => { id: string; where: string }) => {
    const entries: SummaryEntry[] = violations.map((v) => { const t = targetOf(v); return { targetId: t.id, where: t.where, message: messageFor(v) }; });
    setSummary(entries);
    if (entries[0]) focusId(entries[0].targetId);
  };

  const continueFromTravelers = async () => {
    setNotice(null);
    const violations = partyViolations();
    if (violations.length) {
      const ctx = { travelerRefs: drafts.map((d) => d.ref), cartItemIds: [], travelerLabels: labels, itemNames: {} };
      const mapped = mapValidationFields(violations.map((v) => ({ field: v.field, reason: v.reason, message: messageFor(v) })), ctx);
      setErrors(mapped.fieldErrors);
      setSummary(mapped.summary);
      if (mapped.summary[0]) focusId(mapped.summary[0].targetId);
      return;
    }
    setErrors({});
    // Phân bổ mặc định cho mục chưa chỉnh, rồi ghi số khách vào giỏ từng mục một để giá cập nhật (§6.4).
    const recomputed = Object.fromEntries(latest.current.items.map((item) => [
      item.cartItemId, reconcileAllocation(item, latest.current.allocs[item.cartItemId] ?? defaultAllocation(item, drafts), drafts)]));
    latest.current = { ...latest.current, allocs: recomputed };
    setAllocs(recomputed);
    const todo = latest.current.items.filter((item) => {
      const desired = desiredCartState(item, recomputed[item.cartItemId], drafts);
      return desired && !sameCartState(sent.current[item.cartItemId] ?? cartStateOf(item), desired);
    });
    writePatchErrors(() => ({}));
    try {
      let index = 0;
      for (const item of todo) {
        index += 1;
        setBusy(`Đang cập nhật giá (${index}/${todo.length})…`);
        await queue.enqueue(item.cartItemId);
      }
      // Tải giỏ mới về trước khi sang bước sau để thẻ dịch vụ hiện đúng giá ngay từ lần vẽ đầu.
      if (todo.length) await refreshCart();
    } finally {
      setBusy(null);
    }
    setDone((d) => ({ ...d, travelers: true }));
    goto('services', { refresh: false });
  };

  const continueFromServices = async () => {
    setBusy('Đang cập nhật giá…');
    try {
      await queue.flush();
      // Kiểm phân bổ với giỏ Backend đang có (không phải bản React chưa kịp vẽ lại sau PATCH).
      const fresh = await refreshCart();
      const nowItems = fresh ? sortItems(fresh.items) : latest.current.items;
      const violations = nowItems.length
        ? checkItems(latest.current.drafts.map(draftToTraveler), itemInputsOf(nowItems, latest.current.allocs, latest.current.drafts), nowItems.map(cartFactsOf))
        : [];
      const failures = Object.entries(patchErrorsRef.current);
      if (violations.length || failures.length) {
        const targetOf = (v: Violation) => {
          const item = nowItems.find((i) => i.cartItemId === v.cartItemId);
          const room = /rooms\[(\d+)\]/.exec(v.field);
          return { id: v.cartItemId ? (room ? `room-${v.cartItemId}-${room[1]}` : `card-${v.cartItemId}`) : 'checkout-top', where: item?.product.name ?? 'Dịch vụ' };
        };
        const entries: SummaryEntry[] = [
          ...violations.map((v) => { const t = targetOf(v); return { targetId: t.id, where: t.where, message: messageFor(v) }; }),
          ...failures.map(([id, e]) => ({ targetId: `card-${id}`, where: nowItems.find((i) => i.cartItemId === id)?.product.name ?? 'Dịch vụ', message: e.message })),
        ];
        setSummary(entries);
        if (entries[0]) focusId(entries[0].targetId);
        return;
      }
      setDone((d) => ({ ...d, services: true }));
      goto('review', { refresh: false });
    } finally {
      setBusy(null);
    }
  };

  // --- bước ③: thanh toán ------------------------------------------------------------------------------------------------------------------
  const itemName = (productId?: string) => latest.current.items.find((i) => i.product.productId === productId)?.product.name ?? 'Một dịch vụ';

  const buildRequest = (): CheckoutRequest => {
    const { items: nowItems, drafts: nowDrafts, allocs: nowAllocs } = latest.current;
    const details = itemInputsOf(nowItems, nowAllocs, nowDrafts).map((d) => {
      const note = normalizeName(special[d.cartItemId] ?? '');
      return {
        cartItemId: d.cartItemId,
        ...(d.travelerRefs ? { travelerRefs: d.travelerRefs } : {}),
        ...(d.rooms ? { rooms: d.rooms.map((r) => ({ travelerRefs: r.travelerRefs, leadTravelerRef: r.leadTravelerRef ?? '' })) } : {}),
        ...(note ? { specialRequest: note } : {}),
      };
    });
    return {
      // Có draftId thì Backend thanh toán đúng đơn nháp này, không kèm mục nào trong giỏ (R-CHK-01).
      ...(source.draftId ? { draftId: source.draftId } : {}),
      contact: { fullName: normalizeName(contactFullName), email: personaRef.current?.email ?? email, phone: phone.trim() },
      travelers: toTravelerInputs(nowDrafts, hasFlight).map((t) => ({
        travelerRef: t.travelerRef, type: t.type, surname: normalizeName(t.surname), givenNames: normalizeName(t.givenNames),
        ...(t.birthDate ? { birthDate: t.birthDate } : {}),
        ...(t.documents ? { documents: t.documents } : {}),
      })) as CheckoutRequest['travelers'],
      itemDetails: details,
    };
  };

  const showError = async (error: unknown, request: CheckoutRequest) => {
    if (!(error instanceof ApiError)) {
      setBanner({ kind: 'error', text: 'Có lỗi xảy ra. Vui lòng thử lại.', retryable: true, requestId: null });
      return;
    }
    // Đơn nháp hết hạn hoặc không còn: chuyển sang màn hình hết hạn / không tìm thấy (R-DRF-20, R-CHK-04).
    if (source.fail(error)) return;
    const details = error.details ?? {};
    switch (error.code) {
      case 'CART_EMPTY':
        navigate('/cart');
        return;
      case 'BOOKING_PENDING_PAYMENT':
        setPendingHold({ referenceCode: details.referenceCode, holdExpiresAt: details.holdExpiresAt ?? null });
        return;
      case 'PRICE_CHANGED': {
        const item = latest.current.items.find((i) => i.product.productId === details.productId);
        setBanner({ kind: 'price', cartItemId: item?.cartItemId ?? null, name: itemName(details.productId),
          oldPrice: details.oldPrice, newPrice: details.newPrice, fareType: details.fareType === 'CHILD' ? 'CHILD' : 'ADULT' });
        return;
      }
      case 'PRODUCT_UNAVAILABLE':
        setBanner({ kind: 'unavailable', name: itemName(details.productId), text: `${itemName(details.productId)} vừa hết chỗ.` });
        return;
      case 'DATE_OUT_OF_RANGE':
        setBanner({ kind: 'date', name: itemName(details.productId), text: `Ngày sử dụng của ${itemName(details.productId)} nằm ngoài thời gian mở bán`
          + (details.availableFrom ? ` (${details.availableFrom} – ${details.availableTo}).` : '.') });
        return;
      case 'VALIDATION_ERROR': {
        const fields = Array.isArray(details.fields) ? details.fields : [];
        const mapped = mapValidationFields(fields, {
          travelerRefs: (request.travelers ?? []).map((t) => t.travelerRef),
          cartItemIds: request.itemDetails.map((d) => d.cartItemId), travelerLabels: labels,
          itemNames: Object.fromEntries(latest.current.items.map((i) => [i.cartItemId, i.product.name])),
        });
        if (mapped.step === null) {
          setBanner({ kind: 'error', text: error.message, retryable: false, requestId: error.requestId });
          return;
        }
        if (mapped.mismatchedItems.length) {
          // Số khách đã thay đổi so với giá khách đã thấy: tải lại giỏ, tính lại phân bổ cho các mục đó, về bước Dịch vụ.
          const fresh = await refreshCart();
          setAllocs((prev) => {
            const next = { ...prev };
            for (const id of mapped.mismatchedItems) {
              const item = fresh?.items.find((i) => i.cartItemId === id);
              if (item) next[id] = defaultAllocation(item, latest.current.drafts);
            }
            return next;
          });
          setNotice('Số khách của một số dịch vụ vừa thay đổi. Vui lòng xem lại giá.');
        }
        if (mapped.step === 'travelers') setDone({ travelers: false, services: false });
        else setDone((d) => ({ ...d, services: false }));
        // `goto` xoá hộp tóm tắt lỗi của bước cũ, nên phải chuyển bước trước rồi mới ghi lỗi của server.
        goto(mapped.step, { replace: true });
        setBanner(null);
        setErrors(mapped.fieldErrors);
        setServerItemErrors(mapped.itemErrors);
        setServerRoomErrors(mapped.roomErrors);
        setSummary(mapped.summary);
        if (mapped.summary[0]) focusId(mapped.summary[0].targetId);
        return;
      }
      case 'PAYMENT_PROVIDER_UNAVAILABLE':
        setBanner({ kind: 'error', text: 'Cổng thanh toán tạm thời không phản hồi. Vui lòng thử lại.', retryable: true, requestId: error.requestId });
        return;
      default:
        setBanner({ kind: 'error', text: error.code === 'NETWORK_ERROR' ? 'Mất kết nối. Vui lòng thử lại.' : error.message,
          retryable: error.retryable, requestId: error.requestId });
    }
  };

  // Bản `pay` mới nhất cho callback sau đăng nhập.
  const payRef = useRef<() => Promise<void>>(async () => undefined);

  const pay = async () => {
    if (submitting || !termsAgreed || hasUnavailable || method !== 'stripe') return;
    if (!personaRef.current) {
      // Tạo đơn luôn cần đăng nhập (R-CHK-06). Hộp đăng nhập mở ngay trên trang nên thông tin đã nhập còn nguyên; đăng nhập xong
      // thì gửi tiếp, BFF gộp giỏ và đơn nháp của khách vào tài khoản trước khi chuyển tiếp request.
      openLoginModal(() => { window.setTimeout(() => void payRef.current(), 0); });
      return;
    }
    setSubmitting(true);
    setBanner(null);
    const request = buildRequest();
    try {
      const booking: BookingResponse = await bookingApi.createBooking(request);
      rememberBooking(booking);
      // Giữ nút ở trạng thái đang xử lý trong lúc trình duyệt rời sang trang Stripe.
      if (booking.payment?.checkoutUrl) bookingApi.redirectToCheckout(booking.payment.checkoutUrl);
      else navigate(`/booking/${booking.referenceCode}`);
    } catch (error) {
      await showError(error, request);
      setSubmitting(false);
    }
  };

  useEffect(() => { payRef.current = pay; });

  /** Rời trang thanh toán: nguồn giỏ về trang giỏ; nguồn đơn nháp về trang trước (trang sản phẩm, vé máy bay, trợ lý). */
  const leave = () => {
    if (source.kind === 'cart') navigate('/cart');
    else if (typeof window !== 'undefined' && window.history.length > 1) window.history.back();
    else navigate('/');
  };

  const acceptNewPrice = async () => {
    if (banner?.kind !== 'price') return;
    const item = latest.current.items.find((i) => i.cartItemId === banner.cartItemId);
    // PATCH ghi lại giá snapshot (người lớn và trẻ em) bằng giá hiện tại: khách đã thấy giá mới, lần bấm sau không còn PRICE_CHANGED.
    if (item) await updateCartItem(item.cartItemId, { quantity: item.quantity }, { silent: true });
    else await refreshCart();
    setBanner(null);
  };

  const continuePending = async () => {
    if (!pendingHold) return;
    try {
      const held = await bookingApi.getBooking(pendingHold.referenceCode);
      rememberBooking(held);
      if (held.status === 'PENDING_PAYMENT' && held.payment?.checkoutUrl) {
        bookingApi.redirectToCheckout(held.payment.checkoutUrl);
        return;
      }
    } catch {
      // Đọc đơn lỗi thì vẫn mở trang đơn để khách xem trạng thái.
    }
    navigate(`/booking/${pendingHold.referenceCode}`);
  };

  const cancelPendingAndRetry = async () => {
    if (!pendingHold) return;
    const request = buildRequest();
    try {
      rememberBooking(await bookingApi.cancelBooking(pendingHold.referenceCode, 'Đặt lại'));
      setPendingHold(null);
      await pay();
    } catch (error) {
      setPendingHold(null);
      await showError(error, request);
    }
  };

  return {
    // dữ liệu
    cart, items, email, currentPersona, authReady, earliest, facts, partyCap,
    sourceKind: source.kind, sourceStatus: source.status, draftId: source.draftId, draftExpiresAt: source.expiresAt,
    expiredItems: source.expiredItems, leave,
    drafts, travelers, hasFlight, flightDates, isInfant, contactFullName, phone, syncContact, allocs, special, confirmRemove,
    step, done, errors, summary, serverItemErrors, serverRoomErrors, itemViolations, patchErrors, busy, pending, anyPending,
    notice, cartChanged, banner, pendingHold, termsAgreed, method, submitting, hasUnavailable, labels,
    // hành động
    goto, focusId, addTraveler, removeTraveler, setConfirmRemove, updateDraft, updateFlight, setFlightDate, setBirthText, setContactFullName, setPhone: (v: string) => { clearError('c-phone'); setPhone(v.replace(/\s+/g, '')); },
    setSyncContact, validateField, toggleTraveler, moveToRoom, removeFromRoom, setLead, addRoom, removeRoom, setSpecialRequest,
    removeItem, continueFromTravelers, continueFromServices, setTermsAgreed, setMethod, pay, acceptNewPrice, continuePending,
    cancelPendingAndRetry, setPendingHold, setBanner, dismissCartChanged: () => setCartChanged(false), navigate, refreshCart,
    openLoginModal,
    displayNameOf: (d: TravelerDraft) => displayName(d, drafts), parseDob: parseDmy,
    refsOfItem: (item: ApiCartItem) => refsOf(item, allocs[item.cartItemId] ?? { refs: [], rooms: [], custom: false }),
    guestsOfAlloc: (item: ApiCartItem) => guestsFromAllocation(item, allocs[item.cartItemId] ?? { refs: [], rooms: [], custom: false }, drafts),
  };
}

export type CheckoutController = ReturnType<typeof useCheckout>;
