'use client';

/** Bước ① Hành khách (spec checkout-nhieu-buoc-hanh-khach.md §6.4): đoàn khách, họ tên, ngày sinh trẻ em, người liên hệ. */
import React from 'react';
import { ArrowRight, Baby, FileText, Info, Plane, User } from 'lucide-react';
import { MAX_PARTY, ageOn, formatDmy, normalizeName } from './checkoutRules';
import { displayName, partyCounts, ticketName, travelerLabel, type TravelerDraft } from './allocation';
import { CounterRow, ErrorSummaryBox, Field, Notice, PrimaryButton, SectionTitle, cardClass, inputClass } from './CheckoutParts';
import type { CheckoutController } from './useCheckout';

const TITLES_ADULT: Array<[string, string]> = [['MR', 'Ông'], ['MRS', 'Bà'], ['MS', 'Cô']];
const TITLES_CHILD: Array<[string, string]> = [['MSTR', 'Bé trai'], ['MISS', 'Bé gái']];
const NATIONALITIES: Array<[string, string]> = [
  ['VN', 'Việt Nam'], ['KR', 'Hàn Quốc'], ['CN', 'Trung Quốc'], ['JP', 'Nhật Bản'], ['US', 'Hoa Kỳ'], ['AU', 'Úc'], ['FR', 'Pháp'],
  ['OTHER', 'Quốc tịch khác'],
];

/** Nhóm nút chọn một (radio ẩn, nhãn là nút) cho danh xưng và loại giấy tờ; lỗi và nhãn nối qua aria. */
const SegRadio: React.FC<{
  id: string; labelId: string; options: Array<[string, string, boolean?]>; value: string; invalid: boolean; onChange: (value: string) => void;
}> = ({ id, labelId, options, value, invalid, onChange }) => (
  <div id={id} role="radiogroup" tabIndex={-1} aria-labelledby={labelId} aria-describedby={`e-${id}`} className="flex flex-wrap gap-2 outline-hidden">
    {options.map(([v, text, disabled]) => (
      <label key={v} htmlFor={`${id}-${v}`}
        className={`rounded-lg border px-3.5 h-9 inline-flex items-center text-sm font-semibold has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-brand-500 ${
          disabled ? 'opacity-40 cursor-not-allowed border-slate-300 bg-white text-slate-700'
            : `cursor-pointer ${value === v ? 'border-brand-600 bg-brand-50 text-brand-800' : invalid ? 'border-rose-300 bg-white text-slate-700' : 'border-slate-300 bg-white text-slate-700 hover:border-brand-400'}`}`}>
        <input type="radio" className="sr-only" id={`${id}-${v}`} name={id} value={v} checked={value === v} disabled={disabled} onChange={() => onChange(v)} />
        {text}
      </label>
    ))}
  </div>
);

const ErrorLine: React.FC<{ id: string; error?: string }> = ({ id, error }) => (
  <p id={`e-${id}`} aria-live="polite" className="text-xs text-rose-600 font-medium" hidden={!error}>{error}</p>
);

/** Khối "Thông tin cho vé máy bay" của một hành khách (FR-BKG-13): nhập một lần, dùng cho mọi chặng. */
const FlightFields: React.FC<{ ctl: CheckoutController; draft: TravelerDraft }> = ({ ctl, draft }) => {
  const f = draft.flight;
  const adult = draft.type === 'ADULT';
  const infant = !adult && ctl.isInfant(draft);
  const id = (key: string) => `${key}-${draft.ref}`;
  const titleId = id('x-title'), docId = id('x-doc'), dobId = id('dob');
  const escorts = ctl.drafts.filter((d) => d.type === 'ADULT');
  return (
    <div className="rounded-lg border border-brand-100 bg-white p-3.5 space-y-3" data-testid="flight-fields">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <span className="text-xs font-bold text-brand-800 flex items-center gap-1.5"><Plane className="w-3.5 h-3.5" aria-hidden="true" />Thông tin cho vé máy bay</span>
        <span className="text-[11px] text-slate-500">Hãng bay yêu cầu · dùng cho mọi chặng</span>
      </div>
      <div className="space-y-1.5">
        <span id={`lb-${titleId}`} className="block text-xs font-semibold text-slate-700">Danh xưng *</span>
        <SegRadio id={titleId} labelId={`lb-${titleId}`} options={adult ? TITLES_ADULT : TITLES_CHILD} value={f.title} invalid={Boolean(ctl.errors[titleId])}
          onChange={(v) => ctl.updateFlight(draft.ref, { title: v }, titleId)} />
        <ErrorLine id={titleId} error={ctl.errors[titleId]} />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {adult && (
          <Field id={dobId} label="Ngày sinh (dd/mm/yyyy) *" error={ctl.errors[dobId]}>
            {(aria) => (
              <input {...aria} type="text" inputMode="numeric" autoComplete="off" maxLength={10} placeholder="dd/mm/yyyy" value={draft.birthText}
                aria-label={`Ngày sinh (${travelerLabel(draft, ctl.drafts)})`} className={`${inputClass(aria['aria-invalid'])} tabular-nums`}
                onChange={(e) => ctl.setBirthText(draft.ref, e.target.value)} onBlur={() => ctl.validateField(dobId)} />
            )}
          </Field>
        )}
        <Field id={id('x-nat')} label="Quốc tịch *" error={ctl.errors[id('x-nat')]}>
          {(aria) => (
            <select {...aria} value={f.nationality} className={inputClass(aria['aria-invalid'])}
              onChange={(e) => ctl.updateFlight(draft.ref, { nationality: e.target.value }, id('x-nat'))}>
              {NATIONALITIES.map(([v, text]) => <option key={v} value={v}>{text}</option>)}
            </select>
          )}
        </Field>
      </div>
      {adult && (
        <>
          <div className="space-y-1.5">
            <span id={`lb-${docId}`} className="block text-xs font-semibold text-slate-700">Giấy tờ tuỳ thân *</span>
            <SegRadio id={docId} labelId={`lb-${docId}`} value={f.docType} invalid={Boolean(ctl.errors[docId])}
              options={[['CCCD', 'CCCD', f.nationality !== 'VN'], ['PASSPORT', 'Hộ chiếu']]}
              onChange={(v) => ctl.updateFlight(draft.ref, { docType: v as 'CCCD' | 'PASSPORT' }, docId)} />
            <ErrorLine id={docId} error={ctl.errors[docId]} />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field id={id('x-docNo')} label={f.docType === 'CCCD' ? 'Số CCCD *' : 'Số hộ chiếu *'} error={ctl.errors[id('x-docNo')]}>
              {(aria) => (
                <input {...aria} type="text" autoComplete="off" value={f.docNumber} aria-label={`Số giấy tờ (${travelerLabel(draft, ctl.drafts)})`}
                  inputMode={f.docType === 'CCCD' ? 'numeric' : 'text'} maxLength={f.docType === 'CCCD' ? 12 : 9}
                  placeholder={f.docType === 'CCCD' ? '12 chữ số' : 'Ví dụ: C1234567'} className={`${inputClass(aria['aria-invalid'])} tabular-nums uppercase`}
                  onChange={(e) => ctl.updateFlight(draft.ref, { docNumber: e.target.value }, id('x-docNo'))} onBlur={() => ctl.validateField(id('x-docNo'))} />
              )}
            </Field>
            {f.docType === 'PASSPORT' && (
              <Field id={id('x-exp')} label="Ngày hết hạn (dd/mm/yyyy) *" error={ctl.errors[id('x-exp')]}>
                {(aria) => (
                  <input {...aria} type="text" inputMode="numeric" autoComplete="off" maxLength={10} placeholder="dd/mm/yyyy" value={f.docExpiryText}
                    aria-label={`Ngày hết hạn hộ chiếu (${travelerLabel(draft, ctl.drafts)})`} className={`${inputClass(aria['aria-invalid'])} tabular-nums`}
                    onChange={(e) => ctl.setFlightDate(draft.ref, 'docExpiryText', e.target.value, id('x-exp'))} onBlur={() => ctl.validateField(id('x-exp'))} />
                )}
              </Field>
            )}
          </div>
        </>
      )}
      {!adult && (
        <p className="text-xs text-slate-500 flex items-start gap-1.5">
          <FileText className="w-3.5 h-3.5 shrink-0 mt-0.5" aria-hidden="true" />
          Trẻ em, em bé dùng giấy khai sinh khi làm thủ tục, không cần nhập số giấy tờ. Ngày sinh lấy từ ô phía trên.
        </p>
      )}
      {infant && (
        <Field id={id('x-with')} label="Người lớn đi kèm em bé *" error={ctl.errors[id('x-with')]} hint="Bé dưới 2 tuổi tại ngày bay. Mỗi người lớn đi kèm tối đa 1 em bé.">
          {(aria) => (
            <select {...aria} value={f.escortRef} className={inputClass(aria['aria-invalid'])}
              onChange={(e) => ctl.updateFlight(draft.ref, { escortRef: e.target.value }, id('x-with'))}>
              <option value="">Chọn người lớn</option>
              {escorts.map((a) => <option key={a.ref} value={a.ref}>{displayName(a, ctl.drafts)}</option>)}
            </select>
          )}
        </Field>
      )}
      <div className="text-xs text-slate-600 rounded-lg border border-dashed border-slate-300 px-3 py-2">
        Tên in trên vé: <b className="font-mono tracking-wide text-slate-900">{ticketName(draft)}</b>
      </div>
    </div>
  );
};

const TravelerCard: React.FC<{ ctl: CheckoutController; draft: TravelerDraft }> = ({ ctl, draft }) => {
  const label = travelerLabel(draft, ctl.drafts);
  const isLead = ctl.syncContact && ctl.drafts.find((d) => d.type === 'ADULT')?.ref === draft.ref;
  const ids = { sn: `sn-${draft.ref}`, gn: `gn-${draft.ref}`, dob: `dob-${draft.ref}` };
  const birth = draft.type === 'CHILD' ? ctl.parseDob(draft.birthText) : null;
  const ageHint = birth && ctl.earliest && !ctl.errors[ids.dob] && birth <= ctl.earliest
    ? `${ageOn(birth, ctl.earliest)} tuổi vào ${formatDmy(ctl.earliest)} (ngày sử dụng sớm nhất)` : undefined;
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-4 space-y-3" data-testid="traveler-card">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className={`w-7 h-7 rounded-full flex items-center justify-center ${draft.type === 'ADULT' ? 'bg-brand-100 text-brand-700' : 'bg-amber-100 text-amber-800'}`}>
            {draft.type === 'ADULT' ? <User className="w-4 h-4" aria-hidden="true" /> : <Baby className="w-4 h-4" aria-hidden="true" />}
          </span>
          <span className="text-sm font-bold text-slate-900">{label}</span>
        </div>
        {isLead && <span className="text-[11px] font-semibold text-brand-700 bg-brand-50 border border-brand-200 rounded-md px-1.5 py-0.5">Là người liên hệ</span>}
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Field id={ids.sn} label="Họ *" error={ctl.errors[ids.sn]}>
          {(aria) => (
            <input {...aria} type="text" maxLength={50} autoComplete="off" placeholder="Ví dụ: Nguyễn" value={draft.surname}
              aria-label={`Họ (${label})`} className={inputClass(aria['aria-invalid'])}
              onChange={(e) => ctl.updateDraft(draft.ref, { surname: e.target.value }, ids.sn)} onBlur={() => ctl.validateField(ids.sn)} />
          )}
        </Field>
        <Field id={ids.gn} label="Tên đệm và tên *" error={ctl.errors[ids.gn]}>
          {(aria) => (
            <input {...aria} type="text" maxLength={50} autoComplete="off" placeholder="Ví dụ: Minh Anh" value={draft.givenNames}
              aria-label={`Tên đệm và tên (${label})`} className={inputClass(aria['aria-invalid'])}
              onChange={(e) => ctl.updateDraft(draft.ref, { givenNames: e.target.value }, ids.gn)} onBlur={() => ctl.validateField(ids.gn)} />
          )}
        </Field>
        {draft.type === 'CHILD' && (
          <Field id={ids.dob} label="Ngày sinh (dd/mm/yyyy) *" error={ctl.errors[ids.dob]} hint={ageHint}>
            {(aria) => (
              <input {...aria} type="text" inputMode="numeric" autoComplete="off" maxLength={10} placeholder="dd/mm/yyyy" value={draft.birthText}
                aria-label={`Ngày sinh (${label})`} className={`${inputClass(aria['aria-invalid'])} tabular-nums`}
                onChange={(e) => ctl.setBirthText(draft.ref, e.target.value)} onBlur={() => ctl.validateField(ids.dob)} />
            )}
          </Field>
        )}
      </div>
      {ctl.hasFlight && <FlightFields ctl={ctl} draft={draft} />}
    </div>
  );
};

export const TravelersStep: React.FC<{ ctl: CheckoutController }> = ({ ctl }) => {
  const counts = partyCounts(ctl.drafts);
  const total = counts.adults + counts.children;
  const adults = ctl.drafts.filter((d) => d.type === 'ADULT');
  const kids = ctl.drafts.filter((d) => d.type === 'CHILD');
  const seen = new Set<string>();
  const duplicates: string[] = [];
  for (const d of ctl.drafts) {
    const key = normalizeName(`${d.surname} ${d.givenNames}`).toLowerCase();
    if (!key) continue;
    if (seen.has(key) && !duplicates.includes(key)) duplicates.push(normalizeName(`${d.surname} ${d.givenNames}`));
    seen.add(key);
  }
  const removing = ctl.drafts.find((d) => d.ref === ctl.confirmRemove);
  return (
    <>
      <div className="space-y-1">
        <h2 id="step-heading" tabIndex={-1} className="text-xl font-extrabold text-slate-900 outline-hidden">Hành khách</h2>
        <p className="text-sm text-slate-500">Khai đoàn một lần. Ở bước sau bạn chọn ai dùng từng dịch vụ.</p>
      </div>
      {ctl.notice && <Notice>{ctl.notice}</Notice>}
      <ErrorSummaryBox entries={ctl.summary} onJump={ctl.focusId} />

      <section className={cardClass} aria-label="Đoàn khách">
        <SectionTitle title="Ai đi chuyến này?" />
        <div className="divide-y divide-slate-100" id="party-counters">
          <CounterRow
            label="Người lớn" hint="Từ 12 tuổi" value={counts.adults} canDec={counts.adults > 1} canInc={total < MAX_PARTY}
            decLabel="Bớt người lớn" incLabel="Thêm người lớn" onDec={() => ctl.removeTraveler('ADULT')} onInc={() => ctl.addTraveler('ADULT')}
          />
          <CounterRow
            label="Trẻ em" hint="Dưới 12 tuổi" value={counts.children} canDec={counts.children > 0} canInc={total < MAX_PARTY}
            decLabel="Bớt trẻ em" incLabel="Thêm trẻ em" onDec={() => ctl.removeTraveler('CHILD')} onInc={() => ctl.addTraveler('CHILD')}
          />
        </div>
        {ctl.errors['party-counters'] && <p className="text-xs text-rose-600 font-medium" role="alert">{ctl.errors['party-counters']}</p>}
        <p className="text-xs text-slate-500">Tối đa 9 khách mỗi đơn.</p>
      </section>

      <section className={cardClass} aria-label="Thông tin hành khách">
        <SectionTitle title="Thông tin hành khách" />
        <div className="flex items-start gap-2 rounded-xl bg-brand-50 border border-brand-100 px-3.5 py-3 text-xs text-brand-900">
          <Info className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
          <span>
            Nhập đúng họ tên như trên CCCD, hộ chiếu hoặc giấy khai sinh. Hãng bay, khách sạn có thể từ chối nếu tên sai.
            {ctl.hasFlight && ' Đơn có vé máy bay nên mỗi khách cần thêm vài thông tin cho hãng bay; bạn chỉ nhập một lần ở đây.'}
          </span>
        </div>
        <div className="space-y-3">
          {adults.map((d) => <TravelerCard key={d.ref} ctl={ctl} draft={d} />)}
          {kids.map((d) => <TravelerCard key={d.ref} ctl={ctl} draft={d} />)}
        </div>
        {duplicates.length > 0 && (
          <Notice>{duplicates.map((n) => `Có hai hành khách cùng tên ${n}. Kiểm tra lại nếu nhập nhầm.`).join(' ')}</Notice>
        )}
      </section>

      <section className={cardClass} aria-label="Người liên hệ">
        <SectionTitle title="Người liên hệ" />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field id="c-name" label="Họ và tên *" error={ctl.errors['c-name']}>
            {(aria) => (
              <input {...aria} type="text" maxLength={100} autoComplete="name" value={ctl.contactFullName} aria-label="Họ và tên người liên hệ"
                className={inputClass(aria['aria-invalid'])} onChange={(e) => ctl.setContactFullName(e.target.value)} onBlur={() => ctl.validateField('c-name')} />
            )}
          </Field>
          <Field id="c-phone" label="Số điện thoại *" error={ctl.errors['c-phone']}>
            {(aria) => (
              <input {...aria} type="tel" inputMode="numeric" autoComplete="tel" placeholder="0912345678" value={ctl.phone} aria-label="Số điện thoại"
                className={`${inputClass(aria['aria-invalid'])} tabular-nums`} onChange={(e) => ctl.setPhone(e.target.value)} onBlur={() => ctl.validateField('c-phone')} />
            )}
          </Field>
          <div className="sm:col-span-2">
            <Field id="c-email" label="Email nhận thông tin (theo tài khoản)" error={ctl.errors['c-email']}>
              {(aria) => (
                <input {...aria} type="email" disabled value={ctl.email} aria-label="Email"
                  placeholder={ctl.currentPersona ? undefined : 'Lấy theo tài khoản khi bạn đăng nhập'}
                  className="w-full px-3 h-10 text-sm bg-slate-100 border border-slate-300 rounded-lg text-slate-500 cursor-not-allowed" readOnly />
              )}
            </Field>
            {!ctl.currentPersona && (
              <p className="mt-1 text-[11px] text-slate-500" data-testid="guest-email-note">
                Bạn chưa đăng nhập. Cứ điền thông tin trước; khi bấm Thanh toán, bạn sẽ đăng nhập và email của tài khoản được dùng để nhận xác nhận.
              </p>
            )}
          </div>
        </div>
        <label htmlFor="c-sync" className="flex items-center gap-2.5 text-sm text-slate-700 cursor-pointer">
          <input id="c-sync" type="checkbox" checked={ctl.syncContact} onChange={(e) => ctl.setSyncContact(e.target.checked)} className="w-4 h-4 accent-brand-600" />
          Người liên hệ cũng là Người lớn 1
        </label>
      </section>

      <div className="hidden lg:flex justify-end">
        <PrimaryButton onClick={() => void ctl.continueFromTravelers()} busy={ctl.busy}>Tiếp tục <ArrowRight className="w-4 h-4" aria-hidden="true" /></PrimaryButton>
      </div>

      {removing && (
        <div role="dialog" aria-modal="true" aria-label="Xác nhận bỏ khách" className="fixed inset-0 z-50 bg-slate-900/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6 space-y-4">
            <h3 className="text-base font-bold text-slate-900">Bỏ {travelerLabel(removing, ctl.drafts)} khỏi đoàn?</h3>
            <p className="text-sm text-slate-600">Thông tin đã nhập của <b>{normalizeName(`${removing.surname} ${removing.givenNames}`) || travelerLabel(removing, ctl.drafts)}</b> sẽ bị xoá.</p>
            <div className="flex gap-2 justify-end">
              <button type="button" onClick={() => ctl.setConfirmRemove(null)} className="px-4 py-2 text-sm font-semibold text-slate-700 border border-slate-300 rounded-xl hover:bg-slate-50">Giữ lại</button>
              <button type="button" onClick={() => ctl.removeTraveler(removing.type, true)} className="px-4 py-2 text-sm font-bold text-white bg-rose-600 hover:bg-rose-700 rounded-xl">Bỏ khách</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
