import type { NextAuthConfig } from "next-auth";

// Edge-safe subset used by middleware.ts. It must NOT run the token-refresh jwt callback:
// middleware runs in a separate (edge) runtime with its own memory, so refreshing there would
// bypass the single-flight map in token-refresh.ts and double-spend the single-use refresh token.
export const authConfig: NextAuthConfig = {
  providers: [],
  callbacks: {
    authorized({ auth }) {
      return !!auth?.user;
    },
  },
  session: { strategy: "jwt" },
  pages: {
    signIn: "/login",
  },
};
