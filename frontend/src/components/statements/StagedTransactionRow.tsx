'use client';
import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { StagedTransaction, Category } from '@/lib/types';
import { Pencil, Check, X } from 'lucide-react';

interface Props {
  tx: StagedTransaction;
  categories: Category[];
  onUpdated: () => void;
}

export function StagedTransactionRow({ tx, categories, onUpdated }: Props) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [description, setDescription] = useState(tx.description);
  const [amount, setAmount] = useState(tx.amount);
  const [direction, setDirection] = useState<'debit' | 'credit'>(tx.direction);
  const [categoryId, setCategoryId] = useState<string>(tx.category_id?.toString() ?? '');
  const [currency, setCurrency] = useState<string>(tx.currency ?? '');

  const patch = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.patch(`/staged-transactions/${tx.id}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['staged', tx.id] });
      setEditing(false);
      onUpdated();
    },
  });

  const handleSave = () => {
    patch.mutate({
      description,
      amount: parseFloat(amount),
      direction,
      category_id: categoryId ? parseInt(categoryId) : null,
      ...(currency ? { currency: currency.toUpperCase() } : {}),
    });
  };

  const directionBadge = tx.direction === 'debit'
    ? 'bg-red-100 text-red-700'
    : 'bg-green-100 text-green-700';

  if (!editing) {
    return (
      <div className="flex items-center justify-between py-2 px-1 hover:bg-gray-50 rounded">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${directionBadge}`}>
              {tx.direction}
            </span>
            <span className="text-sm truncate">{tx.description}</span>
          </div>
          <div className="text-xs text-gray-400 mt-0.5">{tx.date}</div>
        </div>
        <div className="flex items-center gap-3 ml-2 shrink-0">
          <span className="text-sm font-medium">{tx.currency ?? ''} {tx.amount}</span>
          <button onClick={() => setEditing(true)} className="text-gray-400 hover:text-indigo-600">
            <Pencil size={14} />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="py-2 px-1 space-y-2 bg-indigo-50 rounded">
      <input
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        className="border rounded px-2 py-1 text-sm w-full"
        placeholder="Description"
      />
      <div className="flex gap-2">
        <input
          type="number"
          step="0.01"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          className="border rounded px-2 py-1 text-sm w-28"
          placeholder="Amount"
        />
        <input
          type="text"
          maxLength={3}
          value={currency}
          onChange={(e) => setCurrency(e.target.value.toUpperCase())}
          className="border rounded px-2 py-1 text-sm w-16 uppercase"
          placeholder="CCY"
        />
        <select
          value={direction}
          onChange={(e) => setDirection(e.target.value as 'debit' | 'credit')}
          className="border rounded px-2 py-1 text-sm"
        >
          <option value="debit">Debit</option>
          <option value="credit">Credit</option>
        </select>
        <select
          value={categoryId}
          onChange={(e) => setCategoryId(e.target.value)}
          className="border rounded px-2 py-1 text-sm flex-1"
        >
          <option value="">No category</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
      </div>
      <div className="flex gap-2">
        <button
          onClick={handleSave}
          disabled={patch.isPending}
          className="flex items-center gap-1 bg-indigo-600 text-white px-3 py-1 rounded text-sm"
        >
          <Check size={13} /> Save
        </button>
        <button
          onClick={() => setEditing(false)}
          className="flex items-center gap-1 text-gray-500 px-3 py-1 rounded text-sm border"
        >
          <X size={13} /> Cancel
        </button>
      </div>
    </div>
  );
}
