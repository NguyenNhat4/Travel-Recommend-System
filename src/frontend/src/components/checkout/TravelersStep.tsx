'use client';

/** Bước ① Hành khách (spec checkout-nhieu-buoc-hanh-khach.md §6.4): đoàn khách, họ tên, ngày sinh trẻ em, người liên hệ. */
import React from 'react';
import { ArrowRight, Baby, Info, User } from 'lucide-react';
import { MAX_PARTY, ageOn, formatDmy, normalizeName } from './checkoutRules';
import { partyCounts, travelerLabel, type TravelerDraft } from './allocation';
import { CounterRow, ErrorSummaryBox, Field, Notice, PrimaryButton, SectionTitle, cardClass, inputClass } from './CheckoutParts';
import type { CheckoutController } from './useCheckout';

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
          <span className={`w-7 h-7 rounded-full flex items-center justify-center ${draft.type === 'ADULT' ? 'bg-blue-100 text-blue-700' : 'bg-amber-100 text-amber-800'}`}>
            {draft.type === 'ADULT' ? <User className="w-4 h-4" aria-hidden="true" /> : <Baby className="w-4 h-4" aria-hidden="true" />}
          </span>
          <span className="text-sm font-bold text-slate-900">{label}</span>
        </div>
        {isLead && <span className="text-[11px] font-semibold text-blue-700 bg-blue-50 border border-blue-200 rounded-md px-1.5 py-0.5">Là người liên hệ</span>}
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
        <div className="flex items-start gap-2 rounded-xl bg-blue-50 border border-blue-100 px-3.5 py-3 text-xs text-blue-900">
          <Info className="w-4 h-4 shrink-0 mt-0.5" aria-hidden="true" />
          <span>Nhập đúng họ tên như trên CCCD, hộ chiếu hoặc giấy khai sinh. Hãng bay, khách sạn có thể từ chối nếu tên sai.</span>
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
                  className="w-full px-3 h-10 text-sm bg-slate-100 border border-slate-300 rounded-lg text-slate-500 cursor-not-allowed" readOnly />
              )}
            </Field>
          </div>
        </div>
        <label htmlFor="c-sync" className="flex items-center gap-2.5 text-sm text-slate-700 cursor-pointer">
          <input id="c-sync" type="checkbox" checked={ctl.syncContact} onChange={(e) => ctl.setSyncContact(e.target.checked)} className="w-4 h-4 accent-blue-600" />
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
