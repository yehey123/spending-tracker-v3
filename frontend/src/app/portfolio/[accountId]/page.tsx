'use client';

import { useState } from 'react';
import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { PortfolioResponse } from '@/lib/types';

async function fetchPortfolio(accountId: string, includeClosed: boolean): Promise<PortfolioResponse> {
  const url = `/api/accounts/${accountId}/portfolio${includeClosed ? '?include_closed=true' : ''}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch portfolio');
  return res.json();
}

export default function PortfolioPage() {
  const params = useParams();
  const accountId = params.accountId as string;
  const [includeClosed, setIncludeClosed] = useState(false);

  const { data, isLoading, error } = useQuery<PortfolioResponse>({
    queryKey: ['portfolio', accountId, includeClosed],
    queryFn: () => fetchPortfolio(accountId, includeClosed),
  });

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      <div className="bg-white px-4 pt-12 pb-4 shadow-sm">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">Portfolio</h1>
          <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
            <input
              type="checkbox"
              checked={includeClosed}
              onChange={e => setIncludeClosed(e.target.checked)}
              className="rounded"
            />
            Show closed
          </label>
        </div>
      </div>

      <div className="px-4 pt-4">
        {isLoading && <p className="text-center text-gray-400 py-8">Loading…</p>}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-700 text-sm">
            {(error as Error).message}
          </div>
        )}

        {data && data.holdings.length === 0 && (
          <div className="text-center py-12 text-gray-400">
            <p className="text-lg">No holdings recorded</p>
            <p className="text-sm mt-1">Upload a broker statement to get started</p>
          </div>
        )}

        {data && data.holdings.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm bg-white rounded-xl shadow-sm overflow-hidden">
              <thead className="bg-gray-50 text-gray-600 text-xs uppercase">
                <tr>
                  <th className="px-4 py-3 text-left">Symbol</th>
                  <th className="px-4 py-3 text-right">Shares</th>
                  <th className="px-4 py-3 text-right">Avg Cost</th>
                  <th className="px-4 py-3 text-right">Cost Basis</th>
                  <th className="px-4 py-3 text-right">Last Price</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {data.holdings.map(h => (
                  <tr key={h.symbol} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-semibold text-gray-900">{h.symbol}</td>
                    <td className="px-4 py-3 text-right text-gray-700">
                      {parseFloat(h.shares_held).toFixed(4)}
                    </td>
                    <td className="px-4 py-3 text-right text-gray-700">
                      {h.currency} {parseFloat(h.avg_cost_per_share).toFixed(2)}
                    </td>
                    <td className="px-4 py-3 text-right text-gray-700">
                      {h.currency} {parseFloat(h.total_cost_basis).toFixed(2)}
                    </td>
                    <td className="px-4 py-3 text-right text-gray-400">—</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-xs text-gray-400 mt-2 text-center">{data.last_price_note}</p>
          </div>
        )}
      </div>
    </div>
  );
}
