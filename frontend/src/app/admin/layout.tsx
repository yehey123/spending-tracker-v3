'use client';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from 'next-auth/react';

// Client-side guard for the page shell only. Server components reading headers
// (auth()) cannot be statically exported for the Capacitor build. Access to data is
// enforced server-side: every /admin/* backend handler depends on require_admin.
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { data: session, status } = useSession();
  const router = useRouter();
  const allowed = !!session?.user && !!(session as { isAdmin?: boolean }).isAdmin;

  useEffect(() => {
    if (status !== 'loading' && !allowed) router.replace('/');
  }, [status, allowed, router]);

  if (!allowed) return null;
  return <>{children}</>;
}
