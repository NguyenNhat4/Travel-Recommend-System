import React, { useEffect, useState } from 'react';
import { useTravel } from '../../context/TravelContext';
import { X, Lock, Eye, EyeOff, UserCheck } from 'lucide-react';
import { authErrorMessage } from '../auth/LoginView';

export const LoginModal: React.FC = () => {
  const { isLoginModalOpen, closeLoginModal, signIn, pendingPostLoginAction, showToast, loginPrefillEmail, navigate } = useTravel();
  const [email, setEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Phiên hết hạn giữa chừng: điền sẵn email của người vừa bị đăng xuất.
  useEffect(() => {
    if (isLoginModalOpen && loginPrefillEmail) setEmail(loginPrefillEmail);
  }, [isLoginModalOpen, loginPrefillEmail]);
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');

  if (!isLoginModalOpen) return null;

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Vui lòng nhập đầy đủ email và mật khẩu');
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      await signIn(email, password);
    } catch (err) {
      setError(authErrorMessage(err));
      return;
    } finally {
      setSubmitting(false);
    }
    // Thực hiện đúng hành động đang chờ một lần (§4.2 điều 5).
    const pending = pendingPostLoginAction;
    closeLoginModal();
    setPassword('');
    if (pending) setTimeout(() => pending(), 100);
    showToast('Đăng nhập thành công!');
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-in fade-in duration-150">
      <div 
        className="w-full max-w-md bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white">
              <Lock className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">Đăng nhập V-OTA</h3>
              <p className="text-xs text-slate-500">Nhận gợi ý cá nhân hóa theo chuyến đi của bạn</p>
            </div>
          </div>
          <button
            onClick={closeLoginModal}
            className="p-1 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-200/50 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-5">
          {error && (
            <div className="p-3 bg-red-50 text-red-700 text-xs rounded-lg border border-red-200">
              {error}
            </div>
          )}

          <form onSubmit={handleLoginSubmit} className="space-y-3.5">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="ten@vidu.com"
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-hidden"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Mật khẩu
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-hidden pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="w-full disabled:opacity-60 py-2.5 px-4 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-xs transition-colors"
            >
              Đăng nhập
            </button>
          </form>

          <div className="text-center">
            <button
              type="button"
              onClick={() => {
                closeLoginModal();
                navigate('/register');
              }}
              className="text-xs text-blue-600 hover:underline font-semibold"
            >
              Chưa có tài khoản? Đăng ký miễn phí
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
