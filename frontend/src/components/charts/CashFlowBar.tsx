'use client';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import type { MonthCashFlow } from '@/lib/types';

interface Props {
  months: MonthCashFlow[];
  displayCurrency?: string | null;
  unconvertedCount?: number;
}

export default function CashFlowBar({ months, displayCurrency, unconvertedCount }: Props) {
  if (months.length === 0) {
    return <div data-testid="cashflow-bar" className="text-center text-gray-400 py-12">No cash flow data</div>;
  }
  const data = months.map((m) => ({
    month: m.month,
    Credit: Number(m.total_credit),
    Debit: Number(m.total_debit),
    Net: Number(m.net),
  }));
  return (
    <div data-testid="cashflow-bar">
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="month" />
        <YAxis tickFormatter={(v) => `${displayCurrency ?? '$'}${v}`} />
        <Tooltip formatter={(v: number) => `${displayCurrency ?? '$'}${v.toFixed(2)}`} />
        <Legend />
        <Bar dataKey="Credit" fill="#22c55e" />
        <Bar dataKey="Debit" fill="#ef4444" />
      </BarChart>
    </ResponsiveContainer>
    </div>
  );
}
