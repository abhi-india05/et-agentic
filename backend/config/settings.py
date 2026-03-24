from pydantic import AnyUrl, Field
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    mongodb_uri: AnyUrl = Field(..., env="MONGODB_URI")
    sendgrid_api_key: str = Field(..., env="SENDGRID_API_KEY")
    openai_model: str = Field("gpt-4o", env="OPENAI_MODEL")
    environment: str = Field("development", env="ENVIRONMENT")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    cors_origins: List[AnyUrl] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:3000"],
        env="CORS_ORIGINS",
    )
    max_retries: int = Field(2, env="MAX_RETRIES")
    retry_delay: float = Field(1.0, env="RETRY_DELAY")
    faiss_index_path: str = Field("./memory/faiss_index", env="FAISS_INDEX_PATH")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()