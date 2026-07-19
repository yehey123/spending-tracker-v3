'use client';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { ReceiptCard } from '@/components/receipts/ReceiptCard';

// ReceiptStatement shape (same as in ReceiptCard)
interface ReceiptStatement {
  id: number;
  filename: string;
  status: string;
  uploaded_at: string;
  declared_total: string | null;
  suggested_parent_ids: number[];
}

export default function ReceiptsPage() {
  const { data: receipts = [], isLoading, refetch } = useQuery({
    queryKey: ['receipts'],
    queryFn: () => api.get<ReceiptStatement[]>('/receipts'),
  });

  if (isLoading) return <div className="text-center py-12 text-gray-400">Loading…</div>;

  return (
    <div className="space-y-4 max-w-xl mx-auto">
      <h1 className="text-2xl font-bold">Receipts</h1>
      {receipts.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <p>No receipts yet.</p>
          <p className="text-sm mt-1">Upload a receipt from the Upload page.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {receipts.map((r) => (
            <ReceiptCard
              key={r.id}
              receipt={r}
              onLinked={() => refetch()}
              onUnlinked={() => refetch()}
            />
          ))}
        </div>
      )}
    </div>
  );
}
