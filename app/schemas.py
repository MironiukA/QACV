from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl


class ProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=30)


class ProfileRead(ProfileCreate):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VacancyCreate(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    description: str = Field(min_length=1)
    source_url: HttpUrl | None = None


class VacancyRead(BaseModel):
    id: int
    title: str
    description: str
    source_url: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VacancyFromUrl(BaseModel):
    source_url: HttpUrl
    title: str | None = Field(default=None, min_length=1, max_length=150)


class RequirementRead(BaseModel):
    id: int
    name: str
    category: str
    priority: str
    source_text: str | None

    model_config = ConfigDict(from_attributes=True)


class LocalLlmAnalysis(BaseModel):
    analysis: str
    verified_requirements: list[RequirementRead]
    rejected_requirements: int


class VacancyIngestionRead(BaseModel):
    vacancy: VacancyRead
    requirements: list[RequirementRead]
    ai_analysis: str | None
    ai_analysis_error: str | None
    rejected_ai_requirements: int


class PrivacyStatus(BaseModel):
    remote_vacancy_fetch_enabled: bool
    ai_provider: str
    ai_data_leaves_device: bool
    local_llm_url: str
    local_llm_model: str
    external_data_routes: list[str]


class ApplicationCreate(BaseModel):
    profile_id: int = Field(gt=0)
    vacancy_id: int = Field(gt=0)


class ApplicationRead(BaseModel):
    id: int
    profile_id: int
    vacancy_id: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApplicationMatchRead(BaseModel):
    id: int
    requirement_id: int
    requirement_name: str
    status: str
    evidence: str | None


class ClarificationQuestionRead(BaseModel):
    id: int
    requirement_id: int | None
    question: str


class MatchingResult(BaseModel):
    application_id: int
    matches: list[ApplicationMatchRead]
    clarification_questions: list[ClarificationQuestionRead]


class ClarificationAnswerInput(BaseModel):
    question_id: int = Field(gt=0)
    answer: str = Field(min_length=1, max_length=3000)
    include_in_resume: bool = False


class ClarificationAnswersCreate(BaseModel):
    answers: list[ClarificationAnswerInput] = Field(default_factory=list)
    additional_note: str | None = Field(default=None, max_length=3000)
    include_additional_note: bool = False


class RefinedAnswerRead(BaseModel):
    question_id: int
    raw_answer: str
    refined_answer: str
    resume_section: str
    include_in_resume: bool


class ClarificationAnswersSaved(BaseModel):
    saved_answers: int
    processed_answers: list[RefinedAnswerRead]


class ResumeVersionRead(BaseModel):
    id: int
    application_id: int
    content: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResumeVersionUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=100000)


class ScreeningAnswerCreate(BaseModel):
    answer: str = Field(min_length=1, max_length=5000)


class InterviewStep(BaseModel):
    session_id: int
    stage: str
    status: str
    question: str | None
    completed: bool
    passed: bool | None
    recommendations: list[str] = Field(default_factory=list)


class VacancyProfileData(BaseModel):
    role: str
    level: str
    profile: list[str] = Field(default_factory=list)
    must_have: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    leadership: list[str] = Field(default_factory=list)
    high_risk_gaps: list[str] = Field(default_factory=list)
    domain: str = "other"


class InterviewChatStart(BaseModel):
    mode: str = Field(default="FULL_SCREEN", pattern="^(HR_SCREEN|TECH_SCREEN|FULL_SCREEN|HARD_MODE)$")


class InterviewChatMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=10000)


class InterviewChatTurn(BaseModel):
    session_id: int
    message: str
    mode: str


class InterviewFinalReport(BaseModel):
    session_id: int
    report: str


class TranscriptionRead(BaseModel):
    text: str


class ResumeRead(BaseModel):
    id: int
    profile_id: int
    original_filename: str
    content_type: str | None
    extracted_text: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
