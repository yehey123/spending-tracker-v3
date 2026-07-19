'use client';
// Debounced infinite-scroll search hook for /transactions/search
// Used by ReceiptCard to search for linkable transactions

import { useInfiniteQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import type { Transaction } from '@/lib/types';

export function useTransactionSearch(query: string, linkableOnly = false) {
  // 1. 300ms debounce on query input
  const [debouncedQ, setDebouncedQ] = useState(query);
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(query), 300);
    return () => clearTimeout(t);
  }, [query]);

  // 2. useInfiniteQuery — skip entirely if debouncedQ.length < 2
  const result = useInfiniteQuery({
    queryKey: ['tx-search', debouncedQ, linkableOnly],
    queryFn: async ({ pageParam }: { pageParam: string | undefined }) => {
      // Build URL: /transactions/search?q=...&limit=20[&cursor=...][&linkable_only=true]
      const params = new URLSearchParams({ q: debouncedQ, limit: '20' });
      if (pageParam) params.set('cursor', pageParam);
      if (linkableOnly) params.set('linkable_only', 'true');
      return api.get<Transaction[]>(`/transactions/search?${params}`);
    },
    getNextPageParam: (lastPage: Transaction[]) => {
      // If fewer than 20 results, no next page
      if (lastPage.length < 20) return undefined;
      // Cursor = base64(JSON({date, id})) of last item
      const last = lastPage[lastPage.length - 1];
      return btoa(JSON.stringify({ date: last.date, id: last.id }));
    },
    initialPageParam: undefined as string | undefined,
    enabled: debouncedQ.length >= 2,
  });

  // 3. Flatten pages into single results array
  const results: Transaction[] = result.data?.pages.flat() ?? [];

  return {
    results,
    fetchNextPage: result.fetchNextPage,
    hasNextPage: result.hasNextPage,
    isFetching: result.isFetching,
  };
}
