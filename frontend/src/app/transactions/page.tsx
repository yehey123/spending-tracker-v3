'use client';
import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { Category, AppSettings, TransactionPatch } from '@/lib/types';
import { Tag, Plus, X, ChevronLeft, ChevronRight, RotateCcw } from 'lucide-react';
import {
  useTransactionFilters,
  useTransactions,
  useTransactionMutations,
  useAddTransactionForm,
} from '@/hooks/useTransactions';

interface EditDraft {
  amount: string;
  date: string;
  direction: 'debit' | 'credit';
  description: string;
  categoryId: string;
}

const REVERSE_REASONS = [
  { value: 'duplicate', label: 'Duplicate charge' },
  { value: 'bank_reversal', label: 'Bank reversal' },
  { value: 'user_error', label: 'User error' },
  { value: 'receipt_superseded', label: 'Receipt superseded' },
  { value: 'user_correction', label: 'User correction' },
  { value: 'other', label: 'Other' },
];

function CategorySelect({
  value,
  onChange,
  categories,
  className,
}: {
  value: string;
  onChange: (v: string) => void;
  categories: Category[];
  className?: string;
}) {
  const roots = categories.filter((c) => c.parent_id === null);
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className={className}>
      <option value="">Uncategorized</option>
      {roots.map((parent) => (
        <optgroup key={parent.id} label={parent.name}>
          <option value={String(parent.id)}>{parent.name}</option>
          {(parent.children ?? []).map((child) => (
            <option key={child.id} value={String(child.id)}>
              {'  '}{child.name}
            </option>
          ))}
        </optgroup>
      ))}
    </select>
  );
}

export default function TransactionsPage() {
  const filters = useTransactionFilters();
  const { transactions, isLoading, page, hasMore, hasPrev, nextPage, prevPage } =
    useTransactions(filters);
  const { patchMutation, reverseMutation, createMutation } = useTransactionMutations();
  const form = useAddTransactionForm();

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState<EditDraft>({
    amount: '',
    date: '',
    direction: 'debit',
    description: '',
    categoryId: '',
  });
  const [reversingId, setReversingId] = useState<number | null>(null);
  const [reverseReason, setReverseReason] = useState('user_error');

  const { data: categories = [] } = useQuery({
    queryKey: ['categories'],
    queryFn: () => api.get<Category[]>('/categories'),
  });

  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: () => api.get<AppSettings>('/settings'),
  });

  useEffect(() => {
    if (settings?.home_currency && !form.draft.currency) {
      form.setDraft((p) => ({ ...p, currency: settings.home_currency! }));
    }
  }, [settings?.home_currency]);

  const handleCreate = () => {
    const payload = form.buildPayload();
    if (!payload) return;
    createMutation.mutate(payload, { onSuccess: form.reset });
  };

  const openEdit = (tx: (typeof transactions)[0]) => {
    setReversingId(null);
    setEditingId(tx.id);
    setEditDraft({
      amount: tx.amount,
      date: tx.date.slice(0, 10),
      direction: tx.direction,
      description: tx.description,
      categoryId: String(tx.category_id ?? ''),
    });
  };

  const saveEdit = (txId: number, orig: (typeof transactions)[0]) => {
    const patch: TransactionPatch = {};
    if (editDraft.amount && editDraft.amount !== orig.amount) patch.amount = parseFloat(editDraft.amount);
    if (editDraft.date && editDraft.date !== orig.date.slice(0, 10)) patch.date = new Date(editDraft.date).toISOString();
    if (editDraft.direction !== orig.direction) patch.direction = editDraft.direction;
    if (editDraft.description !== orig.description) patch.description = editDraft.description;
    const newCatId = editDraft.categoryId ? Number(editDraft.categoryId) : null;
    if (newCatId !== orig.category_id) patch.category_id = newCatId;
    if (Object.keys(patch).length > 0) {
      patchMutation.mutate({ id: txId, patch }, { onSuccess: () => setEditingId(null) });
    } else {
      setEditingId(null);
    }
  };

  const confirmReverse = (txId: number) => {
    reverseMutation.mutate(
      { id: txId, reason: reverseReason },
      { onSuccess: () => setReversingId(null) },
    );
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
          <div className="grid grid-cols-3 gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-xs text-gray-500">Currency</label>
              <input type="text" maxLength={3} value={form.draft.currency}
                onChange={(e) => form.setDraft((p) => ({ ...p, currency: e.target.value.toUpperCase() }))}
                placeholder={settings?.home_currency ?? 'PHP'}
                className="border rounded-lg px-3 py-1.5 text-sm uppercase" />
            </div>
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
              <CategorySelect
                value={form.draft.category_id}
                onChange={(v) => form.setDraft((p) => ({ ...p, category_id: v }))}
                categories={categories}
                className="border rounded-lg px-3 py-1.5 text-sm"
              />
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
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-2">
                    <div className="flex flex-col gap-1">
                      <label className="text-xs text-gray-500">Date</label>
                      <input
                        type="date"
                        value={editDraft.date}
                        onChange={(e) => setEditDraft((d) => ({ ...d, date: e.target.value }))}
                        className="border rounded-lg px-2 py-1 text-sm"
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <label className="text-xs text-gray-500">Amount</label>
                      <input
                        type="number"
                        min="0.01"
                        step="0.01"
                        value={editDraft.amount}
                        onChange={(e) => setEditDraft((d) => ({ ...d, amount: e.target.value }))}
                        className="border rounded-lg px-2 py-1 text-sm"
                      />
                    </div>
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-gray-500">Description</label>
                    <input
                      type="text"
                      value={editDraft.description}
                      onChange={(e) => setEditDraft((d) => ({ ...d, description: e.target.value }))}
                      className="border rounded-lg px-2 py-1 text-sm w-full"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="flex flex-col gap-1">
                      <label className="text-xs text-gray-500">Direction</label>
                      <select
                        value={editDraft.direction}
                        onChange={(e) => setEditDraft((d) => ({ ...d, direction: e.target.value as 'debit' | 'credit' }))}
                        className="border rounded-lg px-2 py-1 text-sm"
                      >
                        <option value="debit">Debit (expense)</option>
                        <option value="credit">Credit (income)</option>
                      </select>
                    </div>
                    <div className="flex flex-col gap-1">
                      <label className="text-xs text-gray-500">Category</label>
                      <CategorySelect
                        value={editDraft.categoryId}
                        onChange={(v) => setEditDraft((d) => ({ ...d, categoryId: v }))}
                        categories={categories}
                        className="border rounded-lg px-2 py-1 text-sm"
                      />
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => saveEdit(tx.id, tx)}
                      disabled={patchMutation.isPending}
                      className="bg-indigo-600 text-white text-xs px-4 py-1.5 rounded-lg disabled:opacity-50"
                    >
                      {patchMutation.isPending ? 'Saving…' : 'Save'}
                    </button>
                    <button onClick={() => setEditingId(null)} className="text-gray-400 text-xs px-2">Cancel</button>
                  </div>
                </div>
              ) : reversingId === tx.id ? (
                <div className="space-y-2">
                  <p className="text-sm font-medium text-gray-700">Reverse this transaction?</p>
                  <select
                    value={reverseReason}
                    onChange={(e) => setReverseReason(e.target.value)}
                    className="border rounded-lg px-2 py-1 text-sm w-full"
                  >
                    {REVERSE_REASONS.map((r) => (
                      <option key={r.value} value={r.value}>{r.label}</option>
                    ))}
                  </select>
                  <div className="flex gap-2">
                    <button
                      onClick={() => confirmReverse(tx.id)}
                      disabled={reverseMutation.isPending}
                      className="bg-red-600 text-white text-xs px-4 py-1.5 rounded-lg disabled:opacity-50"
                    >
                      {reverseMutation.isPending ? 'Reversing…' : 'Confirm Reversal'}
                    </button>
                    <button onClick={() => setReversingId(null)} className="text-gray-400 text-xs px-2">Cancel</button>
                  </div>
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
                      {tx.direction === 'debit' ? '-' : '+'}{tx.currency ?? settings?.home_currency ?? ''} {Number(tx.amount).toFixed(2)}
                    </span>
                    {tx.currency && settings?.home_currency && tx.currency !== settings.home_currency && (
                      <span className="text-xs bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded font-medium">
                        {tx.currency}
                      </span>
                    )}
                    <button
                      onClick={() => openEdit(tx)}
                      className="text-gray-400 hover:text-indigo-600"
                      title="Edit transaction"
                    >
                      <Tag size={15} />
                    </button>
                    <button
                      onClick={() => { setEditingId(null); setReversingId(tx.id); setReverseReason('user_error'); }}
                      className="text-gray-400 hover:text-red-600"
                      title="Reverse transaction"
                    >
                      <RotateCcw size={15} />
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
