'use client';
import { useParams, useRouter } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { StagedReviewResponse, Category } from '@/lib/types';
import { StagedTransactionRow } from '@/components/statements/StagedTransactionRow';
import { AlertTriangle, CheckCircle2 } from 'lucide-react';

export default function StatementReviewPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['staged', id],
    queryFn: () => api.get<StagedReviewResponse>(`/statements/${id}/staged`),
  });

  const { data: categories = [] } = useQuery({
    queryKey: ['categories'],
    queryFn: () => api.get<Category[]>('/categories'),
  });

  const commit = useMutation({
    mutationFn: () => api.post(`/statements/${id}/commit`, {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['transactions'] });
      router.push('/transactions');
    },
  });

  const discard = useMutation({
    mutationFn: () => api.post(`/statements/${id}/discard`, {}),
    onSuccess: () => router.push('/upload'),
  });

  if (isLoading) {
    return <div className="text-center py-12 text-gray-400">Loading…</div>;
  }

  if (!data) {
    return <div className="text-center py-12 text-gray-400">Statement not found.</div>;
  }

  return (
    <div className="max-w-xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Review Statement</h1>

      {data.total_match ? (
        <div className="flex items-center gap-2 bg-green-50 border border-green-200 rounded-xl p-3 text-green-700 text-sm">
          <CheckCircle2 size={18} />
          <span>Totals match</span>
        </div>
      ) : (
        <div className="flex items-center gap-2 bg-amber-50 border border-amber-200 rounded-xl p-3 text-amber-700 text-sm">
          <AlertTriangle size={18} />
          <span>
            Gap detected: extracted ${data.extracted_total}
            {data.declared_total ? ` vs declared $${data.declared_total}` : ' (no declared total)'}
          </span>
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm divide-y divide-gray-100 px-4">
        {data.transactions.length === 0 ? (
          <p className="text-center py-8 text-gray-400 text-sm">No staged transactions.</p>
        ) : (
          data.transactions.map((tx) => (
            <StagedTransactionRow
              key={tx.id}
              tx={tx}
              categories={categories}
              onUpdated={() => refetch()}
            />
          ))
        )}
      </div>

      <div className="flex gap-3">
        <button
          onClick={() => commit.mutate()}
          disabled={commit.isPending}
          className="flex-1 bg-indigo-600 text-white py-3 rounded-xl font-semibold hover:bg-indigo-700 transition-colors disabled:opacity-50"
        >
          {commit.isPending ? 'Committing…' : `Commit ${data.transactions.length} transaction${data.transactions.length !== 1 ? 's' : ''}`}
        </button>
        <button
          onClick={() => discard.mutate()}
          disabled={discard.isPending}
          className="px-6 py-3 rounded-xl border border-red-200 text-red-600 hover:bg-red-50 transition-colors disabled:opacity-50"
        >
          {discard.isPending ? 'Discarding…' : 'Discard'}
        </button>
      </div>
    </div>
  );
}
