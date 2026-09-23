'use client';

import type { ReactNode } from 'react';
import { TravelProvider } from '../context/TravelContext';
import { AssistantProvider } from '../context/AssistantProvider';
import AppShell from '../components/layout/AppShell';

export default function Providers({ children }: { children: ReactNode }) {
  return (
    <TravelProvider>
      <AssistantProvider>
        <AppShell>{children}</AppShell>
      </AssistantProvider>
    </TravelProvider>
  );
}
