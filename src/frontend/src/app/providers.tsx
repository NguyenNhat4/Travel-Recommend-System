'use client';

import type { ReactNode } from 'react';
import { TravelProvider } from '../context/TravelContext';
import AppShell from '../components/layout/AppShell';

export default function Providers({ children }: { children: ReactNode }) {
  return (
    <TravelProvider>
      <AppShell>{children}</AppShell>
    </TravelProvider>
  );
}
