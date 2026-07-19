'use client';
import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useTransactionSearch } from '@/hooks/useTransactionSearch';
import { Link2Off, Search } from 'lucide-react';

// ReceiptStatement shape returned by GET /receipts
interface ReceiptStatement {
  id: number;
  filename: string;
  status: string;
  uploaded_at: string;
  declared_total: string | null;
  suggested_parent_ids: number[];
}

interface Props {
  receipt: ReceiptStatement;
  onLinked: () => void;
  onUnlinked: () => void;
}

export function ReceiptCard({ receipt, onLinked, onUnlinked }: Props) {
  const qc = useQueryClient();
  const [searchQ, setSearchQ] = useState('');
  const [showSearch, setShowSearch] = useState(false);
  const { results, isFetching } = useTransactionSearch(searchQ, true); // linkableOnly=true

  const link = useMutation({
    mutationFn: (txId: number) =>
      api.post(`/receipts/${receipt.id}/link`, { transaction_id: txId }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['receipts'] }); setShowSearch(false); onLinked(); },
  });

  const unlink = useMutation({
    mutationFn: () => api.post(`/receipts/${receipt.id}/unlink`, {}),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['receipts'] }); onUnlinked(); },
  });

  return (
    <div className="bg-white rounded-xl p-4 shadow-sm space-y-3">
      {/* Header row */}
      <div className="flex items-start justify-between">
        <div>
          <div className="font-medium text-sm truncate max-w-xs">{receipt.filename}</div>
          <div className="text-xs text-gray-400 mt-0.5">
            {new Date(receipt.uploaded_at).toLocaleDateString()}
            {receipt.declared_total ? ` · $${receipt.declared_total}` : ''}
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowSearch((v) => !v)}
            className="flex items-center gap-1 text-xs border rounded-lg px-2 py-1 hover:bg-gray-50"
          >
            <Search size={12} /> Link
          </button>
          <button
            onClick={() => unlink.mutate()}
            disabled={unlink.isPending}
            className="flex items-center gap-1 text-xs border border-red-200 text-red-600 rounded-lg px-2 py-1 hover:bg-red-50 disabled:opacity-50"
          >
            <Link2Off size={12} /> Unlink
          </button>
        </div>
      </div>

      {/* Search panel */}
      {showSearch && (
        <div className="space-y-2">
          <input
            value={searchQ}
            onChange={(e) => setSearchQ(e.target.value)}
            placeholder="Search transactions…"
            className="border rounded-lg px-3 py-1.5 text-sm w-full"
          />
          {isFetching && <p className="text-xs text-gray-400">Searching…</p>}
          {results.length > 0 && (
            <ul className="divide-y divide-gray-100 max-h-40 overflow-y-auto rounded border">
              {results.map((tx) => (
                <li key={tx.id}
                  className="flex items-center justify-between px-3 py-2 hover:bg-indigo-50 cursor-pointer"
                  onClick={() => link.mutate(tx.id)}
                >
                  <span className="text-sm truncate">{tx.description}</span>
                  <span className="text-xs text-gray-500 ml-2 shrink-0">${tx.amount}</span>
                </li>
              ))}
            </ul>
          )}
          {!isFetching && searchQ.length >= 2 && results.length === 0 && (
            <p className="text-xs text-gray-400 text-center py-2">No matching transactions</p>
          )}
        </div>
      )}

      {/* Link error */}
      {link.isError && (
        <p className="text-xs text-red-500">
          {(link.error as Error).message.includes('AMOUNT_MISMATCH')
            ? 'Amount mismatch — receipt total differs from transaction by more than 5%'
            : (link.error as Error).message}
        </p>
      )}
    </div>
  );
}
