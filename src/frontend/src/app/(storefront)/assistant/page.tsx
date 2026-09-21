import { Suspense } from 'react';
import { AssistantView } from '../../../components/assistant/AssistantView';

export default function AssistantPage() {
  return (
    <Suspense fallback={null}>
      <AssistantView />
    </Suspense>
  );
}
