import React from 'react';
import Card from '../common/Card';
import { ShieldCheck, ShieldAlert, AlertTriangle, Clock, EyeOff, Copy, ClipboardCheck } from 'lucide-react';
import { formatTimestamp } from '../../utils/formatters';

/**
 * Chronological Anti-Cheat Integrity Timeline
 */
export default function IntegrityTimeline({
  events = [],
  className = '',
}) {
  const getEventIcon = (type) => {
    switch (type) {
      case 'visibilitychange':
        return <EyeOff className="w-4 h-4 text-rose-400" />;
      case 'blur':
        return <AlertTriangle className="w-4 h-4 text-amber-400" />;
      case 'paste':
        return <ClipboardCheck className="w-4 h-4 text-purple-400" />;
      case 'copy':
        return <Copy className="w-4 h-4 text-indigo-400" />;
      default:
        return <ShieldCheck className="w-4 h-4 text-emerald-400" />;
    }
  };

  const getSeverityBadge = (severity) => {
    switch (severity) {
      case 'high':
        return 'bg-rose-500/20 text-rose-300 border-rose-500/40';
      case 'medium':
        return 'bg-amber-500/20 text-amber-300 border-amber-500/40';
      default:
        return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40';
    }
  };

  return (
    <Card
      title="Anti-Cheat & Proctoring Timeline"
      subtitle="Chronological feed of background telemetry anomalies"
      icon={<ShieldAlert className="w-5 h-5 text-amber-400" />}
      className={className}
    >
      {events.length === 0 ? (
        <div className="py-8 text-center text-slate-400">
          <ShieldCheck className="w-12 h-12 text-emerald-400 mx-auto mb-2 opacity-80" />
          <p className="font-semibold text-slate-200">Zero Integrity Anomalies Detected</p>
          <p className="text-xs text-slate-400 mt-1">
            Candidate maintained focused window visibility throughout the entire session.
          </p>
        </div>
      ) : (
        <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-3 before:bottom-3 before:w-0.5 before:bg-slate-800">
          {events.map((ev, index) => (
            <div key={index} className="relative group">
              {/* Timeline Node Point */}
              <div className="absolute -left-6 top-1 p-1 rounded-full bg-slate-900 border border-slate-700 group-hover:border-cyan-400 transition-colors">
                {getEventIcon(ev.type)}
              </div>

              {/* Event Content Box */}
              <div className="p-3.5 rounded-xl bg-slate-900/50 border border-slate-800/80 hover:border-slate-700 transition-all">
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className="text-xs font-semibold text-white">
                    {ev.label || ev.type}
                  </span>
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded-full border ${getSeverityBadge(
                        ev.severity || 'medium'
                      )}`}
                    >
                      {ev.severity || 'flag'}
                    </span>
                    <span className="text-[10px] font-mono text-slate-400 flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatTimestamp(ev.timestamp)}
                    </span>
                  </div>
                </div>

                <p className="text-xs text-slate-300">
                  {ev.details || 'Browser interaction anomaly recorded by telemetry engine.'}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
