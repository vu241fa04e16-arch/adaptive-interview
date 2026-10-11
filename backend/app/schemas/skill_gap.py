from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class JobDescriptionSubmitRequest(BaseModel):
    """Payload for submitting a job description to an interview session."""

    job_description: str = Field(
        ...,
        min_length=10,
        max_length=50000,
        description="Full text of the technical job description",
    )


class RequiredSkillItem(BaseModel):
    """Individual skill required by the role and its candidate assessment classification."""

    skill_name: str = Field(description="Name of technical skill or competency")
    category: str = Field(default="Technical", description="Skill category, e.g. Core, Systems, Architecture")
    importance: str = Field(default="Required", description="Required or Preferred")
    classification: Literal[
        "demonstrated",
        "claimed_but_unvalidated",
        "not_demonstrated",
        "not_assessed",
    ] = Field(description="Skill gap assessment classification")
    evidence: str = Field(description="Interview or resume evidence supporting the classification")
    explanation: str = Field(description="Clear explanation of the assessment decision")


class SkillGapReport(BaseModel):
    """Comprehensive Resume-JD Skill Gap Analysis."""

    sessionId: Optional[str] = None
    target_role: str
    target_level: str
    job_description_provided: bool
    summary: str
    required_skills: List[RequiredSkillItem] = Field(default_factory=list)
    demonstrated_skills: List[str] = Field(default_factory=list)
    claimed_unvalidated_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    unassessed_skills: List[str] = Field(default_factory=list)
    improvement_recommendations: List[str] = Field(default_factory=list)
    suggested_follow_up_questions: List[str] = Field(default_factory=list)
