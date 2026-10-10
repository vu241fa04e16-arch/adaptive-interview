import React from 'react';
import Card from '../common/Card';
import { Target, CheckCircle2, AlertCircle, ArrowUpRight } from 'lucide-react';

/**
 * SkillGapMap Component for Recruiter Dashboard
 * Compares required skills vs candidate demonstrated skills
 */
export default function SkillGapMap({
  skillsAssessment = [
    { skill: 'Distributed Systems', required: 90, candidate: 88, status: 'Match' },
    { skill: 'High-Throughput Concurrency', required: 85, candidate: 82, status: 'Match' },
    { skill: 'Database Isolation (MVCC)', required: 80, candidate: 92, status: 'Exceeds' },
    { skill: 'Front-End CWV/Rendering', required: 75, candidate: 85, status: 'Exceeds' },
    { skill: 'Kubernetes Orchestration', required: 85, candidate: 70, status: 'Moderate Gap' },
  ],
  className = '',
}) {
  const getStatusBadge = (status) => {
    switch (status) {
      case 'Exceeds':
        return (
          <span className="flex items-center gap-1 text-[11px] font-mono text-cyan-300 bg-cyan-950/40 border border-cyan-800/40 px-2 py-0.5 rounded-full">
            <ArrowUpRight className="w-3 h-3 text-cyan-400" /> Exceeds Target
          </span>
        );
      case 'Match':
        return (
          <span className="flex items-center gap-1 text-[11px] font-mono text-emerald-300 bg-emerald-950/40 border border-emerald-800/40 px-2 py-0.5 rounded-full">
            <CheckCircle2 className="w-3 h-3 text-emerald-400" /> Role Match
          </span>
        );
      default:
        return (
          <span className="flex items-center gap-1 text-[11px] font-mono text-amber-300 bg-amber-950/40 border border-amber-800/40 px-2 py-0.5 rounded-full">
            <AlertCircle className="w-3 h-3 text-amber-400" /> {status}
          </span>
        );
    }
  };

  return (
    <Card
      title="Role Skill-Gap Matrix"
      subtitle="Benchmark comparison between job criteria and candidate performance"
      icon={<Target className="w-5 h-5 text-cyan-400" />}
      className={className}
    >
      <div className="space-y-4">
        {skillsAssessment.map((item, index) => (
          <div
            key={index}
            className="p-3.5 rounded-xl bg-slate-900/40 border border-slate-800 space-y-2 hover:border-slate-700 transition-colors"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-200">{item.skill}</span>
              {getStatusBadge(item.status)}
            </div>

            {/* Comparison Visualizer */}
            <div className="grid grid-cols-2 gap-3 text-[11px] font-mono">
              <div>
                <div className="flex justify-between text-slate-400 mb-1">
                  <span>Candidate</span>
                  <span className="text-cyan-400 font-bold">{item.candidate}%</span>
                </div>
                <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                  <div
                    className="bg-cyan-400 h-full rounded-full transition-all duration-500"
                    style={{ width: `${item.candidate}%` }}
                  />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-slate-400 mb-1">
                  <span>Role Target</span>
                  <span className="text-slate-300">{item.required}%</span>
                </div>
                <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                  <div
                    className="bg-slate-500 h-full rounded-full transition-all duration-500"
                    style={{ width: `${item.required}%` }}
                  />
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
