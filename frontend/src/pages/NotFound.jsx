import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AlertOctagon, ArrowLeft, Home, Search, Sparkles } from 'lucide-react';
import Button from '../components/common/Button';

/**
 * NotFound 404 Fallback Page
 */
export default function NotFound() {
  const navigate = useNavigate();
  const [searchSession, setSearchSession] = useState('');

  const handleSessionSearch = (e) => {
    e.preventDefault();
    if (searchSession.trim()) {
      navigate(`/interview/${searchSession.trim()}`);
    }
  };

  return (
    <div className="min-h-[75vh] flex flex-col items-center justify-center px-4 py-16 text-center">
      <div className="relative mb-6">
        <div className="w-24 h-24 rounded-3xl bg-rose-500/10 border border-rose-500/30 text-rose-400 flex items-center justify-center mx-auto shadow-2xl shadow-rose-500/20">
          <AlertOctagon className="w-12 h-12" />
        </div>
        <div className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-rose-500 animate-ping" />
      </div>

      <span className="text-xs font-mono font-bold text-rose-400 uppercase tracking-widest px-3 py-1 rounded-full bg-rose-500/10 border border-rose-500/20">
        404 • Resource Not Found
      </span>

      <h1 className="text-3xl sm:text-5xl font-extrabold text-white font-display mt-4 mb-2">
        Invalid Session or URL
      </h1>

      <p className="text-sm text-slate-400 max-w-md mx-auto mb-8">
        The requested interview session URL does not exist or has expired. Check your invitation link
        or start a new session.
      </p>

      {/* Quick Lookup Form */}
      <form onSubmit={handleSessionSearch} className="flex items-center gap-2 max-w-sm w-full mb-8">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
          <input
            type="text"
            value={searchSession}
            onChange={(e) => setSearchSession(e.target.value)}
            placeholder="Paste session ID..."
            className="w-full bg-slate-900 border border-slate-700 rounded-xl pl-10 pr-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 font-mono"
          />
        </div>
        <Button type="submit" variant="secondary" size="sm">
          Go
        </Button>
      </form>

      {/* Navigation Options */}
      <div className="flex flex-wrap items-center justify-center gap-4">
        <Link to="/">
          <Button variant="cyber" size="md" leftIcon={<Home className="w-4 h-4" />}>
            Return to Homepage
          </Button>
        </Link>
        <Link to="/upload">
          <Button variant="outline" size="md" leftIcon={<Sparkles className="w-4 h-4 text-cyan-400" />}>
            Start New Screening
          </Button>
        </Link>
      </div>
    </div>
  );
}
