from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import (
    AsyncOllamaClient,
    get_adaptive_engine,
    get_db,
    get_ollama_client,
    get_resume_service,
)
from app.config import get_settings
from app.core.exceptions import InvalidSessionStateException, ResourceNotFoundException
from app.core.logging import logger
from app.database import check_database_health
from app.models.resume import ResumeAnalysis
from app.models.session import InterviewSession
from app.schemas.health import DatabaseHealth, HealthResponse, OllamaHealth
from app.schemas.question import QuestionResponse
from app.schemas.resume import (
    ClaimedSkill,
    ProjectSummary,
    ResumeUploadResponse,
)
from app.schemas.session import SessionCreateRequest, SessionResponse
from app.services.adaptive_engine import AdaptiveEngine
from app.services.resume_service import ResumeService

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
    """Creates a new interview session and initializes empty competency matrix."""
    session = InterviewSession(
        candidate_name=payload.candidate_name,
        candidate_email=str(payload.candidate_email),
        target_role=payload.target_role,
        target_level=payload.target_level,
        status="created",
        time_limit_minutes=payload.time_limit_minutes,
        competency_state={},
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
        message="Resume analyzed successfully. Interview competency profile primed.",
    )


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
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    summary="Submit and Evaluate Candidate Answer",
)
async def submit_answer(sessionId: str):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Endpoint scheduled for Phase 4 implementation (Real-time Evaluation).",
    )


@router.post(
    "/sessions/{sessionId}/events",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    summary="Stream Integrity Analytics Telemetry",
)
async def record_events(sessionId: str):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Endpoint scheduled for Phase 5 implementation (Integrity Intelligence).",
    )


@router.post(
    "/sessions/{sessionId}/complete",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    summary="Complete Interview Session",
)
async def complete_session(sessionId: str):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Endpoint scheduled for Phase 5 implementation (Decision Reporting).",
    )


@router.get(
    "/sessions/{sessionId}/report",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
    summary="Retrieve Comprehensive Decision Report",
)
async def get_report(sessionId: str):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Endpoint scheduled for Phase 5 implementation (Decision Reporting).",
    )
