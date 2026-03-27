from pydantic import BaseModel, Field, field_validator
from typing import Any, Dict, List, Optional
from enum import Enum
from datetime import datetime

from backend.config.settings import settings

def _clean_optional_text(value: Optional[str], *, max_len: int) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        return str(value)
    cleaned = " ".join(value.split()).strip()
    if not cleaned:
        return None
    return cleaned[:max_len]


class AgentStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PENDING = "pending"
    RETRYING = "retrying"
    ESCALATED = "escalated"


class AgentResponse(BaseModel):
    status: AgentStatus
    data: Dict[str, Any] = Field(default_factory=dict)
    reasoning: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    agent_name: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    retry_count: int = 0
    error: Optional[str] = None


class Lead(BaseModel):
    name: str
    title: str
    company: str
    email: Optional[str] = None
    linkedin: Optional[str] = None
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    signals: List[str] = Field(default_factory=list)


class EmailSequence(BaseModel):
    lead: Lead
    emails: List[Dict[str, str]]
    sequence_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DealRisk(BaseModel):
    deal_id: str
    company: str
    risk_level: str
    risk_signals: List[str]
    days_inactive: int
    recovery_strategy: str
    confidence: float


class ChurnRisk(BaseModel):
    account_id: str
    company: str
    churn_probability: float
    risk_factors: List[str]
    retention_strategy: str
    urgency: str


class OutreachRequest(BaseModel):
    company: str
    industry: str
    size: str
    website: Optional[str] = None
    notes: Optional[str] = None
    product_name: Optional[str] = None
    product_description: Optional[str] = None
    auto_send: bool = False

    @field_validator("company", "industry", "size")
    @classmethod
    def _required_text(cls, v: str) -> str:
        cleaned = _clean_optional_text(v, max_len=200)
        if not cleaned:
            raise ValueError("Field is required")
        return cleaned

    @field_validator("website", "notes", "product_name")
    @classmethod
    def _optional_short_text(cls, v: Optional[str]) -> Optional[str]:
        return _clean_optional_text(v, max_len=500)

    @field_validator("product_description")
    @classmethod
    def _optional_description(cls, v: Optional[str]) -> Optional[str]:
        return _clean_optional_text(v, max_len=5000)


class AuthLoginRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def _username(cls, v: str) -> str:
        cleaned = _clean_optional_text(v, max_len=64)
        if not cleaned:
            raise ValueError("Username is required")
        return cleaned

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        min_len = int(getattr(settings, "auth_password_min_length", 8) or 8)
        if not isinstance(v, str) or len(v) < min_len:
            raise ValueError(f"Password must be at least {min_len} characters")
        return v


class AuthRegisterRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def _reg_username(cls, v: str) -> str:
        cleaned = _clean_optional_text(v, max_len=64)
        if not cleaned:
            raise ValueError("Username is required")
        return cleaned

    @field_validator("password")
    @classmethod
    def _reg_password(cls, v: str) -> str:
        min_len = int(getattr(settings, "auth_password_min_length", 8) or 8)
        if not isinstance(v, str) or len(v) < min_len:
            raise ValueError(f"Password must be at least {min_len} characters")
        return v


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AuthMeResponse(BaseModel):
    user_id: str
    username: str
    is_admin: bool = False


class RiskDetectionRequest(BaseModel):
    deal_ids: Optional[List[str]] = None
    check_all: bool = True
    inactivity_threshold_days: int = 10


class ChurnPredictionRequest(BaseModel):
    account_ids: Optional[List[str]] = None
    top_n: int = 3


class SendEmailRequest(BaseModel):
    to_email: str
    to_name: Optional[str] = ""
    subject: str
    body_text: str
    body_html: Optional[str] = None


class ReviewedEmail(BaseModel):
    subject: str
    body: str
    from_email: Optional[str] = None
    from_name: Optional[str] = None


class ReviewedSequence(BaseModel):
    lead_email: str
    lead_name: Optional[str] = ""
    sequence_id: Optional[str] = None
    emails: List[ReviewedEmail] = Field(default_factory=list)


class SendSequencesRequest(BaseModel):
    sequences: List[ReviewedSequence] = Field(default_factory=list)


class OrchestratorState(BaseModel):
    session_id: str
    task_type: str
    input_data: Dict[str, Any]
    current_agent: str = "orchestrator"
    agent_outputs: Dict[str, AgentResponse] = Field(default_factory=dict)
    completed_agents: List[str] = Field(default_factory=list)
    failed_agents: List[str] = Field(default_factory=list)
    retry_counts: Dict[str, int] = Field(default_factory=dict)
    escalated: bool = False
    final_output: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AuditLog(BaseModel):
    log_id: str
    session_id: str
    agent_name: str
    action: str
    input_summary: str
    output_summary: str
    status: AgentStatus
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    reasoning: str = ""
    confidence: float = 0.0


class CRMAccount(BaseModel):
    account_id: str
    company: str
    contact_name: str
    email: str
    deal_value: float
    stage: str
    last_activity: str
    days_in_stage: int
    arr: float
    health_score: float
    open_tickets: int
    logins_last_30_days: int
    nps_score: float
    industry: str
    employee_count: int


class ProductCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=5000)

    @field_validator("name")
    @classmethod
    def _product_name(cls, v: str) -> str:
        cleaned = _clean_optional_text(v, max_len=200)
        if not cleaned:
            raise ValueError("Name is required")
        return cleaned

    @field_validator("description")
    @classmethod
    def _product_description(cls, v: Optional[str]) -> Optional[str]:
        return _clean_optional_text(v, max_len=5000)


class ProductUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=5000)

    @field_validator("name")
    @classmethod
    def _product_update_name(cls, v: Optional[str]) -> Optional[str]:
        return _clean_optional_text(v, max_len=200)

    @field_validator("description")
    @classmethod
    def _product_update_description(cls, v: Optional[str]) -> Optional[str]:
        return _clean_optional_text(v, max_len=5000)


class ProductResponse(BaseModel):
    product_id: str
    owner_user_id: str
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
