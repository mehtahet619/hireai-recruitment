from typing import Any
from datetime import datetime

from pydantic import BaseModel, Field, EmailStr


# ---------- Employer Auth ----------

class EmployerRegisterRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)
    company_name: str = Field(..., min_length=1)


class EmployerLoginRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)


# ---------- Jobs ----------

class JobCreateRequest(BaseModel):
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=10)
    location: str = "Remote"
    employment_type: str = "full-time"


class JobUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    location: str | None = None
    employment_type: str | None = None
    is_active: bool | None = None


# ---------- Applications ----------

class ApplicationSubmitRequest(BaseModel):
    job_id: str = Field(..., min_length=1)
    candidate_name: str = Field(..., min_length=1)
    candidate_email: str = Field(..., min_length=3)
    resume: str = Field(..., min_length=10)


class GoogleAuthRequest(BaseModel):
    credential: str = Field(..., min_length=1)  # Google ID token
    company_name: str | None = None  # optional, used on first sign-in


class JDParseRequest(BaseModel):
    job_description: str = Field(..., min_length=1)


class ResumeAnalyzeRequest(BaseModel):
    resume: str = Field(..., min_length=1)
    requirements: dict[str, Any] = Field(..., description="Output of /jd/parse")
    candidate_id: str = "cand_1"


class QuestionRequest(BaseModel):
    requirements: dict[str, Any]
    candidate_id: str | None = None


class ScoreRequest(BaseModel):
    resume_analysis: dict[str, Any]
    interview_assessments: dict[str, Any] | None = None
    recruiter_weights: dict[str, Any] | None = None


class FeedbackRequest(BaseModel):
    score: dict[str, Any]
    resume_analysis: dict[str, Any] | None = None
    authorize_candidate_message: bool = False


class PipelineRequest(BaseModel):
    job_description: str = Field(..., min_length=1)
    resume: str = Field(..., min_length=1)
    candidate_id: str = "cand_1"


class PipelineResponse(BaseModel):
    requirements: dict[str, Any]
    resume_analysis: dict[str, Any]
    questions: dict[str, Any]
    score: dict[str, Any]
    feedback: dict[str, Any]
    mock: bool


class InterviewStartRequest(BaseModel):
    job_description: str = Field(..., min_length=1)
    resume: str = Field(..., min_length=1)
    candidate_id: str = "cand_1"


class InterviewMessageRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)


class InterviewCompleteRequest(BaseModel):
    session_id: str = Field(..., min_length=1)


class InterviewSaveReviewRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    transcript: list[dict[str, Any]] = Field(default_factory=list)
    score: dict[str, Any] | None = None
    feedback: dict[str, Any] | None = None
    handoff: dict[str, Any] | None = None
    preflight: dict[str, Any] | None = None
    has_video: bool = False


class InterviewUpdateTabChangeRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    warnings_count: int = Field(..., ge=0)


class BanCheckRequest(BaseModel):
    candidate_id: str = Field(..., min_length=1)


class BanUserRequest(BaseModel):
    candidate_id: str = Field(..., min_length=1)
    reason: str = Field(default="Too many tab changes")


class UnbanUserRequest(BaseModel):
    candidate_id: str = Field(..., min_length=1)


# ---------- Payments ----------

class CreateOrderRequest(BaseModel):
    plan: str = Field(..., pattern="^(starter|growth)$")


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    plan: str


# ---------- Signal Management ----------

class SignalIngestRequest(BaseModel):
    engineer_id: str = Field(..., min_length=1)
    signal_type: str = Field(..., min_length=1)
    payload: dict[str, Any]
    source_system: str = Field(..., min_length=1)
    employer_id: str = Field(..., min_length=1)
    consent_version: str = "1.0"


class SignalResponse(BaseModel):
    signal_id: str
    pseudonymous_id: str
    signal_type: str
    payload: dict[str, Any]
    source_system: str
    collected_at: str
    consent_version: str
    employer_id: str
    revoked: bool = False


# ---------- Onboarding ----------

class OnboardingTaskSchema(BaseModel):
    title: str
    description: str
    due_offset_days: int
    assigned_role: str


class OnboardingTemplateCreateRequest(BaseModel):
    name: str
    tasks: list[OnboardingTaskSchema]


class OnboardingTemplateUpdateRequest(BaseModel):
    name: str | None = None
    tasks: list[OnboardingTaskSchema] | None = None


class OnboardingPlanCreateRequest(BaseModel):
    engineer_id: str
    employer_id: str
    template_id: str
    hire_date: str  # YYYY-MM-DD


# ---------- Payroll ----------

class CompensationCreateRequest(BaseModel):
    engineer_id: str
    base_salary: float
    currency: str
    pay_frequency: str  # monthly | bi-weekly | weekly
    effective_date: str  # YYYY-MM-DD
    deductions: list[dict] = []


# ---------- Performance ----------

class PerformanceCycleCreateRequest(BaseModel):
    name: str
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    participant_ids: list[str] = []
    review_template: dict = {}
    promotion_threshold: float = 0.75  # score above which to send notification


class PerformanceReviewCreateRequest(BaseModel):
    reviewer_id: str
    reviewee_id: str
    form_responses: dict
