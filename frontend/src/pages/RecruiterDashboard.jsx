import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  BarChart3,
  ShieldCheck,
  Award,
  ArrowLeft,
  Sparkles,
  RefreshCw,
  Search,
  CheckCircle,
} from 'lucide-react';
import ScoreCard from '../components/dashboard/ScoreCard';
import CompetencyProfile from '../components/dashboard/CompetencyProfile';
import IntegrityTimeline from '../components/dashboard/IntegrityTimeline';
import SkillGapMap from '../components/dashboard/SkillGapMap';
import ReportSummary from '../components/dashboard/ReportSummary';
import Spinner from '../components/common/Spinner';
import Button from '../components/common/Button';
import { getReport } from '../services/api';

/**
 * Recruiter Dashboard Page
 * Visualizes candidate composite scores, anti-cheat telemetry, and skill-gap radar.
 */
export default function RecruiterDashboard() {
  const { sessionId } = useParams();
  const [reportData, setReportData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Search input for quick session lookup
  const [sessionInput, setSessionInput] = useState(sessionId || '');

  const fetchDashboardReport = async (idToFetch) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getReport(idToFetch);
      setReportData(data);
    } catch (err) {
      console.error('Failed to fetch recruiter report:', err);
      setError(err.message || 'Failed to retrieve candidate report.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardReport(sessionId || 'ses_demo_production');
  }, [sessionId]);

  const handleLookup = (e) => {
    e.preventDefault();
    if (sessionInput.trim()) {
      fetchDashboardReport(sessionInput.trim());
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-[75vh] flex flex-col items-center justify-center p-6 space-y-4">
        <Spinner size="xl" />
        <div className="text-center">
          <h2 className="text-lg font-semibold text-white font-display">
            Synthesizing Candidate Report...
          </h2>
          <p className="text-xs text-slate-400 mt-1 font-mono">
            GET /sessions/{sessionId}/report
          </p>
        </div>
      </div>
    );
  }

  if (error || !reportData) {
    return (
      <div className="max-w-xl mx-auto my-20 p-8 glass-card rounded-3xl border border-rose-500/40 text-center space-y-4">
        <h2 className="text-xl font-bold text-white font-display">
          Unable to Load Report
        </h2>
        <p className="text-xs text-rose-300">{error || 'Session report not found.'}</p>
        <div className="pt-2">
          <Button
            variant="cyber"
            size="md"
            onClick={() => fetchDashboardReport('ses_demo_production')}
          >
            Load Production Demo Report
          </Button>
        </div>
      </div>
    );
  }

  const {
    candidate,
    overallScore,
    integrityScore,
    competencies,
    skillsAssessment,
    integrityTimeline,
    answersBreakdown,
    report,
  } = reportData;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Dashboard Top Header & Session Lookup */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono text-cyan-400 mb-1">
            <BarChart3 className="w-4 h-4" />
            <span>Recruiter Intelligence Portal</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white font-display">
            Candidate Evaluation Dashboard
          </h1>
          <p className="text-xs text-slate-400 mt-0.5 font-mono">
            Session Reference: {reportData.sessionId}
          </p>
        </div>

        {/* Quick Session Lookup & Back to Home */}
        <div className="flex flex-wrap items-center gap-3">
          <form onSubmit={handleLookup} className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={sessionInput}
              onChange={(e) => setSessionInput(e.target.value)}
              placeholder="Search Session ID..."
              className="bg-slate-900 border border-slate-700 rounded-xl pl-9 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 font-mono"
            />
          </form>

          <Button
            variant="secondary"
            size="sm"
            onClick={() => fetchDashboardReport(reportData.sessionId)}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            Refresh
          </Button>

          <Link to="/">
            <Button
              variant="outline"
              size="sm"
              leftIcon={<ArrowLeft className="w-3.5 h-3.5" />}
            >
              Home
            </Button>
          </Link>
        </div>
      </div>

      {/* 1. Hero Score Card */}
      <ScoreCard
        overallScore={overallScore}
        integrityScore={integrityScore}
        recommendation={report.recommendation}
        candidateName={candidate?.name}
        targetRole={candidate?.targetRole}
      />

      {/* 2. Analytical Charts Grid: Competency Profile & Skill Gap Map */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <CompetencyProfile competencies={competencies} />
        <SkillGapMap skillsAssessment={skillsAssessment} />
      </div>

      {/* 3. Anti-Cheat Heuristic Timeline & Verification */}
      <IntegrityTimeline events={integrityTimeline} />

      {/* 4. Executive Summary & Question-by-Question Deep Dive */}
      <ReportSummary
        report={report}
        answersBreakdown={answersBreakdown}
      />
    </div>
  );
}
