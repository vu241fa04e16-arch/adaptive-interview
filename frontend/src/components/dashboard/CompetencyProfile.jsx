import React from 'react';
import Card from '../common/Card';
import ProgressBar from '../common/ProgressBar';
import { Layers } from 'lucide-react';

/**
 * Competency Profile Breakdown Component
 */
export default function CompetencyProfile({
  competencies = {
    'System Architecture': 88,
    'Algorithmic Efficiency': 82,
    'Data Integrity & MVCC': 91,
    'Frontend Performance (CWV)': 85,
    'Communication & Problem Framing': 89,
  },
  className = '',
}) {
  const competencyList = Object.entries(competencies).map(([name, score]) => ({
    name,
    score,
    variant: score >= 88 ? 'cyber' : score >= 80 ? 'cyan' : 'indigo',
    rating: score >= 90 ? 'Mastery' : score >= 80 ? 'Proficient' : 'Developing',
  }));

  return (
    <Card
      title="Competency Assessment"
      subtitle="Evaluated across adaptive multi-tier technical formulations"
      icon={<Layers className="w-5 h-5 text-indigo-400" />}
      className={className}
    >
      <div className="space-y-5">
        {competencyList.map((item) => (
          <div key={item.name} className="space-y-1.5">
            <div className="flex items-center justify-between text-xs">
              <span className="font-medium text-slate-200">{item.name}</span>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                  {item.rating}
                </span>
                <span className="font-mono font-bold text-cyan-400">{item.score}%</span>
              </div>
            </div>
            <ProgressBar
              value={item.score}
              variant={item.variant}
              size="sm"
            />
          </div>
        ))}
      </div>
    </Card>
  );
}
