import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class AnswerSubmitRequest(BaseModel):
    """Payload for submitting a candidate answer."""

    question_id: str = Field(description="UUID of the question being answered")
    answer_text: str = Field(min_length=1, description="Candidate answer content")
    time_taken_seconds: Optional[int] = Field(default=None, ge=0, description="Optional time spent formulating answer")

    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, data: object) -> object:
        if isinstance(data, dict):
            d = dict(data)
            if "question_id" not in d and "questionId" in d:
                d["question_id"] = d["questionId"]
            if "answer_text" not in d and "text" in d:
                d["answer_text"] = d["text"]
            if "time_taken_seconds" not in d and "timeTakenSeconds" in d:
                d["time_taken_seconds"] = d["timeTakenSeconds"]
            return d
        return data

    @field_validator("answer_text")
    @classmethod
    def validate_answer_text_not_blank(cls, val: str) -> str:
        if not val or not val.strip():
            raise ValueError("Candidate answer text cannot be empty or blank.")
        return val.strip()


class AnswerEvaluationLLM(BaseModel):
    """Structured rubric-based evaluation returned by local Ollama."""

    score: float = Field(
        ge=0.0,
        le=10.0,
        description="Rubric score between 0.0 (inadequate) and 10.0 (flawless mastery)",
    )
    strengths: List[str] = Field(
        default_factory=list,
        description="Technical strengths and correct arguments demonstrated in candidate answer",
    )
    weaknesses: List[str] = Field(
        default_factory=list,
        description="Technical omissions, errors, or anti-patterns observed",
    )
    feedback: str = Field(
        description="Concise, actionable qualitative feedback for the candidate",
    )
    improvement_suggestions: List[str] = Field(
        default_factory=list,
        description="Specific topics or architectural concepts recommended for deeper mastery",
    )

    @model_validator(mode="before")
    @classmethod
    def unwrap_and_normalize(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        d = dict(data)
        # 1. Unwrap if nested inside "properties" (schema echo)
        if "properties" in d and isinstance(d["properties"], dict) and "score" not in d:
            d = dict(d["properties"])
        # 2. Unwrap if nested inside top-level wrapper key
        for wrapper_key in ("evaluation", "data", "result", "response"):
            if wrapper_key in d and isinstance(d[wrapper_key], dict) and "score" not in d:
                d = dict(d[wrapper_key])
                break
        # 3. Extract score if it is a dict object
        if "score" in d and isinstance(d["score"], dict):
            for k in ("value", "score", "current", "rating", "val"):
                if k in d["score"]:
                    d["score"] = d["score"][k]
                    break
        return d

    @field_validator("score", mode="before")
    @classmethod
    def normalize_score(cls, val: Any) -> float:
        if val is None:
            raise ValueError("Evaluation score is required from AI evaluation.")
        if isinstance(val, (int, float)):
            num = float(val)
        elif isinstance(val, str):
            match = re.search(r"(\d+(?:\.\d+)?)", val.strip())
            if match:
                num = float(match.group(1))
            else:
                raise ValueError(f"Cannot parse numeric evaluation score from '{val}'.")
        else:
            raise ValueError(f"Invalid evaluation score type '{type(val).__name__}'.")

        # Normalize 0-100 percentage scale down to 0-10 rubric scale
        if num > 10.0 and num <= 100.0:
            num = num / 10.0

        return max(0.0, min(10.0, round(num, 2)))

    @field_validator("strengths", "weaknesses", "improvement_suggestions", mode="before")
    @classmethod
    def normalize_string_list(cls, val: Any) -> List[str]:
        if val is None:
            return []
        if isinstance(val, dict):
            if "items" in val and isinstance(val["items"], list):
                val = val["items"]
            else:
                val = list(val.values())
        if isinstance(val, str):
            val_clean = val.strip()
            if not val_clean:
                return []
            if "\n" in val_clean:
                return [line.lstrip("-* \t").strip() for line in val_clean.splitlines() if line.strip()]
            return [val_clean]
        if isinstance(val, list):
            res = []
            for item in val:
                if isinstance(item, str):
                    s = item.lstrip("-* \t").strip()
                    if s:
                        res.append(s)
                elif isinstance(item, dict):
                    for k in ("item", "text", "description", "content", "name"):
                        if k in item and isinstance(item[k], str) and item[k].strip():
                            res.append(item[k].strip())
                            break
                    else:
                        res.append(str(item))
            return res
        return []

    @field_validator("feedback", mode="before")
    @classmethod
    def normalize_feedback(cls, val: Any) -> str:
        if val is None:
            raise ValueError("Qualitative feedback is required from AI evaluation.")
        if isinstance(val, list):
            joined = " ".join(str(s).strip() for s in val if str(s).strip())
            if not joined:
                raise ValueError("Qualitative feedback cannot be empty.")
            return joined
        if isinstance(val, dict):
            for k in ("text", "summary", "feedback", "comment", "message"):
                if k in val and isinstance(val[k], str) and val[k].strip():
                    return val[k].strip()
            joined = " ".join(f"{k}: {v}" for k, v in val.items() if isinstance(v, (str, int, float)))
            if not joined:
                raise ValueError("Qualitative feedback cannot be empty.")
            return joined
        s = str(val).strip()
        if not s:
            raise ValueError("Qualitative feedback cannot be empty.")
        return s


class AnswerResponse(BaseModel):
    """API response returned by POST /api/sessions/{sessionId}/answers."""

    sessionId: str
    answer_id: str
    question_id: str
    score: float
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    feedback: str
    improvement_suggestions: List[str] = Field(default_factory=list)
    competency: str
    created_at: datetime
    has_more: bool = Field(default=True, description="Whether additional adaptive questions remain")


class AudioAnswerResponse(AnswerResponse):
    """API response returned by POST /api/sessions/{sessionId}/answers/audio."""

    transcript: str = Field(description="Full speech-to-text transcript of candidate audio")
