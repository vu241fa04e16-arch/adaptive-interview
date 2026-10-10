import React from 'react';
import { BrowserRouter } from 'react-router-dom';
import Navbar from './components/common/Navbar';
import AppRoutes from './routes';
import { BrainCircuit, ShieldCheck, Heart } from 'lucide-react';

/**
 * Main Application Component
 */
export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-background flex flex-col selection:bg-cyan-500/30 selection:text-cyan-200">
        {/* Navigation Bar */}
        <Navbar />

        {/* Dynamic Route Content */}
        <main className="flex-1 pb-16">
          <AppRoutes />
        </main>

        {/* Global Footer */}
        <footer className="border-t border-slate-800/80 bg-surface-300/80 backdrop-blur-md py-8">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-500">
            <div className="flex items-center gap-2">
              <BrainCircuit className="w-4 h-4 text-cyan-400" />
              <span className="font-display font-semibold text-slate-300">
                ADAPTIVE<span className="text-cyan-400">AI</span>
              </span>
              <span>• Intelligent Technical Screening Platform</span>
            </div>

            <div className="flex items-center gap-4 font-mono">
              <span className="flex items-center gap-1 text-emerald-400/80">
                <ShieldCheck className="w-3.5 h-3.5" /> Anti-Cheat Telemetry
              </span>
              <span>•</span>
              <span className="text-slate-400">Speech & Adaptive Rigor Engine</span>
            </div>
          </div>
        </footer>
      </div>
    </BrowserRouter>
  );
}
