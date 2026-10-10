import { useEffect, useRef, useState, useCallback } from 'react';
import { recordIntegrityEvent } from '../services/api';
import {
  INTEGRITY_EVENTS,
  INTEGRITY_EVENT_METADATA,
  INTEGRITY_FLUSH_INTERVAL_MS,
} from '../utils/constants';

/**
 * useIntegrity Hook
 * Anti-cheat telemetry tracking in the background.
 * Buffers telemetry events locally and flushes them to the backend in batches
 * every 5 seconds (preventing flood attacks from rapid alt-tabbing/resizing).
 *
 * @param {string} sessionId
 * @param {object} options
 */
export function useIntegrity(sessionId, options = {}) {
  const { enabled = true, flushIntervalMs = INTEGRITY_FLUSH_INTERVAL_MS } = options;

  const [events, setEvents] = useState([]);
  const [violationsCount, setViolationsCount] = useState(0);
  const [integrityScore, setIntegrityScore] = useState(100);

  // Local buffer to throttle and batch HTTP requests
  const eventBufferRef = useRef([]);
  const sessionIdRef = useRef(sessionId);
  sessionIdRef.current = sessionId;

  /**
   * Flush pending buffer to backend
   */
  const flushPendingEvents = useCallback(async () => {
    if (eventBufferRef.current.length === 0 || !sessionIdRef.current) return;

    const batchToSend = [...eventBufferRef.current];
    eventBufferRef.current = [];

    try {
      await recordIntegrityEvent(sessionIdRef.current, { events: batchToSend });
    } catch (err) {
      console.warn('Failed to flush integrity events to backend:', err);
      // Re-insert un-sent events to front of buffer (up to limit of 50 to prevent unbounded growth)
      if (eventBufferRef.current.length < 50) {
        eventBufferRef.current = [...batchToSend, ...eventBufferRef.current];
      }
    }
  }, []);

  /**
   * Log an anti-cheat event
   */
  const logEvent = useCallback((type, details = {}) => {
    const meta = INTEGRITY_EVENT_METADATA[type] || {
      label: type,
      penalty: 5,
      severity: 'low',
    };

    const newEvent = {
      type,
      label: meta.label,
      severity: meta.severity,
      timestamp: new Date().toISOString(),
      ...details,
    };

    // Add to state for real-time UI telemetry
    setEvents((prev) => [newEvent, ...prev]);
    setViolationsCount((prev) => prev + 1);
    setIntegrityScore((prev) => Math.max(30, prev - (meta.penalty || 5)));

    // Buffer for batched dispatch
    eventBufferRef.current.push(newEvent);
  }, []);

  // Periodic flush interval (Mitigation: integrity throttling)
  useEffect(() => {
    if (!enabled || !sessionId) return;

    const intervalId = setInterval(() => {
      flushPendingEvents();
    }, flushIntervalMs);

    return () => {
      clearInterval(intervalId);
      // Flush remaining events before unmounting
      flushPendingEvents();
    };
  }, [enabled, sessionId, flushIntervalMs, flushPendingEvents]);

  // Event Listeners for Anti-cheat triggers
  useEffect(() => {
    if (!enabled || !sessionId) return;

    // 1. Tab switch / backgrounded
    const handleVisibilityChange = () => {
      if (document.hidden) {
        logEvent(INTEGRITY_EVENTS.VISIBILITY_CHANGE, {
          details: 'Browser tab lost visibility / window minimized',
        });
      }
    };

    // 2. Window blur (focus lost to external app or second monitor)
    const handleWindowBlur = () => {
      logEvent(INTEGRITY_EVENTS.WINDOW_BLUR, {
        details: 'Candidate window focus lost',
      });
    };

    // 3. Copy attempt
    const handleCopy = (e) => {
      const selectedText = window.getSelection()?.toString() || '';
      logEvent(INTEGRITY_EVENTS.COPY, {
        details: selectedText ? `Copied ${selectedText.length} characters` : 'Copy action triggered',
      });
    };

    // 4. Paste attempt
    const handlePaste = (e) => {
      const pastedData = e.clipboardData?.getData('text') || '';
      logEvent(INTEGRITY_EVENTS.PASTE, {
        details: pastedData ? `Pasted ${pastedData.length} characters` : 'Paste action triggered',
      });
    };

    // 5. Context menu (Right-click)
    const handleContextMenu = (e) => {
      // We allow standard UI but flag right-click inspect attempts
      logEvent(INTEGRITY_EVENTS.CONTEXT_MENU, {
        details: 'Right-click context menu triggered',
      });
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('blur', handleWindowBlur);
    document.addEventListener('copy', handleCopy);
    document.addEventListener('paste', handlePaste);
    document.addEventListener('contextmenu', handleContextMenu);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('blur', handleWindowBlur);
      document.removeEventListener('copy', handleCopy);
      document.removeEventListener('paste', handlePaste);
      document.removeEventListener('contextmenu', handleContextMenu);
    };
  }, [enabled, sessionId, logEvent]);

  // Compute status category
  const status =
    integrityScore >= 85 ? 'secure' : integrityScore >= 60 ? 'warning' : 'alert';

  return {
    events,
    violationsCount,
    integrityScore,
    status,
    logCustomEvent: logEvent,
    flushEvents: flushPendingEvents,
  };
}
