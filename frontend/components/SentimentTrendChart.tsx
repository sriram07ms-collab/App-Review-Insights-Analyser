'use client';

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { formatDate } from '@/lib/utils';
import { parseISO, subWeeks, isAfter, isEqual } from 'date-fns';
import type { ThemeReviewDetail } from '@/lib/types';

interface SentimentTrendChartProps {
  data: ThemeReviewDetail[];
}

interface WeeklySentimentCounts {
  week_start_date: string;
  positive: number;
  neutral: number;
  negative: number;
}

export default function SentimentTrendChart({ data }: SentimentTrendChartProps) {
  // Calculate the cutoff date (3 weeks ago from today)
  const today = new Date();
  const threeWeeksAgo = subWeeks(today, 3);

  // Group reviews by week and calculate sentiment counts
  const weeklySentimentMap = new Map<string, { positive: number; neutral: number; negative: number }>();

  data.forEach((review) => {
    if (!review.week_start_date) return;

    try {
      const weekDate = parseISO(review.week_start_date);
      if (!isAfter(weekDate, threeWeeksAgo) && !isEqual(weekDate, threeWeeksAgo)) {
        return; // Skip if outside 3-week window
      }
    } catch {
      return;
    }

    const weekKey = review.week_start_date;
    if (!weeklySentimentMap.has(weekKey)) {
      weeklySentimentMap.set(weekKey, { positive: 0, neutral: 0, negative: 0 });
    }

    const counts = weeklySentimentMap.get(weekKey)!;
    const rating = review.rating;

    // Categorize by rating: 4-5 = positive, 3 = neutral, 1-2 = negative
    if (rating >= 4) {
      counts.positive++;
    } else if (rating === 3) {
      counts.neutral++;
    } else if (rating <= 2) {
      counts.negative++;
    }
  });

  // Convert to array and sort by week_start_date
  const chartData: WeeklySentimentCounts[] = Array.from(weeklySentimentMap.entries())
    .map(([week_start_date, counts]) => ({
      week_start_date,
      ...counts,
    }))
    .sort((a, b) => a.week_start_date.localeCompare(b.week_start_date))
    .map((week) => ({
      ...week,
      week: formatDate(week.week_start_date),
    }));

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Review Sentiment Trends</h2>
          <p className="text-sm text-gray-500 mt-1.5">Last 3 weeks sentiment distribution</p>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={450}>
        <LineChart data={chartData} margin={{ top: 10, right: 30, left: 10, bottom: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
          <XAxis
            dataKey="week"
            stroke="#94A3B8"
            style={{ fontSize: '13px', fontWeight: 500 }}
            tick={{ fill: '#64748B' }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            stroke="#94A3B8"
            style={{ fontSize: '13px', fontWeight: 500 }}
            tick={{ fill: '#64748B' }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#fff',
              border: '1px solid #E2E8F0',
              borderRadius: '12px',
              boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
              padding: '12px',
            }}
            labelStyle={{ color: '#0F172A', fontWeight: 600, marginBottom: '8px', fontSize: '13px' }}
            itemStyle={{ padding: '4px 0', fontSize: '13px' }}
          />
          <Legend
            wrapperStyle={{ paddingTop: '24px', fontSize: '13px' }}
            iconType="line"
            iconSize={16}
          />
          <Line
            type="monotone"
            dataKey="positive"
            name="Positive (4-5⭐)"
            stroke="#10b981"
            strokeWidth={2.5}
            dot={{ r: 4, fill: '#10b981', strokeWidth: 2, stroke: '#fff' }}
            activeDot={{ r: 6, strokeWidth: 2, stroke: '#fff' }}
          />
          <Line
            type="monotone"
            dataKey="neutral"
            name="Neutral (3⭐)"
            stroke="#f59e0b"
            strokeWidth={2.5}
            dot={{ r: 4, fill: '#f59e0b', strokeWidth: 2, stroke: '#fff' }}
            activeDot={{ r: 6, strokeWidth: 2, stroke: '#fff' }}
          />
          <Line
            type="monotone"
            dataKey="negative"
            name="Negative (1-2⭐)"
            stroke="#ef4444"
            strokeWidth={2.5}
            dot={{ r: 4, fill: '#ef4444', strokeWidth: 2, stroke: '#fff' }}
            activeDot={{ r: 6, strokeWidth: 2, stroke: '#fff' }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

