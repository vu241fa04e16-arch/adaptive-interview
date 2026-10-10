import React, { useRef, useEffect } from 'react';
import { Send, CornerDownLeft, Sparkles, AlertCircle } from 'lucide-react';
import Button from '../common/Button';

/**
 * Interview Answer Response Box Component
 * Supports real-time text input, speech-to-text transcript updates,
 * keyboard submit shortcuts, and mutex lock disabling.
 */
export default function ResponseBox({
  value = '',
  onChange,
  onSubmit,
  isSubmitting = false,
  disabled = false,
  interimTranscript = '',
  placeholder = 'Type your technical solution here, or use the microphone above to speak your answer...',
  className = '',
}) {
  const textareaRef = useRef(null);

  // Auto-resize textarea to fit content
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.max(160, textareaRef.current.scrollHeight)}px`;
    }
  }, [value, interimTranscript]);

  // Handle Ctrl+Enter / Cmd+Enter for quick submit
  const handleKeyDown = (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      if (!isSubmitting && !disabled && value.trim()) {
        onSubmit();
      }
    }
  };

  const wordCount = value.trim() ? value.trim().split(/\s+/).length : 0;
  const charCount = value.length;
  const isInputLocked = disabled || isSubmitting;

  return (
    <div className={`glass-card rounded-2xl p-4 sm:p-6 border border-slate-700/60 shadow-xl ${className}`}>
      <div className="flex items-center justify-between mb-3">
        <label
          htmlFor="response-input"
          className="text-xs font-semibold uppercase tracking-wider text-slate-300 font-mono flex items-center gap-1.5"
        >
          <span>Candidate Response</span>
          {isSubmitting && (
            <span className="text-[11px] text-amber-400 font-normal normal-case flex items-center gap-1">
              <AlertCircle className="w-3 h-3" />
              Locked for AI Evaluation
            </span>
          )}
        </label>

        <div className="flex items-center gap-3 text-xs text-slate-400 font-mono">
          <span>{wordCount} words</span>
          <span className="text-slate-600">|</span>
          <span>{charCount} chars</span>
        </div>
      </div>

      {/* Main Text Input Area */}
      <div className="relative">
        <textarea
          id="response-input"
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isInputLocked}
          placeholder={placeholder}
          rows={6}
          className={`w-full bg-slate-900/80 border rounded-xl p-4 text-slate-100 placeholder-slate-500 text-sm sm:text-base leading-relaxed font-sans transition-all focus:outline-none focus:ring-2 focus:ring-cyan-500/50 ${
            isInputLocked
              ? 'opacity-60 cursor-not-allowed border-slate-800 bg-slate-950/60'
              : 'border-slate-700/80 hover:border-slate-600 focus:border-cyan-500'
          }`}
        />

        {/* Interim Speech Transcript overlay if active */}
        {interimTranscript && (
          <div className="mt-2 p-2.5 rounded-lg bg-cyan-950/30 border border-cyan-800/40 text-cyan-300 text-xs italic flex items-center gap-2 animate-pulse">
            <Sparkles className="w-3.5 h-3.5 shrink-0" />
            <span>Listening: "{interimTranscript}"</span>
          </div>
        )}
      </div>

      {/* Bottom Actions Bar */}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-800/80">
        <div className="hidden sm:flex items-center gap-1 text-xs text-slate-500 font-mono">
          <CornerDownLeft className="w-3 h-3" />
          <span>Press</span>
          <kbd className="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300 text-[10px]">
            Ctrl + Enter
          </kbd>
          <span>to submit</span>
        </div>

        <div className="flex items-center gap-2 ml-auto">
          {value && !isInputLocked && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onChange('')}
              disabled={isInputLocked}
            >
              Clear
            </Button>
          )}

          <Button
            variant="cyber"
            size="md"
            onClick={onSubmit}
            isLoading={isSubmitting}
            disabled={isInputLocked || !value.trim()}
            rightIcon={<Send className="w-4 h-4" />}
          >
            Submit Answer
          </Button>
        </div>
      </div>
    </div>
  );
}
