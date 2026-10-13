import { Suspense } from 'react';
import { BookingHistorySkeleton, BookingHistoryView } from '../../../../features/bookings/BookingHistoryView';

// BookingHistoryView đọc bộ lọc (`?tab=`, `?taxonomy=`, `?days=`, `?page=`) bằng `useSearchParams`, nên cần ranh giới Suspense;
// fallback là khung trang.
export default function BookingHistoryPage() {
  return (
    <Suspense fallback={<BookingHistorySkeleton />}>
      <BookingHistoryView />
    </Suspense>
  );
}
