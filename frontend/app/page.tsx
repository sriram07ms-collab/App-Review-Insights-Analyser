'use client';

import { useEffect, useState } from 'react';
import OverviewCards from '@/components/OverviewCards';
import ThemeTrendChart from '@/components/ThemeTrendChart';
import SentimentTrendChart from '@/components/SentimentTrendChart';
import { THEME_COLORS } from '@/lib/types';
import { fetchThemeAggregation, fetchThemeReviewDetails } from '@/lib/data-loader';
import type { ThemeAggregation, ThemeReviewDetail } from '@/lib/types';

export default function Dashboard() {
  const [aggregation, setAggregation] = useState<ThemeAggregation | null>(null);
  const [reviewDetails, setReviewDetails] = useState<ThemeReviewDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        console.log('Loading dashboard data...');
        const [aggregationData, reviewData] = await Promise.all([
          fetchThemeAggregation(),
          fetchThemeReviewDetails(),
        ]);
        console.log('Loaded aggregation:', aggregationData ? 'yes' : 'no');
        console.log('Loaded review details:', reviewData.length);
        setAggregation(aggregationData);
        setReviewDetails(reviewData);
        if (!aggregationData && reviewData.length === 0) {
          setError('No data available. Please run the pipeline to generate data.');
        }
      } catch (error) {
        console.error('Error loading data:', error);
        setError('Failed to load data. Please check the browser console for details.');
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-500 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-8">
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-yellow-800 mb-2">Data Loading Issue</h2>
          <p className="text-yellow-700">{error}</p>
          <p className="text-sm text-yellow-600 mt-2">
            Check browser console (F12) for detailed error messages.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-600 mt-1">Overview of app review insights and trends</p>
      </div>
      
      {/* Overview Cards */}
      <OverviewCards aggregation={aggregation} latestPulse={null} />

      {/* Charts Section */}
      <div className="space-y-6">
        {/* Theme Trends Chart */}
        {aggregation && aggregation.weekly_counts.length > 0 && (
          <ThemeTrendChart data={aggregation.weekly_counts} />
        )}

        {/* Sentiment Trends Chart */}
        {reviewDetails.length > 0 && (
          <SentimentTrendChart data={reviewDetails} />
        )}
      </div>

      {/* Top Themes */}
      {aggregation && aggregation.top_themes.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="mb-6">
            <h2 className="text-xl font-bold text-gray-900">Top Themes</h2>
            <p className="text-sm text-gray-500 mt-1">By review count</p>
          </div>
          <div className="space-y-4">
            {aggregation.top_themes.slice(0, 5).map((theme, index) => (
              <div key={theme.theme_id} className="flex items-center justify-between py-2">
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <span className="text-gray-500 font-medium w-6">{index + 1}.</span>
                  <div 
                    className="w-3 h-3 rounded-full flex-shrink-0"
                    style={{ backgroundColor: THEME_COLORS[theme.theme_id] || '#6b7280' }}
                  />
                  <span className="font-medium text-gray-900 flex-1 truncate">
                    {theme.theme_id.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                  </span>
                </div>
                <span className="text-gray-900 font-bold text-lg ml-4">{theme.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
