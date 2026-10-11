import React from 'react';
import { Mic, MicOff, Volume2, AlertCircle, CheckCircle2 } from 'lucide-react';
import Button from '../common/Button';

/**
 * Audio Recorder Component
 * Manages mic toggle, waveform animations, and audio playback review.
 */
export default function AudioRecorder({
  isRecording = false,
  permissionGranted = false,
  isSupported = true,
  audioUrl = null,
  error = null,
  onStart,
  onStop,
  onClear,
  disabled = false,
  className = '',
}) {
  return (
    <div
      className={`glass-panel rounded-2xl p-4 sm:p-5 border border-slate-700/60 shadow-lg ${className}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-4">
        {/* Mic Status & Info */}
        <div className="flex items-center gap-3">
          <div
            className={`relative p-3 rounded-2xl transition-all duration-300 ${
              isRecording
                ? 'bg-rose-500/20 text-rose-400 border border-rose-500/40 shadow-lg shadow-rose-500/30 animate-pulse'
                : 'bg-slate-800/80 text-cyan-400 border border-slate-700/80'
            }`}
          >
            {isRecording ? <Mic className="w-5 h-5" /> : <MicOff className="w-5 h-5" />}
            {isRecording && (
              <span className="absolute -top-1 -right-1 flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-3 w-3 bg-rose-500" />
              </span>
            )}
          </div>

          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-white font-display">
                {isRecording ? 'Listening & Transcribing...' : 'Voice Dictation'}
              </span>
              {permissionGranted && !isRecording && (
                <span className="flex items-center gap-1 text-[11px] text-emerald-400 font-mono">
                  <CheckCircle2 className="w-3 h-3" /> Mic Ready
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              {isRecording
                ? 'Speak clearly into your microphone; speech converts in real-time.'
                : 'Dictate your response or type directly in the box below.'}
            </p>
          </div>
        </div>

        {/* Audio Waveform Animation (When recording) */}
        {isRecording && (
          <div className="flex items-center gap-1 h-8 px-4 bg-slate-900/60 rounded-xl border border-slate-800">
            {[40, 70, 100, 60, 30, 80, 50, 90, 45, 75].map((height, i) => (
              <div
                key={i}
                className="w-1 bg-gradient-to-t from-cyan-500 to-indigo-500 rounded-full soundwave-bar"
                style={{
                  height: `${height}%`,
                  animationDelay: `${(i * 0.1).toFixed(1)}s`,
                }}
              />
            ))}
          </div>
        )}

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          {audioUrl && !isRecording && (
            <div className="flex items-center gap-2">
              <audio src={audioUrl} controls className="h-8 max-w-[200px]" />
            </div>
          )}

          {isRecording ? (
            <Button
              variant="danger"
              size="sm"
              onClick={onStop}
              disabled={disabled}
              leftIcon={<MicOff className="w-4 h-4" />}
            >
              Stop Voice
            </Button>
          ) : (
            <Button
              variant="primary"
              size="sm"
              onClick={onStart}
              disabled={disabled}
              leftIcon={<Mic className="w-4 h-4" />}
            >
              Start Speaking
            </Button>
          )}

          {audioUrl && !isRecording && (
            <Button variant="ghost" size="sm" onClick={onClear} disabled={disabled}>
              Reset Audio
            </Button>
          )}
        </div>
      </div>

      {/* Fallback Notice / Mic Error */}
      {error && (
        <div className="mt-3 p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center gap-2 text-xs text-amber-300">
          <AlertCircle className="w-4 h-4 shrink-0 text-amber-400" />
          <span>{error}</span>
        </div>
      )}

      {!isSupported && (
        <div className="mt-3 p-2.5 rounded-xl bg-slate-800/60 border border-slate-700/60 flex items-center gap-2 text-xs text-slate-300">
          <Volume2 className="w-4 h-4 shrink-0 text-cyan-400" />
          <span>
            Speech Recognition is in simulated/fallback mode for this browser. Standard typing is fully supported.
          </span>
        </div>
      )}
    </div>
  );
}
