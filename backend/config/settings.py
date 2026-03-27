from typing import List, Optional

from pydantic import AnyUrl, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM configuration. We use the OpenAI client SDK for both native OpenAI
    # and Gemini's OpenAI-compatible endpoint.
    openai_api_key: str = Field("", env="OPENAI_API_KEY")
    gemini_api_key: Optional[str] = Field(None, env="GEMINI_API_KEY")
    llm_provider: str = Field("openai", env="LLM_PROVIDER")
    openai_base_url: Optional[str] = Field(None, env="OPENAI_BASE_URL")
    gemini_base_url: str = Field(
        "https://generativelanguage.googleapis.com/v1beta/openai/",
        env="GEMINI_BASE_URL",
    )
    mongodb_uri: AnyUrl = Field(..., env="MONGODB_URI")

    # Email (Gmail SMTP). If these aren't set, the app runs in mock-email mode.
    # For Gmail, set MAIL_PASSWORD to an App Password (recommended) rather than your normal login.
    mail_username: Optional[str] = Field(None, env="MAIL_USERNAME")
    mail_password: Optional[str] = Field(None, env="MAIL_PASSWORD")
    mail_from: Optional[str] = Field(None, env="MAIL_FROM")
    mail_server: str = Field("smtp.gmail.com", env="MAIL_SERVER")
    mail_port: int = Field(587, env="MAIL_PORT")
    mail_tls: bool = Field(True, env="MAIL_TLS")
    mail_ssl: bool = Field(False, env="MAIL_SSL")

    # Back-compat: older versions used SendGrid. We keep the setting optional so
    # existing .env files don't break, but the codebase now prefers SMTP.
    sendgrid_api_key: str = Field("mock_key", env="SENDGRID_API_KEY")

    openai_model: str = Field("gpt-4o", env="OPENAI_MODEL")
    openai_embedding_model: str = Field("text-embedding-3-small", env="OPENAI_EMBEDDING_MODEL")
    environment: str = Field("development", env="ENVIRONMENT")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    cors_origins: str = Field(
        "http://localhost:5173,http://localhost:3000",
        env="CORS_ORIGINS",
    )
    max_retries: int = Field(2, env="MAX_RETRIES")
    retry_delay: float = Field(1.0, env="RETRY_DELAY")
    faiss_index_path: str = Field("./memory/faiss_index", env="FAISS_INDEX_PATH")
    confidence_threshold: float = Field(0.6, env="CONFIDENCE_THRESHOLD")

    class Config:
        # Support running from repo root or from /backend.
        env_file = (".env", "backend/.env")
        env_file_encoding = "utf-8"

    @property
    def cors_origins_list(self) -> List[str]:
        s = (self.cors_origins or "").strip()
        if not s:
            return []
        if s.startswith("["):
            # If someone provides JSON in env, be permissive.
            import json
            try:
                v = json.loads(s)
                if isinstance(v, list):
                    return [str(x) for x in v]
            except Exception:
                pass
        return [p.strip() for p in s.split(",") if p.strip()]

    @property
    def has_openai_key(self) -> bool:
        # Back-compat property name used across the existing codebase.
        return bool(self.llm_api_key)

    @property
    def llm_api_key(self) -> str:
        provider = (self.llm_provider or "openai").strip().lower()
        if provider == "gemini":
            return (self.gemini_api_key or self.openai_api_key or "").strip()
        return (self.openai_api_key or "").strip()

    @property
    def llm_base_url(self) -> Optional[str]:
        if self.openai_base_url:
            return self.openai_base_url.strip()
        provider = (self.llm_provider or "openai").strip().lower()
        if provider == "gemini":
            return self.gemini_base_url.strip()
        return None

    @property
    def is_mock_email(self) -> bool:
        # Treat SMTP creds as the source of truth. If they're not provided, we
        # operate in mock mode and just log/store emails in memory.
        if not (self.mail_username and self.mail_password and self.mail_from):
            return True
        # Common placeholder values should not accidentally enable "live" mode.
        placeholders = ("your_", "example.com", "changeme", "test", "dummy")
        joined = " ".join([self.mail_username, self.mail_password, self.mail_from]).lower()
        return any(p in joined for p in placeholders)


settings = Settings()
