import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  BrainCircuit,
  ShieldCheck,
  Zap,
  Mic,
  BarChart3,
  ArrowRight,
  Sparkles,
  CheckCircle2,
  Lock,
  Layers,
  Activity,
} from 'lucide-react';
import { checkHealth } from '../services/api';
import Button from '../components/common/Button';

/**
 * Home Landing Page
 */
export default function Home() {
  const [healthStatus, setHealthStatus] = useState({ status: 'checking', mock: false });

  useEffect(() => {
    let mounted = true;
    checkHealth()
      .then((data) => {
        if (mounted) setHealthStatus({ status: 'ok', mock: data.mock });
      })
      .catch(() => {
        if (mounted) setHealthStatus({ status: 'offline', mock: false });
      });
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <div className="relative overflow-hidden min-h-[calc(100vh-4rem)]">
      {/* Background Decorative Cyber Glows */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-gradient-to-tr from-cyan-500/10 via-indigo-600/15 to-purple-600/10 rounded-full blur-[120px] pointer-events-none" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 lg:py-20 relative z-10">
        {/* Live System Health Banner */}
        <div className="flex justify-center mb-8">
          <div className="inline-flex items-center gap-2.5 px-4 py-1.5 rounded-full glass-panel border border-cyan-500/30 text-xs font-mono shadow-md shadow-cyan-500/10">
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
            </span>
            <span className="text-slate-300">Target API:</span>
            <span className="text-cyan-300 font-bold uppercase tracking-wider">
              {healthStatus.status === 'ok' ? 'Online & Ready (GET /health)' : 'Checking Status...'}
            </span>
          </div>
        </div>

        {/* Hero Section */}
        <div className="text-center max-w-4xl mx-auto space-y-6">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-300 text-xs font-semibold uppercase tracking-wider">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Next-Gen Technical Interviewing</span>
          </div>

          <h1 className="text-4xl sm:text-6xl lg:text-7xl font-extrabold text-white tracking-tight font-display leading-[1.1]">
            Adaptive AI Screening with{' '}
            <span className="cyber-gradient-text">Zero Compromise</span>
          </h1>

          <p className="text-base sm:text-xl text-slate-300 max-w-2xl mx-auto font-sans leading-relaxed">
            Screen top software engineers with dynamic real-time difficulty calibration,
            multi-modal speech recognition, and proactive anti-cheat telemetry monitoring.
          </p>

          {/* Action CTAs */}
          <div className="flex flex-wrap items-center justify-center gap-4 pt-4">
            <Link to="/upload">
              <Button
                variant="cyber"
                size="lg"
                rightIcon={<ArrowRight className="w-4 h-4" />}
                className="text-base font-semibold"
              >
                Start Candidate Screen
              </Button>
            </Link>

            <Link to="/dashboard/ses_demo_production">
              <Button
                variant="outline"
                size="lg"
                leftIcon={<BarChart3 className="w-4 h-4 text-cyan-400" />}
              >
                Inspect Sample Dashboard
              </Button>
            </Link>
          </div>
        </div>

        {/* System Highlights 4-Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mt-20">
          <div className="glass-card rounded-2xl p-6 border border-slate-700/60 hover:border-cyan-500/40 transition-all">
            <div className="p-3 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 w-fit mb-4">
              <Zap className="w-6 h-6" />
            </div>
            <h2 className="text-base font-bold text-white font-display mb-2">
              Adaptive Difficulty
            </h2>
            <p className="text-xs text-slate-400 leading-relaxed">
              Dynamically scales question complexity (Easy → Medium → Hard) based on evaluated candidate answer depth.
            </p>
          </div>

          <div className="glass-card rounded-2xl p-6 border border-slate-700/60 hover:border-indigo-500/40 transition-all">
            <div className="p-3 rounded-xl bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 w-fit mb-4">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <h2 className="text-base font-bold text-white font-display mb-2">
              Anti-Cheat Telemetry
            </h2>
            <p className="text-xs text-slate-400 leading-relaxed">
              Background event buffering captures window blur, tab switching, and clipboard pasting with 5s throttled flushing.
            </p>
          </div>

          <div className="glass-card rounded-2xl p-6 border border-slate-700/60 hover:border-purple-500/40 transition-all">
            <div className="p-3 rounded-xl bg-purple-500/10 border border-purple-500/30 text-purple-400 w-fit mb-4">
              <Mic className="w-6 h-6" />
            </div>
            <h2 className="text-base font-bold text-white font-display mb-2">
              Multi-Modal Voice Input
            </h2>
            <p className="text-xs text-slate-400 leading-relaxed">
              Real-time Web Speech recognition with fallback typed input and raw audio blob capture for resilient evaluation.
            </p>
          </div>

          <div className="glass-card rounded-2xl p-6 border border-slate-700/60 hover:border-emerald-500/40 transition-all">
            <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 w-fit mb-4">
              <BarChart3 className="w-6 h-6" />
            </div>
            <h2 className="text-base font-bold text-white font-display mb-2">
              Skill Gap & Analytics
            </h2>
            <p className="text-xs text-slate-400 leading-relaxed">
              Holistic recruiter reports synthesize competency profiles, role-fit matrix, and automated hiring recommendations.
            </p>
          </div>
        </div>

        {/* Quick Launchpad Banner */}
        <div className="mt-16 glass-panel rounded-3xl p-8 border border-slate-700/80 shadow-2xl relative overflow-hidden">
          <div className="flex flex-col lg:flex-row items-center justify-between gap-6">
            <div className="space-y-2 text-center lg:text-left">
              <span className="text-xs font-mono font-bold text-cyan-400 uppercase tracking-widest">
                Ready to evaluate?
              </span>
              <h2 className="text-2xl font-bold text-white font-display">
                Create a Session & Upload Resume
              </h2>
              <p className="text-xs sm:text-sm text-slate-400 max-w-xl">
                Parse candidate experience instantly and kick off an adaptive interview session with automated anti-cheat tracking.
              </p>
            </div>
            <Link to="/upload" className="shrink-0">
              <Button
                variant="cyber"
                size="md"
                rightIcon={<ArrowRight className="w-4 h-4" />}
              >
                Launch Interview Workflow
              </Button>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
