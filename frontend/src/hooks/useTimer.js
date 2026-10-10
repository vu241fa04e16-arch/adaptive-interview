import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * useTimer Hook
 * Countdown timer per adaptive question with auto-submit trigger on expiration.
 * Features strict mutex locking to prevent duplicate onExpire callback firing.
 *
 * @param {object} params
 * @param {number} params.initialSeconds - Starting countdown in seconds
 * @param {Function} params.onExpire - Callback fired when timer hits 0
 * @param {boolean} [params.autoStart=true] - Auto-start timer
 */
export function useTimer({ initialSeconds = 120, onExpire, autoStart = true }) {
  const [totalSeconds, setTotalSeconds] = useState(initialSeconds);
  const [remainingSeconds, setRemainingSeconds] = useState(initialSeconds);
  const [isRunning, setIsRunning] = useState(autoStart);
  const [isExpired, setIsExpired] = useState(false);

  // Mutex ref: ensures onExpire is only invoked once per question/cycle
  const hasExpiredRef = useRef(false);
  const onExpireRef = useRef(onExpire);
  onExpireRef.current = onExpire;

  // Reset timer for the next question
  const resetTimer = useCallback((newSeconds) => {
    const nextLimit = typeof newSeconds === 'number' ? newSeconds : initialSeconds;
    hasExpiredRef.current = false;
    setTotalSeconds(nextLimit);
    setRemainingSeconds(nextLimit);
    setIsExpired(false);
    setIsRunning(true);
  }, [initialSeconds]);

  const pauseTimer = useCallback(() => setIsRunning(false), []);
  const resumeTimer = useCallback(() => {
    if (!isExpired) setIsRunning(true);
  }, [isExpired]);

  // Main countdown ticker
  useEffect(() => {
    if (!isRunning || isExpired) return;

    const intervalId = setInterval(() => {
      setRemainingSeconds((prev) => {
        if (prev <= 1) {
          clearInterval(intervalId);
          setIsRunning(false);
          setIsExpired(true);

          // Atomic trigger check to prevent race condition
          if (!hasExpiredRef.current) {
            hasExpiredRef.current = true;
            if (onExpireRef.current) {
              onExpireRef.current();
            }
          }
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(intervalId);
  }, [isRunning, isExpired]);

  // Calculate percentage remaining (0 - 100)
  const progressPercent = totalSeconds > 0
    ? Math.max(0, Math.min(100, Math.round((remainingSeconds / totalSeconds) * 100)))
    : 0;

  return {
    remainingSeconds,
    totalSeconds,
    progressPercent,
    isRunning,
    isExpired,
    resetTimer,
    pauseTimer,
    resumeTimer,
  };
}
