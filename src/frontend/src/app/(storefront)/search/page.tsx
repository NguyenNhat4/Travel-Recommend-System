import { Suspense } from 'react';
import { SearchView, SearchViewSkeleton } from '../../../components/search/SearchView';

// SearchView đọc `?q=`, `?type=` bằng `useSearchParams`: lúc trang mới tải, ranh giới Suspense hiện khung trang thay vì để trống.
export default function SearchPage() {
  return (
    <Suspense fallback={<SearchViewSkeleton />}>
      <SearchView />
    </Suspense>
  );
}
