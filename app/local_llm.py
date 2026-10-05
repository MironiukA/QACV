import json
import re
from io import BytesIO
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException, status

from app.config import (
    AI_PROVIDER,
    LOCAL_LLM_MODEL,
    LOCAL_LLM_URL,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_TRANSCRIPTION_MODEL,
    OPENAI_WEB_RESEARCH_ENABLED,
)
from app.prompts.primary_screening import (
    build_primary_screening_evaluation_prompt,
    build_primary_screening_question_prompt,
)
from app.prompts.qa_interview_screener import build_final_report_prompt, build_interview_turn_prompt
from app.prompts.vacancy_analyzer import build_vacancy_profile_prompt
from app.schemas import VacancyProfileData


def analyze_vacancy(vacancy_text: str) -> str:
    prompt = f"""Analyze this public job vacancy. Return JSON only in this exact shape:
{{"requirements":[{{"name":"skill name","priority":"must_have or nice_to_have","evidence":"exact quote from the vacancy"}}]}}

Rules:
- Include only requirements that are explicitly stated in the vacancy.
- The evidence value must be a verbatim quote from the vacancy, not a paraphrase.
- Do not infer or add related technologies.

Vacancy text:
{vacancy_text}
"""
    return _generate(prompt)


def local_llm_info() -> dict[str, str]:
    if AI_PROVIDER == "openai":
        return {"url": "https://api.openai.com", "model": OPENAI_MODEL}
    return {"url": LOCAL_LLM_URL, "model": LOCAL_LLM_MODEL}


def validate_local_llm_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1"}:
        raise RuntimeError("LOCAL_LLM_URL must use http://127.0.0.1 or http://[::1]")


def evidence_backed_requirements(analysis: str, vacancy_text: str) -> tuple[list[dict[str, str]], int]:
    try:
        data = json.loads(_strip_markdown_fence(analysis))
        items = data.get("requirements") if isinstance(data, dict) else data
    except (json.JSONDecodeError, TypeError):
        return [], 0
    if not isinstance(items, list):
        return [], 0

    accepted: list[dict[str, str]] = []
    rejected = 0
    normalized_vacancy = _normalize(vacancy_text)
    for item in items:
        if not isinstance(item, dict):
            rejected += 1
            continue
        name = item.get("name")
        priority = item.get("priority")
        evidence = item.get("evidence")
        if (
            not isinstance(name, str)
            or not name.strip()
            or priority not in {"must_have", "nice_to_have"}
            or not isinstance(evidence, str)
            or not evidence.strip()
            or _normalize(evidence) not in normalized_vacancy
        ):
            rejected += 1
            continue
        accepted.append(
            {
                "name": name.strip(),
                "category": "skill",
                "priority": priority,
                "source_text": evidence.strip(),
            }
        )
    return accepted, rejected


def match_resume_to_requirements(resume_text: str, requirements: list[dict[str, str]]) -> str:
    requirements_json = json.dumps(requirements, ensure_ascii=False)
    prompt = f"""Compare the resume with each vacancy requirement. Return JSON only in this exact shape:
{{"matches":[{{"requirement_id":1,"status":"confirmed or needs_clarification","evidence":"exact resume quote or null"}}]}}

Rules:
- Mark confirmed only when evidence is a verbatim quote from the resume.
- If the resume does not explicitly prove the requirement, use needs_clarification.
- Do not infer skills from related technologies.
- Include every requirement id exactly once.

Requirements:
{requirements_json}

Resume:
{resume_text[:20_000]}
"""
    return _generate(prompt)


def evidence_backed_matches(
    analysis: str, resume_text: str, requirement_ids: set[int]
) -> dict[int, dict[str, str | None]]:
    try:
        data = json.loads(_strip_markdown_fence(analysis))
        items = data.get("matches") if isinstance(data, dict) else data
    except (json.JSONDecodeError, TypeError):
        items = []

    results = {
        requirement_id: {
            "status": "needs_clarification",
            "evidence": None,
            "question": None,
        }
        for requirement_id in requirement_ids
    }
    if not isinstance(items, list):
        return results

    normalized_resume = _normalize(resume_text)
    for item in items:
        if not isinstance(item, dict) or item.get("requirement_id") not in requirement_ids:
            continue
        requirement_id = item["requirement_id"]
        evidence = item.get("evidence")
        if (
            item.get("status") == "confirmed"
            and isinstance(evidence, str)
            and evidence.strip()
            and _normalize(evidence) in normalized_resume
        ):
            results[requirement_id] = {"status": "confirmed", "evidence": evidence.strip(), "question": None}
    return results


def generate_tailored_resume(resume_text: str, confirmed_answers: list[dict[str, str]]) -> str:
    additions = json.dumps(confirmed_answers, ensure_ascii=False)
    prompt = f"""Create an updated Russian resume tailored to the vacancy requirements.

Use only facts from the original resume and the confirmed candidate answers below.
Do not invent employers, dates, job titles, skills, projects, metrics, or experience levels.
If a fact is vague, state it conservatively. Return only the finished resume in Russian Markdown.

Original resume:
{resume_text[:20_000]}

Confirmed additions from the candidate. Put each fact in its stated resume_section:
{additions}
"""
    return _generate(prompt)


def refine_candidate_answer(question: str, raw_answer: str) -> dict[str, str]:
    prompt = f"""Rewrite a candidate's answer for a resume without adding facts.

Return JSON only in this exact shape:
{{"resume_section":"skills or experience or projects or summary","refined_answer":"concise factual Russian text"}}

Rules:
- Preserve only facts stated by the candidate.
- Correct grammar and make the wording professional and specific.
- Do not invent technologies, dates, companies, seniority, metrics, or responsibilities.
- If the answer is vague, keep it conservative instead of making it stronger.

Clarification question:
{question}

Candidate's raw answer:
{raw_answer}
"""
    response = _generate(prompt)
    try:
        data = json.loads(_strip_markdown_fence(response))
        section = data.get("resume_section")
        refined_answer = data.get("refined_answer")
    except (json.JSONDecodeError, AttributeError):
        section = None
        refined_answer = None
    if section not in {"skills", "experience", "projects", "summary"}:
        section = "experience"
    if not isinstance(refined_answer, str) or not refined_answer.strip():
        refined_answer = raw_answer.strip()
    return {"resume_section": section, "refined_answer": refined_answer.strip()}


def evaluate_screening_answer(topic: str, question: str, answer: str) -> dict[str, str | int]:
    response = _generate(build_primary_screening_evaluation_prompt(topic, question, answer))
    try:
        data = json.loads(_strip_markdown_fence(response))
        score = int(data.get("score"))
        feedback = data.get("feedback")
        recommendation = data.get("recommendation")
    except (json.JSONDecodeError, TypeError, ValueError, AttributeError):
        score, feedback, recommendation = 0, None, None
    return {
        "score": min(3, max(0, score)),
        "feedback": feedback.strip() if isinstance(feedback, str) and feedback.strip() else "Ответ требует уточнения.",
        "recommendation": recommendation.strip()
        if isinstance(recommendation, str) and recommendation.strip()
        else f"Повторите практические задачи по теме «{topic}».",
    }


def generate_interview_question(
    vacancy_title: str,
    vacancy_text: str,
    requirements: list[str],
    asked_topics: list[str],
    technical: bool,
) -> tuple[str, str]:
    prompt = build_primary_screening_question_prompt(
        vacancy_title, vacancy_text, requirements, asked_topics, technical
    )
    response = _generate(prompt, use_web_search=AI_PROVIDER == "openai" and OPENAI_WEB_RESEARCH_ENABLED)
    try:
        data = json.loads(_strip_markdown_fence(response))
        topic = data.get("topic")
        question = data.get("question")
    except (json.JSONDecodeError, AttributeError):
        topic, question = None, None
    allowed_topics = [item for item in requirements if item not in asked_topics]
    if not allowed_topics:
        return "", ""
    if topic not in allowed_topics:
        topic = allowed_topics[0]
    if not isinstance(question, str) or not question.strip():
        question = (
            f"Расскажите о практическом опыте с «{topic}». "
            "На каком проекте вы это применяли и какую задачу решали лично?"
        )
    return topic, question.strip()


def analyze_vacancy_profile(title: str, description: str) -> dict:
    response = _generate(build_vacancy_profile_prompt(title, description))
    try:
        data = json.loads(_strip_markdown_fence(response))
        return VacancyProfileData.model_validate(data).model_dump()
    except (json.JSONDecodeError, ValueError, TypeError) as error:
        raise HTTPException(status_code=502, detail="AI returned an invalid vacancy profile") from error


def generate_interview_turn(context: dict, history: list[dict[str, str]]) -> str:
    response = _generate(build_interview_turn_prompt(context, history))
    try:
        data = json.loads(_strip_markdown_fence(response))
        message = data.get("message")
    except (json.JSONDecodeError, AttributeError):
        message = None
    if not isinstance(message, str) or not message.strip():
        raise HTTPException(status_code=502, detail="AI returned an invalid interview turn")
    return message.strip()


def generate_interview_report(context: dict, history: list[dict[str, str]]) -> str:
    return _generate(build_final_report_prompt(context, history))


def transcribe_audio(content: bytes, filename: str) -> str:
    if AI_PROVIDER != "openai" or not OPENAI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI transcription requires AI_PROVIDER=openai and OPENAI_API_KEY",
        )
    try:
        from openai import OpenAI

        audio = BytesIO(content)
        audio.name = filename
        result = OpenAI(api_key=OPENAI_API_KEY).audio.transcriptions.create(
            model=OPENAI_TRANSCRIPTION_MODEL,
            file=audio,
        )
    except Exception as error:
        raise HTTPException(status_code=503, detail="Audio transcription is unavailable") from error
    text = getattr(result, "text", None)
    if not isinstance(text, str) or not text.strip():
        raise HTTPException(status_code=502, detail="Audio transcription returned no text")
    return text.strip()


def _strip_markdown_fence(value: str) -> str:
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", value.strip(), flags=re.IGNORECASE)


def _normalize(value: str) -> str:
    return " ".join(value.casefold().split())


def _generate(prompt: str, use_web_search: bool = False) -> str:
    if AI_PROVIDER == "openai":
        if not OPENAI_API_KEY:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OPENAI_API_KEY is required when AI_PROVIDER=openai",
            )
        try:
            from openai import OpenAI

            request = {"model": OPENAI_MODEL, "input": prompt}
            if use_web_search:
                request["tools"] = [{"type": "web_search"}]
            answer = OpenAI(api_key=OPENAI_API_KEY).responses.create(**request).output_text
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OpenAI is unavailable. Check the API key, model, and network connection.",
            ) from error
        if not answer:
            raise HTTPException(status_code=502, detail="OpenAI returned an empty response")
        return answer

    try:
        with httpx.Client(timeout=120.0, follow_redirects=False) as client:
            response = client.post(
                f"{LOCAL_LLM_URL}/api/generate",
                json={"model": LOCAL_LLM_MODEL, "prompt": prompt, "stream": False},
            )
            response.raise_for_status()
            answer = response.json().get("response")
    except (httpx.HTTPError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Local Ollama is unavailable. Start Ollama and download the configured model.",
        ) from error

    if not answer:
        raise HTTPException(status_code=502, detail="Local Ollama returned an empty response")
    return answer
