import { signOut } from '@/auth';
import { NextResponse } from 'next/server';

export async function POST() {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? '/api';
  await fetch(`${baseUrl}/auth/logout`, {
    method: 'POST',
    credentials: 'include',
  }).catch(() => {});

  await signOut({ redirect: false });

  return NextResponse.json({ ok: true });
}
