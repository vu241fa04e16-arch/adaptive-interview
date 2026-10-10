import React, { useState } from 'react';
import { ShieldCheck, ShieldAlert, ShieldX, Info, ChevronDown } from 'lucide-react';
import { formatScore } from '../../utils/formatters';

/**
 * Integrity & Anti-Cheat Trust Badge
 */
export default function IntegrityBadge({
  integrityScore = 100,
  violationsCount = 0,
  events = [],
  status = 'secure',
  className = '',
}) {
  const [showDetails, setShowDetails] = useState(false);

  const statusConfig = {
    secure: {
      border: 'border-emerald-500/40',
      bg: 'bg-emerald-500/10',
      text: 'text-emerald-400',
      label: 'Verified Secure',
      icon: <ShieldCheck className="w-4 h-4 text-emerald-400" />,
    },
    warning: {
      border: 'border-amber-500/40',
      bg: 'bg-amber-500/10',
      text: 'text-amber-400',
      label: 'Flagged Activity',
      icon: <ShieldAlert className="w-4 h-4 text-amber-400" />,
    },
    alert: {
      border: 'border-rose-500/40',
      bg: 'bg-rose-500/10',
      text: 'text-rose-400',
      label: 'Integrity Alert',
      icon: <ShieldX className="w-4 h-4 text-rose-400" />,
    },
  }[status] || {
    border: 'border-slate-700',
    bg: 'bg-slate-800',
    text: 'text-slate-300',
    label: 'Monitoring',
    icon: <ShieldCheck className="w-4 h-4" />,
  };

  return (
    <div className={`relative ${className}`}>
      {/* Badge Button */}
      <button
        type="button"
        onClick={() => setShowDetails(!showDetails)}
        className={`flex items-center gap-2.5 px-3 py-1.5 rounded-xl border ${statusConfig.border} ${statusConfig.bg} transition-all hover:bg-slate-800/80 focus:outline-none`}
        aria-label="Toggle anti-cheat telemetry log"
      >
        {statusConfig.icon}

        <div className="flex items-center gap-1.5 text-xs font-mono">
          <span className="text-slate-300 hidden sm:inline">Trust:</span>
          <span className={`font-bold ${statusConfig.text}`}>
            {formatScore(integrityScore)}
          </span>
        </div>

        {violationsCount > 0 && (
          <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40">
            {violationsCount} {violationsCount === 1 ? 'flag' : 'flags'}
          </span>
        )}

        <ChevronDown
          className={`w-3.5 h-3.5 text-slate-400 transition-transform ${
            showDetails ? 'rotate-180' : ''
          }`}
        />
      </button>

      {/* Dropdown Details Telemetry Flyout */}
      {showDetails && (
        <div className="absolute right-0 mt-2 w-80 max-w-[90vw] p-4 glass-panel rounded-2xl border border-slate-700 shadow-2xl z-50 animate-in fade-in zoom-in-95 duration-150">
          <div className="flex items-center justify-between pb-2 border-b border-slate-800">
            <span className="text-xs font-semibold text-white uppercase font-mono">
              Anti-Cheat Telemetry
            </span>
            <span
              className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusConfig.bg} ${statusConfig.text}`}
            >
              {statusConfig.label}
            </span>
          </div>

          <p className="text-[11px] text-slate-400 mt-2 mb-3">
            Real-time heuristic tracking detects focus loss, tab switching, and clipboard anomalies.
          </p>

          <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
            {events.length === 0 ? (
              <div className="text-center py-4 text-xs text-slate-500">
                No security flags detected. Clean session.
              </div>
            ) : (
              events.slice(0, 6).map((ev, index) => (
                <div
                  key={index}
                  className="p-2 rounded-lg bg-slate-900/60 border border-slate-800 text-[11px] flex items-start justify-between gap-2"
                >
                  <div>
                    <span className="font-semibold text-slate-200 block">
                      {ev.label || ev.type}
                    </span>
                    <span className="text-slate-400 text-[10px]">
                      {ev.details || 'System flag'}
                    </span>
                  </div>
                  <span className="text-[10px] font-mono text-slate-500 shrink-0">
                    {new Date(ev.timestamp).toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit',
                      second: '2-digit',
                    })}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
