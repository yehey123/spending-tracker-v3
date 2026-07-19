'use client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { Category } from '@/lib/types';
import { CheckCircle2, XCircle } from 'lucide-react';

interface FlagItem {
  id: number;
  transaction_id: number;
  flag_type: string;
  status: string;
  flag_metadata: {
    suggested_category_id: number;
    confidence: number;
    merchant_key: string;
  } | null;
  created_at: string | null;
}

export default function ReviewPage() {
  const qc = useQueryClient();

  const { data: flags = [] } = useQuery({
    queryKey: ['flags'],
    queryFn: () => api.get<FlagItem[]>('/flags'),
  });

  const { data: categories = [] } = useQuery({
    queryKey: ['categories'],
    queryFn: () => api.get<Category[]>('/categories'),
  });

  const categoryMap = new Map(categories.map((c) => [c.id, c]));

  const patchFlag = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      api.patch(`/flags/${id}`, { status }),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ['flags'] });
      if (variables.status === 'confirmed') {
        qc.invalidateQueries({ queryKey: ['transactions'] });
      }
    },
  });

  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold">Review Suggestions</h1>
        {flags.length > 0 && (
          <span className="bg-amber-100 text-amber-800 text-xs font-semibold px-2.5 py-1 rounded-full">
            {flags.length}
          </span>
        )}
      </div>

      {flags.length === 0 ? (
        <div className="text-center text-gray-500 py-16">No open suggestions</div>
      ) : (
        <ul className="space-y-3">
          {flags.map((flag) => {
            const meta = flag.flag_metadata;
            const category = meta ? categoryMap.get(meta.suggested_category_id) : null;
            const confidence = meta?.confidence ?? 0;
            const isPending = patchFlag.isPending && patchFlag.variables?.id === flag.id;

            return (
              <li key={flag.id} className="bg-white rounded-xl p-5 shadow-sm space-y-3">
                <p className="font-medium text-base">{meta?.merchant_key ?? '—'}</p>

                <div className="space-y-1">
                  <div className="w-full bg-gray-100 rounded-full h-1.5">
                    <div
                      className="bg-indigo-500 h-1.5 rounded-full"
                      style={{ width: `${(confidence * 100).toFixed(0)}%` }}
                    />
                  </div>
                  <p className="text-xs text-gray-500">{(confidence * 100).toFixed(0)}% confidence</p>
                </div>

                <div className="flex items-center gap-2">
                  <span
                    className="w-2.5 h-2.5 rounded-full inline-block flex-shrink-0"
                    style={{ backgroundColor: category?.color ?? '#d1d5db' }}
                  />
                  <span className="text-sm text-gray-700">{category?.name ?? 'Unknown category'}</span>
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={() => patchFlag.mutate({ id: flag.id, status: 'confirmed' })}
                    disabled={isPending}
                    className="flex items-center gap-1.5 bg-green-600 text-white px-3 py-1.5 rounded-lg text-sm disabled:opacity-50"
                  >
                    <CheckCircle2 size={15} /> Accept
                  </button>
                  <button
                    onClick={() => patchFlag.mutate({ id: flag.id, status: 'rejected' })}
                    disabled={isPending}
                    className="flex items-center gap-1.5 bg-red-500 text-white px-3 py-1.5 rounded-lg text-sm disabled:opacity-50"
                  >
                    <XCircle size={15} /> Reject
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
