'use client';
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import type { CategoryBreakdown } from '@/lib/types';

interface Props {
  breakdown: CategoryBreakdown[];
  displayCurrency?: string | null;
  unconvertedCount?: number;
  totalsAvailable?: boolean;
}

export default function SpendingDonut({ breakdown, displayCurrency, unconvertedCount }: Props) {
  if (breakdown.length === 0) {
    return <div data-testid="spending-donut" className="text-center text-gray-400 py-12">No spending data</div>;
  }
  // Recharts Pie requires numeric dataKey values; API returns Decimal as strings.
  // Strip `percent` so Recharts computes its own 0-1 fraction (avoids 100x collision).
  const data = breakdown.map(({ percent: _p, ...b }) => ({ ...b, amount: Number(b.amount) }));
  const cur = displayCurrency ?? '$';
  return (
    <div data-testid="spending-donut">
      <ResponsiveContainer width="100%" height={320}>
        <PieChart>
          <Pie
            data={data}
            dataKey="amount"
            nameKey="category_name"
            innerRadius={70}
            outerRadius={120}
            paddingAngle={2}
          >
            {data.map((entry, i) => (
              <Cell key={i} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip
            formatter={(value: number) => [`${cur}${value.toFixed(2)}`, '']}
          />
          <Legend
            formatter={(_value, entry: any) => {
              const p = entry.payload ?? {};
              const name = p.category_name ?? _value ?? 'Unknown';
              const amt = Number(p.amount ?? 0).toFixed(2);
              // Recharts sets percent as 0–1 fraction on the payload
              const pct = ((p.percent ?? 0) * 100).toFixed(1);
              return `${name}: ${cur}${amt} (${pct}%)`;
            }}
          />
        </PieChart>
      </ResponsiveContainer>
      {(unconvertedCount ?? 0) > 0 && (
        <p className="text-xs text-amber-600 text-center mt-2">
          ⚠ {unconvertedCount} amount{unconvertedCount !== 1 ? 's' : ''} not converted
        </p>
      )}
    </div>
  );
}
