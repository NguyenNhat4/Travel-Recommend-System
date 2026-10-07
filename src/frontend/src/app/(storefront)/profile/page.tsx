import { redirect } from 'next/navigation';
import { ProfileView } from '../../../features/profile/ProfileView';

const OLD_HISTORY_PARAMS = ['tab', 'taxonomy', 'days', 'page'];

// `/profile` từng là trang lịch sử đơn: đường dẫn cũ có bộ lọc thì chuyển sang địa chỉ mới, giữ nguyên bộ lọc.
export default async function ProfilePage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const params = await searchParams;
  const kept = new URLSearchParams();
  for (const key of OLD_HISTORY_PARAMS) {
    const value = params[key];
    if (typeof value === 'string') kept.set(key, value);
  }
  if (kept.size > 0) redirect(`/profile/booking_history?${kept.toString()}`);
  return <ProfileView />;
}
