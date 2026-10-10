import React from 'react';
import { Cpu, Zap, Layers, HelpCircle, Sparkles } from 'lucide-react';
import { DIFFICULTY_LEVELS } from '../../utils/constants';

/**
 * Adaptive Interview Question Card Component
 */
export default function QuestionCard({
  question,
  questionNumber = 1,
  totalQuestions = 4,
  className = '',
}) {
  if (!question) return null;

  const {
    text = '',
    category = 'General Systems',
    difficulty = DIFFICULTY_LEVELS.MEDIUM,
    adaptiveHint = '',
  } = question;

  // Difficulty pill styling
  const difficultyStyles = {
    [DIFFICULTY_LEVELS.EASY]: {
      border: 'border-emerald-500/40',
      bg: 'bg-emerald-500/10',
      text: 'text-emerald-400',
      badge: 'Easy Tier',
    },
    [DIFFICULTY_LEVELS.MEDIUM]: {
      border: 'border-amber-500/40',
      bg: 'bg-amber-500/10',
      text: 'text-amber-400',
      badge: 'Medium Tier',
    },
    [DIFFICULTY_LEVELS.HARD]: {
      border: 'border-purple-500/40',
      bg: 'bg-purple-500/10',
      text: 'text-purple-400',
      badge: 'Hard / Architect Tier',
    },
  }[difficulty] || {
    border: 'border-indigo-500/40',
    bg: 'bg-indigo-500/10',
    text: 'text-indigo-400',
    badge: difficulty,
  };

  return (
    <div
      className={`glass-card rounded-2xl p-6 sm:p-8 border border-slate-700/60 shadow-xl relative overflow-hidden ${className}`}
    >
      {/* Background cyber accent glow */}
      <div className="absolute top-0 right-0 -mr-16 -mt-16 w-48 h-48 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

      {/* Header Info */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-5 border-b border-slate-800 pb-4">
        <div className="flex items-center gap-2">
          <span className="px-3 py-1 rounded-full text-xs font-mono font-semibold bg-slate-800 text-cyan-400 border border-slate-700">
            Question {questionNumber} of {totalQuestions}
          </span>
          <span className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-slate-800/60 text-slate-300 border border-slate-700/50">
            <Layers className="w-3.5 h-3.5 text-indigo-400" />
            {category}
          </span>
        </div>

        {/* Adaptive Difficulty Badge */}
        <div className="flex items-center gap-2">
          <div
            className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border ${difficultyStyles.border} ${difficultyStyles.bg} ${difficultyStyles.text}`}
          >
            <Zap className="w-3.5 h-3.5" />
            <span>{difficultyStyles.badge}</span>
          </div>

          <div className="hidden md:flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-mono text-cyan-300 bg-cyan-950/40 border border-cyan-800/40">
            <Sparkles className="w-3 h-3 text-cyan-400 animate-spin" />
            <span>Adaptive Engine</span>
          </div>
        </div>
      </div>

      {/* Question Content */}
      <div className="mb-6">
        <h2 className="text-lg sm:text-xl md:text-2xl font-semibold text-white leading-relaxed font-display">
          {text}
        </h2>
      </div>

      {/* Adaptive Hint or Guidance */}
      {adaptiveHint && (
        <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 flex items-start gap-3 text-xs text-slate-300">
          <HelpCircle className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold text-slate-200">Evaluation Scope: </span>
            <span className="text-slate-400">{adaptiveHint}</span>
          </div>
        </div>
      )}
    </div>
  );
}
