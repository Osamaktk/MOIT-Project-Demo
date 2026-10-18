from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / "backend" / ".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "demo"
    secret_key: SecretStr = SecretStr("local-development-only-change-this-key")
    database_url: str = "sqlite:///data/app.db"
    data_dir: str = "data"
    access_token_minutes: int = Field(default=30, ge=5, le=1440)
    cors_origins: list[str] = ["http://localhost:5173"]
    ai_zone_mode: str = "cloud"
    ai_provider_chat: str = ""
    ai_provider_reasoning: str = ""
    ai_provider_extraction: str = ""
    ai_provider_fast: str = ""
    ai_provider_embedding: str = ""
    allow_cloud_for_synthetic_demo: bool = True
    openrouter_api_key: SecretStr = SecretStr("")
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    local_llm_base_url: str = "http://localhost:11434/v1"
    model_chat: str = ""
    model_reasoning: str = ""
    model_extraction: str = ""
    model_fast: str = ""
    model_fallback: str = ""
    model_embedding: str = ""
    model_chat_fallback: str = ""
    model_reasoning_fallback: str = ""
    model_extraction_fallback: str = ""
    model_fast_fallback: str = ""
    ai_request_timeout_seconds: int = Field(default=45, ge=1, le=300)
    ai_max_retries: int = Field(default=2, ge=0, le=5)
    log_prompts: bool = False
    demo_mode_cache: bool = False
    stt_provider: str = "faster_whisper"
    stt_model_size: str = "small"
    embedding_provider: str = "local"
    embedding_model: str = ""

    @field_validator("database_url")
    @classmethod
    def resolve_sqlite_path(cls, value: str) -> str:
        prefix = "sqlite:///"
        if value.startswith(prefix) and not value.startswith("sqlite:////") and value[len(prefix):] != ":memory:":
            db_path = (REPO_ROOT / value[len(prefix):]).resolve()
            db_path.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{db_path.as_posix()}"
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.lstrip().startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("ai_zone_mode")
    @classmethod
    def validate_ai_zone(cls, value: str) -> str:
        zone = value.strip().lower()
        if zone not in {"cloud", "local"}:
            raise ValueError("AI_ZONE_MODE must be 'cloud' or 'local'")
        return zone

    @property
    def resolved_data_dir(self) -> Path:
        path = Path(self.data_dir)
        return (REPO_ROOT / path).resolve() if not path.is_absolute() else path


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
