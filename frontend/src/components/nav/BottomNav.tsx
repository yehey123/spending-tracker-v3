'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, ArrowLeftRight, Upload, Settings, Flag, Wallet } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';

const tabs = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/transactions', label: 'Transactions', icon: ArrowLeftRight },
  { href: '/upload', label: 'Upload', icon: Upload },
  { href: '/review', label: 'Review', icon: Flag },
  { href: '/accounts', label: 'Accounts', icon: Wallet },
  { href: '/settings', label: 'Settings', icon: Settings },
];

export default function BottomNav() {
  const pathname = usePathname();
  const { data: flagCount } = useQuery({
    queryKey: ['flags-count'],
    queryFn: () => api.get<{ count: number }>('/flags/count'),
    refetchInterval: 30000,
  });

  return (
    <nav className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 flex md:hidden z-50">
      {tabs.map(({ href, label, icon: Icon }) => {
        const active = pathname === href;
        const showBadge = href === '/review' && (flagCount?.count ?? 0) > 0;
        return (
          <Link
            key={href}
            href={href}
            className={`flex-1 flex flex-col items-center py-2 text-xs gap-1 ${
              active ? 'text-indigo-600' : 'text-gray-500'
            }`}
          >
            <div className="relative">
              <Icon size={20} />
              {showBadge && (
                <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full w-4 h-4 flex items-center justify-center leading-none">
                  {(flagCount?.count ?? 0) > 9 ? '9+' : flagCount!.count}
                </span>
              )}
            </div>
            <span>{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
