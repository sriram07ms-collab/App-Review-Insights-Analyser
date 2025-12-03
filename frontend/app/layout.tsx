import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import Link from 'next/link';
import { BarChart3, Calendar, Tag, CheckSquare } from 'lucide-react';

const inter = Inter({ 
  subsets: ['latin'],
  weight: ['300', '400', '500', '600', '700', '800'],
  variable: '--font-inter',
});

export const metadata: Metadata = {
  title: 'App Review Insights Dashboard | Groww',
  description: 'Weekly pulse notes and theme analysis from app reviews',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="antialiased">
        <div className="min-h-screen bg-gray-50">
          {/* Header */}
          <header className="bg-white border-b border-gray-200 shadow-sm sticky top-0 z-50">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
              <div className="flex items-center justify-between h-16">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-gradient-to-br from-green-400 to-green-600 rounded-lg flex items-center justify-center">
                    <BarChart3 className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <h1 className="text-xl font-bold text-gray-900">App Review Insights</h1>
                    <p className="text-xs text-gray-500">Groww Analytics Dashboard</p>
                  </div>
                </div>
                <nav className="flex items-center gap-1">
                  <Link 
                    href="/" 
                    className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-100 hover:text-green-500 transition-colors"
                  >
                    <BarChart3 className="w-4 h-4" />
                    Dashboard
                  </Link>
                  <Link 
                    href="/pulses" 
                    className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-100 hover:text-green-500 transition-colors"
                  >
                    <Calendar className="w-4 h-4" />
                    Product Pulse
                  </Link>
                  <Link 
                    href="/themes" 
                    className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-100 hover:text-green-500 transition-colors"
                  >
                    <Tag className="w-4 h-4" />
                    Themes
                  </Link>
                  <Link 
                    href="/actions" 
                    className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-100 hover:text-green-500 transition-colors"
                  >
                    <CheckSquare className="w-4 h-4" />
                    Actions
                  </Link>
                </nav>
              </div>
            </div>
          </header>

          {/* Main Content */}
          <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
