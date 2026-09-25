import React, { useState, useEffect } from 'react';
import QRCode from 'qrcode';
import { 
  Share2, Copy, Check, X, ExternalLink, QrCode, 
  Sparkles, Calendar, MapPin, DollarSign, MessageSquare, 
  Send, Mail, Globe, CheckCircle2, Loader2, Smartphone
} from 'lucide-react';
import { GroundedPlan } from '../../types/travel';
import { createSharedTripUrl, getSocialShareLinks } from '../../services/shareService';

interface ShareItineraryModalProps {
  isOpen: boolean;
  onClose: () => void;
  plan: GroundedPlan | null;
  senderName?: string;
  onToast: (msg: string) => void;
}

export const ShareItineraryModal: React.FC<ShareItineraryModalProps> = ({
  isOpen,
  onClose,
  plan,
  senderName = 'Tôi',
  onToast
}) => {
  const [copied, setCopied] = useState(false);
  const [shareUrl, setShareUrl] = useState('');
  const [shareId, setShareId] = useState('');
  const [customNote, setCustomNote] = useState('');
  const [userName, setUserName] = useState(senderName);
  const [isGenerating, setIsGenerating] = useState(false);
  const [qrCodeDataUrl, setQrCodeDataUrl] = useState<string>('');
  const [showQr, setShowQr] = useState(false);

  // Initialize or re-generate share URL when plan changes or modal opens
  useEffect(() => {
    if (!isOpen || !plan) return;

    let isMounted = true;
    setIsGenerating(true);
    setCopied(false);

    createSharedTripUrl(plan, userName, customNote)
      .then(async (result) => {
        if (!isMounted) return;
        setShareUrl(result.fullUrl);
        setShareId(result.shareId);

        // Generate QR code for this link
        try {
          const qr = await QRCode.toDataURL(result.fullUrl, {
            width: 220,
            margin: 1.5,
            color: {
              dark: '#1e3a8a', // Deep blue
              light: '#ffffff'
            }
          });
          if (isMounted) setQrCodeDataUrl(qr);
        } catch (e) {
          console.error('Failed to generate QR code', e);
        }
      })
      .finally(() => {
        if (isMounted) setIsGenerating(false);
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, plan]);

  // Handle note change and update QR
  const handleUpdateNote = async () => {
    if (!plan) return;
    setIsGenerating(true);
    const result = await createSharedTripUrl(plan, userName, customNote);
    setShareUrl(result.fullUrl);
    setShareId(result.shareId);
    try {
      const qr = await QRCode.toDataURL(result.fullUrl, {
        width: 220,
        margin: 1.5,
        color: { dark: '#1e3a8a', light: '#ffffff' }
      });
      setQrCodeDataUrl(qr);
    } catch {}
    setIsGenerating(false);
    onToast('Đã cập nhật lời nhắn vào liên kết chia sẻ!');
  };

  if (!isOpen || !plan) return null;

  const handleCopyLink = async () => {
    if (!shareUrl) return;
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(shareUrl);
      } else {
        // Fallback
        const textArea = document.createElement('textarea');
        textArea.value = shareUrl;
        textArea.style.position = 'fixed';
        textArea.style.opacity = '0';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
      }
      setCopied(true);
      onToast('Đã sao chép liên kết chia sẻ vào khay nhớ tạm!');
      setTimeout(() => setCopied(false), 3000);
    } catch (err) {
      console.error('Failed to copy', err);
      onToast('Không thể sao chép tự động, vui lòng bôi đen và nhấn Ctrl+C.');
    }
  };

  // Native Web Share API
  const handleNativeShare = async () => {
    if (!shareUrl) return;
    if (navigator.share) {
      try {
        await navigator.share({
          title: plan.title,
          text: `Xem lịch trình du lịch "${plan.title}" trên V-OTA! ${customNote ? `\nLưu ý: ${customNote}` : ''}`,
          url: shareUrl
        });
        onToast('Đã mở bảng chia sẻ của thiết bị!');
      } catch (err: any) {
        if (err.name !== 'AbortError') {
          console.warn('Native share failed', err);
        }
      }
    } else {
      handleCopyLink();
    }
  };

  const socialLinks = getSocialShareLinks(
    shareUrl,
    plan.title,
    plan.intent.destination,
    customNote
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-200">
      <div 
        className="bg-white rounded-3xl shadow-2xl border border-slate-200 w-full max-w-xl overflow-hidden flex flex-col max-h-[92vh] animate-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="p-5 bg-gradient-to-r from-blue-900 via-indigo-900 to-blue-800 text-white flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-white/10 flex items-center justify-center text-blue-200">
              <Share2 className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white leading-tight">
                Chia sẻ lịch trình du lịch
              </h3>
              <p className="text-xs text-blue-200">
                Gửi liên kết độc quyền để bạn bè & gia đình cùng xem trên điện thoại hoặc máy tính
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-blue-200 hover:text-white hover:bg-white/10 rounded-xl transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-5 overflow-y-auto space-y-4 text-xs sm:text-sm">
          {/* Trip Card Preview */}
          <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-2xl space-y-2">
            <div className="flex items-start justify-between gap-2">
              <div>
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-100 text-blue-800 text-[10px] font-bold">
                  <Sparkles className="w-3 h-3" />
                  Lịch trình V-OTA AI
                </span>
                <h4 className="text-sm font-bold text-slate-900 mt-1">
                  {plan.title}
                </h4>
              </div>
              <div className="text-right shrink-0">
                <span className="text-xs font-bold text-emerald-600">
                  ~{new Intl.NumberFormat('vi-VN').format(plan.totalEstimatedPrice)} ₫
                </span>
                <p className="text-[10px] text-slate-500">Ước tính toàn chuyến</p>
              </div>
            </div>

            <div className="flex items-center gap-4 text-xs text-slate-600 pt-1 border-t border-slate-200/80 flex-wrap">
              <span className="flex items-center gap-1">
                <MapPin className="w-3.5 h-3.5 text-rose-500" />
                {plan.intent.destination}
              </span>
              <span className="flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5 text-blue-500" />
                {plan.days.length} ngày khám phá
              </span>
              <span className="flex items-center gap-1 text-blue-700 font-semibold">
                <CheckCircle2 className="w-3.5 h-3.5 text-blue-600" />
                {plan.bookableProductsCount} dịch vụ thật đặt được
              </span>
            </div>
          </div>

          {/* Unique Link Input Box */}
          <div className="space-y-1.5">
            <label className="text-xs font-bold text-slate-800 flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <Globe className="w-3.5 h-3.5 text-blue-600" />
                Đường dẫn liên kết duy nhất (Unique URL):
              </span>
              {shareId && (
                <span className="text-[10px] text-slate-400 font-mono">
                  Mã: {shareId}
                </span>
              )}
            </label>

            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <input
                  type="text"
                  readOnly
                  value={isGenerating ? 'Đang tạo liên kết chia sẻ...' : shareUrl}
                  className="w-full px-3 py-2 text-xs font-mono bg-slate-50 border border-slate-300 rounded-xl text-slate-700 select-all outline-hidden"
                />
              </div>

              <button
                type="button"
                onClick={handleCopyLink}
                disabled={isGenerating || !shareUrl}
                className={`px-3.5 py-2 text-xs font-bold rounded-xl border transition-all flex items-center gap-1.5 shrink-0 shadow-2xs ${
                  copied
                    ? 'bg-emerald-600 text-white border-emerald-600'
                    : 'bg-blue-600 hover:bg-blue-700 text-white border-blue-600'
                }`}
              >
                {copied ? (
                  <>
                    <Check className="w-4 h-4" />
                    <span>Đã chép!</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-4 h-4" />
                    <span>Sao chép</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Personalize Note (Optional) */}
          <div className="space-y-1.5">
            <label className="text-xs font-bold text-slate-700 flex items-center gap-1">
              <MessageSquare className="w-3.5 h-3.5 text-indigo-600" />
              <span>Ghi chú gửi kèm cho người nhận (tùy chọn):</span>
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={customNote}
                onChange={(e) => setCustomNote(e.target.value)}
                placeholder="Ví dụ: Lịch trình nhóm mình đi hè này nhé, mọi người xem thử..."
                className="flex-1 px-3 py-1.5 text-xs border border-slate-300 rounded-xl outline-hidden focus:ring-2 focus:ring-blue-500"
              />
              <button
                type="button"
                onClick={handleUpdateNote}
                className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-semibold transition-colors shrink-0"
              >
                Cập nhật
              </button>
            </div>
          </div>

          {/* Social Share Buttons */}
          <div className="space-y-2 pt-1">
            <span className="text-xs font-bold text-slate-800 block">
              Chia sẻ trực tiếp qua mạng xã hội:
            </span>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {/* Zalo Share */}
              <a
                href={socialLinks.zalo}
                target="_blank"
                rel="noopener noreferrer"
                className="p-2.5 bg-blue-50 hover:bg-blue-100 border border-blue-200 text-blue-700 font-bold rounded-xl flex items-center justify-center gap-2 transition-colors text-xs"
                title="Chia sẻ qua Zalo"
              >
                <span className="w-5 h-5 rounded-full bg-blue-600 text-white font-black text-[10px] flex items-center justify-center">
                  Z
                </span>
                <span>Zalo</span>
              </a>

              {/* Facebook Share */}
              <a
                href={socialLinks.facebook}
                target="_blank"
                rel="noopener noreferrer"
                className="p-2.5 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 text-indigo-700 font-bold rounded-xl flex items-center justify-center gap-2 transition-colors text-xs"
                title="Chia sẻ lên Facebook"
              >
                <span className="w-5 h-5 rounded-full bg-indigo-600 text-white font-black text-[10px] flex items-center justify-center">
                  f
                </span>
                <span>Facebook</span>
              </a>

              {/* Telegram */}
              <a
                href={socialLinks.telegram}
                target="_blank"
                rel="noopener noreferrer"
                className="p-2.5 bg-sky-50 hover:bg-sky-100 border border-sky-200 text-sky-700 font-bold rounded-xl flex items-center justify-center gap-2 transition-colors text-xs"
                title="Gửi qua Telegram"
              >
                <Send className="w-4 h-4 text-sky-600" />
                <span>Telegram</span>
              </a>

              {/* WhatsApp */}
              <a
                href={socialLinks.whatsapp}
                target="_blank"
                rel="noopener noreferrer"
                className="p-2.5 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 text-emerald-700 font-bold rounded-xl flex items-center justify-center gap-2 transition-colors text-xs"
                title="Gửi qua WhatsApp"
              >
                <span className="w-5 h-5 rounded-full bg-emerald-600 text-white font-black text-[10px] flex items-center justify-center">
                  W
                </span>
                <span>WhatsApp</span>
              </a>
            </div>

            {/* Native Mobile Share & QR Toggle */}
            <div className="flex items-center gap-2 pt-2">
              {typeof navigator !== 'undefined' && 'share' in navigator && (
                <button
                  type="button"
                  onClick={handleNativeShare}
                  className="flex-1 py-2 px-3 bg-slate-100 hover:bg-slate-200 text-slate-800 rounded-xl font-semibold flex items-center justify-center gap-2 text-xs transition-colors"
                >
                  <Smartphone className="w-4 h-4 text-slate-600" />
                  <span>Mở bảng chia sẻ máy</span>
                </button>
              )}

              <button
                type="button"
                onClick={() => setShowQr(!showQr)}
                className={`py-2 px-3 border rounded-xl font-semibold flex items-center justify-center gap-1.5 text-xs transition-colors ${
                  showQr
                    ? 'bg-blue-50 text-blue-700 border-blue-300'
                    : 'bg-white hover:bg-slate-50 text-slate-700 border-slate-300'
                }`}
              >
                <QrCode className="w-4 h-4" />
                <span>{showQr ? 'Ẩn mã QR' : 'Mã QR quét trên điện thoại'}</span>
              </button>
            </div>
          </div>

          {/* QR Code Expansion Panel */}
          {showQr && qrCodeDataUrl && (
            <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl flex flex-col items-center justify-center text-center space-y-2 animate-in fade-in duration-150">
              <div className="p-2 bg-white rounded-xl shadow-xs border border-slate-100">
                <img 
                  src={qrCodeDataUrl} 
                  alt="QR Code Lịch trình" 
                  className="w-40 h-40 object-contain" 
                />
              </div>
              <div>
                <p className="text-xs font-bold text-slate-800">
                  Quét bằng Camera điện thoại
                </p>
                <p className="text-[10px] text-slate-500">
                  Mở trực tiếp lịch trình này trên điện thoại của bạn bè hoặc người thân
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="p-4 bg-slate-50 border-t border-slate-100 flex items-center justify-between">
          <span className="text-[11px] text-slate-500">
            Người nhận có thể xem bản đồ, chi tiết hoạt động & đặt dịch vụ ngay lập tức.
          </span>

          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-800 font-bold rounded-xl text-xs transition-colors"
          >
            Đóng
          </button>
        </div>
      </div>
    </div>
  );
};
