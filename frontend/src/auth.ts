import NextAuth, { type NextAuthConfig } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";

import { authConfig as edgeAuthConfig } from "@/auth.config";
import {
  API_BASE,
  jwtExpiresMs,
  readRefreshCookie,
  refreshBackendToken,
} from "@/lib/token-refresh";

// Refresh the backend access token this long before it expires.
const REFRESH_SKEW_MS = 60_000;

export const authConfig: NextAuthConfig = {
  providers: [
    CredentialsProvider({
      name: "Email",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) return null;
        const res = await fetch(`${API_BASE}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: credentials.email,
            password: credentials.password,
          }),
        });
        if (!res.ok) return null;
        const data = await res.json();
        const refreshToken = readRefreshCookie(res);
        let accessTokenExpires: number | undefined;
        try {
          accessTokenExpires = jwtExpiresMs(data.access_token);
        } catch {
          accessTokenExpires = undefined;
        }
        return {
          id: credentials.email as string,
          accessToken: data.access_token,
          accessTokenExpires,
          refreshToken,
          isAdmin: data.is_admin ?? false,
        };
      },
    }),
  ],
  callbacks: {
    ...edgeAuthConfig.callbacks,
    async jwt({ token, user }) {
      if (user) {
        // Sign-in: store everything the backend gave us.
        token.accessToken = (user as any).accessToken;
        token.accessTokenExpires = (user as any).accessTokenExpires;
        token.refreshToken = (user as any).refreshToken ?? undefined;
        token.isAdmin = (user as any).isAdmin ?? false;
        delete token.error;
        return token;
      }
      // Unknown expiry or no refresh token (older session): leave as is.
      if (!token.accessTokenExpires || !token.refreshToken) return token;
      if (Date.now() < token.accessTokenExpires - REFRESH_SKEW_MS) return token;
      try {
        const r = await refreshBackendToken(token.refreshToken);
        token.accessToken = r.accessToken;
        token.accessTokenExpires = r.accessTokenExpires;
        token.refreshToken = r.refreshToken;
        delete token.error;
      } catch {
        token.error = "RefreshTokenError";
      }
      return token;
    },
    async session({ session, token }) {
      // The refresh token is never exposed to the client session.
      session.accessToken = token.accessToken as string | undefined;
      session.error = token.error;
      (session as any).isAdmin = token.isAdmin ?? false;
      return session;
    },
  },
  session: { strategy: "jwt" },
  pages: {
    signIn: "/login",
  },
};

export const { handlers, auth, signIn, signOut } = NextAuth(authConfig);
