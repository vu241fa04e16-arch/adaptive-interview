import React from 'react';

/**
 * Common ProgressBar Component
 */
export default function ProgressBar({
  value = 0,
  max = 100,
  label = '',
  showLabel = false,
  showPercentage = false,
  variant = 'cyan',
  size = 'md',
  className = '',
}) {
  const percentage = Math.min(100, Math.max(0, Math.round((value / max) * 100)));

  const sizeClasses = {
    xs: 'h-1.5',
    sm: 'h-2',
    md: 'h-3',
    lg: 'h-4',
  };

  const variantGradients = {
    cyan: 'bg-gradient-to-r from-cyan-500 to-blue-500',
    indigo: 'bg-gradient-to-r from-blue-600 to-indigo-500',
    cyber: 'bg-gradient-to-r from-cyan-400 via-indigo-500 to-purple-500',
    emerald: 'bg-gradient-to-r from-emerald-500 to-teal-400',
    amber: 'bg-gradient-to-r from-amber-500 to-yellow-400',
    rose: 'bg-gradient-to-r from-red-500 to-rose-500',
  };

  return (
    <div className={`w-full ${className}`}>
      {(showLabel || showPercentage) && (
        <div className="flex justify-between items-center mb-1.5 text-xs text-slate-300 font-medium">
          {showLabel && <span>{label}</span>}
          {showPercentage && <span className="font-mono text-cyan-400">{percentage}%</span>}
        </div>
      )}
      <div
        role="progressbar"
        aria-valuenow={percentage}
        aria-valuemin={0}
        aria-valuemax={100}
        className={`w-full bg-slate-800/80 rounded-full overflow-hidden border border-slate-700/50 p-0.5 ${sizeClasses[size] || sizeClasses.md}`}
      >
        <div
          className={`h-full rounded-full transition-all duration-500 ease-out shadow-sm ${variantGradients[variant] || variantGradients.cyan}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
