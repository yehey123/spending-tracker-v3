import NextAuth from 'next-auth';
import { authConfig } from '@/auth.config';

// Auth gate only (no refresh): see auth.config.ts.
export const { auth: middleware } = NextAuth(authConfig);

export const config = {
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico|login|register|request-access).*)'],
};
