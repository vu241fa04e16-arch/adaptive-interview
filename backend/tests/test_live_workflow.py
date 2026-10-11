import pytest
from app.config import get_settings
from app.core.ollama_client import AsyncOllamaClient
from app.schemas.answer import AnswerEvaluationLLM
from app.schemas.question import GeneratedQuestionLLM


@pytest.mark.live_ollama
@pytest.mark.asyncio
async def test_live_ollama_adaptive_question_and_answer_eval():
    """Live validation of question generation and answer evaluation against real local Ollama llama3.1."""
    settings = get_settings()
    client = AsyncOllamaClient(
        base_url=settings.OLLAMA_BASE_URL,
        model=settings.OLLAMA_MODEL,
        timeout_seconds=90.0,
    )

    try:
        # 1. Health check
        health = await client.check_health()
        assert health["status"] == "available"
        assert health["model_available"] is True

        # 2. Live adaptive question generation
        question_prompt = (
            "TARGET ROLE: Senior Backend Architect\n"
            "SENIORITY LEVEL: Senior\n"
            "COMPETENCY: Database Internals & Concurrency\n"
            "TARGET DIFFICULTY: advanced\n"
            "QUESTION TYPE: technical_concept\n\n"
            "Generate the technical question and 2 to 4 key evaluation criteria."
        )
        system_question_prompt = (
            "You are an expert technical interviewer conducting a live adaptive engineering interview.\n"
            "Formulate ONE direct, precise interview question tailored to the target role, competency, and difficulty.\n\n"
            "CRITICAL CONSTRAINTS:\n"
            "1. Output MUST strictly conform to the JSON schema provided.\n"
            "2. Formulate ONLY ONE question.\n"
            "3. Keep the question professional, practical, and focused on real-world engineering."
        )

        generated_q = await client.generate_structured(
            prompt=question_prompt,
            schema=GeneratedQuestionLLM,
            system_prompt=system_question_prompt,
            options={"temperature": 0.2, "num_predict": 250},
        )
        assert isinstance(generated_q, GeneratedQuestionLLM)
        assert len(generated_q.question_text) > 20
        assert len(generated_q.key_evaluation_criteria) >= 1
        print(f"\n[LIVE QUESTION GENERATION SUCCESS]\nQuestion: {generated_q.question_text}")
        print(f"Criteria: {generated_q.key_evaluation_criteria}")

        # 3. Live rubric answer evaluation
        candidate_answer = (
            "In PostgreSQL, Read Committed transactions obtain a new snapshot at the beginning of each individual statement. "
            "Serializable snapshot isolation (SSI) keeps a single snapshot across the whole transaction and tracks rw-antidependencies "
            "using SIREAD predicate locks to prevent anomalies without locking physical rows."
        )
        eval_prompt = (
            "TARGET ROLE: Senior Backend Architect\n"
            "SENIORITY LEVEL: Senior\n"
            "COMPETENCY: Database Internals & Concurrency\n"
            f"QUESTION DIFFICULTY: advanced\n"
            f"QUESTION:\n{generated_q.question_text}\n\n"
            f"KEY EVALUATION CRITERIA:\n- {generated_q.key_evaluation_criteria}\n\n"
            f"CANDIDATE ANSWER:\n{candidate_answer}\n\n"
            "Evaluate the answer according to the rubric and return structured evaluation JSON."
        )
        system_eval_prompt = (
            "You are an expert technical interviewer evaluating an engineering candidate's answer.\n"
            "Evaluate the candidate's answer rigorously, objectively, and constructively against the target role, seniority level, and question evaluation criteria.\n\n"
            "CRITICAL CONSTRAINTS:\n"
            "1. Output MUST strictly conform to the provided JSON Schema.\n"
            "2. Score on a scale from 0.0 to 10.0.\n"
            "3. Identify concrete strengths, weaknesses, feedback, and improvement suggestions."
        )

        evaluation = await client.generate_structured(
            prompt=eval_prompt,
            schema=AnswerEvaluationLLM,
            system_prompt=system_eval_prompt,
            options={"temperature": 0.1, "num_predict": 350},
        )
        assert isinstance(evaluation, AnswerEvaluationLLM)
        assert 0.0 <= evaluation.score <= 10.0
        assert len(evaluation.feedback) > 10
        print(f"\n[LIVE ANSWER EVALUATION SUCCESS]\nScore: {evaluation.score}/10")
        print(f"Feedback: {evaluation.feedback}")
        print(f"Strengths: {evaluation.strengths}")
        print(f"Weaknesses: {evaluation.weaknesses}")

    finally:
        await client.aclose()
