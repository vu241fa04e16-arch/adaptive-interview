# Adaptive AI: Intelligent Technical Screening & Anti-Cheat Interview Platform

A state-of-the-art, high-tech React frontend for adaptive AI technical interviews with real-time dynamic difficulty scaling, background anti-cheat telemetry tracking, multi-modal speech-to-text dictation, and comprehensive recruiter analytics.

---

## 📁 Repository Directory Structure

```text
frontend/
├── public/
│   ├── favicon.ico
│   └── index.html
├── src/
│   ├── assets/
│   │   ├── icons/
│   │   │   └── index.js
│   │   └── styles/
│   │       └── index.css
│   ├── components/
│   │   ├── common/
│   │   │   ├── Button.jsx
│   │   │   ├── Card.jsx
│   │   │   ├── Modal.jsx
│   │   │   ├── Navbar.jsx
│   │   │   ├── ProgressBar.jsx
│   │   │   └── Spinner.jsx
│   │   ├── interview/
│   │   │   ├── AudioRecorder.jsx
│   │   │   ├── IntegrityBadge.jsx
│   │   │   ├── QuestionCard.jsx
│   │   │   ├── ResponseBox.jsx
│   │   │   └── Timer.jsx
│   │   └── dashboard/
│   │       ├── CompetencyProfile.jsx
│   │       ├── IntegrityTimeline.jsx
│   │       ├── ReportSummary.jsx
│   │       ├── ScoreCard.jsx
│   │       └── SkillGapMap.jsx
│   ├── hooks/
│   │   ├── useAudioRecorder.js
│   │   ├── useIntegrity.js
│   │   ├── useInterviewSession.js
│   │   └── useTimer.js
│   ├── pages/
│   │   ├── Home.jsx
│   │   ├── Interview.jsx
│   │   ├── NotFound.jsx
│   │   ├── RecruiterDashboard.jsx
│   │   └── UploadResume.jsx
│   ├── services/
│   │   ├── api.js
│   │   └── speechToText.js
│   ├── utils/
│   │   ├── constants.js
│   │   ├── formatters.js
│   │   └── validators.js
│   ├── App.jsx
│   ├── main.jsx
│   └── routes.jsx
├── .env.example
├── .gitignore
├── package.json
├── tailwind.config.js
├── vite.config.js
└── README.md
```

---

## 🗺️ Application Routing and Page Responsibilities

| Route Path | Component Name | Description & Key Operations | Target API Endpoint |
| :--- | :--- | :--- | :--- |
| `/` | `Home.jsx` | Landing page introducing the AI interview system with live system health ping. | `GET /health` |
| `/upload` | `UploadResume.jsx` | Collects candidate details, validates files, and parses uploaded resume. | `POST /sessions`<br>`POST /sessions/{id}/resume` |
| `/interview/:sessionId` | `Interview.jsx` | Manages active question sequence, timer countdown, audio dictation, and anti-cheat tracking. | `GET /sessions/{id}/next-question`<br>`POST /sessions/{id}/answers`<br>`POST /sessions/{id}/complete` |
| `/dashboard/:sessionId` | `RecruiterDashboard.jsx` | Renders candidate scoring, anti-cheat breakdown timeline, and skill-gap visualization. | `GET /sessions/{id}/report` |
| `*` | `NotFound.jsx` | Graceful 404 fallback page for invalid session URLs with lookup input. | None |

---

## ⚙️ Custom Hooks Implementation Matrix

| Hook | File Location | Core Responsibility | Events / Output Handled |
| :--- | :--- | :--- | :--- |
| `useIntegrity` | `src/hooks/useIntegrity.js` | Anti-cheat tracking in background. Buffers and flushes telemetry in 5-second batches. | `visibilitychange`, `blur`, `copy`, `paste`, `contextmenu`. |
| `useInterviewSession` | `src/hooks/useInterviewSession.js` | Orchestrates question transitions, answer evaluation submissions, and completion state with mutex lock. | Current question ID, question text, difficulty tier, submission lock mutex. |
| `useTimer` | `src/hooks/useTimer.js` | Countdown timer per adaptive question with auto-submit trigger on expiration. | Remaining seconds, progress percentage, auto-submit trigger callback. |
| `useAudioRecorder` | `src/hooks/useAudioRecorder.js` | Manages microphone permissions, audio streaming, and speech-to-text conversion with fallback. | Recording state, audio blob, interim and final transcript text. |

---

## 🔌 API Service Contract (`src/services/api.js`)

| Exported Function | HTTP Method | Target Backend Path | Payload / Headers | Expected Return Data |
| :--- | :--- | :--- | :--- | :--- |
| `checkHealth()` | `GET` | `/health` | None | `{ status: "ok" }` |
| `createSession(data)` | `POST` | `/sessions` | JSON body with candidate metadata | `{ sessionId: string, status: string }` |
| `uploadResume(sessionId, file)` | `POST` | `/sessions/{id}/resume` | `multipart/form-data` with file | `{ skills: string[], experienceYears: number }` |
| `getNextQuestion(sessionId)` | `GET` | `/sessions/{id}/next-question` | URL param `sessionId` | `{ questionId: string, text: string, timeLimit: number }` |
| `submitAnswer(sessionId, payload)` | `POST` | `/sessions/{id}/answers` | `{ questionId: string, text: string }` | `{ score: number, feedback: string, hasMore: boolean }` |
| `recordIntegrityEvent(sessionId, ev)` | `POST` | `/sessions/{id}/events` | `{ type: string, timestamp: string }` | `{ recorded: boolean }` |
| `completeInterview(sessionId)` | `POST` | `/sessions/{id}/complete` | URL param `sessionId` | `{ status: "completed", finishedAt: string }` |
| `getReport(sessionId)` | `GET` | `/sessions/{id}/report` | URL param `sessionId` | `{ competencies: object, integrityScore: number, report: object }` |

*Note: `src/services/api.js` includes a seamless, stateful mock fallback mode that automatically activates when the backend is offline, allowing complete end-to-end testing without external servers.*

---

## 🛡️ Common Pitfalls and Mitigation Strategies

| Area | Risk / Pitfall | Mitigation Implemented |
| :--- | :--- | :--- |
| **Audio Transcription** | Web Speech API is unreliable on non-Chromium browsers and mobile devices. | Built a dual-mode response system: candidates can speak via Web Speech API / `MediaRecorder` or type directly in a fallback text area with full synchronization. |
| **Integrity Throttling** | Rapid tab switching or window resizing can trigger hundreds of HTTP requests per second. | Local event buffering in `useIntegrity.js` that batches telemetry events and flushes them to the backend in 5-second intervals. |
| **Timer Race Conditions** | Latency during answer upload can cause the timer to fire a second auto-submission. | Implemented an atomic `submissionMutexRef` and disabled input states in `useInterviewSession.js` and `useTimer.js` immediately upon expiration or submission initiation. |
| **Session Hydration** | Refreshing `/interview/:sessionId` clears component state and restarts flow. | Integrated automatic mount-time state hydration directly from `/sessions/{id}/next-question` inside `useInterviewSession.js`. |

---

## 🚀 Getting Started

### Prerequisites
- Node.js >= 18.0.0
- npm >= 9.0.0

### Installation
```bash
cd frontend
npm install
```

### Development Server
```bash
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

### Production Build
```bash
npm run build
```
