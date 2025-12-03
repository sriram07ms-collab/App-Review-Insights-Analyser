'use client';

import { useEffect, useState } from 'react';
import WeeklyPulseCard from '@/components/WeeklyPulseCard';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import { fetchPulse } from '@/lib/data-loader';
import type { WeeklyPulseNote } from '@/lib/types';

export default function PulseDetailClient({ week }: { week: string }) {
  const [pulse, setPulse] = useState<WeeklyPulseNote | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadPulse() {
      if (!week) {
        console.error('No week parameter provided');
        setError('No week parameter provided');
        setLoading(false);
        return;
      }
      
      console.log('Loading pulse for week:', week);
      try {
        const data = await fetchPulse(week);
        console.log('Pulse loaded:', data ? 'yes' : 'no');
        if (data) {
          setPulse(data);
        } else {
          setError(`Pulse for week ${week} not found`);
        }
      } catch (error) {
        console.error('Error loading pulse:', error);
        setError(`Failed to load pulse: ${error instanceof Error ? error.message : 'Unknown error'}`);
      } finally {
        setLoading(false);
      }
    }
    loadPulse();
  }, [week]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-500 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading product pulse...</p>
          <p className="text-sm text-gray-400 mt-2">Week: {week || 'unknown'}</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <Link 
          href="/pulses" 
          className="inline-flex items-center gap-2 text-green-500 hover:text-green-600 font-medium transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Product Pulse
        </Link>
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-6">
          <h2 className="text-lg font-semibold text-yellow-800 mb-2">Error Loading Pulse</h2>
          <p className="text-yellow-700">{error}</p>
          <p className="text-sm text-yellow-600 mt-2">
            Check browser console (F12) for more details.
          </p>
        </div>
      </div>
    );
  }

  if (!pulse) {
    return (
      <div className="space-y-6">
        <Link 
          href="/pulses" 
          className="inline-flex items-center gap-2 text-green-500 hover:text-green-600 font-medium transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Product Pulse
        </Link>
        <div className="bg-white p-12 rounded-xl shadow-sm border border-gray-200 text-center">
          <p className="text-gray-500 text-lg">Pulse not found</p>
          <p className="text-sm text-gray-400 mt-2">Week: {week}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Link 
        href="/pulses" 
        className="inline-flex items-center gap-2 text-green-500 hover:text-green-600 font-medium transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to all pulses
      </Link>
      
      <WeeklyPulseCard pulse={pulse} />
    </div>
  );
}
