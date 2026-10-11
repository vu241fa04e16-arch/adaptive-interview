import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  BrainCircuit,
  ShieldCheck,
  Activity,
  FileText,
  BarChart3,
  Menu,
  X,
  Sparkles,
} from 'lucide-react';
import { checkHealth } from '../../services/api';

/**
 * Common Navigation Header
 */
export default function Navbar() {
  const location = useLocation();
  const [isHealthy, setIsHealthy] = useState(true);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    let mounted = true;
    checkHealth()
      .then((res) => {
        if (mounted) setIsHealthy(res.status === 'ok');
      })
      .catch(() => {
        if (mounted) setIsHealthy(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const isInterviewActive = location.pathname.startsWith('/interview/');

  const navLinks = [
    { label: 'Overview', to: '/', icon: <Activity className="w-4 h-4" /> },
    { label: 'New Candidate', to: '/upload', icon: <FileText className="w-4 h-4" /> },
    {
      label: 'Recruiter Dashboard',
      to: '/dashboard/ses_demo_production',
      icon: <BarChart3 className="w-4 h-4" />,
    },
  ];

  return (
    <nav className="sticky top-0 z-40 w-full glass-panel border-b border-slate-800/80 transition-all">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Brand Logo */}
          <Link to="/" className="flex items-center gap-3 group">
            <div className="relative p-2 rounded-xl bg-gradient-to-br from-indigo-500/20 to-cyan-500/20 border border-cyan-500/30 group-hover:border-cyan-400/60 transition-all shadow-md shadow-cyan-500/10">
              <BrainCircuit className="w-6 h-6 text-cyan-400 group-hover:rotate-12 transition-transform duration-300" />
              <div className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse" />
            </div>
            <div>
              <span className="font-display font-bold text-lg text-white tracking-wider flex items-center gap-1.5">
                ADAPTIVE<span className="cyber-gradient-text font-black">AI</span>
              </span>
              <span className="text-[10px] text-slate-400 tracking-widest uppercase block -mt-1 font-mono">
                Intelligent Screening
              </span>
            </div>
          </Link>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center gap-1">
            {navLinks.map((link) => {
              const isActive = location.pathname === link.to;
              return (
                <Link
                  key={link.to}
                  to={link.to}
                  className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-slate-800 text-cyan-300 border border-slate-700/60 shadow-inner'
                      : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
                  }`}
                >
                  {link.icon}
                  <span>{link.label}</span>
                </Link>
              );
            })}
          </div>

          {/* Header Right: Status and Indicators */}
          <div className="hidden md:flex items-center gap-3">
            {/* Live Interview Anti-Cheat State */}
            {isInterviewActive && (
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-medium animate-pulse">
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>Anti-Cheat Active</span>
              </div>
            )}

            {/* AI Engine Health Status */}
            <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-slate-900/60 border border-slate-800 text-xs font-mono">
              <div
                className={`w-2 h-2 rounded-full ${
                  isHealthy ? 'bg-emerald-400 animate-ping' : 'bg-amber-400'
                }`}
              />
              <span className={isHealthy ? 'text-slate-300' : 'text-amber-400'}>
                {isHealthy ? 'AI Core: Online' : 'AI Core: Standby'}
              </span>
            </div>

            <Link
              to="/upload"
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-gradient-to-r from-cyan-500 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 text-white shadow-md shadow-cyan-500/20 transition-all"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Start Screen</span>
            </Link>
          </div>

          {/* Mobile menu button */}
          <div className="flex md:hidden">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/80"
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Menu Dropdown */}
      {mobileMenuOpen && (
        <div className="md:hidden border-t border-slate-800/80 bg-surface-200/95 backdrop-blur-xl px-4 pt-3 pb-5 space-y-2">
          {navLinks.map((link) => {
            const isActive = location.pathname === link.to;
            return (
              <Link
                key={link.to}
                to={link.to}
                onClick={() => setMobileMenuOpen(false)}
                className={`flex items-center gap-2.5 px-4 py-2.5 rounded-xl text-sm font-medium ${
                  isActive
                    ? 'bg-slate-800 text-cyan-300 border border-slate-700'
                    : 'text-slate-300 hover:bg-slate-800/50 hover:text-white'
                }`}
              >
                {link.icon}
                <span>{link.label}</span>
              </Link>
            );
          })}
          <div className="pt-2">
            <Link
              to="/upload"
              onClick={() => setMobileMenuOpen(false)}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold bg-gradient-to-r from-cyan-500 to-indigo-600 text-white"
            >
              <Sparkles className="w-4 h-4" />
              <span>Start New Interview</span>
            </Link>
          </div>
        </div>
      )}
    </nav>
  );
}
