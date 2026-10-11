/**
 * Application Constants and Configurations
 */
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
export const USE_MOCK_API = import.meta.env.VITE_USE_MOCK_API === 'true';

// Integrity and Anti-Cheat Event Definitions
export const INTEGRITY_EVENTS = {
  VISIBILITY_CHANGE: 'visibilitychange',
  WINDOW_BLUR: 'blur',
  COPY: 'copy',
  PASTE: 'paste',
  CONTEXT_MENU: 'contextmenu',
  FULLSCREEN_EXIT: 'fullscreen_exit',
};

export const INTEGRITY_SEVERITIES = {
  LOW: 'low',
  MEDIUM: 'medium',
  HIGH: 'high',
};

// Event metadata mapping
export const INTEGRITY_EVENT_METADATA = {
  [INTEGRITY_EVENTS.VISIBILITY_CHANGE]: {
    label: 'Tab Switch / Backgrounded',
    severity: INTEGRITY_SEVERITIES.HIGH,
    penalty: 15,
    description: 'Candidate switched tabs or minimized the browser window',
  },
  [INTEGRITY_EVENTS.WINDOW_BLUR]: {
    label: 'Window Focus Lost',
    severity: INTEGRITY_SEVERITIES.MEDIUM,
    penalty: 10,
    description: 'Focus moved to an external application or monitor',
  },
  [INTEGRITY_EVENTS.COPY]: {
    label: 'Text Copied',
    severity: INTEGRITY_SEVERITIES.MEDIUM,
    penalty: 8,
    description: 'Question or content was copied to clipboard',
  },
  [INTEGRITY_EVENTS.PASTE]: {
    label: 'Content Pasted',
    severity: INTEGRITY_SEVERITIES.HIGH,
    penalty: 18,
    description: 'External text was pasted into the response field',
  },
  [INTEGRITY_EVENTS.CONTEXT_MENU]: {
    label: 'Right-Click / Context Menu',
    severity: INTEGRITY_SEVERITIES.LOW,
    penalty: 5,
    description: 'Candidate attempted to open the browser inspect/context menu',
  },
};

// Anti-cheat Flush Interval (Recommended: 5000ms)
export const INTEGRITY_FLUSH_INTERVAL_MS = 5000;

// Question Difficulty Levels
export const DIFFICULTY_LEVELS = {
  EASY: 'Easy',
  MEDIUM: 'Medium',
  HARD: 'Hard',
};

// Default Question Time Limits (seconds)
export const DEFAULT_QUESTION_TIME_LIMIT = 120; // 2 minutes

// Sample initial mock questions for fallback hydration and testing
export const MOCK_QUESTIONS = [
  {
    questionId: 'q-adaptive-01',
    category: 'System Architecture & Concurrency',
    difficulty: DIFFICULTY_LEVELS.MEDIUM,
    timeLimit: 120,
    text: 'How would you architect a distributed rate-limiting service capable of handling 500,000 requests per second across multi-region clusters with minimal latency overhead?',
    adaptiveHint: 'Focus on consensus algorithms, Redis Cluster vs Token Bucket algorithms, and cache invalidation strategies.',
  },
  {
    questionId: 'q-adaptive-02',
    category: 'Data Structures & Algorithmic Optimization',
    difficulty: DIFFICULTY_LEVELS.HARD,
    timeLimit: 150,
    text: 'Given an asynchronous stream of genomic sequences, describe an algorithm and data structure that finds the top-k most frequent k-mers in real-time under constrained memory limits (O(k)).',
    adaptiveHint: 'Consider Count-Min Sketch, Heavy Hitters, or Min-Heap coupled with hash maps.',
  },
  {
    questionId: 'q-adaptive-03',
    category: 'Database Internals & Transaction Isolation',
    difficulty: DIFFICULTY_LEVELS.MEDIUM,
    timeLimit: 120,
    text: 'Explain the difference between Optimistic Concurrency Control (OCC) and Pessimistic Locking in high-throughput transactional database systems. When does write-skew anomaly manifest?',
    adaptiveHint: 'Address Snapshot Isolation, MVCC, and write-skew in PostgreSQL or CockroachDB.',
  },
  {
    questionId: 'q-adaptive-04',
    category: 'Front-End Performance & Critical Rendering Path',
    difficulty: DIFFICULTY_LEVELS.EASY,
    timeLimit: 90,
    text: 'How do modern browser engines calculate Interaction to Next Paint (INP) and Largest Contentful Paint (LCP)? What architectural strategies eliminate main-thread bottlenecks?',
    adaptiveHint: 'Discuss Web Workers, CSS containment, layout thrashing, and requestIdleCallback.',
  },
];
