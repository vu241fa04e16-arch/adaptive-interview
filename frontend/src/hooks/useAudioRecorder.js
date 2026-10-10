import { useState, useRef, useEffect, useCallback } from 'react';
import {
  isSpeechRecognitionSupported,
  createSpeechRecognizer,
  AudioStreamCapture,
} from '../services/speechToText';

/**
 * useAudioRecorder Hook
 * Manages microphone capture, Web Speech API speech-to-text,
 * and audio blob recording with graceful fallback.
 */
export function useAudioRecorder() {
  const [isRecording, setIsRecording] = useState(false);
  const [permissionGranted, setPermissionGranted] = useState(false);
  const [isSupported, setIsSupported] = useState(true);
  const [transcript, setTranscript] = useState('');
  const [interimTranscript, setInterimTranscript] = useState('');
  const [audioBlob, setAudioBlob] = useState(null);
  const [audioUrl, setAudioUrl] = useState(null);
  const [error, setError] = useState(null);

  const captureRef = useRef(null);
  const recognizerRef = useRef(null);

  // Initialize support check
  useEffect(() => {
    setIsSupported(isSpeechRecognitionSupported());
    captureRef.current = new AudioStreamCapture();

    return () => {
      if (captureRef.current) {
        captureRef.current.cleanup();
      }
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
      }
    };
  }, []);

  /**
   * Start microphone capture and live recognition
   */
  const startRecording = useCallback(async () => {
    setError(null);
    try {
      // 1. Request microphone permission & stream
      await captureRef.current.requestMicStream();
      setPermissionGranted(true);

      // 2. Start audio media recorder (for raw audio blob)
      captureRef.current.startRecording();

      // 3. Start Web Speech recognition if supported
      if (isSpeechRecognitionSupported()) {
        const recognizer = createSpeechRecognizer({
          onResult: ({ final, interim }) => {
            if (final) {
              setTranscript((prev) => (prev ? `${prev} ${final}` : final));
            }
            setInterimTranscript(interim);
          },
          onError: (err) => {
            console.warn('SpeechRecognition warning:', err);
            // Non-fatal warning; typed response fallback remains functional
          },
          onEnd: () => {
            // Keep active if recording state is still active
          },
        });

        if (recognizer) {
          recognizerRef.current = recognizer;
          try {
            recognizer.start();
          } catch (e) {
            console.warn('SpeechRecognition start error:', e);
          }
        }
      }

      setIsRecording(true);
    } catch (err) {
      console.warn('Microphone access denied or unavailable:', err.message);
      setError(err.message || 'Microphone access denied. You can still type your answers.');
      setPermissionGranted(false);
      setIsRecording(false);
    }
  }, []);

  /**
   * Stop recording and capture the audio blob
   */
  const stopRecording = useCallback(async () => {
    setIsRecording(false);
    setInterimTranscript('');

    if (recognizerRef.current) {
      try {
        recognizerRef.current.stop();
      } catch (e) {
        // Ignored
      }
      recognizerRef.current = null;
    }

    if (captureRef.current) {
      const blob = await captureRef.current.stopRecording();
      if (blob) {
        setAudioBlob(blob);
        if (audioUrl) URL.revokeObjectURL(audioUrl);
        const url = URL.createObjectURL(blob);
        setAudioUrl(url);
      }
    }
  }, [audioUrl]);

  /**
   * Clear recorded text and audio
   */
  const clearTranscript = useCallback(() => {
    setTranscript('');
    setInterimTranscript('');
    setAudioBlob(null);
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl);
      setAudioUrl(null);
    }
  }, [audioUrl]);

  /**
   * Directly update transcript (e.g. manual typing edits)
   */
  const setTranscriptDirectly = useCallback((newText) => {
    setTranscript(newText);
  }, []);

  return {
    isRecording,
    isSupported,
    permissionGranted,
    transcript,
    interimTranscript,
    audioBlob,
    audioUrl,
    error,
    startRecording,
    stopRecording,
    clearTranscript,
    setTranscriptDirectly,
  };
}
