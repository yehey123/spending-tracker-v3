'use client';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { Category } from '@/lib/types';
import { Trash2, Tag, Plus, X, ChevronLeft, ChevronRight } from 'lucide-react';
import {
  useTransactionFilters,
  useTransactions,
  useTransactionMutations,
  useAddTransactionForm,
} from '@/hooks/useTransactions';

export default function TransactionsPage() {
  const filters = useTransactionFilters();
  const { transactions, isLoading, page, hasMore, hasPrev, nextPage, prevPage } =
    useTransactions(filters);
  const { patchMutation, deleteMutation, createMutation } = useTransactionMutations();
  const form = useAddTransactionForm();

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editCategoryId, setEditCategoryId] = useState('');

  const { data: categories = [] } = useQuery({
    queryKey: ['categories'],
    queryFn: () => api.get<Category[]>('/categories'),
  });

  const handleCreate = () => {
    const payload = form.buildPayload();
    if (!payload) return;
    createMutation.mutate(payload, { onSuccess: form.reset });
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Transactions</h1>
        <button
          onClick={() => form.setShow((v) => !v)}
          className="flex items-center gap-1.5 bg-indigo-600 text-white text-sm px-3 py-1.5 rounded-lg hover:bg-indigo-700"
        >
          {form.show ? <X size={15} /> : <Plus size={15} />}
          {form.show ? 'Cancel' : 'Add transaction'}
        </button>
      </div>

      {form.show && (
        <div className="bg-white rounded-xl p-4 shadow-sm space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-xs text-gray-500">Date</label>
              <input type="date" value={form.draft.date}
                onChange={(e) => form.setDraft((p) => ({ ...p, date: e.target.value }))}
                className="border rounded-lg px-3 py-1.5 text-sm" />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-gray-500">Amount</label>
              <input type="number" min="0.01" step="0.01" value={form.draft.amount || ''}
                onChange={(e) => form.setDraft((p) => ({ ...p, amount: parseFloat(e.target.value) || 0 }))}
                placeholder="0.00"
                className="border rounded-lg px-3 py-1.5 text-sm" />
            </div>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500">Description</label>
            <input type="text" value={form.draft.description}
              onChange={(e) => form.setDraft((p) => ({ ...p, description: e.target.value }))}
              placeholder="e.g. Coffee shop"
              className="border rounded-lg px-3 py-1.5 text-sm w-full" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-xs text-gray-500">Direction</label>
              <select value={form.draft.direction}
                onChange={(e) => form.setDraft((p) => ({ ...p, direction: e.target.value as 'debit' | 'credit' }))}
                className="border rounded-lg px-3 py-1.5 text-sm">
                <option value="debit">Debit (expense)</option>
                <option value="credit">Credit (income)</option>
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs text-gray-500">Category (optional)</label>
              <select value={form.draft.category_id}
                onChange={(e) => form.setDraft((p) => ({ ...p, category_id: e.target.value }))}
                className="border rounded-lg px-3 py-1.5 text-sm">
                <option value="">Uncategorized</option>
                {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
          </div>
          <button
            onClick={handleCreate}
            disabled={createMutation.isPending || !form.draft.description.trim() || form.draft.amount <= 0}
            className="w-full bg-indigo-600 text-white text-sm py-2 rounded-lg hover:bg-indigo-700 disabled:opacity-50"
          >
            {createMutation.isPending ? 'Saving…' : 'Save transaction'}
          </button>
          {createMutation.isError && (
            <p className="text-xs text-red-500">{(createMutation.error as Error).message}</p>
          )}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        <input type="month" value={filters.month} onChange={(e) => filters.setMonth(e.target.value)}
          className="border rounded-lg px-3 py-1.5 text-sm" />
        <select value={filters.direction} onChange={(e) => filters.setDirection(e.target.value)}
          className="border rounded-lg px-3 py-1.5 text-sm">
          <option value="">All directions</option>
          <option value="debit">Debit</option>
          <option value="credit">Credit</option>
        </select>
        <select value={filters.categoryId} onChange={(e) => filters.setCategoryId(e.target.value)}
          className="border rounded-lg px-3 py-1.5 text-sm">
          <option value="">All categories</option>
          {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </div>

      {/* List */}
      {isLoading ? (
        <p className="text-center text-gray-400 py-12">Loading…</p>
      ) : transactions.length === 0 ? (
        <p className="text-center text-gray-400 py-12">No transactions found</p>
      ) : (
        <ul className="space-y-2">
          {transactions.map((tx) => (
            <li key={tx.id} className="bg-white rounded-xl p-4 shadow-sm">
              {editingId === tx.id ? (
                <div className="flex gap-2 items-center">
                  <select
                    value={editCategoryId}
                    onChange={(e) => setEditCategoryId(e.target.value)}
                    className="border rounded-lg px-2 py-1 text-sm flex-1"
                  >
                    <option value="">Uncategorized</option>
                    {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                  <button
                    onClick={() => {
                      patchMutation.mutate(
                        { id: tx.id, patch: { category_id: editCategoryId ? Number(editCategoryId) : null } },
                        { onSuccess: () => setEditingId(null) },
                      );
                    }}
                    className="bg-indigo-600 text-white text-xs px-3 py-1.5 rounded-lg"
                  >Save</button>
                  <button onClick={() => setEditingId(null)} className="text-gray-400 text-xs px-2">Cancel</button>
                </div>
              ) : (
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-medium text-sm">{tx.description}</div>
                    <div className="text-xs text-gray-400 mt-0.5">
                      {tx.date.slice(0, 10)} ·{' '}
                      <span className="inline-flex items-center gap-1">
                        <span className="inline-block w-2 h-2 rounded-full"
                          style={{ backgroundColor: tx.category?.color ?? '#9ca3af' }} />
                        {tx.category?.name ?? 'Uncategorized'}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={`font-bold ${tx.direction === 'debit' ? 'text-red-600' : 'text-green-600'}`}>
                      {tx.direction === 'debit' ? '-' : '+'}${Number(tx.amount).toFixed(2)}
                    </span>
                    <button
                      onClick={() => { setEditingId(tx.id); setEditCategoryId(String(tx.category_id ?? '')); }}
                      className="text-gray-400 hover:text-indigo-600">
                      <Tag size={15} />
                    </button>
                    <button
                      onClick={() => { if (confirm('Delete this transaction?')) deleteMutation.mutate(tx.id); }}
                      className="text-gray-400 hover:text-red-500">
                      <Trash2 size={15} />
                    </button>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {/* Pagination */}
      {(hasPrev || hasMore) && (
        <div className="flex items-center justify-center gap-4 pt-2">
          <button
            onClick={prevPage}
            disabled={!hasPrev}
            className="flex items-center gap-1 text-sm text-gray-600 disabled:opacity-30 hover:text-indigo-600"
          >
            <ChevronLeft size={16} /> Prev
          </button>
          <span className="text-sm text-gray-400">Page {page}</span>
          <button
            onClick={nextPage}
            disabled={!hasMore}
            className="flex items-center gap-1 text-sm text-gray-600 disabled:opacity-30 hover:text-indigo-600"
          >
            Next <ChevronRight size={16} />
          </button>
        </div>
      )}
    </div>
  );
}
