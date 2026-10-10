import React, { useEffect } from 'react';
import { X } from 'lucide-react';

/**
 * Common Accessible Modal Component
 */
export default function Modal({
  isOpen,
  onClose,
  title,
  description,
  children,
  footer = null,
  size = 'md',
  closeOnBackdrop = true,
}) {
  // Handle ESC key to dismiss
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen && onClose) {
        onClose();
      }
    };
    if (isOpen) {
      document.body.style.overflow = 'hidden';
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      document.body.style.overflow = 'unset';
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const sizeClasses = {
    sm: 'max-w-md',
    md: 'max-w-lg',
    lg: 'max-w-2xl',
    xl: 'max-w-4xl',
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={title ? 'modal-title' : undefined}
      aria-describedby={description ? 'modal-description' : undefined}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6"
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/75 backdrop-blur-md transition-opacity duration-300"
        onClick={closeOnBackdrop ? onClose : undefined}
      />

      {/* Dialog Window */}
      <div
        className={`relative w-full ${sizeClasses[size] || sizeClasses.md} bg-surface-100 border border-slate-700/80 rounded-2xl shadow-2xl shadow-black/80 overflow-hidden transform transition-all duration-300 z-10`}
      >
        {/* Header */}
        {(title || onClose) && (
          <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800">
            <div>
              {title && (
                <h3 id="modal-title" className="text-lg font-semibold text-white font-display">
                  {title}
                </h3>
              )}
              {description && (
                <p id="modal-description" className="text-xs text-slate-400 mt-0.5">
                  {description}
                </p>
              )}
            </div>
            {onClose && (
              <button
                type="button"
                onClick={onClose}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/80 transition-colors"
                aria-label="Close dialog"
              >
                <X className="w-5 h-5" />
              </button>
            )}
          </div>
        )}

        {/* Content Body */}
        <div className="p-6 text-slate-200">{children}</div>

        {/* Optional Footer */}
        {footer && (
          <div className="flex items-center justify-end gap-3 px-6 py-4 bg-slate-900/60 border-t border-slate-800">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}
