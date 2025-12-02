'use client';

import { useEffect, useState } from 'react';
import ThemeCard from '@/components/ThemeCard';
import { fetchThemeAggregation, fetchThemeReviewDetails } from '@/lib/data-loader';
import type { ThemeAggregation, ThemeReviewDetail } from '@/lib/types';
import { formatThemeName } from '@/lib/utils';
import { Download } from 'lucide-react';

export default function ThemesPage() {
  const [aggregation, setAggregation] = useState<ThemeAggregation | null>(null);
  const [loading, setLoading] = useState(true);
  const [reviewDetails, setReviewDetails] = useState<ThemeReviewDetail[]>([]);
  const [reviewsLoading, setReviewsLoading] = useState<boolean>(false);

  useEffect(() => {
    async function loadData() {
      try {
        const [agg, reviews] = await Promise.all([
          fetchThemeAggregation(),
          fetchThemeReviewDetails(),
        ]);
        setAggregation(agg);
        setReviewDetails(reviews);
      } catch (error) {
        console.error('Error loading themes:', error);
      } finally {
        setLoading(false);
        setReviewsLoading(false);
      }
    }
    setReviewsLoading(true);
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-500 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading themes...</p>
        </div>
      </div>
    );
  }

  if (!aggregation) {
    return (
      <div className="bg-white p-12 rounded-xl shadow-sm border border-gray-200 text-center">
        <div className="max-w-md mx-auto">
          <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
            </svg>
          </div>
          <p className="text-gray-500 text-lg mb-2">No theme data found</p>
          <p className="text-gray-400 text-sm">Run the pipeline to generate data.</p>
        </div>
      </div>
    );
  }

  // Calculate trends (simplified - compare last 2 weeks)
  const calculateTrend = (themeId: string): number | undefined => {
    if (aggregation.weekly_counts.length < 2) return undefined;
    const last = aggregation.weekly_counts[aggregation.weekly_counts.length - 1];
    const prev = aggregation.weekly_counts[aggregation.weekly_counts.length - 2];
    const lastCount = last.theme_counts[themeId] || 0;
    const prevCount = prev.theme_counts[themeId] || 0;
    if (prevCount === 0) return undefined;
    return ((lastCount - prevCount) / prevCount) * 100;
  };

  const handleExportCsv = () => {
    if (!aggregation) return;

    try {
      const headers = [
        'theme_id',
        'theme_name',
        'overall_count',
        'latest_week_count',
        'previous_week_count',
        'trend_percent',
      ];

      const rows = aggregation.top_themes.map((theme) => {
        const themeId = theme.theme_id;
        const themeName = formatThemeName(themeId);

        const overallCount = aggregation.overall_counts?.[themeId] ?? theme.count ?? 0;

        let latestWeekCount = 0;
        let previousWeekCount = 0;
        let trendPercent: number | '' = '';

        if (aggregation.weekly_counts.length >= 2) {
          const last = aggregation.weekly_counts[aggregation.weekly_counts.length - 1];
          const prev = aggregation.weekly_counts[aggregation.weekly_counts.length - 2];
          latestWeekCount = last.theme_counts[themeId] || 0;
          previousWeekCount = prev.theme_counts[themeId] || 0;

          if (previousWeekCount > 0) {
            trendPercent = Number((((latestWeekCount - previousWeekCount) / previousWeekCount) * 100).toFixed(1));
          }
        }

        const rawValues = [
          themeId,
          themeName,
          overallCount,
          latestWeekCount,
          previousWeekCount,
          trendPercent,
        ];

        const escapedValues = rawValues.map((value) => {
          const str = String(value ?? '');
          if (str.includes(',') || str.includes('"') || str.includes('\n')) {
            return `"${str.replace(/"/g, '""')}"`;
          }
          return str;
        });

        return escapedValues.join(',');
      });

      const csvContent = [headers.join(','), ...rows].join('\n');
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'theme_explorer_export.csv');
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Error exporting theme data to CSV:', error);
    }
  };

  const handleExportReviewsCsv = () => {
    if (!reviewDetails || reviewDetails.length === 0) {
      console.warn('No detailed review data to export');
      return;
    }

    try {
      const headers = [
        'theme_id',
        'theme_name',
        'review_id',
        'rating',
        'date',
        'author',
        'title',
        'week_start_date',
        'week_end_date',
        'review_text',
        'reason',
      ];

      const rows = reviewDetails.map((r) => {
        const rawValues = [
          r.theme_id,
          r.theme_name,
          r.review_id,
          r.rating,
          r.date,
          r.author,
          r.title ?? '',
          r.week_start_date ?? '',
          r.week_end_date ?? '',
          r.text ?? '',
          r.reason ?? '',
        ];

        const escaped = rawValues.map((value) => {
          const str = String(value ?? '');
          if (str.includes(',') || str.includes('"') || str.includes('\n')) {
            return `"${str.replace(/"/g, '""')}"`;
          }
          return str;
        });

        return escaped.join(',');
      });

      const csvContent = [headers.join(','), ...rows].join('\n');
      const blob = new Blob([csvContent], {
        type: 'text/csv;charset=utf-8;',
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'theme_reviews_detailed.csv');
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Error exporting detailed theme reviews to CSV:', error);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Theme Explorer</h1>
          <p className="text-gray-500 mt-1">
            Explore themes with trends and export raw user reviews
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={handleExportCsv}
            className="inline-flex items-center gap-2 rounded-lg bg-green-500 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-green-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-green-500 focus-visible:ring-offset-2"
          >
            <Download className="w-4 h-4" />
            Summary CSV
          </button>
          <button
            type="button"
            onClick={handleExportReviewsCsv}
            disabled={reviewsLoading}
            className="inline-flex items-center gap-2 rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-emerald-600 disabled:opacity-60 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2"
          >
            <Download className="w-4 h-4" />
            {reviewsLoading ? 'Preparing reviews…' : 'Reviews CSV (Excel)'}
          </button>
        </div>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {aggregation.top_themes.map((theme) => {
          const trend = calculateTrend(theme.theme_id);
          return (
            <ThemeCard
              key={theme.theme_id}
              themeId={theme.theme_id}
              count={theme.count}
              trend={trend}
            />
          );
        })}
      </div>
    </div>
  );
}
