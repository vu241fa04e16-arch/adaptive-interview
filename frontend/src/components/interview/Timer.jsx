import React from 'react';
import { Clock, AlertTriangle } from 'lucide-react';
import { formatTime } from '../../utils/formatters';

/**
 * Question Countdown Timer Component
 */
export default function Timer({
  remainingSeconds = 120,
  progressPercent = 100,
  isExpired = false,
  className = '',
}) {
  const isCritical = remainingSeconds <= 20;
  const isWarning = remainingSeconds <= 45 && !isCritical;

  // Determine color accents
  const colorTheme = isCritical
    ? {
        border: 'border-rose-500/50',
        text: 'text-rose-400',
        bg: 'bg-rose-500/10',
        bar: 'bg-gradient-to-r from-red-600 to-rose-500',
        glow: 'shadow-rose-500/30',
      }
    : isWarning
    ? {
        border: 'border-amber-500/50',
        text: 'text-amber-400',
        bg: 'bg-amber-500/10',
        bar: 'bg-gradient-to-r from-yellow-500 to-amber-500',
        glow: 'shadow-amber-500/20',
      }
    : {
        border: 'border-cyan-500/40',
        text: 'text-cyan-400',
        bg: 'bg-cyan-500/10',
        bar: 'bg-gradient-to-r from-cyan-500 to-indigo-500',
        glow: 'shadow-cyan-500/20',
      };

  return (
    <div
      className={`glass-card rounded-2xl p-4 border ${colorTheme.border} ${colorTheme.bg} transition-all duration-300 ${
        isCritical ? 'animate-alert-pulse shadow-lg' : ''
      } ${className}`}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className={`p-2 rounded-xl bg-slate-900/60 border border-slate-700/50 ${colorTheme.text}`}>
            {isCritical ? (
              <AlertTriangle className="w-5 h-5 animate-bounce" />
            ) : (
              <Clock className="w-5 h-5" />
            )}
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-wider text-slate-400 font-mono">
              Time Remaining
            </div>
            <div className={`text-2xl font-bold font-mono tracking-tight ${colorTheme.text}`}>
              {formatTime(remainingSeconds)}
            </div>
          </div>
        </div>

        {/* Circular / Indicator Badge */}
        <div className="text-right">
          <span
            className={`inline-block px-2.5 py-1 rounded-full text-xs font-semibold font-mono border ${
              isCritical
                ? 'bg-rose-500/20 border-rose-500/40 text-rose-300'
                : isWarning
                ? 'bg-amber-500/20 border-amber-500/40 text-amber-300'
                : 'bg-slate-800 border-slate-700 text-slate-300'
            }`}
          >
            {isExpired ? 'EXPIRED' : isCritical ? 'URGENT' : `${progressPercent}%`}
          </span>
          {isCritical && !isExpired && (
            <p className="text-[10px] text-rose-400 mt-1 font-medium">Auto-submits at 00:00</p>
          )}
        </div>
      </div>

      {/* Linear progress bar */}
      <div className="mt-3 w-full bg-slate-900/80 rounded-full h-1.5 overflow-hidden border border-slate-800">
        <div
          className={`h-full transition-all duration-1000 ease-linear rounded-full ${colorTheme.bar}`}
          style={{ width: `${progressPercent}%` }}
        />
      </div>
    </div>
  );
}
