'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Check, Loader2, LockKeyhole, LogIn } from 'lucide-react';
import { useTravel } from '../../context/TravelContext';
import * as authApi from '../../services/auth';
import { ApiError } from '../../services/http';
import { SkeletonBlock, SkeletonStatus } from '../../components/common/Skeleton';
import {
  NAME_MAX, isDirty, profileChanges, validatePassword, validateProfile,
  type PasswordErrors, type PasswordForm, type ProfileForm,
} from './profileModel';

const INPUT = 'min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3 text-sm text-slate-900 hover:border-slate-500 focus-visible:border-brand-600 focus-visible:outline-2 focus-visible:outline-brand-300 aria-[invalid=true]:border-rose-600 read-only:cursor-not-allowed read-only:border-slate-200 read-only:bg-slate-100 read-only:text-slate-500';
const BTN_PRIMARY = 'inline-flex min-h-11 items-center justify-center gap-2 rounded-full bg-brand-600 px-5 text-[13px] font-semibold text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-45';
const BTN_SECONDARY = 'inline-flex min-h-11 items-center justify-center gap-2 rounded-full border border-slate-200 bg-white px-5 text-[13px] font-semibold text-slate-800 hover:border-brand-600 hover:text-brand-700 disabled:cursor-not-allowed disabled:opacity-45';

const Card: React.FC<{ id: string; title: string; children: React.ReactNode }> = ({ id, title, children }) => (
  <section aria-labelledby={id} className="rounded-2xl border border-slate-200 bg-white">
    <h2 id={id} className="px-5 pt-4 text-base font-semibold text-slate-900">{title}</h2>
    <div className="px-5 pb-5 pt-4">{children}</div>
  </section>
);

/** Khung chờ khi phiên đang khôi phục: tiêu đề, thẻ "Thông tin cá nhân" ba ô và thẻ "Mật khẩu", đúng bố cục khi đã tải. */
const ProfileSkeleton: React.FC = () => (
  <SkeletonStatus label="Đang tải hồ sơ" className="grid gap-4">
    <div className="space-y-1.5">
      <SkeletonBlock className="h-7 w-48 rounded-lg" />
      <SkeletonBlock className="h-4 w-72 max-w-full rounded" />
    </div>
    <div className="rounded-2xl border border-slate-200 bg-white px-5 pb-5 pt-4">
      <SkeletonBlock className="h-5 w-40 rounded" />
      <div className="grid max-w-[30rem] gap-4 pt-4">
        {[0, 1, 2].map((i) => (
          <div key={i} className="grid gap-1.5">
            <SkeletonBlock className="h-4 w-28 rounded" />
            <SkeletonBlock className="h-11 w-full rounded-xl" />
          </div>
        ))}
        <div className="flex gap-2 pt-1">
          <SkeletonBlock className="h-11 w-36 rounded-full" />
          <SkeletonBlock className="h-11 w-32 rounded-full" />
        </div>
      </div>
    </div>
    <div className="rounded-2xl border border-slate-200 bg-white px-5 pb-5 pt-4">
      <SkeletonBlock className="h-5 w-24 rounded" />
      <div className="flex items-center justify-between gap-3 pt-4">
        <SkeletonBlock className="h-4 w-64 max-w-full rounded" />
        <SkeletonBlock className="h-11 w-36 rounded-full" />
      </div>
    </div>
  </SkeletonStatus>
);

const Field: React.FC<{ id: string; label: string; optional?: boolean; error?: string; hint?: string; children: React.ReactNode }> = ({
  id, label, optional, error, hint, children,
}) => (
  <div>
    <label htmlFor={id} className="mb-1.5 block text-[13px] font-semibold text-slate-900">
      {label}{optional && <span className="font-normal text-slate-500"> (không bắt buộc)</span>}
    </label>
    {children}
    {error ? <p id={`${id}-error`} className="mt-1.5 text-xs font-medium text-rose-700">{error}</p>
      : hint ? <p id={`${id}-hint`} className="mt-1.5 text-xs text-slate-500">{hint}</p> : null}
  </div>
);

const Banner: React.FC<{ tone: 'ok' | 'bad'; children: React.ReactNode }> = ({ tone, children }) => (
  <div role={tone === 'ok' ? 'status' : 'alert'}
    className={`mb-4 flex items-start gap-2.5 rounded-xl px-3.5 py-3 text-[13px] font-medium ${tone === 'ok' ? 'bg-emerald-50 text-emerald-800' : 'bg-rose-50 text-rose-800'}`}>
    {tone === 'ok' && <Check className="mt-px h-[18px] w-[18px] flex-none" aria-hidden="true" />}
    <span>{children}</span>
  </div>
);

const BLANK_PASSWORD: PasswordForm = { current: '', next: '', confirm: '' };

export const ProfileView: React.FC = () => {
  const { currentPersona, authReady, updateProfile, openLoginModal, showToast } = useTravel();
  const [saved, setSaved] = useState<ProfileForm>({ fullName: '', phone: '' });
  const [form, setForm] = useState<ProfileForm>({ fullName: '', phone: '' });
  const [touched, setTouched] = useState<Partial<Record<keyof ProfileForm, boolean>>>({});
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<{ tone: 'ok' | 'bad'; text: string } | null>(null);

  // Lấy giá trị đã lưu từ người dùng hiện tại; chỉ nạp lại khi đổi người dùng, không ghi đè lúc đang gõ.
  const personaId = currentPersona?.id ?? null;
  const loadedFor = useRef<string | null>(null);
  useEffect(() => {
    if (!currentPersona || loadedFor.current === personaId) return;
    loadedFor.current = personaId;
    const baseline = { fullName: currentPersona.name, phone: currentPersona.phone ?? '' };
    setSaved(baseline);
    setForm(baseline);
    setTouched({});
  }, [currentPersona, personaId]);

  // Mọi hook đứng trước các `return` sớm bên dưới.
  const [pwOpen, setPwOpen] = useState(false);
  const [pw, setPw] = useState<PasswordForm>(BLANK_PASSWORD);
  const [pwTouched, setPwTouched] = useState<Partial<Record<keyof PasswordForm, boolean>>>({});
  const [pwServerError, setPwServerError] = useState<PasswordErrors>({});
  const [pwBusy, setPwBusy] = useState(false);
  const [reveal, setReveal] = useState<Partial<Record<keyof PasswordForm, boolean>>>({});

  if (!currentPersona && !authReady) return <ProfileSkeleton />;
  if (!currentPersona) {
    return (
      <div className="grid justify-items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-12 text-center">
        <h1 className="text-xl font-bold text-slate-900">Hồ sơ cá nhân</h1>
        <p className="max-w-[44ch] text-[13px] text-slate-500">Đăng nhập để xem và sửa thông tin của bạn.</p>
        <button type="button" className={`${BTN_PRIMARY} mt-2`} onClick={() => openLoginModal()}>
          <LogIn className="h-4 w-4" aria-hidden="true" /> Đăng nhập
        </button>
      </div>
    );
  }

  const errors = validateProfile(form);
  const dirty = isDirty(saved, form);
  const shown = (key: keyof ProfileForm) => (touched[key] ? errors[key] : undefined);
  const set = (key: keyof ProfileForm, value: string) => {
    setForm((f) => ({ ...f, [key]: value }));
    if (notice) setNotice(null);
  };
  const blur = (key: keyof ProfileForm) => setTouched((t) => ({ ...t, [key]: true }));

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setTouched({ fullName: true, phone: true });
    if (Object.keys(errors).length) return;
    const changes = profileChanges(saved, form);
    if (!Object.keys(changes).length) return;
    setSaving(true);
    try {
      const user = await updateProfile(changes);
      const baseline = { fullName: user.fullName, phone: user.phone ?? '' };
      setSaved(baseline);
      setForm(baseline);
      setTouched({});
      setNotice({ tone: 'ok', text: 'Đã lưu thông tin của bạn.' });
    } catch (error) {
      const invalid = (error as { status?: number })?.status === 422;
      setNotice({
        tone: 'bad',
        text: invalid ? 'Thông tin chưa hợp lệ. Kiểm tra lại họ và tên, số điện thoại rồi thử lại.'
          : error instanceof ApiError && error.code === 'NETWORK_ERROR' ? 'Mất kết nối. Kiểm tra mạng rồi bấm Lưu lại.'
            : 'Chưa lưu được thông tin. Vui lòng thử lại.',
      });
    } finally {
      setSaving(false);
    }
  };

  const pwErrors = validatePassword(pw);
  const pwShown = (key: keyof PasswordForm) => pwServerError[key] ?? (pwTouched[key] ? pwErrors[key] : undefined);
  const setPwField = (key: keyof PasswordForm, value: string) => {
    setPw((p) => ({ ...p, [key]: value }));
    if (pwServerError[key]) setPwServerError((e) => ({ ...e, [key]: undefined }));
  };
  const closePassword = () => { setPwOpen(false); setPw(BLANK_PASSWORD); setPwTouched({}); setPwServerError({}); setReveal({}); };

  const submitPassword = async (event: React.FormEvent) => {
    event.preventDefault();
    setPwTouched({ current: true, next: true, confirm: true });
    if (Object.keys(pwErrors).length) return;
    setPwBusy(true);
    try {
      await authApi.changePassword(pw.current, pw.next);
      closePassword();
      setNotice({ tone: 'ok', text: 'Đã đổi mật khẩu. Các thiết bị khác đã được đăng xuất.' });
      showToast('Đã đổi mật khẩu.');
    } catch (error) {
      const code = (error as { code?: string })?.code;
      if (code === 'INVALID_CREDENTIALS') setPwServerError({ current: 'Mật khẩu hiện tại không đúng.' });
      else if (code === 'WEAK_PASSWORD') setPwServerError({ next: 'Mật khẩu mới chưa đủ an toàn. Dùng mật khẩu dài hơn và không chứa họ tên hay email.' });
      else if (code === 'TOO_MANY_ATTEMPTS') setPwServerError({ current: 'Bạn thử quá nhiều lần. Vui lòng đợi ít phút rồi thử lại.' });
      else setPwServerError({ confirm: 'Chưa đổi được mật khẩu. Vui lòng thử lại.' });
    } finally {
      setPwBusy(false);
    }
  };

  const passwordField = (key: keyof PasswordForm, id: string, label: string, autoComplete: string, hint?: string) => (
    <Field id={id} label={label} error={pwShown(key)} hint={hint}>
      <div className="relative">
        <input
          id={id} type={reveal[key] ? 'text' : 'password'} autoComplete={autoComplete} value={pw[key]}
          aria-invalid={pwShown(key) ? true : undefined} aria-describedby={pwShown(key) ? `${id}-error` : hint ? `${id}-hint` : undefined}
          onChange={(e) => setPwField(key, e.target.value)} onBlur={() => setPwTouched((t) => ({ ...t, [key]: true }))}
          className={`${INPUT} pr-20`}
        />
        <button
          type="button" onClick={() => setReveal((r) => ({ ...r, [key]: !r[key] }))} aria-pressed={Boolean(reveal[key])}
          className="absolute right-1 top-1/2 min-h-9 -translate-y-1/2 rounded-lg px-3 text-xs font-semibold text-brand-700 hover:bg-brand-50"
        >
          {reveal[key] ? 'Ẩn' : 'Hiện'}<span className="sr-only"> {label.toLowerCase()}</span>
        </button>
      </div>
    </Field>
  );

  return (
    <div className="grid gap-4">
      <div>
        <h1 className="text-[22px] font-bold leading-tight tracking-tight text-slate-900">Hồ sơ cá nhân</h1>
        <p className="mt-0.5 text-[13px] text-slate-500">Thông tin này dùng để điền sẵn khi bạn đặt chỗ.</p>
      </div>

      {notice && <div><Banner tone={notice.tone}>{notice.text}</Banner></div>}

      <Card id="profile-info" title="Thông tin cá nhân">
        <form onSubmit={(e) => void submit(e)} noValidate className="grid max-w-[30rem] gap-4">
          <Field id="profile-name" label="Họ và tên" error={shown('fullName')}>
            <input
              id="profile-name" name="fullName" autoComplete="name" maxLength={NAME_MAX + 20} value={form.fullName}
              aria-invalid={shown('fullName') ? true : undefined} aria-describedby={shown('fullName') ? 'profile-name-error' : undefined}
              onChange={(e) => set('fullName', e.target.value)} onBlur={() => blur('fullName')} className={INPUT}
            />
          </Field>
          <Field id="profile-email" label="Email" hint="Email dùng để đăng nhập nên không đổi được ở đây.">
            <div className="relative">
              <input id="profile-email" value={currentPersona.email} readOnly aria-describedby="profile-email-hint" className={`${INPUT} pr-10`} />
              <LockKeyhole className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" aria-hidden="true" />
            </div>
          </Field>
          <Field id="profile-phone" label="Số điện thoại" optional error={shown('phone')} hint="10 chữ số, bắt đầu bằng 0. Tự điền vào bước thanh toán.">
            <input
              id="profile-phone" name="phone" type="tel" inputMode="tel" autoComplete="tel" value={form.phone}
              aria-invalid={shown('phone') ? true : undefined} aria-describedby={shown('phone') ? 'profile-phone-error' : 'profile-phone-hint'}
              onChange={(e) => set('phone', e.target.value)} onBlur={() => blur('phone')} className={INPUT}
            />
          </Field>
          <div className="flex flex-wrap gap-2 pt-1 max-sm:[&>*]:flex-1">
            <button type="submit" disabled={!dirty || saving || Object.keys(errors).length > 0} className={BTN_PRIMARY}>
              {saving && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />} Lưu thay đổi
            </button>
            <button type="button" disabled={!dirty || saving} onClick={() => { setForm(saved); setTouched({}); }} className={BTN_SECONDARY}>
              Huỷ thay đổi
            </button>
          </div>
        </form>
      </Card>

      <Card id="profile-password" title="Mật khẩu">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-[13px] text-slate-500">Đổi mật khẩu định kỳ để bảo vệ tài khoản.</p>
          {!pwOpen && <button type="button" onClick={() => setPwOpen(true)} className={BTN_SECONDARY}>Đổi mật khẩu</button>}
        </div>
        {pwOpen && (
          <form onSubmit={(e) => void submitPassword(e)} noValidate className="mt-4 grid max-w-[30rem] gap-4">
            {passwordField('current', 'pw-current', 'Mật khẩu hiện tại', 'current-password')}
            {passwordField('next', 'pw-next', 'Mật khẩu mới', 'new-password', 'Từ 8 đến 128 ký tự. Các thiết bị khác sẽ bị đăng xuất sau khi đổi.')}
            {passwordField('confirm', 'pw-confirm', 'Nhập lại mật khẩu mới', 'new-password')}
            <div className="flex flex-wrap gap-2 pt-1 max-sm:[&>*]:flex-1">
              <button type="submit" disabled={pwBusy} className={BTN_PRIMARY}>
                {pwBusy && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />} Đổi mật khẩu
              </button>
              <button type="button" onClick={closePassword} disabled={pwBusy} className={BTN_SECONDARY}>Huỷ</button>
            </div>
          </form>
        )}
      </Card>
    </div>
  );
};
