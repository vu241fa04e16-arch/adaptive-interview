import { useState, useEffect, useRef, useCallback } from 'react';
import { getNextQuestion, submitAnswer, completeInterview } from '../services/api';

/**
 * useInterviewSession Hook
 * Manages interview question lifecycle, adaptive difficulty progression,
 * submission mutex locking, and session hydration on browser refresh.
 *
 * @param {string} sessionId
 */
export function useInterviewSession(sessionId) {
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [questionNumber, setQuestionNumber] = useState(1);
  const [totalQuestions, setTotalQuestions] = useState(4);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isCompleted, setIsCompleted] = useState(false);
  const [error, setError] = useState(null);
  const [answersHistory, setAnswersHistory] = useState([]);

  // Submission Mutex: Guards against double-submission from concurrent timer expiry and button click
  const submissionMutexRef = useRef(false);

  /**
   * Session Hydration on Mount:
   * Hydrates active question state and progress directly from /sessions/{id}/next-question
   */
  const hydrateSession = useCallback(async () => {
    if (!sessionId) {
      setError('Invalid or missing session identifier.');
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const questionData = await getNextQuestion(sessionId);

      if (!questionData || !questionData.hasMore) {
        setIsCompleted(true);
        setCurrentQuestion(null);
      } else {
        setCurrentQuestion(questionData);
        setQuestionNumber(questionData.questionNumber || 1);
        if (questionData.totalQuestions) {
          setTotalQuestions(questionData.totalQuestions);
        }
      }
    } catch (err) {
      console.error('Session hydration failed:', err);
      setError(err.message || 'Failed to load interview session questions.');
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  // Initial mount hydration
  useEffect(() => {
    hydrateSession();
  }, [hydrateSession]);

  /**
   * Submit candidate answer for current question
   * @param {string} answerText
   */
  const submitCurrentAnswer = useCallback(
    async (answerText) => {
      // Check Mutex
      if (submissionMutexRef.current || isSubmitting) {
        console.warn('Submission blocked: mutex active (already submitting answer)');
        return { success: false, reason: 'in_progress' };
      }

      if (!currentQuestion) {
        return { success: false, reason: 'no_active_question' };
      }

      // Lock Mutex immediately (Mitigation: timer race conditions)
      submissionMutexRef.current = true;
      setIsSubmitting(true);
      setError(null);

      const payload = {
        questionId: currentQuestion.questionId,
        text: (answerText || '').trim(),
      };

      try {
        const evalResult = await submitAnswer(sessionId, payload);

        setAnswersHistory((prev) => [
          ...prev,
          {
            ...payload,
            score: evalResult.score,
            feedback: evalResult.feedback,
            timestamp: new Date().toISOString(),
          },
        ]);

        if (evalResult.hasMore) {
          // Fetch next adaptive question
          const nextQ = await getNextQuestion(sessionId);
          if (nextQ && nextQ.hasMore) {
            setCurrentQuestion(nextQ);
            setQuestionNumber((prev) => prev + 1);
          } else {
            // No more questions, complete interview
            await completeInterview(sessionId);
            setIsCompleted(true);
            setCurrentQuestion(null);
          }
        } else {
          // Interview complete
          await completeInterview(sessionId);
          setIsCompleted(true);
          setCurrentQuestion(null);
        }

        return { success: true, result: evalResult };
      } catch (err) {
        console.error('Failed to submit answer:', err);
        setError(err.message || 'Failed to evaluate answer. Please try again.');
        return { success: false, error: err.message };
      } finally {
        // Unlock Mutex
        submissionMutexRef.current = false;
        setIsSubmitting(false);
      }
    },
    [sessionId, currentQuestion, isSubmitting]
  );

  /**
   * Conclude the interview manually
   */
  const finishInterviewSession = useCallback(async () => {
    try {
      setIsSubmitting(true);
      await completeInterview(sessionId);
      setIsCompleted(true);
    } catch (err) {
      console.warn('Complete interview request notice:', err);
      setIsCompleted(true);
    } finally {
      setIsSubmitting(false);
    }
  }, [sessionId]);

  return {
    sessionId,
    currentQuestion,
    questionNumber,
    totalQuestions,
    isLoading,
    isSubmitting,
    isCompleted,
    error,
    answersHistory,
    submitCurrentAnswer,
    finishInterviewSession,
    hydrateSession,
  };
}
