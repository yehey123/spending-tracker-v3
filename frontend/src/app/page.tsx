'use client';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { ByCategoryResponse, CashFlowResponse, Transaction } from '@/lib/types';
import SpendingDonut from '@/components/charts/SpendingDonut';
import CashFlowBar from '@/components/charts/CashFlowBar';

export default function DashboardPage() {
  const [month, setMonth] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  });
  const [catBreakdown, setCatBreakdown] = useState<'parent' | 'subcategory'>('parent');

  const { data: byCategory } = useQuery({
    queryKey: ['analytics', 'by-category', month, catBreakdown],
    queryFn: () => api.get<ByCategoryResponse>(`/analytics/by-category?month=${month}&breakdown=${catBreakdown}`),
  });

  const { data: cashFlow } = useQuery({
    queryKey: ['analytics', 'cash-flow'],
    queryFn: () => api.get<CashFlowResponse>('/analytics/cash-flow?months=6'),
  });

  const { data: recentTx } = useQuery({
    queryKey: ['transactions', 'recent'],
    queryFn: () => api.get<Transaction[]>(`/transactions?limit=5&month=${month}`),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <input
          type="month"
          value={month}
          onChange={(e) => setMonth(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm"
        />
      </div>

      {/* Cash flow summary */}
      {byCategory && (
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-white rounded-xl p-4 shadow-sm">
            <div className="text-xs text-gray-500 uppercase tracking-wide">Total Spent</div>
            <div className="text-2xl font-bold text-red-600">
              {byCategory.display_currency ?? ''} {Number(byCategory.total_debit).toFixed(2)}
            </div>
          </div>
          <div className="bg-white rounded-xl p-4 shadow-sm">
            <div className="text-xs text-gray-500 uppercase tracking-wide">Categories</div>
            <div className="text-2xl font-bold">{byCategory.breakdown.length}</div>
          </div>
        </div>
      )}

      {/* Spending donut */}
      <div className="bg-white rounded-xl p-4 shadow-sm">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-base font-semibold">Spending by Category</h2>
          <div className="flex text-xs overflow-hidden rounded-lg border border-gray-200">
            <button
              onClick={() => setCatBreakdown('parent')}
              className={`px-3 py-1 ${catBreakdown === 'parent' ? 'bg-indigo-600 text-white' : 'text-gray-600 hover:bg-gray-50'}`}
            >
              Top-level
            </button>
            <button
              onClick={() => setCatBreakdown('subcategory')}
              className={`px-3 py-1 ${catBreakdown === 'subcategory' ? 'bg-indigo-600 text-white' : 'text-gray-600 hover:bg-gray-50'}`}
            >
              Detail
            </button>
          </div>
        </div>
        <SpendingDonut
          breakdown={byCategory?.breakdown ?? []}
          displayCurrency={byCategory?.display_currency}
          unconvertedCount={byCategory?.unconverted_count}
          totalsAvailable={byCategory?.totals_available}
        />
      </div>

      {/* Cash flow bar */}
      <div className="bg-white rounded-xl p-4 shadow-sm">
        <h2 className="text-base font-semibold mb-2">Cash Flow (6 months)</h2>
        <CashFlowBar
          months={cashFlow?.months ?? []}
          displayCurrency={cashFlow?.display_currency}
          unconvertedCount={cashFlow?.unconverted_count}
        />
      </div>

      {/* Recent transactions */}
      <div className="bg-white rounded-xl p-4 shadow-sm">
        <h2 className="text-base font-semibold mb-3">Recent Transactions</h2>
        {(!recentTx || recentTx.length === 0) ? (
          <p className="text-gray-400 text-sm text-center py-4">No transactions this month</p>
        ) : (
          <ul className="divide-y divide-gray-100">
            {recentTx.map((tx) => (
              <li key={tx.id} className="py-2 flex items-center justify-between text-sm">
                <div>
                  <div className="font-medium">{tx.description}</div>
                  <div className="text-gray-400 text-xs">{tx.date.slice(0, 10)} · {tx.category?.name ?? 'Uncategorized'}</div>
                </div>
                <div className={tx.direction === 'debit' ? 'text-red-600 font-semibold' : 'text-green-600 font-semibold'}>
                  {tx.direction === 'debit' ? '-' : '+'}{tx.currency ?? byCategory?.display_currency ?? ''} {Number(tx.amount).toFixed(2)}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
