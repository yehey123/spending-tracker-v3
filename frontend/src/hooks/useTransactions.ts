'use client';
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { Transaction, TransactionCreate, TransactionPatch } from '@/lib/types';

const PAGE_SIZE = 50;

export interface TransactionFilters {
  month: string;
  categoryId: string;
  direction: string;
}

export function useTransactionFilters() {
  const [month, setMonth] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [direction, setDirection] = useState('');
  return { month, setMonth, categoryId, setCategoryId, direction, setDirection };
}

export function useTransactions(filters: TransactionFilters) {
  const [offset, setOffset] = useState(0);

  // Reset to first page whenever filters change
  const filtersKey = `${filters.month}|${filters.categoryId}|${filters.direction}`;
  const [prevFiltersKey, setPrevFiltersKey] = useState(filtersKey);
  if (filtersKey !== prevFiltersKey) {
    setPrevFiltersKey(filtersKey);
    setOffset(0);
  }

  const query = useQuery({
    queryKey: ['transactions', filters, offset],
    queryFn: () => {
      const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
      if (filters.month) params.set('month', filters.month);
      if (filters.categoryId) params.set('category_id', filters.categoryId);
      if (filters.direction) params.set('direction', filters.direction);
      return api.get<Transaction[]>(`/transactions?${params}`);
    },
  });

  const transactions = query.data ?? [];
  const hasMore = transactions.length === PAGE_SIZE;
  const hasPrev = offset > 0;

  return {
    ...query,
    transactions,
    offset,
    page: Math.floor(offset / PAGE_SIZE) + 1,
    hasMore,
    hasPrev,
    nextPage: () => setOffset((o) => o + PAGE_SIZE),
    prevPage: () => setOffset((o) => Math.max(0, o - PAGE_SIZE)),
  };
}

export function useTransactionMutations() {
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: ['transactions'] });

  const patchMutation = useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: TransactionPatch }) =>
      api.patch<{ id: number; re_categorized: number; reversal_id?: number; correction_id?: number }>(
        `/transactions/${id}`, patch
      ),
    onSuccess: invalidate,
  });

  const reverseMutation = useMutation({
    mutationFn: ({ id, reason }: { id: number; reason: string }) =>
      api.post(`/transactions/${id}/reverse`, { reason }),
    onSuccess: invalidate,
  });

  const createMutation = useMutation({
    mutationFn: (body: TransactionCreate) => api.post<Transaction>('/transactions', body),
    onSuccess: invalidate,
  });

  return { patchMutation, reverseMutation, createMutation };
}

interface TransactionDraft {
  date: string;
  amount: number;
  description: string;
  direction: 'debit' | 'credit';
  category_id: string;
  currency: string;
}

const emptyDraft = (): TransactionDraft => ({
  date: new Date().toISOString().slice(0, 10),
  amount: 0,
  description: '',
  direction: 'debit',
  category_id: '',
  currency: '',
});

export function useAddTransactionForm() {
  const [show, setShow] = useState(false);
  const [draft, setDraft] = useState(emptyDraft);

  const reset = () => { setDraft(emptyDraft); setShow(false); };

  const buildPayload = (): TransactionCreate | null => {
    if (!draft.description.trim() || draft.amount <= 0) return null;
    return {
      ...draft,
      category_id: draft.category_id ? Number(draft.category_id) : null,
      date: new Date(draft.date).toISOString(),
      currency: draft.currency || null,
    };
  };

  return { show, setShow, draft, setDraft, reset, buildPayload };
}
