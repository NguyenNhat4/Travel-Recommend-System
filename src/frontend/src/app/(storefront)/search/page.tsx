import { Suspense } from 'react';
import { SearchView } from '../../../components/search/SearchView';

export default function SearchPage() {
  return (
    <Suspense fallback={null}>
      <SearchView />
    </Suspense>
  );
}
