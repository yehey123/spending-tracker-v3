'use client';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { LayoutDashboard, ArrowLeftRight, Upload, Settings, Flag, Wallet, LogOut, ShieldCheck, Monitor } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useSession } from 'next-auth/react';
import { api } from '@/lib/api';

const items = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/transactions', label: 'Transactions', icon: ArrowLeftRight },
  { href: '/upload', label: 'Upload', icon: Upload },
  { href: '/review', label: 'Review', icon: Flag },
  { href: '/accounts', label: 'Accounts', icon: Wallet },
  { href: '/settings', label: 'Settings', icon: Settings },
  { href: '/settings/devices', label: 'Devices', icon: Monitor },
];

export default function SideNav() {
  const pathname = usePathname();
  const router = useRouter();
  const { data: session } = useSession();
  const isAdmin = (session as any)?.isAdmin ?? false;

  const handleLogout = async () => {
    await fetch('/api/auth/logout', { method: 'POST' }).catch(() => {});
    router.push('/login');
  };

  const { data: flagCount } = useQuery({
    queryKey: ['flags-count'],
    queryFn: () => api.get<{ count: number }>('/flags/count'),
    refetchInterval: 30000,
  });

  return (
    <aside className="hidden md:flex flex-col w-56 min-h-screen bg-white border-r border-gray-200 p-4 gap-1">
      <div className="text-lg font-bold text-indigo-600 mb-6 px-2">💳 SpendTracker</div>
      {items.map(({ href, label, icon: Icon }) => {
        const active = pathname === href;
        const showBadge = href === '/review' && (flagCount?.count ?? 0) > 0;
        return (
          <Link
            key={href}
            href={href}
            className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
              active
                ? 'bg-indigo-50 text-indigo-700'
                : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
            }`}
          >
            <div className="relative">
              <Icon size={18} />
              {showBadge && (
                <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full w-4 h-4 flex items-center justify-center leading-none">
                  {(flagCount?.count ?? 0) > 9 ? '9+' : flagCount!.count}
                </span>
              )}
            </div>
            {label}
          </Link>
        );
      })}
      {isAdmin && (
        <Link
          href="/admin"
          className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
            pathname === '/admin'
              ? 'bg-indigo-50 text-indigo-700'
              : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
          }`}
        >
          <ShieldCheck size={18} />
          Admin
        </Link>
      )}
      <button
        onClick={handleLogout}
        className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-gray-600 hover:bg-gray-50 hover:text-gray-900 transition-colors mt-auto"
      >
        <LogOut size={18} />
        Sign out
      </button>
    </aside>
  );
}
