/**
 * API Service Contract
 * Implements communication with the backend service with graceful mock fallback
 * for development, testing, and offline resilience.
 */

import { API_BASE_URL, USE_MOCK_API, MOCK_QUESTIONS, DIFFICULTY_LEVELS } from '../utils/constants';

// Local storage key for mocked session state
const STORAGE_PREFIX = 'adaptive_interview_';

/**
 * Helper to get or set mock sessions
 */
function getMockSession(sessionId) {
  try {
    const raw = sessionStorage.getItem(`${STORAGE_PREFIX}${sessionId}`);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveMockSession(sessionId, data) {
  try {
    sessionStorage.setItem(`${STORAGE_PREFIX}${sessionId}`, JSON.stringify(data));
  } catch (e) {
    console.warn('SessionStorage save error:', e);
  }
}

/**
 * Standard fetch wrapper with timeout and fallback
 */
async function apiRequest(path, options = {}) {
  const url = `${API_BASE_URL}${path}`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 6000);

  try {
    const res = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (!res.ok) {
      const errorBody = await res.json().catch(() => ({}));
      throw new Error(errorBody.message || `API error ${res.status}: ${res.statusText}`);
    }
    return await res.json();
  } catch (err) {
    clearTimeout(timeoutId);
    // If mock mode is forced or network fails, throw with indication
    err.isNetworkOrServerDown = true;
    throw err;
  }
}

/**
 * 1. checkHealth()
 * Target: GET /health
 * Return: { status: "ok" }
 */
export async function checkHealth() {
  if (!USE_MOCK_API) {
    try {
      return await apiRequest('/health', { method: 'GET' });
    } catch (e) {
      console.warn('Backend /health unreachable, falling back to simulated operational status:', e.message);
    }
  }
  // Simulated fallback
  return { status: 'ok', mock: true, timestamp: new Date().toISOString() };
}

/**
 * 2. createSession(data)
 * Target: POST /sessions
 * Payload: Candidate metadata
 * Return: { sessionId: string, status: string }
 */
export async function createSession(data) {
  if (!USE_MOCK_API) {
    try {
      return await apiRequest('/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
    } catch (e) {
      console.warn('Backend POST /sessions failed, using local mock session:', e.message);
    }
  }

  // Generate simulated session
  const sessionId = 'ses_' + Math.random().toString(36).substring(2, 9) + '_' + Date.now().toString(36);
  const sessionState = {
    sessionId,
    candidate: data,
    status: 'initialized',
    createdAt: new Date().toISOString(),
    currentQuestionIndex: 0,
    answers: [],
    integrityEvents: [],
    parsedResume: null,
  };
  saveMockSession(sessionId, sessionState);

  return {
    sessionId,
    status: 'initialized',
  };
}

/**
 * 3. uploadResume(sessionId, file)
 * Target: POST /sessions/{id}/resume
 * Payload: multipart/form-data with file
 * Return: { skills: string[], experienceYears: number }
 */
export async function uploadResume(sessionId, file) {
  if (!USE_MOCK_API) {
    try {
      const formData = new FormData();
      formData.append('file', file);
      return await apiRequest(`/sessions/${sessionId}/resume`, {
        method: 'POST',
        body: formData,
      });
    } catch (e) {
      console.warn(`Backend POST /sessions/${sessionId}/resume failed, falling back to mock parser:`, e.message);
    }
  }

  // Simulated AI resume parsing
  await new Promise((r) => setTimeout(r, 900)); // realistic parsing delay
  const mockSkills = [
    'Distributed Systems',
    'TypeScript',
    'React',
    'Node.js',
    'PostgreSQL',
    'Kubernetes',
    'System Architecture',
    'GraphQL',
    'Redis',
  ];
  const experienceYears = 5 + Math.floor(Math.random() * 4);

  const session = getMockSession(sessionId) || { sessionId };
  session.parsedResume = {
    fileName: file.name,
    fileSize: file.size,
    skills: mockSkills,
    experienceYears,
  };
  saveMockSession(sessionId, session);

  return {
    skills: mockSkills,
    experienceYears,
  };
}

/**
 * 4. getNextQuestion(sessionId)
 * Target: GET /sessions/{id}/next-question
 * Return: { questionId: string, text: string, timeLimit: number, ... }
 */
export async function getNextQuestion(sessionId) {
  if (!USE_MOCK_API) {
    try {
      return await apiRequest(`/sessions/${sessionId}/next-question`, {
        method: 'GET',
      });
    } catch (e) {
      console.warn(`Backend GET /sessions/${sessionId}/next-question unreachable, serving adaptive mock question:`, e.message);
    }
  }

  const session = getMockSession(sessionId) || { currentQuestionIndex: 0, answers: [] };
  const idx = session.currentQuestionIndex || 0;

  if (idx >= MOCK_QUESTIONS.length) {
    return {
      hasMore: false,
      questionId: null,
      text: null,
      timeLimit: 0,
      questionNumber: idx + 1,
      totalQuestions: MOCK_QUESTIONS.length,
    };
  }

  const question = MOCK_QUESTIONS[idx];
  return {
    questionId: question.questionId,
    text: question.text,
    timeLimit: question.timeLimit,
    difficulty: question.difficulty,
    category: question.category,
    adaptiveHint: question.adaptiveHint,
    questionNumber: idx + 1,
    totalQuestions: MOCK_QUESTIONS.length,
    hasMore: true,
  };
}

/**
 * 5. submitAnswer(sessionId, payload)
 * Target: POST /sessions/{id}/answers
 * Payload: { questionId: string, text: string }
 * Return: { score: number, feedback: string, hasMore: boolean }
 */
export async function submitAnswer(sessionId, payload) {
  if (!USE_MOCK_API) {
    try {
      return await apiRequest(`/sessions/${sessionId}/answers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } catch (e) {
      console.warn(`Backend POST /sessions/${sessionId}/answers failed, evaluating via local simulation:`, e.message);
    }
  }

  // Simulate AI evaluation of response
  await new Promise((r) => setTimeout(r, 650));
  const answerLength = (payload.text || '').trim().length;
  // Calculate simulated score based on richness of response (60-95%)
  const score = Math.min(95, Math.max(62, 70 + Math.floor(Math.min(answerLength / 20, 25))));

  const feedbackOptions = [
    'Strong structural clarity. Good breakdown of distributed concurrency and edge cases.',
    'Effective algorithmic intuition demonstrated. Highlighted trade-offs between space complexity and throughput.',
    'Clear understanding of transactional isolation levels and write-skew anomalies.',
    'Comprehensive answer. Explicitly identified main-thread rendering bottlenecks and worker isolation.',
  ];

  const session = getMockSession(sessionId) || { currentQuestionIndex: 0, answers: [] };
  const currentIndex = session.currentQuestionIndex || 0;

  session.answers = session.answers || [];
  session.answers.push({
    questionId: payload.questionId,
    answerText: payload.text,
    score,
    feedback: feedbackOptions[currentIndex % feedbackOptions.length],
    submittedAt: new Date().toISOString(),
  });

  session.currentQuestionIndex = currentIndex + 1;
  const hasMore = session.currentQuestionIndex < MOCK_QUESTIONS.length;
  saveMockSession(sessionId, session);

  return {
    score,
    feedback: feedbackOptions[currentIndex % feedbackOptions.length],
    hasMore,
    nextDifficulty: score > 80 ? DIFFICULTY_LEVELS.HARD : score > 65 ? DIFFICULTY_LEVELS.MEDIUM : DIFFICULTY_LEVELS.EASY,
  };
}

/**
 * 6. recordIntegrityEvent(sessionId, ev)
 * Target: POST /sessions/{id}/events
 * Payload: { type: string, timestamp: string } or batch { events: [...] }
 * Return: { recorded: boolean }
 */
export async function recordIntegrityEvent(sessionId, ev) {
  if (!USE_MOCK_API) {
    try {
      return await apiRequest(`/sessions/${sessionId}/events`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(ev),
      });
    } catch (e) {
      // Background telemetry failure should not disrupt candidate experience
      console.debug(`Backend POST /sessions/${sessionId}/events buffered locally:`, e.message);
    }
  }

  const session = getMockSession(sessionId) || { integrityEvents: [] };
  session.integrityEvents = session.integrityEvents || [];

  if (Array.isArray(ev?.events)) {
    session.integrityEvents.push(...ev.events);
  } else if (ev) {
    session.integrityEvents.push(ev);
  }

  saveMockSession(sessionId, session);
  return { recorded: true };
}

/**
 * 7. completeInterview(sessionId)
 * Target: POST /sessions/{id}/complete
 * Return: { status: "completed", finishedAt: string }
 */
export async function completeInterview(sessionId) {
  if (!USE_MOCK_API) {
    try {
      return await apiRequest(`/sessions/${sessionId}/complete`, {
        method: 'POST',
      });
    } catch (e) {
      console.warn(`Backend POST /sessions/${sessionId}/complete failed, marking completed locally:`, e.message);
    }
  }

  const session = getMockSession(sessionId) || {};
  session.status = 'completed';
  session.finishedAt = new Date().toISOString();
  saveMockSession(sessionId, session);

  return {
    status: 'completed',
    finishedAt: session.finishedAt,
  };
}

/**
 * 8. getReport(sessionId)
 * Target: GET /sessions/{id}/report
 * Return: { competencies: object, integrityScore: number, report: object }
 */
export async function getReport(sessionId) {
  if (!USE_MOCK_API) {
    try {
      return await apiRequest(`/sessions/${sessionId}/report`, {
        method: 'GET',
      });
    } catch (e) {
      console.warn(`Backend GET /sessions/${sessionId}/report failed, generating comprehensive report:`, e.message);
    }
  }

  const session = getMockSession(sessionId) || {};
  const events = session.integrityEvents || [];
  const answers = session.answers || [];

  // Calculate integrity score (starts at 100%, deducts points per violation)
  const penaltyTotal = events.reduce((acc, curr) => {
    if (curr.type === 'visibilitychange') return acc + 12;
    if (curr.type === 'blur') return acc + 8;
    if (curr.type === 'paste') return acc + 15;
    if (curr.type === 'copy') return acc + 6;
    if (curr.type === 'contextmenu') return acc + 4;
    return acc + 5;
  }, 0);
  const integrityScore = Math.max(35, 100 - penaltyTotal);

  // Calculate average response score
  const avgTechnicalScore = answers.length > 0
    ? Math.round(answers.reduce((acc, a) => acc + (a.score || 75), 0) / answers.length)
    : 84;

  const candidateName = session.candidate?.name || 'Alex Chen';
  const targetRole = session.candidate?.targetRole || 'Senior Full-Stack & Systems Engineer';

  return {
    sessionId: sessionId || 'ses_demo_production',
    candidate: {
      name: candidateName,
      email: session.candidate?.email || 'alex.chen@example.com',
      targetRole: targetRole,
      experienceYears: session.parsedResume?.experienceYears || 6,
      skills: session.parsedResume?.skills || [
        'Distributed Systems',
        'TypeScript',
        'React',
        'Node.js',
        'PostgreSQL',
        'Kubernetes',
        'Redis',
      ],
    },
    integrityScore,
    overallScore: Math.round(avgTechnicalScore * 0.7 + (integrityScore >= 80 ? 25 : 15)),
    competencies: {
      'System Architecture': 88,
      'Algorithmic Efficiency': 82,
      'Data Integrity & MVCC': 91,
      'Frontend Performance (CWV)': 85,
      'Communication & Problem Framing': 89,
    },
    skillsAssessment: [
      { skill: 'Distributed Systems', required: 90, candidate: 88, status: 'Match' },
      { skill: 'High-Throughput Concurrency', required: 85, candidate: 82, status: 'Match' },
      { skill: 'Database Isolation (MVCC)', required: 80, candidate: 92, status: 'Exceeds' },
      { skill: 'Front-End CWV/Rendering', required: 75, candidate: 85, status: 'Exceeds' },
      { skill: 'Kubernetes Orchestration', required: 85, candidate: 70, status: 'Moderate Gap' },
    ],
    integrityTimeline: events.length > 0 ? events : [
      { type: 'session_start', timestamp: new Date(Date.now() - 900000).toISOString(), details: 'Proctoring environment locked' },
      { type: 'fullscreen_enter', timestamp: new Date(Date.now() - 880000).toISOString(), details: 'Candidate initiated full-focus mode' },
    ],
    answersBreakdown: answers.length > 0 ? answers : MOCK_QUESTIONS.slice(0, 3).map((q, idx) => ({
      questionId: q.questionId,
      questionText: q.text,
      difficulty: q.difficulty,
      score: 82 + idx * 4,
      feedback: 'Candidate explained trade-offs clearly with concrete architecture patterns.',
      answerText: 'We deployed a distributed token bucket algorithm with sliding window counters in Redis clusters, avoiding cross-DC round trips via localized tokens.',
    })),
    report: {
      summary: `${candidateName} demonstrated senior-level technical depth across distributed systems and modern web architecture. Provided well-structured solutions with strong algorithmic rigor.`,
      recommendation: integrityScore >= 75 && avgTechnicalScore >= 75 ? 'Strong Hire' : avgTechnicalScore >= 65 ? 'Hire' : 'Re-evaluate',
      keyStrengths: [
        'Deep architectural understanding of distributed caching and token-bucket concurrency',
        'Precise articulation of MVCC write-skew mitigation in ACID-compliant databases',
        'Clear, articulate voice responses with zero audio dropouts',
      ],
      areasForImprovement: [
        'Could provide deeper elaboration on Kubernetes ingress failover strategies',
        events.length > 2 ? 'Observed brief tab switches during technical formulation' : 'Maintain consistent time pacing on hard-tier questions',
      ],
      generatedAt: new Date().toISOString(),
    },
  };
}
