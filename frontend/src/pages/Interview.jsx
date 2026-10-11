import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Shield,
  CheckCircle,
  AlertCircle,
  Sparkles,
  ArrowRight,
  Maximize2,
  Lock,
} from 'lucide-react';
import QuestionCard from '../components/interview/QuestionCard';
import Timer from '../components/interview/Timer';
import AudioRecorder from '../components/interview/AudioRecorder';
import ResponseBox from '../components/interview/ResponseBox';
import IntegrityBadge from '../components/interview/IntegrityBadge';
import Modal from '../components/common/Modal';
import Button from '../components/common/Button';
import Spinner from '../components/common/Spinner';

import { useInterviewSession } from '../hooks/useInterviewSession';
import { useTimer } from '../hooks/useTimer';
import { useAudioRecorder } from '../hooks/useAudioRecorder';
import { useIntegrity } from '../hooks/useIntegrity';

/**
 * Interview Active Room Page
 */
export default function Interview() {
  const { sessionId } = useParams();
  const navigate = useNavigate();

  // 1. Core Interview Session Manager (Hydration & Question Transitions)
  const {
    currentQuestion,
    questionNumber,
    totalQuestions,
    isLoading: isQuestionLoading,
    isSubmitting,
    isCompleted,
    error: sessionError,
    submitCurrentAnswer,
    finishInterviewSession,
  } = useInterviewSession(sessionId);

  // 2. Anti-Cheat Integrity Tracking Hook (Buffering & 5s Batch Flush)
  const {
    events: integrityEvents,
    violationsCount,
    integrityScore,
    status: integrityStatus,
    flushEvents,
  } = useIntegrity(sessionId, { enabled: !isCompleted });

  // 3. Audio & Speech-to-Text Dictation Hook
  const {
    isRecording,
    isSupported: isSpeechSupported,
    permissionGranted: micPermissionGranted,
    transcript,
    interimTranscript,
    audioUrl,
    error: audioError,
    startRecording,
    stopRecording,
    clearTranscript,
    setTranscriptDirectly,
  } = useAudioRecorder();

  // Answer text state (combines typed and voice input)
  const [responseText, setResponseText] = useState('');
  const responseTextRef = useRef('');
  responseTextRef.current = responseText;

  // Sync speech transcript into response text
  useEffect(() => {
    if (transcript) {
      setResponseText((prev) => {
        // If transcript changed, append or set
        return transcript;
      });
    }
  }, [transcript]);

  // Handle auto-submit on timer expiration (Mitigation: timer race conditions)
  const handleTimerExpire = useCallback(async () => {
    console.warn('Question timer expired! Automatically submitting current answer...');
    // Stop recording if active
    if (isRecording) {
      stopRecording();
    }
    const finalAnswer = responseTextRef.current || 'Time expired before response submission.';
    await submitCurrentAnswer(finalAnswer);
    setResponseText('');
    clearTranscript();
  }, [isRecording, stopRecording, submitCurrentAnswer, clearTranscript]);

  // 4. Per-Question Countdown Timer Hook
  const {
    remainingSeconds,
    progressPercent,
    isExpired: isTimerExpired,
    resetTimer,
  } = useTimer({
    initialSeconds: currentQuestion?.timeLimit || 120,
    onExpire: handleTimerExpire,
    autoStart: true,
  });

  // Reset timer whenever a new adaptive question loads
  const currentQuestionId = currentQuestion?.questionId;
  useEffect(() => {
    if (currentQuestion?.timeLimit) {
      resetTimer(currentQuestion.timeLimit);
      setResponseText('');
      clearTranscript();
    }
  }, [currentQuestionId, resetTimer, clearTranscript]);

  // Manual answer submission handler
  const handleSubmitAnswer = async () => {
    if (isRecording) {
      stopRecording();
    }
    const res = await submitCurrentAnswer(responseText);
    if (res?.success) {
      setResponseText('');
      clearTranscript();
    }
  };

  // Navigate to Dashboard when completed
  const handleViewReport = () => {
    flushEvents();
    navigate(`/dashboard/${sessionId}`);
  };

  if (isQuestionLoading) {
    return (
      <div className="min-h-[70vh] flex flex-col items-center justify-center p-6 space-y-4">
        <Spinner size="xl" />
        <div className="text-center">
          <h2 className="text-lg font-semibold text-white font-display">
            Hydrating Adaptive Session...
          </h2>
          <p className="text-xs text-slate-400 mt-1 font-mono">
            GET /sessions/{sessionId}/next-question
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 lg:py-8 space-y-6">
      {/* Top Session Status and Anti-Cheat Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 glass-panel rounded-2xl px-5 py-3 border border-slate-700/60 shadow-lg">
        <div className="flex items-center gap-3">
          <span className="flex h-3 w-3 relative">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500" />
          </span>
          <div>
            <span className="text-xs font-semibold text-white tracking-wide">
              Active Screening Session
            </span>
            <span className="text-[10px] text-slate-400 block font-mono">
              Session ID: {sessionId}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Anti-cheat live telemetry badge */}
          <IntegrityBadge
            integrityScore={integrityScore}
            violationsCount={violationsCount}
            events={integrityEvents}
            status={integrityStatus}
          />

          <Button
            variant="ghost"
            size="sm"
            onClick={finishInterviewSession}
            disabled={isSubmitting}
            className="text-xs text-slate-400 hover:text-rose-400"
          >
            End Interview
          </Button>
        </div>
      </div>

      {sessionError && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-center gap-3 text-sm text-rose-300">
          <AlertCircle className="w-5 h-5 shrink-0 text-rose-400" />
          <span>{sessionError}</span>
        </div>
      )}

      {/* Main Grid: Question & Timer on top, Response & Audio below */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Adaptive Question Card (Spans 2 cols) */}
        <div className="lg:col-span-2 space-y-6">
          <QuestionCard
            question={currentQuestion}
            questionNumber={questionNumber}
            totalQuestions={totalQuestions}
          />

          {/* Voice Dictation Panel */}
          <AudioRecorder
            isRecording={isRecording}
            permissionGranted={micPermissionGranted}
            isSupported={isSpeechSupported}
            audioUrl={audioUrl}
            error={audioError}
            disabled={isSubmitting}
            onStart={startRecording}
            onStop={stopRecording}
            onClear={clearTranscript}
          />

          {/* Text/Speech Answer Response Box */}
          <ResponseBox
            value={responseText}
            onChange={(val) => {
              setResponseText(val);
              setTranscriptDirectly(val);
            }}
            onSubmit={handleSubmitAnswer}
            isSubmitting={isSubmitting}
            disabled={isTimerExpired || isSubmitting}
            interimTranscript={interimTranscript}
          />
        </div>

        {/* Right Column: Timer & Heuristic Monitoring */}
        <div className="space-y-6">
          <Timer
            remainingSeconds={remainingSeconds}
            progressPercent={progressPercent}
            isExpired={isTimerExpired}
          />

          {/* Real-Time Session Guidance Card */}
          <div className="glass-card rounded-2xl p-5 border border-slate-700/60 space-y-3">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-300 font-mono">
              <Sparkles className="w-4 h-4 text-cyan-400" />
              <span>Interview Heuristics</span>
            </div>
            <ul className="text-xs text-slate-400 space-y-2.5">
              <li className="flex items-start gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 mt-1.5 shrink-0" />
                <span>
                  <strong>Dynamic Rigor:</strong> Solutions with concrete architecture
                  trade-offs unlock advanced architect-tier questions.
                </span>
              </li>
              <li className="flex items-start gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 mt-1.5 shrink-0" />
                <span>
                  <strong>Multi-Modal Input:</strong> You can speak using the microphone or type
                  directly. Both feed into the semantic evaluator.
                </span>
              </li>
              <li className="flex items-start gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mt-1.5 shrink-0" />
                <span>
                  <strong>Focus Lock:</strong> Tab switches or window defocus are tracked via
                  anti-cheat telemetry and reflected in the recruiter report.
                </span>
              </li>
            </ul>
          </div>
        </div>
      </div>

      {/* Completion Modal */}
      <Modal
        isOpen={isCompleted}
        onClose={handleViewReport}
        title="Adaptive Screening Completed"
        description="All questions completed. AI evaluation synthesis is ready."
        size="md"
        closeOnBackdrop={false}
        footer={
          <Button
            variant="cyber"
            size="md"
            onClick={handleViewReport}
            rightIcon={<ArrowRight className="w-4 h-4" />}
          >
            View Candidate Report & Dashboard
          </Button>
        }
      >
        <div className="text-center py-4 space-y-4">
          <div className="w-16 h-16 rounded-full bg-emerald-500/20 border border-emerald-500/40 text-emerald-400 flex items-center justify-center mx-auto shadow-lg shadow-emerald-500/20">
            <CheckCircle className="w-8 h-8" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white font-display">
              Interview Successfully Concluded
            </h3>
            <p className="text-xs text-slate-300 mt-1 max-w-sm mx-auto">
              Candidate answers have been scored and calibrated against target role competencies.
              Anti-cheat telemetry has been bundled and sealed.
            </p>
          </div>
          <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 text-xs font-mono text-cyan-300">
            Session: {sessionId} • Status: COMPLETED
          </div>
        </div>
      </Modal>
    </div>
  );
}
