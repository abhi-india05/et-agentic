from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.auth.passwords import validate_password_strength
from backend.utils.helpers import sanitize_text, utcnow

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AgentStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PENDING = "pending"
    RETRYING = "retrying"
    ESCALATED = "escalated"


class AgentResponse(StrictBaseModel):
    status: AgentStatus
    data: Dict[str, Any] = Field(default_factory=dict)
    reasoning: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    agent_name: str = ""
    timestamp: datetime = Field(default_factory=utcnow)
    retry_count: int = 0
    error: Optional[str] = None
    tools_used: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProductContext(StrictBaseModel):
    product_id: Optional[str] = None
    name: str = ""
    description: str = ""
    source: str = "none"

    def prompt_block(self) -> str:
        if not (self.name or self.description):
            return "No product context available."
        return f"Product: {self.name or 'Unnamed Product'}\nDescription: {self.description or 'No product description provided.'}"


class ExecutionPlan(StrictBaseModel):
    task_type: str
    allowed_tools: List[str]
    steps: List[str]
    fallback_strategy: str
    product_context: ProductContext = Field(default_factory=ProductContext)
    created_at: datetime = Field(default_factory=utcnow)


class WorkflowValidation(StrictBaseModel):
    valid: bool = True
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class Lead(StrictBaseModel):
    name: str
    title: str
    company: str
    email: Optional[str] = None
    linkedin: Optional[str] = None
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    signals: List[str] = Field(default_factory=list)
    pain_points: List[str] = Field(default_factory=list)


class EmailStep(StrictBaseModel):
    step: int = Field(ge=1, le=10)
    send_day: int = Field(ge=1, le=30)
    subject: str
    body: str
    cta: str
    angle: str


class EmailSequenceResult(StrictBaseModel):
    lead_name: str
    lead_email: str = ""
    sequence_id: str
    emails: List[EmailStep]
    sequence_strategy: str
    predicted_open_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    predicted_reply_rate: float = Field(default=0.0, ge=0.0, le=1.0)


class DealRisk(StrictBaseModel):
    deal_id: str
    company: str
    risk_level: str
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    risk_signals: List[str] = Field(default_factory=list)
    competitor_threat: bool = False
    competitor_name: Optional[str] = None
    deal_velocity: str = "stalled"
    days_inactive: int = Field(default=0, ge=0)
    recovery_strategy: str
    recommended_actions: List[str] = Field(default_factory=list)
    escalate_to_manager: bool = False
    predicted_close_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning: str = ""


class ChurnRisk(StrictBaseModel):
    account_id: str
    company: str
    churn_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    risk_factors: List[str] = Field(default_factory=list)
    retention_strategy: str
    urgency: str


class OutreachRequest(StrictBaseModel):
    company: str
    industry: str
    size: str
    website: Optional[str] = None
    notes: Optional[str] = None
    product_id: Optional[str] = None
    product_name: Optional[str] = None
    product_description: Optional[str] = None
    auto_send: bool = False

    @field_validator("company", "industry", "size")
    @classmethod
    def _required_text(cls, value: str) -> str:
        cleaned = sanitize_text(value, max_len=200)
        if not cleaned:
            raise ValueError("Field is required")
        return cleaned

    @field_validator("website")
    @classmethod
    def _website(cls, value: Optional[str]) -> Optional[str]:
        cleaned = sanitize_text(value, max_len=500)
        if not cleaned:
            return None
        if not cleaned.startswith(("http://", "https://")):
            raise ValueError("Website must start with http:// or https://")
        return cleaned

    @field_validator("notes", "product_name")
    @classmethod
    def _short_text(cls, value: Optional[str]) -> Optional[str]:
        return sanitize_text(value, max_len=500)

    @field_validator("product_description")
    @classmethod
    def _long_text(cls, value: Optional[str]) -> Optional[str]:
        return sanitize_text(value, max_len=5000)


class AuthLoginRequest(StrictBaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def _username(cls, value: str) -> str:
        cleaned = sanitize_text(value, max_len=64)
        if not cleaned:
            raise ValueError("Username is required")
        return cleaned

    @field_validator("password")
    @classmethod
    def _password(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Password is required")
        return value


class AuthRegisterRequest(StrictBaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def _username(cls, value: str) -> str:
        cleaned = sanitize_text(value, max_len=64)
        if not cleaned:
            raise ValueError("Username is required")
        return cleaned

    @field_validator("password")
    @classmethod
    def _password(cls, value: str) -> str:
        validate_password_strength(value)
        return value


class AuthRefreshRequest(StrictBaseModel):
    refresh_token: Optional[str] = None


class AuthTokenResponse(StrictBaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int
    role: str


class AuthMeResponse(StrictBaseModel):
    user_id: str
    username: str
    role: str
    is_admin: bool = False


class RiskDetectionRequest(StrictBaseModel):
    deal_ids: Optional[List[str]] = None
    check_all: bool = True
    inactivity_threshold_days: int = Field(default=10, ge=1, le=180)
    product_id: Optional[str] = None


class ChurnPredictionRequest(StrictBaseModel):
    account_ids: Optional[List[str]] = None
    top_n: int = Field(default=3, ge=1, le=20)
    product_id: Optional[str] = None


class SendEmailRequest(StrictBaseModel):
    to_email: str
    to_name: Optional[str] = ""
    subject: str
    body_text: str
    body_html: Optional[str] = None

    @field_validator("to_email")
    @classmethod
    def _email(cls, value: str) -> str:
        if not EMAIL_RE.match(value.strip()):
            raise ValueError("Invalid email address")
        return value.strip().lower()

    @field_validator("subject")
    @classmethod
    def _subject(cls, value: str) -> str:
        cleaned = sanitize_text(value, max_len=255)
        if not cleaned:
            raise ValueError("Subject is required")
        return cleaned

    @field_validator("body_text", "body_html")
    @classmethod
    def _body(cls, value: Optional[str]) -> Optional[str]:
        return sanitize_text(value, max_len=10000, allow_empty=True)


class ReviewedEmail(StrictBaseModel):
    subject: str
    body: str
    from_email: Optional[str] = None
    from_name: Optional[str] = None


class ReviewedSequence(StrictBaseModel):
    lead_email: str
    lead_name: Optional[str] = ""
    sequence_id: Optional[str] = None
    emails: List[ReviewedEmail] = Field(default_factory=list)


class SendSequencesRequest(StrictBaseModel):
    sequences: List[ReviewedSequence] = Field(default_factory=list)


class ProductCreateRequest(StrictBaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=5000)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        cleaned = sanitize_text(value, max_len=200)
        if not cleaned:
            raise ValueError("Name is required")
        return cleaned

    @field_validator("description")
    @classmethod
    def _description(cls, value: Optional[str]) -> Optional[str]:
        return sanitize_text(value, max_len=5000)


class ProductUpdateRequest(StrictBaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=5000)

    @field_validator("name")
    @classmethod
    def _name(cls, value: Optional[str]) -> Optional[str]:
        return sanitize_text(value, max_len=200)

    @field_validator("description")
    @classmethod
    def _description(cls, value: Optional[str]) -> Optional[str]:
        return sanitize_text(value, max_len=5000)


class ProductResponse(StrictBaseModel):
    product_id: str
    owner_user_id: str
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None


class SessionResponse(StrictBaseModel):
    session_id: str
    owner_user_id: str
    task_type: str
    status: str
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    request_id: Optional[str] = None


class ProspectingLeadOutput(Lead):
    why_prioritized: str = ""


class ProspectingOutput(StrictBaseModel):
    leads: List[ProspectingLeadOutput] = Field(default_factory=list)
    company_summary: str = ""
    recommended_approach: str = ""
    icp_fit_score: float = Field(default=0.0, ge=0.0, le=1.0)


class DigitalTwinObjection(StrictBaseModel):
    objection: str
    severity: str
    counter_strategy: str


class DigitalTwinProfileOutput(StrictBaseModel):
    buyer_name: str
    buyer_title: str
    buying_style: str
    primary_motivations: List[str] = Field(default_factory=list)
    top_objections: List[DigitalTwinObjection] = Field(default_factory=list)
    decision_criteria: List[str] = Field(default_factory=list)
    likely_questions: List[str] = Field(default_factory=list)
    emotional_triggers: List[str] = Field(default_factory=list)
    risk_perception: str = "medium"
    estimated_decision_timeline: str = ""
    recommended_tone: str = "consultative"
    opening_hook: str = ""
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)


class ExplainabilityDecision(StrictBaseModel):
    step: int
    agent: str
    decision: str
    why: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    impact: str


class ExplainabilityOutput(StrictBaseModel):
    executive_summary: str
    decision_chain: List[ExplainabilityDecision] = Field(default_factory=list)
    key_insights: List[str] = Field(default_factory=list)
    data_sources_used: List[str] = Field(default_factory=list)
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    limitations: List[str] = Field(default_factory=list)
    human_review_recommended: bool = False
    human_review_reasons: List[str] = Field(default_factory=list)
    impact_metrics: Dict[str, Any] = Field(default_factory=dict)
