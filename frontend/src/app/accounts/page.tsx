'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Pencil } from 'lucide-react';
import { Account } from '@/lib/types';

const ACCOUNT_TYPES = ['checking', 'savings', 'credit_card', 'cash', 'broker'] as const;

async function fetchAccounts(): Promise<Account[]> {
  const res = await fetch('/api/accounts');
  if (!res.ok) throw new Error('Failed to fetch accounts');
  return res.json();
}

export default function AccountsPage() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [editName, setEditName] = useState('');
  const [form, setForm] = useState({
    name: '', type: 'checking', currency: 'PHP',
    institution: '', opening_balance: '0', account_number: '',
  });

  const { data: accounts = [], isLoading } = useQuery<Account[]>({
    queryKey: ['accounts'],
    queryFn: fetchAccounts,
  });

  const createMutation = useMutation({
    mutationFn: async (body: Record<string, unknown>) => {
      const res = await fetch('/api/accounts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error('Failed to create account');
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['accounts'] });
      setShowForm(false);
      setForm({ name: '', type: 'checking', currency: 'PHP', institution: '', opening_balance: '0', account_number: '' });
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, name }: { id: number; name: string }) => {
      const res = await fetch(`/api/accounts/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      });
      if (!res.ok) throw new Error('Failed to update account');
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['accounts'] });
      setEditId(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      const res = await fetch(`/api/accounts/${id}`, { method: 'DELETE' });
      if (!res.ok && res.status !== 204) throw new Error('Failed to delete account');
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['accounts'] }),
  });

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    const body: Record<string, unknown> = {
      name: form.name,
      type: form.type,
      currency: form.currency,
      opening_balance: parseFloat(form.opening_balance) || 0,
    };
    if (form.institution) body.institution = form.institution;
    if (form.account_number) body.account_number = form.account_number;
    createMutation.mutate(body);
  };

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      <div className="bg-white px-4 pt-12 pb-4 shadow-sm">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">Accounts</h1>
          <button
            onClick={() => setShowForm(!showForm)}
            className="bg-indigo-600 text-white text-sm px-4 py-2 rounded-lg font-medium"
          >
            {showForm ? 'Cancel' : '+ Add'}
          </button>
        </div>
      </div>

      <div className="px-4 pt-4 space-y-3">
        {showForm && (
          <form onSubmit={handleCreate} className="bg-white rounded-xl p-4 shadow-sm space-y-3">
            <h2 className="font-semibold text-gray-800">New Account</h2>
            <input
              required
              placeholder="Account name"
              value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              className="w-full border rounded-lg px-3 py-2 text-sm"
            />
            <select
              value={form.type}
              onChange={e => setForm(f => ({ ...f, type: e.target.value }))}
              className="w-full border rounded-lg px-3 py-2 text-sm"
            >
              {ACCOUNT_TYPES.map(t => (
                <option key={t} value={t}>{t.replace('_', ' ')}</option>
              ))}
            </select>
            <div className="flex gap-2">
              <input
                placeholder="Currency (PHP)"
                value={form.currency}
                onChange={e => setForm(f => ({ ...f, currency: e.target.value }))}
                className="w-24 border rounded-lg px-3 py-2 text-sm"
              />
              <input
                type="number"
                placeholder="Opening balance"
                value={form.opening_balance}
                onChange={e => setForm(f => ({ ...f, opening_balance: e.target.value }))}
                className="flex-1 border rounded-lg px-3 py-2 text-sm"
              />
            </div>
            <input
              placeholder="Institution (optional)"
              value={form.institution}
              onChange={e => setForm(f => ({ ...f, institution: e.target.value }))}
              className="w-full border rounded-lg px-3 py-2 text-sm"
            />
            <input
              placeholder="Account number (optional, for auto-detect)"
              value={form.account_number}
              onChange={e => setForm(f => ({ ...f, account_number: e.target.value }))}
              className="w-full border rounded-lg px-3 py-2 text-sm"
            />
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="w-full bg-indigo-600 text-white py-2 rounded-lg text-sm font-medium disabled:opacity-50"
            >
              {createMutation.isPending ? 'Creating…' : 'Create Account'}
            </button>
            {createMutation.isError && (
              <p className="text-red-600 text-xs">{(createMutation.error as Error).message}</p>
            )}
          </form>
        )}

        {isLoading && <p className="text-center text-gray-400 py-8">Loading…</p>}

        {!isLoading && accounts.length === 0 && !showForm && (
          <div className="text-center py-12 text-gray-400">
            <p className="text-lg">No accounts yet</p>
            <p className="text-sm mt-1">Add an account to start tracking balances</p>
          </div>
        )}

        {accounts.map(acc => (
          <div key={acc.id} className="bg-white rounded-xl p-4 shadow-sm">
            <div className="flex items-start justify-between">
              <div>
                {editId === acc.id ? (
                  <div className="flex gap-2">
                    <input
                      value={editName}
                      onChange={e => setEditName(e.target.value)}
                      className="border rounded px-2 py-1 text-sm"
                    />
                    <button
                      onClick={() => updateMutation.mutate({ id: acc.id, name: editName })}
                      className="text-xs bg-indigo-600 text-white px-2 py-1 rounded"
                    >
                      Save
                    </button>
                    <button onClick={() => setEditId(null)} className="text-xs text-gray-400">✕</button>
                  </div>
                ) : (
                  <button
                    onClick={() => { setEditId(acc.id); setEditName(acc.name); }}
                    className="flex items-center gap-1.5 font-semibold text-gray-900 text-left hover:text-indigo-600 group"
                  >
                    {acc.name}
                    <Pencil size={12} className="text-gray-300 group-hover:text-indigo-400" />
                  </button>
                )}
                <span className="ml-2 text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
                  {acc.type.replace('_', ' ')}
                </span>
                {acc.last_four && (
                  <span className="ml-1 text-xs text-gray-400">••••{acc.last_four}</span>
                )}
                {acc.institution && (
                  <p className="text-xs text-gray-500 mt-0.5">{acc.institution}</p>
                )}
              </div>
              <button
                onClick={() => deleteMutation.mutate(acc.id)}
                className="text-xs text-red-400 hover:text-red-600 ml-2"
              >
                Remove
              </button>
            </div>
            <div className="mt-2 flex items-center justify-between">
              {acc.type === 'broker' ? (
                <a
                  href={`/portfolio/${acc.id}`}
                  className="text-sm text-indigo-600 font-medium hover:underline"
                >
                  View Portfolio →
                </a>
              ) : (
                <p className="text-sm text-gray-600">
                  Balance: {acc.currency} {parseFloat(acc.current_balance).toLocaleString('en-PH', { minimumFractionDigits: 2 })}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
