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
    return <div className="text-center text-gray-400 py-12">No spending data</div>;
  }
  return (
    <div>
      <ResponsiveContainer width="100%" height={320}>
        <PieChart>
          <Pie
            data={breakdown}
            dataKey="amount"
            nameKey="category_name"
            innerRadius={70}
            outerRadius={120}
            paddingAngle={2}
          >
            {breakdown.map((entry, i) => (
              <Cell key={i} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip
            formatter={(value: string) => [`${displayCurrency ?? '$'}${Number(value).toFixed(2)}`, '']}
          />
          <Legend
            formatter={(value, entry: any) =>
              `${value}: ${displayCurrency ?? '$'}${Number(entry.payload.amount).toFixed(2)} (${entry.payload.percent.toFixed(1)}%)`
            }
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
