'use client';

import type { ReactNode } from 'react';
import { Suspense } from 'react';
import { useTravel } from '../../context/TravelContext';
import { Header } from '../common/Header';
import { Footer } from '../common/Footer';
import { MobileTabBar } from '../common/MobileTabBar';
import { Toast } from '../common/Toast';
import { LoginModal } from '../common/LoginModal';
// import { DebugPanel } from '../common/DebugPanel'; // đã comment: xem history/2026-10-14-comment-out-debug-panel.md
import { AiFloatingWidget } from '../assistant/AiFloatingWidget';

export default function AppShell({ children }: { children: ReactNode }) {
  const { currentRoute } = useTravel();
  const isCheckout = currentRoute.startsWith('/checkout');

  return (
    <div className="min-h-screen bg-slate-50/70 flex flex-col font-sans antialiased text-slate-900 pb-16 md:pb-0">
      <Suspense fallback={null}>
        <Header isCheckout={isCheckout} />
      </Suspense>
      <main className="flex-1">{children}</main>
      <Footer />
      <MobileTabBar />
      <Toast />
      <LoginModal />
      {/* <DebugPanel /> */}
      {!isCheckout && <AiFloatingWidget />}
    </div>
  );
}
