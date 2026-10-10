import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Home from './pages/Home';
import UploadResume from './pages/UploadResume';
import Interview from './pages/Interview';
import RecruiterDashboard from './pages/RecruiterDashboard';
import NotFound from './pages/NotFound';

/**
 * Application Routes Configuration
 */
export default function AppRoutes() {
  return (
    <Routes>
      {/* Landing page */}
      <Route path="/" element={<Home />} />

      {/* Candidate Intake & Resume Parsing */}
      <Route path="/upload" element={<UploadResume />} />

      {/* Active Adaptive Interview Room */}
      <Route path="/interview/:sessionId" element={<Interview />} />

      {/* Recruiter Evaluation Dashboard */}
      <Route path="/dashboard/:sessionId" element={<RecruiterDashboard />} />

      {/* 404 Fallback */}
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
