from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class ClaimedSkill(BaseModel):
    """Represents a skill or technology explicitly claimed on the candidate's resume."""

    name: str = Field(description="Name of the skill or technology, e.g. PostgreSQL, Distributed Systems")
    claimed_experience_years: Optional[float] = Field(
        default=None,
        description="Years of experience explicitly stated in resume, or null if unspecified",
    )
    claimed_proficiency: Literal["Beginner", "Intermediate", "Advanced", "Expert"] = Field(
        default="Intermediate",
        description="Claimed proficiency level based on resume roles and self-assessment",
    )
    context_snippet: Optional[str] = Field(
        default=None,
        description="Verbatim phrase or project mention supporting the claim",
    )


class ProjectSummary(BaseModel):
    """Summary of a notable project or system detailed on the resume."""

    project_name: str = Field(description="Title or identifier of the project")
    technologies: List[str] = Field(default_factory=list, description="Technologies applied")
    highlights: List[str] = Field(default_factory=list, description="Key contributions or achievements")


class ResumeAnalysisLLMOutput(BaseModel):
    """Strict structured JSON schema produced by Ollama when parsing extracted resume text."""

    candidate_overview: str = Field(
        description="Factual, objective 2-3 sentence summary of candidate's career experience",
    )
    claimed_skills: List[ClaimedSkill] = Field(
        default_factory=list,
        description="All technical skills and competencies explicitly claimed in the resume",
    )
    projects: List[ProjectSummary] = Field(
        default_factory=list,
        description="Key engineering projects and production systems mentioned",
    )
    suggested_focus_areas: List[str] = Field(
        default_factory=list,
        description="3 to 6 critical competency areas that require deep probing during the interview",
    )


class ResumeUploadResponse(BaseModel):
    """Response returned upon successful resume upload and AI analysis."""

    sessionId: str
    resume_parsed: bool = True
    file_name: str
    file_hash: str
    file_size_bytes: int
    candidate_overview: Optional[str] = None
    claimed_skills: List[ClaimedSkill]
    projects: List[ProjectSummary]
    suggested_focus_areas: List[str]
    message: str = "Resume analyzed successfully. Interview competency profile primed."
