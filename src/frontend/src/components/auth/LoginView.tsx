'use client';

import React, { useState } from 'react';
import { useTravel } from '../../context/TravelContext';
import { AuthError } from '../../services/auth';
import { DemoAccountSwitcher } from '../common/DemoAccountSwitcher';
import { Lock, Eye, EyeOff, Check, UserPlus, LogIn } from 'lucide-react';

/** Thông điệp theo `code` (hop-dong-tich-hop-frontend.md §8, auth §17). */
export function authErrorMessage(err: unknown): string {
  if (!(err instanceof AuthError)) return 'Không kết nối được máy chủ. Vui lòng thử lại.';
  switch (err.code) {
    case 'INVALID_CREDENTIALS':
      return 'Email hoặc mật khẩu không đúng.';
    case 'EMAIL_ALREADY_EXISTS':
      return 'Email này đã được đăng ký. Hãy đăng nhập.';
    case 'WEAK_PASSWORD': {
      const reasons = err.details?.reasons;
      return Array.isArray(reasons) && reasons.length ? reasons.join(' ') : err.message;
    }
    case 'TOO_MANY_ATTEMPTS':
      return `Quá nhiều lần thử. Vui lòng thử lại sau ${Math.ceil((err.retryAfterSeconds ?? 900) / 60)} phút.`;
    case 'VALIDATION_ERROR':
      return 'Thông tin chưa hợp lệ. Kiểm tra lại email và mật khẩu.';
    default:
      return err.message;
  }
}

export const LoginView: React.FC = () => {
  const { signIn, signUp, navigate, showToast } = useTravel();
  const [isRegisterMode, setIsRegisterMode] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const has8Chars = password.length >= 8;
  const hasLetter = /[a-zA-Z]/.test(password);
  const hasNumber = /[0-9]/.test(password);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Vui lòng điền đầy đủ email và mật khẩu.');
      return;
    }

    // Chỉ độ dài là điều kiện chặn; chữ/số là gợi ý hiển thị. Server kiểm lại toàn bộ chính sách (auth §8.3).
    if (isRegisterMode && !has8Chars) {
      setError('Mật khẩu phải có ít nhất 8 ký tự.');
      return;
    }

    setSubmitting(true);
    setError('');
    try {
      if (isRegisterMode) await signUp(email, password, fullName);
      else await signIn(email, password);
      showToast(isRegisterMode ? 'Đăng ký tài khoản thành công!' : 'Đăng nhập thành công!');
      navigate('/');
    } catch (err) {
      setError(authErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-xl mx-auto px-4 py-12 space-y-8">
      <div className="bg-white p-8 rounded-3xl border border-slate-200 shadow-xl space-y-6">
        <div className="text-center space-y-1">
          <div className="w-12 h-12 rounded-2xl bg-blue-600 text-white flex items-center justify-center mx-auto mb-2 shadow-xs">
            <Lock className="w-6 h-6" />
          </div>
          <h1 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight">
            {isRegisterMode ? 'Đăng ký tài khoản V-OTA' : 'Đăng nhập V-OTA'}
          </h1>
          <p className="text-xs text-slate-500">
            {isRegisterMode 
              ? 'Tạo tài khoản mới để cá nhân hóa đề xuất theo từng chuyến đi' 
              : 'Nhận gợi ý theo từng chuyến đi của bạn'}
          </p>
        </div>

        {error && (
          <div className="p-3 bg-red-50 text-red-700 text-xs rounded-xl border border-red-200">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {isRegisterMode && (
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Họ và tên *
              </label>
              <input
                type="text"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Nguyễn Văn A"
                className="w-full px-3.5 py-2.5 text-xs sm:text-sm border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-hidden"
              />
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Email *
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="ten@vidu.com"
              className="w-full px-3.5 py-2.5 text-xs sm:text-sm border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-hidden"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Mật khẩu *
            </label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full px-3.5 py-2.5 text-xs sm:text-sm border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-hidden pr-10"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* Real-time Password Rules Checklist for Registration (§4.7.4) */}
          {isRegisterMode && (
            <div className="p-3 bg-slate-50 rounded-xl space-y-1.5 text-[11px] text-slate-600 border border-slate-200">
              <span className="font-semibold text-slate-700">Yêu cầu mật khẩu:</span>
              <div className="grid grid-cols-2 gap-1.5">
                <div className={`flex items-center gap-1.5 ${has8Chars ? 'text-emerald-700 font-bold' : 'text-slate-400'}`}>
                  <Check className={`w-3.5 h-3.5 ${has8Chars ? 'text-emerald-600' : 'text-slate-300'}`} />
                  <span>Ít nhất 8 ký tự</span>
                </div>
                <div className={`flex items-center gap-1.5 ${hasLetter ? 'text-emerald-700 font-bold' : 'text-slate-400'}`}>
                  <Check className={`w-3.5 h-3.5 ${hasLetter ? 'text-emerald-600' : 'text-slate-300'}`} />
                  <span>Có chữ cái</span>
                </div>
                <div className={`flex items-center gap-1.5 ${hasNumber ? 'text-emerald-700 font-bold' : 'text-slate-400'}`}>
                  <Check className={`w-3.5 h-3.5 ${hasNumber ? 'text-emerald-600' : 'text-slate-300'}`} />
                  <span>Có ít nhất 1 chữ số</span>
                </div>
              </div>
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full py-3 disabled:opacity-60 bg-blue-600 hover:bg-blue-700 text-white font-bold text-sm rounded-xl shadow-xs transition-colors"
          >
            {isRegisterMode ? 'Tạo tài khoản' : 'Đăng nhập'}
          </button>
        </form>

        <div className="text-center">
          <button
            type="button"
            onClick={() => {
              setIsRegisterMode(!isRegisterMode);
              setError('');
            }}
            className="text-xs text-blue-600 hover:underline font-semibold"
          >
            {isRegisterMode 
              ? 'Đã có tài khoản? Đăng nhập ngay' 
              : 'Chưa có tài khoản? Đăng ký miễn phí'}
          </button>
        </div>

        {/* Demo Account Switcher for 1-click test (§4.7.3) */}
        <div className="pt-6 border-t border-slate-100 space-y-3">
          <DemoAccountSwitcher />
        </div>
      </div>
    </div>
  );
};
