from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import AI_PROVIDER, REMOTE_VACANCY_FETCH_ENABLED
from app.local_llm import (
    analyze_vacancy,
    analyze_vacancy_profile,
    evidence_backed_matches,
    evidence_backed_requirements,
    evaluate_screening_answer,
    generate_interview_question,
    generate_interview_report,
    generate_interview_turn,
    transcribe_audio,
    generate_tailored_resume,
    local_llm_info,
    match_resume_to_requirements,
    refine_candidate_answer,
    validate_local_llm_url,
)
from app.models import (
    Application,
    ApplicationMatch,
    ClarificationAnswer,
    ClarificationQuestion,
    MasterProfile,
    ResumeFile,
    ResumeVersion,
    InterviewMessage,
    InterviewSession,
    Vacancy,
    VacancyAnalysis,
    VacancyProfile,
    VacancyRequirement,
)
from app.parsers import extract_known_requirements, fetch_vacancy_page, save_and_extract_resume
from app.pdf_export import create_resume_pdf
from app.schemas import (
    ApplicationCreate,
    ApplicationMatchRead,
    ApplicationRead,
    ClarificationAnswersCreate,
    ClarificationAnswersSaved,
    ClarificationQuestionRead,
    LocalLlmAnalysis,
    MatchingResult,
    PrivacyStatus,
    ProfileCreate,
    ProfileRead,
    RefinedAnswerRead,
    RequirementRead,
    ResumeRead,
    ResumeVersionRead,
    ResumeVersionUpdate,
    InterviewStep,
    ScreeningAnswerCreate,
    VacancyCreate,
    VacancyFromUrl,
    VacancyIngestionRead,
    VacancyRead,
    VacancyProfileData,
    InterviewChatStart,
    InterviewChatMessageCreate,
    InterviewChatTurn,
    InterviewFinalReport,
    TranscriptionRead,
)

app = FastAPI(title="QACV API", version="0.1.0")
if AI_PROVIDER == "ollama":
    validate_local_llm_url(local_llm_info()["url"])
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def landing_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/interview/{application_id}", include_in_schema=False)
def interview_page(application_id: int) -> FileResponse:
    return FileResponse(STATIC_DIR / "interview.html")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/privacy", response_model=PrivacyStatus)
def privacy_status() -> PrivacyStatus:
    llm = local_llm_info()
    external_routes = ["POST /vacancies/from-url"] if REMOTE_VACANCY_FETCH_ENABLED else []
    if AI_PROVIDER == "openai":
        external_routes.append("AI prompts and answers are sent to OpenAI")
    return PrivacyStatus(
        remote_vacancy_fetch_enabled=REMOTE_VACANCY_FETCH_ENABLED,
        ai_provider=AI_PROVIDER,
        ai_data_leaves_device=AI_PROVIDER == "openai",
        local_llm_url=llm["url"],
        local_llm_model=llm["model"],
        external_data_routes=external_routes,
    )


@app.post("/profiles", response_model=ProfileRead, status_code=status.HTTP_201_CREATED)
def create_profile(payload: ProfileCreate, db: Session = Depends(get_db)) -> MasterProfile:
    existing = db.scalar(select(MasterProfile).where(MasterProfile.email == payload.email))
    if existing:
        existing.name = payload.name
        existing.phone = payload.phone
        db.commit()
        db.refresh(existing)
        return existing

    profile = MasterProfile(**payload.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@app.post("/profiles/{profile_id}/resume", response_model=ResumeRead, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    profile_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ResumeFile:
    if not db.get(MasterProfile, profile_id):
        raise HTTPException(status_code=404, detail="Profile not found")

    storage_path, extracted_text = await save_and_extract_resume(file)
    resume = ResumeFile(
        profile_id=profile_id,
        original_filename=file.filename or "resume",
        content_type=file.content_type,
        storage_path=storage_path,
        extracted_text=extracted_text,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


@app.post("/vacancies", response_model=VacancyRead, status_code=status.HTTP_201_CREATED)
def create_vacancy(payload: VacancyCreate, db: Session = Depends(get_db)) -> Vacancy:
    vacancy = Vacancy(**payload.model_dump(mode="json"))
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)
    return vacancy


@app.post("/vacancies/from-url", response_model=VacancyIngestionRead, status_code=status.HTTP_201_CREATED)
def create_vacancy_from_url(payload: VacancyFromUrl, db: Session = Depends(get_db)) -> VacancyIngestionRead:
    if not REMOTE_VACANCY_FETCH_ENABLED:
        raise HTTPException(status_code=403, detail="Remote vacancy fetching is disabled")
    page_title, description = fetch_vacancy_page(str(payload.source_url))
    vacancy = Vacancy(
        title=payload.title or page_title,
        description=description,
        source_url=str(payload.source_url),
    )
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)

    requirement_data = extract_known_requirements(vacancy.description)

    ai_analysis = None
    ai_analysis_error = None
    rejected_ai_requirements = 0
    try:
        ai_analysis = analyze_vacancy(vacancy.description)
        verified_requirements, rejected_ai_requirements = evidence_backed_requirements(
            ai_analysis, vacancy.description
        )
        requirement_data.extend(verified_requirements)
        db.add(
            VacancyAnalysis(
                vacancy_id=vacancy.id,
                model_name=local_llm_info()["model"],
                content=ai_analysis,
            )
        )
    except HTTPException as error:
        ai_analysis_error = str(error.detail)

    requirements = _save_requirements(db, vacancy.id, requirement_data)
    db.commit()
    db.refresh(vacancy)
    return VacancyIngestionRead(
        vacancy=VacancyRead.model_validate(vacancy),
        requirements=[RequirementRead.model_validate(requirement) for requirement in requirements],
        ai_analysis=ai_analysis,
        ai_analysis_error=ai_analysis_error,
        rejected_ai_requirements=rejected_ai_requirements,
    )


@app.post("/vacancies/{vacancy_id}/requirements/extract", response_model=list[RequirementRead])
def extract_requirements(vacancy_id: int, db: Session = Depends(get_db)) -> list[VacancyRequirement]:
    vacancy = db.get(Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")

    existing = db.scalars(
        select(VacancyRequirement).where(VacancyRequirement.vacancy_id == vacancy_id)
    ).all()
    if existing:
        return existing

    requirements = _save_requirements(db, vacancy_id, extract_known_requirements(vacancy.description))
    db.commit()
    return requirements


@app.post("/vacancies/{vacancy_id}/requirements/ai-analysis", response_model=LocalLlmAnalysis)
def analyze_requirements_with_local_llm(vacancy_id: int, db: Session = Depends(get_db)) -> LocalLlmAnalysis:
    vacancy = db.get(Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    analysis = analyze_vacancy(vacancy.description)
    verified_data, rejected_requirements = evidence_backed_requirements(analysis, vacancy.description)
    verified_requirements = _save_requirements(db, vacancy_id, verified_data)
    db.add(
        VacancyAnalysis(
            vacancy_id=vacancy.id,
            model_name=local_llm_info()["model"],
            content=analysis,
        )
    )
    db.commit()
    return LocalLlmAnalysis(
        analysis=analysis,
        verified_requirements=[RequirementRead.model_validate(item) for item in verified_requirements],
        rejected_requirements=rejected_requirements,
    )


def _save_requirements(
    db: Session, vacancy_id: int, requirement_data: list[dict[str, str]]
) -> list[VacancyRequirement]:
    existing = db.scalars(
        select(VacancyRequirement).where(VacancyRequirement.vacancy_id == vacancy_id)
    ).all()
    names = {requirement.name.casefold() for requirement in existing}
    created = []
    for requirement in requirement_data:
        if requirement["name"].casefold() in names:
            continue
        record = VacancyRequirement(vacancy_id=vacancy_id, **requirement)
        db.add(record)
        created.append(record)
        names.add(record.name.casefold())
    db.flush()
    return [*existing, *created]


@app.post("/applications", response_model=ApplicationRead, status_code=status.HTTP_201_CREATED)
def create_application(payload: ApplicationCreate, db: Session = Depends(get_db)) -> Application:
    if not db.get(MasterProfile, payload.profile_id):
        raise HTTPException(status_code=404, detail="Profile not found")
    if not db.get(Vacancy, payload.vacancy_id):
        raise HTTPException(status_code=404, detail="Vacancy not found")

    application = Application(**payload.model_dump())
    db.add(application)
    db.commit()
    db.refresh(application)
    return application


@app.post("/applications/{application_id}/match", response_model=MatchingResult)
def match_application(application_id: int, db: Session = Depends(get_db)) -> MatchingResult:
    application = db.get(Application, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    resume = db.scalar(
        select(ResumeFile)
        .where(ResumeFile.profile_id == application.profile_id)
        .order_by(ResumeFile.created_at.desc(), ResumeFile.id.desc())
    )
    if not resume:
        raise HTTPException(status_code=422, detail="Upload a resume before matching")

    requirements = db.scalars(
        select(VacancyRequirement).where(VacancyRequirement.vacancy_id == application.vacancy_id)
    ).all()
    if not requirements:
        raise HTTPException(status_code=422, detail="Analyze vacancy requirements before matching")

    requirement_payload = [
        {"id": requirement.id, "name": requirement.name, "source_text": requirement.source_text}
        for requirement in requirements
    ]
    analysis = match_resume_to_requirements(resume.extracted_text, requirement_payload)
    decisions = evidence_backed_matches(
        analysis, resume.extracted_text, {requirement.id for requirement in requirements}
    )

    db.execute(delete(ApplicationMatch).where(ApplicationMatch.application_id == application_id))
    db.execute(delete(ClarificationQuestion).where(ClarificationQuestion.application_id == application_id))

    matches = []
    questions = []
    for requirement in requirements:
        decision = decisions[requirement.id]
        match = ApplicationMatch(
            application_id=application_id,
            requirement_id=requirement.id,
            status=decision["status"],
            evidence=decision["evidence"],
        )
        db.add(match)
        matches.append((match, requirement.name))
        if decision["status"] == "needs_clarification":
            question = ClarificationQuestion(
                application_id=application_id,
                requirement_id=requirement.id,
                question=_clarification_question(requirement.name),
            )
            db.add(question)
            questions.append(question)
    db.commit()
    for match, _ in matches:
        db.refresh(match)
    for question in questions:
        db.refresh(question)

    return MatchingResult(
        application_id=application_id,
        matches=[
            ApplicationMatchRead(
                id=match.id,
                requirement_id=match.requirement_id,
                requirement_name=name,
                status=match.status,
                evidence=match.evidence,
            )
            for match, name in matches
        ],
        clarification_questions=[
            ClarificationQuestionRead(
                id=question.id,
                requirement_id=question.requirement_id,
                question=question.question,
            )
            for question in questions
        ],
    )


def _clarification_question(requirement_name: str) -> str:
    return (
        f"В вакансии требуется «{requirement_name}», но в резюме это не подтверждено. "
        "Был ли у вас такой опыт? Укажите проект, конкретные задачи и период использования."
    )


@app.post(
    "/applications/{application_id}/clarification-answers",
    response_model=ClarificationAnswersSaved,
)
def save_clarification_answers(
    application_id: int,
    payload: ClarificationAnswersCreate,
    db: Session = Depends(get_db),
) -> ClarificationAnswersSaved:
    if not db.get(Application, application_id):
        raise HTTPException(status_code=404, detail="Application not found")

    questions = db.scalars(
        select(ClarificationQuestion).where(ClarificationQuestion.application_id == application_id)
    ).all()
    questions_by_id = {question.id: question for question in questions}
    answer_ids = {answer.question_id for answer in payload.answers}
    if not answer_ids.issubset(questions_by_id):
        raise HTTPException(status_code=422, detail="Question does not belong to this application")

    if answer_ids:
        db.execute(delete(ClarificationAnswer).where(ClarificationAnswer.question_id.in_(answer_ids)))
    saved_answers = 0
    processed_answers = []
    for answer in payload.answers:
        refined = refine_candidate_answer(questions_by_id[answer.question_id].question, answer.answer.strip())
        db.add(
            ClarificationAnswer(
                question_id=answer.question_id,
                raw_answer=answer.answer.strip(),
                answer=refined["refined_answer"],
                resume_section=refined["resume_section"],
                confirmed_for_profile=answer.include_in_resume,
            )
        )
        processed_answers.append(
            RefinedAnswerRead(
                question_id=answer.question_id,
                raw_answer=answer.answer.strip(),
                refined_answer=refined["refined_answer"],
                resume_section=refined["resume_section"],
                include_in_resume=answer.include_in_resume,
            )
        )
        saved_answers += 1

    if payload.additional_note and payload.additional_note.strip():
        additional_question = next(
            (question for question in questions if question.requirement_id is None), None
        )
        if not additional_question:
            additional_question = ClarificationQuestion(
                application_id=application_id,
                requirement_id=None,
                question="Дополнительная информация кандидата",
            )
            db.add(additional_question)
            db.flush()
        db.execute(
            delete(ClarificationAnswer).where(ClarificationAnswer.question_id == additional_question.id)
        )
        refined = refine_candidate_answer(additional_question.question, payload.additional_note.strip())
        db.add(
            ClarificationAnswer(
                question_id=additional_question.id,
                raw_answer=payload.additional_note.strip(),
                answer=refined["refined_answer"],
                resume_section=refined["resume_section"],
                confirmed_for_profile=payload.include_additional_note,
            )
        )
        processed_answers.append(
            RefinedAnswerRead(
                question_id=additional_question.id,
                raw_answer=payload.additional_note.strip(),
                refined_answer=refined["refined_answer"],
                resume_section=refined["resume_section"],
                include_in_resume=payload.include_additional_note,
            )
        )
        saved_answers += 1

    db.commit()
    return ClarificationAnswersSaved(saved_answers=saved_answers, processed_answers=processed_answers)


@app.post("/applications/{application_id}/resume/generate", response_model=ResumeVersionRead)
def generate_resume_version(application_id: int, db: Session = Depends(get_db)) -> ResumeVersion:
    application = db.get(Application, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    resume = db.scalar(
        select(ResumeFile)
        .where(ResumeFile.profile_id == application.profile_id)
        .order_by(ResumeFile.created_at.desc(), ResumeFile.id.desc())
    )
    if not resume:
        raise HTTPException(status_code=422, detail="Upload a resume before generating a new version")

    rows = db.execute(
        select(
            ClarificationAnswer.answer,
            ClarificationQuestion.question,
            ClarificationAnswer.resume_section,
        )
        .join(ClarificationQuestion, ClarificationQuestion.id == ClarificationAnswer.question_id)
        .where(
            ClarificationQuestion.application_id == application_id,
            ClarificationAnswer.confirmed_for_profile.is_(True),
        )
    ).all()
    confirmed_answers = [
        {"question": question, "answer": answer, "resume_section": section or "experience"}
        for answer, question, section in rows
    ]
    content = generate_tailored_resume(resume.extracted_text, confirmed_answers)
    version = ResumeVersion(application_id=application_id, content=content)
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


@app.patch("/resume-versions/{resume_version_id}", response_model=ResumeVersionRead)
def update_resume_version(
    resume_version_id: int,
    payload: ResumeVersionUpdate,
    db: Session = Depends(get_db),
) -> ResumeVersion:
    version = db.get(ResumeVersion, resume_version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Resume version not found")
    version.content = payload.content.strip()
    db.commit()
    db.refresh(version)
    return version


@app.get("/resume-versions/{resume_version_id}/export.pdf")
def export_resume_pdf(resume_version_id: int, db: Session = Depends(get_db)) -> Response:
    version = db.get(ResumeVersion, resume_version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Resume version not found")
    try:
        pdf = create_resume_pdf(version.content)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="resume-{resume_version_id}.pdf"'},
    )


@app.post("/applications/{application_id}/screening/start", response_model=InterviewStep)
def start_screening(application_id: int, db: Session = Depends(get_db)) -> InterviewStep:
    if not db.get(Application, application_id):
        raise HTTPException(status_code=404, detail="Application not found")
    session = db.scalar(
        select(InterviewSession)
        .where(
            InterviewSession.application_id == application_id,
            InterviewSession.stage == "screening",
            InterviewSession.status == "active",
        )
        .order_by(InterviewSession.id.desc())
    )
    if session:
        question = db.scalar(
            select(InterviewMessage.content)
            .where(InterviewMessage.session_id == session.id, InterviewMessage.role == "interviewer")
            .order_by(InterviewMessage.id.desc())
        )
        return InterviewStep(
            session_id=session.id,
            stage=session.stage,
            status=session.status,
            question=question,
            completed=False,
            passed=None,
        )

    requirements = _screening_requirements(application_id, db)
    if not requirements:
        raise HTTPException(status_code=422, detail="Analyze vacancy requirements before screening")
    session = InterviewSession(application_id=application_id, stage="screening", status="active")
    db.add(session)
    db.flush()
    topic, question = _next_interview_question(application_id, requirements, [], technical=False, db=db)
    _add_interviewer_question(db, session.id, topic, question)
    db.commit()
    return InterviewStep(
        session_id=session.id,
        stage=session.stage,
        status=session.status,
        question=question,
        completed=False,
        passed=None,
    )


@app.post("/screenings/{session_id}/answers", response_model=InterviewStep)
@app.post("/interviews/{session_id}/answers", response_model=InterviewStep)
def answer_interview(
    session_id: int,
    payload: ScreeningAnswerCreate,
    db: Session = Depends(get_db),
) -> InterviewStep:
    session = db.get(InterviewSession, session_id)
    if not session or session.stage not in {"screening", "technical"}:
        raise HTTPException(status_code=404, detail="Interview session not found")
    if session.status != "active":
        raise HTTPException(status_code=409, detail="Screening is already complete")

    question = db.scalar(
        select(InterviewMessage)
        .where(InterviewMessage.session_id == session_id, InterviewMessage.role == "interviewer")
        .order_by(InterviewMessage.id.desc())
    )
    if not question:
        raise HTTPException(status_code=409, detail="Screening question not found")
    evaluation = evaluate_screening_answer(question.topic or "Требование вакансии", question.content, payload.answer)
    db.add(
        InterviewMessage(
            session_id=session_id,
            role="candidate",
            topic=question.topic,
            content=payload.answer.strip(),
            score=evaluation["score"],
            feedback=evaluation["feedback"],
        )
    )
    db.flush()

    requirements = _screening_requirements(session.application_id, db)
    asked_topics = set(
        db.scalars(
            select(InterviewMessage.topic).where(
                InterviewMessage.session_id == session_id,
                InterviewMessage.role == "interviewer",
            )
        ).all()
    )
    technical = session.stage == "technical"
    if len(asked_topics) < len(requirements):
        topic, next_question = _next_interview_question(
            session.application_id, requirements, list(asked_topics), technical=technical, db=db
        )
        _add_interviewer_question(db, session_id, topic, next_question)
        db.commit()
        return InterviewStep(
            session_id=session_id,
            stage=session.stage,
            status=session.status,
            question=next_question,
            completed=False,
            passed=None,
        )

    candidate_answers = db.scalars(
        select(InterviewMessage).where(
            InterviewMessage.session_id == session_id,
            InterviewMessage.role == "candidate",
        )
    ).all()
    average_score = sum(message.score or 0 for message in candidate_answers) / max(1, len(candidate_answers))
    passed = average_score >= 2
    recommendations = [
        f"{message.topic}: {message.feedback}"
        for message in candidate_answers
        if (message.score or 0) < 2
    ]
    if not recommendations:
        recommendations = ["Сильная база для следующего этапа. Подготовьте реальные примеры проектов."]
    session.status = "completed" if technical else "passed" if passed else "needs_preparation"
    session.passed = passed
    session.feedback = "\n".join(recommendations)
    db.commit()
    return InterviewStep(
        session_id=session.id,
        stage=session.stage,
        status=session.status,
        question=None,
        completed=True,
        passed=passed if not technical else None,
        recommendations=recommendations,
    )


@app.post("/applications/{application_id}/technical/start", response_model=InterviewStep)
def start_technical_interview(application_id: int, db: Session = Depends(get_db)) -> InterviewStep:
    screening = db.scalar(
        select(InterviewSession)
        .where(
            InterviewSession.application_id == application_id,
            InterviewSession.stage == "screening",
            InterviewSession.passed.is_(True),
        )
        .order_by(InterviewSession.id.desc())
    )
    if not screening:
        raise HTTPException(status_code=409, detail="Pass screening before starting the technical interview")
    requirements = _screening_requirements(application_id, db)
    if not requirements:
        raise HTTPException(status_code=422, detail="Analyze vacancy requirements before the interview")
    session = InterviewSession(application_id=application_id, stage="technical", status="active")
    db.add(session)
    db.flush()
    topic, question = _next_interview_question(application_id, requirements, [], technical=True, db=db)
    _add_interviewer_question(db, session.id, topic, question)
    db.commit()
    return InterviewStep(
        session_id=session.id,
        stage=session.stage,
        status=session.status,
        question=question,
        completed=False,
        passed=None,
    )


def _screening_requirements(application_id: int, db: Session) -> list[VacancyRequirement]:
    application = db.get(Application, application_id)
    if not application:
        return []
    requirements = db.scalars(
        select(VacancyRequirement).where(VacancyRequirement.vacancy_id == application.vacancy_id)
    ).all()
    requirements.sort(key=lambda item: (item.priority != "must_have", item.id))
    return requirements[:4]


def _add_interviewer_question(db: Session, session_id: int, topic: str, question: str) -> None:
    db.add(
        InterviewMessage(
            session_id=session_id,
            role="interviewer",
            topic=topic,
            content=question,
        )
    )


def _screening_question(requirement_name: str) -> str:
    return (
        f"Расскажите о практическом опыте с «{requirement_name}». "
        "На каком проекте вы это применяли и какую задачу решали лично?"
    )


def _technical_question(requirement_name: str) -> str:
    return (
        f"Технический вопрос по теме «{requirement_name}»: опишите, как бы вы подошли к реальной задаче "
        "из проекта, включая проверку результата и возможные риски."
    )


def _next_interview_question(
    application_id: int,
    requirements: list[VacancyRequirement],
    asked_topics: list[str],
    technical: bool,
    db: Session,
) -> tuple[str, str]:
    application = db.get(Application, application_id)
    vacancy = db.get(Vacancy, application.vacancy_id) if application else None
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    topic, question = generate_interview_question(
        vacancy.title,
        vacancy.description,
        [requirement.name for requirement in requirements],
        asked_topics,
        technical,
    )
    if not question:
        raise HTTPException(status_code=422, detail="No remaining interview topics")
    return topic, question


@app.post("/applications/{application_id}/interview-chat/start", response_model=InterviewChatTurn)
def start_interview_chat(
    application_id: int,
    payload: InterviewChatStart,
    db: Session = Depends(get_db),
) -> InterviewChatTurn:
    context = _interview_context(application_id, db)
    session = InterviewSession(
        application_id=application_id,
        stage="chat",
        mode=payload.mode,
        status="active",
    )
    db.add(session)
    db.flush()
    context["interview_mode"] = payload.mode
    message = generate_interview_turn(context, [])
    db.add(InterviewMessage(session_id=session.id, role="interviewer", content=message))
    db.commit()
    return InterviewChatTurn(session_id=session.id, message=message, mode=payload.mode)


@app.post("/interview-chat/{session_id}/messages", response_model=InterviewChatTurn)
def send_interview_chat_message(
    session_id: int,
    payload: InterviewChatMessageCreate,
    db: Session = Depends(get_db),
) -> InterviewChatTurn:
    session = db.get(InterviewSession, session_id)
    if not session or session.stage != "chat":
        raise HTTPException(status_code=404, detail="Interview chat session not found")
    if session.status != "active":
        raise HTTPException(status_code=409, detail="Interview chat is complete")
    db.add(InterviewMessage(session_id=session.id, role="candidate", content=payload.content.strip()))
    db.flush()
    context = _interview_context(session.application_id, db)
    context["interview_mode"] = session.mode or "FULL_SCREEN"
    message = generate_interview_turn(context, _interview_history(session.id, db))
    db.add(InterviewMessage(session_id=session.id, role="interviewer", content=message))
    db.commit()
    return InterviewChatTurn(session_id=session.id, message=message, mode=session.mode or "FULL_SCREEN")


@app.post("/interview-chat/{session_id}/complete", response_model=InterviewFinalReport)
def complete_interview_chat(session_id: int, db: Session = Depends(get_db)) -> InterviewFinalReport:
    session = db.get(InterviewSession, session_id)
    if not session or session.stage != "chat":
        raise HTTPException(status_code=404, detail="Interview chat session not found")
    context = _interview_context(session.application_id, db)
    context["interview_mode"] = session.mode or "FULL_SCREEN"
    report = generate_interview_report(context, _interview_history(session.id, db))
    session.status = "completed"
    session.feedback = report
    db.commit()
    return InterviewFinalReport(session_id=session.id, report=report)


@app.post("/interview-chat/{session_id}/transcribe", response_model=TranscriptionRead)
async def transcribe_interview_audio(
    session_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> TranscriptionRead:
    session = db.get(InterviewSession, session_id)
    if not session or session.stage != "chat" or session.status != "active":
        raise HTTPException(status_code=404, detail="Active interview chat session not found")
    content = await file.read()
    if not content or len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio must be between 1 byte and 20 MB")
    return TranscriptionRead(text=transcribe_audio(content, file.filename or "answer.webm"))


@app.get("/vacancies/{vacancy_id}/profile", response_model=VacancyProfileData)
def get_vacancy_profile(vacancy_id: int, db: Session = Depends(get_db)) -> VacancyProfileData:
    vacancy = db.get(Vacancy, vacancy_id)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found")
    return VacancyProfileData.model_validate(_vacancy_profile(vacancy, db))


def _interview_context(application_id: int, db: Session) -> dict:
    application = db.get(Application, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    vacancy = db.get(Vacancy, application.vacancy_id)
    profile = db.get(MasterProfile, application.profile_id)
    if not vacancy or not profile:
        raise HTTPException(status_code=404, detail="Application data not found")
    resume = db.scalar(
        select(ResumeFile)
        .where(ResumeFile.profile_id == profile.id)
        .order_by(ResumeFile.created_at.desc(), ResumeFile.id.desc())
    )
    requirements = db.scalars(
        select(VacancyRequirement).where(VacancyRequirement.vacancy_id == vacancy.id)
    ).all()
    matches = db.scalars(
        select(ApplicationMatch).where(
            ApplicationMatch.application_id == application.id,
            ApplicationMatch.status == "needs_clarification",
        )
    ).all()
    requirements_by_id = {item.id: item.name for item in requirements}
    return {
        "vacancy": {"title": vacancy.title, "description": vacancy.description[:30000]},
        "vacancy_analysis": _vacancy_profile(vacancy, db),
        "candidate_resume": resume.extracted_text[:20000] if resume else "Resume not provided",
        "master_profile": {"name": profile.name, "email": profile.email, "phone": profile.phone},
        "known_gaps": [requirements_by_id.get(match.requirement_id, "Unknown requirement") for match in matches],
    }


def _vacancy_profile(vacancy: Vacancy, db: Session) -> dict:
    stored = db.scalar(select(VacancyProfile).where(VacancyProfile.vacancy_id == vacancy.id))
    if stored:
        return stored.content
    content = analyze_vacancy_profile(vacancy.title, vacancy.description)
    db.add(VacancyProfile(vacancy_id=vacancy.id, content=content))
    db.flush()
    return content


def _interview_history(session_id: int, db: Session) -> list[dict[str, str]]:
    messages = db.scalars(
        select(InterviewMessage).where(InterviewMessage.session_id == session_id).order_by(InterviewMessage.id)
    ).all()
    return [
        {"role": "assistant" if message.role == "interviewer" else "user", "content": message.content}
        for message in messages
    ]
