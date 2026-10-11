import React from 'react';
import Card from '../common/Card';
import {
  FileCheck,
  CheckCircle,
  AlertTriangle,
  MessageSquare,
  HelpCircle,
  Download,
  Share2,
} from 'lucide-react';
import Button from '../common/Button';

/**
 * Detailed Report Summary & Question Breakdown Component
 */
export default function ReportSummary({
  report = {
    summary: '',
    recommendation: 'Strong Hire',
    keyStrengths: [],
    areasForImprovement: [],
  },
  answersBreakdown = [],
  className = '',
}) {
  const handlePrint = () => {
    window.print();
  };

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Executive Summary Card */}
      <Card
        title="AI Executive Evaluation"
        subtitle="Holistic performance synthesis and hiring recommendation"
        icon={<FileCheck className="w-5 h-5 text-indigo-400" />}
        headerRight={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handlePrint}
              leftIcon={<Download className="w-3.5 h-3.5" />}
            >
              Export PDF
            </Button>
          </div>
        }
      >
        <p className="text-sm text-slate-300 leading-relaxed bg-slate-900/40 p-4 rounded-xl border border-slate-800">
          {report.summary ||
            'The candidate demonstrated thorough engineering competency, maintaining calm reasoning under time constraints and articulating clean distributed system designs.'}
        </p>

        {/* Strengths & Improvement Points */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
          {/* Key Strengths */}
          <div className="p-4 rounded-xl bg-emerald-950/20 border border-emerald-800/30">
            <h4 className="text-xs font-semibold text-emerald-300 uppercase tracking-wider font-mono flex items-center gap-1.5 mb-3">
              <CheckCircle className="w-4 h-4 text-emerald-400" />
              Key Demonstrations
            </h4>
            <ul className="space-y-2">
              {(report.keyStrengths || []).map((strength, i) => (
                <li key={i} className="text-xs text-slate-300 flex items-start gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mt-1.5 shrink-0" />
                  <span>{strength}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Growth / Improvement Areas */}
          <div className="p-4 rounded-xl bg-amber-950/20 border border-amber-800/30">
            <h4 className="text-xs font-semibold text-amber-300 uppercase tracking-wider font-mono flex items-center gap-1.5 mb-3">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              Areas for Deeper Probing
            </h4>
            <ul className="space-y-2">
              {(report.areasForImprovement || []).map((area, i) => (
                <li key={i} className="text-xs text-slate-300 flex items-start gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400 mt-1.5 shrink-0" />
                  <span>{area}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </Card>

      {/* Question-by-Question Transcript and Feedback Breakdown */}
      <Card
        title="Question-by-Question Deep Dive"
        subtitle="Individual response transcripts, AI scoring, and feedback"
        icon={<MessageSquare className="w-5 h-5 text-purple-400" />}
      >
        <div className="space-y-5">
          {answersBreakdown.map((item, index) => (
            <div
              key={item.questionId || index}
              className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-3"
            >
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
                <span className="text-xs font-mono font-bold text-cyan-400">
                  Question #{index + 1}
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                    {item.difficulty || 'Adaptive'}
                  </span>
                  <span className="text-xs font-mono font-bold text-white bg-indigo-950/60 border border-indigo-700/50 px-2.5 py-0.5 rounded-full">
                    Score: {item.score}%
                  </span>
                </div>
              </div>

              {/* Question Text */}
              <div className="text-sm font-semibold text-slate-100 font-display">
                {item.questionText || `Question ID: ${item.questionId}`}
              </div>

              {/* Candidate Answer */}
              <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800 text-xs text-slate-300 leading-relaxed font-sans">
                <div className="text-[10px] uppercase font-mono text-slate-500 mb-1">
                  Candidate Transcript / Solution:
                </div>
                {item.answerText || item.text || 'No response recorded.'}
              </div>

              {/* AI Evaluator Feedback */}
              {item.feedback && (
                <div className="p-3 rounded-xl bg-indigo-950/20 border border-indigo-900/30 text-xs text-indigo-200">
                  <span className="font-semibold text-indigo-300">AI Evaluation: </span>
                  {item.feedback}
                </div>
              )}
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
