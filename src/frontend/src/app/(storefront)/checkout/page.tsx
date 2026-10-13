import { Suspense } from 'react';
import { CheckoutSkeleton, CheckoutView } from '../../../components/checkout/CheckoutView';

// CheckoutView đọc `?draft=` bằng `useSearchParams`, nên cần một ranh giới Suspense (như trang /search); fallback là khung trang.
export default function CheckoutPage() {
  return (
    <Suspense fallback={<CheckoutSkeleton />}>
      <CheckoutView />
    </Suspense>
  );
}
