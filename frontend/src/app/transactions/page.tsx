'use client';
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { Transaction, Category, TransactionPatch } from '@/lib/types';
import { Trash2, Tag } from 'lucide-react';

export default function TransactionsPage() {
  const qc = useQueryClient();
  const [month, setMonth] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [direction, setDirection] = useState('');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editCategoryId, setEditCategoryId] = useState<string>('');

  const params = new URLSearchParams({ limit: '50', offset: '0' });
  if (month) params.set('month', month);
  if (categoryId) params.set('category_id', categoryId);
  if (direction) params.set('direction', direction);

  const { data: transactions = [] } = useQuery({
    queryKey: ['transactions', month, categoryId, direction],
    queryFn: () => api.get<Transaction[]>(`/transactions?${params}`),
  });

  const { data: categories = [] } = useQuery({
    queryKey: ['categories'],
    queryFn: () => api.get<Category[]>('/categories'),
  });

  const patchMutation = useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: TransactionPatch }) =>
      api.patch<Transaction>(`/transactions/${id}`, patch),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['transactions'] }); setEditingId(null); },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.delete(`/transactions/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['transactions'] }),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Transactions</h1>

      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        <input type="month" value={month} onChange={(e) => setMonth(e.target.value)}
          className="border rounded-lg px-3 py-1.5 text-sm" placeholder="All months" />
        <select value={direction} onChange={(e) => setDirection(e.target.value)}
          className="border rounded-lg px-3 py-1.5 text-sm">
          <option value="">All directions</option>
          <option value="debit">Debit</option>
          <option value="credit">Credit</option>
        </select>
        <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)}
          className="border rounded-lg px-3 py-1.5 text-sm">
          <option value="">All categories</option>
          {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </div>

      {/* List */}
      {transactions.length === 0 ? (
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
                    onClick={() => patchMutation.mutate({
                      id: tx.id,
                      patch: { category_id: editCategoryId ? Number(editCategoryId) : null }
                    })}
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
                        <span
                          className="inline-block w-2 h-2 rounded-full"
                          style={{ backgroundColor: tx.category?.color ?? '#9ca3af' }}
                        />
                        {tx.category?.name ?? 'Uncategorized'}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={`font-bold ${tx.direction === 'debit' ? 'text-red-600' : 'text-green-600'}`}>
                      {tx.direction === 'debit' ? '-' : '+'}${Number(tx.amount).toFixed(2)}
                    </span>
                    <button onClick={() => { setEditingId(tx.id); setEditCategoryId(String(tx.category_id ?? '')); }}
                      className="text-gray-400 hover:text-indigo-600">
                      <Tag size={15} />
                    </button>
                    <button onClick={() => { if (confirm('Delete this transaction?')) deleteMutation.mutate(tx.id); }}
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
    </div>
  );
}
