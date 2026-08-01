'use client';
import { useState } from 'react';
import { usePathname } from 'next/navigation';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SessionProvider } from 'next-auth/react';
import BottomNav from '@/components/nav/BottomNav';
import SideNav from '@/components/nav/SideNav';
import './globals.css';

const PUBLIC_PATHS = ['/login', '/register', '/request-access'];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient());
  const pathname = usePathname();
  const showNav = !PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(p + '/'));

  return (
    <html lang="en">
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="manifest" href="/manifest.json" />
        <meta name="theme-color" content="#4F46E5" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="default" />
        <meta name="apple-mobile-web-app-title" content="Spending Tracker" />
        <link rel="apple-touch-icon" href="/icons/icon-192.png" />
        <title>Spending Tracker</title>
      </head>
      <body className="bg-gray-50 text-gray-900">
        <SessionProvider>
        <QueryClientProvider client={queryClient}>
          {showNav ? (
            <div className="flex min-h-screen">
              <SideNav />
              <main className="flex-1 p-4 pb-24 md:pb-4 max-w-5xl mx-auto w-full">
                {children}
              </main>
            </div>
          ) : (
            children
          )}
          {showNav && <BottomNav />}
        </QueryClientProvider>
        </SessionProvider>
      </body>
    </html>
  );
}
