import re
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.core.ollama_client import AsyncOllamaClient
from app.models.session import InterviewSession
from app.schemas.skill_gap import RequiredSkillItem, SkillGapReport


class JDExtractionLLM(BaseModel):
    """Structured extraction of requirements from a Job Description."""

    required_skills: List[str] = Field(
        default_factory=list,
        description="Core must-have technical skills, frameworks, or competencies",
    )
    preferred_skills: List[str] = Field(
        default_factory=list,
        description="Nice-to-have or preferred technical skills",
    )
    key_responsibilities: List[str] = Field(
        default_factory=list,
        description="Primary technical responsibilities described in the JD",
    )
    summary: str = Field(
        description="Concise 1-2 sentence overview of the role requirements",
    )


class SkillGapService:
    """Performs Resume–JD Skill Gap Analysis, comparing job requirements against resume claims and interview evidence."""

    def __init__(self, ollama_client: Optional[AsyncOllamaClient] = None):
        self.ollama = ollama_client

    # Common engineering competency benchmarks for fallback or when no explicit JD is provided
    ROLE_BENCHMARKS = {
        "backend": [
            ("PostgreSQL / Relational Databases", "Core Database Architecture and ACID Transactions", "Required"),
            ("Distributed Systems & Concurrency", "System Scalability, Locking, and Partitioning", "Required"),
            ("API Architecture & REST/gRPC", "API Design and Microservice Communication", "Required"),
            ("Caching & Message Queues", "Redis, Kafka, or Event-Driven Messaging", "Preferred"),
            ("Testing & Code Quality", "Unit and Integration Testing Rigor", "Required"),
        ],
        "fullstack": [
            ("Frontend Engineering", "React / Modern UI Architecture", "Required"),
            ("Backend Services", "API Design, Authentication, and Business Logic", "Required"),
            ("Databases & ORM", "SQL Schema Design and Query Performance", "Required"),
            ("System Architecture", "End-to-end distributed client-server flow", "Required"),
            ("DevOps & CI/CD", "Containerization and Cloud Deployment", "Preferred"),
        ],
        "frontend": [
            ("JavaScript / TypeScript", "Deep Language Mechanics and Async Patterns", "Required"),
            ("Component Architecture", "State Management, Virtual DOM, and Rendering Lifecycles", "Required"),
            ("Web Performance", "Bundle Optimization, Critical Rendering Path, and Core Web Vitals", "Required"),
            ("Testing & Accessibility", "Unit Testing and WCAG Standards", "Preferred"),
        ],
    }

    async def extract_skills_from_jd(
        self,
        job_description: str,
        target_role: str,
        target_level: str,
    ) -> List[Dict[str, str]]:
        """Extracts required skills from JD text using Ollama, with robust deterministic fallback."""
        if self.ollama:
            try:
                system_prompt = (
                    "You are a technical recruiting architect analyzing a technical job description.\n"
                    "Extract the required technical competencies and skills strictly conforming to the JSON schema."
                )
                prompt = (
                    f"ROLE: {target_role}\n"
                    f"LEVEL: {target_level}\n"
                    f"JOB DESCRIPTION:\n{job_description[:3000]}\n\n"
                    "Extract required skills, preferred skills, and summary."
                )
                extracted: JDExtractionLLM = await self.ollama.generate_structured(
                    prompt=prompt,
                    schema=JDExtractionLLM,
                    system_prompt=system_prompt,
                    options={"temperature": 0.1, "num_predict": 300},
                )
                skills: List[Dict[str, str]] = []
                for s in extracted.required_skills:
                    if s.strip():
                        skills.append({"name": s.strip(), "importance": "Required", "category": "Technical"})
                for s in extracted.preferred_skills:
                    if s.strip():
                        skills.append({"name": s.strip(), "importance": "Preferred", "category": "Technical"})
                if skills:
                    return skills
            except Exception as e:
                logger.warning(f"Ollama JD extraction failed, using deterministic extractor: {e}")

        # Deterministic extraction fallback: parse bullet points and recognized technical skills
        return self._deterministic_extract_jd_skills(job_description, target_role)

    def _deterministic_extract_jd_skills(self, text: str, target_role: str) -> List[Dict[str, str]]:
        """Rule-based extraction searching for industry keywords and bullet items."""
        found_skills: List[Dict[str, str]] = []
        seen_names: Set[str] = set()

        # Curated technical keyword list
        keywords = [
            ("PostgreSQL", "Database", "Required"),
            ("Distributed Systems", "Architecture", "Required"),
            ("Kafka", "Messaging", "Preferred"),
            ("Docker", "DevOps", "Preferred"),
            ("Kubernetes", "DevOps", "Preferred"),
            ("Python", "Language", "Required"),
            ("FastAPI", "Framework", "Required"),
            ("Redis", "Caching", "Preferred"),
            ("SQL", "Database", "Required"),
            ("System Design", "Architecture", "Required"),
            ("Microservices", "Architecture", "Required"),
            ("Concurrency", "Systems", "Required"),
            ("REST APIs", "API Design", "Required"),
            ("CI/CD", "DevOps", "Preferred"),
            ("GraphQL", "API Design", "Preferred"),
            ("TypeScript", "Language", "Required"),
            ("React", "Frontend", "Required"),
            ("Node.js", "Runtime", "Required"),
        ]

        lower_text = text.lower()
        for name, category, importance in keywords:
            pattern = r"\b" + re.escape(name.lower()) + r"\b"
            if re.search(pattern, lower_text):
                if name.lower() not in seen_names:
                    seen_names.add(name.lower())
                    found_skills.append({"name": name, "category": category, "importance": importance})

        # Also extract bullet points containing "experience with", "knowledge of", "proficient in"
        lines = text.splitlines()
        for line in lines:
            line_str = line.strip(" -*•\t")
            if len(line_str) > 5 and len(line_str) < 60:
                if any(kw in line_str.lower() for kw in ["experience with", "knowledge of", "proficient in", "strong in"]):
                    cleaned = re.sub(r"(?i)^(experience with|knowledge of|proficient in|strong in)\s+", "", line_str)
                    cleaned = cleaned.strip(" .,;")
                    if cleaned and cleaned.lower() not in seen_names:
                        seen_names.add(cleaned.lower())
                        found_skills.append({"name": cleaned, "category": "Technical", "importance": "Required"})

        # If too few found, supplement with role benchmark
        if len(found_skills) < 3:
            benchmarks = self._get_role_benchmarks(target_role)
            for name, category, imp in benchmarks:
                if name.lower() not in seen_names:
                    seen_names.add(name.lower())
                    found_skills.append({"name": name, "category": category, "importance": imp})

        return found_skills

    def _get_role_benchmarks(self, role: str) -> List[Tuple[str, str, str]]:
        lower_role = role.lower()
        if "frontend" in lower_role or "ui" in lower_role:
            return self.ROLE_BENCHMARKS["frontend"]
        elif "full" in lower_role:
            return self.ROLE_BENCHMARKS["fullstack"]
        return self.ROLE_BENCHMARKS["backend"]

    async def analyze_and_persist_gap(
        self,
        session: InterviewSession,
        job_description: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> SkillGapReport:
        """Executes skill gap analysis, persists in session competency_state, and returns report."""
        report = await self.generate_skill_gap_report(session, job_description)

        # Persist in session.competency_state JSONB
        comp_state = dict(session.competency_state or {})
        if job_description:
            comp_state["job_description"] = job_description
        comp_state["skill_gap_analysis"] = report.model_dump()
        session.competency_state = comp_state

        if db:
            await db.commit()

        return report

    async def generate_skill_gap_report(
        self,
        session: InterviewSession,
        job_description: Optional[str] = None,
    ) -> SkillGapReport:
        """Generates comprehensive skill gap analysis comparing requirements against resume and interview answers."""
        comp_state = session.competency_state or {}
        jd_text = (
            job_description
            or comp_state.get("job_description")
            or ""
        ).strip()
        jd_provided = bool(jd_text)

        # 1. Determine requirements
        if jd_provided:
            extracted_reqs = await self.extract_skills_from_jd(
                jd_text,
                session.target_role,
                session.target_level,
            )
        else:
            benchmarks = self._get_role_benchmarks(session.target_role)
            extracted_reqs = [
                {"name": name, "category": cat, "importance": imp}
                for name, cat, imp in benchmarks
            ]

        # 2. Gather candidate resume claims
        claimed_skills_list = list(comp_state.get("claimed_skills", []))
        if not claimed_skills_list and session.resume_analysis:
            claimed_skills_list = list(session.resume_analysis.claimed_skills or [])

        claimed_lookup: Dict[str, Dict[str, Any]] = {}
        for cs in claimed_skills_list:
            c_name = cs.get("name", "").strip().lower()
            if c_name:
                claimed_lookup[c_name] = cs

        # 3. Gather interview answers and verified competencies
        answers_list = list(session.answers or [])
        questions_list = list(session.questions or [])
        answers_by_qid = {a.question_id: a for a in answers_list}

        # 4. Classify each required skill
        required_items: List[RequiredSkillItem] = []
        demonstrated_skills: List[str] = []
        claimed_unvalidated: List[str] = []
        missing_skills: List[str] = []
        unassessed_skills: List[str] = []
        follow_ups: List[str] = []
        recommendations: List[str] = []

        for req in extracted_reqs:
            req_name = req["name"]
            req_lower = req_name.lower()
            req_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", req_lower))

            # Match claimed skill in resume
            matched_claim = claimed_lookup.get(req_lower)
            if not matched_claim:
                for c_name, c_data in claimed_lookup.items():
                    c_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", c_name))
                    if req_words.intersection(c_words) or c_name in req_lower or req_lower in c_name:
                        matched_claim = c_data
                        break

            # Find matching question and answer
            matched_question = None
            matched_answer = None
            for q in questions_list:
                q_comp_lower = (q.competency or "").lower()
                q_text_lower = (q.question_text or "").lower()
                q_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", q_comp_lower))
                if req_words.intersection(q_words) or any(w in q_text_lower for w in req_words if len(w) >= 4):
                    matched_question = q
                    matched_answer = answers_by_qid.get(q.id)
                    if matched_answer:
                        break

            # Classification logic
            # Rule 1: Demonstrated
            is_demonstrated = False
            if matched_claim and matched_claim.get("verified") is True:
                is_demonstrated = True
            elif matched_answer and matched_answer.score >= 7.0:
                is_demonstrated = True

            if is_demonstrated:
                score = (
                    matched_claim.get("demonstrated_score")
                    if matched_claim and matched_claim.get("demonstrated_score") is not None
                    else (matched_answer.score if matched_answer else 7.5)
                )
                evidence = (
                    f"Verified in interview answer with score {score}/10. "
                    f"Demonstrated core competency criteria: {matched_question.competency if matched_question else req_name}."
                )
                explanation = "Candidate answered targeted technical questions meeting seniority threshold."
                classification = "demonstrated"
                demonstrated_skills.append(req_name)

            # Rule 2: Attempted but Not Demonstrated (Low Score / Inadequate)
            elif matched_answer and matched_answer.score < 7.0:
                evidence = (
                    f"Assessed on Question '{matched_question.question_text[:75]}...' but scored {matched_answer.score}/10. "
                    f"Feedback noted omissions in: {', '.join(matched_answer.weaknesses[:2]) if matched_answer.weaknesses else 'depth of understanding'}."
                )
                explanation = "Candidate answered questions addressing this competency but did not achieve the required threshold."
                classification = "not_demonstrated"
                missing_skills.append(req_name)
                recommendations.append(f"Strengthen depth in {req_name}: focus on production patterns and edge cases.")
                follow_ups.append(f"Could you walk through a production failure or edge case you handled involving {req_name}?")

            # Rule 3: Claimed in Resume but Unvalidated
            elif matched_claim:
                years = matched_claim.get("claimed_years") or matched_claim.get("claimed_experience_years") or "N/A"
                prof = matched_claim.get("claimed_proficiency") or "Intermediate"
                evidence = f"Claimed in resume ({years} yrs experience, stated proficiency: '{prof}'), but not yet assessed in interview questions."
                explanation = "Candidate claims familiarity on resume, but capability has not yet been validated through live technical questioning."
                classification = "claimed_but_unvalidated"
                claimed_unvalidated.append(req_name)
                follow_ups.append(f"Given your resume background in {req_name}, how would you approach architecting it for high throughput?")

            # Rule 4: Not Assessed
            else:
                evidence = "Skill requirement is neither claimed in the candidate's submitted resume nor evaluated in interview questioning."
                explanation = "Requirement has not yet been addressed during the evaluation process."
                classification = "not_assessed"
                unassessed_skills.append(req_name)
                missing_skills.append(req_name)
                follow_ups.append(f"Do you have practical experience applying {req_name} in previous roles?")
                recommendations.append(f"Evaluate candidate hands-on experience with {req_name}.")

            required_items.append(
                RequiredSkillItem(
                    skill_name=req_name,
                    category=req.get("category", "Technical"),
                    importance=req.get("importance", "Required"),
                    classification=classification,
                    evidence=evidence,
                    explanation=explanation,
                )
            )

        # Summary generation
        total_reqs = len(required_items)
        demo_count = len(demonstrated_skills)
        summary = (
            f"Candidate demonstrated {demo_count} of {total_reqs} target role requirements. "
            f"{len(claimed_unvalidated)} skill(s) claimed in resume require live validation, and "
            f"{len(missing_skills)} skill gap(s) identified for further exploration."
        )

        return SkillGapReport(
            sessionId=str(session.id),
            target_role=session.target_role,
            target_level=session.target_level,
            job_description_provided=jd_provided,
            summary=summary,
            required_skills=required_items,
            demonstrated_skills=demonstrated_skills,
            claimed_unvalidated_skills=claimed_unvalidated,
            missing_skills=missing_skills,
            unassessed_skills=unassessed_skills,
            improvement_recommendations=recommendations[:4],
            suggested_follow_up_questions=follow_ups[:4],
        )
