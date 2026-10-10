import React from 'react';

/**
 * Common Card Component
 */
export default function Card({
  children,
  title,
  subtitle,
  icon = null,
  headerRight = null,
  footer = null,
  className = '',
  bodyClassName = '',
  variant = 'glass',
  ...rest
}) {
  const variantClasses = {
    glass: 'glass-card rounded-2xl',
    solid: 'bg-surface border border-slate-800 rounded-2xl shadow-xl',
    glow: 'glass-card rounded-2xl border-cyan-500/20 shadow-lg shadow-cyan-500/5',
    subtle: 'bg-surface-200/50 border border-slate-800/80 rounded-2xl',
  };

  return (
    <div
      className={`${variantClasses[variant] || variantClasses.glass} ${className}`}
      {...rest}
    >
      {(title || subtitle || headerRight || icon) && (
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800/80">
          <div className="flex items-center gap-3">
            {icon && (
              <div className="p-2 rounded-xl bg-slate-800/60 text-cyan-400 border border-slate-700/50">
                {icon}
              </div>
            )}
            <div>
              {title && (
                <h3 className="text-base font-semibold text-white tracking-wide font-display">
                  {title}
                </h3>
              )}
              {subtitle && (
                <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>
              )}
            </div>
          </div>
          {headerRight && <div className="shrink-0">{headerRight}</div>}
        </div>
      )}

      <div className={`p-6 ${bodyClassName}`}>{children}</div>

      {footer && (
        <div className="px-6 py-3.5 bg-slate-900/40 border-t border-slate-800/60 rounded-b-2xl">
          {footer}
        </div>
      )}
    </div>
  );
}
