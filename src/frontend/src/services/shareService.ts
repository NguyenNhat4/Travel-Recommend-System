import { GroundedPlan, SharedTripRecord } from '../types/travel';
import { apiFetch } from './http';

export interface ShareResult {
  shareId: string;
  shareUrl: string;
  fullUrl: string;
  trip?: SharedTripRecord;
}

/**
 * Compact plan serializer for URL parameters fallback
 */
export function encodePlanForUrl(plan: GroundedPlan): string {
  try {
    const compact = {
      t: plan.title,
      i: plan.intent,
      m: plan.missing,
      s: plan.stay,
      d: plan.days.map(d => ({
        day: d.day,
        title: d.title,
        slots: d.slots
      })),
      p: plan.totalEstimatedPrice,
      c: plan.bookableProductsCount
    };
    const jsonStr = JSON.stringify(compact);
    // Base64 encoding compatible with UTF-8
    const base64 = btoa(encodeURIComponent(jsonStr));
    return base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  } catch (err) {
    console.warn('Could not compress plan for URL:', err);
    return '';
  }
}

/**
 * Unpack compact plan serializer from URL
 */
export function decodePlanFromUrl(encoded: string): GroundedPlan | null {
  try {
    const base64 = encoded.replace(/-/g, '+').replace(/_/g, '/');
    const jsonStr = decodeURIComponent(atob(base64));
    const compact = JSON.parse(jsonStr);

    if (!compact || !compact.t || !compact.d) return null;

    return {
      title: compact.t,
      intent: compact.i,
      missing: compact.m,
      stay: compact.s,
      days: compact.d,
      totalEstimatedPrice: compact.p || 0,
      bookableProductsCount: compact.c || 0
    };
  } catch (err) {
    console.warn('Could not decode plan from URL string:', err);
    return null;
  }
}

/**
 * Save trip on server to produce a short share URL
 */
export async function createSharedTripUrl(
  plan: GroundedPlan,
  senderName?: string,
  note?: string
): Promise<ShareResult> {
  let shareId = '';
  let origin = typeof window !== 'undefined' ? window.location.origin : '';

  try {
    const res = await apiFetch('/api/trips/share', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ plan, senderName, note })
    });

    if (res.ok) {
      const data = await res.json();
      shareId = data.shareId;
    }
  } catch (err) {
    console.warn('Server sharing unavailable, falling back to client-encoded URL:', err);
  }

  // If server produced an ID, use it with backup compact query
  const compactBackup = encodePlanForUrl(plan);

  let sharePath = '';
  if (shareId) {
    // Both server shareId and compact param so it works in every environment
    sharePath = `/assistant?share=${shareId}${compactBackup ? `&data=${compactBackup}` : ''}`;
  } else {
    // Client-only URL
    const clientSlug = (plan.intent?.destination || 'trip')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .replace(/[^a-z0-9]/g, '-');
    sharePath = `/assistant?share=vota-${clientSlug}&data=${compactBackup}`;
    shareId = `vota-${clientSlug}`;
  }

  const fullUrl = `${origin}${sharePath}`;

  return {
    shareId,
    shareUrl: sharePath,
    fullUrl,
    trip: {
      id: shareId,
      plan,
      senderName: senderName || 'Du khách V-OTA',
      note: note || '',
      createdAt: new Date().toISOString(),
      views: 1
    }
  };
}

/**
 * Retrieve shared trip by shareId from server or decode from URL parameter
 */
export async function getSharedTrip(shareId: string, urlDataParam?: string): Promise<SharedTripRecord | null> {
  // Try fetching from server first
  if (shareId) {
    try {
      const res = await apiFetch(`/api/trips/share/${encodeURIComponent(shareId)}`);
      if (res.ok) {
        const data = await res.json();
        if (data.success && data.trip) {
          return data.trip;
        }
      }
    } catch (e) {
      console.warn('Server fetch for shared trip failed:', e);
    }
  }

  // Fallback: decode from data parameter
  if (urlDataParam) {
    const decodedPlan = decodePlanFromUrl(urlDataParam);
    if (decodedPlan) {
      return {
        id: shareId || 'vota-shared-plan',
        plan: decodedPlan,
        senderName: 'Bạn bè / Người thân',
        note: 'Lịch trình du lịch được chia sẻ riêng cho bạn',
        createdAt: new Date().toISOString(),
        views: 1
      };
    }
  }

  return null;
}

/**
 * Build popular social sharing URLs
 */
export function getSocialShareLinks(
  shareUrl: string,
  title: string,
  destination: string,
  note?: string
) {
  const shareText = `Xem lịch trình du lịch "${title}" tại ${destination} trên V-OTA! ${note ? `\nLưu ý: ${note}` : ''}`;
  const encodedUrl = encodeURIComponent(shareUrl);
  const encodedText = encodeURIComponent(shareText);

  return {
    zalo: `https://zalo.me/share?url=${encodedUrl}`,
    facebook: `https://www.facebook.com/sharer/sharer.php?u=${encodedUrl}&quote=${encodedText}`,
    telegram: `https://t.me/share/url?url=${encodedUrl}&text=${encodedText}`,
    whatsapp: `https://api.whatsapp.com/send?text=${encodedText}%20${encodedUrl}`,
    twitter: `https://twitter.com/intent/tweet?url=${encodedUrl}&text=${encodedText}`,
    email: `mailto:?subject=${encodeURIComponent(`Lịch trình du lịch V-OTA: ${title}`)}&body=${encodeURIComponent(`${shareText}\n\nXem chi tiết tại: ${shareUrl}`)}`
  };
}
