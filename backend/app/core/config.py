"""The single source of backend environment configuration."""
from pathlib import Path

from pydantic import Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # Required for the application to start safely.
    DATABASE_URL: str = Field(min_length=1)
    JWT_SECRET_KEY: str = Field(min_length=1)
    ADMIN_JWT_SECRET_KEY: str = Field(min_length=1)
    FRONTEND_ORIGINS: str = Field(min_length=1)

    MYSQL_SSL_CA: str | None = None
    FRONTEND_BASE_URL: str = "http://127.0.0.1:5173"
    OPENWEATHER_API_KEY: str = Field(min_length=1)
    # Optional: used only by the admin address-to-coordinate search endpoint.
    GOOGLE_MAPS_API_KEY: str | None = None

    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str | None = None
    SMTP_TIMEOUT_SECONDS: float = 10
    SMTP_USE_TLS: bool = True

    ENABLE_DEMO_MODELS: bool = False

    CHATBOT_PROVIDER: str = "gemini"
    CHATBOT_MODEL: str = ""
    GOOGLE_API_KEY: str | None = None
    GROQ_API_KEY: str | None = None
    OPENROUTER_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    CHATBOT_EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    CHATBOT_VECTOR_DIR: str = "chatbot_vectorstore"
    CHATBOT_KB_DIR: str = "app/chatbot/knowledge"
    CHATBOT_RATE_LIMIT: str = "20/minute"

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("FRONTEND_ORIGINS")
    @classmethod
    def validate_frontend_origins(cls, value: str) -> str:
        origins = list(dict.fromkeys(
            origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()
        ))
        if not origins:
            raise ValueError("FRONTEND_ORIGINS must contain at least one origin")
        if any(not origin.startswith(("http://", "https://")) for origin in origins):
            raise ValueError("FRONTEND_ORIGINS entries must be absolute http(s) origins")
        return ",".join(origins)

    @model_validator(mode="after")
    def validate_chatbot_provider(self):
        provider_keys = {
            "gemini": self.GOOGLE_API_KEY,
            "groq": self.GROQ_API_KEY,
            "openrouter": self.OPENROUTER_API_KEY,
            "anthropic": self.ANTHROPIC_API_KEY,
        }
        if self.CHATBOT_PROVIDER not in {"gemini", "groq", "openrouter", "anthropic", "ollama"}:
            raise ValueError("CHATBOT_PROVIDER must be gemini, groq, openrouter, anthropic or ollama")
        if self.CHATBOT_PROVIDER != "ollama" and not provider_keys[self.CHATBOT_PROVIDER]:
            raise ValueError(f"A provider credential is required for CHATBOT_PROVIDER={self.CHATBOT_PROVIDER}")
        return self

    @property
    def frontend_origins(self) -> list[str]:
        return [origin for origin in self.FRONTEND_ORIGINS.split(",") if origin]


try:
    settings = Settings()
except ValidationError as exc:
    missing = sorted({str(error["loc"][0]) for error in exc.errors() if error["type"] == "missing"})
    if missing:
        raise RuntimeError(
            "Required backend settings are missing: " + ", ".join(missing)
            + f". Configure them in {BASE_DIR / '.env'} or the deployment environment."
        ) from None
    fields = sorted({str(error["loc"][0]) if error["loc"] else "CHATBOT_PROVIDER" for error in exc.errors()})
    raise RuntimeError(
        "Backend configuration contains invalid values for: " + ", ".join(fields)
        + ". Check backend/.env or the deployment environment."
    ) from None
