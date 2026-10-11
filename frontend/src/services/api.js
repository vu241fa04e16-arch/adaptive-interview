/**
 * API Service Contract
 * Connects the React frontend to the FastAPI backend, PostgreSQL database, and Ollama AI.
 */

import {
  API_BASE_URL,
  USE_MOCK_API,
  MOCK_QUESTIONS,
  DIFFICULTY_LEVELS,
} from '../utils/constants';

const STORAGE_PREFIX = 'adaptive_interview_';

// Default and AI-heavy timeout configurations (in milliseconds)
export const DEFAULT_TIMEOUT_MS = 60000;  // 60 seconds for standard requests
export const AI_TIMEOUT_MS = 120000;      // 120 seconds for Ollama LLM inference & transcription

/**
 * Standardized API request helper
 * Handles configurable timeouts, distinct timeout/network errors, HTTP 204, and JSON errors.
 */
async function apiRequest(path, options = {}) {
  // Normalize base URL and path to avoid duplicate or missing '/api'
  const base = (API_BASE_URL || 'http://localhost:8000').replace(/\/+$/, '');
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  const url = `${base}${cleanPath}`;

  const timeoutMs = options.timeoutMs || DEFAULT_TIMEOUT_MS;
  const controller = new AbortController();
  let timedOut = false;

  const timeoutId = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  try {
    const fetchOptions = {
      ...options,
      signal: controller.signal,
    };
    delete fetchOptions.timeoutMs;

    const res = await fetch(url, fetchOptions);

    if (!res.ok) {
      const errorBody = await res.json().catch(() => ({}));
      const message =
        errorBody.detail ||
        errorBody.message ||
        `HTTP Error ${res.status}: ${res.statusText || 'Request failed'}`;
      const err = new Error(typeof message === 'object' ? JSON.stringify(message) : message);
      err.status = res.status;
      err.details = errorBody;
      throw err;
    }

    if (res.status === 204) return null;
    return await res.json();
  } catch (err) {
    if (timedOut) {
      const timeoutErr = new Error(
        `Request to ${cleanPath} timed out after ${timeoutMs / 1000}s while waiting for backend AI response.`
      );
      timeoutErr.isTimeout = true;
      throw timeoutErr;
    }
    if (err.name === 'AbortError') {
      const abortErr = new Error(`Request to ${cleanPath} was aborted.`);
      abortErr.isAborted = true;
      throw abortErr;
    }
    if (err instanceof TypeError && err.message.includes('fetch')) {
      const netErr = new Error(
        `Unable to reach interview backend at ${base}. Please verify the FastAPI server is running.`
      );
      netErr.isNetworkError = true;
      throw netErr;
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Mock session helpers (active ONLY when USE_MOCK_API is explicitly true)
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
 * 1. Health check
 * GET /api/health
 */
export async function checkHealth() {
  if (!USE_MOCK_API) {
    const data = await apiRequest('/api/health');
    return {
      ...data,
      status: (data.status === 'healthy' || data.status === 'ok') ? 'ok' : data.status,
      mock: false,
    };
  }

  return {
    status: 'ok',
    mock: true,
    timestamp: new Date().toISOString(),
  };
}

/**
 * 2. Create interview session
 * POST /api/sessions
 */
export async function createSession(data) {
  if (!USE_MOCK_API) {
    const payload = {
      candidate_name: data.candidate_name || data.name || '',
      candidate_email: data.candidate_email || data.email || '',
      target_role: data.target_role || data.targetRole || '',
      target_level: data.target_level || data.targetLevel || 'Senior',
      time_limit_minutes: data.time_limit_minutes || data.timeLimitMinutes || 45,
    };
    if (data.job_description || data.jobDescription) {
      payload.job_description = data.job_description || data.jobDescription;
    }

    const sessionRes = await apiRequest('/api/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    return {
      ...sessionRes,
      sessionId: sessionRes.sessionId,
      status: sessionRes.status || 'initialized',
    };
  }

  const sessionId =
    'ses_' +
    Math.random().toString(36).substring(2, 9) +
    '_' +
    Date.now().toString(36);

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
  return { sessionId, status: 'initialized' };
}

/**
 * 3. Upload and parse resume
 * POST /api/sessions/{sessionId}/resume
 */
export async function uploadResume(sessionId, file) {
  if (!USE_MOCK_API) {
    const formData = new FormData();
    formData.append('file', file);

    const data = await apiRequest(
      `/api/sessions/${encodeURIComponent(sessionId)}/resume`,
      {
        method: 'POST',
        body: formData,
        timeoutMs: AI_TIMEOUT_MS,
      }
    );

    // Extract flat skills and experienceYears from claimed_skills for UI
    const claimed = Array.isArray(data.claimed_skills) ? data.claimed_skills : [];
    const skillsList = data.skills && data.skills.length > 0
      ? data.skills
      : claimed.map((s) => (typeof s === 'string' ? s : s.name));

    const yearsList = claimed
      .map((s) => (typeof s === 'object' ? s.claimed_experience_years : null))
      .filter((y) => typeof y === 'number');
    const calcYears = data.experienceYears != null
      ? data.experienceYears
      : (yearsList.length > 0 ? Math.max(...yearsList) : 5);

    return {
      ...data,
      skills: skillsList,
      experienceYears: calcYears,
    };
  }

  await new Promise((resolve) => setTimeout(resolve, 900));
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

  return { skills: mockSkills, experienceYears };
}

/**
 * 4. Get next interview question
 * GET /api/sessions/{sessionId}/next-question
 */
export async function getNextQuestion(sessionId) {
  if (!USE_MOCK_API) {
    const data = await apiRequest(
      `/api/sessions/${encodeURIComponent(sessionId)}/next-question`,
      {
        timeoutMs: AI_TIMEOUT_MS,
      }
    );

    if (!data) {
      return { hasMore: false, questionId: null, text: null };
    }

    const currentSeq = data.sequence_number || 1;
    const totalQuestions = 4;
    const hasMore = data.has_more !== undefined ? data.has_more : (currentSeq <= totalQuestions);

    const diffRaw = (data.difficulty || 'Medium').toLowerCase();
    const diffMap = {
      easy: DIFFICULTY_LEVELS.EASY || 'Easy',
      medium: DIFFICULTY_LEVELS.MEDIUM || 'Medium',
      hard: DIFFICULTY_LEVELS.HARD || 'Hard',
      intermediate: DIFFICULTY_LEVELS.MEDIUM || 'Medium',
      advanced: DIFFICULTY_LEVELS.HARD || 'Hard',
      expert: DIFFICULTY_LEVELS.HARD || 'Hard',
    };
    const difficulty = diffMap[diffRaw] || data.difficulty || 'Medium';

    const criteriaList = Array.isArray(data.key_evaluation_criteria)
      ? data.key_evaluation_criteria
      : [];
    const adaptiveHint = criteriaList.length > 0
      ? criteriaList.join(' • ')
      : (data.adaptation_context?.reasoning || '');

    return {
      ...data,
      questionId: data.question_id || data.questionId,
      text: data.question_text || data.text,
      category: data.competency || data.category || 'System Architecture',
      difficulty,
      timeLimit: data.time_remaining_seconds || 120,
      adaptiveHint,
      questionNumber: currentSeq,
      totalQuestions,
      hasMore,
    };
  }

  const session = getMockSession(sessionId) || {
    currentQuestionIndex: 0,
    answers: [],
  };
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
 * 5. Submit an interview answer
 * POST /api/sessions/{sessionId}/answers
 */
export async function submitAnswer(sessionId, payload) {
  if (!USE_MOCK_API) {
    const backendPayload = {
      question_id: payload.question_id || payload.questionId,
      answer_text: (payload.answer_text || payload.text || '').trim(),
    };
    if (payload.time_taken_seconds != null || payload.timeTakenSeconds != null) {
      backendPayload.time_taken_seconds =
        payload.time_taken_seconds != null
          ? payload.time_taken_seconds
          : payload.timeTakenSeconds;
    }

    const data = await apiRequest(
      `/api/sessions/${encodeURIComponent(sessionId)}/answers`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(backendPayload),
        timeoutMs: AI_TIMEOUT_MS,
      }
    );

    // Normalize score: backend returns 0.0 - 10.0, UI uses percentage scale 0-100
    const normalizedScore = data.score != null ? Math.round(data.score * 10) : 75;

    return {
      ...data,
      score: normalizedScore,
      rawScore: data.score,
      feedback: data.feedback || '',
      hasMore: data.has_more !== undefined ? data.has_more : true,
    };
  }

  await new Promise((resolve) => setTimeout(resolve, 650));
  const answerLength = (payload.text || '').trim().length;
  const score = Math.min(
    95,
    Math.max(62, 70 + Math.floor(Math.min(answerLength / 20, 25)))
  );

  const feedbackOptions = [
    'Strong structural clarity. Good breakdown of concurrency and edge cases.',
    'Effective algorithmic intuition. Trade-offs between space complexity and throughput were identified.',
    'Clear understanding of transactional isolation and database consistency.',
    'Comprehensive answer with clear technical reasoning.',
  ];

  const session = getMockSession(sessionId) || {
    currentQuestionIndex: 0,
    answers: [],
  };

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
    nextDifficulty:
      score > 80
        ? DIFFICULTY_LEVELS.HARD
        : score > 65
          ? DIFFICULTY_LEVELS.MEDIUM
          : DIFFICULTY_LEVELS.EASY,
  };
}

/**
 * 6. Record integrity events
 * POST /api/sessions/{sessionId}/events
 */
export async function recordIntegrityEvent(sessionId, ev) {
  if (!USE_MOCK_API) {
    let payload = {};
    if (ev && Array.isArray(ev.events)) {
      payload = {
        events: ev.events.map((e) => ({
          event_type: e.event_type || e.type || 'HEARTBEAT',
          timestamp: e.timestamp || new Date().toISOString(),
          event_data: e.event_data || e.details ? (typeof e.details === 'object' ? e.details : { details: e.details }) : {},
        })),
      };
    } else if (ev) {
      payload = {
        event_type: ev.event_type || ev.type || 'HEARTBEAT',
        timestamp: ev.timestamp || new Date().toISOString(),
        event_data: ev.event_data || ev.details ? (typeof ev.details === 'object' ? ev.details : { details: ev.details }) : {},
      };
    }

    return apiRequest(
      `/api/sessions/${encodeURIComponent(sessionId)}/events`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }
    );
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
 * 7. Complete interview
 * POST /api/sessions/{sessionId}/complete
 */
export async function completeInterview(sessionId) {
  if (!USE_MOCK_API) {
    return apiRequest(
      `/api/sessions/${encodeURIComponent(sessionId)}/complete`,
      {
        method: 'POST',
      }
    );
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
 * 8. Get interview report
 * GET /api/sessions/{sessionId}/report
 */
export async function getReport(sessionId) {
  if (!USE_MOCK_API) {
    const data = await apiRequest(
      `/api/sessions/${encodeURIComponent(sessionId)}/report`,
      {
        timeoutMs: AI_TIMEOUT_MS,
      }
    );

    // Map candidate information
    const candidateName = data.candidate_name || 'Candidate';
    const targetRole = data.target_role
      ? `${data.target_role} (${data.target_level || 'Senior'})`
      : 'Engineering Candidate';

    // Normalize overall scores
    const rawScore = data.summary?.overall_average_score;
    const overallScore = rawScore != null ? Math.round(rawScore * 10) : 80;

    const riskScore = data.summary?.integrity?.risk_score || 0;
    const integrityScore = Math.max(30, Math.min(100, Math.round(100 - riskScore * 10)));

    // Map competencies array into name -> score percentage object for CompetencyProfile
    const competenciesObj = {};
    if (Array.isArray(data.competencies)) {
      data.competencies.forEach((c) => {
        const cScore = c.average_score != null ? Math.round(c.average_score * 10) : 75;
        competenciesObj[c.competency] = cScore;
      });
    }

    // Map skills assessment for SkillGapMap
    let skillsAssessment = [];
    if (data.skill_gap_analysis && Array.isArray(data.skill_gap_analysis.required_skills)) {
      skillsAssessment = data.skill_gap_analysis.required_skills.map((item) => {
        let status = 'Moderate Gap';
        let candidateScore = 50;
        if (item.classification === 'demonstrated') {
          status = 'Exceeds';
          candidateScore = 90;
        } else if (item.classification === 'claimed_but_unvalidated') {
          status = 'Match';
          candidateScore = 75;
        } else if (item.classification === 'not_demonstrated') {
          status = 'Significant Gap';
          candidateScore = 35;
        }
        return {
          skill: item.skill_name,
          required: item.importance?.toLowerCase() === 'required' ? 85 : 70,
          candidate: candidateScore,
          status,
        };
      });
    }

    // If skillsAssessment is empty, derive from claimed skills and competencies
    if (skillsAssessment.length === 0 && Array.isArray(data.claimed_skills)) {
      skillsAssessment = data.claimed_skills.slice(0, 5).map((s) => {
        const name = typeof s === 'string' ? s : s.name;
        const demonstrated = (data.demonstrated_skills || []).includes(name);
        return {
          skill: name,
          required: 80,
          candidate: demonstrated ? 88 : 70,
          status: demonstrated ? 'Match' : 'Unvalidated',
        };
      });
    }

    // Map integrity timeline
    const rawTimeline = data.summary?.integrity?.timeline || [];
    const integrityTimeline = rawTimeline.map((ev) => ({
      type: (ev.event_type || 'flag').toLowerCase(),
      label: ev.event_type || 'Telemetry Event',
      severity: ev.severity || 'info',
      timestamp: ev.timestamp,
      details: ev.description || 'Observed telemetry event',
    }));

    // Map questions and answers breakdown for ReportSummary
    const answersBreakdown = (data.questions || []).map((q, idx) => ({
      questionId: q.question_id,
      questionText: q.question_text,
      difficulty: q.difficulty,
      score: q.answer?.score != null ? Math.round(q.answer.score * 10) : 0,
      feedback: q.answer?.feedback || 'Awaiting evaluation',
      answerText: q.answer?.answer_text || 'No response recorded',
    }));

    // Recommendation formatting
    const recMap = {
      hire: 'Strong Hire',
      lean_hire: 'Hire',
      borderline: 'Borderline',
      do_not_hire: 'Do Not Hire',
    };
    const recommendation = recMap[data.decision_recommendation] || data.decision_recommendation || 'Hire';

    const keyStrengths = (data.competencies || []).flatMap((c) => c.strengths || []).slice(0, 4);
    const areasForImprovement = (data.competencies || [])
      .flatMap((c) => c.areas_for_improvement || [])
      .slice(0, 4);

    return {
      sessionId: data.sessionId,
      candidate: {
        name: candidateName,
        email: data.candidate_email,
        targetRole,
        experienceYears: 5,
        skills: (data.claimed_skills || []).map((s) => (typeof s === 'string' ? s : s.name)),
      },
      overallScore,
      integrityScore,
      competencies: competenciesObj,
      skillsAssessment,
      integrityTimeline,
      answersBreakdown,
      report: {
        summary: data.overall_assessment || data.candidate_overview || 'Comprehensive evaluation completed.',
        recommendation,
        keyStrengths: keyStrengths.length > 0 ? keyStrengths : ['Demonstrated technical proficiency in core engineering areas.'],
        areasForImprovement: areasForImprovement.length > 0 ? areasForImprovement : ['Deepen edge-case explanations during system design.'],
        generatedAt: data.completed_at || data.created_at || new Date().toISOString(),
      },
      rawReport: data,
    };
  }

  // Simulated fallback report for deliberate mock testing
  const session = getMockSession(sessionId) || {};
  const events = session.integrityEvents || [];
  const answers = session.answers || [];

  const penaltyTotal = events.reduce((acc, curr) => {
    if (curr.type === 'visibilitychange') return acc + 12;
    if (curr.type === 'blur') return acc + 8;
    if (curr.type === 'paste') return acc + 15;
    if (curr.type === 'copy') return acc + 6;
    if (curr.type === 'contextmenu') return acc + 4;
    return acc + 5;
  }, 0);

  const integrityScore = Math.max(35, 100 - penaltyTotal);
  const avgTechnicalScore =
    answers.length > 0
      ? Math.round(
          answers.reduce((acc, answer) => acc + (answer.score || 75), 0) /
            answers.length
        )
      : 84;

  const candidateName = session.candidate?.name || 'Alex Chen';
  const targetRole =
    session.candidate?.targetRole ||
    'Senior Full-Stack & Systems Engineer';

  return {
    sessionId: sessionId || 'ses_demo_production',
    candidate: {
      name: candidateName,
      email: session.candidate?.email || 'alex.chen@example.com',
      targetRole,
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
    overallScore: Math.round(
      avgTechnicalScore * 0.7 + (integrityScore >= 80 ? 25 : 15)
    ),
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
    integrityTimeline:
      events.length > 0
        ? events
        : [
            {
              type: 'session_start',
              timestamp: new Date(Date.now() - 900000).toISOString(),
              details: 'Proctoring environment locked',
            },
            {
              type: 'fullscreen_enter',
              timestamp: new Date(Date.now() - 880000).toISOString(),
              details: 'Candidate initiated full-focus mode',
            },
          ],
    answersBreakdown:
      answers.length > 0
        ? answers
        : MOCK_QUESTIONS.slice(0, 3).map((question, idx) => ({
            questionId: question.questionId,
            questionText: question.text,
            difficulty: question.difficulty,
            score: 82 + idx * 4,
            feedback: 'Candidate explained trade-offs clearly with concrete examples.',
            answerText: 'Example response for a mock interview question.',
          })),
    report: {
      summary: `${candidateName} demonstrated technical knowledge in the selected interview areas.`,
      recommendation:
        integrityScore >= 75 && avgTechnicalScore >= 75
          ? 'Strong Hire'
          : avgTechnicalScore >= 65
            ? 'Hire'
            : 'Re-evaluate',
      keyStrengths: [
        'Clear technical explanations',
        'Structured problem-solving',
        'Understanding of architecture trade-offs',
      ],
      areasForImprovement: [
        'Provide more detailed examples',
        'Explain trade-offs and edge cases',
      ],
      generatedAt: new Date().toISOString(),
    },
  };
}

/**
 * 9. Submit audio answer via Speech-to-Text
 * POST /api/sessions/{sessionId}/answers/audio
 */
export async function submitAudioAnswer(sessionId, questionIdOrPayload, maybeFile, timeTakenSeconds) {
  let questionId = questionIdOrPayload;
  let file = maybeFile;
  let time = timeTakenSeconds;

  if (typeof questionIdOrPayload === 'object' && !(questionIdOrPayload instanceof Blob)) {
    questionId = questionIdOrPayload.questionId || questionIdOrPayload.question_id;
    file = questionIdOrPayload.file || questionIdOrPayload.audioBlob;
    time = questionIdOrPayload.timeTakenSeconds || questionIdOrPayload.time_taken_seconds;
  } else if (questionIdOrPayload instanceof Blob && !maybeFile) {
    file = questionIdOrPayload;
    questionId = null;
  }

  const formData = new FormData();
  if (file) {
    const fileName = file.name || 'recording.webm';
    formData.append('file', file, fileName);
  }
  if (questionId) {
    formData.append('question_id', questionId);
  }
  if (time != null) {
    formData.append('time_taken_seconds', String(time));
  }

  return apiRequest(
    `/api/sessions/${encodeURIComponent(sessionId)}/answers/audio`,
    {
      method: 'POST',
      body: formData,
      timeoutMs: AI_TIMEOUT_MS,
    }
  );
}

/**
 * 10. Submit job description
 * POST /api/sessions/{sessionId}/job-description
 */
export async function submitJobDescription(sessionId, data) {
  const jobDescriptionText =
    typeof data === 'string'
      ? data
      : (data?.job_description || data?.jobDescription || '');

  return apiRequest(
    `/api/sessions/${encodeURIComponent(sessionId)}/job-description`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_description: jobDescriptionText }),
      timeoutMs: AI_TIMEOUT_MS,
    }
  );
}

/**
 * 11. Retrieve skill gap analysis
 * GET /api/sessions/{sessionId}/skill-gap
 */
export async function getSkillGap(sessionId) {
  const data = await apiRequest(
    `/api/sessions/${encodeURIComponent(sessionId)}/skill-gap`,
    {
      timeoutMs: AI_TIMEOUT_MS,
    }
  );

  if (!data) return data;

  const skillsAssessment = (data.required_skills || []).map((item) => {
    let status = 'Moderate Gap';
    let candidate = 50;
    if (item.classification === 'demonstrated') {
      status = 'Exceeds';
      candidate = 90;
    } else if (item.classification === 'claimed_but_unvalidated') {
      status = 'Match';
      candidate = 75;
    } else if (item.classification === 'not_demonstrated') {
      status = 'Significant Gap';
      candidate = 35;
    }
    return {
      skill: item.skill_name,
      required: item.importance?.toLowerCase() === 'required' ? 85 : 70,
      candidate,
      status,
      classification: item.classification,
      evidence: item.evidence,
      explanation: item.explanation,
    };
  });

  return {
    ...data,
    skillsAssessment,
  };
}
