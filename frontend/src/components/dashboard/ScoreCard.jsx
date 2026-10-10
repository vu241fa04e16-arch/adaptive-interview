import React from 'react';
import { Award, ShieldCheck, Cpu, MessageSquare, TrendingUp } from 'lucide-react';
import { formatScore } from '../../utils/formatters';

/**
 * ScoreCard Component for Recruiter Dashboard
 */
export default function ScoreCard({
  overallScore = 88,
  integrityScore = 95,
  recommendation = 'Strong Hire',
  candidateName = 'Alex Chen',
  targetRole = 'Senior Full-Stack Engineer',
  className = '',
}) {
  const getBadgeStyle = (rec) => {
    if (rec === 'Strong Hire') {
      return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40';
    }
    if (rec === 'Hire') {
      return 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40';
    }
    return 'bg-amber-500/20 text-amber-300 border-amber-500/40';
  };

  return (
    <div
      className={`glass-panel rounded-3xl p-6 sm:p-8 border border-slate-700/60 shadow-2xl relative overflow-hidden ${className}`}
    >
      {/* Background cyber accent glow */}
      <div className="absolute top-0 right-0 -mr-20 -mt-20 w-64 h-64 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-0 left-0 -ml-20 -mb-20 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />

      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 relative z-10">
        {/* Candidate Profile Info */}
        <div>
          <div className="flex items-center gap-3 mb-2">
            <span
              className={`px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider border font-mono ${getBadgeStyle(
                recommendation
              )}`}
            >
              {recommendation}
            </span>
            <span className="text-xs font-mono text-slate-400">AI Verified Screening</span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-bold text-white font-display">
            {candidateName}
          </h1>
          <p className="text-sm text-cyan-400 font-medium mt-1">{targetRole}</p>
        </div>

        {/* Hero Score Display */}
        <div className="flex flex-wrap items-center gap-4 sm:gap-6">
          {/* Overall Composite Score */}
          <div className="flex items-center gap-4 px-6 py-4 rounded-2xl bg-slate-900/80 border border-slate-700 shadow-inner">
            <div className="relative flex items-center justify-center">
              <Award className="w-10 h-10 text-cyan-400" />
            </div>
            <div>
              <div className="text-xs uppercase tracking-wider text-slate-400 font-mono">
                Composite Score
              </div>
              <div className="text-3xl sm:text-4xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-indigo-400 font-mono">
                {formatScore(overallScore)}
              </div>
            </div>
          </div>

          {/* Integrity Trust Score */}
          <div className="flex items-center gap-4 px-6 py-4 rounded-2xl bg-slate-900/80 border border-slate-700 shadow-inner">
            <ShieldCheck
              className={`w-10 h-10 ${
                integrityScore >= 80 ? 'text-emerald-400' : 'text-amber-400'
              }`}
            />
            <div>
              <div className="text-xs uppercase tracking-wider text-slate-400 font-mono">
                Integrity Score
              </div>
              <div
                className={`text-3xl sm:text-4xl font-extrabold font-mono ${
                  integrityScore >= 80 ? 'text-emerald-400' : 'text-amber-400'
                }`}
              >
                {formatScore(integrityScore)}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Sub-Metric Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-8 pt-6 border-t border-slate-800">
        <div className="p-3.5 rounded-xl bg-slate-900/40 border border-slate-800">
          <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
            <Cpu className="w-4 h-4 text-cyan-400" />
            <span>Technical Depth</span>
          </div>
          <div className="text-xl font-bold font-mono text-white">88%</div>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-900/40 border border-slate-800">
          <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
            <TrendingUp className="w-4 h-4 text-indigo-400" />
            <span>Adaptive Rigor</span>
          </div>
          <div className="text-xl font-bold font-mono text-white">Level 4 (Hard)</div>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-900/40 border border-slate-800">
          <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
            <MessageSquare className="w-4 h-4 text-purple-400" />
            <span>Communication</span>
          </div>
          <div className="text-xl font-bold font-mono text-white">91%</div>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-900/40 border border-slate-800">
          <div className="flex items-center gap-2 text-slate-400 text-xs mb-1">
            <Award className="w-4 h-4 text-emerald-400" />
            <span>Candidate Rank</span>
          </div>
          <div className="text-xl font-bold font-mono text-emerald-400">Top 5%</div>
        </div>
      </div>
    </div>
  );
}
