import React from 'react';

/**
 * Common Spinner Component
 */
export default function Spinner({
  size = 'md',
  className = '',
  label = 'Loading...',
}) {
  const sizeClasses = {
    xs: 'w-3.5 h-3.5 border-2',
    sm: 'w-4 h-4 border-2',
    md: 'w-6 h-6 border-[2.5px]',
    lg: 'w-8 h-8 border-3',
    xl: 'w-12 h-12 border-4',
  };

  return (
    <div
      role="status"
      aria-label={label}
      className={`inline-flex items-center justify-center ${className}`}
    >
      <div
        className={`${sizeClasses[size] || sizeClasses.md} rounded-full border-t-cyan-400 border-r-indigo-500 border-b-transparent border-l-transparent animate-spin`}
      />
      <span className="sr-only">{label}</span>
    </div>
  );
}
