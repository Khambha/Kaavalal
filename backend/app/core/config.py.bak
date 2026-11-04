
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


# backend/ directory
BASE_DIR = Path(__file__).resolve().parents[2]

# Settings are also read directly with os.getenv() in several modules.
# Load backend/.env into the process environment before those modules import.
load_dotenv(BASE_DIR / ".env")


class Settings(BaseSettings):
    DATABASE_URL: str
    MYSQL_SSL_CA: str | None = None

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
