import { Suspense } from 'react';
import { CheckoutView } from '../../../components/checkout/CheckoutView';

// CheckoutView đọc `?draft=` bằng `useSearchParams`, nên cần một ranh giới Suspense (như trang /search).
export default function CheckoutPage() {
  return (
    <Suspense fallback={null}>
      <CheckoutView />
    </Suspense>
  );
}
