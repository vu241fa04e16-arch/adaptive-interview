from datetime import datetime, timezone
from typing import Optional
import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import (
    AsyncOllamaClient,
    get_adaptive_engine,
    get_db,
    get_evaluation_service,
    get_ollama_client,
    get_report_service,
    get_resume_service,
    get_skill_gap_service,
    get_transcription_service,
)
from app.config import get_settings
from app.core.exceptions import InvalidSessionStateException, ResourceNotFoundException
from app.core.logging import logger
from app.database import check_database_health
from app.models.answer import Answer
from app.models.event import SessionEvent
from app.models.question import Question
from app.models.resume import ResumeAnalysis
from app.models.session import InterviewSession
from app.schemas.answer import AnswerResponse, AnswerSubmitRequest, AudioAnswerResponse
from app.schemas.event import EventCreateRequest, EventResponse, InterviewProgress
from app.schemas.health import DatabaseHealth, HealthResponse, OllamaHealth
from app.schemas.question import QuestionResponse
from app.schemas.report import InterviewReportResponse, SessionCompleteResponse
from app.schemas.resume import (
    ClaimedSkill,
    ProjectSummary,
    ResumeUploadResponse,
)
from app.schemas.session import SessionCreateRequest, SessionResponse
from app.schemas.skill_gap import JobDescriptionSubmitRequest, SkillGapReport
from app.services.adaptive_engine import AdaptiveEngine
from app.services.evaluation_service import EvaluationService
from app.services.report_service import ReportService
from app.services.resume_service import ResumeService
from app.services.skill_gap_service import SkillGapService
from app.services.transcription_service import TranscriptionService

router = APIRouter(prefix="/api", tags=["Interview Intelligence"])
settings = get_settings()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System Health and Readiness Probe",
    description="Probes PostgreSQL database connectivity and local Ollama model readiness.",
)
async def get_health(
    ollama_client: AsyncOllamaClient = Depends(get_ollama_client),
) -> HealthResponse:
    """Probes separate application, database, and Ollama health."""
    db_info = await check_database_health()
    ollama_info = await ollama_client.check_health()

    # Determine overall status
    is_db_ok = db_info.get("status") == "connected"
    is_ollama_ok = ollama_info.get("status") == "available" and ollama_info.get("model_available", False)

    if is_db_ok and is_ollama_ok:
        overall_status = "healthy"
    elif is_db_ok and not is_ollama_ok:
        overall_status = "degraded"
    else:
        overall_status = "unhealthy"

    return HealthResponse(
        status=overall_status,
        app=settings.PROJECT_NAME,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc),
        database=DatabaseHealth(
            status=db_info.get("status", "disconnected"),
            dialect=db_info.get("dialect"),
            driver=db_info.get("driver"),
            error=db_info.get("error"),
        ),
        ollama=OllamaHealth(
            status=ollama_info.get("status", "unavailable"),
            base_url=ollama_info.get("base_url", settings.OLLAMA_BASE_URL),
            configured_model=ollama_info.get("configured_model", settings.OLLAMA_MODEL),
            model_available=ollama_info.get("model_available", False),
            available_models=ollama_info.get("available_models"),
            error=ollama_info.get("error"),
        ),
    )


@router.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initialize Interview Session",
    description="Initializes a new interview session record in PostgreSQL.",
)
async def create_session(
    payload: SessionCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """Creates a new interview session and initializes empty competency matrix and optional job description."""
    initial_comp_state: Dict[str, Any] = {}
    if payload.job_description and payload.job_description.strip():
        initial_comp_state["job_description"] = payload.job_description.strip()

    session = InterviewSession(
        candidate_name=payload.candidate_name,
        candidate_email=str(payload.candidate_email),
        target_role=payload.target_role,
        target_level=payload.target_level,
        status="created",
        time_limit_minutes=payload.time_limit_minutes,
        competency_state=initial_comp_state,
    )

    db.add(session)
    await db.commit()
    await db.refresh(session)

    logger.info(f"Initialized interview session {session.id} for candidate {session.candidate_name} ({session.target_role})")

    return SessionResponse(
        sessionId=str(session.id),
        candidate_name=session.candidate_name,
        candidate_email=session.candidate_email,
        target_role=session.target_role,
        target_level=session.target_level,
        status=session.status,
        time_limit_minutes=session.time_limit_minutes,
        created_at=session.created_at,
        resume_uploaded=False,
        job_description_provided=bool(payload.job_description and payload.job_description.strip()),
    )


@router.post(
    "/sessions/{sessionId}/resume",
    response_model=ResumeUploadResponse,
    summary="Upload & Parse Candidate Resume",
    description="Uploads a PDF or DOCX resume, securely stores it, and triggers Ollama skill extraction.",
)
async def upload_resume(
    sessionId: str,
    file: UploadFile = File(..., description="PDF or DOCX resume file"),
    db: AsyncSession = Depends(get_db),
    resume_service: ResumeService = Depends(get_resume_service),
) -> ResumeUploadResponse:
    """Validates and analyzes candidate resume, extracting claimed skills and suggested focus areas."""
    # 1. Validate UUID format
    try:
        session_uuid = uuid.UUID(sessionId)
    except (ValueError, AttributeError):
        raise InvalidSessionStateException(
            message=f"Invalid sessionId format '{sessionId}'. Must be a valid UUID.",
            details={"sessionId": sessionId},
        )

    # 2. Retrieve session from database
    result = await db.execute(
        select(InterviewSession)
        .options(selectinload(InterviewSession.resume_analysis))
        .where(InterviewSession.id == session_uuid)
    )
    session = result.scalar_one_or_none()

    if session is None:
        raise ResourceNotFoundException(
            resource="InterviewSession",
            resource_id=sessionId,
        )

    # 3. Validate session state
    if session.status in ["completed", "abandoned"]:
        raise InvalidSessionStateException(
            message=f"Cannot upload resume to a session that is already '{session.status}'.",
            details={"sessionId": sessionId, "status": session.status},
        )

    # 4. Validate file, compute SHA-256 hash, and enforce limits
    content, clean_filename, file_hash = await resume_service.validate_and_read_upload(file)

    # 5. Handle duplicate upload deliberately
    if session.resume_analysis and session.resume_analysis.file_hash == file_hash:
        logger.info(f"Duplicate identical resume upload detected for session {sessionId} (SHA256: {file_hash[:12]}...). Returning existing analysis.")
        ra = session.resume_analysis
        return ResumeUploadResponse(
            sessionId=sessionId,
            resume_parsed=True,
            file_name=ra.file_name,
            file_hash=ra.file_hash,
            file_size_bytes=ra.file_size_bytes,
            candidate_overview=ra.candidate_overview,
            claimed_skills=[ClaimedSkill(**s) for s in ra.claimed_skills],
            projects=[ProjectSummary(**p) for p in ra.projects],
            suggested_focus_areas=ra.suggested_focus_areas,
            message="Identical resume already analyzed for this session. Retrieved existing profile.",
        )

    # 6. Extract text content
    parsed_text = resume_service.extract_text(content, clean_filename)

    # 7. Secure storage
    saved_path = resume_service.save_upload_safely(
        session_id=sessionId,
        filename=clean_filename,
        file_hash=file_hash,
        content=content,
    )

    # 8. Real Ollama extraction
    logger.info(f"Initiating Ollama resume skill extraction for session {sessionId} (Chars: {len(parsed_text)})")
    analysis = await resume_service.analyze_resume_with_ollama(
        resume_text=parsed_text,
        target_role=session.target_role,
        target_level=session.target_level,
    )

    # 9. Separate claimed skills from verified state in competency_state
    competency_state = {
        "candidate_overview": analysis.candidate_overview,
        "suggested_focus_areas": analysis.suggested_focus_areas,
        "claimed_skills": [
            {
                "name": s.name,
                "claimed_years": s.claimed_experience_years,
                "claimed_proficiency": s.claimed_proficiency,
                "verified": False,
                "demonstrated_score": None,
                "evaluation_notes": [],
            }
            for s in analysis.claimed_skills
        ],
    }
    session.competency_state = competency_state

    # 10. Persist or update ResumeAnalysis in PostgreSQL
    claimed_skills_dicts = [s.model_dump() for s in analysis.claimed_skills]
    projects_dicts = [p.model_dump() for p in analysis.projects]

    if session.resume_analysis:
        session.resume_analysis.file_name = clean_filename
        session.resume_analysis.file_hash = file_hash
        session.resume_analysis.file_size_bytes = len(content)
        session.resume_analysis.file_path = saved_path
        session.resume_analysis.parsed_text_length = len(parsed_text)
        session.resume_analysis.parsed_text = parsed_text
        session.resume_analysis.candidate_overview = analysis.candidate_overview
        session.resume_analysis.claimed_skills = claimed_skills_dicts
        session.resume_analysis.projects = projects_dicts
        session.resume_analysis.suggested_focus_areas = analysis.suggested_focus_areas
        session.resume_analysis.raw_model_output = analysis.model_dump()
    else:
        new_analysis = ResumeAnalysis(
            session_id=session.id,
            file_name=clean_filename,
            file_hash=file_hash,
            file_size_bytes=len(content),
            file_path=saved_path,
            parsed_text_length=len(parsed_text),
            parsed_text=parsed_text,
            candidate_overview=analysis.candidate_overview,
            claimed_skills=claimed_skills_dicts,
            projects=projects_dicts,
            suggested_focus_areas=analysis.suggested_focus_areas,
            raw_model_output=analysis.model_dump(),
        )
        db.add(new_analysis)

    await db.commit()
    logger.info(f"Resume analysis successfully stored for session {sessionId}. Extracted {len(analysis.claimed_skills)} skills and {len(analysis.projects)} projects.")

    flat_skills = [s.name for s in analysis.claimed_skills]
    years_list = [s.claimed_experience_years for s in analysis.claimed_skills if s.claimed_experience_years is not None]
    calc_years = max(years_list) if years_list else 5.0

    return ResumeUploadResponse(
        sessionId=sessionId,
        resume_parsed=True,
        file_name=clean_filename,
        file_hash=file_hash,
        file_size_bytes=len(content),
        candidate_overview=analysis.candidate_overview,
        claimed_skills=analysis.claimed_skills,
        projects=analysis.projects,
        suggested_focus_areas=analysis.suggested_focus_areas,
        skills=flat_skills,
        experienceYears=calc_years,
        message="Resume analyzed successfully. Interview competency profile primed.",
    )


@router.post(
    "/sessions/{sessionId}/job-description",
    response_model=SkillGapReport,
    status_code=status.HTTP_200_OK,
    summary="Ingest Job Description & Analyze Skill Gap",
    description="Accepts technical job description, extracts required competencies, compares against candidate claims/answers, and persists gap analysis.",
)
async def submit_job_description(
    sessionId: str,
    payload: JobDescriptionSubmitRequest,
    db: AsyncSession = Depends(get_db),
    skill_gap_service: SkillGapService = Depends(get_skill_gap_service),
) -> SkillGapReport:
    """Extracts required skills from JD, evaluates against resume claims and interview evidence, persists in session."""
    try:
        session_uuid = uuid.UUID(sessionId)
    except (ValueError, AttributeError):
        raise InvalidSessionStateException(
            message=f"Invalid sessionId format '{sessionId}'. Must be a valid UUID.",
            details={"sessionId": sessionId},
        )

    result = await db.execute(
        select(InterviewSession)
        .options(
            selectinload(InterviewSession.resume_analysis),
            selectinload(InterviewSession.questions),
            selectinload(InterviewSession.answers),
        )
        .where(InterviewSession.id == session_uuid)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise ResourceNotFoundException(
            resource="InterviewSession",
            resource_id=sessionId,
        )

    return await skill_gap_service.analyze_and_persist_gap(
        session=session,
        job_description=payload.job_description,
        db=db,
    )


@router.get(
    "/sessions/{sessionId}/skill-gap",
    response_model=SkillGapReport,
    status_code=status.HTTP_200_OK,
    summary="Retrieve Resume-JD Skill Gap Analysis",
    description="Returns 4-way classification of required skills (demonstrated, claimed_but_unvalidated, not_demonstrated, not_assessed) with evidence.",
)
async def get_skill_gap(
    sessionId: str,
    db: AsyncSession = Depends(get_db),
    skill_gap_service: SkillGapService = Depends(get_skill_gap_service),
) -> SkillGapReport:
    """Returns the comprehensive skill gap report comparing role requirements against candidate resume and answers."""
    try:
        session_uuid = uuid.UUID(sessionId)
    except (ValueError, AttributeError):
        raise InvalidSessionStateException(
            message=f"Invalid sessionId format '{sessionId}'. Must be a valid UUID.",
            details={"sessionId": sessionId},
        )

    result = await db.execute(
        select(InterviewSession)
        .options(
            selectinload(InterviewSession.resume_analysis),
            selectinload(InterviewSession.questions),
            selectinload(InterviewSession.answers),
        )
        .where(InterviewSession.id == session_uuid)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise ResourceNotFoundException(
            resource="InterviewSession",
            resource_id=sessionId,
        )

    return await skill_gap_service.generate_skill_gap_report(session=session)


# Exact Endpoints - Adaptive Question Generation (Phase 3)
@router.get(
    "/sessions/{sessionId}/next-question",
    response_model=QuestionResponse,
    summary="Adaptive Question Generation",
    description="Selects and generates the next interview question tailored adaptively to candidate state.",
)
async def get_next_question(
    sessionId: str,
    db: AsyncSession = Depends(get_db),
    adaptive_engine: AdaptiveEngine = Depends(get_adaptive_engine),
) -> QuestionResponse:
    """Generates the next interview question based on role, resume, assessed competencies, and difficulty."""
    # 1. Validate UUID format
    try:
        session_uuid = uuid.UUID(sessionId)
    except (ValueError, AttributeError):
        raise InvalidSessionStateException(
            message=f"Invalid sessionId format '{sessionId}'. Must be a valid UUID.",
            details={"sessionId": sessionId},
        )

    # 2. Query session with questions and resume analysis
    result = await db.execute(
        select(InterviewSession)
        .options(
            selectinload(InterviewSession.questions),
            selectinload(InterviewSession.resume_analysis),
        )
        .where(InterviewSession.id == session_uuid)
    )
    session = result.scalar_one_or_none()

    if session is None:
        raise ResourceNotFoundException(
            resource="InterviewSession",
            resource_id=sessionId,
        )

    # 3. Generate adaptive question and persist in DB
    question_response = await adaptive_engine.generate_next_question(
        session=session,
        db=db,
    )

    return question_response


@router.post(
    "/sessions/{sessionId}/answers",
    response_model=AnswerResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit and Evaluate Candidate Answer",
    description="Accepts candidate answer, evaluates it against role and criteria with Ollama, updates competency state.",
)
async def submit_answer(
    sessionId: str,
    payload: AnswerSubmitRequest,
    db: AsyncSession = Depends(get_db),
    evaluation_service: EvaluationService = Depends(get_evaluation_service),
) -> AnswerResponse:
    """Validates session and question, runs real-time rubric AI evaluation, updates competency state."""
    # 1. Validate sessionId format
    try:
        session_uuid = uuid.UUID(sessionId)
    except (ValueError, AttributeError):
        raise InvalidSessionStateException(
            message=f"Invalid sessionId format '{sessionId}'. Must be a valid UUID.",
            details={"sessionId": sessionId},
        )

    # 2. Validate question_id format
    try:
        question_uuid = uuid.UUID(payload.question_id)
    except (ValueError, AttributeError):
        raise InvalidSessionStateException(
            message=f"Invalid question_id format '{payload.question_id}'. Must be a valid UUID.",
            details={"question_id": payload.question_id},
        )

    # 3. Retrieve session
    result = await db.execute(
        select(InterviewSession).where(InterviewSession.id == session_uuid)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise ResourceNotFoundException(
            resource="InterviewSession",
            resource_id=sessionId,
        )

    # 4. Validate session state
    if session.status in ["completed", "abandoned"]:
        raise InvalidSessionStateException(
            message=f"Cannot submit answer: session is already '{session.status}'.",
            details={"sessionId": sessionId, "status": session.status},
        )

    # 5. Retrieve question belonging to this session
    q_result = await db.execute(
        select(Question).where(
            Question.id == question_uuid,
            Question.session_id == session_uuid,
        )
    )
    question = q_result.scalar_one_or_none()
    if question is None:
        raise ResourceNotFoundException(
            resource="Question",
            resource_id=payload.question_id,
        )

    # 6. Evaluate and persist answer
    return await evaluation_service.evaluate_and_save_answer(
        session=session,
        question=question,
        answer_payload=payload,
        db=db,
    )


@router.post(
    "/sessions/{sessionId}/answers/audio",
    response_model=AudioAnswerResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit and Evaluate Audio Answer via Speech-to-Text",
    description="Accepts candidate audio via multipart form data, transcribes it with faster-whisper, and evaluates it with Ollama.",
)
async def submit_audio_answer(
    sessionId: str,
    question_id: str = Form(..., description="UUID of the question being answered"),
    file: UploadFile = File(..., description="Audio recording file (wav, mp3, m4a, webm, ogg, flac)"),
    time_taken_seconds: Optional[int] = Form(default=None, description="Optional time spent formulating answer in seconds"),
    db: AsyncSession = Depends(get_db),
    evaluation_service: EvaluationService = Depends(get_evaluation_service),
    transcription_service: TranscriptionService = Depends(get_transcription_service),
) -> AudioAnswerResponse:
    """Validates session and question, transcribes audio to text with faster-whisper, and evaluates candidate answer."""
    # 1. Validate sessionId format
    try:
        session_uuid = uuid.UUID(sessionId)
    except (ValueError, AttributeError):
        raise InvalidSessionStateException(
            message=f"Invalid sessionId format '{sessionId}'. Must be a valid UUID.",
            details={"sessionId": sessionId},
        )

    # 2. Validate question_id format
    try:
        question_uuid = uuid.UUID(question_id)
    except (ValueError, AttributeError):
        raise InvalidSessionStateException(
            message=f"Invalid question_id format '{question_id}'. Must be a valid UUID.",
            details={"question_id": question_id},
        )

    # 3. Retrieve session
    result = await db.execute(
        select(InterviewSession).where(InterviewSession.id == session_uuid)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise ResourceNotFoundException(
            resource="InterviewSession",
            resource_id=sessionId,
        )

    # 4. Validate session state
    if session.status in ["completed", "abandoned"]:
        raise InvalidSessionStateException(
            message=f"Cannot submit answer: session is already '{session.status}'.",
            details={"sessionId": sessionId, "status": session.status},
        )

    # 5. Retrieve question belonging to this session
    q_result = await db.execute(
        select(Question).where(
            Question.id == question_uuid,
            Question.session_id == session_uuid,
        )
    )
    question = q_result.scalar_one_or_none()
    if question is None:
        raise ResourceNotFoundException(
            resource="Question",
            resource_id=question_id,
        )

    # 6. Validate and read audio file
    audio_bytes, clean_filename = await transcription_service.validate_and_read_audio(file)

    # 7. Real Speech-to-Text Transcription via faster-whisper
    transcript = await transcription_service.transcribe_audio(audio_bytes, clean_filename)

    # 8. Evaluate and persist answer using existing evaluation pipeline
    answer_payload = AnswerSubmitRequest(
        question_id=str(question.id),
        answer_text=transcript,
        time_taken_seconds=time_taken_seconds,
    )
    eval_response = await evaluation_service.evaluate_and_save_answer(
        session=session,
        question=question,
        answer_payload=answer_payload,
        db=db,
    )

    return AudioAnswerResponse(
        **eval_response.model_dump(),
        transcript=transcript,
    )


@router.post(
    "/sessions/{sessionId}/events",
    response_model=EventResponse,
    status_code=status.HTTP_200_OK,
    summary="Record Session Telemetry and Integrity Events",
    description="Persists interview events (tab switches, blurs, warnings) and tracks real-time progress.",
)
async def record_events(
    sessionId: str,
    payload: EventCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> EventResponse:
    """Persists session telemetry events, tracks questions/answers progress, returns current session state."""
    # 1. Validate sessionId format
    try:
        session_uuid = uuid.UUID(sessionId)
    except (ValueError, AttributeError):
        raise InvalidSessionStateException(
            message=f"Invalid sessionId format '{sessionId}'. Must be a valid UUID.",
            details={"sessionId": sessionId},
        )

    # 2. Retrieve session with questions and answers
    result = await db.execute(
        select(InterviewSession)
        .options(
            selectinload(InterviewSession.questions),
            selectinload(InterviewSession.answers),
            selectinload(InterviewSession.events),
        )
        .where(InterviewSession.id == session_uuid)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise ResourceNotFoundException(
            resource="InterviewSession",
            resource_id=sessionId,
        )

    # 3. Validate session state
    if session.status in ["completed", "abandoned"]:
        raise InvalidSessionStateException(
            message=f"Cannot record events: session is already '{session.status}'.",
            details={"sessionId": sessionId, "status": session.status},
        )

    # 4. Prepare events to persist
    events_to_add: List[SessionEvent] = []
    if payload.events and len(payload.events) > 0:
        for ev in payload.events:
            clean_type = ev.event_type.strip()
            if len(clean_type) >= 2:
                ev_time = ev.timestamp or datetime.now(timezone.utc)
                events_to_add.append(
                    SessionEvent(
                        session_id=session.id,
                        event_type=clean_type,
                        event_data=ev.event_data,
                        timestamp=ev_time,
                    )
                )
    elif payload.event_type:
        clean_event_type = payload.event_type.strip()
        if len(clean_event_type) < 2:
            raise InvalidSessionStateException(
                message="Event type must be at least 2 characters long.",
                details={"event_type": payload.event_type},
            )
        event_timestamp = payload.timestamp or datetime.now(timezone.utc)
        events_to_add.append(
            SessionEvent(
                session_id=session.id,
                event_type=clean_event_type,
                event_data=payload.event_data,
                timestamp=event_timestamp,
            )
        )
    else:
        raise InvalidSessionStateException(
            message="Either 'event_type' or 'events' list must be provided.",
            details={},
        )

    # 4b. Guard against excessive event spam (maximum 500 events per session)
    current_count = len(session.events) if session.events else 0
    if current_count + len(events_to_add) > 500:
        raise InvalidSessionStateException(
            message="Event limit reached for this interview session (maximum 500 events).",
            details={"sessionId": sessionId, "event_count": current_count},
        )

    # 5. Persist events
    for ev_item in events_to_add:
        db.add(ev_item)
    await db.commit()
    new_event = events_to_add[-1]
    await db.refresh(new_event)

    # 6. Compute progress
    now = datetime.now(timezone.utc)
    if session.started_at is None:
        time_rem = session.time_limit_minutes * 60
    else:
        elapsed = (now - session.started_at).total_seconds()
        time_rem = max(0, int(session.time_limit_minutes * 60 - elapsed))

    questions_count = len(session.questions) if session.questions else 0
    answers_count = len(session.answers) if session.answers else 0

    return EventResponse(
        sessionId=str(session.id),
        event_id=str(new_event.id),
        event_type=new_event.event_type,
        timestamp=new_event.timestamp,
        progress=InterviewProgress(
            questions_asked=questions_count,
            answers_submitted=answers_count,
            current_status=session.status,
            time_remaining_seconds=time_rem,
        ),
    )


@router.post(
    "/sessions/{sessionId}/complete",
    response_model=SessionCompleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Complete Interview Session",
    description="Marks session as completed, records completion timestamp, returns interview completion summary.",
)
async def complete_session(
    sessionId: str,
    db: AsyncSession = Depends(get_db),
) -> SessionCompleteResponse:
    """Validates session, updates status to completed, prevents further activity, calculates summary metrics."""
    # 1. Validate sessionId format
    try:
        session_uuid = uuid.UUID(sessionId)
    except (ValueError, AttributeError):
        raise InvalidSessionStateException(
            message=f"Invalid sessionId format '{sessionId}'. Must be a valid UUID.",
            details={"sessionId": sessionId},
        )

    # 2. Retrieve session with questions and answers
    result = await db.execute(
        select(InterviewSession)
        .options(
            selectinload(InterviewSession.questions),
            selectinload(InterviewSession.answers),
        )
        .where(InterviewSession.id == session_uuid)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise ResourceNotFoundException(
            resource="InterviewSession",
            resource_id=sessionId,
        )

    # 3. Handle repeated completion consistently (idempotency)
    now = datetime.now(timezone.utc)
    if session.status != "completed":
        session.status = "completed"
        if session.completed_at is None:
            session.completed_at = now
        await db.commit()
        await db.refresh(session)
        logger.info(f"Interview session {sessionId} transitioned to 'completed' at {session.completed_at}")

    # 4. Calculate metrics from saved answers
    total_questions = len(session.questions) if session.questions else 0
    total_answers = len(session.answers) if session.answers else 0
    avg_score = (
        round(sum(a.score for a in session.answers) / total_answers, 2)
        if total_answers > 0
        else None
    )

    return SessionCompleteResponse(
        sessionId=str(session.id),
        status=session.status,
        completed_at=session.completed_at or now,
        total_questions=total_questions,
        total_answers=total_answers,
        average_score=avg_score,
        message="Interview session completed successfully.",
    )


@router.get(
    "/sessions/{sessionId}/report",
    response_model=InterviewReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve Comprehensive Decision Report",
    description="Compiles deterministic candidate decision report from persisted session, questions, answers, and telemetry.",
)
async def get_report(
    sessionId: str,
    db: AsyncSession = Depends(get_db),
    report_service: ReportService = Depends(get_report_service),
) -> InterviewReportResponse:
    """Builds comprehensive evaluation decision report deterministically from database records."""
    # 1. Validate sessionId format
    try:
        session_uuid = uuid.UUID(sessionId)
    except (ValueError, AttributeError):
        raise InvalidSessionStateException(
            message=f"Invalid sessionId format '{sessionId}'. Must be a valid UUID.",
            details={"sessionId": sessionId},
        )

    # 2. Retrieve session with all related data
    result = await db.execute(
        select(InterviewSession)
        .options(
            selectinload(InterviewSession.resume_analysis),
            selectinload(InterviewSession.questions).selectinload(Question.answer),
            selectinload(InterviewSession.answers),
            selectinload(InterviewSession.events),
        )
        .where(InterviewSession.id == session_uuid)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise ResourceNotFoundException(
            resource="InterviewSession",
            resource_id=sessionId,
        )

    # 3. Generate deterministic report
    return await report_service.generate_report(session)
