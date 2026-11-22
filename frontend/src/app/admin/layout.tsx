import { redirect } from 'next/navigation';
import { auth } from '@/auth';

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();
  if (!session?.user || !(session as { isAdmin?: boolean }).isAdmin) {
    redirect('/');
  }
  return <>{children}</>;
}
