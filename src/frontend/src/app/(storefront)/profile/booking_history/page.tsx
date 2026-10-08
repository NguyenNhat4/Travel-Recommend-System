import { Suspense } from 'react';
import { BookingHistoryView } from '../../../../features/bookings/BookingHistoryView';

// BookingHistoryView đọc bộ lọc (`?tab=`, `?taxonomy=`, `?days=`, `?page=`) bằng `useSearchParams`, nên cần ranh giới Suspense.
export default function BookingHistoryPage() {
  return (
    <Suspense fallback={null}>
      <BookingHistoryView />
    </Suspense>
  );
}
